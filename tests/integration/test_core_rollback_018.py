"""Full-Core rollback tests for the Core-owned migration executor."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from test_core_multibridge_migration_015 import _run

pytestmark = pytest.mark.experimental_core

ROLLBACK_FAULTS = [
    "BEFORE_ROLLBACK_PENDING",
    "AFTER_ROLLBACK_PENDING",
    "BEFORE_ROLLBACK_SOURCE_MUTATION",
    "AFTER_ROLLBACK_SOURCE_MUTATION",
    "BEFORE_ROLLBACK_RECONCILIATION",
    "AFTER_ROLLBACK_RECONCILIATION",
    "BEFORE_ROLLBACK_HAP_VERIFY",
    "AFTER_ROLLBACK_HAP_VERIFY",
    "BEFORE_ROLLBACK_COMMIT",
    "AFTER_ROLLBACK_COMMIT",
]


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
@pytest.mark.parametrize("fault", ROLLBACK_FAULTS)
def test_core_owned_rollback_survives_sigkill(
    direction: str, fault: str
) -> None:
    """Every rollback boundary recovers or reaches a safe committed result."""
    with TemporaryDirectory(prefix=f"hkm-core-rollback-018-{direction}-{fault}-") as directory:
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr

        crashed = _run(directory, direction, "rollback", fault=fault)
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr

        expected_source = (
            "import" if direction == "ui_to_yaml" else "user"
        ) if fault == "BEFORE_ROLLBACK_PENDING" else (
            "user" if direction == "ui_to_yaml" else "import"
        )
        recovered = _run(
            directory,
            direction,
            "verify",
            expected_source=expected_source,
        )
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr


@pytest.mark.parametrize("direction", ["ui_to_yaml", "yaml_to_ui"])
def test_committed_transaction_is_never_rolled_back(direction: str) -> None:
    """A committed target remains stable after repeated Core restarts."""
    with TemporaryDirectory(prefix=f"hkm-core-rollback-018-committed-{direction}-") as directory:
        paired = _run(directory, direction, "pair")
        assert paired.returncode == 0, paired.stdout + paired.stderr
        crashed = _run(directory, direction, "migrate")
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr
        committed = _run(
            directory,
            direction,
            "verify",
            expected_source="import" if direction == "ui_to_yaml" else "user",
        )
        assert committed.returncode == 0, committed.stdout + committed.stderr
        journal = json.loads(
            Path(directory, ".storage", "homekit.migration").read_text(encoding="utf-8")
        )
        assert journal["data"]["state"] == "COMMITTED"
        restarted = _run(
            directory,
            direction,
            "verify",
            expected_source="import" if direction == "ui_to_yaml" else "user",
        )
        assert restarted.returncode == 0, restarted.stdout + restarted.stderr


def test_rollback_preserves_25_entity_positive_list_and_rejects_25_excluded() -> None:
    """Rollback keeps the real HAP accessory count at bridge plus 25."""
    direction = "ui_to_yaml"
    with TemporaryDirectory(prefix="hkm-core-rollback-018-allowlist-") as directory:
        paired = _run(directory, direction, "pair", large_allowlist=True)
        assert paired.returncode == 0, paired.stdout + paired.stderr
        crashed = _run(
            directory,
            direction,
            "rollback",
            fault="AFTER_ROLLBACK_COMMIT",
            large_allowlist=True,
        )
        assert crashed.returncode == -9, crashed.stdout + crashed.stderr
        recovered = _run(
            directory,
            direction,
            "verify",
            expected_source="user",
            large_allowlist=True,
        )
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
