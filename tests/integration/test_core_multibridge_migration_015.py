"""Full Home Assistant Core multi-bridge crash-recovery tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = Path(__file__).with_name("_core_multibridge_migration_worker_015.py")


def _run(
    directory: str,
    direction: str,
    phase: str,
    *,
    fault: str | None = None,
    error_name: str | None = None,
    expected_source: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(
        os.environ,
        HKM_CORE_MULTIBRIDGE_DIR=directory,
        HKM_CORE_MULTIBRIDGE_DIRECTION=direction,
        HKM_CORE_MULTIBRIDGE_PHASE=phase,
        PYTHONPATH=os.pathsep.join(
            item for item in (str(ROOT), os.environ.get("PYTHONPATH", "")) if item
        ),
    )
    if fault:
        environment["HKM_CORE_MIGRATION_TEST_MODE"] = "1"
        environment["HKM_CORE_MIGRATION_TEST_FAULT"] = fault
    if error_name:
        environment["HKM_CORE_MIGRATION_TEST_ERRNO"] = error_name
    if expected_source:
        environment["HKM_CORE_MULTIBRIDGE_EXPECT_SOURCE"] = expected_source
    return subprocess.run(
        [sys.executable, "-X", "faulthandler", str(WORKER)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
@pytest.mark.parametrize("run_number", [1, 2, 3])
def test_two_real_hap_bridges_survive_core_sigkill_and_startup_recovery(
    direction: str, run_number: int
) -> None:
    with TemporaryDirectory(
        prefix=f"hkm-core-multibridge-015-{direction}-{run_number}-"
    ) as directory:
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr

        crashed = _run(directory, direction, "migrate")
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr
        assert (Path(directory) / "fault-reached").read_text(encoding="utf-8") == (
            "AFTER_SOURCE_MUTATION"
        )

        recovered = _run(directory, direction, "verify")
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr


def test_two_real_hap_bridges_survive_second_sigkill_during_startup_recovery() -> None:
    direction = "ui_to_yaml"
    with TemporaryDirectory(prefix="hkm-core-multibridge-015-recovery-crash-") as directory:
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr
        crashed = _run(directory, direction, "migrate")
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr

        recovery_crashed = _run(
            directory, direction, "recover_crash", fault="DURING_RECOVERY"
        )
        assert recovery_crashed.returncode == -9, (
            recovery_crashed.stdout + recovery_crashed.stderr
        )
        store = Path(directory, ".storage", "homekit.migration")
        persisted = json.loads(store.read_text(encoding="utf-8"))
        assert persisted["data"]["state"] == "VERIFYING"

        recovered = _run(directory, direction, "verify")
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr

