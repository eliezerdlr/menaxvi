# Policy, authorization, and evidence controls

## Purpose

This layer makes authorization a technical requirement for each execution.
It checks policy and human gates before it selects an adapter or tool.
It also writes an evidence event for each decision and result.

## Components

- `core/policy/engine.py` validates authorization scope, time, actor, and human gates.
- `core/evidence/execution.py` controls the order of policy and tool selection.
- `core/evidence/log.py` writes redacted JSON Lines events with a SHA-256 hash chain.
- `tests/test_policy_evidence.py` tests allowed and denied execution paths.

The components do not depend on a model provider or a runtime adapter.

## Authorization contract

An `AuthorizationArtifact` must contain these items:

- one authorization ID and version;
- one subject;
- one or more exact targets;
- one or more exact techniques;
- a start time and an end time with time zones;
- one or more approvers;
- one or more impact limits;
- one or more stop conditions.

The policy engine does not trust a status field in the artifact.
`DigestAuthorizationVerifier` compares the artifact SHA-256 value with a trusted allowlist.
`DigestApprovalVerifier` applies the same control to each human approval record.
The owner of the execution environment supplies both allowlists from its approval system.

The engine denies the request for each of these conditions:

- the artifact is missing or untrusted;
- the subject does not match the actor;
- the target or technique is outside the exact scope;
- the artifact is not active or has expired;
- a required human approval is missing, duplicate, rejected, early, or expired.

## Required execution order

Use `GovernedExecution.prepare()` as the tool-selection boundary.

1. The boundary writes the input and resource versions.
2. The policy engine checks the authorization artifact.
3. The policy engine checks each required human gate.
4. The boundary writes all gate decisions.
5. The boundary writes the final policy decision.
6. The boundary stops when the decision is denied.
7. The boundary calls the tool selector when the decision is allowed.
8. The boundary writes the selected adapter, tool, and version.
9. The caller supplies the result to `record_output()`.

A failure to write evidence stops the sequence before tool selection.
A tool-selection failure also creates an evidence event.

## Evidence format

The log uses one JSON object for each line.
Each event contains these fields:

- `sequence`;
- `timestamp`;
- `execution_id`;
- `event_type`;
- `data`;
- `previous_hash`;
- `event_hash`.

The supported event types are:

- `execution_started`;
- `gate_evaluated`;
- `policy_decision`;
- `tool_selected`;
- `tool_selection_failed`;
- `output_recorded`.

The log removes values for common secret keys.
It stores byte values as a size and a SHA-256 value.
It does not store an exception message from a tool selector.

Use `EvidenceLog.verify()` before you accept the log as internally consistent.
The function detects incomplete lines, sequence changes, hash changes, and chain changes.

## Operations and limits

Store the evidence log in an access-controlled directory.
Keep the trusted authorization and approval digest lists outside user-controlled input.
Use a single writer for each evidence file.
Use an external process lock when many processes can write to one file.

The hash chain detects a change inside the available file.
It does not prove who wrote the file.
Anchor the last trusted hash in an external audit store for stronger proof.

Key-name redaction cannot detect a secret under an incorrect key.
Adapters must classify sensitive fields before they send evidence data.

The policy engine uses exact string scope matching.
A future scope language must keep fail-closed behavior and must have separate tests.
