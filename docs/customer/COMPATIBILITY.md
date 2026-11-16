# MENAXVI 0.1.0 compatibility matrix

## Supported combinations

| Area | Supported | Not currently supported or validated |
|---|---|---|
| Python | CPython 3.10 and newer | Python 3.9 or older; alternative interpreters are unverified |
| Operating system | POSIX-style environments used by the documented shell commands | Native Windows command syntax is not documented or validated |
| Runtime dependencies | Python standard library only | Third-party runtime packages are not required |
| Installation | Source execution; deterministic `.pyz` artifact; user-local side-by-side install | System package managers, containers, and hosted service installation |
| CLI functions | `validate`, `diagnose`, `workflow validate`, `workflow plan`, `workflow record`, `workflow retry`, `workflow rollback` | Autonomous workflow execution or remote service control; rollback performs no automatic external action |
| Workflow adapter | Manual adapter | Model-provider, browser, email, advertising, CMS, or social adapters |
| Workflow catalog | `workflow.reviewed-campaign-message@1.0.0` | Full imported-corpus capability parity |
| Evidence | Local JSON reports, SHA-256 inventory, plan and record digests | Central evidence store, signatures, remote attestation |
| Network | No network access required by current CLI and build | Networked execution is outside the validated boundary |
| Data stores | Local files | Database, queue, object store, or multi-user service |

## Build-tool assumptions

- `python3` must resolve to Python 3.10 or newer.
- `sha256sum` is used by the documented artifact verification procedure.
- GNU Make is optional and is used only for convenience targets.
- `git` is required only for the documented backup procedure and source management.

## Compatibility promise

Compatibility applies only to documented public CLI commands and committed canonical resource contracts. Internal Python modules and generated report formatting can change during pre-alpha development. See [Support and upgrade policy](SUPPORT-AND-UPGRADES.md).
