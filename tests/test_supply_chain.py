from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_supply_chain import audit


class SupplyChainAuditTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools==80.9.0"]\n\n[project]\ndependencies = []\n',
            encoding="utf-8",
        )
        (root / "requirements-dev.txt").write_text("jsonschema==4.26.0\n", encoding="utf-8")
        inventory = root / "supply-chain/dependencies.json"
        inventory.parent.mkdir()
        inventory.write_text(
            json.dumps(
                {
                    "schema": "menaxvi.supply-chain.v1",
                    "dependencies": [
                        {
                            "name": "setuptools",
                            "ecosystem": "pypi",
                            "version": "80.9.0",
                            "scope": "build",
                            "license": "MIT",
                            "source": "https://example.test/setuptools",
                            "licenseEvidence": "https://example.test/setuptools-license",
                            "reviewed": True,
                        },
                        {
                            "name": "jsonschema",
                            "ecosystem": "pypi",
                            "version": "4.26.0",
                            "scope": "development",
                            "license": "MIT",
                            "source": "https://example.test/jsonschema",
                            "licenseEvidence": "https://example.test/jsonschema-license",
                            "reviewed": True,
                        },
                    ],
                    "runtime": {"externalDependencies": [], "basis": "stdlib only"},
                }
            ),
            encoding="utf-8",
        )
        return temporary, root, inventory

    def test_exact_reviewed_dependencies_pass(self) -> None:
        temporary, root, inventory = self.fixture()
        self.addCleanup(temporary.cleanup)
        findings, report = audit(root, inventory)
        self.assertEqual([], findings)
        self.assertTrue(report["passed"])
        self.assertEqual(2, report["declaredDependencyCount"])

    def test_mutable_requirement_blocks(self) -> None:
        temporary, root, inventory = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "requirements-dev.txt").write_text("jsonschema>=4.26.0\n", encoding="utf-8")
        findings, _ = audit(root, inventory)
        self.assertIn("mutable-dependency", {finding.check for finding in findings})

    def test_unreviewed_dependency_blocks(self) -> None:
        temporary, root, inventory = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "requirements-dev.txt").write_text("jsonschema==4.26.0\npytest==9.0.0\n", encoding="utf-8")
        findings, _ = audit(root, inventory)
        self.assertIn("dependency-unreviewed", {finding.check for finding in findings})

    def test_version_drift_blocks(self) -> None:
        temporary, root, inventory = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "requirements-dev.txt").write_text("jsonschema==4.25.0\n", encoding="utf-8")
        findings, _ = audit(root, inventory)
        self.assertIn("dependency-version-mismatch", {finding.check for finding in findings})

    def test_unknown_license_blocks(self) -> None:
        temporary, root, inventory = self.fixture()
        self.addCleanup(temporary.cleanup)
        payload = json.loads(inventory.read_text(encoding="utf-8"))
        payload["dependencies"][0]["license"] = "NOASSERTION"
        inventory.write_text(json.dumps(payload), encoding="utf-8")
        findings, _ = audit(root, inventory)
        self.assertIn("license-unapproved", {finding.check for finding in findings})


if __name__ == "__main__":
    unittest.main()
