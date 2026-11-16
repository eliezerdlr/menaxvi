from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_customer_dashboard_journey as journey  # noqa: E402


class CustomerDashboardJourneyTests(unittest.TestCase):
    @patch.object(journey, "repository_sha", return_value="abc123")
    def test_missing_target_fails_closed_with_all_steps_accounted_for(self, _sha) -> None:
        report = journey.build_preflight_report(ROOT, None, "2026-11-16T12:00:00Z")
        self.assertFalse(report["passed"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(11, len(report["steps"]))
        self.assertEqual("BLOCKED", report["steps"][0]["result"])
        self.assertTrue(all(step["result"] == "NOT_RUN" for step in report["steps"][1:]))
        self.assertEqual("critical", report["defects"][0]["severity"])
        self.assertEqual([], report["screenshots"])

    @patch.object(journey, "repository_sha", return_value="abc123")
    def test_valid_target_is_ready_but_never_claimed_as_passed(self, _sha) -> None:
        report = journey.build_preflight_report(ROOT, "https://rc.example.test/dashboard")
        self.assertEqual("READY_FOR_BROWSER_PASS", report["status"])
        self.assertFalse(report["passed"])
        self.assertFalse(report["browserPassExecuted"])
        self.assertEqual([], report["defects"])
        self.assertTrue(all(step["result"] == "READY" for step in report["steps"]))

    @patch.object(journey, "repository_sha", return_value="abc123")
    def test_cli_writes_machine_readable_blocked_evidence(self, _sha) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "customer-journey.json"
            exit_code = journey.main(["--root", str(ROOT), "--output", str(output)])
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(2, exit_code)
        self.assertEqual("menaxvi.customer-journey/v1", payload["schema"])
        self.assertEqual("NOT_RUN", payload["retryRollbackEvidence"]["result"])
        self.assertEqual("NOT_RUN", payload["persistenceEvidence"]["result"])


if __name__ == "__main__":
    unittest.main()
