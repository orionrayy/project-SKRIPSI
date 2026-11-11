from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path

from project_skripsi.audit import append_audit_event, verify_audit_log
from project_skripsi.locking import FileLock


def _append_same_event(path: str, result_queue) -> None:
    try:
        event = append_audit_event(
            Path(path),
            event_type="test.concurrent",
            object_type="test",
            object_id="shared-object",
            summary="same idempotent event",
            evidence_refs=["fixture.json"],
            idempotency_key="same-operation-001",
        )
        result_queue.put(event["event_index"])
    except Exception as exc:  # pragma: no cover - surfaced through parent assertion
        result_queue.put(f"{type(exc).__name__}: {exc}")



def _lock_until_released(path: str, acquired_event, release_event) -> None:
    with FileLock(Path(path), timeout=3):
        acquired_event.set()
        release_event.wait(8)


def _lock_then_exit(path: str, acquired_event) -> None:
    lock = FileLock(Path(path), timeout=2)
    lock.__enter__()
    acquired_event.set()
    os._exit(0)


class FileLockTests(unittest.TestCase):
    @unittest.skipUnless(os.name != "nt", "same-process byte-range lock semantics differ on Windows")
    def test_lock_times_out_while_held_and_releases_after_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace.lock"
            with FileLock(path):
                with self.assertRaises(TimeoutError):
                    with FileLock(path, timeout=0.08, poll_interval=0.01):
                        self.fail("second lock unexpectedly acquired")
            with FileLock(path, timeout=0.2):
                self.assertTrue(path.is_file())

    def test_second_process_cannot_enter_until_kernel_lock_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "workspace.lock")
            context = multiprocessing.get_context("spawn")
            acquired = context.Event()
            release = context.Event()
            process = context.Process(target=_lock_until_released, args=(path, acquired, release))
            process.start()
            try:
                self.assertTrue(acquired.wait(5), "child did not acquire workspace lock")
                with self.assertRaises(TimeoutError):
                    with FileLock(Path(path), timeout=0.1, poll_interval=0.01):
                        self.fail("parent unexpectedly entered a lock held by the child process")
            finally:
                release.set()
                process.join(10)
            self.assertEqual(process.exitcode, 0)
            with FileLock(Path(path), timeout=1):
                self.assertTrue(Path(path).is_file())

    @unittest.skipUnless(os.name != "nt", "POSIX process termination test")
    def test_process_termination_releases_kernel_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "workspace.lock")
            context = multiprocessing.get_context("spawn")
            acquired = context.Event()
            process = context.Process(target=_lock_then_exit, args=(path, acquired))
            process.start()
            self.assertTrue(acquired.wait(3), "child did not acquire lock")
            process.join(3)
            self.assertEqual(process.exitcode, 0)
            with FileLock(Path(path), timeout=0.5):
                self.assertTrue(Path(path).exists())

    @unittest.skipUnless(os.name != "nt", "symlink behavior varies on Windows")
    def test_symlinked_lock_path_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_bytes(b"")
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlinked lock path"):
                with FileLock(link):
                    self.fail("symlinked lock path unexpectedly accepted")


class AuditConcurrencyTests(unittest.TestCase):
    def test_concurrent_retries_with_same_idempotency_key_write_one_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "events.jsonl"
            context = multiprocessing.get_context("spawn")
            result_queue = context.Queue()
            processes = [
                context.Process(target=_append_same_event, args=(str(audit_path), result_queue))
                for _ in range(6)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            results = [result_queue.get(timeout=2) for _ in processes]
            self.assertTrue(all(isinstance(item, int) for item in results), results)
            lines = audit_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            self.assertEqual(event["idempotency_key"], "same-operation-001")
            self.assertTrue(verify_audit_log(audit_path)[0])

    def test_idempotency_key_reuse_with_changed_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "events.jsonl"
            append_audit_event(
                audit_path,
                event_type="test.first",
                object_type="test",
                object_id="object-1",
                summary="original payload",
                idempotency_key="reuse-key",
            )
            with self.assertRaisesRegex(ValueError, "different event payload"):
                append_audit_event(
                    audit_path,
                    event_type="test.first",
                    object_type="test",
                    object_id="object-1",
                    summary="changed payload",
                    idempotency_key="reuse-key",
                )
            self.assertEqual(len(audit_path.read_text(encoding="utf-8").splitlines()), 1)

    @unittest.skipUnless(os.name != "nt", "symlink behavior varies on Windows")
    def test_symlinked_audit_log_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside.jsonl"
            outside.write_text("", encoding="utf-8")
            audit_path = root / "events.jsonl"
            audit_path.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "symlinked audit log"):
                append_audit_event(
                    audit_path,
                    event_type="test.event",
                    object_type="test",
                    object_id="one",
                    summary="must not follow symlink",
                )
            self.assertEqual(outside.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
