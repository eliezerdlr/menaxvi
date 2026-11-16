from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.cli import main
from menaxvi.manual import ManualWorkflowError, record_results, render_plan, validate_workflow


WORKFLOW = "workflow.reviewed-campaign-message@1.0.0"
INPUTS = {
    "brief": {
        "audience": "Operations leaders",
        "channel": "email",
        "desiredOutcome": "Request a review",
        "nextAction": "Reply with approval",
    },
    "evidence": [
        {
            "id": "evidence-1",
            "statement": "The workflow is manually reviewed.",
            "source": "approved project evidence",
        }
    ],
}


def supplied_results(execution_id: str = "exec-men-007") -> dict[str, object]:
    return {
        "executionId": execution_id,
        "nodes": [
            {
                "id": "draft-and-review",
                "status": "completed",
                "outputs": {
                    "message-draft": "Draft message",
                    "claim-ledger": [],
                    "quality-review": {"overall": "pass"},
                },
            }
        ],
        "gates": [
            {
                "id": "human-approval",
                "status": "passed",
                "decision": "approve_draft",
                "decidedBy": "user:marketing-reviewer",
                "evidence": "review-ticket-007",
            }
        ],
        "outputs": {"reviewed-message-package": "artifact://draft-message"},
        "residualRisks": ["The manual adapter does not publish content."],
    }


class ManualWorkflowTests(unittest.TestCase):
    def test_validates_approved_workflow_and_dependencies(self) -> None:
        result = validate_workflow(ROOT, WORKFLOW)

        self.assertEqual(
            result,
            {
                "valid": True,
                "adapter": "manual",
                "workflow": WORKFLOW,
                "nodes": 1,
                "tasks": 1,
                "gates": 1,
            },
        )

    def test_plan_is_deterministic_and_contains_operator_instructions(self) -> None:
        first = render_plan(ROOT, WORKFLOW, "exec-men-007", INPUTS)
        second = render_plan(ROOT, WORKFLOW, "exec-men-007", INPUTS)

        self.assertEqual(first, second)
        self.assertEqual(first["nodes"][0]["id"], "draft-and-review")
        self.assertEqual(
            [step["id"] for step in first["nodes"][0]["task"]["steps"]],
            ["extract", "draft", "ledger", "review"],
        )
        self.assertEqual(len(first["planDigest"]), 64)

    def test_plan_rejects_missing_or_unknown_inputs(self) -> None:
        with self.assertRaisesRegex(ManualWorkflowError, "missing required workflow input: evidence"):
            render_plan(ROOT, WORKFLOW, "exec-men-007", {"brief": INPUTS["brief"]})
        with self.assertRaisesRegex(ManualWorkflowError, "unknown workflow input: extra"):
            render_plan(ROOT, WORKFLOW, "exec-men-007", {**INPUTS, "extra": True})

    def test_records_supplied_results_and_binds_them_to_plan(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "exec-men-007", INPUTS)

        record = record_results(plan, supplied_results())

        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["planDigest"], plan["planDigest"])
        self.assertEqual(len(record["recordDigest"]), 64)
        self.assertEqual(record, record_results(plan, supplied_results()))

    def test_records_failed_node_with_not_run_gate(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "exec-men-007", INPUTS)
        results = supplied_results()
        results["nodes"][0] = {
            "id": "draft-and-review",
            "status": "failed",
            "error": "Operator stopped after a failed quality check.",
        }
        results["gates"][0] = {
            "id": "human-approval",
            "status": "not-run",
            "reason": "The required node did not complete.",
        }

        record = record_results(plan, results)

        self.assertEqual(record["status"], "failed")

    def test_record_rejects_tampered_plan_and_invalid_results(self) -> None:
        plan = render_plan(ROOT, WORKFLOW, "exec-men-007", INPUTS)
        tampered = dict(plan)
        tampered["executionId"] = "changed"
        with self.assertRaisesRegex(ManualWorkflowError, "plan digest does not match"):
            record_results(tampered, supplied_results("changed"))

        invalid_decision = supplied_results()
        invalid_decision["gates"][0]["decision"] = "publish"
        with self.assertRaisesRegex(ManualWorkflowError, "decision must be one of"):
            record_results(plan, invalid_decision)

        missing_output = supplied_results()
        del missing_output["nodes"][0]["outputs"]["claim-ledger"]
        with self.assertRaisesRegex(ManualWorkflowError, "outputs do not match the task"):
            record_results(plan, missing_output)

    def test_cli_validates_plans_and_records_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            inputs_path = output / "inputs.json"
            plan_path = output / "plan.json"
            results_path = output / "results.json"
            record_path = output / "record.json"
            inputs_path.write_text(json.dumps(INPUTS), encoding="utf-8")
            results_path.write_text(json.dumps(supplied_results()), encoding="utf-8")

            self.assertEqual(
                main(["workflow", "validate", "--root", str(ROOT), "--workflow", WORKFLOW]),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "workflow",
                        "plan",
                        "--root",
                        str(ROOT),
                        "--workflow",
                        WORKFLOW,
                        "--execution-id",
                        "exec-men-007",
                        "--inputs",
                        str(inputs_path),
                        "--output",
                        str(plan_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "workflow",
                        "record",
                        "--plan",
                        str(plan_path),
                        "--results",
                        str(results_path),
                        "--output",
                        str(record_path),
                    ]
                ),
                0,
            )

            self.assertEqual(json.loads(record_path.read_text(encoding="utf-8"))["status"], "completed")


if __name__ == "__main__":
    unittest.main()
