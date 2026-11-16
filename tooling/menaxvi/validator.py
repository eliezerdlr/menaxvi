"""Static, dependency-free MENAXVI repository policy validator."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".js", ".ts", ".py", ".txt", ".toml"}
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "reports"}
PRODUCT_ROOTS = {"catalog", "core", "adapters", "migrations", "schemas", "quarantine"}
SUPPLY_CHAIN_ROOTS = PRODUCT_ROOTS | {".github"}
SUPPLY_CHAIN_ROOT_FILES = {"pyproject.toml", "requirements.txt", "requirements-dev.txt"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
GITHUB_ACTION = re.compile(r"(?m)^\s*(?:-\s*)?uses:\s*[^\s@]+@([^\s#]+)")
IMMUTABLE_GIT_REF = re.compile(r"^[0-9a-f]{40}$", re.I)

CHECKS = {
    "remote-pipe-shell": re.compile(r"(?:curl|wget)[^\n|]{0,300}\|\s*(?:ba)?sh\b", re.I),
    "mutable-version": re.compile(r"(?:@(?![0-9a-f]{40}\b)(?:latest|main|master|head)\b|git\+[^\s#]+(?:\s|$))", re.I),
    "identity-replacement": re.compile(
        r"(?:ACTIVATION-NOTICE|you are now\s+(?!an?\s+(?:AI|assistant|role)))", re.I
    ),
    "offensive-shell": re.compile(
        r"(?:--os-shell\b|meterpreter\b|mimikatz\b|webshell\b|reverse shell|credential dumping|"
        r"post-exploitation|command and control|lateral movement|brute[ -]?force|\bC2\b)",
        re.I,
    ),
    "dynamic-js-eval": re.compile(r"\b(?:eval|new\s+Function)\s*\(", re.I),
}


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    path: str
    line: int
    message: str


def files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def text_files(root: Path) -> Iterable[Path]:
    for path in files(root):
        if path.suffix.lower() in TEXT_SUFFIXES or path.name == "SKILL.md":
            yield path


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_quarantined(relative: Path) -> bool:
    return bool(relative.parts and relative.parts[0] == "quarantine")


def scan_patterns(root: Path) -> list[Finding]:
    result: list[Finding] = []
    for path in text_files(root):
        relative = path.relative_to(root)
        if not relative.parts:
            continue
        in_product = relative.parts[0] in PRODUCT_ROOTS
        in_supply_chain = (
            relative.parts[0] in SUPPLY_CHAIN_ROOTS
            or (len(relative.parts) == 1 and relative.name in SUPPLY_CHAIN_ROOT_FILES)
        )
        if not in_product and not in_supply_chain:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        severity = "warning" if is_quarantined(relative) else "error"
        if in_product:
            for name, pattern in CHECKS.items():
                for match in pattern.finditer(text):
                    excerpt = " ".join(match.group(0).split())[:120]
                    result.append(
                        Finding(
                            severity,
                            name,
                            relative.as_posix(),
                            line_number(text, match.start()),
                            excerpt,
                        )
                    )
        if in_supply_chain:
            for match in GITHUB_ACTION.finditer(text):
                reference = match.group(1)
                if not IMMUTABLE_GIT_REF.fullmatch(reference):
                    result.append(
                        Finding(
                            severity,
                            "mutable-github-action",
                            relative.as_posix(),
                            line_number(text, match.start()),
                            f"uses ref {reference}",
                        )
                    )
    return result


def scan_links(root: Path) -> list[Finding]:
    result: list[Finding] = []
    for path in text_files(root):
        if path.suffix.lower() != ".md":
            continue
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8", errors="replace")
        severity = "warning" if is_quarantined(relative) else "error"
        for match in MARKDOWN_LINK.finditer(text):
            raw = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            target = unquote(raw.split("#", 1)[0])
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
                continue
            destination = (path.parent / target).resolve()
            try:
                destination.relative_to(root.resolve())
            except ValueError:
                result.append(
                    Finding(
                        severity,
                        "link-escape",
                        relative.as_posix(),
                        line_number(text, match.start()),
                        raw,
                    )
                )
                continue
            if not destination.exists():
                result.append(
                    Finding(
                        severity,
                        "broken-link",
                        relative.as_posix(),
                        line_number(text, match.start()),
                        raw,
                    )
                )
    return result


def inventory(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in files(root):
        relative = path.relative_to(root)
        data = path.read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "provenance": "restricted" if is_quarantined(relative) else "unknown",
            }
        )
    return records


def validate(root: Path) -> dict[str, object]:
    root = root.resolve()
    findings = sorted(scan_patterns(root) + scan_links(root), key=lambda item: (item.path, item.line, item.check))
    counts = {"error": 0, "warning": 0}
    for finding in findings:
        counts[finding.severity] += 1
    return {
        "root": str(root),
        "counts": counts,
        "findings": [asdict(finding) for finding in findings],
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_findings(payload: dict[str, object]) -> list[str]:
    findings = payload["findings"]
    if not isinstance(findings, list):
        raise TypeError("findings must be a list")
    lines = [
        f"{str(finding['severity']).upper()} {finding['check']} "
        f"{finding['path']}:{finding['line']}: {finding['message']}"
        for finding in findings
        if isinstance(finding, dict)
    ]
    counts = payload["counts"]
    if not isinstance(counts, dict):
        raise TypeError("counts must be an object")
    lines.append(f"SUMMARY errors={counts['error']} warnings={counts['warning']}")
    return lines


def exit_code(payload: dict[str, object], strict_warnings: bool = False) -> int:
    counts = payload["counts"]
    if not isinstance(counts, dict):
        raise TypeError("counts must be an object")
    return 1 if counts["error"] or (strict_warnings and counts["warning"]) else 0
