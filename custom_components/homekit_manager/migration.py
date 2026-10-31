"""Legacy source-migration descriptions; every action is disabled.

Home Assistant does not expose a stable public API for a custom integration to
move an existing HomeKit bridge between YAML, SOURCE_IMPORT and SOURCE_USER.
This module retains compatibility for status clients while 0.10.11 excludes
native source migration entirely.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .const import MANAGEMENT_MODES, MODE_HOMEKIT_BRIDGE, MODE_HOMEKIT_MANAGER, MODE_YAML

MODE_LABELS = {
    MODE_HOMEKIT_BRIDGE: "Standard",
    MODE_YAML: "YAML",
    MODE_HOMEKIT_MANAGER: "HomeKit Manager",
}

CORE_CONTRACT_BLOCKER = (
    "Quellenmigration ist in 0.10.11 nicht freigegeben. "
    "Home Assistant Core 2026.10.4/2026.11.0b0 bietet keine stabile öffentliche API für "
    "einen externen Wechsel zwischen YAML/SOURCE_IMPORT, SOURCE_USER und einer "
    "Custom-Integration-Draft-Schicht. Ein automatischer Wechsel könnte "
    "Bridge-Identität oder Pairings gefährden und bleibt daher gesperrt."
)


def build_migration_matrix() -> dict[str, dict[str, Any]]:
    """Return legacy directions with no executable target."""
    matrix: dict[str, dict[str, Any]] = {}
    for source in MANAGEMENT_MODES:
        for target in MANAGEMENT_MODES:
            same = source == target
            matrix[f"{source}->{target}"] = {
                "source": source,
                "target": target,
                "source_label": MODE_LABELS[source],
                "target_label": MODE_LABELS[target],
                "supported": False,
                "status": "not_applicable" if same else "blocked",
                "reason": (
                    "Kein Quellenwechsel erforderlich; der aktuelle Backendzustand "
                    "kann ohne Migrationsaktion gelesen werden."
                    if same else CORE_CONTRACT_BLOCKER
                ),
                "changes_homekit": False,
                "changes_pairings": False,
            }
    return matrix


def build_migration_plan(source: str, target: str, bridge_id: str | None) -> dict[str, Any]:
    """Build a deterministic plan without changing HA or HomeKit state."""
    if source not in MANAGEMENT_MODES or target not in MANAGEMENT_MODES:
        raise ValueError("Unbekannter Konfigurationsmodus")
    item = build_migration_matrix()[f"{source}->{target}"]
    return {
        **item,
        "bridge_entry_id": bridge_id,
        "steps": [],
        "progress_mode": "not_applicable",
        "requires_confirmation": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def completed_verification(plan: dict[str, Any], bridge_id: str | None) -> dict[str, Any]:
    """Describe a same-source verification as complete, never as a migration."""
    return {
        "state": "completed",
        "progress": 100,
        "step": "complete",
        "message": "Speicherort verifiziert; es wurde kein Speicherwechsel durchgeführt.",
        "bridge_entry_id": bridge_id,
        "changed": False,
        "migration_performed": False,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
