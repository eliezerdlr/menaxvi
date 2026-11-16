#!/usr/bin/env python3
"""Run the complete local MENAXVI release gate and record evidence."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path
from typing import Sequence

def run(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(cwd / "tooling"), str(cwd), env.get("PYTHONPATH", "")]))
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)

def run_test_suite(root: Path, tests_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir or root / "tests"), "-p", "test_*.py"], root)

def emit(label: str, result: subprocess.CompletedProcess[str]) -> None:
    print(f"== {label} ==")
    if result.stdout: print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr: print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")
    print(f"{label}: {'PASS' if result.returncode == 0 else 'FAIL'} (exit {result.returncode})")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    report = (args.report or root / "reports/release-gate.json").resolve()
    commands = {
        "tests": [sys.executable, str(root / "scripts/run_acceptance.py"), "--quiet", "--json", str(root / "reports/acceptance.json")],
        "repositoryPolicy": [sys.executable, str(root / "scripts/validate_repository.py"), "--root", str(root), "--json", str(root / "reports/validation.json")],
        "provenance": [sys.executable, str(root / "scripts/verify_file_rights.py"), "--root", str(root), "--json", str(root / "reports/provenance-inventory.json")],
        "contentPolicy": [sys.executable, str(root / "scripts/check_release_content.py"), "--root", str(root), "--json", str(root / "reports/content-policy.json")],
    }
    results = {name: run(command, root) for name, command in commands.items()}
    for name, result in results.items(): emit(name, result)
    payload = {
        "passed": all(result.returncode == 0 for result in results.values()),
        "checks": {name: {"command": commands[name], "exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr} for name, result in results.items()},
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"EVIDENCE {report.relative_to(root)}")
    return 0 if payload["passed"] else 1

if __name__ == "__main__": sys.exit(main())
