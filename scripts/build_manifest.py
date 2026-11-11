#!/usr/bin/env python3
"""Build a deterministic SHA-256 manifest for the public source snapshot.

The manifest deliberately excludes local/private research workspaces, cached or
compiled files, binary thesis documents, databases, distribution archives, credentials
and P1/P2 corpus exports. Distribution archives are checksummed separately. It is a
source-integrity aid, not a substitute for review.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import tempfile
from pathlib import Path

DEFAULT_EXCLUDED_DIRS = {
    ".git", ".private", ".venv", "venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "cache",
    "private", "private_data", "research_data", "raw_data", "processed_data",
    "datasets", "staging", "local-only", "workspaces", "workspace",
    "temp", "tmp", "source_cache", "corpus", "evidence_register", "source_ledger", "dist",
}
BLOCKED_SUFFIXES = {
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".zip", ".sqlite", ".sqlite3",
    ".db", ".parquet", ".jsonl", ".ndjson", ".pem", ".key", ".p12", ".pfx",
}
PRIVATE_NAME_RE = re.compile(
    r"^(?:\.env(?:\..*)?|credentials(?:.*)?|P1_.*\.(?:csv|json|jsonl|ndjson|parquet|zip)|P2_.*\.(?:csv|json|jsonl|ndjson|parquet|zip)|.*_package\.zip|.*_data\.csv)$",
    re.IGNORECASE,
)


def is_excluded(path: Path, root: Path, manifest_name: str) -> bool:
    rel = path.relative_to(root)
    if rel.as_posix() == manifest_name:
        return True
    if any(part in DEFAULT_EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel.parts[:-1]):
        return True
    if path.is_symlink() or not path.is_file():
        return True
    if path.suffix.lower() in BLOCKED_SUFFIXES or path.suffix.lower() in {".pyc", ".pyo"}:
        return True
    if PRIVATE_NAME_RE.match(path.name):
        return True
    return False


def build(root: Path, manifest_name: str) -> tuple[int, Path]:
    root = root.resolve()
    output = root / manifest_name
    entries: list[str] = []
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        dirs[:] = sorted(
            d for d in dirs
            if d not in DEFAULT_EXCLUDED_DIRS and not d.endswith(".egg-info")
        )
        for name in sorted(files):
            path = current_path / name
            if is_excluded(path, root, manifest_name):
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(f"{digest}  {path.relative_to(root).as_posix()}")
    payload = "\n".join(sorted(entries, key=lambda item: item.split("  ", 1)[1])) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, output)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return len(entries), output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", default="MANIFEST.sha256")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    count, output = build(root, args.manifest)
    print(f"PASS: wrote {count} public-source hash entries to {output}")
    print("NOTICE: private and binary research artifacts are excluded by policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
