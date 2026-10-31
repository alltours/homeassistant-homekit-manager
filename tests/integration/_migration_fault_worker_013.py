"""Plain-process worker for durable migration fault injection.

This worker models the native source and reload side effects with isolated
files.  It intentionally does not touch Home Assistant production or a real
Core instance; real HAP/Core evidence remains in the dedicated 0.12 POC.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

from custom_components.homekit_manager.migration_engine import MigrationEngine, MigrationPlan
from custom_components.homekit_manager.migration_journal import JournalStore
from custom_components.homekit_manager.migration_lock import BridgeMigrationLock
from custom_components.homekit_manager.migration_snapshot import MigrationSnapshot, SnapshotStore


def _atomic_write(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    root = Path(os.environ["HKM_FAULT_ROOT"])
    operation = os.environ["HKM_FAULT_OPERATION"]
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    source_file = root / "configuration.yaml"
    source_file.write_text("homekit: []\n", encoding="utf-8")
    control = root / "continue"
    journal = JournalStore(root / "journal.json")
    engine = MigrationEngine(
        journal=journal,
        snapshots=SnapshotStore(root / "snapshot.json"),
        lock=BridgeMigrationLock(root / "bridge.lock", "bridge-a"),
        experimental_test_permit=True,
    )

    def gated(name: str):
        def callback():
            (root / f"entered-{name}").write_text("1", encoding="utf-8")
            if operation == name:
                while not control.exists():
                    time.sleep(0.01)
            return {name: f"{name}-done"}

        return callback

    def source_switch():
        _atomic_write(source_file, "homekit: !include native.yaml\n")
        return gated("source_switch")()

    steps = {
        name: gated(name)
        for name in ("lock", "snapshot", "prepare", "quiesce", "reload", "verify", "commit")
    }
    steps["source_switch"] = source_switch
    snapshot = MigrationSnapshot.build(
        transaction_id="pending",
        bridge_id="bridge-a",
        logical={"entry_id": "bridge-a", "source": "user"},
        files={"configuration.yaml": source_file},
    )
    engine.execute(
        MigrationPlan("bridge-a", "user", "import", snapshot.fingerprint, "revision-1"),
        steps=steps,
        snapshot=snapshot,
    )
    print(json.dumps(journal.load().as_dict(), sort_keys=True))


if __name__ == "__main__":
    main()
