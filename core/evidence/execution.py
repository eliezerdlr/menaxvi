"""Execution boundary that enforces policy before tool selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from core.policy import (
    AuthorizationArtifact,
    ExecutionRequest,
    HumanApproval,
    PolicyDecision,
    PolicyEngine,
)

from .log import EvidenceLog


class AuthorizationDenied(PermissionError):
    """Raised when a request fails authorization or a required human gate."""

    def __init__(self, decision: PolicyDecision):
        self.decision = decision
        detail = "; ".join(decision.reasons) or "policy denied the request"
        super().__init__(detail)


@dataclass(frozen=True)
class ToolSelection:
    adapter: str
    tool: str
    version: str

    def __post_init__(self) -> None:
        for field_name in ("adapter", "tool", "version"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")


@dataclass(frozen=True)
class PreparedExecution:
    request: ExecutionRequest
    decision: PolicyDecision
    selection: ToolSelection


class GovernedExecution:
    """Authorize, record, and only then call an adapter/tool selector."""

    def __init__(
        self,
        policy: PolicyEngine,
        evidence: EvidenceLog,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._policy = policy
        self._evidence = evidence
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prepare(
        self,
        request: ExecutionRequest,
        authorization: AuthorizationArtifact | None,
        approvals: Sequence[HumanApproval],
        selector: Callable[[ExecutionRequest], ToolSelection],
    ) -> PreparedExecution:
        self._evidence.append(
            request.execution_id,
            "execution_started",
            {
                "actor": request.actor,
                "action": request.action,
                "target": request.target,
                "technique": request.technique,
                "inputs": request.inputs,
                "resource_versions": request.resource_versions,
                "policy_version": request.policy_version,
            },
        )

        decision = self._policy.evaluate(
            request, authorization, approvals, now=self._clock()
        )
        for gate in decision.gate_decisions:
            self._evidence.append(
                request.execution_id,
                "gate_evaluated",
                {
                    "gate_type": gate.gate_type,
                    "gate_id": gate.gate_id,
                    "allowed": gate.allowed,
                    "reason": gate.reason,
                    "approval_id": gate.approval_id,
                    "approval_version": gate.approval_version,
                    "approval_digest": gate.approval_digest,
                    "approved_by": gate.approved_by,
                },
            )
        self._evidence.append(
            request.execution_id,
            "policy_decision",
            {
                "allowed": decision.allowed,
                "code": decision.code,
                "reasons": decision.reasons,
                "evaluated_at": decision.evaluated_at,
                "authorization_id": decision.authorization_id,
                "authorization_version": decision.authorization_version,
                "authorization_digest": decision.authorization_digest,
                "authorization_approved_by": decision.authorization_approved_by,
                "policy_version": decision.policy_version,
            },
        )

        if not decision.allowed:
            raise AuthorizationDenied(decision)

        try:
            selection = selector(request)
            if not isinstance(selection, ToolSelection):
                raise TypeError("selector must return ToolSelection")
        except Exception as error:
            self._evidence.append(
                request.execution_id,
                "tool_selection_failed",
                {"error_type": type(error).__name__, "message": "tool selection failed"},
            )
            raise

        self._evidence.append(
            request.execution_id,
            "tool_selected",
            {
                "adapter": selection.adapter,
                "tool": selection.tool,
                "version": selection.version,
            },
        )
        return PreparedExecution(request, decision, selection)

    def record_output(
        self,
        prepared: PreparedExecution,
        output: Mapping[str, Any],
        *,
        output_version: str,
    ) -> None:
        if not output_version.strip():
            raise ValueError("output_version must not be empty")
        self._evidence.append(
            prepared.request.execution_id,
            "output_recorded",
            {
                "output": output,
                "output_version": output_version,
                "adapter": prepared.selection.adapter,
                "tool": prepared.selection.tool,
                "tool_version": prepared.selection.version,
            },
        )
