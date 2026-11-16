from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.dashboard_api import AuthenticationError, DashboardError, DashboardService
from core.policy import AuthorizationArtifact


NOW = datetime.now(timezone.utc)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def plan(execution_id: str) -> dict:
    body = {
        "schema": "menaxvi.manual-plan/v1",
        "executionId": execution_id,
        "adapter": {"name": "manual", "version": "1"},
        "workflow": {"id": "campaign", "version": "1.0.0", "title": "Campaign", "purpose": "test"},
        "inputs": {"brief": "safe"},
        "nodes": [{
            "id": "draft", "dependsOn": [], "inputBindings": {},
            "task": {"id": "draft", "version": "1", "title": "Draft", "purpose": "draft",
                     "preconditions": [], "steps": [], "acceptanceCriteria": [],
                     "outputs": [{"name": "copy"}], "policies": []},
        }],
        "gates": [{"id": "review", "type": "human", "afterNodes": ["draft"],
                   "decisionOptions": ["approve", "reject"], "evidenceRequired": True}],
        "outputs": [{"name": "campaign"}],
        "failurePolicy": {"maxAttempts": 2}, "evidencePolicy": {}, "policies": [],
    }
    return {**body, "planDigest": hashlib.sha256(canonical(body).encode()).hexdigest()}


class DashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.service = DashboardService(Path.cwd(), root / "dashboard.sqlite3", root / "evidence")
        self.user = self.service.register("owner@example.com", "correct horse battery staple")
        self.token = self.service.login("owner@example.com", "correct horse battery staple")
        self.workspace = self.service.create_workspace(
            self.token, "Acme", {"company": "Acme", "audience": "operators", "constraints": ["draft only"]}
        )

    def _execution(self, execution_id: str = "exe_test") -> str:
        document = plan(execution_id)
        with self.service._connect() as db:
            db.execute("INSERT INTO plans VALUES (?, ?, ?, ?)",
                       ("pln_test", self.workspace["id"], canonical(document), NOW.isoformat()))
        authorization = AuthorizationArtifact(
            authorization_id="auth_test", subject=f"workspace:{self.workspace['id']}",
            targets=("workflow:campaign@1.0.0",), techniques=("manual",),
            valid_from=NOW - timedelta(minutes=5), valid_until=NOW + timedelta(hours=1),
            approved_by=("user:security-owner",), impact_limits=("draft only",),
            stop_conditions=("unexpected customer data",),
        )
        self.service.create_execution(self.token, self.workspace["id"], "pln_test", authorization)
        self.service.approve(self.token, execution_id, "review")
        return execution_id

    def test_authentication_and_workspace_survive_new_service_instance(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.service.login("owner@example.com", "wrong password value")

        reopened = DashboardService(self.service.project_root, self.service.database, self.service.evidence_dir)
        restored = reopened.get_workspace(self.token, self.workspace["id"])
        self.assertEqual("Acme", restored["name"])
        self.assertEqual("operators", restored["businessContext"]["audience"])

        reopened.logout(self.token)
        with self.assertRaises(AuthenticationError):
            reopened.get_workspace(self.token, self.workspace["id"])

    def test_approved_execution_persists_artifact_and_hash_chained_evidence(self) -> None:
        execution_id = self._execution()
        result = self.service.execute(self.token, execution_id, {
            "executionId": execution_id,
            "nodes": [{"id": "draft", "status": "completed", "outputs": {"copy": "Hello"}}],
            "gates": [{"id": "review", "status": "passed", "decision": "approve",
                       "decidedBy": "owner", "evidence": "reviewed"}],
            "outputs": {"campaign": "Hello"}, "residualRisks": [],
        })

        self.assertEqual("completed", result["status"])
        self.assertEqual("Hello", result["artifact"]["outputs"]["campaign"])
        self.assertTrue(result["evidenceValid"])
        self.assertEqual(
            ["execution_started", "gate_evaluated", "gate_evaluated", "policy_decision", "tool_selected", "output_recorded"],
            [event["event_type"] for event in result["evidence"]],
        )
        reopened = DashboardService(self.service.project_root, self.service.database, self.service.evidence_dir)
        self.assertEqual(result["artifact"], reopened.get_execution(self.token, execution_id)["artifact"])

    def test_failed_record_supports_bounded_retry_and_rollback(self) -> None:
        execution_id = self._execution()
        failed = self.service.execute(self.token, execution_id, {
            "executionId": execution_id,
            "nodes": [{"id": "draft", "status": "failed"}],
            "gates": [{"id": "review", "status": "not-run"}],
            "outputs": {}, "residualRisks": ["draft unavailable"],
        })
        self.assertEqual("failed", failed["status"])

        retry = self.service.retry(self.token, execution_id)
        self.assertEqual("retry", retry["document"]["recovery"]["kind"])
        self.assertEqual(2, retry["document"]["recovery"]["attempt"])
        rollback = self.service.rollback(self.token, execution_id, "customer requested reversal")
        self.assertFalse(rollback["automaticActionsPerformed"])
        self.assertEqual(failed["record"]["recordDigest"], rollback["sourceRecordDigest"])

    def test_validation_failure_is_safe_and_does_not_create_artifact(self) -> None:
        execution_id = self._execution()
        with self.assertRaisesRegex(DashboardError, "completed node draft must contain outputs"):
            self.service.execute(self.token, execution_id, {
                "executionId": execution_id,
                "nodes": [{"id": "draft", "status": "completed"}],
                "gates": [{"id": "review", "status": "passed", "decision": "approve",
                           "decidedBy": "owner", "evidence": "reviewed"}],
                "outputs": {"campaign": "unsafe"}, "residualRisks": [],
            })
        execution = self.service.get_execution(self.token, execution_id)
        self.assertEqual("failed", execution["status"])
        self.assertIsNone(execution["artifact"])
        self.assertNotIn("Traceback", execution["failure"]["message"])


if __name__ == "__main__":
    unittest.main()
