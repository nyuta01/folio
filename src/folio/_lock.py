"""``.lock`` acquisition helper.

Single-writer assumption per §12 of the design overview. The default lock
acquisition timeout is 30 seconds.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import filelock

from .exceptions import LockTimeoutError

DEFAULT_LOCK_TIMEOUT_SECONDS = 30.0


@contextmanager
def acquire_sheet_lock(
    sheet_path: Path,
    timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Acquire ``<sheet_path>/.lock`` for writes. Blocks up to ``timeout`` seconds."""
    lock_path = sheet_path / ".lock"
    lock = filelock.FileLock(str(lock_path), timeout=timeout)
    try:
        lock.acquire()
    except filelock.Timeout as exc:
        raise LockTimeoutError(
            f"could not acquire {lock_path} within {timeout}s"
        ) from exc
    try:
        yield
    finally:
        try:
            lock.release()
        finally:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
