"""Cooperative export locking and atomic replacement using the standard library.

The lock file stays in place: deleting it can let writers lock different inodes.
Replacements are atomic per file, not a transaction across several files.
"""

from __future__ import annotations

import errno
import math
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_LOCK_TIMEOUT = 10.0
LOCK_FILENAME = '.agent-sessions.lock'


class StorageError(Exception):
    """An export cannot safely update its destination."""


class LockTimeoutError(StorageError):
    pass


class InvalidIndexError(StorageError):
    pass


def validate_session_id(session_id: str) -> None:
    if not isinstance(session_id, str) or not re.fullmatch(r'[\w-]+', session_id):
        raise StorageError('Invalid session ID. Expected a filename-safe identifier.')


def _try_lock(stream) -> None:
    if os.name == 'nt':
        import msvcrt
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream) -> None:
    if os.name == 'nt':
        import msvcrt
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def directory_lock(directory: Path, timeout: float = DEFAULT_LOCK_TIMEOUT):
    """Wait at most timeout seconds for a kernel lock on this export directory.

    Each acquisition uses its own descriptor. Calls must not nest for the same
    directory. Process termination releases the OS lock without deleting files.
    """
    if not math.isfinite(timeout) or timeout < 0:
        raise StorageError('Lock timeout must be a finite, nonnegative number.')
    stream = None
    acquired = False
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(directory / LOCK_FILENAME, os.O_CREAT | os.O_RDWR, 0o600)
        stream = os.fdopen(fd, 'r+b')
        if os.name == 'nt' and os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'\0')
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                _try_lock(stream)
                acquired = True
                break
            except OSError as error:
                if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LockTimeoutError(
                        f'Timed out waiting for the export lock in {directory}. Retry after the active export finishes.'
                    ) from error
                time.sleep(min(0.05, remaining))
    except OSError as error:
        if stream is not None:
            stream.close()
        raise StorageError(f'Cannot acquire the export lock in {directory}: {type(error).__name__}.') from error
    except BaseException:
        if stream is not None:
            stream.close()
        raise
    try:
        yield
    finally:
        try:
            if acquired:
                _unlock(stream)
        finally:
            stream.close()


def _sync_directory(directory: Path) -> None:
    # Windows does not expose a directory fsync through these stdlib calls.
    if os.name == 'nt':
        return
    fd = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write_many(contents: dict[Path, str]) -> None:
    """Stage and fsync every file before replacing any destination.

    Callers hold the directory lock for read/modify/write operations. A failure
    during replacement can leave different generations of complete files. The
    JSON index is the last replacement in the session export path.
    """
    staged: list[tuple[Path, Path]] = []
    replacing = False
    try:
        for path, text in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.agent-sessions-', suffix='.tmp', dir=path.parent)
            temporary = Path(name)
            staged.append((path, temporary))
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        replacing = True
        for path, temporary in staged:
            os.replace(temporary, path)
            _sync_directory(path.parent)
    except (OSError, UnicodeError) as error:
        guidance = ('Export can be incomplete. Run doctor and retry the export.' if replacing
                    else 'No destination files were replaced.')
        raise StorageError(f'Cannot write export files: {type(error).__name__}. {guidance}') from error
    finally:
        for _, temporary in staged:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Do not mask the write failure if cleanup also fails.
                pass


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_many({path: text})
