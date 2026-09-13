"""Safe filesystem output helpers.

File generation is deliberately centralized here so every mutating code path
gets locking, flushing, fsync, and atomic replacement consistently.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

from filelock import FileLock


def _atomic_write_unlocked(path: Path, text: str, *, mode: int | None = None) -> None:
    """Write PATH atomically; caller is responsible for inter-process locking."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if mode is not None:
            os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace PATH while serializing concurrent writers."""

    with FileLock(str(path) + ".lock"):
        existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
        _atomic_write_unlocked(path, text, mode=existing_mode)


def replace_with_backup(path: Path, text: str, suffix: str) -> Path:
    """Back up and atomically replace PATH under one inter-process lock.

    Keeping backup creation and replacement inside the same lock closes a race
    where another adjustkernel process could otherwise modify the file between
    those two operations.
    """

    backup = path.with_name(path.name + suffix)
    with FileLock(str(path) + ".lock"):
        original_mode = stat.S_IMODE(path.stat().st_mode)
        shutil.copy2(path, backup)
        _atomic_write_unlocked(path, text, mode=original_mode)
    return backup
