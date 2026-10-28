"""Verify real Core bootstrap and persisted HomeKit pairing across processes."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_hap_full_bootstrap_worker.py")


def test_full_bootstrap_reloads_persisted_entry_and_hap_pairing():
    with TemporaryDirectory(prefix="hkm-hap-full-bootstrap-") as directory:
        for phase in ("pair", "reconnect"):
            environment = dict(os.environ, HKM_FULL_BOOTSTRAP_DIR=directory,
                               HKM_FULL_BOOTSTRAP_PHASE=phase)
            result = subprocess.run(  # noqa: S603 - fixed interpreter and local worker
                [sys.executable, "-X", "faulthandler", str(WORKER)],
                cwd=ROOT, env=environment, capture_output=True, text=True,
                timeout=90, check=False,
            )
            # Keep all child diagnostics private: Core may log ephemeral HAP
            # pairing material on failure.
            assert result.returncode == 0, f"Isolated full Core bootstrap phase {phase} failed (exit {result.returncode})"
