"""Crash and restart the real isolated HA-Core migration worker."""
from __future__ import annotations

import os
import json
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_native_source_migration_worker_012.py")


def _run(directory: str, phase: str, *, fault: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(
        os.environ,
        HKM_NATIVE_SOURCE_MIGRATION_DIR=directory,
        HKM_NATIVE_SOURCE_MIGRATION_PHASE=phase,
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTEST_ADDOPTS=(
            "-p pytest_asyncio.plugin -p pytest_socket "
            "-p pytest_homeassistant_custom_component.plugins"
        ),
    )
    if fault:
        environment["HKM_NATIVE_SOURCE_MIGRATION_FAULT"] = fault
    return subprocess.run(  # noqa: S603 - fixed local isolated worker
        [sys.executable, "-m", "pytest", "-q", str(WORKER)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _pair(directory: str) -> None:
    result = _run(directory, "pair_ui")
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_core_sigkill_after_source_mutation_recovers_pairing_and_rolls_back():
    with TemporaryDirectory(prefix="hkm-native-crash-recovery-013-") as directory:
        _pair(directory)
        crashed = _run(directory, "migrate_ui_yaml", fault="AFTER_SOURCE_MUTATION")
        assert crashed.returncode == -signal.SIGKILL, crashed.stdout + crashed.stderr
        assert (Path(directory) / "fault-reached").read_text(encoding="utf-8") == "AFTER_SOURCE_MUTATION"

        recovered = _run(directory, "recover")
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
        journal = json.loads((Path(directory) / "migration.journal.json").read_text(encoding="utf-8"))
        assert journal["state"] == "ROLLED_BACK"
        assert journal["recovery_status"] == "ROLLBACK_COMPLETED"
        assert "rollback_complete" in journal["completed_operations"]


def test_real_core_sigkill_before_native_change_completes_recovery_without_mutation():
    with TemporaryDirectory(prefix="hkm-native-crash-recovery-013-") as directory:
        _pair(directory)
        crashed = _run(directory, "migrate_ui_yaml", fault="AFTER_SNAPSHOT")
        assert crashed.returncode == -signal.SIGKILL, crashed.stdout + crashed.stderr

        recovered = _run(directory, "recover")
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
        journal = json.loads((Path(directory) / "migration.journal.json").read_text(encoding="utf-8"))
        assert journal["state"] == "FAILED"
        assert journal["recovery_status"] == "RECOVERY_COMPLETED"
        assert "recovery_complete" in journal["completed_operations"]


def test_real_core_sigkill_after_reload_recovers_original_hap_identity():
    with TemporaryDirectory(prefix="hkm-native-crash-recovery-013-") as directory:
        _pair(directory)
        crashed = _run(directory, "migrate_ui_yaml", fault="AFTER_RELOAD")
        assert crashed.returncode == -signal.SIGKILL, crashed.stdout + crashed.stderr

        recovered = _run(directory, "recover")
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
        journal = json.loads((Path(directory) / "migration.journal.json").read_text(encoding="utf-8"))
        assert journal["state"] == "ROLLED_BACK"
        assert journal["recovery_status"] == "ROLLBACK_COMPLETED"


@pytest.mark.parametrize("fault", ["AFTER_UNLOAD", "BEFORE_SOURCE_MUTATION"])
def test_real_core_sigkill_before_source_commit_rolls_back(fault: str):
    with TemporaryDirectory(prefix="hkm-native-crash-recovery-013-") as directory:
        _pair(directory)
        crashed = _run(directory, "migrate_ui_yaml", fault=fault)
        assert crashed.returncode == -signal.SIGKILL, crashed.stdout + crashed.stderr

        recovered = _run(directory, "recover")
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
        journal = json.loads((Path(directory) / "migration.journal.json").read_text(encoding="utf-8"))
        assert journal["state"] == "ROLLED_BACK"
        assert journal["recovery_status"] == "ROLLBACK_COMPLETED"
