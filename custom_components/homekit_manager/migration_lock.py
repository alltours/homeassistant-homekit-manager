"""Cross-process bridge migration lock.

The kernel lock is the authority.  The sidecar JSON is diagnostic metadata;
its presence alone never blocks or authorizes a recovery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
from typing import Any
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - Home Assistant supported platforms provide fcntl
    fcntl = None


class MigrationLockError(Exception):
    """Base class for lock failures."""


class MigrationLockBusy(MigrationLockError):
    """Another process owns the bridge lock."""


@dataclass(frozen=True)
class LockOwner:
    token: str
    bridge_id: str
    pid: int
    host: str
    acquired_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "bridge_id": self.bridge_id,
            "pid": self.pid,
            "host": self.host,
            "acquired_at": self.acquired_at,
        }


class BridgeMigrationLock:
    """Hold an exclusive kernel lock and publish redacted owner metadata."""

    def __init__(self, path: str | Path, bridge_id: str):
        self.path = Path(path)
        self.bridge_id = bridge_id
        self._handle = None
        self.owner: LockOwner | None = None

    def acquire(self) -> LockOwner:
        if fcntl is None:
            raise MigrationLockError("Diese Plattform bietet keinen sicheren Prozess-Lock")
        if self._handle is not None:
            raise MigrationLockError("Lock wurde bereits erworben")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            handle.close()
            raise MigrationLockBusy("Bridge wird bereits bearbeitet") from err
        owner = LockOwner(
            token=str(uuid4()),
            bridge_id=self.bridge_id,
            pid=os.getpid(),
            host=socket.gethostname(),
            acquired_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            payload = json.dumps(owner.as_dict(), sort_keys=True).encode("utf-8") + b"\n"
            handle.seek(0)
            handle.truncate()
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            self.path.chmod(0o600)
        except OSError:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
            raise
        self._handle = handle
        self.owner = owner
        return owner

    def release(self) -> None:
        if self._handle is None:
            return
        if fcntl is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None
        self.owner = None

    def __enter__(self) -> "BridgeMigrationLock":
        self.acquire()
        return self

    def __exit__(self, _exception_type, _exception, _traceback) -> None:
        self.release()
