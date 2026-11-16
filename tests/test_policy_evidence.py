from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.evidence import AuthorizationDenied, EvidenceLog, GovernedExecution, ToolSelection
from core.policy import (
    AuthorizationArtifact,
    DigestApprovalVerifier,
    DigestAuthorizationVerifier,
    ExecutionRequest,
    HumanApproval,
    PolicyEngine,
)


NOW = datetime(2030, 1, 2, 12, 0, tzinfo=timezone.utc)


class PolicyEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.log_path = Path(self.temporary_directory.name) / "evidence.jsonl"
        self.authorization = AuthorizationArtifact(
            authorization_id="auth-001",
            subject="agent:marketing-ops",
            targets=("customer:acme/campaign:spring",),
            techniques=("draft-content",),
            valid_from=NOW - timedelta(days=1),
            valid_until=NOW + timedelta(days=1),
            approved_by=("user:security-owner",),
            impact_limits=("draft only",),
            stop_conditions=("unexpected customer data",),
            version="3",
        )
        self.request = ExecutionRequest(
            execution_id="exec-001",
            actor="agent:marketing-ops",
            action="prepare campaign draft",
            target="customer:acme/campaign:spring",
            technique="draft-content",
            inputs={"brief": "Launch safely", "api_token": "must-not-appear"},
            resource_versions={"workflow": "1.4.0", "role": "2.1.0"},
            required_human_gates=("brand-review",),
        )
        self.approval = HumanApproval(
            approval_id="approval-001",
            execution_id="exec-001",
            gate_id="brand-review",
            approved_by="user:brand-owner",
            approved_at=NOW - timedelta(hours=1),
            valid_until=NOW + timedelta(hours=1),
            version="2",
        )
        self.authorization_verifier = DigestAuthorizationVerifier(
            frozenset({self.authorization.digest})
        )
        self.approval_verifier = DigestApprovalVerifier(
            frozenset({self.approval.digest})
        )
        self.policy = PolicyEngine(
            self.authorization_verifier, self.approval_verifier
        )

    def test_valid_authorization_and_human_gate_allow(self) -> None:
        decision = self.policy.evaluate(
            self.request, self.authorization, (self.approval,), now=NOW
        )

        self.assertTrue(decision.allowed)
        self.assertEqual("allowed", decision.code)
        self.assertEqual([True, True], [gate.allowed for gate in decision.gate_decisions])
        self.assertEqual(self.authorization.digest, decision.authorization_digest)

    def test_missing_authorization_fails_closed(self) -> None:
        decision = self.policy.evaluate(self.request, None, (self.approval,), now=NOW)

        self.assertFalse(decision.allowed)
        self.assertIn("authorization artifact is required", decision.reasons)

    def test_untrusted_or_out_of_scope_authorization_is_denied(self) -> None:
        untrusted = AuthorizationArtifact(
            authorization_id="auth-002",
            subject=self.authorization.subject,
            targets=("customer:other",),
            techniques=self.authorization.techniques,
            valid_from=self.authorization.valid_from,
            valid_until=self.authorization.valid_until,
            approved_by=self.authorization.approved_by,
            impact_limits=self.authorization.impact_limits,
            stop_conditions=self.authorization.stop_conditions,
        )

        decision = self.policy.evaluate(self.request, untrusted, (self.approval,), now=NOW)

        self.assertFalse(decision.allowed)
        self.assertIn("authorization artifact digest is not trusted", decision.reasons)
        self.assertIn("target is outside authorization scope", decision.reasons)

    def test_expired_authorization_and_approval_are_denied(self) -> None:
        decision = self.policy.evaluate(
            self.request,
            self.authorization,
            (self.approval,),
            now=NOW + timedelta(days=2),
        )

        self.assertFalse(decision.allowed)
        self.assertIn("authorization has expired", decision.reasons)
        self.assertIn("brand-review: human approval has expired", decision.reasons)

    def test_authorization_verifier_error_fails_closed(self) -> None:
        class UnavailableVerifier:
            def verify(self, _artifact: AuthorizationArtifact) -> bool:
                raise RuntimeError("private verifier detail")

        decision = PolicyEngine(
            UnavailableVerifier(), self.approval_verifier
        ).evaluate(self.request, self.authorization, (self.approval,), now=NOW)

        self.assertFalse(decision.allowed)
        self.assertIn("authorization verifier failed closed", decision.reasons)
        self.assertNotIn("private verifier detail", decision.reasons)

    def test_human_approval_verifier_error_fails_closed(self) -> None:
        class UnavailableApprovalVerifier:
            def verify(self, _approval: HumanApproval) -> bool:
                raise RuntimeError("private verifier detail")

        decision = PolicyEngine(
            self.authorization_verifier, UnavailableApprovalVerifier()
        ).evaluate(self.request, self.authorization, (self.approval,), now=NOW)

        self.assertIn(
            "brand-review: human approval verifier failed closed", decision.reasons
        )
        self.assertNotIn("private verifier detail", decision.reasons)

    def test_untrusted_or_rejected_human_approval_is_denied(self) -> None:
        untrusted = HumanApproval(
            approval_id=self.approval.approval_id,
            execution_id=self.approval.execution_id,
            gate_id=self.approval.gate_id,
            approved_by=self.approval.approved_by,
            approved_at=self.approval.approved_at,
            valid_until=self.approval.valid_until,
            version="untrusted",
        )
        untrusted_decision = self.policy.evaluate(
            self.request, self.authorization, (untrusted,), now=NOW
        )

        rejected = HumanApproval(
            approval_id="approval-rejected",
            execution_id=self.approval.execution_id,
            gate_id=self.approval.gate_id,
            approved_by=self.approval.approved_by,
            approved_at=self.approval.approved_at,
            valid_until=self.approval.valid_until,
            approved=False,
        )
        rejected_policy = PolicyEngine(
            self.authorization_verifier,
            DigestApprovalVerifier(frozenset({rejected.digest})),
        )
        rejected_decision = rejected_policy.evaluate(
            self.request, self.authorization, (rejected,), now=NOW
        )

        self.assertIn(
            "brand-review: human approval digest is not trusted",
            untrusted_decision.reasons,
        )
        self.assertIn(
            "brand-review: human approval was rejected", rejected_decision.reasons
        )

    def test_missing_or_duplicate_human_approval_is_denied(self) -> None:
        missing = self.policy.evaluate(self.request, self.authorization, (), now=NOW)
        duplicate = self.policy.evaluate(
            self.request,
            self.authorization,
            (self.approval, self.approval),
            now=NOW,
        )

        self.assertFalse(missing.allowed)
        self.assertFalse(duplicate.allowed)
        self.assertIn(
            "brand-review: exactly one matching human approval is required",
            missing.reasons,
        )

    def test_tool_selector_runs_only_after_policy_allows(self) -> None:
        evidence = EvidenceLog(self.log_path, clock=lambda: NOW)
        governed = GovernedExecution(self.policy, evidence, clock=lambda: NOW)
        calls: list[str] = []

        prepared = governed.prepare(
            self.request,
            self.authorization,
            (self.approval,),
            lambda request: calls.append(request.execution_id)
            or ToolSelection("manual", "plan-renderer", "1.0.0"),
        )
        governed.record_output(
            prepared,
            {"artifact": "draft.md", "password": "must-not-appear"},
            output_version="1",
        )

        events = evidence.events()
        event_types = [event.event_type for event in events]
        self.assertEqual(["exec-001"], calls)
        self.assertLess(event_types.index("policy_decision"), event_types.index("tool_selected"))
        self.assertEqual("output_recorded", event_types[-1])
        self.assertTrue(evidence.verify().valid)
        contents = self.log_path.read_text(encoding="utf-8")
        self.assertNotIn("must-not-appear", contents)
        self.assertIn("[REDACTED]", contents)
        self.assertEqual(self.authorization.digest, events[-3].data["authorization_digest"])

    def test_denied_request_never_calls_tool_selector_and_is_logged(self) -> None:
        evidence = EvidenceLog(self.log_path, clock=lambda: NOW)
        governed = GovernedExecution(self.policy, evidence, clock=lambda: NOW)
        called = False

        def selector(_request: ExecutionRequest) -> ToolSelection:
            nonlocal called
            called = True
            return ToolSelection("manual", "unsafe", "1")

        with self.assertRaises(AuthorizationDenied):
            governed.prepare(self.request, None, (self.approval,), selector)

        self.assertFalse(called)
        events = evidence.events()
        self.assertEqual("policy_decision", events[-1].event_type)
        self.assertFalse(events[-1].data["allowed"])

    def test_selector_failure_is_recorded_and_propagated(self) -> None:
        evidence = EvidenceLog(self.log_path, clock=lambda: NOW)
        governed = GovernedExecution(self.policy, evidence, clock=lambda: NOW)

        def selector(_request: ExecutionRequest) -> ToolSelection:
            raise RuntimeError("adapter unavailable")

        with self.assertRaisesRegex(RuntimeError, "adapter unavailable"):
            governed.prepare(
                self.request, self.authorization, (self.approval,), selector
            )

        self.assertEqual("tool_selection_failed", evidence.events()[-1].event_type)

    def test_tampering_is_detected_and_blocks_append(self) -> None:
        evidence = EvidenceLog(self.log_path, clock=lambda: NOW)
        evidence.append("exec-001", "test", {"value": 1})
        payload = json.loads(self.log_path.read_text(encoding="utf-8"))
        payload["data"]["value"] = 2
        self.log_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

        verification = evidence.verify()
        self.assertFalse(verification.valid)
        self.assertIn("hash does not match", verification.error or "")
        with self.assertRaisesRegex(ValueError, "existing evidence log is invalid"):
            evidence.append("exec-001", "second", {})

    def test_artifacts_require_bounded_scope_and_timezone_aware_dates(self) -> None:
        with self.assertRaisesRegex(ValueError, "impact_limits must not be empty"):
            AuthorizationArtifact(
                authorization_id="auth-invalid",
                subject="agent:test",
                targets=("target",),
                techniques=("technique",),
                valid_from=NOW,
                valid_until=NOW + timedelta(hours=1),
                approved_by=("owner",),
                impact_limits=(),
                stop_conditions=("stop",),
            )
        with self.assertRaisesRegex(ValueError, "valid_from must be timezone-aware"):
            AuthorizationArtifact(
                authorization_id="auth-invalid",
                subject="agent:test",
                targets=("target",),
                techniques=("technique",),
                valid_from=datetime(2030, 1, 1),
                valid_until=NOW + timedelta(hours=1),
                approved_by=("owner",),
                impact_limits=("bounded",),
                stop_conditions=("stop",),
            )


if __name__ == "__main__":
    unittest.main()
