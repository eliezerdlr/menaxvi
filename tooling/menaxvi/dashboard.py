"""Dependency-free local customer dashboard with durable, governed workflow state."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import uuid
from dataclasses import dataclass
from importlib.resources import files
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from menaxvi.manual import ManualWorkflowError, record_results, render_plan
from menaxvi.recovery import create_retry_plan, create_rollback_plan

WORKFLOW = "workflow.reviewed-campaign-message@1.0.0"
SESSION_COOKIE = "menaxvi_session"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _password_hash(password: str, salt: bytes | None = None) -> str:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters.")
    salt = salt or os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${derived.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
        )
        return hmac.compare_digest(actual.hex(), expected)
    except (TypeError, ValueError):
        return False


class DashboardError(ValueError):
    """Actionable customer-safe dashboard error."""


@dataclass
class JsonStore:
    path: Path

    def __post_init__(self) -> None:
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"schema": "menaxvi.dashboard/v1", "users": {}, "workspaces": {}, "executions": {}})

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("dashboard data store is unavailable") from error
        if not isinstance(value, dict) or value.get("schema") != "menaxvi.dashboard/v1":
            raise RuntimeError("dashboard data store has an unsupported format")
        return value

    def _write(self, value: Mapping[str, Any]) -> None:
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)

    def view(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def update(self, operation: Any) -> Any:
        with self._lock:
            data = self._read()
            result = operation(data)
            self._write(data)
            return result


class DashboardService:
    """Own dashboard state transitions while reusing core workflow invariants."""

    def __init__(self, root: Path, data_path: Path):
        self.root = root.resolve()
        self.store = JsonStore(data_path)
        self.sessions: dict[str, str] = {}
        self._session_lock = threading.Lock()

    def register(self, email: str, password: str) -> str:
        normalized = email.strip().lower()
        if "@" not in normalized or len(normalized) > 254:
            raise DashboardError("Enter a valid email address.")
        try:
            encoded = _password_hash(password)
        except ValueError as error:
            raise DashboardError(str(error)) from error

        def save(data: dict[str, Any]) -> None:
            if normalized in data["users"]:
                raise DashboardError("An account already exists for this email.")
            data["users"][normalized] = {"passwordHash": encoded, "createdAt": _now()}

        self.store.update(save)
        return self.login(normalized, password)

    def login(self, email: str, password: str) -> str:
        normalized = email.strip().lower()
        user = self.store.view()["users"].get(normalized)
        if not user or not _password_matches(password, user.get("passwordHash", "")):
            raise DashboardError("Email or password is incorrect.")
        token = secrets.token_urlsafe(32)
        with self._session_lock:
            self.sessions[token] = normalized
        return token

    def logout(self, token: str) -> None:
        with self._session_lock:
            self.sessions.pop(token, None)

    def user_for(self, token: str | None) -> str | None:
        if not token:
            return None
        with self._session_lock:
            return self.sessions.get(token)

    def state(self, email: str) -> dict[str, Any]:
        data = self.store.view()
        workspaces = [value for value in data["workspaces"].values() if value["owner"] == email]
        executions = [value for value in data["executions"].values() if value["owner"] == email]
        executions.sort(key=lambda item: item["createdAt"], reverse=True)
        return {"email": email, "workspaces": workspaces, "executions": executions, "modules": [{"id": WORKFLOW, "title": "Reviewed campaign message", "status": "approved"}]}

    @staticmethod
    def _split_claim_evidence(value: str) -> tuple[str, str]:
        sections: dict[str, list[str]] = {"claim": [], "evidence": []}
        current: str | None = None
        for raw_line in value.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            normalized = line.casefold()
            matched = False
            for section, labels in {
                "claim": ("claim:", "alegação:", "alegacao:"),
                "evidence": ("evidence:", "evidência:", "evidencia:"),
            }.items():
                for label in labels:
                    if normalized.startswith(label):
                        current = section
                        content = line[len(label):].strip()
                        if content:
                            sections[section].append(content)
                        matched = True
                        break
                if matched:
                    break
            if not matched and current:
                sections[current].append(line)
        return " ".join(sections["claim"]), " ".join(sections["evidence"])

    @staticmethod
    def _language_consistent(text: str, language: str) -> bool:
        normalized = f" {text.casefold()} "
        forbidden = {
            "pt-BR": (" for ", " reply ", " request ", " next step ", " the ", " with "),
            "en": (" para ", " responda ", " solicitar ", " próximo passo ", " você ", " evidência "),
        }
        return not any(marker in normalized for marker in forbidden[language])

    @classmethod
    def _quality_review(
        cls, context: Mapping[str, str], draft: str, claim: str, evidence: str
    ) -> dict[str, str]:
        language = context["language"]
        consistent = cls._language_consistent(draft, language)
        expected_action = "responda para solicitar" if language == "pt-BR" else "reply to request"
        checks = {
            "audience": context["audience"].casefold() in draft.casefold() and consistent,
            "outcome": context["offer"].casefold() in draft.casefold() and consistent,
            "evidence": bool(claim and evidence),
            "action": expected_action in draft.casefold() and consistent,
        }
        review = {key: "pass" if passed else "fail" for key, passed in checks.items()}
        review["overall"] = "pass" if all(checks.values()) else "fail"
        return review

    def create_workspace(self, email: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        required = ("company", "audience", "offer", "brand", "channels", "language", "claims", "constraints", "approvalOwners")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise DashboardError(f"Complete the required onboarding field: {missing[0]}.")
        if str(payload["language"]).strip() not in {"pt-BR", "en"}:
            raise DashboardError("Choose a supported output language: pt-BR or en.")
        claim, evidence = self._split_claim_evidence(str(payload["claims"]))
        if not claim or not evidence:
            raise DashboardError("Enter separate Claim and Evidence sections in the onboarding field.")
        workspace_id = f"ws-{uuid.uuid4().hex[:12]}"
        workspace = {
            "id": workspace_id,
            "owner": email,
            "createdAt": _now(),
            "updatedAt": _now(),
            "context": {key: str(payload[key]).strip() for key in required},
        }
        self.store.update(lambda data: data["workspaces"].__setitem__(workspace_id, workspace))
        return workspace

    def create_plan(self, email: str, workspace_id: str) -> dict[str, Any]:
        data = self.store.view()
        workspace = data["workspaces"].get(workspace_id)
        if not workspace or workspace["owner"] != email:
            raise DashboardError("Select a workspace that belongs to your account.")
        execution_id = f"run-{uuid.uuid4().hex[:12]}"
        context = workspace["context"]
        claim, evidence = self._split_claim_evidence(context["claims"])
        inputs = {
            "brief": {
                "company": context["company"], "audience": context["audience"],
                "offer": context["offer"], "brand": context["brand"],
                "channels": context["channels"], "constraints": context["constraints"],
            },
            "evidence": [{"id": "customer-claims", "statement": evidence, "source": "customer onboarding"}],
        }
        try:
            plan = render_plan(self.root, WORKFLOW, execution_id, inputs)
        except ManualWorkflowError as error:
            raise DashboardError(f"The selected module cannot be planned: {error}") from error
        execution = {
            "id": execution_id, "owner": email, "workspaceId": workspace_id,
            "createdAt": _now(), "updatedAt": _now(), "status": "plan-review",
            "plan": plan, "record": None, "artifact": None, "rollback": None,
            "evidence": [self._event("plan_created", {"planDigest": plan["planDigest"], "workflow": plan["workflow"], "inputs": plan["inputs"]})],
        }
        self.store.update(lambda store: store["executions"].__setitem__(execution_id, execution))
        return execution

    def execute(self, email: str, execution_id: str, *, fail: bool = False) -> dict[str, Any]:
        def operation(data: dict[str, Any]) -> dict[str, Any]:
            execution = self._owned(data, email, execution_id)
            if execution["status"] not in {"plan-review", "retry-ready"}:
                raise DashboardError("This execution is not ready to run.")
            plan = execution["plan"]
            if fail:
                results = {"executionId": execution_id, "nodes": [{"id": "draft-and-review", "status": "failed", "error": "Controlled validation failure"}], "gates": [{"id": "human-approval", "status": "not-run", "reason": "node failed"}], "outputs": {}, "residualRisks": ["Controlled validation failure; no artifact was published."]}
                record = record_results(plan, results)
                execution["status"] = "failed"
                execution["record"] = record
                execution["evidence"].append(self._event("validation_failed", {"message": "The draft did not pass controlled validation.", "recordDigest": record["recordDigest"]}))
            else:
                context = data["workspaces"][execution["workspaceId"]]["context"]
                artifact = self._draft_outputs(context)
                node_outputs = {"message-draft": artifact["draft"], "claim-ledger": artifact["claimLedger"], "quality-review": artifact["qualityReview"]}
                validation = {"executionId": execution_id, "nodes": [{"id": "draft-and-review", "status": "completed", "outputs": node_outputs}], "gates": [{"id": "human-approval", "status": "not-run", "reason": "awaiting human review"}], "outputs": {}, "residualRisks": ["Human approval is required before handoff."]}
                try:
                    record_results(plan, validation)
                except ManualWorkflowError as error:
                    raise DashboardError(f"Generated output failed contract validation: {error}") from error
                execution["status"] = "awaiting-approval"
                execution["artifact"] = artifact
                execution["evidence"].append(self._event("output_recorded", {"artifactDigest": _digest(artifact), "output": artifact}))
            execution["updatedAt"] = _now()
            return execution
        return self.store.update(operation)

    def approve(self, email: str, execution_id: str) -> dict[str, Any]:
        def operation(data: dict[str, Any]) -> dict[str, Any]:
            execution = self._owned(data, email, execution_id)
            if execution["status"] != "awaiting-approval" or not execution["artifact"]:
                raise DashboardError("Generate and review the draft outputs before deciding the gate.")
            context = data["workspaces"][execution["workspaceId"]]["context"]
            required_checks = ("audience", "outcome", "evidence", "action", "overall")
            quality = execution["artifact"].get("qualityReview", {})
            if any(quality.get(check) != "pass" for check in required_checks):
                raise DashboardError("The quality review must pass before human approval.")
            artifact = {**execution["artifact"], "gateDecision": "approve_draft"}
            node_outputs = {"message-draft": artifact["draft"], "claim-ledger": artifact["claimLedger"], "quality-review": artifact["qualityReview"]}
            results = {"executionId": execution_id, "nodes": [{"id": "draft-and-review", "status": "completed", "outputs": node_outputs}], "gates": [{"id": "human-approval", "status": "passed", "decision": "approve_draft", "decidedBy": context["approvalOwners"], "evidence": "dashboard-review-confirmation"}], "outputs": {"reviewed-message-package": artifact}, "residualRisks": ["The local dashboard does not publish content."]}
            try:
                record = record_results(execution["plan"], results)
            except ManualWorkflowError as error:
                raise DashboardError(f"Generated output failed contract validation: {error}") from error
            execution["status"] = "completed"
            execution["record"] = record
            execution["artifact"] = artifact
            execution["evidence"].append(self._event("gate_decided", {"gate": "human-approval", "decision": "approve_draft", "decidedBy": context["approvalOwners"]}))
            execution["updatedAt"] = _now()
            return execution
        return self.store.update(operation)

    @classmethod
    def _draft_outputs(cls, context: Mapping[str, str]) -> dict[str, Any]:
        claim, evidence = cls._split_claim_evidence(context["claims"])
        if context["language"] == "pt-BR":
            draft = f"{context['offer']} para {context['audience']}. {claim} Responda para solicitar o próximo passo revisado."
        else:
            draft = f"{context['offer']} for {context['audience']}. {claim} Reply to request the reviewed next step."
        return {
            "draft": draft,
            "claimLedger": [{"claim": claim, "evidenceRef": "customer-claims"}],
            "qualityReview": cls._quality_review(context, draft, claim, evidence),
        }

    def retry(self, email: str, execution_id: str) -> dict[str, Any]:
        def operation(data: dict[str, Any]) -> dict[str, Any]:
            prior = self._owned(data, email, execution_id)
            if prior["status"] != "failed" or not prior["record"]:
                raise DashboardError("Only a failed execution can be retried.")
            new_id = f"run-{uuid.uuid4().hex[:12]}"
            try:
                plan = create_retry_plan(prior["plan"], prior["record"], new_id)
            except ManualWorkflowError as error:
                raise DashboardError(str(error)) from error
            execution = {"id": new_id, "owner": email, "workspaceId": prior["workspaceId"], "createdAt": _now(), "updatedAt": _now(), "status": "retry-ready", "plan": plan, "record": None, "artifact": None, "rollback": None, "evidence": prior["evidence"] + [self._event("retry_created", {"previousExecutionId": execution_id, "previousRecordDigest": prior["record"]["recordDigest"], "planDigest": plan["planDigest"]})]}
            data["executions"][new_id] = execution
            return execution
        return self.store.update(operation)

    def rollback(self, email: str, execution_id: str, reason: str) -> dict[str, Any]:
        def operation(data: dict[str, Any]) -> dict[str, Any]:
            execution = self._owned(data, email, execution_id)
            if not execution["record"]:
                raise DashboardError("Run the workflow before creating a rollback plan.")
            try:
                rollback = create_rollback_plan(execution["plan"], execution["record"], reason)
            except ManualWorkflowError as error:
                raise DashboardError(str(error)) from error
            execution["rollback"] = rollback
            execution["status"] = "rolled-back"
            execution["updatedAt"] = _now()
            execution["evidence"].append(self._event("rollback_created", {"rollbackDigest": rollback["rollbackDigest"], "reason": rollback["reason"], "automaticActionsPerformed": False}))
            return execution
        return self.store.update(operation)

    @staticmethod
    def _event(event_type: str, data: Mapping[str, Any]) -> dict[str, Any]:
        body = {"timestamp": _now(), "type": event_type, "data": dict(data)}
        return {**body, "digest": _digest(body)}

    @staticmethod
    def _owned(data: Mapping[str, Any], email: str, execution_id: str) -> dict[str, Any]:
        execution = data["executions"].get(execution_id)
        if not execution or execution["owner"] != email:
            raise DashboardError("Execution was not found.")
        return execution


def dashboard_handler(service: DashboardService, html: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "MENAXVI-Dashboard/0.1"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _token(self) -> str | None:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            morsel = cookie.get(SESSION_COOKIE)
            return morsel.value if morsel else None

        def _json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1_000_000:
                    raise DashboardError("Request is too large.")
                value = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(value, dict):
                    raise DashboardError("Request body must be a JSON object.")
                return value
            except (ValueError, json.JSONDecodeError) as error:
                raise DashboardError("Request body contains invalid JSON.") from error

        def _send(self, status: int, payload: object, *, cookie: str | None = None) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)

        def _user(self) -> str:
            user = service.user_for(self._token())
            if not user:
                raise PermissionError
            return user

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
                self.end_headers(); self.wfile.write(body); return
            try:
                if path == "/api/state":
                    self._send(200, service.state(self._user())); return
                self._send(404, {"error": "Not found."})
            except PermissionError:
                self._send(401, {"error": "Sign in to continue."})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                payload = self._json()
                if path == "/api/register":
                    token = service.register(str(payload.get("email", "")), str(payload.get("password", "")))
                    self._send(201, {"ok": True}, cookie=f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict"); return
                if path == "/api/login":
                    token = service.login(str(payload.get("email", "")), str(payload.get("password", "")))
                    self._send(200, {"ok": True}, cookie=f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict"); return
                if path == "/api/logout":
                    service.logout(self._token() or "")
                    self._send(200, {"ok": True}, cookie=f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"); return
                user = self._user()
                if path == "/api/workspaces": self._send(201, service.create_workspace(user, payload)); return
                if path == "/api/plans": self._send(201, service.create_plan(user, str(payload.get("workspaceId", "")))); return
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "executions":
                    execution_id, action = parts[2], parts[3]
                    if action == "execute": self._send(200, service.execute(user, execution_id, fail=bool(payload.get("controlledFailure")))); return
                    if action == "approve": self._send(200, service.approve(user, execution_id)); return
                    if action == "retry": self._send(201, service.retry(user, execution_id)); return
                    if action == "rollback": self._send(200, service.rollback(user, execution_id, str(payload.get("reason", "")))); return
                self._send(404, {"error": "Not found."})
            except PermissionError:
                self._send(401, {"error": "Sign in to continue."})
            except DashboardError as error:
                self._send(400, {"error": str(error)})
            except Exception:
                self._send(500, {"error": "The dashboard could not complete the request. Your saved state was preserved."})

    return Handler


def serve_dashboard(root: Path, data_path: Path, host: str, port: int) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise DashboardError("The pre-alpha dashboard only supports a loopback host.")
    html = files(__package__).joinpath("dashboard.html").read_text(encoding="utf-8")
    service = DashboardService(root, data_path)
    server = ThreadingHTTPServer((host, port), dashboard_handler(service, html))
    print(f"MENAXVI dashboard: http://{host}:{server.server_port}")
    print(f"Persistent data: {data_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
