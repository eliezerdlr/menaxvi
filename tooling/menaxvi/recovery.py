"""Fail-closed recovery plans for manual workflow executions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from menaxvi.manual import PLAN_SCHEMA, RECORD_SCHEMA, ManualWorkflowError

RETRY_SCHEMA = "menaxvi.manual-retry-plan/v1"
ROLLBACK_SCHEMA = "menaxvi.manual-rollback-plan/v1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _verified(document: Mapping[str, Any], *, schema: str, digest_field: str, label: str) -> None:
    if document.get("schema") != schema:
        raise ManualWorkflowError(f"{label} schema must be {schema}")
    expected = document.get(digest_field)
    body = {key: value for key, value in document.items() if key != digest_field}
    if expected != _digest(body):
        raise ManualWorkflowError(f"{label} digest does not match {label} contents")


def _matching_execution(plan: Mapping[str, Any], record: Mapping[str, Any]) -> None:
    if record.get("executionId") != plan.get("executionId"):
        raise ManualWorkflowError("record executionId does not match the plan")
    if record.get("planDigest") != plan.get("planDigest"):
        raise ManualWorkflowError("record planDigest does not match the plan")


def create_retry_plan(
    plan: Mapping[str, Any],
    record: Mapping[str, Any],
    new_execution_id: str,
) -> dict[str, Any]:
    """Create a bounded retry plan without executing or overwriting the prior attempt."""
    _verified(plan, schema=PLAN_SCHEMA, digest_field="planDigest", label="plan")
    _verified(record, schema=RECORD_SCHEMA, digest_field="recordDigest", label="record")
    _matching_execution(plan, record)
    if record.get("status") not in {"failed", "incomplete"}:
        raise ManualWorkflowError("only failed or incomplete executions can be retried")
    if not new_execution_id.strip():
        raise ManualWorkflowError("new_execution_id must not be empty")
    if new_execution_id == plan.get("executionId"):
        raise ManualWorkflowError("retry executionId must differ from the prior execution")

    policy = plan.get("failurePolicy")
    if not isinstance(policy, Mapping):
        raise ManualWorkflowError("plan failurePolicy must be an object")
    max_attempts = policy.get("maxAttempts")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts < 1:
        raise ManualWorkflowError("plan failurePolicy.maxAttempts must be a positive integer")
    recovery = plan.get("recovery")
    previous_attempt = recovery.get("attempt", 1) if isinstance(recovery, Mapping) else 1
    if not isinstance(previous_attempt, int) or previous_attempt < 1:
        raise ManualWorkflowError("plan recovery.attempt must be a positive integer")
    attempt = previous_attempt + 1
    if attempt > max_attempts:
        raise ManualWorkflowError(f"retry limit reached: maxAttempts={max_attempts}")

    body = {key: value for key, value in plan.items() if key != "planDigest"}
    body["executionId"] = new_execution_id
    body["recovery"] = {
        "kind": "retry",
        "attempt": attempt,
        "maxAttempts": max_attempts,
        "previousExecutionId": plan["executionId"],
        "previousRecordDigest": record["recordDigest"],
    }
    return {**body, "planDigest": _digest(body)}


def create_rollback_plan(
    plan: Mapping[str, Any],
    record: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Create operator instructions for a compensating rollback; perform no side effects."""
    _verified(plan, schema=PLAN_SCHEMA, digest_field="planDigest", label="plan")
    _verified(record, schema=RECORD_SCHEMA, digest_field="recordDigest", label="record")
    _matching_execution(plan, record)
    if not reason.strip():
        raise ManualWorkflowError("rollback reason must not be empty")

    results = record.get("results")
    if not isinstance(results, Mapping):
        raise ManualWorkflowError("record results must be an object")
    completed = [
        item.get("id")
        for item in results.get("nodes", [])
        if isinstance(item, Mapping) and item.get("status") == "completed"
    ]
    body = {
        "schema": ROLLBACK_SCHEMA,
        "executionId": plan["executionId"],
        "workflow": plan.get("workflow"),
        "reason": reason.strip(),
        "sourcePlanDigest": plan["planDigest"],
        "sourceRecordDigest": record["recordDigest"],
        "completedNodes": completed,
        "instructions": [
            "Stop downstream use of all outputs from this execution.",
            "Identify and reverse external effects manually; MENAXVI has not performed any reversal.",
            "Preserve the original plan, record, approval evidence, and this rollback plan.",
            "Record the operator, actions, timestamps, outcomes, and residual risks in separate evidence.",
        ],
        "automaticActionsPerformed": False,
    }
    return {**body, "rollbackDigest": _digest(body)}
