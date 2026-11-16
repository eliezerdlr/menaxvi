# MENAXVI install and operations runbook

## Scope and release status

This runbook covers the installable MENAXVI `0.1.0` repository-policy CLI. The
CLI is a stateless, dependency-free operator tool that checks unsafe patterns
and local links and can create hash inventory evidence. It is not the future
workflow runtime described in
[the target architecture](../architecture/TARGET-ARCHITECTURE.md).

The repository remains **pre-alpha and not approved for public release**.
Quarantined material is excluded from the executable artifact and is not cleared
for redistribution. See [the provenance policy](../governance/PROVENANCE.md).

## Prerequisites

- Python 3.10 or newer;
- a POSIX shell for the installation commands below;
- `sha256sum` for artifact verification;
- no network access and no third-party Python packages are required.

## Build and verify

Build the deterministic zip application from the repository root:

```bash
python3 scripts/build_release.py
(cd dist && sha256sum -c menaxvi-0.1.0.pyz.sha256)
python3 dist/menaxvi-0.1.0.pyz --version
```

Expected version output:

```text
menaxvi 0.1.0
```

Building the same source tree twice produces byte-identical `.pyz` files. The
builder uses sorted input paths, fixed ZIP timestamps, fixed compression, and a
fixed entry point.

## Install

Keep releases side by side so an upgrade is reversible:

```bash
release=0.1.0
base="$HOME/.local/lib/menaxvi"
install -d "$base/releases/$release" "$HOME/.local/bin"
install -m 0755 "dist/menaxvi-$release.pyz" "$base/releases/$release/menaxvi"
ln -sfn "$base/releases/$release/menaxvi" "$HOME/.local/bin/menaxvi"
"$HOME/.local/bin/menaxvi" --version
```

Add `$HOME/.local/bin` to `PATH` if it is not already present. The install does
not write outside the selected user directories.

For source-only use without installation:

```bash
PYTHONPATH=tooling python3 -m menaxvi --version
```

## Configuration

The CLI has no configuration file, background service, database, or secret.
Configuration is explicit for each invocation:

| Option | Purpose | Default |
|---|---|---|
| `--root PATH` | Repository to inspect | current directory |
| `--json PATH` | Machine-readable validation report | not written |
| `--inventory PATH` | SHA-256 inventory with quarantine status | not written |
| `--strict-warnings` | Make quarantine warnings fail the command | disabled |

Use absolute paths in automation. Write generated evidence under
`reports/generated/`, which is ignored by Git:

```bash
menaxvi validate \
  --root "$(pwd)" \
  --json reports/generated/validation.json \
  --inventory reports/generated/provenance-inventory.json
```

## Routine operation

1. Confirm the selected root:

   ```bash
   menaxvi diagnose --root "$(pwd)"
   ```

2. Run the portable repository-policy check:

   ```bash
   menaxvi validate --root "$(pwd)"
   ```

3. In a source checkout, run the complete gate for tests, provenance, content,
   and repository policy:

   ```bash
   python3 scripts/release_gate.py --root "$(pwd)"
   ```

4. Run the strict portable audit when every quarantine warning must be reviewed:

   ```bash
   menaxvi validate --root "$(pwd)" --strict-warnings
   ```

Exit statuses:

- `0`: the selected policy mode passed;
- `1`: validation findings or failed diagnostic checks;
- `2`: invalid command input or a missing repository root.

Warnings under `quarantine/` do not block normal mode. The same finding in
`catalog/`, `core/`, `adapters/`, `migrations/`, or `schemas/` is an error.

## Backup

The CLI is stateless. The authoritative state is the repository plus any
external evidence copied from `reports/generated/`.

Before an upgrade:

```bash
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$HOME/menaxvi-backups/$stamp"
install -d "$backup"
readlink "$HOME/.local/bin/menaxvi" > "$backup/active-release.txt"
git bundle create "$backup/repository.bundle" --all
if [ -d reports/generated ]; then cp -a reports/generated "$backup/"; fi
sha256sum "$backup/repository.bundle" > "$backup/SHA256SUMS"
```

Do not place credentials, `.env` files, customer data, or private prompts in the
repository or backup. Store those values in an approved secret or data system.

Verify a backup before relying on it:

```bash
(cd "$backup" && sha256sum -c SHA256SUMS)
git bundle verify "$backup/repository.bundle"
```

## Rollback

An executable rollback only changes the active symbolic link. Replace `0.1.0`
with the previously verified release:

```bash
previous=0.1.0
base="$HOME/.local/lib/menaxvi"
test -x "$base/releases/$previous/menaxvi"
ln -sfn "$base/releases/$previous/menaxvi" "$HOME/.local/bin/menaxvi"
menaxvi --version
menaxvi validate --root "$(pwd)"
```

Repository rollback is separate from executable rollback. Restore into a new
directory first; do not overwrite the working repository:

```bash
mkdir MENAXVI-restore
cd MENAXVI-restore
git clone "$backup/repository.bundle" repository
cd repository
menaxvi validate --root "$(pwd)"
```

Promote the restored copy only after checksum, validation, and operator review.

## Troubleshooting

### `menaxvi: command not found`

Run `$HOME/.local/bin/menaxvi --version`. If it works, add
`$HOME/.local/bin` to `PATH`.

### `ERROR root-not-directory`

The value passed to `--root` does not exist or is not a directory. Use
`menaxvi diagnose --root /absolute/path/to/MENAXVI`.

### Normal mode passes but strict mode fails

This is expected when restricted imported files remain in `quarantine/`. Read
the warning list. Do not suppress or relocate those files into product paths.

### Generated reports are missing

`--json` and `--inventory` are opt-in. Check that the parent directory is
writable. The CLI creates missing parent directories but does not change file
ownership or permissions.

### Checksum verification fails

Do not install or run the artifact. Rebuild from a trusted checkout and compare
the source revision. A checksum mismatch is not a recoverable warning.

## Security boundaries

- The release artifact contains only the `menaxvi` Python package. It does not
  contain `quarantine/`, reports, imported prompts, or customer data.
- The CLI reads files but does not execute repository content.
- The build does not access the network or invoke a shell installer.
- Keep artifacts and backups least-privileged and verify SHA-256 before use.
- Treat repository text and findings as untrusted data.
- Never commit credentials or include them in generated reports.
- Do not interpret a clean validator result as provenance approval. The
  provenance gate remains authoritative.

See [the security policy](../governance/SECURITY.md) for mandatory controls.

## Reproducible examples

Use the built artifact and an isolated temporary directory.

### Passing repository

```bash
fixture="$(mktemp -d)"
printf '# Fixture\n' > "$fixture/README.md"
python3 dist/menaxvi-0.1.0.pyz validate --root "$fixture"
rm -rf "$fixture"
```

Expected summary:

```text
SUMMARY errors=0 warnings=0
```

### Product-path error

```bash
fixture="$(mktemp -d)"
mkdir -p "$fixture/catalog"
printf 'eval(user_input)\n' > "$fixture/catalog/unsafe.js"
set +e
python3 dist/menaxvi-0.1.0.pyz validate --root "$fixture"
status=$?
set -e
printf 'exit=%s\n' "$status"
rm -rf "$fixture"
```

Expected result: one `dynamic-js-eval` error and `exit=1`.

### Quarantine warning

```bash
fixture="$(mktemp -d)"
mkdir -p "$fixture/quarantine/imported"
printf 'eval(user_input)\n' > "$fixture/quarantine/imported/unsafe.js"
python3 dist/menaxvi-0.1.0.pyz validate --root "$fixture"
rm -rf "$fixture"
```

Expected result: one warning, no errors, and exit status `0` in normal mode.

## Uninstall

Remove only the active link and the selected release directory:

```bash
rm "$HOME/.local/bin/menaxvi"
rm -rf "$HOME/.local/lib/menaxvi/releases/0.1.0"
```

Keep the previous release and backups until the retention policy permits their
removal.
