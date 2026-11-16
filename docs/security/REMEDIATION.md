# MENAXVI security remediation backlog

Static review only. No offensive command was executed.

## P1 — Release blockers

### SEC-001 — Quarantine executable offensive content

Locations include `commands/cybersecurity/data/security-tools-catalog.yaml:112-155,212-227`.
The catalog contains copy/paste exploitation, remote shell, brute-force,
credential extraction, persistence and post-exploitation material.

**Action:** exclude it from all public/runtime indexes. Retain only defensive,
conceptual metadata in distributable modules.

**Acceptance:** public artifacts contain no shell, credential dumping, brute
force, persistence, C2, webshell or movement-lateral commands.

### SEC-002 — Make authorization a technical prerequisite

Locations include `commands/cybersecurity/tasks/generate-commands.md:43-94` and
`commands/cybersecurity/agents/skille25.md:21-87`.

**Action:** fail closed unless a central signed/validated authorization artifact
matches target, allowed techniques, validity period, impact and stop conditions.
Direct loading must not bypass the workflow gate. Remove exfiltration and
persistence from public capabilities.

**Acceptance:** missing, expired or mismatched authorization returns no command.

### SEC-003 — Remove identity-hijacking prompts

Representative locations include:

- `commands/copy-squad/agents/skillcp53.md:3`
- `commands/copy-squad/agents/skillcp54.md:3`
- `commands/hormozi-squad/agents/skilln03.md:3`
- `commands/traffic-masters/agents/skillt11.md:3`
- `commands/advisory-board/agents/skilln27.md:3`

**Action:** replace `ACTIVATION-NOTICE: You are now ...` and real-person
impersonation with generic professional roles that preserve all higher-priority
runtime, legal, privacy and safety rules.

**Acceptance:** CI rejects identity replacement and claims of being or speaking
for a real person.

### SEC-004 — Quarantine post-exploitation and C2 guidance

Location: `commands/cybersecurity/agents/skille34.md:40-81`.

**Action:** public content retains only non-destructive validation, minimum
evidence, risk explanation and remediation.

### SEC-005 — Remove mutable remote installation

Locations include `commands/cybersecurity/data/security-tools-catalog.yaml:33-45,114,121,152,230`.

**Action:** prohibit `curl | sh`; pin immutable versions/commits, verify hashes
or signatures, and use lockfiles.

**Acceptance:** automated scanning rejects pipe-to-shell, `@latest`, `@master`
and unpinned installers.

## P2 — Engineering controls

### SEC-006 — Pin third-party CI actions and dependencies

Use immutable versions or commit SHAs with reviewed update procedures.

### SEC-007 — Treat PRs, diffs and imported content as untrusted data

Never execute or follow instructions embedded in reviewed artifacts. Parse and
quote them as data; restrict tools and filesystem scope during reviews.

### SEC-008 — Restrict helper scripts

Validate and constrain project paths, reject traversal/symlink escape, avoid
dynamic code evaluation, default to dry-run for destructive operations, and
require explicit confirmation for deletion or overwrite.

### SEC-009 — Remove personal and provider-specific identity data

Review `skills/skillct02/references/biblia-jpv.md` and
`skills/skillct02/references/identidade-jpv.md`. Move real asset IDs, account
references and biometric/visual identity profiles to approved private storage;
use synthetic placeholders in distributable content.

### SEC-010 — Turn policy into enforceable controls

`docs/governance/SECURITY.md` must map every security requirement to an owner,
preventive control, automated check, exception process and release evidence.

### SEC-011 — Enforce provenance

Every distributable file must have an approved provenance classification. The
release fails on unknown, `restricted`, or `remove` records.

## Positive evidence

- No literal credential or private-key pattern was found in the static review.
- `commands/cybersecurity/workflows/wf-pentest-engagement.yaml:34-56,94-101`
  contains useful documentary authorization gates, but direct loading can still
  bypass them until SEC-002 is implemented.

## Execution order

1. SEC-001, SEC-002 and SEC-003.
2. Physical quarantine and provenance inventory.
3. SEC-004 through SEC-009.
4. SEC-010 and SEC-011 as release automation.
