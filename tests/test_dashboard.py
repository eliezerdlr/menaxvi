from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.dashboard import DashboardError, DashboardService


CONTEXT = {
    "company": "Northstar Labs",
    "audience": "Operations leaders",
    "offer": "Governed campaign review",
    "brand": "Clear and evidence-led",
    "channels": "Email",
    "claims": "Every message requires a recorded human decision.",
    "constraints": "Do not publish automatically.",
    "approvalOwners": "owner@example.test",
}


class DashboardJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name) / "dashboard.json"
        self.service = DashboardService(ROOT, self.data)
        self.email = "owner@example.test"
        self.password = "correct-horse-battery"
        self.token = self.service.register(self.email, self.password)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_customer_journey_persists_after_relogin(self) -> None:
        workspace = self.service.create_workspace(self.email, CONTEXT)
        execution = self.service.create_plan(self.email, workspace["id"])
        prepared = self.service.execute(self.email, execution["id"])
        self.assertEqual(prepared["status"], "awaiting-approval")
        self.assertEqual([event["type"] for event in prepared["evidence"]], ["plan_created", "output_recorded"])
        self.assertEqual(prepared["artifact"]["claimLedger"], [{"claim": CONTEXT["claims"], "evidenceRef": "customer-claims"}])
        self.assertEqual(set(prepared["artifact"]["qualityReview"]), {"audience", "outcome", "evidence", "action", "overall"})

        completed = self.service.approve(self.email, execution["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["record"]["status"], "completed")
        self.assertIn("draft", completed["artifact"])
        self.assertEqual([event["type"] for event in completed["evidence"]], ["plan_created", "output_recorded", "gate_decided"])

        self.service.logout(self.token)
        restarted = DashboardService(ROOT, self.data)
        new_token = restarted.login(self.email, self.password)
        restored = restarted.state(restarted.user_for(new_token))
        self.assertEqual(restored["workspaces"][0]["id"], workspace["id"])
        self.assertEqual(restored["executions"][0]["artifact"], completed["artifact"])

    def test_controlled_failure_retry_and_rollback_preserve_lineage(self) -> None:
        workspace = self.service.create_workspace(self.email, CONTEXT)
        original = self.service.create_plan(self.email, workspace["id"])
        failed = self.service.execute(self.email, original["id"], fail=True)
        self.assertEqual(failed["status"], "failed")
        self.assertIsNone(failed["artifact"])

        retry = self.service.retry(self.email, original["id"])
        self.assertEqual(retry["plan"]["recovery"]["previousExecutionId"], original["id"])
        prepared = self.service.execute(self.email, retry["id"])
        completed = self.service.approve(self.email, prepared["id"])
        rollback = self.service.rollback(self.email, completed["id"], "Customer withdrew request")

        self.assertEqual(rollback["status"], "rolled-back")
        self.assertFalse(rollback["rollback"]["automaticActionsPerformed"])
        self.assertEqual(rollback["rollback"]["sourceRecordDigest"], completed["record"]["recordDigest"])
        self.assertEqual(self.service.state(self.email)["executions"][-1]["status"], "failed")

    def test_generated_output_schema_violation_fails_closed_before_gate(self) -> None:
        workspace = self.service.create_workspace(self.email, CONTEXT)
        execution = self.service.create_plan(self.email, workspace["id"])
        invalid = {"draft": "Valid draft", "claimLedger": [CONTEXT["claims"]], "qualityReview": {"overall": "pass"}}
        with patch.object(DashboardService, "_draft_outputs", return_value=invalid):
            with self.assertRaisesRegex(DashboardError, "failed contract validation"):
                self.service.execute(self.email, execution["id"])
        restored = self.service.state(self.email)["executions"][0]
        self.assertEqual(restored["status"], "plan-review")
        self.assertIsNone(restored["artifact"])
        self.assertEqual([event["type"] for event in restored["evidence"]], ["plan_created"])

    def test_validation_and_tenant_boundaries_are_actionable(self) -> None:
        with self.assertRaisesRegex(DashboardError, "required onboarding field"):
            self.service.create_workspace(self.email, {**CONTEXT, "claims": ""})
        other = "other@example.test"
        self.service.register(other, "another-correct-password")
        workspace = self.service.create_workspace(self.email, CONTEXT)
        with self.assertRaisesRegex(DashboardError, "belongs to your account"):
            self.service.create_plan(other, workspace["id"])
        with self.assertRaisesRegex(DashboardError, "Email or password is incorrect"):
            self.service.login(self.email, "wrong-password")


if __name__ == "__main__":
    unittest.main()
