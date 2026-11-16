#!/usr/bin/env python3
"""Verify the reviewed, per-file MENAXVI provenance and rights manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

CLASSIFICATIONS = {
    "MENAXVI-original",
    "third-party-compatible",
    "rewritten-clean-room",
    "restricted",
    "remove",
}
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
GENERATED_PREFIXES = ("reports/",)
MANIFEST_PATH = Path("provenance/manifest.json")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    message: str


def subject_files(root: Path, manifest_path: Path) -> Iterable[Path]:
    resolved_manifest = manifest_path.resolve()
    candidates: Iterable[Path]
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            candidates = (root / item.decode("utf-8", "surrogateescape") for item in result.stdout.split(b"\0") if item)
        else:
            candidates = root.rglob("*")
    else:
        candidates = root.rglob("*")

    for path in sorted(candidates):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if path.resolve() == resolved_manifest or relative.startswith(GENERATED_PREFIXES):
            continue
        yield path


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or not isinstance(payload.get("files"), list):
        raise ValueError("manifest must use schemaVersion 1 and contain a files array")
    return payload


def verify(root: Path, manifest_path: Path) -> tuple[list[Finding], list[dict[str, Any]]]:
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    payload = load_manifest(manifest_path)
    findings: list[Finding] = []
    records: dict[str, dict[str, Any]] = {}

    for index, record in enumerate(payload["files"]):
        label = f"manifest.files[{index}]"
        if not isinstance(record, dict):
            findings.append(Finding("record-invalid", label, "record must be an object"))
            continue
        path = record.get("path")
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
            findings.append(Finding("path-invalid", label, str(path)))
            continue
        if path in records:
            findings.append(Finding("path-duplicate", path, "path appears more than once"))
            continue
        records[path] = record

        classification = record.get("classification")
        if classification not in CLASSIFICATIONS:
            findings.append(Finding("classification-invalid", path, str(classification)))
        for field in ("source", "license", "rightsBasis"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                findings.append(Finding("evidence-missing", path, field))
        evidence = record.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
            findings.append(Finding("evidence-missing", path, "evidence"))
        else:
            for item in evidence:
                if item.startswith(("https://", "http://", "git:", "Paperclip ")):
                    continue
                evidence_path = (root / item).resolve()
                try:
                    evidence_path.relative_to(root)
                except ValueError:
                    findings.append(Finding("evidence-reference-invalid", path, item))
                    continue
                if not evidence_path.is_file():
                    findings.append(Finding("evidence-reference-missing", path, item))
        if not isinstance(record.get("releaseAllowed"), bool):
            findings.append(Finding("release-flag-invalid", path, "releaseAllowed must be boolean"))
        digest = record.get("sha256")
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            findings.append(Finding("digest-invalid", path, str(digest)))
        if classification in {"restricted", "remove"} and record.get("releaseAllowed") is not False:
            findings.append(Finding("release-flag-invalid", path, "restricted/remove must not be release allowed"))
        if classification in {"MENAXVI-original", "third-party-compatible", "rewritten-clean-room"} and record.get("releaseAllowed") is not True:
            findings.append(Finding("release-flag-invalid", path, "approved classification must be release allowed"))
        if classification == "restricted" and not path.startswith("quarantine/"):
            findings.append(Finding("restricted-outside-quarantine", path, "restricted files must remain under quarantine/"))
        if classification == "remove":
            findings.append(Finding("remove-file-present", path, "delete the file before release"))
        if classification == "third-party-compatible" and record.get("license") in {"unknown", "unknown-or-mixed"}:
            findings.append(Finding("compatible-license-invalid", path, str(record.get("license"))))

    present: dict[str, Path] = {
        path.relative_to(root).as_posix(): path for path in subject_files(root, manifest_path)
    }
    for path, file_path in present.items():
        record = records.get(path)
        if record is None:
            findings.append(Finding("file-unclassified", path, "no reviewed manifest record"))
            continue
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if record.get("sha256") != digest:
            findings.append(Finding("digest-mismatch", path, f"expected {record.get('sha256')}, actual {digest}"))
    for path in records.keys() - present.keys():
        findings.append(Finding("record-stale", path, "manifest record has no matching file"))

    summary = payload.get("summary")
    if summary is not None:
        expected_counts = dict(sorted(Counter(str(record.get("classification")) for record in records.values()).items()))
        if summary.get("fileCount") != len(records) or summary.get("classifications") != expected_counts:
            findings.append(Finding("summary-mismatch", "manifest.summary", "summary does not match file records"))

    inventory = [records[path] for path in sorted(records)]
    return sorted(findings, key=lambda finding: (finding.path, finding.check)), inventory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--json", type=Path, help="write verification evidence")
    parser.add_argument("--inventory", type=Path, help="write the reviewed per-file inventory")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest

    try:
        findings, inventory = verify(root, manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR manifest-invalid {manifest_path}: {exc}")
        return 1

    for finding in findings:
        print(f"ERROR {finding.check} {finding.path}: {finding.message}")
    print(f"SUMMARY files={len(inventory)} errors={len(findings)}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "schema": "menaxvi.file-rights-verification.v1",
                    "manifest": str(manifest_path.relative_to(root)),
                    "fileCount": len(inventory),
                    "errors": len(findings),
                    "findings": [asdict(finding) for finding in findings],
                    "files": inventory,
                    "scope": "git-tracked files when Git metadata is available; filesystem files otherwise",
                    "excludedGeneratedPrefixes": list(GENERATED_PREFIXES),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.inventory:
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
