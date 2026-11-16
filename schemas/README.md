# MENAXVI canonical schemas

The canonical resource contracts use JSON Schema Draft 2020-12. The first
contract version is `menaxvi.io/v1alpha1` and is stored in
`schemas/menaxvi.io/v1alpha1/`.

## Resource envelope

Every canonical resource has:

- `apiVersion`: the contract version;
- `kind`: `Role`, `Skill`, `Task`, `Workflow`, `Module`, or `ProvenanceRecord`;
- `metadata.id`: a stable canonical ID;
- `metadata.version`: the resource semantic version;
- `metadata.status`: `draft`, `active`, `deprecated`, or `retired`;
- `metadata.provenanceRef`: a pinned provenance record reference, except on the
  provenance record itself to avoid recursive bootstrap;
- `spec`: the kind-specific contract.

All inter-resource references include `kind`, `id`, and an exact semantic
`version`. This makes resolution deterministic and permits a later contract
version to coexist with `v1alpha1`.

## Validation boundary

The schemas validate document shape and local values. Cross-document rules are
intentionally outside this batch. The loader/reference validator must later
verify that references exist, IDs are unique, task and workflow dependencies
refer to local nodes, and dependency graphs are acyclic.

A valid provenance record can classify content as `restricted` or `remove`.
Those classifications are records of governance decisions. The release and
loader policies must reject them from loadable or distributable sets.

## Tests and fixtures

Install the development dependency and run the automated suite:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -p 'test_*.py'
```

Positive fixtures are in `tests/fixtures/schemas/valid/`. Negative fixtures and
their expected failing keyword/path are in
`tests/fixtures/schemas/invalid/`.

The schemas are additive and reversible: consumers can continue to ignore the
new directory until they explicitly adopt `menaxvi.io/v1alpha1`.
