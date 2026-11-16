# MENAXVI security policy

- Instructions never override system, legal, authorization, privacy, or safety
  requirements.
- Active security testing requires documented authorization, explicit targets,
  scope, permitted techniques, impact limits, and stop conditions.
- Remote installers must be version-pinned and integrity-verified; piping a
  network response directly into a shell is prohibited.
- Credentials must never be committed, logged, embedded in prompts, or placed
  in generated reports.
- Offensive commands are non-executable reference data until a dedicated
  authorization gate validates their use.
- Prompt content must describe a role or expertise; it must not claim to replace
  the runtime identity or higher-priority instructions.

## Control mapping

| Requirement | Owner | Preventive control | Automated evidence | Exception process |
|---|---|---|---|---|
| Authorization before tool selection | Security and Governance | `GovernedExecution.prepare()` stops denied requests before the selector runs. | `tests/test_policy_evidence.py` checks allowed, denied, expired, and mismatched cases. | Record a new scoped authorization artifact. Do not bypass the gate. |
| Human approval gates | Workflow owner | The policy engine requires one active approval for each declared gate. | Tests cover missing, duplicate, expired, and valid approvals. | The workflow owner must issue a new approval for the same execution ID. |
| Complete execution evidence | Runtime owner | The evidence log records inputs, versions, decisions, approvals, tools, and outputs. | Tests verify event order, secret redaction, and the hash chain. | Stop execution when the evidence store is not available. |
| Credential protection | Security and Governance | Evidence redaction removes common secret fields before a write. | Tests verify input and output secret redaction. | Remove the data and rotate an exposed credential through the approved process. |

See [Policy, authorization, and evidence controls](POLICY-EVIDENCE.md) for the detailed contract and limits.
