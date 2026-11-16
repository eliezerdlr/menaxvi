#!/usr/bin/env python3
"""Fail-closed preflight and evidence writer for the customer dashboard journey."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

STEPS = (
    "authenticate",
    "select-workspace",
    "complete-business-context",
    "start-workflow",
    "review-plan",
    "complete-gates",
    "inspect-artifact",
    "inspect-evidence",
    "controlled-validation-failure",
    "retry-or-rollback",
    "verify-session-persistence",
)


def repository_sha(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


def valid_browser_target(target: str | None) -> bool:
    if not target:
        return False
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_preflight_report(root: Path, target: str | None, captured_at: str | None = None) -> dict[str, object]:
    timestamp = captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    target_available = valid_browser_target(target)
    blocker = {
        "id": "MEN-040-B01",
        "severity": "critical",
        "summary": "No supported customer dashboard target was supplied",
        "impact": "The real browser journey cannot start, so UI retry, rollback, and persistence cannot be evidenced.",
        "remediation": "Provide a frozen release-candidate dashboard URL and supported test authentication flow.",
    }
    steps = []
    for number, name in enumerate(STEPS, start=1):
        steps.append({
            "step": number,
            "name": name,
            "result": "READY" if target_available else ("BLOCKED" if number == 1 else "NOT_RUN"),
            "blockedBy": [] if target_available else [blocker["id"]],
        })
    return {
        "schema": "menaxvi.customer-journey/v1",
        "issue": "EMR-52",
        "capturedAtUtc": timestamp,
        "releaseCandidate": {"commitSha": repository_sha(root), "dashboardUrl": target, "frozen": False},
        "passed": False,
        "status": "READY_FOR_BROWSER_PASS" if target_available else "BLOCKED",
        "browserPassExecuted": False,
        "steps": steps,
        "screenshots": [],
        "defects": [] if target_available else [blocker],
        "retryRollbackEvidence": {"result": "NOT_RUN", "reason": "browser pass not executed"},
        "persistenceEvidence": {"result": "NOT_RUN", "reason": "browser pass not executed"},
        "security": {
            "syntheticDataOnly": True,
            "credentialsCaptured": False,
            "stackTraceExposed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dashboard-url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = (args.output or root / "reports/customer-journey.json").resolve()
    report = build_preflight_report(root, args.dashboard_url)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CUSTOMER_JOURNEY {report['status']} output={output}")
    return 2 if report["status"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
