#!/usr/bin/env python3
"""Build a deterministic, dependency-free MENAXVI CLI zipapp."""

from __future__ import annotations

import argparse
import hashlib
import os
import zipfile
from pathlib import Path

FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ENTRYPOINT = b"from menaxvi.cli import main\n\nraise SystemExit(main())\n"
SHEBANG = b"#!/usr/bin/env python3\n"


def add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data, compresslevel=9)


def build(output: Path, source_root: Path) -> str:
    package_root = source_root / "menaxvi"
    sources = sorted(package_root.glob("*.py"))
    assets = sorted(package_root.glob("*.html"))
    if not sources:
        raise FileNotFoundError(f"no package sources found under {package_root}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_bytes(SHEBANG)
        with zipfile.ZipFile(temporary, mode="a") as archive:
            add_bytes(archive, "__main__.py", ENTRYPOINT)
            for source in [*sources, *assets]:
                add_bytes(archive, f"menaxvi/{source.name}", source.read_bytes())
        os.chmod(temporary, 0o755)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name(f"{output.name}.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repository_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--source", type=Path, default=repository_root / "tooling")
    parser.add_argument("--output", type=Path, default=repository_root / "dist" / "menaxvi-0.1.0.pyz")
    args = parser.parse_args()

    digest = build(args.output.resolve(), args.source.resolve())
    print(f"artifact={args.output.resolve()}")
    print(f"sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
