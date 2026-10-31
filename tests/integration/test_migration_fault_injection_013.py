"""Real process-abort tests for the durable migration scaffolding."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from custom_components.homekit_manager.migration_journal import JournalStore
from custom_components.homekit_manager.migration_lock import BridgeMigrationLock
from custom_components.homekit_manager.migration_recovery import classify


ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_migration_fault_worker_013.py")


def _kill_at_operation(tmp_path, operation: str, sig: signal.Signals):
    environment = dict(
        os.environ,
        HKM_FAULT_ROOT=str(tmp_path),
        HKM_FAULT_OPERATION=operation,
        PYTHONPATH=str(ROOT),
    )
    process = subprocess.Popen(  # noqa: S603 - fixed local fault-injection worker
        [sys.executable, str(WORKER)],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    marker = tmp_path / f"entered-{operation}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not marker.exists():
        time.sleep(0.01)
    assert marker.exists(), f"Worker reached no fault point: {operation}"
    process.send_signal(sig)
    process.wait(timeout=10)
    return JournalStore(tmp_path / "journal.json").load(), process


def test_sigkill_fault_points_are_classified_without_automatic_mutation(tmp_path):
    safe_before_native = ("lock", "snapshot", "prepare")
    for operation in safe_before_native:
        record, process = _kill_at_operation(tmp_path / operation, operation, signal.SIGKILL)
        assert process.returncode == -signal.SIGKILL
        assert record is not None
        assert classify(record).action == "resume_preflight"

    for operation in ("quiesce", "source_switch", "reload", "verify", "commit"):
        record, process = _kill_at_operation(tmp_path / operation, operation, signal.SIGKILL)
        assert process.returncode == -signal.SIGKILL
        assert record is not None
        assert classify(record).action == "manual_recovery"


def test_sigterm_during_quiesce_requires_manual_recovery_and_lock_is_reusable(tmp_path):
    record, process = _kill_at_operation(tmp_path, "quiesce", signal.SIGTERM)
    assert process.returncode == -signal.SIGTERM
    assert record is not None
    decision = classify(record)
    assert decision.action == "manual_recovery"
    lock = BridgeMigrationLock(tmp_path / "bridge.lock", "bridge-a")
    lock.acquire()
    lock.release()
