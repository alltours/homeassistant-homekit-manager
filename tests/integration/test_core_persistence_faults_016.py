"""Full-Core persistence-fault and journal-corruption tests.

The I/O failures in this file are controlled Core test-adapter exceptions, not
claims of physical disk failure.  The HAP assertions still use real pairings.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from test_core_multibridge_migration_015 import _run


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
@pytest.mark.parametrize("error_name", ["ENOSPC", "EIO", "EACCES"])
def test_core_journal_write_fault_keeps_both_bridges_safe(
    direction: str, error_name: str
) -> None:
    with TemporaryDirectory(prefix=f"hkm-core-persist-016-{direction}-{error_name}-") as directory:
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr

        failed = _run(
            directory,
            direction,
            "migrate",
            fault="BEFORE_MIGRATION_JOURNAL_WRITE",
            error_name=error_name,
        )
        assert failed.returncode == 1, failed.stdout + failed.stderr

        original_source = "user" if direction == "ui_to_yaml" else "import"
        recovered = _run(
            directory,
            direction,
            "verify",
            expected_source=original_source,
        )
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr


def test_corrupt_core_journal_blocks_only_the_pending_bridge() -> None:
    direction = "ui_to_yaml"
    with TemporaryDirectory(prefix="hkm-core-persist-016-corrupt-journal-") as directory:
        assert _run(directory, direction, "pair").returncode == 0
        crashed = _run(directory, direction, "migrate")
        assert crashed.returncode == -9

        journal = Path(directory, ".storage", "homekit.migration")
        journal.write_text("{truncated", encoding="utf-8")
        observed = _run(directory, direction, "verify_corrupt")
        assert observed.returncode == 0, observed.stdout + observed.stderr


def test_corrupt_core_journal_has_no_cross_bridge_data_path() -> None:
    direction = "yaml_to_ui"
    with TemporaryDirectory(prefix="hkm-core-persist-016-corrupt-yaml-to-ui-") as directory:
        assert _run(directory, direction, "pair").returncode == 0
        crashed = _run(directory, direction, "migrate")
        assert crashed.returncode == -9

        journal = Path(directory, ".storage", "homekit.migration")
        payload = json.loads(journal.read_text(encoding="utf-8"))
        payload["data"]["entry_id"] = "bridge-that-does-not-exist"
        journal.write_text(json.dumps(payload), encoding="utf-8")
        observed = _run(directory, direction, "verify_corrupt")
        assert observed.returncode == 0, observed.stdout + observed.stderr
