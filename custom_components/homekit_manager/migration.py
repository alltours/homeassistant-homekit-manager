"""Conservative storage-mode migration planning.

Home Assistant does not expose a stable public API for a custom integration to
move an existing HomeKit bridge between YAML, SOURCE_IMPORT and SOURCE_USER.
This module therefore models the supported read-only verification path and
returns explicit blockers for every cross-source migration.
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
    "Home Assistant Core 2026.10.4 bietet keine stabile öffentliche API für "
    "einen externen Wechsel zwischen YAML/SOURCE_IMPORT, SOURCE_USER und einer "
    "Custom-Integration-Draft-Schicht. Ein automatischer Wechsel könnte "
    "Bridge-Identität oder Pairings gefährden und bleibt daher gesperrt."
)


def build_migration_matrix() -> dict[str, dict[str, Any]]:
    """Return all nine source/target combinations, including six directions."""
    matrix: dict[str, dict[str, Any]] = {}
    for source in MANAGEMENT_MODES:
        for target in MANAGEMENT_MODES:
            same = source == target
            matrix[f"{source}->{target}"] = {
                "source": source,
                "target": target,
                "source_label": MODE_LABELS[source],
                "target_label": MODE_LABELS[target],
                "supported": same,
                "status": "verify_only" if same else "blocked",
                "reason": (
                    "Kein Speicherwechsel erforderlich; der aktuelle Backendzustand "
                    "wird erneut gelesen und verifiziert."
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
    steps = [
        {"key": "validate", "label": "Konfiguration prüfen", "progress": 16},
        {"key": "prepare", "label": "Änderungen vorbereiten", "progress": 33},
        {"key": "create", "label": "Zielkonfiguration erstellen", "progress": 50},
        {"key": "activate", "label": "Konfiguration aktivieren", "progress": 66},
        {"key": "verify", "label": "Bridge überprüfen", "progress": 83},
        {"key": "complete", "label": "Migration abschließen", "progress": 100},
    ]
    return {
        **item,
        "bridge_entry_id": bridge_id,
        "steps": steps,
        "progress_mode": "deterministic" if item["supported"] else "indeterminate",
        "requires_confirmation": bool(item["supported"]),
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
