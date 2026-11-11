#!/usr/bin/env python3
"""Verify the SHA-256 public-source allowlist on POSIX and Windows."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path, PurePosixPath

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def verify(root: Path, manifest_path: Path) -> list[str]:
    root = root.expanduser().resolve()
    manifest = manifest_path if manifest_path.is_absolute() else root / manifest_path
    if manifest.is_symlink() or not manifest.is_file():
        return [f"manifest is missing or not a regular file: {manifest}"]

    errors: list[str] = []
    seen: set[str] = set()
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [f"cannot read manifest: {exc}"]

    for line_number, line in enumerate(lines, start=1):
        if not line:
            errors.append(f"blank line at {line_number}")
            continue
        if "  " not in line:
            errors.append(f"malformed manifest row at {line_number}")
            continue
        expected, relative = line.split("  ", 1)
        if not _SHA256_RE.fullmatch(expected):
            errors.append(f"invalid SHA-256 value at line {line_number}")
            continue
        if not relative or "\\" in relative:
            errors.append(f"invalid relative path at line {line_number}")
            continue
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts or relative == "MANIFEST.sha256":
            errors.append(f"unsafe or self-referential path at line {line_number}: {relative}")
            continue
        if relative in seen:
            errors.append(f"duplicate manifest path at line {line_number}: {relative}")
            continue
        seen.add(relative)

        candidate = root
        symlink_found = False
        for part in rel.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                errors.append(f"symlinked manifest target at line {line_number}: {relative}")
                symlink_found = True
                break
        if symlink_found:
            continue
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            errors.append(f"missing or escaped manifest target at line {line_number}: {relative}")
            continue
        if not resolved.is_file():
            errors.append(f"manifest target is not a regular file at line {line_number}: {relative}")
            continue
        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"SHA-256 mismatch: {relative}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=Path("MANIFEST.sha256"))
    args = parser.parse_args()
    errors = verify(args.root, args.manifest)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: manifest SHA-256 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
