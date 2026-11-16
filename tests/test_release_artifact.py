from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_release.py"


class ReleaseArtifactTests(unittest.TestCase):
    def test_release_artifact_is_reproducible_and_executable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.pyz"
            second = Path(directory) / "second.pyz"
            for output in (first, second):
                completed = subprocess.run(
                    [sys.executable, str(BUILD), "--output", str(output)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertTrue(output.is_file())
                self.assertTrue(output.with_name(f"{output.name}.sha256").is_file())

            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertIn("menaxvi/dashboard.html", archive.namelist())

            executed = subprocess.run(
                [sys.executable, str(first), "--version"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, executed.returncode, executed.stderr)
            self.assertIn("menaxvi 0.1.0", executed.stdout)


if __name__ == "__main__":
    unittest.main()
