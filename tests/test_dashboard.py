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
    "company": "North Texas Clean Co.",
    "audience": "busy homeowners in North Texas",
    "offer": "dependable residential cleaning",
    "brand": "local, practical, and evidence-led",
    "objective": "local reach and qualified quote requests",
    "geography": "North Texas, United States",
    "channels": "meta-ads,google-search,email,organic-social",
    "language": "en-US",
    "budget": "900",
    "currency": "USD",
    "durationDays": "30",
    "claims": "Claim: Every quote is reviewed against the customer's stated service needs.\nEvidence: The company requires a service-needs review before confirming a quote.",
    "constraints": "Do not invent prices, reviews, guarantees, or service areas.",
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

    def test_complete_multichannel_campaign_persists_after_relogin(self) -> None:
        workspace = self.service.create_workspace(self.email, CONTEXT)
        execution = self.service.create_plan(self.email, workspace["id"])
        prepared = self.service.execute(self.email, execution["id"])
        self.assertEqual(prepared["status"], "awaiting-approval")
        self.assertEqual([event["type"] for event in prepared["evidence"]], ["plan_created", "output_recorded"])
        campaign = prepared["artifact"]["campaign"]
        self.assertEqual(campaign["language"], "en-US")
        self.assertEqual(set(campaign["channelPlans"]), {"metaAds", "googleSearch", "email", "organicSocial"})
        self.assertEqual(campaign["landingPage"]["hero"]["cta"], "Request a personalized quote")
        self.assertEqual(campaign["summary"]["budget"], {"currency": "USD", "total": "900.00"})
        self.assertEqual(prepared["artifact"]["qualityReview"]["overall"], "pass")

        completed = self.service.approve(self.email, execution["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["record"]["status"], "completed")
        self.assertEqual(completed["artifact"]["gateDecision"], "approve_campaign")
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

    def test_portuguese_portugal_campaign_is_complete_and_consistent(self) -> None:
        context = {
            **CONTEXT,
            "company": "Limpeza Norte",
            "audience": "gestores de alojamento local no Porto",
            "offer": "limpeza profissional entre estadias",
            "objective": "alcance local e pedidos de proposta qualificados",
            "geography": "Porto, Portugal",
            "language": "pt-PT",
            "budget": "1200",
            "currency": "EUR",
            "claims": "Alegação: Cada serviço é revisto de acordo com as necessidades indicadas pelo cliente.\nEvidência: A empresa confirma o âmbito do serviço antes de aceitar a proposta.",
        }
        workspace = self.service.create_workspace(self.email, context)
        execution = self.service.create_plan(self.email, workspace["id"])
        prepared = self.service.execute(self.email, execution["id"])
        campaign = prepared["artifact"]["campaign"]
        serialized = str(campaign).casefold()
        self.assertEqual(campaign["language"], "pt-PT")
        self.assertIn("pedir uma proposta personalizada", serialized)
        self.assertNotIn("request a personalized quote", serialized)
        self.assertEqual(prepared["artifact"]["claimLedger"][0]["claim"], "Cada serviço é revisto de acordo com as necessidades indicadas pelo cliente.")
        self.assertEqual(prepared["artifact"]["qualityReview"]["overall"], "pass")

    def test_quality_failure_blocks_human_approval(self) -> None:
        workspace = self.service.create_workspace(self.email, CONTEXT)
        execution = self.service.create_plan(self.email, workspace["id"])
        valid = self.service._draft_outputs(workspace["context"])
        valid["qualityReview"]["channels"] = "fail"
        valid["qualityReview"]["overall"] = "fail"
        with patch.object(DashboardService, "_draft_outputs", return_value=valid):
            prepared = self.service.execute(self.email, execution["id"])
        self.assertEqual(prepared["status"], "awaiting-approval")
        with self.assertRaisesRegex(DashboardError, "quality review must pass"):
            self.service.approve(self.email, execution["id"])

    def test_onboarding_requires_campaign_fields_and_supported_locale(self) -> None:
        with self.assertRaisesRegex(DashboardError, "required onboarding field: objective"):
            self.service.create_workspace(self.email, {key: value for key, value in CONTEXT.items() if key != "objective"})
        with self.assertRaisesRegex(DashboardError, "pt-PT or en-US"):
            self.service.create_workspace(self.email, {**CONTEXT, "language": "pt-BR"})
        with self.assertRaisesRegex(DashboardError, "separate Claim and Evidence"):
            self.service.create_workspace(self.email, {**CONTEXT, "claims": "An unsupported claim."})

    def test_invalid_budget_or_single_channel_fails_before_artifact(self) -> None:
        for changed, message in [({"budget": "0"}, "positive campaign budget"), ({"channels": "email"}, "at least two")]:
            workspace = self.service.create_workspace(self.email, {**CONTEXT, **changed})
            execution = self.service.create_plan(self.email, workspace["id"])
            with self.assertRaisesRegex(DashboardError, message):
                self.service.execute(self.email, execution["id"])
            restored = next(item for item in self.service.state(self.email)["executions"] if item["id"] == execution["id"])
            self.assertEqual(restored["status"], "plan-review")
            self.assertIsNone(restored["artifact"])

    def test_generated_output_schema_violation_fails_closed_before_gate(self) -> None:
        workspace = self.service.create_workspace(self.email, CONTEXT)
        execution = self.service.create_plan(self.email, workspace["id"])
        invalid = {"campaign": {}, "claimLedger": [CONTEXT["claims"]], "qualityReview": {"overall": "pass"}}
        with patch.object(DashboardService, "_draft_outputs", return_value=invalid):
            with self.assertRaisesRegex(DashboardError, "failed contract validation"):
                self.service.execute(self.email, execution["id"])
        restored = self.service.state(self.email)["executions"][0]
        self.assertEqual(restored["status"], "plan-review")
        self.assertIsNone(restored["artifact"])

    def test_validation_and_tenant_boundaries_are_actionable(self) -> None:
        other = "other@example.test"
        self.service.register(other, "another-correct-password")
        workspace = self.service.create_workspace(self.email, CONTEXT)
        with self.assertRaisesRegex(DashboardError, "belongs to your account"):
            self.service.create_plan(other, workspace["id"])
        with self.assertRaisesRegex(DashboardError, "Email or password is incorrect"):
            self.service.login(self.email, "wrong-password")


if __name__ == "__main__":
    unittest.main()
