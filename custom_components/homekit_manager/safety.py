"""Fail-closed policy for legacy writes and ungranted operations."""

import ctypes
import errno
import os
import sys


def has_extended_acl(descriptor: int) -> bool:
    """Detect macOS ACLs that Unix mode bits do not describe.

    An uninspectable ACL fails closed. On Linux, a writable POSIX ACL updates
    the group class bits, which the callers already reject.
    """
    if sys.platform != "darwin":
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    get_acl = libc.acl_get_fd_np
    get_acl.argtypes = [ctypes.c_int, ctypes.c_int]
    get_acl.restype = ctypes.c_void_p
    libc.acl_free.argtypes = [ctypes.c_void_p]
    libc.acl_free.restype = ctypes.c_int
    acl = get_acl(descriptor, 0x00000100)  # ACL_TYPE_EXTENDED in macOS sys/acl.h
    if not acl:
        code = ctypes.get_errno()
        if code == errno.ENOENT:
            return False
        raise OSError(code, os.strerror(code))
    try:
        return True
    finally:
        libc.acl_free(acl)

WRITE_LOCK_REASON = (
    "HomeKit-Änderungen benötigen eine lokale, befristete und Bridge-gebundene Schreibfreigabe. "
    "Ohne diese Freigabe bleiben nur Entwurf, Vorschau und Export verfügbar. "
    "Ein unbekannter Apply-Ausgang wird niemals automatisch wiederholt."
)


def write_policy() -> dict:
    """The legacy direct apply route is always disabled; use operation policy."""
    return {"enabled": False, "reason": "Direkter Options-Apply-Pfad ist gesperrt; nur validierte Operationen mit lokaler Freigabe sind möglich.", "automatic_retry": False}
