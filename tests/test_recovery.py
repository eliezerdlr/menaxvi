from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.cli import main
from menaxvi.manual import ManualWorkflowError, record_results, render_plan
from menaxvi.recovery import create_retry_plan, create_rollback_plan

WORKFLOW = "workflow.reviewed-campaign-message@1.0.0"
INPUTS = {
    "brief": {"audience": "Operators"},
    "evidence": [{"id": "e-1", "statement": "Reviewed", "source": "test"}],
}


def failed_record(plan: dict[str, object]) -> dict[str, object]:
    return record_results(
        plan,
        {
            "executionId": plan["executionId"],
            "nodes": [{"id": "draft-and-review", "status": "failed", "error": "quality check"}],
            "gates": [{"id": "human-approval", "status": "not-run", "reason": "node failed"}],
            "outputs": {},
            "residualRisks": ["Draft requires revision."],
        },
    )


class RecoveryTests(unittest.TestCase):
    def test_creates_bounded_retry_with_lineage(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "attempt-1", INPUTS)
        record = failed_record(plan)

        retry = create_retry_plan(plan, record, "attempt-2")

        self.assertEqual(retry["executionId"], "attempt-2")
        self.assertEqual(retry["recovery"]["attempt"], 2)
        self.assertEqual(retry["recovery"]["previousRecordDigest"], record["recordDigest"])
        with self.assertRaisesRegex(ManualWorkflowError, "retry limit reached"):
            create_retry_plan(retry, failed_record(retry), "attempt-3")

    def test_retry_rejects_completed_tampered_or_reused_execution(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "attempt-1", INPUTS)
        record = failed_record(plan)
        with self.assertRaisesRegex(ManualWorkflowError, "must differ"):
            create_retry_plan(plan, record, "attempt-1")
        tampered = dict(record)
        tampered["status"] = "completed"
        with self.assertRaisesRegex(ManualWorkflowError, "record digest does not match"):
            create_retry_plan(plan, tampered, "attempt-2")

    def test_rollback_is_explicitly_manual_and_digest_bound(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "attempt-1", INPUTS)
        record = failed_record(plan)

        rollback = create_rollback_plan(plan, record, "Customer withdrew the request")

        self.assertFalse(rollback["automaticActionsPerformed"])
        self.assertEqual(rollback["sourceRecordDigest"], record["recordDigest"])
        self.assertIn("reverse external effects manually", " ".join(rollback["instructions"]))

    def test_cli_creates_retry_and_rollback_files(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "attempt-1", INPUTS)
        record = failed_record(plan)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_path, record_path = root / "plan.json", root / "record.json"
            retry_path, rollback_path = root / "retry.json", root / "rollback.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            record_path.write_text(json.dumps(record), encoding="utf-8")

            self.assertEqual(main(["workflow", "retry", "--plan", str(plan_path), "--record", str(record_path), "--execution-id", "attempt-2", "--output", str(retry_path)]), 0)
            self.assertEqual(main(["workflow", "rollback", "--plan", str(plan_path), "--record", str(record_path), "--reason", "operator request", "--output", str(rollback_path)]), 0)
            self.assertEqual(json.loads(retry_path.read_text())["recovery"]["attempt"], 2)
            self.assertFalse(json.loads(rollback_path.read_text())["automaticActionsPerformed"])


if __name__ == "__main__":
    unittest.main()
