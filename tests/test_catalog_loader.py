from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from core.loader import (
    CatalogLoader,
    CatalogSchemaError,
    DuplicateResourceError,
    MissingReferenceError,
    ReferenceCycleError,
    ReferenceKindError,
    UnapprovedResourceError,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALID_FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "schemas" / "valid"
RESOURCE_PATHS = {
    "provenance-record.json": "provenance/provenance-record.json",
    "role.json": "roles/role.json",
    "skill.json": "skills/skill.json",
    "task.json": "tasks/task.json",
    "workflow.json": "workflows/workflow.json",
    "module.json": "modules/module.json",
}


class CatalogLoaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary_directory.name)
        shutil.copytree(REPOSITORY_ROOT / "schemas", self.project / "schemas")
        (self.project / "catalog").mkdir()
        for fixture_name, catalog_path in RESOURCE_PATHS.items():
            self._write_resource(catalog_path, self._fixture(fixture_name))

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_loads_fully_approved_resolved_catalog(self) -> None:
        catalog = CatalogLoader(self.project).load()

        self.assertEqual(6, len(catalog.resources))
        self.assertEqual("Task", catalog.require("marketing.review-copy@1.0.0").kind)
        self.assertEqual(1, len(catalog.resources_by_kind["Module"]))

    def test_rejects_schema_invalid_resource(self) -> None:
        role = self._read_resource("roles/role.json")
        role["spec"].pop("capabilities")
        self._write_resource("roles/role.json", role)

        with self.assertRaisesRegex(CatalogSchemaError, "capabilities"):
            CatalogLoader(self.project).load()

    def test_rejects_duplicate_versioned_resource_identity(self) -> None:
        self._write_resource("roles/duplicate.json", self._fixture("role.json"))

        with self.assertRaisesRegex(
            DuplicateResourceError, "marketing.copy-editor@1.0.0"
        ):
            CatalogLoader(self.project).load()

    def test_rejects_missing_resource_reference(self) -> None:
        (self.project / "catalog/provenance/provenance-record.json").unlink()

        with self.assertRaisesRegex(
            MissingReferenceError, "provenance.copy-review@1.0.0"
        ):
            CatalogLoader(self.project).load()

    def test_rejects_reference_to_wrong_resource_kind(self) -> None:
        task = self._read_resource("tasks/task.json")
        task["spec"]["roleRef"] = {
            "kind": "Role",
            "id": "marketing.copy-review",
            "version": "1.0.0",
        }
        self._write_resource("tasks/task.json", task)

        with self.assertRaisesRegex(ReferenceKindError, "expected Role"):
            CatalogLoader(self.project).load()

    def test_rejects_catalog_resource_cycle(self) -> None:
        self._write_peer_schema()
        self._write_resource("peers/one.json", self._peer("peer.one", "peer.two"))
        self._write_resource("peers/two.json", self._peer("peer.two", "peer.one"))

        with self.assertRaisesRegex(
            ReferenceCycleError,
            "peer.one@1.0.0 -> peer.two@1.0.0 -> peer.one@1.0.0",
        ):
            CatalogLoader(self.project).load()

    def test_allows_descriptive_provenance_back_reference(self) -> None:
        provenance = self._read_resource("provenance/provenance-record.json")
        provenance["spec"]["subject"] = {
            "resourceRef": {
                "kind": "Task",
                "id": "marketing.review-copy",
                "version": "1.0.0",
            }
        }
        self._write_resource("provenance/provenance-record.json", provenance)

        catalog = CatalogLoader(self.project).load()

        self.assertEqual(6, len(catalog.resources))

    def test_rejects_local_dependency_cycle(self) -> None:
        task = self._read_resource("tasks/task.json")
        task["spec"]["steps"] = [
            {
                "id": "inspect-claims",
                "instruction": "Inspect every supplied claim and its evidence.",
                "dependsOn": ["write-report"],
            },
            {
                "id": "write-report",
                "instruction": "Write the review findings and corrections.",
                "dependsOn": ["inspect-claims"],
            },
        ]
        self._write_resource("tasks/task.json", task)

        with self.assertRaisesRegex(
            ReferenceCycleError,
            "inspect-claims -> write-report -> inspect-claims",
        ):
            CatalogLoader(self.project).load()

    def test_rejects_missing_local_dependency(self) -> None:
        task = self._read_resource("tasks/task.json")
        task["spec"]["steps"][0]["dependsOn"] = ["absent-step"]
        self._write_resource("tasks/task.json", task)

        with self.assertRaisesRegex(MissingReferenceError, "absent-step"):
            CatalogLoader(self.project).load()

    def test_rejects_duplicate_local_id(self) -> None:
        task = self._read_resource("tasks/task.json")
        task["spec"]["steps"][1]["id"] = task["spec"]["steps"][0]["id"]
        task["spec"]["steps"][1]["dependsOn"] = []
        self._write_resource("tasks/task.json", task)

        with self.assertRaisesRegex(DuplicateResourceError, "duplicate local id"):
            CatalogLoader(self.project).load()

    def test_rejects_gate_after_missing_workflow_node(self) -> None:
        workflow = self._read_resource("workflows/workflow.json")
        workflow["spec"]["gates"][0]["afterNodes"] = ["absent-node"]
        self._write_resource("workflows/workflow.json", workflow)

        with self.assertRaisesRegex(MissingReferenceError, "absent-node"):
            CatalogLoader(self.project).load()

    def test_rejects_non_active_resource(self) -> None:
        role = self._read_resource("roles/role.json")
        role["metadata"]["status"] = "draft"
        self._write_resource("roles/role.json", role)

        with self.assertRaisesRegex(UnapprovedResourceError, "status 'draft'"):
            CatalogLoader(self.project).load()

    def test_rejects_unapproved_provenance_classification(self) -> None:
        provenance = self._read_resource("provenance/provenance-record.json")
        provenance["spec"]["classification"] = "restricted"
        self._write_resource("provenance/provenance-record.json", provenance)

        with self.assertRaisesRegex(UnapprovedResourceError, "restricted"):
            CatalogLoader(self.project).load()

    def test_rejects_unapproved_provenance_review(self) -> None:
        provenance = self._read_resource("provenance/provenance-record.json")
        provenance["spec"]["review"] = {"status": "pending"}
        self._write_resource("provenance/provenance-record.json", provenance)

        with self.assertRaisesRegex(UnapprovedResourceError, "pending"):
            CatalogLoader(self.project).load()

    def test_rejects_provenance_without_redistribution_rights(self) -> None:
        provenance = self._read_resource("provenance/provenance-record.json")
        provenance["spec"]["license"]["redistributionAllowed"] = False
        self._write_resource("provenance/provenance-record.json", provenance)

        with self.assertRaisesRegex(UnapprovedResourceError, "redistribution"):
            CatalogLoader(self.project).load()

    def test_does_not_read_quarantine(self) -> None:
        quarantine = self.project / "quarantine" / "invalid.json"
        quarantine.parent.mkdir()
        quarantine.write_text("not json", encoding="utf-8")

        catalog = CatalogLoader(self.project).load()

        self.assertEqual(6, len(catalog.resources))

    def _write_peer_schema(self) -> None:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://schemas.menaxvi.io/v1alpha1/peer.schema.json",
            "type": "object",
            "required": ["apiVersion", "kind", "metadata", "spec"],
            "properties": {
                "apiVersion": {"const": "menaxvi.io/v1alpha1"},
                "kind": {"const": "Peer"},
                "metadata": {"$ref": "common.schema.json#/$defs/resourceMetadata"},
                "spec": {
                    "type": "object",
                    "required": ["peerRef"],
                    "properties": {
                        "peerRef": {
                            "type": "object",
                            "required": ["kind", "id", "version"],
                            "properties": {
                                "kind": {"const": "Peer"},
                                "id": {"$ref": "common.schema.json#/$defs/canonicalId"},
                                "version": {
                                    "$ref": "common.schema.json#/$defs/semanticVersion"
                                },
                            },
                            "additionalProperties": False,
                        }
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }
        path = self.project / "schemas/menaxvi.io/v1alpha1/peer.schema.json"
        path.write_text(json.dumps(schema), encoding="utf-8")

    @staticmethod
    def _peer(resource_id: str, target_id: str) -> dict[str, Any]:
        return {
            "apiVersion": "menaxvi.io/v1alpha1",
            "kind": "Peer",
            "metadata": {
                "id": resource_id,
                "version": "1.0.0",
                "title": resource_id,
                "status": "active",
                "provenanceRef": {
                    "kind": "ProvenanceRecord",
                    "id": "provenance.copy-review",
                    "version": "1.0.0",
                },
            },
            "spec": {
                "peerRef": {
                    "kind": "Peer",
                    "id": target_id,
                    "version": "1.0.0",
                }
            },
        }

    def _fixture(self, name: str) -> dict[str, Any]:
        return json.loads((VALID_FIXTURES / name).read_text(encoding="utf-8"))

    def _read_resource(self, relative_path: str) -> dict[str, Any]:
        return json.loads(
            (self.project / "catalog" / relative_path).read_text(encoding="utf-8")
        )

    def _write_resource(self, relative_path: str, document: dict[str, Any]) -> None:
        path = self.project / "catalog" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
