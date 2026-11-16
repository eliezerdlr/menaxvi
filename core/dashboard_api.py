"""Secure, persistent application service for the MENAXVI dashboard.

The service keeps HTTP concerns out of the governance core.  It reuses the
catalog, policy, evidence, manual-plan, retry, and rollback contracts instead of
reimplementing their decisions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from core.evidence import EvidenceLog, GovernedExecution, ToolSelection
from core.loader import CatalogLoader
from core.policy import (
    AuthorizationArtifact,
    DigestApprovalVerifier,
    DigestAuthorizationVerifier,
    ExecutionRequest,
    HumanApproval,
    PolicyEngine,
)
from menaxvi.manual import record_results, render_plan
from menaxvi.recovery import create_retry_plan, create_rollback_plan


class DashboardError(ValueError):
    """A safe error that may be returned to a dashboard client."""


class AuthenticationError(DashboardError):
    pass


class NotFoundError(DashboardError):
    pass


class ConflictError(DashboardError):
    pass


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


class _Connection(sqlite3.Connection):
    """SQLite connection whose context manager also releases the descriptor."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


class DashboardService:
    """Authenticated workspace and execution API backed by SQLite."""

    def __init__(self, project_root: str | Path, database: str | Path, evidence_dir: str | Path):
        self.project_root = Path(project_root).resolve()
        self.database = Path(database)
        self.evidence_dir = Path(evidence_dir)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, factory=_Connection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    expires_at TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
                    name TEXT NOT NULL, business_context TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    document TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
                    plan_id TEXT NOT NULL REFERENCES plans(id), status TEXT NOT NULL,
                    authorization TEXT NOT NULL, record TEXT, artifact TEXT, failure TEXT,
                    evidence_path TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES executions(id),
                    gate_id TEXT NOT NULL, document TEXT NOT NULL,
                    UNIQUE(execution_id, gate_id)
                );
                """
            )

    @staticmethod
    def _password_hash(password: str, *, salt: bytes | None = None) -> str:
        if len(password) < 12:
            raise DashboardError("password must contain at least 12 characters")
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
        return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"

    @staticmethod
    def _password_matches(password: str, encoded: str) -> bool:
        try:
            algorithm, rounds, salt, expected = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
            ).hex()
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    def register(self, email: str, password: str) -> dict[str, str]:
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise DashboardError("email must be valid")
        user_id = f"usr_{secrets.token_hex(12)}"
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?)",
                    (user_id, normalized, self._password_hash(password), _iso(_now())),
                )
        except sqlite3.IntegrityError as error:
            raise ConflictError("account already exists") from error
        return {"id": user_id, "email": normalized}

    def login(self, email: str, password: str, *, lifetime: timedelta = timedelta(hours=12)) -> str:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
            if row is None or not self._password_matches(password, row["password_hash"]):
                raise AuthenticationError("invalid email or password")
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), row["id"], _iso(_now() + lifetime), _iso(_now())),
            )
        return token

    def logout(self, token: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))

    def _user(self, db: sqlite3.Connection, token: str) -> sqlite3.Row:
        row = db.execute(
            """SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
            (hashlib.sha256(token.encode()).hexdigest(), _iso(_now())),
        ).fetchone()
        if row is None:
            raise AuthenticationError("session is missing or expired")
        return row

    def create_workspace(self, token: str, name: str, business_context: Mapping[str, Any]) -> dict[str, Any]:
        if not name.strip() or not isinstance(business_context, Mapping):
            raise DashboardError("workspace name and business context are required")
        workspace_id = f"wsp_{secrets.token_hex(12)}"
        timestamp = _iso(_now())
        with self._connect() as db:
            user = self._user(db, token)
            db.execute(
                "INSERT INTO workspaces VALUES (?, ?, ?, ?, ?, ?)",
                (workspace_id, user["id"], name.strip(), _json(dict(business_context)), timestamp, timestamp),
            )
        return self.get_workspace(token, workspace_id)

    def get_workspace(self, token: str, workspace_id: str) -> dict[str, Any]:
        with self._connect() as db:
            user = self._user(db, token)
            row = db.execute(
                "SELECT * FROM workspaces WHERE id = ? AND owner_id = ?", (workspace_id, user["id"])
            ).fetchone()
            if row is None:
                raise NotFoundError("workspace not found")
            return {"id": row["id"], "name": row["name"], "businessContext": json.loads(row["business_context"])}

    def catalog(self, token: str, *, kind: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as db:
            self._user(db, token)
        catalog = CatalogLoader(self.project_root).load()
        resources = catalog.resources_by_kind.get(kind, ()) if kind else catalog.resources.values()
        return [
            {"reference": item.key, "kind": item.kind, "id": item.resource_id, "version": item.version,
             "title": item.document.get("metadata", {}).get("title")}
            for item in resources
        ]

    def create_plan(self, token: str, workspace_id: str, workflow_ref: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
        self.get_workspace(token, workspace_id)
        execution_id = f"exe_{secrets.token_hex(12)}"
        document = render_plan(self.project_root, workflow_ref, execution_id, inputs)
        plan_id = f"pln_{secrets.token_hex(12)}"
        with self._connect() as db:
            self._user(db, token)
            db.execute("INSERT INTO plans VALUES (?, ?, ?, ?)", (plan_id, workspace_id, _json(document), _iso(_now())))
        return {"id": plan_id, "document": document}

    def create_execution(self, token: str, workspace_id: str, plan_id: str, authorization: AuthorizationArtifact) -> dict[str, Any]:
        self.get_workspace(token, workspace_id)
        with self._connect() as db:
            self._user(db, token)
            plan_row = db.execute("SELECT * FROM plans WHERE id = ? AND workspace_id = ?", (plan_id, workspace_id)).fetchone()
            if plan_row is None:
                raise NotFoundError("plan not found")
            plan = json.loads(plan_row["document"])
            execution_id = plan["executionId"]
            if authorization.subject != f"workspace:{workspace_id}":
                raise DashboardError("authorization subject must match the workspace")
            timestamp = _iso(_now())
            evidence_path = str(self.evidence_dir / f"{execution_id}.jsonl")
            db.execute(
                "INSERT INTO executions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (execution_id, workspace_id, plan_id, "awaiting_approval", _json(authorization.canonical_payload()),
                 None, None, None, evidence_path, timestamp, timestamp),
            )
        return self.get_execution(token, execution_id)

    def approve(self, token: str, execution_id: str, gate_id: str, *, approved: bool = True,
                valid_for: timedelta = timedelta(hours=24)) -> dict[str, Any]:
        with self._connect() as db:
            user = self._user(db, token)
            execution = self._owned_execution(db, user["id"], execution_id)
            plan = self._plan(db, execution["plan_id"])
            human_gates = {gate["id"] for gate in plan.get("gates", []) if gate.get("type") == "human"}
            if gate_id not in human_gates:
                raise DashboardError("human approval gate does not exist")
            now = _now()
            approval = HumanApproval(
                approval_id=f"apr_{secrets.token_hex(12)}", execution_id=execution_id, gate_id=gate_id,
                approved_by=f"user:{user['id']}", approved_at=now, valid_until=now + valid_for, approved=approved,
            )
            db.execute("INSERT INTO approvals VALUES (?, ?, ?, ?)",
                       (approval.approval_id, execution_id, gate_id, _json(approval.canonical_payload())))
            db.execute("UPDATE executions SET status = ?, updated_at = ? WHERE id = ?",
                       ("ready" if approved else "rejected", _iso(now), execution_id))
        return approval.canonical_payload() | {"digest": approval.digest}

    def execute(self, token: str, execution_id: str, results: Mapping[str, Any]) -> dict[str, Any]:
        with self._connect() as db:
            user = self._user(db, token)
            execution = self._owned_execution(db, user["id"], execution_id)
            plan = self._plan(db, execution["plan_id"])
            authorization = self._authorization(json.loads(execution["authorization"]))
            approvals = tuple(self._approval(row) for row in db.execute(
                "SELECT document FROM approvals WHERE execution_id = ?", (execution_id,)
            ))
            request = ExecutionRequest(
                execution_id=execution_id, actor=f"workspace:{execution['workspace_id']}", action="execute workflow",
                target=f"workflow:{plan['workflow']['id']}@{plan['workflow']['version']}", technique="manual",
                inputs=plan.get("inputs", {}), resource_versions={"workflow": plan["workflow"]["version"]},
                required_human_gates=tuple(gate["id"] for gate in plan.get("gates", []) if gate.get("type") == "human"),
            )
            policy = PolicyEngine(DigestAuthorizationVerifier(frozenset({authorization.digest})),
                                  DigestApprovalVerifier(frozenset(item.digest for item in approvals)))
            governed = GovernedExecution(policy, EvidenceLog(execution["evidence_path"]))
            try:
                prepared = governed.prepare(request, authorization, approvals,
                                            lambda _request: ToolSelection("manual", "record-results", "1"))
                record = record_results(plan, results)
                governed.record_output(prepared, record, output_version="1")
            except Exception as error:
                safe_failure = {"type": type(error).__name__, "message": str(error)}
                db.execute("UPDATE executions SET status = 'failed', failure = ?, updated_at = ? WHERE id = ?",
                           (_json(safe_failure), _iso(_now()), execution_id))
                db.commit()
                raise DashboardError(str(error)) from error
            artifact = {"executionId": execution_id, "outputs": record["results"]["outputs"], "recordDigest": record["recordDigest"]}
            db.execute("UPDATE executions SET status = ?, record = ?, artifact = ?, failure = NULL, updated_at = ? WHERE id = ?",
                       (record["status"], _json(record), _json(artifact), _iso(_now()), execution_id))
        return self.get_execution(token, execution_id)

    def retry(self, token: str, execution_id: str) -> dict[str, Any]:
        with self._connect() as db:
            user = self._user(db, token)
            execution = self._owned_execution(db, user["id"], execution_id)
            if execution["record"] is None:
                raise ConflictError("execution has no immutable result record to retry")
            retry_plan = create_retry_plan(self._plan(db, execution["plan_id"]), json.loads(execution["record"]),
                                           f"exe_{secrets.token_hex(12)}")
            plan_id = f"pln_{secrets.token_hex(12)}"
            db.execute("INSERT INTO plans VALUES (?, ?, ?, ?)", (plan_id, execution["workspace_id"], _json(retry_plan), _iso(_now())))
        return {"id": plan_id, "document": retry_plan}

    def rollback(self, token: str, execution_id: str, reason: str) -> dict[str, Any]:
        with self._connect() as db:
            user = self._user(db, token)
            execution = self._owned_execution(db, user["id"], execution_id)
            if execution["record"] is None:
                raise ConflictError("execution has no immutable result record to roll back")
            return create_rollback_plan(self._plan(db, execution["plan_id"]), json.loads(execution["record"]), reason)

    def get_execution(self, token: str, execution_id: str) -> dict[str, Any]:
        with self._connect() as db:
            user = self._user(db, token)
            row = self._owned_execution(db, user["id"], execution_id)
            evidence = EvidenceLog(row["evidence_path"])
            return {"id": row["id"], "workspaceId": row["workspace_id"], "status": row["status"],
                    "record": json.loads(row["record"]) if row["record"] else None,
                    "artifact": json.loads(row["artifact"]) if row["artifact"] else None,
                    "failure": json.loads(row["failure"]) if row["failure"] else None,
                    "evidence": [event.__dict__ for event in evidence.events()],
                    "evidenceValid": evidence.verify().valid}

    @staticmethod
    def _owned_execution(db: sqlite3.Connection, user_id: str, execution_id: str) -> sqlite3.Row:
        row = db.execute(
            """SELECT executions.* FROM executions JOIN workspaces ON workspaces.id = executions.workspace_id
               WHERE executions.id = ? AND workspaces.owner_id = ?""", (execution_id, user_id)
        ).fetchone()
        if row is None:
            raise NotFoundError("execution not found")
        return row

    @staticmethod
    def _plan(db: sqlite3.Connection, plan_id: str) -> dict[str, Any]:
        row = db.execute("SELECT document FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if row is None:
            raise NotFoundError("plan not found")
        return json.loads(row["document"])

    @staticmethod
    def _authorization(value: Mapping[str, Any]) -> AuthorizationArtifact:
        return AuthorizationArtifact(
            authorization_id=value["authorization_id"], subject=value["subject"], targets=tuple(value["targets"]),
            techniques=tuple(value["techniques"]), valid_from=_parse(value["valid_from"]),
            valid_until=_parse(value["valid_until"]), approved_by=tuple(value["approved_by"]),
            impact_limits=tuple(value["impact_limits"]), stop_conditions=tuple(value["stop_conditions"]),
            version=value["version"],
        )

    @staticmethod
    def _approval(row: sqlite3.Row) -> HumanApproval:
        value = json.loads(row["document"])
        return HumanApproval(
            approval_id=value["approval_id"], execution_id=value["execution_id"], gate_id=value["gate_id"],
            approved_by=value["approved_by"], approved_at=_parse(value["approved_at"]),
            valid_until=_parse(value["valid_until"]), approved=value["approved"], version=value["version"],
        )
