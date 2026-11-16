from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "menaxvi.io" / "v1alpha1"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "schemas"

SCHEMA_FILES = {
    "Role": "role.schema.json",
    "Skill": "skill.schema.json",
    "Task": "task.schema.json",
    "Workflow": "workflow.schema.json",
    "Module": "module.schema.json",
    "ProvenanceRecord": "provenance-record.schema.json",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_pointer(parts) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped) if escaped else ""


class CanonicalSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {
            path.name: load_json(path) for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
        }
        resources = [
            (schema["$id"], Resource.from_contents(schema))
            for schema in cls.schemas.values()
        ]
        cls.registry = Registry().with_resources(resources)

    def validator(self, kind: str):
        schema = self.schemas[SCHEMA_FILES[kind]]
        validator_class = validator_for(schema)
        return validator_class(
            schema,
            registry=self.registry,
            format_checker=FormatChecker(),
        )

    def test_schema_documents_are_valid_draft_2020_12(self):
        expected_files = {"common.schema.json", *SCHEMA_FILES.values()}
        self.assertTrue(expected_files.issubset(self.schemas))

        for name, schema in self.schemas.items():
            with self.subTest(schema=name):
                validator_for(schema).check_schema(schema)
                self.assertEqual(
                    "https://json-schema.org/draft/2020-12/schema",
                    schema["$schema"],
                )

    def test_positive_fixtures_validate(self):
        fixture_paths = sorted((FIXTURE_DIR / "valid").glob("*.json"))
        self.assertEqual(len(SCHEMA_FILES), len(fixture_paths))

        seen_kinds = set()
        for path in fixture_paths:
            instance = load_json(path)
            kind = instance["kind"]
            seen_kinds.add(kind)
            with self.subTest(fixture=path.name, kind=kind):
                errors = sorted(self.validator(kind).iter_errors(instance), key=str)
                self.assertEqual([], errors, "\n".join(error.message for error in errors))

        self.assertEqual(set(SCHEMA_FILES), seen_kinds)

    def test_negative_fixtures_fail_for_expected_reason(self):
        invalid_dir = FIXTURE_DIR / "invalid"
        cases = load_json(invalid_dir / "cases.json")
        fixture_names = {path.name for path in invalid_dir.glob("*.json")} - {"cases.json"}
        self.assertEqual(fixture_names, {case["file"] for case in cases})
        self.assertEqual(set(SCHEMA_FILES), {case["kind"] for case in cases})

        for case in cases:
            instance = load_json(invalid_dir / case["file"])
            with self.subTest(fixture=case["file"], kind=case["kind"]):
                errors = list(self.validator(case["kind"]).iter_errors(instance))
                matching = [
                    error
                    for error in errors
                    if error.validator == case["validator"]
                    and json_pointer(error.absolute_path) == case["path"]
                ]
                self.assertTrue(
                    matching,
                    "Expected {validator} at {path}; got:\n{errors}".format(
                        validator=case["validator"],
                        path=case["path"],
                        errors="\n".join(
                            f"{error.validator} {json_pointer(error.absolute_path)}: {error.message}"
                            for error in errors
                        ),
                    ),
                )


if __name__ == "__main__":
    unittest.main()
