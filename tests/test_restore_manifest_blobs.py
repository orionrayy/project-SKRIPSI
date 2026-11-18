from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.restore_manifest_blobs import BlobRestoreError, restore


class RestoreManifestBlobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / "docs" / "example.md"
        self.target.parent.mkdir()
        self.target.write_bytes(b"line one\r\nline two\r\n")
        self.manifest = self.root / "MANIFEST.sha256"
        self.manifest.write_text(
            "0" * 64 + "  docs/example.md\n",
            encoding="utf-8",
            newline="\n",
        )

    def tearDown(self):
        self.tmp.cleanup()

    @patch("scripts.restore_manifest_blobs.subprocess.run")
    def test_restores_exact_git_blob_bytes_without_newline_conversion(self, run):
        expected = b"first line\nsecond line\n"
        run.return_value = subprocess.CompletedProcess(
            args=["git", "cat-file"],
            returncode=0,
            stdout=expected,
            stderr=b"",
        )
        count = restore(self.root)
        self.assertEqual(count, 1)
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(run.call_args.args[0], ["git", "cat-file", "blob", "HEAD:docs/example.md"])

    @patch("scripts.restore_manifest_blobs.subprocess.run")
    def test_fails_closed_when_git_blob_is_missing(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["git", "cat-file"],
            returncode=128,
            stdout=b"",
            stderr=b"not a valid object",
        )
        with self.assertRaises(BlobRestoreError):
            restore(self.root)

    @patch("scripts.restore_manifest_blobs.subprocess.run")
    def test_rejects_path_traversal_before_git_access(self, run):
        self.manifest.write_text("0" * 64 + "  ../outside.txt\n", encoding="utf-8")
        with self.assertRaises(BlobRestoreError):
            restore(self.root)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
