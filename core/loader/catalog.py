"""Approved catalog loading and deterministic reference resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

APPROVED_PROVENANCE = frozenset(
    {"MENAXVI-original", "third-party-compatible", "rewritten-clean-room"}
)
LOADABLE_STATUS = "active"
PROVENANCE_KINDS = frozenset({"ProvenanceRecord"})
SCHEMA_FILENAME_KINDS = {
    "role": "Role",
    "skill": "Skill",
    "task": "Task",
    "workflow": "Workflow",
    "module": "Module",
    "provenance": "Provenance",
    "provenance-record": "ProvenanceRecord",
}


class CatalogError(ValueError):
    """Base error for a catalog that cannot be loaded safely."""


class CatalogConfigurationError(CatalogError):
    """The project does not expose the required catalog or schema boundary."""


class CatalogParseError(CatalogError):
    """A catalog or schema document is not valid JSON."""


class CatalogSchemaError(CatalogError):
    """A resource does not satisfy its canonical JSON Schema."""


class DuplicateResourceError(CatalogError):
    """Two catalog files declare the same versioned resource identity."""


class UnapprovedResourceError(CatalogError):
    """A resource or its provenance has not passed the approval gate."""


class MissingReferenceError(CatalogError):
    """A declared resource or local dependency does not exist."""


class ReferenceKindError(CatalogError):
    """A reference resolves to a resource of the wrong kind."""


class ReferenceCycleError(CatalogError):
    """A resource or local dependency graph contains a cycle."""


@dataclass(frozen=True)
class CatalogResource:
    """One schema-valid, approved resource from the canonical catalog."""

    key: str
    kind: str
    resource_id: str
    version: str
    path: Path
    document: Mapping[str, Any]


@dataclass(frozen=True)
class Catalog:
    """Immutable lookup indexes for a fully resolved catalog."""

    resources: Mapping[str, CatalogResource]
    resources_by_kind: Mapping[str, tuple[CatalogResource, ...]]

    def get(self, reference: str) -> CatalogResource | None:
        return self.resources.get(reference)

    def require(self, reference: str) -> CatalogResource:
        resource = self.get(reference)
        if resource is None:
            raise MissingReferenceError(f"resource reference does not exist: {reference}")
        return resource


@dataclass(frozen=True)
class _Reference:
    target: str
    field: str
    location: str
    expected_kinds: frozenset[str] | None
    cycle_edge: bool


@dataclass(frozen=True)
class _Schema:
    path: Path
    document: Mapping[str, Any]


class CatalogLoader:
    """Load only ``catalog/`` resources below a MENAXVI project root.

    The load is atomic: no ``Catalog`` is returned until every document passes
    schema, approval, reference, and cycle validation.
    """

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.catalog_root = self.project_root / "catalog"
        self.schema_root = self.project_root / "schemas"

    def load(self) -> Catalog:
        self._validate_boundaries()
        schemas, all_schemas = self._load_schemas()
        resources = self._load_resources(schemas, all_schemas)
        references = self._validate_references(resources, frozenset(schemas))
        self._validate_approval(resources, references)
        self._validate_resource_cycles(resources, references)
        self._validate_local_dependencies(resources.values())

        by_kind: dict[str, list[CatalogResource]] = {}
        for resource in resources.values():
            by_kind.setdefault(resource.kind, []).append(resource)
        immutable_by_kind = MappingProxyType(
            {
                kind: tuple(sorted(items, key=lambda item: item.key))
                for kind, items in sorted(by_kind.items())
            }
        )
        return Catalog(MappingProxyType(dict(sorted(resources.items()))), immutable_by_kind)

    def _validate_boundaries(self) -> None:
        if not self.project_root.is_dir():
            raise CatalogConfigurationError(
                f"project root is not a directory: {self.project_root}"
            )
        for label, root in (
            ("catalog", self.catalog_root),
            ("schema", self.schema_root),
        ):
            if not root.is_dir():
                raise CatalogConfigurationError(f"{label} directory does not exist: {root}")
            for path in root.rglob("*"):
                if path.is_symlink():
                    raise CatalogConfigurationError(
                        f"{label} boundary contains a symbolic link: {path}"
                    )

    def _load_schemas(self) -> tuple[dict[str, _Schema], tuple[_Schema, ...]]:
        schemas: dict[str, _Schema] = {}
        all_schemas: list[_Schema] = []
        schema_paths = sorted(self.schema_root.rglob("*.schema.json"))
        if not schema_paths:
            raise CatalogConfigurationError(
                f"no canonical *.schema.json files found in {self.schema_root}"
            )

        for path in schema_paths:
            document = self._read_json_object(path, "schema")
            schema = _Schema(path, document)
            all_schemas.append(schema)
            kind = self._schema_kind(path, document)
            if kind is None:
                continue
            existing = schemas.get(kind)
            if existing is not None:
                raise CatalogConfigurationError(
                    f"duplicate schema for kind {kind}: {existing.path} and {path}"
                )
            schemas[kind] = schema
        if not schemas:
            raise CatalogConfigurationError("canonical schemas declare no resource kinds")
        return schemas, tuple(all_schemas)

    def _load_resources(
        self,
        schemas: Mapping[str, _Schema],
        all_schemas: Iterable[_Schema],
    ) -> dict[str, CatalogResource]:
        resource_paths = sorted(self.catalog_root.rglob("*.json"))
        if not resource_paths:
            raise CatalogConfigurationError(
                f"approved catalog contains no JSON resources: {self.catalog_root}"
            )

        schema_registry = self._schema_registry(all_schemas)
        resources: dict[str, CatalogResource] = {}
        for path in resource_paths:
            document = self._read_json_object(path, "catalog resource")
            kind = document.get("kind")
            if not isinstance(kind, str) or kind not in schemas:
                raise CatalogSchemaError(
                    f"{path}: no canonical schema is registered for kind {kind!r}"
                )
            self._validate_schema(path, document, schemas[kind], schema_registry)
            metadata = document.get("metadata")
            if not isinstance(metadata, Mapping):
                raise CatalogSchemaError(f"{path}: metadata must be an object")
            resource_id = metadata.get("id")
            version = metadata.get("version")
            if not isinstance(resource_id, str) or not resource_id:
                raise CatalogSchemaError(f"{path}: metadata.id must be a non-empty string")
            if not isinstance(version, str) or not version:
                raise CatalogSchemaError(
                    f"{path}: metadata.version must be a non-empty string"
                )
            key = f"{resource_id}@{version}"
            existing = resources.get(key)
            if existing is not None:
                raise DuplicateResourceError(
                    f"duplicate resource {key}: {existing.path} and {path}"
                )
            resources[key] = CatalogResource(
                key=key,
                kind=kind,
                resource_id=resource_id,
                version=version,
                path=path.relative_to(self.project_root),
                document=document,
            )
        return resources

    def _validate_references(
        self,
        resources: Mapping[str, CatalogResource],
        known_kinds: frozenset[str],
    ) -> dict[str, tuple[_Reference, ...]]:
        references: dict[str, tuple[_Reference, ...]] = {}
        for resource in resources.values():
            found = tuple(self._external_references(resource, known_kinds))
            references[resource.key] = found
            for reference in found:
                target = resources.get(reference.target)
                if target is None:
                    raise MissingReferenceError(
                        f"{resource.path}{reference.location}: missing reference "
                        f"{reference.target!r}"
                    )
                if (
                    reference.expected_kinds is not None
                    and target.kind not in reference.expected_kinds
                ):
                    expected = ", ".join(sorted(reference.expected_kinds))
                    raise ReferenceKindError(
                        f"{resource.path}{reference.location}: {reference.target!r} "
                        f"is {target.kind}, expected {expected}"
                    )
        return references

    def _validate_approval(
        self,
        resources: Mapping[str, CatalogResource],
        references: Mapping[str, tuple[_Reference, ...]],
    ) -> None:
        for resource in resources.values():
            metadata = resource.document["metadata"]
            status = metadata.get("status")
            if status != LOADABLE_STATUS:
                raise UnapprovedResourceError(
                    f"{resource.path}: resource {resource.key} has status {status!r}, "
                    f"expected {LOADABLE_STATUS!r}"
                )

        for resource in resources.values():
            if resource.kind not in PROVENANCE_KINDS:
                continue
            spec = resource.document.get("spec", {})
            classification = spec.get("classification")
            review_status = spec.get("review", {}).get("status")
            redistribution_allowed = spec.get("license", {}).get(
                "redistributionAllowed"
            )
            if classification not in APPROVED_PROVENANCE:
                raise UnapprovedResourceError(
                    f"{resource.path}: provenance classification "
                    f"{classification!r} is not loadable"
                )
            if review_status != "approved":
                raise UnapprovedResourceError(
                    f"{resource.path}: provenance review status is "
                    f"{review_status!r}, expected 'approved'"
                )
            if redistribution_allowed is not True:
                raise UnapprovedResourceError(
                    f"{resource.path}: provenance does not permit redistribution"
                )

        for resource in resources.values():
            if resource.kind in PROVENANCE_KINDS:
                continue
            provenance_refs = [
                reference
                for reference in references[resource.key]
                if reference.field == "provenanceRef"
            ]
            if len(provenance_refs) != 1:
                raise UnapprovedResourceError(
                    f"{resource.path}: resource must declare exactly one provenanceRef"
                )
            provenance = resources[provenance_refs[0].target]
            provenance_spec = provenance.document.get("spec", {})
            classification = provenance_spec.get("classification")
            review_status = provenance_spec.get("review", {}).get("status")
            redistribution_allowed = provenance_spec.get("license", {}).get(
                "redistributionAllowed"
            )
            if (
                classification not in APPROVED_PROVENANCE
                or review_status != "approved"
                or redistribution_allowed is not True
            ):
                raise UnapprovedResourceError(
                    f"{resource.path}: provenance {provenance.key} is not approved"
                )

    def _validate_resource_cycles(
        self,
        resources: Mapping[str, CatalogResource],
        references: Mapping[str, tuple[_Reference, ...]],
    ) -> None:
        graph = {
            key: tuple(
                reference.target
                for reference in references[key]
                if reference.cycle_edge
            )
            for key in resources
        }
        cycle = _find_cycle(graph)
        if cycle:
            raise ReferenceCycleError(
                "catalog resource cycle: " + " -> ".join(cycle)
            )

    def _validate_local_dependencies(
        self, resources: Iterable[CatalogResource]
    ) -> None:
        for resource in resources:
            spec = resource.document.get("spec", {})
            if resource.kind == "Task":
                self._validate_dependency_collection(
                    resource, "/spec/steps", spec.get("steps", [])
                )
            elif resource.kind == "Workflow":
                node_ids = self._validate_dependency_collection(
                    resource, "/spec/nodes", spec.get("nodes", [])
                )
                gate_ids: set[str] = set()
                for index, gate in enumerate(spec.get("gates", [])):
                    gate_id = gate["id"]
                    if gate_id in gate_ids:
                        raise DuplicateResourceError(
                            f"{resource.path}/spec/gates: duplicate local id {gate_id!r}"
                        )
                    gate_ids.add(gate_id)
                    for node_id in gate["afterNodes"]:
                        if node_id not in node_ids:
                            raise MissingReferenceError(
                                f"{resource.path}/spec/gates/{index}/afterNodes: "
                                f"missing workflow node {node_id!r}"
                            )

    @staticmethod
    def _validate_dependency_collection(
        resource: CatalogResource,
        location: str,
        items: Iterable[Mapping[str, Any]],
    ) -> frozenset[str]:
        ids: dict[str, int] = {}
        materialized = tuple(items)
        for index, item in enumerate(materialized):
            node_id = item["id"]
            if node_id in ids:
                raise DuplicateResourceError(
                    f"{resource.path}{location}: duplicate local id {node_id!r}"
                )
            ids[node_id] = index

        graph: dict[str, tuple[str, ...]] = {}
        for item in materialized:
            node_id = item["id"]
            dependencies = tuple(item["dependsOn"])
            for dependency in dependencies:
                if dependency not in ids:
                    raise MissingReferenceError(
                        f"{resource.path}{location}/{ids[node_id]}/dependsOn: "
                        f"missing local dependency {dependency!r}"
                    )
            graph[node_id] = dependencies
        cycle = _find_cycle(graph)
        if cycle:
            raise ReferenceCycleError(
                f"{resource.path}{location}: dependency cycle: "
                + " -> ".join(cycle)
            )
        return frozenset(ids)

    def _external_references(
        self,
        resource: CatalogResource,
        known_kinds: frozenset[str],
    ) -> Iterable[_Reference]:
        def walk(value: Any, parts: tuple[str, ...]) -> Iterable[_Reference]:
            if isinstance(value, Mapping):
                reference_kind = value.get("kind")
                reference_id = value.get("id")
                reference_version = value.get("version")
                if (
                    reference_kind in known_kinds
                    and isinstance(reference_id, str)
                    and isinstance(reference_version, str)
                ):
                    field = parts[-1] if parts else "resourceRef"
                    descriptive_provenance_link = (
                        resource.kind in PROVENANCE_KINDS
                        and parts == ("spec", "subject", "resourceRef")
                    )
                    yield _Reference(
                        target=f"{reference_id}@{reference_version}",
                        field=field,
                        location=_json_pointer(parts),
                        expected_kinds=frozenset({reference_kind}),
                        cycle_edge=not descriptive_provenance_link,
                    )
                    return
                for field, child in value.items():
                    yield from walk(child, parts + (str(field),))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from walk(child, parts + (str(index),))

        yield from walk(resource.document, ())

    @staticmethod
    def _schema_kind(path: Path, document: Mapping[str, Any]) -> str | None:
        properties = document.get("properties")
        if isinstance(properties, Mapping):
            kind_schema = properties.get("kind")
            if isinstance(kind_schema, Mapping) and isinstance(
                kind_schema.get("const"), str
            ):
                return kind_schema["const"]
        name = path.name.removesuffix(".schema.json")
        return SCHEMA_FILENAME_KINDS.get(name)

    @staticmethod
    def _read_json_object(path: Path, label: str) -> Mapping[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CatalogParseError(f"cannot parse {label} {path}: {error}") from error
        if not isinstance(value, Mapping):
            raise CatalogParseError(f"{label} {path} must contain a JSON object")
        return value

    def _schema_registry(self, schemas: Iterable[_Schema]) -> Any:
        try:
            from referencing import Registry, Resource
            from referencing.jsonschema import DRAFT202012
        except ImportError as error:
            raise CatalogConfigurationError(
                "JSON Schema support is unavailable; install jsonschema>=4.23,<5"
            ) from error

        pairs: list[tuple[str, Any]] = []
        for schema in schemas:
            resource = Resource.from_contents(
                schema.document, default_specification=DRAFT202012
            )
            pairs.append((schema.path.resolve().as_uri(), resource))
            schema_id = schema.document.get("$id")
            if isinstance(schema_id, str):
                pairs.append((schema_id, resource))
        return Registry().with_resources(pairs)

    @staticmethod
    def _validate_schema(
        path: Path,
        document: Mapping[str, Any],
        schema: _Schema,
        registry: Any,
    ) -> None:
        try:
            from jsonschema import FormatChecker
            from jsonschema.validators import validator_for
        except ImportError as error:
            raise CatalogConfigurationError(
                "JSON Schema support is unavailable; install jsonschema>=4.23,<5"
            ) from error

        validator_class = validator_for(schema.document)
        try:
            validator_class.check_schema(schema.document)
            validator = validator_class(
                schema.document,
                registry=registry,
                format_checker=FormatChecker(),
            )
            errors = sorted(
                validator.iter_errors(document),
                key=lambda error: tuple(str(part) for part in error.absolute_path),
            )
        except Exception as error:
            raise CatalogConfigurationError(
                f"cannot evaluate canonical schema {schema.path}: {error}"
            ) from error
        if errors:
            error = errors[0]
            location = _json_pointer(tuple(str(part) for part in error.absolute_path))
            raise CatalogSchemaError(f"{path}{location}: {error.message}")


def load_catalog(project_root: str | Path = ".") -> Catalog:
    """Load the canonical approved catalog below ``project_root``."""

    return CatalogLoader(project_root).load()


def _find_cycle(graph: Mapping[str, Iterable[str]]) -> tuple[str, ...] | None:
    state: dict[str, int] = {}
    stack: list[str] = []
    positions: dict[str, int] = {}

    def visit(node: str) -> tuple[str, ...] | None:
        state[node] = 1
        positions[node] = len(stack)
        stack.append(node)
        for neighbour in sorted(graph.get(node, ())):
            neighbour_state = state.get(neighbour, 0)
            if neighbour_state == 0:
                cycle = visit(neighbour)
                if cycle:
                    return cycle
            elif neighbour_state == 1:
                start = positions[neighbour]
                return tuple(stack[start:] + [neighbour])
        stack.pop()
        positions.pop(node)
        state[node] = 2
        return None

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def _json_pointer(parts: tuple[str, ...]) -> str:
    if not parts:
        return ""
    escaped = [part.replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped)
