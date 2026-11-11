#!/usr/bin/env python3
"""Build a deterministic public-source ZIP or TAR.XZ and its SHA-256 sidecar.

The explicit MANIFEST.sha256 is the only content allowlist. Local/private research
workspaces, binary thesis documents, caches and distribution archives are never
recursively copied into a release bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

BLOCKED_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".sqlite", ".sqlite3", ".db",
    ".parquet", ".jsonl", ".ndjson", ".pem", ".key", ".p12", ".pfx", ".pyc", ".pyo",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _safe_files(root: Path) -> list[Path]:
    """Resolve and verify every manifest entry; reject path escapes and unsafe files."""
    manifest = root / "MANIFEST.sha256"
    if not manifest.is_file() or manifest.is_symlink():
        raise RuntimeError("MANIFEST.sha256 is missing or unsafe")

    paths: list[Path] = []
    seen: set[str] = set()
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        if "  " not in line:
            raise RuntimeError(f"malformed manifest line {line_number}")
        digest, relative = line.split("  ", 1)
        rel = PurePosixPath(relative)
        if not SHA256_RE.fullmatch(digest):
            raise RuntimeError(f"malformed SHA-256 at manifest line {line_number}")
        if not relative or rel.is_absolute() or ".." in rel.parts or "\\" in relative:
            raise RuntimeError(f"unsafe manifest path at line {line_number}: {relative!r}")
        if relative in seen:
            raise RuntimeError(f"duplicate manifest path: {relative}")
        seen.add(relative)

        unresolved = root / Path(*rel.parts)
        if unresolved.is_symlink():
            raise RuntimeError(f"symlink is not allowed in public source: {relative}")
        candidate = unresolved.resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"manifest path escapes repository root: {relative}") from exc
        if not candidate.is_file():
            raise RuntimeError(f"manifest entry is not a regular file: {relative}")
        if candidate.suffix.lower() in BLOCKED_SUFFIXES:
            raise RuntimeError(f"blocked file type in public manifest: {relative}")
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != digest:
            raise RuntimeError(f"manifest checksum mismatch: {relative}")
        paths.append(candidate)
    return paths


def _write_zip(archive: Path, root: Path, files: list[Path]) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(2026, 11, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.create_system = 3
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC failed at {bad}")


def _write_tar_xz(archive: Path, root: Path, files: list[Path]) -> None:
    with tarfile.open(archive, mode="w:xz", preset=9) as tf:
        for path in files:
            rel = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            info = tarfile.TarInfo(name=rel)
            info.size = len(payload)
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.type = tarfile.REGTYPE
            tf.addfile(info, io.BytesIO(payload))
    with tarfile.open(archive, mode="r:xz") as tf:
        members = tf.getmembers()
        expected = {p.relative_to(root).as_posix() for p in files}
        actual = {m.name for m in members}
        if actual != expected or any(not m.isfile() for m in members):
            raise RuntimeError("TAR.XZ member set or member type validation failed")
        for member in members:
            extracted = tf.extractfile(member)
            source = root / member.name
            if extracted is None or extracted.read() != source.read_bytes():
                raise RuntimeError(f"TAR.XZ content mismatch: {member.name}")


def build(root: Path, archive: Path) -> tuple[int, str]:
    root = root.expanduser().resolve(strict=True)
    archive = archive.expanduser().resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = _safe_files(root)
    files.append(root / "MANIFEST.sha256")
    files = sorted(files, key=lambda p: p.relative_to(root).as_posix())

    if archive.name.endswith(".tar.xz"):
        _write_tar_xz(archive, root, files)
    elif archive.suffix.lower() == ".zip":
        _write_zip(archive, root, files)
    else:
        raise ValueError("archive extension must be .zip or .tar.xz")

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n")
    return len(files), digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("dist/project-SKRIPSI-public-source-v0.8.0.zip"))
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else args.root / args.output
    count, digest = build(args.root, output)
    print(f"PASS: created {output} with {count} files; SHA-256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
