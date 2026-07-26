from __future__ import annotations

import logging

from PySide6.QtCore import QLockFile

from coderadio_tray.config import config_dir

logger = logging.getLogger(__name__)


def try_acquire() -> QLockFile | None:
    """Return a held QLockFile if this is the first instance, else None.

    Uses a lock file under the OS config dir so it works the same for
    frozen builds and source runs (more reliable than QLocalServer alone
    on Windows).
    """
    path = config_dir() / "instance.lock"
    lock = QLockFile(str(path))
    # If a previous crash left a lock and the PID is dead, Qt can reclaim it.
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(250):
        logger.info("another instance is already running (%s)", path)
        return None
    return lock
