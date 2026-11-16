from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.verify_file_rights import verify


def record(path: Path, relative: str, classification: str = "MENAXVI-original") -> dict[str, object]:
    return {
        "path": relative,
        "classification": classification,
        "source": "test fixture",
        "license": "MIT" if classification != "restricted" else "unknown-or-mixed",
        "rightsBasis": "fixture evidence",
        "evidence": ["Paperclip test case"],
        "releaseAllowed": classification != "restricted",
        "sha256": hashlib.sha256((path / relative).read_bytes()).hexdigest(),
    }


class FileRightsTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, dict[str, object]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "docs").mkdir()
        (root / "docs/guide.md").write_text("guide\n", encoding="utf-8")
        (root / "quarantine/imported").mkdir(parents=True)
        (root / "quarantine/imported/legacy.md").write_text("legacy\n", encoding="utf-8")
        manifest_path = root / "provenance/manifest.json"
        manifest_path.parent.mkdir()
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "files": [
                record(root, "docs/guide.md"),
                record(root, "quarantine/imported/legacy.md", "restricted"),
            ],
        }
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        return temporary, root, manifest_path, payload

    def test_complete_reviewed_manifest_passes(self) -> None:
        temporary, root, manifest_path, _ = self.fixture()
        self.addCleanup(temporary.cleanup)
        findings, inventory = verify(root, manifest_path)
        self.assertEqual([], findings)
        self.assertEqual(2, len(inventory))

    def test_unclassified_file_blocks(self) -> None:
        temporary, root, manifest_path, _ = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "docs/new.md").write_text("new\n", encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertIn("file-unclassified", {finding.check for finding in findings})

    def test_digest_change_blocks(self) -> None:
        temporary, root, manifest_path, _ = self.fixture()
        self.addCleanup(temporary.cleanup)
        (root / "docs/guide.md").write_text("changed\n", encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertIn("digest-mismatch", {finding.check for finding in findings})

    def test_missing_evidence_reference_blocks(self) -> None:
        temporary, root, manifest_path, payload = self.fixture()
        self.addCleanup(temporary.cleanup)
        payload["files"][0]["evidence"] = ["docs/missing.md"]  # type: ignore[index]
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertIn("evidence-reference-missing", {finding.check for finding in findings})

    def test_git_scope_ignores_untracked_work_in_progress(self) -> None:
        temporary, root, manifest_path, _ = self.fixture()
        self.addCleanup(temporary.cleanup)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(
            ["git", "-C", str(root), "add", "docs/guide.md", "quarantine/imported/legacy.md", "provenance/manifest.json"],
            check=True,
        )
        (root / "draft.md").write_text("concurrent work\n", encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertEqual([], findings)

    def test_stale_summary_blocks(self) -> None:
        temporary, root, manifest_path, payload = self.fixture()
        self.addCleanup(temporary.cleanup)
        payload["summary"] = {"fileCount": 99, "classifications": {}}
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertIn("summary-mismatch", {finding.check for finding in findings})

    def test_restricted_file_must_stay_in_quarantine(self) -> None:
        temporary, root, manifest_path, payload = self.fixture()
        self.addCleanup(temporary.cleanup)
        payload["files"][0]["classification"] = "restricted"  # type: ignore[index]
        payload["files"][0]["license"] = "unknown-or-mixed"  # type: ignore[index]
        payload["files"][0]["releaseAllowed"] = False  # type: ignore[index]
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertIn("restricted-outside-quarantine", {finding.check for finding in findings})

    def test_remove_file_cannot_remain_present(self) -> None:
        temporary, root, manifest_path, payload = self.fixture()
        self.addCleanup(temporary.cleanup)
        payload["files"][0]["classification"] = "remove"  # type: ignore[index]
        payload["files"][0]["releaseAllowed"] = False  # type: ignore[index]
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        findings, _ = verify(root, manifest_path)
        self.assertIn("remove-file-present", {finding.check for finding in findings})


if __name__ == "__main__":
    unittest.main()
