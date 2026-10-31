"""Verify isolated Core/HAP storage across two fresh Python interpreters."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_hap_restart_worker.py")


def test_pairing_reconnects_after_isolated_core_process_restart():
    with TemporaryDirectory(prefix="hkm-hap-restart-") as directory:
        for phase in ("pair", "reconnect"):
            environment = dict(os.environ, HKM_RESTART_DIR=directory, HKM_RESTART_PHASE=phase)
            result = subprocess.run(  # noqa: S603 - fixed worker executable and isolated test path
                [sys.executable, "-m", "pytest", "-q", "--show-capture=no", str(WORKER)],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=90, check=False,
            )
            # Child output stays in memory and is not published: it can contain
            # ephemeral pairing material from Core's own diagnostics on failure.
            assert result.returncode == 0, f"Isolated HAP process phase {phase} failed (exit {result.returncode})"
