"""Deterministic, process-safe ports for isolated Home Assistant workers."""
from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path
import tempfile

_LOCK_DIR = Path(os.environ.get("HKM_TEST_PORT_LOCK_DIR", tempfile.gettempdir()))
_BASE_PORT = 18000
_PORT_SPAN = 10000
_HAP_BASE_PORT = 28000
_HAP_PORT_SPAN = 10000
_held_locks: dict[int, int] = {}
_identity_ports: dict[tuple[str, str], int] = {}


def _candidate_ports(identity: str, base_port: int, span: int):
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    start = base_port + int.from_bytes(digest[:2], "big") % span
    for offset in range(span):
        yield base_port + ((start - base_port + offset) % span)


def _reserve(identity: str, base_port: int, span: int, label: str, error: str) -> int:
    key = (label, identity)
    if (port := _identity_ports.get(key)) is not None:
        return port
    for port in _candidate_ports(identity, base_port, span):
        if port in _held_locks:
            continue
        lock_path = _LOCK_DIR / f"homekit-manager-test-port-{port}.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            continue
        _held_locks[port] = descriptor
        _identity_ports[key] = port
        return port
    raise RuntimeError(error)


def reserve_http_port(identity: str) -> int:
    """Reserve a deterministic HTTP port until the worker process exits.

    The lock is held by the process which will bind Home Assistant.  This avoids
    the usual free-port-then-close race between independent pytest workers.
    The operating-system bind remains the final authority.
    """
    return _reserve(identity, _BASE_PORT, _PORT_SPAN, "http", "No isolated Home Assistant HTTP port available")


def reserve_hap_port(identity: str) -> int:
    """Reserve a deterministic HAP port for an isolated bridge worker."""
    return _reserve(identity, _HAP_BASE_PORT, _HAP_PORT_SPAN, "hap", "No isolated HomeKit HAP port available")


def release_http_port(port: int) -> None:
    """Release a port reserved by this process."""
    descriptor = _held_locks.pop(port, None)
    if descriptor is None:
        return
    for key, value in tuple(_identity_ports.items()):
        if value == port:
            del _identity_ports[key]
    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)
