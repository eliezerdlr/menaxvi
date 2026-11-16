from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.cli import main


class CustomerDocumentationTests(unittest.TestCase):
    def test_customer_documents_and_local_links_exist(self) -> None:
        documents = [
            ROOT / "docs/customer/README.md",
            ROOT / "docs/customer/VALIDATION-TUTORIAL.md",
            ROOT / "docs/customer/WORKFLOW-TUTORIAL.md",
            ROOT / "docs/customer/COMPATIBILITY.md",
            ROOT / "docs/customer/SUPPORT-AND-UPGRADES.md",
            ROOT / "docs/customer/LIMITATIONS.md",
            ROOT / "examples/reviewed-campaign-message/README.md",
        ]
        for document in documents:
            self.assertTrue(document.is_file(), document)

        index = documents[0].read_text(encoding="utf-8")
        for target in (
            "VALIDATION-TUTORIAL.md",
            "WORKFLOW-TUTORIAL.md",
            "DASHBOARD-TUTORIAL.md",
            "COMPATIBILITY.md",
            "SUPPORT-AND-UPGRADES.md",
            "LIMITATIONS.md",
            "../../examples/reviewed-campaign-message/README.md",
        ):
            self.assertIn(target, index)

    def test_documented_example_runs_end_to_end(self) -> None:
        inputs = ROOT / "examples/reviewed-campaign-message/inputs.json"
        results = ROOT / "examples/reviewed-campaign-message/results.json"
        self.assertIsInstance(json.loads(inputs.read_text(encoding="utf-8")), dict)
        self.assertIsInstance(json.loads(results.read_text(encoding="utf-8")), dict)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            plan = output / "plan.json"
            record = output / "record.json"
            self.assertEqual(
                main(
                    [
                        "workflow",
                        "plan",
                        "--root",
                        str(ROOT),
                        "--workflow",
                        "workflow.reviewed-campaign-message@1.0.0",
                        "--execution-id",
                        "tutorial-001",
                        "--inputs",
                        str(inputs),
                        "--output",
                        str(plan),
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
                        str(plan),
                        "--results",
                        str(results),
                        "--output",
                        str(record),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["status"], "completed")

    def test_limitations_match_public_distribution_boundary(self) -> None:
        limitations = (ROOT / "docs/customer/LIMITATIONS.md").read_text(encoding="utf-8")
        self.assertIn("open-source pre-alpha for local evaluation", limitations)
        self.assertIn("restricted migration inputs", limitations)
        self.assertIn("intentionally excluded from Git history", limitations)
        self.assertFalse((ROOT / "quarantine").exists())
        self.assertFalse((ROOT / "migrations").exists())


if __name__ == "__main__":
    unittest.main()
