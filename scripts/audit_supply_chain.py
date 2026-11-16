#!/usr/bin/env python3
"""Verify immutable dependency declarations and their reviewed license inventory."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXACT_REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)$")
PYPROJECT_BUILD_REQUIREMENT = re.compile(r'"([A-Za-z0-9][A-Za-z0-9._-]*)==([^"\s;]+)"')
APPROVED_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "PSF-2.0"}


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    message: str


def _declared_dependencies(root: Path) -> tuple[dict[tuple[str, str], str], list[Finding]]:
    declared: dict[tuple[str, str], str] = {}
    findings: list[Finding] = []

    requirements = root / "requirements-dev.txt"
    for line_number, raw in enumerate(requirements.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = EXACT_REQUIREMENT.fullmatch(line)
        if match is None:
            findings.append(Finding("mutable-dependency", "requirements-dev.txt", f"line {line_number}: {line}"))
            continue
        declared[(match.group(1).casefold(), "development")] = match.group(2)

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    build_block = re.search(r"(?ms)^\[build-system\]\s*(.*?)(?=^\[|\Z)", pyproject)
    if build_block is None:
        findings.append(Finding("build-system-missing", "pyproject.toml", "[build-system] is required"))
    else:
        requires = re.search(r"(?m)^requires\s*=\s*\[(.*?)\]", build_block.group(1))
        if requires is None:
            findings.append(Finding("build-requirements-missing", "pyproject.toml", "build-system.requires is required"))
        else:
            matches = PYPROJECT_BUILD_REQUIREMENT.findall(requires.group(1))
            tokens = re.findall(r'"([^"]+)"', requires.group(1))
            if len(matches) != len(tokens):
                findings.append(Finding("mutable-dependency", "pyproject.toml", "all build requirements must use exact == pins"))
            for name, version in matches:
                declared[(name.casefold(), "build")] = version

    project_block = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", pyproject)
    if project_block is not None:
        dependencies = re.search(r"(?m)^dependencies\s*=\s*\[(.*?)\]", project_block.group(1))
        if dependencies and dependencies.group(1).strip():
            findings.append(Finding("runtime-dependency-present", "pyproject.toml", "shipped runtime must remain dependency-free"))
    return declared, findings


def audit(root: Path, inventory_path: Path) -> tuple[list[Finding], dict[str, Any]]:
    declared, findings = _declared_dependencies(root)
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "menaxvi.supply-chain.v1" or not isinstance(payload.get("dependencies"), list):
        raise ValueError("inventory must use menaxvi.supply-chain.v1 with a dependencies array")

    reviewed: dict[tuple[str, str], str] = {}
    for index, item in enumerate(payload["dependencies"]):
        label = f"dependencies[{index}]"
        if not isinstance(item, dict):
            findings.append(Finding("inventory-record-invalid", str(inventory_path), label))
            continue
        name, version, scope = item.get("name"), item.get("version"), item.get("scope")
        if not all(isinstance(value, str) and value.strip() for value in (name, version, scope)):
            findings.append(Finding("inventory-record-invalid", str(inventory_path), label))
            continue
        key = (name.casefold(), scope)
        if key in reviewed:
            findings.append(Finding("inventory-record-duplicate", str(inventory_path), f"{name}:{scope}"))
        reviewed[key] = version
        if item.get("ecosystem") != "pypi":
            findings.append(Finding("ecosystem-invalid", str(inventory_path), f"{name}: {item.get('ecosystem')}"))
        if item.get("license") not in APPROVED_LICENSES:
            findings.append(Finding("license-unapproved", str(inventory_path), f"{name}: {item.get('license')}"))
        for field in ("source", "licenseEvidence"):
            value = item.get(field)
            if not isinstance(value, str) or not value.startswith("https://"):
                findings.append(Finding("evidence-missing", str(inventory_path), f"{name}: {field}"))
        if item.get("reviewed") is not True:
            findings.append(Finding("review-pending", str(inventory_path), name))

    for key, version in sorted(declared.items()):
        if key not in reviewed:
            findings.append(Finding("dependency-unreviewed", "dependency manifests", f"{key[0]}=={version} ({key[1]})"))
        elif reviewed[key] != version:
            findings.append(Finding("dependency-version-mismatch", "dependency manifests", f"{key[0]}: declared {version}, reviewed {reviewed[key]}"))
    for key, version in sorted(reviewed.items()):
        if key not in declared:
            findings.append(Finding("inventory-record-stale", str(inventory_path), f"{key[0]}=={version} ({key[1]})"))

    runtime = payload.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("externalDependencies") != [] or not runtime.get("basis"):
        findings.append(Finding("runtime-inventory-invalid", str(inventory_path), "runtime dependency declaration is incomplete"))

    report = {
        "schema": "menaxvi.supply-chain-audit.v1",
        "passed": not findings,
        "declaredDependencyCount": len(declared),
        "reviewedDependencyCount": len(reviewed),
        "runtimeExternalDependencyCount": len(runtime.get("externalDependencies", [])) if isinstance(runtime, dict) else None,
        "dependencies": [
            {"name": name, "scope": scope, "version": version}
            for (name, scope), version in sorted(declared.items())
        ],
        "findings": [asdict(finding) for finding in sorted(findings, key=lambda item: (item.path, item.check, item.message))],
    }
    return sorted(findings, key=lambda item: (item.path, item.check, item.message)), report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory", type=Path, default=Path("supply-chain/dependencies.json"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory = args.inventory if args.inventory.is_absolute() else root / args.inventory
    try:
        findings, report = audit(root, inventory)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR supply-chain {inventory}: {error}")
        return 1
    for finding in findings:
        print(f"ERROR {finding.check} {finding.path}: {finding.message}")
    print(f"SUMMARY dependencies={report['declaredDependencyCount']} errors={len(findings)}")
    if args.json:
        output = args.json if args.json.is_absolute() else root / args.json
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
