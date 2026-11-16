# Business-context onboarding contract

**Status:** `v1alpha1`

The `BusinessContext` resource captures the reviewed facts and controls that a
marketing workflow needs before execution. The canonical JSON Schema is
[`schemas/menaxvi.io/v1alpha1/business-context.schema.json`](../../schemas/menaxvi.io/v1alpha1/business-context.schema.json).

## Scope

The contract requires:

- company identity, industry, markets, and languages;
- one or more audiences and their needs and exclusions;
- one or more offers linked to audiences;
- brand positioning and explicit voice guidance;
- claims separated from their supporting evidence;
- channels linked to their intended audiences;
- blocking or warning constraints and their scope;
- approval owners with explicit approval scopes.

An approved or substantiated claim must reference at least one evidence record.
Each claim and constraint must identify at least one approval owner. Direct
contact data is not required; `userRef` can point to an identity or team in an
external authorization system.

## Validation boundaries

JSON Schema validates document shape, required fields, controlled values,
formats, and the evidence requirement for approved claims. The reference
validator owns semantic checks that JSON Schema cannot express portably:

- IDs are unique within each collection;
- `audienceRefs`, `evidenceRefs`, and `approvalOwnerRefs` resolve;
- referenced approval owners have a compatible scope;
- timestamps and lifecycle transitions are coherent;
- a provenance record exists and is approved for loading.

Unknown fields are rejected so an adapter cannot silently add ungoverned
context. The resource is additive and can be rolled back by removing the schema,
fixtures, tests, and this document; it does not change existing content or
runtime behavior.

## Verification

Install the bounded development dependency and run the focused tests:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest tests/test_business_context_schema.py
```

The valid fixture is a fictional clean-room example. Negative fixtures prove
that approved claims without evidence and contexts without approval owners are
rejected.
