"""Small cross-platform advisory file locks for local workspace mutations.

Locks are kernel-managed (flock on POSIX, msvcrt on Windows), so process
termination releases ownership automatically. Lock files are persistent
markers; they are not treated as proof that a lock is held.
"""

from __future__ import annotations

import errno
import os
import stat
import time
from pathlib import Path
from typing import IO


class FileLock:
    """Exclusive advisory lock with bounded waiting and symlink refusal."""

    def __init__(self, path: Path, *, timeout: float = 15.0, poll_interval: float = 0.05) -> None:
        if timeout < 0:
            raise ValueError("lock timeout must not be negative")
        if poll_interval <= 0:
            raise ValueError("lock poll interval must be positive")
        self.path = Path(path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._handle: IO[bytes] | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise ValueError(f"refusing symlinked lock path: {self.path}")

        flags = os.O_RDWR | os.O_CREAT
        # Close the check/open race on platforms that support O_NOFOLLOW.
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags, 0o600)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError(f"refusing symlinked lock path: {self.path}") from exc
            raise

        try:
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"lock path is not a regular file: {self.path}")
            handle = os.fdopen(fd, "r+b", buffering=0)
        except BaseException:
            os.close(fd)
            raise

        if os.name != "nt":
            try:
                self.path.parent.chmod(0o700)
                self.path.chmod(0o600)
            except OSError:
                handle.close()
                raise
        else:
            # msvcrt.locking locks a byte range; ensure byte zero exists.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()

        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._handle = handle
                return self
            except (BlockingIOError, OSError) as exc:
                expected = {errno.EACCES, errno.EAGAIN}
                if getattr(exc, "errno", None) not in expected and not isinstance(exc, BlockingIOError):
                    handle.close()
                    raise
                if time.monotonic() >= deadline:
                    handle.close()
                    raise TimeoutError(f"timed out waiting for workspace lock: {self.path}") from exc
                time.sleep(self.poll_interval)

    def __exit__(self, exc_type, exc, traceback) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
