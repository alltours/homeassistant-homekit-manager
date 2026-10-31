"""Filesystem preconditions for isolated HomeKit source fixtures."""
from __future__ import annotations

import os
from pathlib import Path


def secure_private_source(path: Path) -> Path:
    """Make a synthetic source private and free of inherited xattrs."""
    path.chmod(0o600)
    if hasattr(os, "listxattr") and hasattr(os, "removexattr"):
        for name in os.listxattr(path, follow_symlinks=False):
            os.removexattr(path, name, follow_symlinks=False)
    return path
