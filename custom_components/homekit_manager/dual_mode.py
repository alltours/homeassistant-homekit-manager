"""Safe dual-mode administration metadata.

Home Assistant's native source and HomeKit Manager's administration surface are
different concepts.  This module describes that distinction without changing a
ConfigEntry, YAML source, reload state, or HAP storage.
"""
from __future__ import annotations

from typing import Any


ADMIN_MODE_UI = "ui_bridge"
ADMIN_MODE_YAML = "yaml"
ADMIN_MODES = (ADMIN_MODE_UI, ADMIN_MODE_YAML)

SOURCE_USER = "user"
SOURCE_IMPORT = "import"


def native_source_details(source: str | None) -> dict[str, Any]:
    """Return a user-facing description of a HomeKit ConfigEntry source."""
    if source == SOURCE_USER:
        return {
            "key": SOURCE_USER,
            "label": "Home Assistant UI / Config Entry",
            "short_label": "UI / Bridge",
            "kind": "native",
        }
    if source == SOURCE_IMPORT:
        return {
            "key": SOURCE_IMPORT,
            "label": "Home Assistant YAML (SOURCE_IMPORT)",
            "short_label": "YAML",
            "kind": "native",
        }
    return {
        "key": "unknown",
        "label": "Unbekannte native Konfigurationsquelle",
        "short_label": "Unbekannt",
        "kind": "unknown",
    }


def administration_mode_for_source(source: str | None) -> str | None:
    """Return the matching default Manager surface for a native source."""
    if source == SOURCE_USER:
        return ADMIN_MODE_UI
    if source == SOURCE_IMPORT:
        return ADMIN_MODE_YAML
    return None


def _mode_option(
    mode: str,
    *,
    selected: bool,
    native_source: dict[str, Any],
    bridge_mode: str,
    core_version: str,
    stale: bool,
) -> dict[str, Any]:
    """Build one safe administration-mode option."""
    if mode == ADMIN_MODE_UI:
        return {
            "key": mode,
            "label": "UI / Bridge",
            "selected": selected,
            "available": True,
            "surface": "native_entry",
            "description": (
                "Verwaltet die native Home-Assistant-Bridge über die bestätigte "
                "Config-Entry-Oberfläche."
            ),
            "native_source_required": SOURCE_USER,
            "native_source_unchanged": native_source["key"] == SOURCE_USER,
            "capabilities": {
                "entity_management": native_source["key"] == SOURCE_USER
                and bridge_mode == "bridge"
                and not stale,
                "yaml_preview": True,
                "yaml_export": True,
                "yaml_validation": True,
                "yaml_import_draft": True,
                "native_filter_management": native_source["key"] == SOURCE_USER
                and bridge_mode == "bridge"
                and not stale,
                "native_source_write": False,
            },
            "core_version": core_version,
        }
    return {
        "key": mode,
        "label": "YAML",
        "selected": selected,
        "available": True,
        "surface": "yaml_draft",
        "description": (
            "Erzeugt, validiert und exportiert eine deterministische YAML-Projektion "
            "als Entwurf. Die native Home-Assistant-Quelle bleibt unverändert."
        ),
        "native_source_required": SOURCE_IMPORT,
        "native_source_unchanged": native_source["key"] == SOURCE_IMPORT,
        "capabilities": {
            "entity_management": True and not stale,
            "yaml_preview": True,
            "yaml_export": True,
            "yaml_validation": True,
            "yaml_import_draft": True,
            "native_source_write": False,
        },
        "core_version": core_version,
    }


def build_mode_transition_plan(
    native_source: str | None,
    target_mode: str,
    *,
    bridge_entry_id: str | None,
    bridge_mode: str,
    core_version: str,
    yaml_valid: bool,
    yaml_exists: bool,
    snapshot_stale: bool,
) -> dict[str, Any]:
    """Describe a mode selection without offering a source migration."""
    if target_mode not in ADMIN_MODES:
        raise ValueError("Unbekannter Verwaltungsmodus")
    source = native_source_details(native_source)
    required_source = SOURCE_USER if target_mode == ADMIN_MODE_UI else SOURCE_IMPORT
    same_source = source["key"] == required_source
    if same_source:
        status = "same_native_source"
        title = "Verwaltungsmodus kann sicher verwendet werden"
        message = (
            "Die gewählte Oberfläche entspricht der nativen Quelle. Es ist keine "
            "Quellenmigration erforderlich."
        )
        safe_action = "manage_existing_source"
    elif target_mode == ADMIN_MODE_YAML:
        status = "draft_only"
        title = "YAML nur als sicherer Entwurf verfügbar"
        message = (
            "Eine YAML-Projektion kann geprüft und exportiert werden. Ein Wechsel "
            "von SOURCE_USER zu SOURCE_IMPORT wird nicht ausgeführt, weil Core "
            "keine stabile öffentliche Quellenmigration anbietet."
        )
        safe_action = "preview_export_validate"
    else:
        status = "read_only_projection"
        title = "UI-Modus nur als Lesesicht verfügbar"
        message = (
            "Die aktive YAML-Quelle bleibt maßgeblich. Ein Wechsel von "
            "SOURCE_IMPORT zu SOURCE_USER wird nicht ausgeführt."
        )
        safe_action = "read_existing_source"
    blockers = []
    if snapshot_stale:
        blockers.append("Der aktuelle Backend-Snapshot ist veraltet.")
    if not bridge_entry_id:
        blockers.append("Keine eindeutig ausgewählte HomeKit-Bridge.")
    if bridge_mode != "bridge":
        blockers.append("Accessory-Modus ist für diese Verwaltungsfunktionen nicht freigegeben.")
    if target_mode == ADMIN_MODE_YAML and yaml_exists and not yaml_valid:
        blockers.append("Der gespeicherte Manager-YAML-Entwurf ist ungültig oder fehlt.")
    return {
        "target_mode": target_mode,
        "target_label": "UI / Bridge" if target_mode == ADMIN_MODE_UI else "YAML",
        "status": "blocked" if blockers else status,
        "title": title,
        "message": "; ".join(blockers) if blockers else message,
        "safe_action": safe_action if not blockers else "none",
        "can_execute": False,
        "requires_confirmation": False,
        "native_source": source,
        "required_native_source": required_source,
        "native_source_change": not same_source,
        "source_migration_supported": False,
        "bridge_entry_id": bridge_entry_id,
        "bridge_mode": bridge_mode,
        "core_version": core_version,
        "pairing_preservation_proven": False,
        "identity_preservation_proven": False,
        "steps": [
            "Native Config-Entry und Quelle lesen",
            "Manager-Entwurf gegen das HomeKit-Core-Schema validieren",
            "Deterministische YAML-Projektion als Vorschau/Export erzeugen",
        ],
    }


def build_dual_mode_status(
    bridge: dict[str, Any] | None,
    *,
    core_version: str,
    yaml_valid: bool,
    yaml_exists: bool,
    snapshot_stale: bool,
) -> dict[str, Any]:
    """Return the complete read-only dual-mode contract for the UI."""
    source_value = bridge.get("source") if bridge else None
    source = native_source_details(source_value)
    bridge_mode = str((bridge or {}).get("mode") or "unknown")
    default_mode = administration_mode_for_source(source_value)
    plans = {
        mode: build_mode_transition_plan(
            source_value,
            mode,
            bridge_entry_id=bridge.get("entry_id") if bridge else None,
            bridge_mode=bridge_mode,
            core_version=core_version,
            yaml_valid=yaml_valid,
            yaml_exists=yaml_exists,
            snapshot_stale=snapshot_stale,
        )
        for mode in ADMIN_MODES
    }
    return {
        "administration_mode": default_mode or "unknown",
        "administration_mode_label": (
            "UI / Bridge" if default_mode == ADMIN_MODE_UI else "YAML" if default_mode == ADMIN_MODE_YAML else "Unbekannt"
        ),
        "native_configuration_source": source,
        "native_source_is_authoritative": True,
        "available_modes": list(ADMIN_MODES),
        "mode_options": [
            _mode_option(
                mode,
                selected=mode == default_mode,
                native_source=source,
                bridge_mode=bridge_mode,
                core_version=core_version,
                stale=snapshot_stale,
            )
            for mode in ADMIN_MODES
        ],
        "source_migration": {
            "supported": False,
            "status": "blocked",
            "reason": (
                "Home Assistant Core bietet keinen stabilen öffentlichen API-Vertrag "
                "für SOURCE_USER↔SOURCE_IMPORT. Config-Entry-ID, HAP-Persistenz, "
                "Pairings, AIDs und IIDs dürfen nicht durch einen Manager-Workaround "
                "verschoben werden."
            ),
            "pairing_risk": "high",
            "entry_id_preservation": "unproven",
        },
        "plans": plans,
    }
