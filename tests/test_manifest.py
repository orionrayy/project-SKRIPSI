from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.verify_manifest import verify
from scripts.build_manifest import build as build_manifest, is_excluded
from scripts.package_public_source import build as build_public_bundle


class ManifestVerificationTests(unittest.TestCase):
    def test_verifies_sha256_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "src" / "module.py"
            target.parent.mkdir()
            target.write_text("value = 1\n", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (root / "MANIFEST.sha256").write_text(f"{digest}  src/module.py\n", encoding="utf-8")
            self.assertEqual(verify(root, Path("MANIFEST.sha256")), [])

    def test_detects_changed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "file.txt"
            target.write_text("original", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (root / "MANIFEST.sha256").write_text(f"{digest}  file.txt\n", encoding="utf-8")
            target.write_text("modified", encoding="utf-8")
            self.assertIn("SHA-256 mismatch: file.txt", verify(root, Path("MANIFEST.sha256")))

    def test_rejects_path_traversal_and_duplicate_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = "0" * 64
            (root / "MANIFEST.sha256").write_text(
                f"{payload}  ../outside.txt\n{payload}  safe.txt\n{payload}  safe.txt\n",
                encoding="utf-8",
            )
            errors = verify(root, Path("MANIFEST.sha256"))
            self.assertTrue(any("unsafe or self-referential" in error for error in errors))
            self.assertTrue(any("duplicate manifest path" in error for error in errors))

    def test_rejects_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root.parent / f"{root.name}-outside.txt"
            outside.write_text("do not follow", encoding="utf-8")
            try:
                link = root / "link.txt"
                link.symlink_to(outside)
                digest = hashlib.sha256(outside.read_bytes()).hexdigest()
                (root / "MANIFEST.sha256").write_text(f"{digest}  link.txt\n", encoding="utf-8")
                self.assertTrue(any("symlinked manifest target" in error for error in verify(root, Path("MANIFEST.sha256"))))
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            finally:
                outside.unlink(missing_ok=True)

    def test_sanitized_phase_summaries_are_manifestable_but_research_rows_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            safe = root / "P2_EXECUTION_REPORT.md"
            private = root / "P2_EXTRACTION.json"
            safe.write_text("Aggregate-only public summary", encoding="utf-8")
            private.write_text("{\"private\":true}", encoding="utf-8")
            self.assertFalse(is_excluded(safe, root, "MANIFEST.sha256"))
            self.assertTrue(is_excluded(private, root, "MANIFEST.sha256"))

    def test_public_bundle_contains_exact_manifest_allowlist_only(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "engine.py").write_text("value = 1\n", encoding="utf-8")
            (root / "P1_HUMAN_ACCEPTANCE_RECORD.md").write_text("sanitized acceptance summary", encoding="utf-8")
            (root / "P2_EXECUTION_REPORT.md").write_text("aggregate only", encoding="utf-8")
            (root / "P2_EXTRACTION.json").write_text("private rows", encoding="utf-8")
            count, _ = build_manifest(root, "MANIFEST.sha256")
            self.assertEqual(count, 3)
            archive = root / "dist" / "public.zip"
            build_public_bundle(root, archive)
            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(set(zf.namelist()), {"MANIFEST.sha256", "src/engine.py", "P1_HUMAN_ACCEPTANCE_RECORD.md", "P2_EXECUTION_REPORT.md"})
                self.assertIsNone(zf.testzip())
                self.assertNotIn("P2_EXTRACTION.json", zf.namelist())


if __name__ == "__main__":
    unittest.main()
