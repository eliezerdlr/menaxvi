# MENAXVI acceptance suite

## Purpose

The acceptance suite is the executable release contract for the current
remediation baseline. The runner executes both component tests in `tests/` and
cross-cutting acceptance tests in `tests/acceptance/`. Product runtime code uses
the Python standard library. Schema tests use the development dependency pinned
in `requirements-dev.txt`.

Run it with:

```bash
python3 scripts/run_acceptance.py --json reports/acceptance.json
```

A non-zero exit blocks release. The JSON report is durable execution evidence;
it does not replace code review or provenance approval.

## Traceability

| Acceptance area | Automated evidence |
| --- | --- |
| Schemas and machine contracts | Canonical schema fixture tests plus validation JSON shape, finding fields, deterministic ordering, and supported formats |
| References | Loader/repository tests plus existing, external, anchor, encoded, missing, and repository-escape cases |
| Policies | Authorization, human gates, tool-selection ordering, quarantine isolation, and generic role language |
| Provenance | File-rights/release-gate tests plus SHA-256, byte count, path, and quarantine classification |
| Security | Release signatures, personal/opaque identifier gates, secret redaction, and evidence tamper detection |
| Migration | Corpus map/inventory tests plus proof that validation does not change source or quarantine bytes |
| CLI | Exit codes, strict-warning mode, reports, inventory, diagnosis, and release-artifact execution |
| Workflows | Canonical copy vertical slice, dependency acyclicity, safety gates, workflow scanning, and references |
| Functional regression | All component tests and the repository static validation must pass with no skipped critical test |

Test IDs from both test directories are the stable evidence identifiers for
these controls. `reports/acceptance.json` records every failure, error, and skip.

## Dependency activation

The runner already includes implemented component suites. Add cross-component
behavior tests in the acceptance directory as these remaining components become
available:

- approved-catalog loader integration with duplicate/reference/cycle rejection;
- manual planner/recorder CLI end-to-end execution;
- install, backup, rollback, and troubleshooting workflow smoke tests.

Those additions must be behavior tests against public entry points. They must
not copy implementation logic into tests. Positive and negative fixtures from
component work may be reused, but acceptance assertions must verify the
cross-component outcome.

## Release evidence rules

- Keep generated evidence under `reports/`.
- Do not commit Python caches or transient test output.
- Record the command, test count, failures, errors, skips, and residual risks.
- A skipped release-critical test is not a pass. Any temporary skip needs an
  owner, reason, and removal condition in the task or release record.
- Quarantine warnings are expected during remediation. Product-path errors are
  never accepted.
