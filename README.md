# MENAXVI

[![CI](https://github.com/eliezerdlr/menaxvi/actions/workflows/ci.yml/badge.svg)](https://github.com/eliezerdlr/menaxvi/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#scope-and-maturity)

**Governed, evidence-driven workflows with explicit human approval.**

MENAXVI is an open-source Python platform for validating, planning, executing,
and recording professional AI-assisted workflows. It keeps policy, provenance,
human gates, artifacts, and evidence explicit instead of hiding them behind a
provider-specific runtime.

## What is included

| Component | Purpose | Boundary |
|---|---|---|
| Canonical catalog | Approved roles, tasks, workflows, modules, and knowledge | Versioned JSON resources |
| Core contracts | Loading, policy decisions, evidence, and execution state | Provider-neutral Python |
| Manual adapter | Reviewable plans and human-supplied results | No autonomous external action |
| Customer dashboard | Local onboarding, planning, approval, execution, retry, rollback, and evidence | Loopback-only HTTP service |
| Release tooling | Tests, content policy, provenance, supply-chain checks, and deterministic artifact build | Fail-closed release gate |

The public repository contains only redistributable MENAXVI source and clean-room
resources. Restricted migration source and private project operations are not
part of the OSS history.

## Requirements

- Python 3.10 or newer
- Git for source-checkout provenance verification
- No runtime Python dependencies

## Quick start

```bash
git clone https://github.com/eliezerdlr/menaxvi.git
cd menaxvi
python3 scripts/release_gate.py
python3 scripts/build_release.py
python3 dist/menaxvi-0.1.0.pyz --version
```

Run the local customer dashboard:

```bash
python3 dist/menaxvi-0.1.0.pyz dashboard \
  --root . \
  --data ~/.menaxvi/dashboard.json \
  --host 127.0.0.1 \
  --port 8765
```

Open `http://127.0.0.1:8765/`.

The dashboard intentionally refuses non-loopback hosts in this release. It is a
local evaluation interface, not a hosted multi-user service.

## Workflow example

Validate the reviewed campaign-message workflow:

```bash
PYTHONPATH=tooling:. python3 -m menaxvi workflow validate \
  --root . \
  --workflow workflow.reviewed-campaign-message@1.0.0
```

Create a deterministic plan:

```bash
PYTHONPATH=tooling:. python3 -m menaxvi workflow plan \
  --root . \
  --workflow workflow.reviewed-campaign-message@1.0.0 \
  --execution-id example-001 \
  --inputs examples/reviewed-campaign-message/inputs.json \
  --output /tmp/menaxvi-plan.json
```

MENAXVI does not silently execute external actions. The operator reviews the
plan, satisfies its approval gate, performs the bounded work, and records the
result through the CLI or dashboard.

## Release integrity

Run the authoritative gate before opening a pull request or creating a tag:

```bash
python3 scripts/release_gate.py
```

It verifies:

- unit, integration, and acceptance behavior;
- repository and content policy;
- per-file provenance and SHA-256 integrity;
- professional identifiers and authorship policy;
- dependency and supply-chain constraints;
- safe errors, authorization gates, retry, rollback, and evidence contracts.

Builds are deterministic:

```bash
python3 scripts/build_release.py
cd dist && sha256sum --check menaxvi-0.1.0.pyz.sha256
```

## Security and governance

MENAXVI uses deny-by-default policy decisions, explicit human approval, bounded
retry and rollback, tenant-aware dashboard state, PBKDF2 password hashing, and
hash-linked execution evidence. These controls do not make a local pre-alpha
interface suitable for direct Internet exposure.

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
See also:

- [Security governance](docs/governance/SECURITY.md)
- [Provenance policy](docs/governance/PROVENANCE.md)
- [Release gate](docs/governance/RELEASE-GATE.md)
- [Policy and evidence](docs/governance/POLICY-EVIDENCE.md)

## Repository structure

```text
MENAXVI/
├── catalog/             # approved canonical resources and provenance
├── core/                # loader, policy, dashboard service, and evidence
├── schemas/             # canonical validation contracts
├── tooling/menaxvi/     # dependency-free package, CLI, and local dashboard
├── scripts/             # validation, release, and supply-chain tooling
├── tests/               # unit, integration, and acceptance checks
├── examples/            # runnable synthetic workflow data
├── docs/                # architecture, customer, governance, and operations
├── provenance/          # reviewed per-file rights and integrity manifest
└── supply-chain/        # dependency and release evidence
```

Generated `build/`, `dist/`, and `reports/` directories are intentionally not
versioned. Release artifacts are attached to GitHub Releases.

## Documentation

- [Customer documentation](docs/customer/README.md)
- [Dashboard tutorial](docs/customer/DASHBOARD-TUTORIAL.md)
- [Workflow tutorial](docs/customer/WORKFLOW-TUTORIAL.md)
- [Compatibility](docs/customer/COMPATIBILITY.md)
- [Known limitations](docs/customer/LIMITATIONS.md)
- [Target architecture](docs/architecture/TARGET-ARCHITECTURE.md)
- [Product runbook](docs/operations/PRODUCT-RUNBOOK.md)
- [Acceptance suite](docs/quality/ACCEPTANCE-SUITE.md)

## Scope and maturity

MENAXVI `0.1.0` is an **OSS pre-alpha for local evaluation**.

Validated in this release:

- canonical resource loading and schema checks;
- one complete governed workflow vertical slice;
- human approval, artifact, and evidence lifecycle;
- local dashboard authentication and persistence;
- controlled failure, bounded retry, and rollback planning;
- deterministic build and fail-closed release validation.

Not claimed:

- hosted SaaS operation or remote dashboard exposure;
- production identity federation or multi-user administration;
- autonomous publishing, advertising, email, CMS, browser, or payment actions;
- identical behavior across model providers;
- legal, factual, or business correctness of user-supplied content.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). Changes must preserve provenance,
security, authorization, human-approval, and evidence invariants.

## License and authorship

MENAXVI is authored and maintained by **Eliezer Rodrigues** and distributed
under the [MIT License](LICENSE). See [NOTICE.md](NOTICE.md) for scope and
third-party notices.
