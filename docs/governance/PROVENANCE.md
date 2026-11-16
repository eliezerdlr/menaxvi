# Provenance and relicensing policy

## Invariant

No file may enter a public MENAXVI release until its authorship, source,
license, and right to redistribute are recorded and accepted.

## Required classification

Every reviewed Git-tracked file must use one of these canonical classifications:

1. **MENAXVI-original** — created for MENAXVI and owned by the project owner;
2. **third-party-compatible** — third-party source and compatible license are
   recorded;
3. **rewritten-clean-room** — facts or concepts were reimplemented without
   copying protected expression;
4. **restricted** — retained privately but excluded from distributions;
5. **remove** — unsafe, unlicensed, obsolete, or commercially inappropriate.

The authoritative per-file records are in
[`provenance/manifest.json`](../../provenance/manifest.json). Untracked files are
work in progress and cannot enter a release artifact. Each record binds
the reviewed bytes to a SHA-256 digest and states the source, license, rights
basis, evidence, and release eligibility. Generated reports are mechanical
evidence and are excluded from the manifest because validation rewrites them.
The manifest is the trust root and cannot contain its own digest.

A license claim inside imported material is evidence to review; it is not by
itself a complete chain of title. `remove` files must not remain in the tree.
`restricted` files must remain inside `quarantine/`.

## Mandatory review flags

Manual review is required for content containing:

- names, likenesses, voices, biographies, trademarks, or implied endorsements;
- named commercial frameworks, books, courses, or proprietary methods;
- substantial quotations or close stylistic imitation;
- copied code, templates, screenshots, fonts, images, or datasets;
- offensive-security instructions or executable commands;
- unknown authorship or an absent/inconsistent license.

## Release gate

The file-rights verifier fails when a present file is unclassified, its digest
changed after review, its record lacks evidence, it is marked `remove`, or it is
`restricted` outside `quarantine/`. Repository-level MIT metadata does not
override third-party rights or separate licenses.

Run the automated rights checks with:

```bash
python3 -m unittest tests.test_file_rights
python3 scripts/verify_file_rights.py \
  --json reports/file-rights-verification.json \
  --inventory reports/provenance-inventory.json
```
