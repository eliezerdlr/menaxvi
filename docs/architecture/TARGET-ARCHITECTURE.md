# MENAXVI target architecture

**Status:** remediation proposal

## Objective

Build a portable, governed enterprise-AI context and workflow system. The core
must not depend on AIOS, Claude, or any single model/runtime.

## Target layout

```text
MENAXVI/
├── schemas/                  # contracts only; no runtime logic
├── catalog/                  # approved canonical content
│   ├── roles/
│   ├── tasks/
│   ├── workflows/
│   ├── modules/
│   └── knowledge/
├── core/
│   ├── loader/
│   ├── validator/
│   ├── planner/
│   ├── policy/
│   └── evidence/
├── adapters/                 # optional runtime integrations
│   ├── cli/
│   ├── filesystem/
│   ├── llm/
│   └── legacy/
├── quarantine/               # never distributed or loaded
├── migrations/
├── tests/
├── scripts/
├── reports/
└── docs/
```

## Processing pipeline

```text
Context → Loader → Schema Validator → Reference Resolver → Policy Engine
        → Planner → Runtime Adapter → Artifact Store + Evidence Log
```

## Core invariants

1. Invalid documents never reach the planner.
2. Missing references and dependency cycles block execution.
3. Unknown, `restricted`, or `remove` provenance is never loadable.
4. Authorization and human gates run before tool selection.
5. Every execution records inputs, versions, decisions, gates, and outputs.
6. Adapters cannot silently alter contracts or policy.
7. Roles describe professional expertise and never impersonate real people.

## Canonical resources

Every resource uses `apiVersion: menaxvi.io/v1alpha1`, a `kind`, versioned
metadata, and lifecycle status. Product resources have a pinned
`provenanceRef`; `ProvenanceRecord` omits that field to avoid recursive
bootstrap.

### Role

Required concepts: stable ID, semantic version, title, status, provenance,
summary, capabilities, constraints, assigned skills, accepted/produced
artifacts, and policies. Roles contain no vendor commands or runtime identity
replacement.

### Skill

Required concepts: bounded purpose, typed inputs/outputs, ordered procedure,
constraints, and policies. Skills remain portable and contain no adapter or
provider identity assumptions.

### Task

Required concepts: purpose, canonical role reference, typed inputs/outputs,
preconditions, ordered/dependent steps, acceptance criteria, and policies.

### Workflow

Required concepts: typed inputs, task nodes, acyclic dependencies, human or
policy gates, outputs, and explicit failure/evidence policy.

### Module

A curated product boundary listing pinned approved roles, skills, tasks, and
workflows. A module contains no copied implementation and is the unit exposed
to customers.

### ProvenanceRecord

Required concepts: subject, classification, authorship, source, license,
integrity evidence, and review state. Restricted and removal classifications
remain valid governance records but are not loadable or distributable.

## Adapters

The initial adapter is manual and deterministic: render an execution plan and
record supplied results. Model, filesystem, CLI, AIOS, and Claude adapters are
optional. Unsupported capabilities fail before execution. Removing an adapter
must not change schemas or the approved catalog.

## Migration

1. Preserve hashes and place all imported material under quarantine.
2. Implement Role, Skill, Task, Workflow, Module, and ProvenanceRecord schemas.
3. Migrate one generic low-risk vertical slice and execute it manually.
4. Use `copy-master` and `copy-squad` as the first deduplication case.
5. Replace named personas with generic professional roles.
6. Keep AIOX, runtime-specific and offensive-security content outside v1.
7. Add adapters only after canonical validation is stable.
8. Release only when provenance, references, security and acceptance gates pass.

## First vertical-slice acceptance

- one generic role, one low-risk task, one short workflow and one module;
- all references resolve and provenance is approved;
- no real-person name, impersonation, unsupported claim, or hidden dependency;
- manual adapter completes the workflow and produces a complete evidence log.
