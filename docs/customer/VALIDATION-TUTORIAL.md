# Tutorial: validate a repository

## Goal

Create repeatable policy and inventory evidence without executing repository content.

## Requirements

- Python 3.10 or newer;
- a trusted MENAXVI source checkout;
- write access to the selected report directory.

## Run from source

From the MENAXVI repository root:

```bash
PYTHONPATH=tooling python3 -m menaxvi --version
PYTHONPATH=tooling python3 -m menaxvi diagnose --root "$(pwd)"
mkdir -p reports/generated
PYTHONPATH=tooling python3 -m menaxvi validate \
  --root "$(pwd)" \
  --json reports/generated/validation.json \
  --inventory reports/generated/provenance-inventory.json
```

Expected version output:

```text
menaxvi 0.1.0
```

`diagnose` checks that the root exists and contains `README.md`. It also reports whether `quarantine/` is present.

## Interpret the result

| Exit status | Meaning |
|---:|---|
| `0` | The selected validation mode passed. Quarantine warnings can still exist in normal mode. |
| `1` | Validation findings failed the selected mode. |
| `2` | Command input is invalid or the repository root does not exist. |

Findings in approved product paths are errors. Findings below `quarantine/` are warnings in normal mode because quarantine content is not executable product content.

Use strict mode when all quarantine warnings must fail the command:

```bash
PYTHONPATH=tooling python3 -m menaxvi validate \
  --root "$(pwd)" \
  --strict-warnings
```

## Run the complete source-checkout gate

The portable CLI is not the complete release gate. In a trusted source checkout, run:

```bash
python3 scripts/release_gate.py --root "$(pwd)"
```

This combines tests, repository policy, content policy, file-rights checks, provenance verification, and release evidence. A passing CLI validation does not override a failing release gate.

## Recovery

- If the root is wrong, rerun `diagnose` with an absolute path.
- If report output cannot be written, select a writable directory.
- If checksum verification of a built artifact fails, do not run it; rebuild from a trusted checkout.
- Do not move warnings from quarantine into product paths to make a report appear clean.
