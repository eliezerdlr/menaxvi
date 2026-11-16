"""Deterministic, provider-neutral manual workflow adapter."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PLAN_SCHEMA = "menaxvi.manual-plan/v1"
RECORD_SCHEMA = "menaxvi.manual-record/v1"
APPROVED_PROVENANCE = {
    "MENAXVI-original",
    "third-party-compatible",
    "rewritten-clean-room",
}


class ManualWorkflowError(ValueError):
    """Raised when a workflow cannot be planned or recorded safely."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManualWorkflowError(f"cannot read JSON object {target}: {error}") from error
    if not isinstance(value, dict):
        raise ManualWorkflowError(f"JSON document must contain an object: {target}")
    return value


def write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _resource_key(resource: Mapping[str, Any], *, source: Path) -> str:
    metadata = resource.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ManualWorkflowError(f"{source}: metadata must be an object")
    resource_id = metadata.get("id")
    version = metadata.get("version")
    if not isinstance(resource_id, str) or not resource_id.strip():
        raise ManualWorkflowError(f"{source}: metadata.id must be a non-empty string")
    if not isinstance(version, str) or not version.strip():
        raise ManualWorkflowError(f"{source}: metadata.version must be a non-empty string")
    return f"{resource_id}@{version}"


def _reference_key(reference: object, *, location: str, expected_kind: str) -> str:
    if not isinstance(reference, Mapping):
        raise ManualWorkflowError(f"{location} must be a {expected_kind} reference")
    if reference.get("kind") != expected_kind:
        raise ManualWorkflowError(f"{location} must reference kind {expected_kind}")
    resource_id = reference.get("id")
    version = reference.get("version")
    if not isinstance(resource_id, str) or not isinstance(version, str):
        raise ManualWorkflowError(f"{location} must contain string id and version")
    return f"{resource_id}@{version}"


def _catalog(root: Path) -> dict[str, dict[str, Any]]:
    catalog_root = root / "catalog"
    if not catalog_root.is_dir():
        raise ManualWorkflowError(f"catalog directory does not exist: {catalog_root}")
    resources: dict[str, dict[str, Any]] = {}
    for path in catalog_root.rglob("*"):
        if path.is_symlink():
            raise ManualWorkflowError(f"catalog boundary contains a symbolic link: {path}")
    for path in sorted(catalog_root.rglob("*.json")):
        resource = read_json(path)
        key = _resource_key(resource, source=path)
        if key in resources:
            raise ManualWorkflowError(f"duplicate catalog resource: {key}")
        resources[key] = resource
    if not resources:
        raise ManualWorkflowError(f"catalog contains no JSON resources: {catalog_root}")
    return resources


def _require_resource(
    resources: Mapping[str, dict[str, Any]],
    key: str,
    *,
    expected_kind: str,
    location: str,
) -> dict[str, Any]:
    resource = resources.get(key)
    if resource is None:
        raise ManualWorkflowError(f"{location}: missing catalog resource {key}")
    if resource.get("kind") != expected_kind:
        raise ManualWorkflowError(f"{location}: {key} is not kind {expected_kind}")
    metadata = resource.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("status") != "active":
        raise ManualWorkflowError(f"{location}: {key} is not active")
    return resource


def _validate_provenance(
    resources: Mapping[str, dict[str, Any]], resource: Mapping[str, Any], *, location: str
) -> None:
    metadata = resource.get("metadata")
    if not isinstance(metadata, Mapping):
        raise ManualWorkflowError(f"{location}: metadata must be an object")
    provenance_key = _reference_key(
        metadata.get("provenanceRef"),
        location=f"{location}.metadata.provenanceRef",
        expected_kind="ProvenanceRecord",
    )
    provenance = _require_resource(
        resources,
        provenance_key,
        expected_kind="ProvenanceRecord",
        location=f"{location}.metadata.provenanceRef",
    )
    spec = provenance.get("spec")
    if not isinstance(spec, Mapping):
        raise ManualWorkflowError(f"provenance {provenance_key} has no spec")
    classification = spec.get("classification")
    review = spec.get("review")
    license_record = spec.get("license")
    if classification not in APPROVED_PROVENANCE:
        raise ManualWorkflowError(f"provenance {provenance_key} is not loadable")
    if not isinstance(review, Mapping) or review.get("status") != "approved":
        raise ManualWorkflowError(f"provenance {provenance_key} is not approved")
    if not isinstance(license_record, Mapping) or license_record.get("redistributionAllowed") is not True:
        raise ManualWorkflowError(f"provenance {provenance_key} does not permit redistribution")


def _collection(value: object, *, location: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManualWorkflowError(f"{location} must be an array")
    if not all(isinstance(item, dict) for item in value):
        raise ManualWorkflowError(f"{location} must contain objects")
    return value


def _topological(items: Sequence[Mapping[str, Any]], *, location: str) -> list[Mapping[str, Any]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    order: dict[str, int] = {}
    for index, item in enumerate(items):
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ManualWorkflowError(f"{location}[{index}].id must be a non-empty string")
        if item_id in by_id:
            raise ManualWorkflowError(f"{location} contains duplicate id {item_id}")
        by_id[item_id] = item
        order[item_id] = index

    dependencies: dict[str, tuple[str, ...]] = {}
    followers: dict[str, list[str]] = {item_id: [] for item_id in by_id}
    for item_id, item in by_id.items():
        raw = item.get("dependsOn")
        if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
            raise ManualWorkflowError(f"{location}.{item_id}.dependsOn must be a string array")
        if len(raw) != len(set(raw)):
            raise ManualWorkflowError(f"{location}.{item_id}.dependsOn contains duplicates")
        for dependency in raw:
            if dependency not in by_id:
                raise ManualWorkflowError(f"{location}.{item_id} depends on missing id {dependency}")
            followers[dependency].append(item_id)
        dependencies[item_id] = tuple(raw)

    ready = sorted((item_id for item_id, values in dependencies.items() if not values), key=order.get)
    result: list[Mapping[str, Any]] = []
    remaining = {item_id: set(values) for item_id, values in dependencies.items()}
    while ready:
        item_id = ready.pop(0)
        result.append(by_id[item_id])
        for follower in sorted(followers[item_id], key=order.get):
            remaining[follower].discard(item_id)
            if not remaining[follower] and follower not in ready:
                ready.append(follower)
        ready.sort(key=order.get)
    if len(result) != len(items):
        blocked = sorted((item_id for item_id, values in remaining.items() if values), key=order.get)
        raise ManualWorkflowError(f"{location} contains a dependency cycle involving {', '.join(blocked)}")
    return result


def _resolve_workflow(
    root: str | Path, workflow_ref: str
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    project_root = Path(root).resolve()
    resources = _catalog(project_root)
    workflow = _require_resource(
        resources,
        workflow_ref,
        expected_kind="Workflow",
        location="workflow",
    )
    _validate_provenance(resources, workflow, location=workflow_ref)
    spec = workflow.get("spec")
    if not isinstance(spec, Mapping):
        raise ManualWorkflowError(f"workflow {workflow_ref} has no spec")
    nodes = _collection(spec.get("nodes"), location="workflow.spec.nodes")
    ordered_nodes = _topological(nodes, location="workflow.spec.nodes")

    resolved_tasks: list[dict[str, Any]] = []
    node_ids = {str(node["id"]) for node in ordered_nodes}
    for node in ordered_nodes:
        node_id = str(node["id"])
        task_key = _reference_key(
            node.get("taskRef"),
            location=f"workflow.spec.nodes.{node_id}.taskRef",
            expected_kind="Task",
        )
        task = _require_resource(
            resources,
            task_key,
            expected_kind="Task",
            location=f"workflow.spec.nodes.{node_id}.taskRef",
        )
        _validate_provenance(resources, task, location=task_key)
        task_spec = task.get("spec")
        if not isinstance(task_spec, Mapping):
            raise ManualWorkflowError(f"task {task_key} has no spec")
        steps = _collection(task_spec.get("steps"), location=f"task {task_key}.spec.steps")
        _topological(steps, location=f"task {task_key}.spec.steps")
        _require_task_dependencies(resources, task, task_key)
        resolved_tasks.append(task)

    gates = _collection(spec.get("gates"), location="workflow.spec.gates")
    gate_ids: set[str] = set()
    for gate in gates:
        gate_id = gate.get("id")
        if not isinstance(gate_id, str) or not gate_id:
            raise ManualWorkflowError("workflow gate id must be a non-empty string")
        if gate_id in gate_ids:
            raise ManualWorkflowError(f"workflow contains duplicate gate id {gate_id}")
        gate_ids.add(gate_id)
        after_nodes = gate.get("afterNodes")
        if not isinstance(after_nodes, list) or not after_nodes:
            raise ManualWorkflowError(f"workflow gate {gate_id} must declare afterNodes")
        missing = [node_id for node_id in after_nodes if node_id not in node_ids]
        if missing:
            raise ManualWorkflowError(f"workflow gate {gate_id} follows missing node {missing[0]}")
    return resources, workflow, resolved_tasks


def _require_task_dependencies(
    resources: Mapping[str, dict[str, Any]], task: Mapping[str, Any], task_key: str
) -> None:
    spec = task["spec"]
    role_key = _reference_key(
        spec.get("roleRef"), location=f"task {task_key}.spec.roleRef", expected_kind="Role"
    )
    role = _require_resource(resources, role_key, expected_kind="Role", location=f"task {task_key}.spec.roleRef")
    _validate_provenance(resources, role, location=role_key)
    skill_refs = spec.get("skillRefs")
    if not isinstance(skill_refs, list) or not skill_refs:
        raise ManualWorkflowError(f"task {task_key}.spec.skillRefs must be a non-empty array")
    for index, reference in enumerate(skill_refs):
        skill_key = _reference_key(
            reference,
            location=f"task {task_key}.spec.skillRefs[{index}]",
            expected_kind="Skill",
        )
        skill = _require_resource(
            resources,
            skill_key,
            expected_kind="Skill",
            location=f"task {task_key}.spec.skillRefs[{index}]",
        )
        _validate_provenance(resources, skill, location=skill_key)


def validate_workflow(root: str | Path, workflow_ref: str) -> dict[str, Any]:
    """Validate that the manual adapter can resolve and plan a workflow."""
    _, workflow, tasks = _resolve_workflow(root, workflow_ref)
    spec = workflow["spec"]
    return {
        "valid": True,
        "adapter": "manual",
        "workflow": workflow_ref,
        "nodes": len(spec["nodes"]),
        "tasks": len(tasks),
        "gates": len(spec["gates"]),
    }


def _validate_inputs(workflow: Mapping[str, Any], inputs: Mapping[str, Any]) -> None:
    contracts = _collection(workflow["spec"].get("inputs"), location="workflow.spec.inputs")
    known: set[str] = set()
    for contract in contracts:
        name = contract.get("name")
        if not isinstance(name, str) or not name:
            raise ManualWorkflowError("workflow input name must be a non-empty string")
        known.add(name)
        if contract.get("required") is True and name not in inputs:
            raise ManualWorkflowError(f"missing required workflow input: {name}")
    unknown = sorted(set(inputs) - known)
    if unknown:
        raise ManualWorkflowError(f"unknown workflow input: {unknown[0]}")


def render_plan(
    root: str | Path,
    workflow_ref: str,
    execution_id: str,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Render a deterministic plan without invoking a model or provider."""
    if not execution_id.strip():
        raise ManualWorkflowError("execution_id must not be empty")
    _, workflow, tasks = _resolve_workflow(root, workflow_ref)
    _validate_inputs(workflow, inputs)
    task_by_key = {_resource_key(task, source=Path("catalog")): task for task in tasks}
    spec = workflow["spec"]
    ordered_nodes = _topological(spec["nodes"], location="workflow.spec.nodes")
    plan_nodes: list[dict[str, Any]] = []
    for node in ordered_nodes:
        task_key = _reference_key(
            node["taskRef"],
            location=f"workflow.spec.nodes.{node['id']}.taskRef",
            expected_kind="Task",
        )
        task = task_by_key[task_key]
        task_spec = task["spec"]
        task_steps = _topological(task_spec["steps"], location=f"task {task_key}.spec.steps")
        metadata = task["metadata"]
        input_bindings = node.get("inputBindings")
        if not isinstance(input_bindings, Mapping):
            raise ManualWorkflowError(
                f"workflow.spec.nodes.{node['id']}.inputBindings must be an object"
            )
        plan_nodes.append(
            {
                "id": node["id"],
                "dependsOn": list(node["dependsOn"]),
                "inputBindings": dict(sorted(input_bindings.items())),
                "task": {
                    "id": metadata["id"],
                    "version": metadata["version"],
                    "title": metadata["title"],
                    "purpose": task_spec["purpose"],
                    "preconditions": task_spec["preconditions"],
                    "steps": list(task_steps),
                    "acceptanceCriteria": task_spec["acceptanceCriteria"],
                    "outputs": task_spec["outputs"],
                    "policies": task_spec["policies"],
                },
            }
        )
    body: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "executionId": execution_id,
        "adapter": {"name": "manual", "version": "1"},
        "workflow": {
            "id": workflow["metadata"]["id"],
            "version": workflow["metadata"]["version"],
            "title": workflow["metadata"]["title"],
            "purpose": spec["purpose"],
        },
        "inputs": dict(sorted(inputs.items())),
        "nodes": plan_nodes,
        "gates": spec["gates"],
        "outputs": spec["outputs"],
        "failurePolicy": spec["failurePolicy"],
        "evidencePolicy": spec["evidencePolicy"],
        "policies": spec["policies"],
    }
    return {**body, "planDigest": _digest(body)}


def _indexed_results(value: object, *, collection: str) -> dict[str, dict[str, Any]]:
    items = _collection(value, location=collection)
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ManualWorkflowError(f"{collection} result id must be a non-empty string")
        if item_id in indexed:
            raise ManualWorkflowError(f"{collection} contains duplicate result id {item_id}")
        indexed[item_id] = item
    return indexed


def record_results(plan: Mapping[str, Any], results: Mapping[str, Any]) -> dict[str, Any]:
    """Validate supplied manual results and create an immutable result record."""
    if plan.get("schema") != PLAN_SCHEMA:
        raise ManualWorkflowError(f"plan schema must be {PLAN_SCHEMA}")
    expected_digest = plan.get("planDigest")
    plan_body = {key: value for key, value in plan.items() if key != "planDigest"}
    if expected_digest != _digest(plan_body):
        raise ManualWorkflowError("plan digest does not match plan contents")
    execution_id = plan.get("executionId")
    if results.get("executionId") != execution_id:
        raise ManualWorkflowError("result executionId does not match the plan")

    planned_nodes = {node["id"]: node for node in plan.get("nodes", [])}
    node_results = _indexed_results(results.get("nodes"), collection="nodes")
    if set(node_results) != set(planned_nodes):
        missing = sorted(set(planned_nodes) - set(node_results))
        extra = sorted(set(node_results) - set(planned_nodes))
        detail = f"missing={missing}, extra={extra}"
        raise ManualWorkflowError(f"node results do not match the plan: {detail}")
    allowed_statuses = {"completed", "failed", "skipped"}
    for node_id, result in node_results.items():
        status = result.get("status")
        if status not in allowed_statuses:
            raise ManualWorkflowError(f"node {node_id} has unsupported status {status!r}")
        if status == "completed" and not isinstance(result.get("outputs"), Mapping):
            raise ManualWorkflowError(f"completed node {node_id} must contain outputs")
        if status == "completed":
            outputs = result["outputs"]
            expected_outputs = {
                contract["name"]
                for contract in planned_nodes[node_id]["task"]["outputs"]
            }
            missing_outputs = sorted(expected_outputs - set(outputs))
            unknown_outputs = sorted(set(outputs) - expected_outputs)
            if missing_outputs or unknown_outputs:
                raise ManualWorkflowError(
                    f"node {node_id} outputs do not match the task: "
                    f"missing={missing_outputs}, extra={unknown_outputs}"
                )
            for dependency in planned_nodes[node_id]["dependsOn"]:
                if node_results[dependency].get("status") != "completed":
                    raise ManualWorkflowError(
                        f"completed node {node_id} requires completed dependency {dependency}"
                    )

    planned_gates = {gate["id"]: gate for gate in plan.get("gates", [])}
    gate_results = _indexed_results(results.get("gates"), collection="gates")
    if set(gate_results) != set(planned_gates):
        missing = sorted(set(planned_gates) - set(gate_results))
        extra = sorted(set(gate_results) - set(planned_gates))
        detail = f"missing={missing}, extra={extra}"
        raise ManualWorkflowError(f"gate results do not match the plan: {detail}")
    gate_passes: list[bool] = []
    for gate_id, result in gate_results.items():
        gate = planned_gates[gate_id]
        gate_status = result.get("status")
        if gate_status not in {"passed", "failed", "not-run"}:
            raise ManualWorkflowError(
                f"gate {gate_id} status must be passed, failed, or not-run"
            )
        incomplete_nodes = [
            node_id
            for node_id in gate["afterNodes"]
            if node_results[node_id].get("status") != "completed"
        ]
        if incomplete_nodes and gate_status != "not-run":
            raise ManualWorkflowError(
                f"gate {gate_id} must be not-run after incomplete node {incomplete_nodes[0]}"
            )
        if gate_status == "not-run":
            gate_passes.append(False)
            continue

        decision = result.get("decision")
        if gate.get("type") == "human":
            options = gate.get("decisionOptions", [])
            if decision not in options:
                raise ManualWorkflowError(f"gate {gate_id} decision must be one of {options}")
            if not isinstance(result.get("decidedBy"), str) or not result["decidedBy"].strip():
                raise ManualWorkflowError(f"human gate {gate_id} requires decidedBy")
            if gate.get("evidenceRequired") is True and not result.get("evidence"):
                raise ManualWorkflowError(f"human gate {gate_id} requires evidence")
            approval_decision = options[0] if options else None
            if (decision == approval_decision) != (gate_status == "passed"):
                raise ManualWorkflowError(
                    f"human gate {gate_id} status does not match decision {decision}"
                )
        elif gate.get("type") == "policy":
            if decision not in {"pass", "fail", "request-review"}:
                raise ManualWorkflowError(
                    f"policy gate {gate_id} decision must be pass, fail, or request-review"
                )
            if (decision == "pass") != (gate_status == "passed"):
                raise ManualWorkflowError(
                    f"policy gate {gate_id} status does not match decision {decision}"
                )
        else:
            raise ManualWorkflowError(f"gate {gate_id} has unsupported type {gate.get('type')!r}")
        gate_passes.append(gate_status == "passed")

    all_nodes_completed = all(result["status"] == "completed" for result in node_results.values())
    any_node_failed = any(result["status"] == "failed" for result in node_results.values())
    if any_node_failed or not all(gate_passes):
        status = "failed"
    elif all_nodes_completed:
        status = "completed"
    else:
        status = "incomplete"

    supplied_outputs = results.get("outputs")
    if not isinstance(supplied_outputs, Mapping):
        raise ManualWorkflowError("results.outputs must be an object")
    expected_outputs = {output["name"] for output in plan.get("outputs", [])}
    missing_outputs = sorted(expected_outputs - set(supplied_outputs))
    unknown_outputs = sorted(set(supplied_outputs) - expected_outputs)
    if unknown_outputs or (status == "completed" and missing_outputs):
        raise ManualWorkflowError(
            "workflow outputs do not match the plan: "
            f"missing={missing_outputs}, extra={unknown_outputs}"
        )
    residual_risks = results.get("residualRisks", [])
    if not isinstance(residual_risks, list) or not all(
        isinstance(risk, str) and risk.strip() for risk in residual_risks
    ):
        raise ManualWorkflowError("results.residualRisks must be an array of non-empty strings")
    normalized_results = {
        "executionId": execution_id,
        "nodes": [node_results[node_id] for node_id in planned_nodes],
        "gates": [gate_results[gate_id] for gate_id in planned_gates],
        "outputs": dict(supplied_outputs),
        "residualRisks": residual_risks,
    }
    body = {
        "schema": RECORD_SCHEMA,
        "executionId": execution_id,
        "status": status,
        "planDigest": expected_digest,
        "workflow": plan.get("workflow"),
        "results": normalized_results,
    }
    return {**body, "recordDigest": _digest(body)}
