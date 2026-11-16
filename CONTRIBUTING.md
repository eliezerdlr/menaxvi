# Contributing to MENAXVI

Thank you for improving MENAXVI. Contributions must preserve its security,
provenance, human-approval, and evidence invariants.

## Before opening a change

1. Open an issue for material behavior, schema, policy, or architecture changes.
2. Do not submit credentials, personal data, restricted source material, copied
   personas, offensive commands, or mutable remote-install instructions.
3. Keep imported or uncleared material outside approved runtime content.
4. Use professional semantic identifiers and original expression.

## Development workflow

```bash
git clone https://github.com/eliezerdlr/menaxvi.git
cd menaxvi
python3 scripts/release_gate.py
```

The project requires Python 3.10 or newer and has no runtime dependencies.

For a change:

1. create a focused branch;
2. add or update tests with the implementation;
3. update documentation and provenance records when shipped files change;
4. run `python3 scripts/release_gate.py`;
5. open a pull request describing behavior, evidence, risks, and rollback.

## Acceptance requirements

A pull request is ready only when:

- tests and the complete release gate pass;
- new or changed shipped files have reviewed provenance records;
- authorization and human gates remain enforceable;
- errors remain safe and actionable;
- migration and rollback implications are documented;
- no critical or high-severity defect is knowingly introduced.

## Security reports

Do not disclose vulnerabilities in public issues. Follow [SECURITY.md](SECURITY.md).

By contributing, you confirm that you have the right to submit the work under
the repository's MIT license and that any third-party material is identified
with its original terms.
