"""Append-only, hash-chained project event log with cross-process protection."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .locking import FileLock

GENESIS = "0" * 64


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _event_hash(event_without_hash: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(event_without_hash)).hexdigest()


def _verify_audit_log_unlocked(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return True, "audit log not created yet"
    previous = GENESIS
    expected_index = 1
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    return False, f"blank line at {line_number}"
                event = json.loads(line)
                if not isinstance(event, dict):
                    return False, f"event at line {line_number} is not an object"
                supplied_hash = event.pop("event_hash", None)
                if not isinstance(supplied_hash, str) or len(supplied_hash) != 64:
                    return False, f"event hash is missing or malformed at line {line_number}"
                if event.get("event_index") != expected_index:
                    return False, f"event index mismatch at line {line_number}"
                if event.get("previous_event_hash") != previous:
                    return False, f"previous hash mismatch at line {line_number}"
                if supplied_hash != _event_hash(event):
                    return False, f"event hash mismatch at line {line_number}"
                previous = supplied_hash
                expected_index += 1
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        return False, f"cannot verify audit log: {exc}"
    return True, f"verified {expected_index - 1} event(s)"


def verify_audit_log(path: Path) -> tuple[bool, str]:
    """Verify the chain while excluding concurrent append operations."""
    if path.is_symlink():
        return False, f"refusing symlinked audit log: {path}"
    if not path.exists():
        return True, "audit log not created yet"
    lock_path = path.with_name(path.name + ".lock")
    with FileLock(lock_path):
        return _verify_audit_log_unlocked(path)


def read_audit_events(path: Path) -> tuple[bool, str, list[dict[str, Any]]]:
    """Read a verified audit snapshot under the same lock used by appenders."""
    if path.is_symlink():
        return False, f"refusing symlinked audit log: {path}", []
    lock_path = path.with_name(path.name + ".lock")
    with FileLock(lock_path):
        ok, reason = _verify_audit_log_unlocked(path)
        if not ok:
            return False, reason, []
        if not path.exists():
            return True, "audit log not created yet", []
        try:
            with path.open("r", encoding="utf-8") as handle:
                events = [json.loads(line) for line in handle if line.strip()]
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return False, f"cannot read audit log: {exc}", []
        if any(not isinstance(event, dict) for event in events):
            return False, "audit log contains a non-object event", []
        return True, reason, events


def append_audit_event(
    path: Path,
    *,
    event_type: str,
    object_type: str,
    object_id: str,
    summary: str,
    actor_type: str = "human_operator",
    evidence_refs: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append one event; an optional key makes retries safe across processes."""
    if path.is_symlink():
        raise ValueError(f"refusing symlinked audit log: {path}")
    lock_path = path.with_name(path.name + ".lock")
    with FileLock(lock_path):
        ok, reason = _verify_audit_log_unlocked(path)
        if not ok:
            raise ValueError(f"refusing to append to invalid audit log: {reason}")

        previous = GENESIS
        index = 1
        if path.is_symlink():
            raise ValueError(f"refusing symlinked audit log: {path}")
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    old = json.loads(line)
                    if idempotency_key and old.get("idempotency_key") == idempotency_key:
                        expected_payload = {
                            "event_type": event_type,
                            "object_type": object_type,
                            "object_id": object_id,
                            "summary": summary,
                            "actor_type": actor_type,
                            "evidence_refs": evidence_refs or [],
                        }
                        actual_payload = {key: old.get(key) for key in expected_payload}
                        if actual_payload != expected_payload:
                            raise ValueError("audit idempotency key already belongs to a different event payload")
                        return old
                    previous = old["event_hash"]
                    index += 1

        event: dict[str, Any] = {
            "event_index": index,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event_type": event_type,
            "object_type": object_type,
            "object_id": object_id,
            "summary": summary,
            "actor_type": actor_type,
            "evidence_refs": evidence_refs or [],
            "previous_event_hash": previous,
        }
        if idempotency_key:
            event["idempotency_key"] = idempotency_key
        event["event_hash"] = _event_hash(event)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError(f"refusing symlinked audit log: {path}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except OSError as exc:
            if getattr(exc, "errno", None) == errno.ELOOP:
                raise ValueError(f"refusing symlinked audit log: {path}") from exc
            raise
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError(f"audit log is not a regular file: {path}")
            payload = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("audit append made no forward progress")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        if os.name != "nt":
            try:
                path.parent.chmod(0o700)
                path.chmod(0o600)
            except OSError:
                pass
        return event
