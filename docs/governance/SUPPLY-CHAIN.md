# Supply-chain clearance

## Release rule

A dependency may be used only when its package name, ecosystem, exact version,
scope, license, source, and license evidence are reviewed in
[`supply-chain/dependencies.json`](../../supply-chain/dependencies.json).
Version ranges, branch names, floating tags, direct unpinned Git references,
and unreviewed packages block release.

The shipped MENAXVI zipapp has no external runtime dependency. It contains the
project's Python sources and uses only the Python standard library. The build
and development tools are not bundled into the artifact, but they remain in
scope because they can affect produced or accepted release evidence.

## Current inventory

| Package | Exact version | Scope | License | Shipped at runtime |
|---|---:|---|---|---|
| setuptools | 80.9.0 | build | MIT | No |
| jsonschema | 4.26.0 | development and schema tests | MIT | No |

This inventory is an offline clearance record. It does not claim current CVE
coverage. A release process with network access must also run a current advisory
scan against the exact versions and preserve that dated result.

## Verification

Run:

```bash
python3 scripts/audit_supply_chain.py --json reports/supply-chain-audit.json
python3 -m unittest tests.test_supply_chain
```

The audit fails for mutable declarations, missing or stale inventory records,
version drift, unknown or unapproved licenses, missing HTTPS evidence, pending
review, or an external runtime dependency.
