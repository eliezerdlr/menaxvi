#!/usr/bin/env python3
"""Run the MENAXVI acceptance suite and optionally write JSON evidence."""

from __future__ import annotations

import argparse
import json
import sys
import time
import unittest
from pathlib import Path

DETAIL_LIMIT = 12_000


class RecordingResult(unittest.TextTestResult):
    """Expose stable failure records without changing unittest behavior."""

    def records(self) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for outcome, entries in (("failure", self.failures), ("error", self.errors)):
            for test, traceback in entries:
                detail = traceback
                if len(detail) > DETAIL_LIMIT:
                    detail = "[earlier output truncated]\n" + detail[-DETAIL_LIMIT:]
                records.append({"test": test.id(), "outcome": outcome, "detail": detail})
        for test, reason in self.skipped:
            records.append({"test": test.id(), "outcome": "skipped", "detail": reason})
        return records


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-directory",
        type=Path,
        action="append",
        dest="start_directories",
        help="test directory; repeat to replace the default unit + acceptance directories",
    )
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--json", type=Path, help="write machine-readable execution evidence")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    source_directory = repository_root / "src"
    for import_root in (repository_root, source_directory):
        if str(import_root) not in sys.path:
            sys.path.insert(0, str(import_root))
    start_directories = args.start_directories or [
        repository_root / "tests",
        repository_root / "tests" / "acceptance",
    ]

    started = time.time()
    suite = unittest.TestSuite()
    for start_directory in start_directories:
        suite.addTests(
            unittest.defaultTestLoader.discover(
                str(start_directory),
                pattern=args.pattern,
                top_level_dir=str(start_directory),
            )
        )
    runner = unittest.TextTestRunner(
        verbosity=1 if args.quiet else 2,
        resultclass=RecordingResult,
    )
    result = runner.run(suite)
    duration = time.time() - started

    payload = {
        "suite": "MENAXVI acceptance",
        "testsRun": result.testsRun,
        "successful": result.wasSuccessful(),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "durationSeconds": round(duration, 3),
        "startDirectories": [str(path.resolve()) for path in start_directories],
        "records": result.records(),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        "ACCEPTANCE "
        f"tests={payload['testsRun']} failures={payload['failures']} "
        f"errors={payload['errors']} skipped={payload['skipped']} "
        f"successful={str(payload['successful']).lower()}"
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
