"""Policy primitives for governed MENAXVI execution.

The engine is intentionally independent of adapters and model providers. It makes
one fail-closed decision from a validated authorization artifact and any required
human approvals. Tool selection belongs to ``core.evidence.execution`` and only
runs after this decision allows the request.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _nonempty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _string_tuple(values: Sequence[str], field_name: str, *, required: bool = False) -> tuple[str, ...]:
    normalized = tuple(_nonempty(value, field_name) for value in values)
    if required and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class AuthorizationArtifact:
    """Documented authorization whose digest is trusted out of band.

    ``impact_limits`` and ``stop_conditions`` are mandatory so a broad target and
    technique grant cannot silently become unconstrained authorization.
    """

    authorization_id: str
    subject: str
    targets: tuple[str, ...]
    techniques: tuple[str, ...]
    valid_from: datetime
    valid_until: datetime
    approved_by: tuple[str, ...]
    impact_limits: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    version: str = "1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "authorization_id", _nonempty(self.authorization_id, "authorization_id"))
        object.__setattr__(self, "subject", _nonempty(self.subject, "subject"))
        object.__setattr__(self, "version", _nonempty(self.version, "version"))
        object.__setattr__(self, "targets", _string_tuple(self.targets, "targets", required=True))
        object.__setattr__(self, "techniques", _string_tuple(self.techniques, "techniques", required=True))
        object.__setattr__(self, "approved_by", _string_tuple(self.approved_by, "approved_by", required=True))
        object.__setattr__(self, "impact_limits", _string_tuple(self.impact_limits, "impact_limits", required=True))
        object.__setattr__(self, "stop_conditions", _string_tuple(self.stop_conditions, "stop_conditions", required=True))
        object.__setattr__(self, "valid_from", _utc(self.valid_from, "valid_from"))
        object.__setattr__(self, "valid_until", _utc(self.valid_until, "valid_until"))
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "subject": self.subject,
            "targets": list(self.targets),
            "techniques": list(self.techniques),
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "approved_by": list(self.approved_by),
            "impact_limits": list(self.impact_limits),
            "stop_conditions": list(self.stop_conditions),
            "version": self.version,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


def _validate_digests(digests: frozenset[str], label: str) -> None:
    for digest in digests:
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError(f"approved {label} digests must be lowercase SHA-256 values")


class AuthorizationVerifier(Protocol):
    """Trust-boundary interface for validating authorization artifacts."""

    def verify(self, artifact: AuthorizationArtifact) -> bool:
        """Return whether the approval system trusts the artifact."""


@dataclass(frozen=True)
class DigestAuthorizationVerifier:
    """Validate artifacts against a centrally supplied SHA-256 allowlist."""

    approved_digests: frozenset[str]

    def __post_init__(self) -> None:
        _validate_digests(self.approved_digests, "authorization")

    def verify(self, artifact: AuthorizationArtifact) -> bool:
        return artifact.digest in self.approved_digests


@dataclass(frozen=True)
class HumanApproval:
    approval_id: str
    execution_id: str
    gate_id: str
    approved_by: str
    approved_at: datetime
    valid_until: datetime
    approved: bool = True
    version: str = "1"

    def __post_init__(self) -> None:
        for field_name in (
            "approval_id",
            "execution_id",
            "gate_id",
            "approved_by",
            "version",
        ):
            object.__setattr__(
                self, field_name, _nonempty(getattr(self, field_name), field_name)
            )
        object.__setattr__(self, "approved_at", _utc(self.approved_at, "approved_at"))
        object.__setattr__(self, "valid_until", _utc(self.valid_until, "valid_until"))
        if self.valid_until <= self.approved_at:
            raise ValueError("approval valid_until must be after approved_at")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "execution_id": self.execution_id,
            "gate_id": self.gate_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "approved": self.approved,
            "version": self.version,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.canonical_payload()).encode("utf-8")
        ).hexdigest()


class ApprovalVerifier(Protocol):
    """Trust-boundary interface for validating human approval records."""

    def verify(self, approval: HumanApproval) -> bool:
        """Return whether the approval system trusts the approval record."""


@dataclass(frozen=True)
class DigestApprovalVerifier:
    """Validate human approvals against a centrally supplied digest allowlist."""

    approved_digests: frozenset[str]

    def __post_init__(self) -> None:
        _validate_digests(self.approved_digests, "human approval")

    def verify(self, approval: HumanApproval) -> bool:
        return approval.digest in self.approved_digests


@dataclass(frozen=True)
class ExecutionRequest:
    execution_id: str
    actor: str
    action: str
    target: str
    technique: str
    inputs: Mapping[str, Any] = field(default_factory=dict)
    resource_versions: Mapping[str, str] = field(default_factory=dict)
    required_human_gates: tuple[str, ...] = ()
    policy_version: str = "menaxvi-policy/v1"

    def __post_init__(self) -> None:
        for field_name in ("execution_id", "actor", "action", "target", "technique", "policy_version"):
            object.__setattr__(self, field_name, _nonempty(getattr(self, field_name), field_name))
        object.__setattr__(self, "required_human_gates", _string_tuple(self.required_human_gates, "required_human_gates"))
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(
            self,
            "resource_versions",
            MappingProxyType({
                _nonempty(str(key), "resource_versions key"): _nonempty(str(value), "resource_versions value")
                for key, value in self.resource_versions.items()
            }),
        )


@dataclass(frozen=True)
class GateDecision:
    gate_type: str
    gate_id: str
    allowed: bool
    reason: str
    approval_id: str | None = None
    approval_version: str | None = None
    approval_digest: str | None = None
    approved_by: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    code: str
    reasons: tuple[str, ...]
    evaluated_at: datetime
    authorization_id: str | None
    authorization_version: str | None
    authorization_digest: str | None
    authorization_approved_by: tuple[str, ...]
    gate_decisions: tuple[GateDecision, ...]
    policy_version: str


class PolicyEngine:
    """Evaluate authorization and human approvals with fail-closed semantics."""

    def __init__(
        self,
        authorization_verifier: AuthorizationVerifier,
        approval_verifier: ApprovalVerifier,
    ):
        self._authorization_verifier = authorization_verifier
        self._approval_verifier = approval_verifier

    def evaluate(
        self,
        request: ExecutionRequest,
        authorization: AuthorizationArtifact | None,
        approvals: Sequence[HumanApproval] = (),
        *,
        now: datetime | None = None,
    ) -> PolicyDecision:
        evaluated_at = _utc(now or datetime.now(timezone.utc), "now")
        reasons: list[str] = []
        gates: list[GateDecision] = []
        authorization_id: str | None = None
        authorization_version: str | None = None
        authorization_digest: str | None = None
        authorization_approved_by: tuple[str, ...] = ()

        if authorization is None:
            reason = "authorization artifact is required"
            reasons.append(reason)
            gates.append(GateDecision("authorization", "authorization", False, reason))
        else:
            authorization_id = authorization.authorization_id
            authorization_version = authorization.version
            authorization_digest = authorization.digest
            authorization_approved_by = authorization.approved_by
            verifier_failed = False
            try:
                valid = self._authorization_verifier.verify(authorization)
            except Exception:
                valid = False
                verifier_failed = True
            authorization_reasons: list[str] = []
            if verifier_failed:
                authorization_reasons.append("authorization verifier failed closed")
            elif valid is not True:
                authorization_reasons.append(
                    "authorization artifact digest is not trusted"
                )
            if authorization.subject != request.actor:
                authorization_reasons.append("authorization subject does not match actor")
            if request.target not in authorization.targets:
                authorization_reasons.append("target is outside authorization scope")
            if request.technique not in authorization.techniques:
                authorization_reasons.append("technique is outside authorization scope")
            if evaluated_at < authorization.valid_from:
                authorization_reasons.append("authorization is not active yet")
            if evaluated_at >= authorization.valid_until:
                authorization_reasons.append("authorization has expired")

            if authorization_reasons:
                reasons.extend(authorization_reasons)
                gates.append(
                    GateDecision(
                        "authorization",
                        authorization.authorization_id,
                        False,
                        "; ".join(authorization_reasons),
                    )
                )
            else:
                gates.append(
                    GateDecision(
                        "authorization",
                        authorization.authorization_id,
                        True,
                        "authorization artifact digest is trusted",
                    )
                )

        approvals_by_gate: dict[str, list[HumanApproval]] = {}
        for approval in approvals:
            approvals_by_gate.setdefault(approval.gate_id, []).append(approval)

        for gate_id in request.required_human_gates:
            matching = [
                approval
                for approval in approvals_by_gate.get(gate_id, [])
                if approval.execution_id == request.execution_id
            ]
            if len(matching) != 1:
                reason = "exactly one matching human approval is required"
                reasons.append(f"{gate_id}: {reason}")
                gates.append(GateDecision("human", gate_id, False, reason))
                continue

            approval = matching[0]
            approval_verifier_failed = False
            try:
                approval_is_trusted = self._approval_verifier.verify(approval)
            except Exception:
                approval_is_trusted = False
                approval_verifier_failed = True

            if approval_verifier_failed:
                reason = "human approval verifier failed closed"
            elif approval_is_trusted is not True:
                reason = "human approval digest is not trusted"
            elif not approval.approved:
                reason = "human approval was rejected"
            elif approval.approved_at > evaluated_at:
                reason = "human approval is not active yet"
            elif evaluated_at >= approval.valid_until:
                reason = "human approval has expired"
            else:
                reason = "human approval is valid"

            allowed = reason == "human approval is valid"
            if not allowed:
                reasons.append(f"{gate_id}: {reason}")
            gates.append(
                GateDecision(
                    "human",
                    gate_id,
                    allowed,
                    reason,
                    approval.approval_id,
                    approval.version,
                    approval.digest,
                    approval.approved_by,
                )
            )

        allowed = not reasons
        return PolicyDecision(
            allowed=allowed,
            code="allowed" if allowed else "denied",
            reasons=tuple(reasons),
            evaluated_at=evaluated_at,
            authorization_id=authorization_id,
            authorization_version=authorization_version,
            authorization_digest=authorization_digest,
            authorization_approved_by=authorization_approved_by,
            gate_decisions=tuple(gates),
            policy_version=request.policy_version,
        )
