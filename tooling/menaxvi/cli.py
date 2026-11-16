"""Command-line interface for MENAXVI validation tooling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from menaxvi import __version__
from menaxvi.dashboard import serve_dashboard
from menaxvi.manual import (
    ManualWorkflowError,
    read_json,
    record_results,
    render_plan,
    validate_workflow,
    write_json as write_manual_json,
)
from menaxvi.recovery import create_retry_plan, create_rollback_plan
from menaxvi.validator import exit_code, inventory, render_findings, validate, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="menaxvi", description="MENAXVI repository operations")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="run release-policy validation")
    validate_parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: current directory)")
    validate_parser.add_argument("--json", type=Path, help="write a machine-readable validation report")
    validate_parser.add_argument("--inventory", type=Path, help="write a SHA-256/provenance inventory")
    validate_parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="return a non-zero status when quarantined content produces warnings",
    )

    diagnose_parser = subparsers.add_parser("diagnose", help="check whether a repository root is usable")
    diagnose_parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: current directory)")

    dashboard_parser = subparsers.add_parser("dashboard", help="run the local customer dashboard")
    dashboard_parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: current directory)")
    dashboard_parser.add_argument("--data", type=Path, default=Path.home() / ".menaxvi" / "dashboard.json", help="durable dashboard data file")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="listen host (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=8765, help="listen port (default: 8765)")

    workflow_parser = subparsers.add_parser(
        "workflow", help="validate, plan, and record provider-neutral workflows"
    )
    workflow_commands = workflow_parser.add_subparsers(dest="workflow_command", required=True)

    workflow_validate = workflow_commands.add_parser(
        "validate", help="validate manual-adapter workflow readiness"
    )
    workflow_validate.add_argument("--root", type=Path, default=Path.cwd())
    workflow_validate.add_argument("--workflow", required=True, help="workflow id and version (id@version)")
    workflow_validate.add_argument("--json", type=Path, help="write the validation result")

    workflow_plan = workflow_commands.add_parser(
        "plan", help="render a deterministic manual execution plan"
    )
    workflow_plan.add_argument("--root", type=Path, default=Path.cwd())
    workflow_plan.add_argument("--workflow", required=True, help="workflow id and version (id@version)")
    workflow_plan.add_argument("--execution-id", required=True)
    workflow_plan.add_argument("--inputs", type=Path, required=True, help="JSON object with workflow inputs")
    workflow_plan.add_argument("--output", type=Path, required=True, help="plan JSON destination")

    workflow_record = workflow_commands.add_parser(
        "record", help="validate supplied results and write a result record"
    )
    workflow_record.add_argument("--plan", type=Path, required=True)
    workflow_record.add_argument("--results", type=Path, required=True)
    workflow_record.add_argument("--output", type=Path, required=True)

    workflow_retry = workflow_commands.add_parser(
        "retry", help="create a bounded retry plan from a failed or incomplete record"
    )
    workflow_retry.add_argument("--plan", type=Path, required=True)
    workflow_retry.add_argument("--record", type=Path, required=True)
    workflow_retry.add_argument("--execution-id", required=True, help="new execution identifier")
    workflow_retry.add_argument("--output", type=Path, required=True)

    workflow_rollback = workflow_commands.add_parser(
        "rollback", help="create a manual compensating-action plan"
    )
    workflow_rollback.add_argument("--plan", type=Path, required=True)
    workflow_rollback.add_argument("--record", type=Path, required=True)
    workflow_rollback.add_argument("--reason", required=True)
    workflow_rollback.add_argument("--output", type=Path, required=True)
    return parser


def validate_command(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR root-not-directory {root}", file=sys.stderr)
        return 2

    payload = validate(root)
    for line in render_findings(payload):
        print(line)
    if args.json:
        write_json(args.json, payload)
    if args.inventory:
        write_json(args.inventory, inventory(root))
    return exit_code(payload, args.strict_warnings)


def diagnose_command(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    checks = {
        "root_exists": root.is_dir(),
        "readme_present": (root / "README.md").is_file(),
        "quarantine_present": (root / "quarantine").is_dir(),
    }
    print(f"root={root}")
    for name, passed in checks.items():
        print(f"{name}={'ok' if passed else 'missing'}")
    return 0 if checks["root_exists"] and checks["readme_present"] else 1


def workflow_command(args: argparse.Namespace) -> int:
    try:
        if args.workflow_command == "validate":
            payload = validate_workflow(args.root, args.workflow)
            print(
                f"VALID workflow={payload['workflow']} nodes={payload['nodes']} "
                f"tasks={payload['tasks']} gates={payload['gates']} adapter=manual"
            )
            if args.json:
                write_manual_json(args.json, payload)
            return 0
        if args.workflow_command == "plan":
            payload = render_plan(
                args.root,
                args.workflow,
                args.execution_id,
                read_json(args.inputs),
            )
            write_manual_json(args.output, payload)
            print(f"PLAN execution={payload['executionId']} digest={payload['planDigest']} output={args.output}")
            return 0
        if args.workflow_command == "record":
            payload = record_results(read_json(args.plan), read_json(args.results))
            write_manual_json(args.output, payload)
            print(
                f"RECORDED execution={payload['executionId']} status={payload['status']} "
                f"digest={payload['recordDigest']} output={args.output}"
            )
            return 0
        if args.workflow_command == "retry":
            payload = create_retry_plan(
                read_json(args.plan), read_json(args.record), args.execution_id
            )
            write_manual_json(args.output, payload)
            print(
                f"RETRY execution={payload['executionId']} attempt={payload['recovery']['attempt']} "
                f"digest={payload['planDigest']} output={args.output}"
            )
            return 0
        if args.workflow_command == "rollback":
            payload = create_rollback_plan(
                read_json(args.plan), read_json(args.record), args.reason
            )
            write_manual_json(args.output, payload)
            print(
                f"ROLLBACK execution={payload['executionId']} "
                f"digest={payload['rollbackDigest']} output={args.output}"
            )
            return 0
    except ManualWorkflowError as error:
        print(f"ERROR manual-workflow {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unsupported workflow command: {args.workflow_command}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return validate_command(args)
    if args.command == "diagnose":
        return diagnose_command(args)
    if args.command == "dashboard":
        serve_dashboard(args.root, args.data, args.host, args.port)
        return 0
    if args.command == "workflow":
        return workflow_command(args)
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
