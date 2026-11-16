"""Contract tests for the MENAXVI business-context onboarding schema."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "menaxvi.io" / "v1alpha1" / "business-context.schema.json"
FIXTURES = ROOT / "tests" / "fixtures" / "business-context"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class BusinessContextSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def errors_for(self, fixture_name: str):
        instance = load_json(FIXTURES / fixture_name)
        return sorted(self.validator.iter_errors(instance), key=lambda error: list(error.path))

    def test_valid_complete_context(self) -> None:
        self.assertEqual([], self.errors_for("valid.json"))

    def test_approved_claim_requires_evidence(self) -> None:
        errors = self.errors_for("invalid-approved-claim-without-evidence.json")
        self.assertTrue(
            any(
                list(error.absolute_path) == ["spec", "claims", 0, "evidenceRefs"]
                and "non-empty" in error.message
                for error in errors
            ),
            [error.message for error in errors],
        )

    def test_at_least_one_approval_owner_is_required(self) -> None:
        errors = self.errors_for("invalid-missing-approval-owners.json")
        self.assertTrue(
            any(
                list(error.absolute_path) == ["spec", "approvalOwners"]
                and "non-empty" in error.message
                for error in errors
            ),
            [error.message for error in errors],
        )

    def test_unknown_fields_are_rejected(self) -> None:
        instance = load_json(FIXTURES / "valid.json")
        instance["spec"]["company"]["unreviewedField"] = "not allowed"
        errors = sorted(self.validator.iter_errors(instance), key=lambda error: list(error.path))
        self.assertTrue(
            any(
                list(error.absolute_path) == ["spec", "company"]
                and "Additional properties are not allowed" in error.message
                for error in errors
            ),
            [error.message for error in errors],
        )


if __name__ == "__main__":
    unittest.main()
