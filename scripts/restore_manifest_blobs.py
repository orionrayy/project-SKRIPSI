#!/usr/bin/env python3
"""Restore manifest-listed working-tree files from exact Git blob bytes.

Git checkout filters can alter line endings on Windows before a byte-level
manifest check. This helper bypasses working-tree conversion by reading blobs
with git cat-file and writing the returned bytes directly.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path, PurePosixPath
from typing import Sequence


class BlobRestoreError(ValueError):
    """Raised when a manifest target cannot be safely restored from Git."""


def _manifest_targets(root: Path, manifest_path: Path) -> list[str]:
    manifest = manifest_path if manifest_path.is_absolute() else root / manifest_path
    if manifest.is_symlink() or not manifest.is_file():
        raise BlobRestoreError("manifest is missing or is not a regular file")
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise BlobRestoreError(f"cannot read manifest: {exc}") from exc

    targets: list[str] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, start=1):
        if not line or "  " not in line:
            raise BlobRestoreError(f"malformed manifest row at line {number}")
        digest, relative = line.split("  ", 1)
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise BlobRestoreError(f"invalid SHA-256 at line {number}")
        if not relative or "\\" in relative or relative == "MANIFEST.sha256":
            raise BlobRestoreError(f"invalid target path at line {number}")
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts or rel.as_posix() != relative:
            raise BlobRestoreError(f"unsafe or non-canonical path at line {number}")
        if relative in seen:
            raise BlobRestoreError(f"duplicate target at line {number}: {relative}")
        seen.add(relative)
        targets.append(relative)
    return targets


def _safe_target(root: Path, relative: str) -> Path:
    candidate = root
    for part in PurePosixPath(relative).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise BlobRestoreError(f"refusing symlinked target: {relative}")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise BlobRestoreError(f"target escapes repository root: {relative}") from exc
    if candidate.exists() and not candidate.is_file():
        raise BlobRestoreError(f"target is not a regular file: {relative}")
    return candidate


def restore(root: Path, manifest_path: Path = Path("MANIFEST.sha256"), revision: str = "HEAD") -> int:
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise BlobRestoreError("repository root is not a directory")
    if not revision or revision.startswith("-"):
        raise BlobRestoreError("invalid Git revision")
    targets = _manifest_targets(root, manifest_path)

    for relative in targets:
        target = _safe_target(root, relative)
        spec = f"{revision}:{relative}"
        result = subprocess.run(
            ["git", "cat-file", "blob", spec],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise BlobRestoreError(f"cannot read Git blob for {relative}: {detail}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target = _safe_target(root, relative)
        target.write_bytes(result.stdout)
    return len(targets)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=Path("MANIFEST.sha256"))
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args(argv)
    try:
        count = restore(args.root, args.manifest, args.revision)
    except (OSError, BlobRestoreError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"PASS: restored {count} manifest-listed files from exact Git blob bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
