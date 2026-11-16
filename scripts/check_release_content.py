#!/usr/bin/env python3
"""Block personal identity, legacy authorship, and opaque IDs from release content."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOTS = {"catalog", "core", "adapters", "schemas", "src"}
SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".txt"}
PATTERNS = {
    "personal-email": re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    "personal-phone": re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)"),
    "opaque-uuid": re.compile(
        r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}(?![0-9a-f])",
        re.I,
    ),
    "opaque-provider-id": re.compile(
        r"\b(?:asset|account|user|person|face|reference)(?:[_-]?id)?\s*[:=]\s*"
        r"[`'\"]?([A-Za-z0-9_-]{12,})",
        re.I,
    ),
    "identity-replacement": re.compile(
        r"(?:ACTIVATION-NOTICE|you are now\s+(?!an?\s+(?:AI|assistant|role)))",
        re.I,
    ),
    "legacy-agent-id": re.compile(r"\bskill[a-z]{1,4}\d{2}\b", re.I),
}


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    line: int
    message: str


def _load_policy(policy_path: Path) -> dict[str, Any]:
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("schema") != "menaxvi.content-policy.v1":
        raise ValueError("invalid content policy schema")
    for key in ("blockedPersonalTerms", "blockedLegacyAuthors"):
        value = policy.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"invalid {key}")
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"invalid {key}[{index}]")
    author = policy.get("canonicalAuthor")
    if not isinstance(author, str) or not author.strip():
        raise ValueError("invalid canonicalAuthor")
    return policy


def _content_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            path.is_file()
            and relative.parts
            and relative.parts[0] in ROOTS
            and path.suffix.lower() in SUFFIXES
        ):
            result.append(path)
    return result


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _content_findings(root: Path, policy: dict[str, Any]) -> tuple[list[Finding], int]:
    patterns = dict(PATTERNS)
    for term in policy.get("blockedPersonalTerms", []):
        normalized = term.strip()
        patterns[f"personal-reference:{normalized}"] = re.compile(
            rf"(?<!\w){re.escape(normalized)}(?!\w)", re.I
        )

    findings: list[Finding] = []
    paths = _content_files(root)
    for path in paths:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for check, pattern in patterns.items():
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        check,
                        relative,
                        _line(text, match.start()),
                        " ".join(match.group(0).split())[:120],
                    )
                )
    return findings, len(paths)


def _authorship_findings(root: Path, policy: dict[str, Any]) -> tuple[list[Finding], int]:
    canonical = policy.get("canonicalAuthor")
    if canonical is None:
        return [], 0

    findings: list[Finding] = []
    blocked = {value.strip().casefold() for value in policy.get("blockedLegacyAuthors", [])}

    pyproject = root / "pyproject.toml"
    pyproject_text = pyproject.read_text(encoding="utf-8")
    declared = re.findall(
        r'^authors\s*=\s*\[\{\s*name\s*=\s*"([^"]+)"(?:\s*,[^}]*)?\s*\}\]\s*$',
        pyproject_text,
        re.M,
    )
    if declared != [canonical]:
        findings.append(
            Finding("canonical-author", "pyproject.toml", 1, "project author metadata does not match policy")
        )
    if any(value.casefold() in blocked for value in declared):
        findings.append(Finding("legacy-author", "pyproject.toml", 1, "legacy project author metadata"))

    license_path = root / "LICENSE"
    license_text = license_path.read_text(encoding="utf-8")
    if re.search(rf"^Copyright \(c\) \d{{4}}(?:-\d{{4}})? {re.escape(canonical)}$", license_text, re.M) is None:
        findings.append(Finding("canonical-author", "LICENSE", 1, "copyright author does not match policy"))

    notice_path = root / "NOTICE.md"
    notice_text = notice_path.read_text(encoding="utf-8")
    notice_statement = f"MENAXVI is authored by {canonical}."
    if notice_statement not in notice_text:
        findings.append(Finding("canonical-author", "NOTICE.md", 1, "authorship statement is missing"))

    record_count = 0
    provenance_dir = root / "catalog" / "provenance"
    for path in sorted(provenance_dir.glob("*.json")):
        relative = path.relative_to(root).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            findings.append(Finding("canonical-author", relative, 1, f"invalid provenance record: {error}"))
            continue
        if payload.get("kind") != "ProvenanceRecord":
            continue
        record_count += 1
        authors = payload.get("spec", {}).get("authors")
        expected = [{"name": canonical, "type": "person"}]
        if authors != expected:
            findings.append(
                Finding("canonical-author", relative, 1, "provenance author does not match policy")
            )
        if isinstance(authors, list):
            for author in authors:
                name = author.get("name") if isinstance(author, dict) else None
                if isinstance(name, str) and name.casefold() in blocked:
                    findings.append(Finding("legacy-author", relative, 1, "legacy provenance author"))

    if record_count == 0:
        findings.append(
            Finding("canonical-author", "catalog/provenance", 1, "no provenance records found")
        )
    return findings, record_count


def audit(root: Path, policy_path: Path) -> tuple[list[Finding], dict[str, Any]]:
    policy = _load_policy(policy_path)
    content_findings, scanned_files = _content_findings(root, policy)
    authorship_findings, authorship_records = _authorship_findings(root, policy)
    findings = sorted(
        content_findings + authorship_findings,
        key=lambda item: (item.path, item.line, item.check),
    )
    summary = {
        "schema": "menaxvi.identity-audit.v1",
        "canonicalAuthor": policy.get("canonicalAuthor"),
        "scope": {
            "contentRoots": sorted(ROOTS),
            "authorshipFiles": [
                "pyproject.toml",
                "LICENSE",
                "NOTICE.md",
                "catalog/provenance/*.json",
            ],
            "excluded": [
                "quarantine/imported (immutable restricted source)",
                "reports (generated evidence)",
                "migration inventories (historical translation evidence)",
            ],
        },
        "scannedFiles": scanned_files,
        "authorshipRecords": authorship_records,
        "counts": {"error": len(findings)},
        "zeroOccurrence": not findings,
        "findings": [asdict(item) for item in findings],
    }
    return findings, summary


def scan(root: Path, policy_path: Path) -> list[Finding]:
    return audit(root, policy_path)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    policy = (args.policy or root / "docs/governance/CONTENT-POLICY.json").resolve()
    try:
        findings, summary = audit(root, policy)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR content-policy {policy}: {error}")
        return 1
    for finding in findings:
        print(f"ERROR {finding.check} {finding.path}:{finding.line}: {finding.message}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(
        f"SUMMARY errors={len(findings)} zeroOccurrence={str(not findings).lower()} "
        f"scannedFiles={summary['scannedFiles']} authorshipRecords={summary['authorshipRecords']}"
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
