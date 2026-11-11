from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import zipfile
import tarfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from package_public_source import build  # noqa: E402


class PublicSourcePackagingTests(unittest.TestCase):
    def _root(self, root: Path) -> Path:
        (root / "src").mkdir(parents=True)
        (root / "src" / "module.py").write_text("VALUE = 7\n", encoding="utf-8")
        (root / "README.md").write_text("public fixture\n", encoding="utf-8")
        entries = []
        for relative in ("README.md", "src/module.py"):
            digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
            entries.append(f"{digest}  {relative}")
        (root / "MANIFEST.sha256").write_text("\n".join(entries) + "\n", encoding="utf-8")
        return root

    def test_tar_xz_contains_only_manifested_files_and_is_checksummed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(Path(temp) / "source")
            archive = Path(temp) / "release.tar.xz"
            count, digest = build(root, archive)
            self.assertEqual(count, 3)
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertIn(digest, (Path(str(archive) + ".sha256")).read_text(encoding="utf-8"))
            with tarfile.open(archive, "r:xz") as tf:
                self.assertEqual(set(tf.getnames()), {"MANIFEST.sha256", "README.md", "src/module.py"})

    def test_zip_archive_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(Path(temp) / "source")
            first = Path(temp) / "first.zip"
            second = Path(temp) / "second.zip"
            build(root, first)
            build(root, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as zf:
                self.assertEqual(set(zf.namelist()), {"MANIFEST.sha256", "README.md", "src/module.py"})
                self.assertIsNone(zf.testzip())

    def test_rejects_stale_manifest_and_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(Path(temp) / "source")
            (root / "src" / "module.py").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "manifest checksum mismatch"):
                build(root, Path(temp) / "bad.tar.xz")
            (root / "MANIFEST.sha256").write_text("0" * 64 + "  ../outside.py\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unsafe manifest path"):
                build(root, Path(temp) / "unsafe.tar.xz")


if __name__ == "__main__":
    unittest.main()
