# Verifiable local release gate

## Command

Run the complete gate from the repository root:

```bash
make release-gate
```

The command fails when the automated tests fail or when repository policy has a
release-blocking finding. It writes consolidated evidence to
`reports/release-gate.json`, detailed findings to `reports/validation.json`, and
the file inventory to `reports/provenance-inventory.json`.

## Enforced controls

The gate checks:

- every repository file has a rights record with a classification, source,
  license, rights basis, evidence, and release decision;
- unclassified, invalid, stale, `remove`, or misplaced `restricted` records
  block release, while the generated inventory binds ordinary files to SHA-256;
- local Markdown links resolve and do not escape the repository;
- configured personal references, masked aliases, personal brands, email
  addresses, phone numbers, UUIDs, provider-style opaque identifiers, legacy
  agent IDs, and identity-replacement prompts do not enter product content;
- `pyproject.toml`, `LICENSE`, `NOTICE.md`, and every canonical provenance record
  identify Eliezer Rodrigues as the MENAXVI author; legacy author values block
  the release;
- unsafe product patterns such as remote pipe-to-shell installers, mutable
  versions, identity replacement, offensive shell guidance, and dynamic
  JavaScript evaluation are absent;
- all tests discovered under `tests/` pass.

`quarantine/` and generated `reports/` are excluded from the release file set.
Mechanical migration inventories are provenance evidence, not loadable product
content, so the identity scan targets `catalog/`, `core/`, `adapters/`,
`schemas/`, and `src/`, plus the explicit authorship metadata listed above.
`quarantine/imported/` remains immutable restricted source; it is excluded from
the zero-occurrence result and cannot be loaded or distributed. Generated
reports and migration inventories are also excluded because they record control
or historical evidence rather than candidate product content. Policy findings
in quarantine remain visible as warnings but do not approve that content for
loading or distribution. The provenance manifest is the signed-off trust root,
so it is schema-validated but cannot contain its own digest.

## Updating provenance

Review a content change, then update its exact record or applicable prefix rule
in `docs/governance/FILE-RIGHTS.json`. Approved release classifications are
`original`, `compatible`, and `clean-room`. Each record must include an auditable
source, license, rights basis, evidence, and `release_allowed` decision.

A new file without a record must remain release-blocking until provenance review
is complete. Generated inventory hashes are evidence, not a substitute for the
rights decision.

## Reversibility

The implementation is local and dependency-free. Reverting `Makefile`,
`scripts/release_gate.py`, the validator changes, tests, and the provenance
manifest removes the gate without changing quarantined source material.
