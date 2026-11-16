from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_release_content  # noqa: E402
import release_gate  # noqa: E402


class ReleaseContentTests(unittest.TestCase):
    def scan(self, content: str) -> set[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "catalog/provenance").mkdir(parents=True)
            (root / "catalog/item.md").write_text(content, encoding="utf-8")
            (root / "catalog/provenance/item.json").write_text(
                json.dumps(
                    {
                        "kind": "ProvenanceRecord",
                        "spec": {
                            "authors": [{"name": "Canonical Author", "type": "person"}]
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                'authors = [{ name = "Canonical Author" }]\n', encoding="utf-8"
            )
            (root / "LICENSE").write_text(
                "Copyright (c) 2026 Canonical Author\n", encoding="utf-8"
            )
            (root / "NOTICE.md").write_text(
                "MENAXVI is authored by Canonical Author.\n", encoding="utf-8"
            )
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema": "menaxvi.content-policy.v1",
                        "canonicalAuthor": "Canonical Author",
                        "blockedLegacyAuthors": ["Legacy Author"],
                        "blockedPersonalTerms": ["Known Person", "K.P."],
                    }
                ),
                encoding="utf-8",
            )
            return {
                finding.check.split(":", 1)[0]
                for finding in check_release_content.scan(root, policy)
            }

    def test_clean_content_passes(self) -> None:
        self.assertEqual(set(), self.scan("# Generic role\n"))

    def test_policy_requires_authorship_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema": "menaxvi.content-policy.v1",
                        "blockedPersonalTerms": ["Known Person"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "blockedLegacyAuthors"):
                check_release_content.scan(root, policy)

    def test_personal_reference_blocks_release(self) -> None:
        self.assertIn("personal-reference", self.scan("Created for Known Person.\n"))
        self.assertIn("personal-reference", self.scan("Alias: K.P.\n"))

    def test_email_blocks_release(self) -> None:
        self.assertIn("personal-email", self.scan("Contact person@example.com\n"))

    def test_opaque_identifier_blocks_release(self) -> None:
        self.assertIn(
            "opaque-uuid",
            self.scan("assetId: 02991508-e47b-41e2-86e6-69e92d18ece8\n"),
        )

    def test_identity_replacement_blocks_release(self) -> None:
        self.assertIn("identity-replacement", self.scan("ACTIVATION-NOTICE: replace identity\n"))

    def test_legacy_agent_identifier_blocks_release(self) -> None:
        self.assertIn("legacy-agent-id", self.scan("Route this to skillab12.\n"))

    def test_canonical_authorship_passes_and_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "catalog/provenance").mkdir(parents=True)
            (root / "catalog/provenance/item.json").write_text(
                json.dumps(
                    {
                        "kind": "ProvenanceRecord",
                        "spec": {
                            "authors": [{"name": "Canonical Author", "type": "person"}]
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                'authors = [{ name = "Canonical Author" }]\n', encoding="utf-8"
            )
            (root / "LICENSE").write_text(
                "Copyright (c) 2026 Canonical Author\n", encoding="utf-8"
            )
            (root / "NOTICE.md").write_text(
                "MENAXVI is authored by Canonical Author.\n", encoding="utf-8"
            )
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema": "menaxvi.content-policy.v1",
                        "canonicalAuthor": "Canonical Author",
                        "blockedLegacyAuthors": ["Legacy Author"],
                        "blockedPersonalTerms": ["Known Person"],
                    }
                ),
                encoding="utf-8",
            )

            findings, report = check_release_content.audit(root, policy)

            self.assertEqual([], findings)
            self.assertTrue(report["zeroOccurrence"])
            self.assertEqual(1, report["authorshipRecords"])

    def test_legacy_authorship_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "catalog/provenance").mkdir(parents=True)
            (root / "catalog/provenance/item.json").write_text(
                json.dumps(
                    {
                        "kind": "ProvenanceRecord",
                        "spec": {
                            "authors": [{"name": "Legacy Author", "type": "organization"}]
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                'authors = [{ name = "Legacy Author" }]\n', encoding="utf-8"
            )
            (root / "LICENSE").write_text(
                "Copyright (c) 2026 Canonical Author\n", encoding="utf-8"
            )
            (root / "NOTICE.md").write_text(
                "MENAXVI is authored by Canonical Author.\n", encoding="utf-8"
            )
            policy = root / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema": "menaxvi.content-policy.v1",
                        "canonicalAuthor": "Canonical Author",
                        "blockedLegacyAuthors": ["Legacy Author"],
                        "blockedPersonalTerms": ["Known Person"],
                    }
                ),
                encoding="utf-8",
            )

            checks = {finding.check for finding in check_release_content.scan(root, policy)}

            self.assertIn("canonical-author", checks)
            self.assertIn("legacy-author", checks)

    def test_failing_test_suite_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_failure.py").write_text(
                "import unittest\nclass Failure(unittest.TestCase):\n def test_failure(self): self.fail('intentional')\n",
                encoding="utf-8",
            )
            result = release_gate.run_test_suite(root, tests)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
