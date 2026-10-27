"""Event-driven read-only coordinator."""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from homeassistant.core import callback
from .compatibility import classify_entity
from .homekit_reader import read_homekit_entries
from .inventory import build_inventory
from .change_planner import plan_changes
from .fingerprint import build_fingerprint
from .homekit_writer import HomeKitWriter, OptionsDiff, build_options_diff, HomeKitWriteBlocked, HomeKitActivationUnknown
from .reconcile import reconcile_desired_state
from .exporter import export_desired_state
from .yaml_store import (
    YamlSnapshot,
    YamlStore,
    YamlValidationError,
    YamlVersionConflict,
    empty_document,
)
from .const import MANAGEMENT_MODES, MODE_HOMEKIT_BRIDGE, MODE_HOMEKIT_MANAGER, MODE_YAML
from .mode_store import ModeStore
from .grouping import build_area_views, build_device_views
from .diagnostics import build_diagnostics, diagnostics_summary, group_diagnostics
from .history import make_history_entry, restore_as_draft
from .history_store import HistoryStore
from .config_source import inspect_configuration_sources
from .migration import build_migration_plan, build_migration_matrix, completed_verification
from .migration_store import MigrationStore
from .management_store import ManagementStore

_LOGGER = logging.getLogger(__name__)

class HomeKitManagerCoordinator:
    """Build and cache an inventory; never writes HomeKit configuration."""
    def __init__(self, hass):
        self.hass = hass
        self.inventory: list[dict[str, Any]] = []
        self.bridges: list[dict[str, Any]] = []
        self.devices: list[dict[str, Any]] = []
        self.areas: list[dict[str, Any]] = []
        self.diagnostic_findings: list[dict[str, Any]] = []
        self.history_entries: list[dict[str, Any]] = []
        self.history_store = HistoryStore(hass)
        self.selected_bridge_id: str | None = None
        self.last_error: str | None = None
        self.fingerprint: str | None = None
        config_path = getattr(getattr(hass, "config", None), "path", None)
        yaml_path = config_path("homekit_manager.yaml") if callable(config_path) else "/config/homekit_manager.yaml"
        self.yaml_store = YamlStore(yaml_path)
        self.mode_store = ModeStore(hass)
        self.migration_store = MigrationStore(hass)
        self.management_store = ManagementStore(hass)
        self.management_statuses: dict[str, dict[str, Any]] = {}
        self.migration_status: dict[str, Any] = {
            "state": "unknown",
            "message": "Noch kein verifizierter Speicherwechselstatus vorhanden.",
            "stale": True,
        }
        self.desired_modes: dict[str, str] = {}
        self.configuration_sources: dict[str, Any] = {
            "sources": [], "active_mode": "unknown", "mixed": False,
            "ambiguous": True, "message": "Konfigurationsquelle wird gelesen.",
        }
        self._configuration_text = ""
        self._manager_file_exists = False
        self._config_dir = Path("/config")
        # File I/O is intentionally deferred to the executor.  The coordinator
        # is constructed during Home Assistant setup, which runs on the event
        # loop and must not perform synchronous filesystem reads.
        self.yaml_snapshot = YamlSnapshot(empty_document(), None, False, True, None, None)
        self._unsubscribers = []
        self._refresh_task: asyncio.Task | None = None
        self.activation_statuses: dict[str, dict[str, Any]] = {}
        self._activation_locks: dict[str, asyncio.Lock] = {}
        self._subscribe_events()

    async def async_initialize(self) -> None:
        """Load the desired-state snapshot without blocking the event loop."""
        self.desired_modes = await self.mode_store.async_load()
        self.yaml_snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
        self.history_entries = await self.history_store.async_load()
        stored_migration = await self.migration_store.async_load()
        if stored_migration:
            self.migration_status = stored_migration
        self.management_statuses = await self.management_store.async_load()
        config_path = getattr(getattr(self.hass, "config", None), "path", None)
        if callable(config_path):
            configuration_file = config_path("configuration.yaml")
            manager_file = config_path("homekit_manager.yaml")
            self._config_dir = Path(configuration_file).parent
            def _read_sources():
                try:
                    with open(configuration_file, encoding="utf-8") as configuration_stream:
                        text = configuration_stream.read()
                except OSError:
                    text = ""
                try:
                    manager_exists = Path(manager_file).exists()
                except OSError:
                    manager_exists = False
                return text, manager_exists
            self._configuration_text, self._manager_file_exists = await self.hass.async_add_executor_job(_read_sources)
            self.configuration_sources = inspect_configuration_sources(
                self._configuration_text,
                config_dir=self._config_dir,
                manager_file_exists=self._manager_file_exists,
                bridge_count=0,
            )

    def selected_bridge(self) -> dict[str, Any] | None:
        """Return the selected bridge, never an arbitrary bridge."""
        if self.selected_bridge_id is None:
            return self.bridges[0] if len(self.bridges) == 1 else None
        return next((bridge for bridge in self.bridges if bridge.get("entry_id") == self.selected_bridge_id), None)

    async def async_select_bridge(self, entry_id: str) -> dict[str, Any]:
        """Select an existing bridge context without changing HomeKit."""
        if not isinstance(entry_id, str) or not any(bridge.get("entry_id") == entry_id for bridge in self.bridges):
            raise ValueError("Unbekannte oder nicht verfügbare HomeKit-Bridge")
        self.selected_bridge_id = entry_id
        await self.async_refresh()
        return {"selected_bridge_id": self.selected_bridge_id, "overview": self.overview()}

    def _subscribe_events(self) -> None:
        for event_type in ("state_changed", "entity_registry_updated", "device_registry_updated", "area_registry_updated", "homekit_state_change"):
            self._unsubscribers.append(self.hass.bus.async_listen(event_type, self._event_received))

    @callback
    def _event_received(self, _event) -> None:
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_task = self.hass.async_create_task(self._async_debounced_refresh())

    async def _async_debounced_refresh(self) -> None:
        """Coalesce bursts of state/registry events without polling."""
        await asyncio.sleep(0.25)
        await self.async_refresh()

    async def async_refresh(self) -> None:
        """Refresh from registries/states and retain unknown publication status."""
        try:
            from homeassistant.helpers import area_registry, device_registry, entity_registry
            entities = entity_registry.async_get(self.hass)
            devices = device_registry.async_get(self.hass)
            areas = area_registry.async_get(self.hass)
            states = {state.entity_id: state for state in self.hass.states.async_all()}
            records = build_inventory(entities, devices, areas, states)
            bridges = read_homekit_entries(self.hass)
            self.configuration_sources = inspect_configuration_sources(
                self._configuration_text,
                config_dir=self._config_dir,
                manager_file_exists=self._manager_file_exists,
                bridge_count=len(bridges),
            )
            bridge_ids = {bridge.entry_id for bridge in bridges}
            if self.selected_bridge_id not in bridge_ids:
                self.selected_bridge_id = next(iter(bridge_ids), None) if len(bridges) == 1 else None
            selected = next((bridge for bridge in bridges if bridge.entry_id == self.selected_bridge_id), None)
            bridge_filter = selected.filter if selected is not None else None
            self.inventory = []
            from .filtering import evaluate_filter
            from .filtering import build_core_filter
            core_filter = build_core_filter(bridge_filter)
            for record in records:
                item = record.as_dict()
                item["compatibility"] = classify_entity(record).as_dict()
                item["homekit"] = {"configured_by_filter": None, "current_status": "unknown", "filter_reason": "filter_unavailable", "published": "unknown", "apple_home_visible": "unknown"}
                if bridge_filter is not None:
                    item["homekit"].update(evaluate_filter(record.entity_id, record.entity_category, record.hidden_by, bridge_filter, core_filter).as_dict())
                configured = item["homekit"].get("configured_by_filter")
                item["homekit"]["current_status"] = "included" if configured is True else "excluded" if configured is False else "unknown"
                self.inventory.append(item)
            self.bridges = [bridge.as_dict() | {"selected": bridge.entry_id == self.selected_bridge_id} for bridge in bridges]
            self.devices = build_device_views(self.inventory)
            self.areas = build_area_views(self.inventory)
            self.yaml_snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
            self.diagnostic_findings = build_diagnostics(self.inventory, self.bridges, self.yaml_snapshot.as_dict() if hasattr(self.yaml_snapshot, "as_dict") else {"valid": self.yaml_snapshot.valid, "error": self.yaml_snapshot.error})
            self.fingerprint = build_fingerprint(self.bridges, self.inventory, self.yaml_snapshot.document)
            self.last_error = None
        except Exception as err:
            self.last_error = str(err)
            _LOGGER.exception("HomeKit Manager Inventaraktualisierung fehlgeschlagen")

    def overview(self) -> dict[str, Any]:
        compatible = sum(item["compatibility"]["status"] == "supported" for item in self.inventory)
        configured = sum(item["homekit"]["configured_by_filter"] is True for item in self.inventory)
        excluded = sum(item["homekit"]["configured_by_filter"] is False for item in self.inventory)
        unknown = sum(item["homekit"]["configured_by_filter"] is None for item in self.inventory)
        filter_known = bool(self.bridges) and unknown == 0
        return {
            "total_entities": len(self.inventory),
            "active_entities": sum(item["disabled_by"] is None for item in self.inventory),
            "disabled_entities": sum(item["disabled_by"] is not None for item in self.inventory),
            "unavailable_entities": sum(not item["available"] for item in self.inventory),
            "device_count": len({item["device_id"] for item in self.inventory if item["device_id"]}),
            "area_count": len({item["area_id"] for item in self.inventory if item["area_id"]}),
            "compatible_entities": compatible,
            "configured_entities": configured if filter_known else None,
            "excluded_entities": excluded if filter_known else None,
            "unknown_entities": unknown,
            "bridges": len(self.bridges),
            "bridge_selection_required": len(self.bridges) > 1,
            "selected_bridge_id": self.selected_bridge_id,
            "fingerprint": self.fingerprint,
            "yaml_valid": self.yaml_snapshot.valid,
            "yaml_exists": self.yaml_snapshot.exists,
            "yaml_file_version": self.yaml_snapshot.file_version,
            "last_error": self.last_error,
            "last_updated": self.yaml_snapshot.last_modified,
            "diagnostics": diagnostics_summary(self.diagnostic_findings),
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return the current diagnostic snapshot without applying corrections."""
        return {"findings": self.diagnostic_findings, "grouped_findings": group_diagnostics(self.diagnostic_findings), "summary": diagnostics_summary(self.diagnostic_findings), "fingerprint": self.fingerprint}

    def activation_status(self, entry_id: str | None = None, request_id: str | None = None) -> dict[str, Any]:
        """Return the last in-memory activation state; restart means unknown."""
        entry_id = entry_id or self.selected_bridge_id
        status = self.activation_statuses.get(entry_id or "")
        if status is None:
            return {
                "entry_id": entry_id,
                "request_id": request_id,
                "state": "unknown",
                "message": "Für diesen Anwendungsvorgang liegt kein bestätigter Laufzeitstatus vor.",
            }
        if request_id and status.get("request_id") != request_id:
            return {
                "entry_id": entry_id,
                "request_id": request_id,
                "state": "unknown",
                "message": "Der angeforderte Anwendungsvorgang ist nicht mehr im Speicher vorhanden.",
            }
        return dict(status)

    def _set_activation_status(self, entry_id: str, request_id: str, state: str, **details: Any) -> dict[str, Any]:
        status = {
            "entry_id": entry_id,
            "request_id": request_id,
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self.activation_statuses[entry_id] = status
        return status

    def history(self) -> dict[str, Any]:
        """Return bounded desired-state history without pairing material."""
        return {"entries": list(self.history_entries), "count": len(self.history_entries)}

    def restore_history(self, index: int) -> dict[str, Any]:
        if not isinstance(index, int) or index < 0 or index >= len(self.history_entries):
            raise ValueError("Historieneintrag nicht gefunden")
        return restore_as_draft(self.history_entries[index])

    def _active_mode(self, bridge: dict[str, Any] | None) -> str:
        """Infer the current mode without claiming a migration occurred."""
        detected = self.configuration_sources.get("active_mode")
        if detected in (*MANAGEMENT_MODES, "mixed"):
            return detected
        if bridge:
            return MODE_HOMEKIT_BRIDGE
        if self.yaml_snapshot.exists and self.yaml_snapshot.valid:
            return MODE_YAML
        return MODE_HOMEKIT_MANAGER

    def mode_status(self) -> dict[str, Any]:
        """Return conservative mode status and the six-direction matrix."""
        bridge = self.selected_bridge()
        entry_id = bridge.get("entry_id") if bridge else None
        active = self._active_mode(bridge)
        desired = self.desired_modes.get(entry_id, active) if entry_id else active
        matrix = build_migration_matrix()
        return {
            "active_mode": active,
            "desired_mode": desired,
            "prepared_mode": desired if desired != active else None,
            "transition": "blocked" if desired != active else "stable",
            "bridge_entry_id": entry_id,
            "bridge_title": bridge.get("title") if bridge else None,
            "yaml_path": str(self.yaml_store.path),
            "yaml_valid": self.yaml_snapshot.valid,
            "yaml_exists": self.yaml_snapshot.exists,
            "matrix": matrix,
            "supported_modes": list(MANAGEMENT_MODES),
            "bridge_count": len(self.bridges),
            "bridge_selection_required": len(self.bridges) > 1,
            "message": "Moduswechsel bleiben gesperrt, solange Bridge-Identität und Pairing-Erhalt nicht nachgewiesen sind.",
            "source_detection": self.configuration_sources,
        }

    def migration_plan(self, target: str | None = None) -> dict[str, Any]:
        """Return a verified-source plan without changing Home Assistant."""
        bridge = self.selected_bridge()
        source = self._active_mode(bridge)
        if source not in MANAGEMENT_MODES:
            source = MODE_HOMEKIT_BRIDGE if bridge else MODE_HOMEKIT_MANAGER
        target = target or self.desired_modes.get(bridge.get("entry_id") if bridge else "", source)
        return build_migration_plan(source, target, bridge.get("entry_id") if bridge else None) | {
            "active_mode": source,
            "desired_mode": target,
            "status": self.migration_status,
        }

    def migration_status_snapshot(self) -> dict[str, Any]:
        """Return persisted status; stale status is never treated as active."""
        return dict(self.migration_status)

    def management_status(self) -> dict[str, Any]:
        """Describe native source and explicit Manager ownership separately."""
        bridge = self.selected_bridge()
        if bridge is None:
            return {
                "state": "unknown",
                "configuration_source": "unknown",
                "management_surface": "homekit_manager",
                "message": "Keine eindeutig ausgewählte HomeKit-Bridge vorhanden.",
            }
        entry_id = bridge["entry_id"]
        source = "home_assistant" if bridge.get("source") == "user" else "yaml" if bridge.get("source") == "import" else "unknown"
        status = self.management_statuses.get(entry_id, {})
        state = status.get("state", "not_enabled")
        if status.get("source") not in (None, source):
            state = "unknown"
        if bridge.get("state") != "loaded" and state == "active":
            state = "unknown"
        active = state == "active" and source == "home_assistant"
        management_surface = "homekit_manager" if active else "home_assistant"
        write_status = "available" if active else "locked" if bridge.get("state") == "loaded" else "unknown"
        return {
            "entry_id": entry_id,
            "bridge_title": bridge.get("title"),
            "configuration_source": source,
            "configuration_source_label": "Home Assistant" if source == "home_assistant" else "YAML" if source == "yaml" else "Unbekannt",
            "management_surface": management_surface,
            "management_surface_label": "HomeKit Manager" if management_surface == "homekit_manager" else "Home Assistant",
            "state": state,
            "active": active,
            "write_status": write_status,
            "write_status_label": {"available": "Verfügbar", "locked": "Gesperrt", "unknown": "Status unbekannt"}[write_status],
            "bridge_state": bridge.get("state"),
            "supported": bridge.get("source") == "user" and bridge.get("state") == "loaded",
            "message": status.get("message") or ("HomeKit Manager verwaltet diese Bridge jetzt." if active else "Die Verwaltung liegt bei Home Assistant. HomeKit Manager kann für diese Bridge aktiviert werden."),
            "step": status.get("step"),
            "request_id": status.get("request_id"),
            "updated_at": status.get("updated_at"),
        }

    async def async_enable_management(self, confirmed: bool = False) -> dict[str, Any]:
        """Enable the management surface after live, read-only prerequisites."""
        bridge = self.selected_bridge()
        status = self.management_status()
        if bridge is None or not status["supported"]:
            status["state"] = "blocked"
            status["message"] = "Nur eine geladene SOURCE_USER-Bridge kann durch HomeKit Manager verwaltet werden."
            return status
        if not confirmed:
            status["state"] = "awaiting_confirmation"
            status["message"] = "Bestätigung erforderlich: HomeKit Manager verwaltet danach diese bestehende Bridge; die native Quelle bleibt Home Assistant."
            return status
        request_id = uuid4().hex
        entry_id = bridge["entry_id"]
        status.update({"state": "verifying", "step": "validate", "request_id": request_id, "message": "Voraussetzungen geprüft; Bridge wird erneut verifiziert."})
        self.management_statuses[entry_id] = status.copy()
        await self.management_store.async_save(self.management_statuses)
        await self.async_refresh()
        verified = self.selected_bridge()
        if verified is None or verified.get("entry_id") != entry_id or verified.get("state") != "loaded":
            status.update({"state": "unknown", "step": "verify", "message": "Bridge-Verifikation nach der Prüfung nicht eindeutig."})
        else:
            status.update({"state": "active", "step": "complete", "message": "HomeKit Manager verwaltet diese Bridge jetzt."})
        self.management_statuses[entry_id] = status.copy()
        await self.management_store.async_save(self.management_statuses)
        return self.management_status()

    async def async_disable_management(self, confirmed: bool = False) -> dict[str, Any]:
        """Return ownership to Home Assistant without changing native options."""
        bridge = self.selected_bridge()
        status = self.management_status()
        if bridge is None or not status["supported"]:
            status["state"] = "blocked"
            status["message"] = "Nur eine geladene SOURCE_USER-Bridge kann zurückgestellt werden."
            return status
        if not confirmed:
            status["state"] = "awaiting_confirmation"
            status["message"] = "Bestätigung erforderlich: Die Verwaltungsoberfläche wird auf Home Assistant zurückgestellt. Entwürfe bleiben erhalten."
            return status
        request_id = uuid4().hex
        entry_id = bridge["entry_id"]
        status.update({"state": "verifying", "step": "validate", "request_id": request_id, "message": "Bridge verifiziert; Verwaltungsstatus wird auf Home Assistant zurückgestellt."})
        self.management_statuses[entry_id] = status.copy()
        await self.management_store.async_save(self.management_statuses)
        await self.async_refresh()
        verified = self.selected_bridge()
        if verified is None or verified.get("entry_id") != entry_id or verified.get("state") != "loaded":
            status.update({"state": "unknown", "step": "verify", "message": "Bridge-Verifikation nach der Rückstellung nicht eindeutig."})
        else:
            status.update({"state": "inactive", "step": "complete", "message": "Die Verwaltung wurde auf Home Assistant zurückgestellt."})
        self.management_statuses[entry_id] = status.copy()
        await self.management_store.async_save(self.management_statuses)
        return self.management_status()

    async def async_start_migration(self, target: str, confirmed: bool = False) -> dict[str, Any]:
        """Verify same-source state or explicitly block cross-source migration."""
        plan = self.migration_plan(target)
        if not plan["supported"]:
            status = {
                "state": "blocked",
                "progress": None,
                "step": None,
                "message": plan["reason"],
                "bridge_entry_id": plan.get("bridge_entry_id"),
                "source": plan["source"],
                "target": plan["target"],
                "changed": False,
                "migration_performed": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "stale": False,
            }
            self.migration_status = status
            await self.migration_store.async_save(status)
            return plan | {"status": status}
        if not confirmed:
            return plan | {"status": {"state": "awaiting_confirmation", "progress": 0, "message": "Explizite Bestätigung für die schreibfreie Verifikation erforderlich."}}
        await self.async_refresh()
        bridge = self.selected_bridge()
        if plan.get("bridge_entry_id") != (bridge.get("entry_id") if bridge else None):
            raise ValueError("Bridge-Kontext hat sich während der Verifikation geändert")
        status = completed_verification(plan, plan.get("bridge_entry_id"))
        status.update({"source": plan["source"], "target": plan["target"], "stale": False})
        self.migration_status = status
        await self.migration_store.async_save(status)
        return plan | {"status": status}

    async def async_set_mode(self, mode: str) -> dict[str, Any]:
        """Persist a desired mode; never activate a risky migration."""
        if mode not in MANAGEMENT_MODES:
            raise ValueError("Unbekannter Verwaltungsmodus")
        bridge = self.selected_bridge()
        entry_id = bridge.get("entry_id") if bridge else None
        if not entry_id:
            raise ValueError("Keine eindeutige HomeKit-Bridge gefunden")
        self.desired_modes[entry_id] = mode
        await self.mode_store.async_save(self.desired_modes)
        return self.mode_status()

    def yaml_status(self) -> dict[str, Any]:
        snapshot = self.yaml_store.load()
        self.yaml_snapshot = snapshot
        return {"document": snapshot.document, "schema_version": snapshot.document.get("schema_version"), "file_version": snapshot.file_version, "last_modified": snapshot.last_modified, "exists": snapshot.exists, "valid": snapshot.valid, "error": snapshot.error, "backup_exists": self.yaml_store.backup_path.is_file(), "included": self.configuration_sources.get("manager_include", False), "active_mode": self.configuration_sources.get("active_mode"), "is_applied": False}

    async def async_yaml_status(self) -> dict[str, Any]:
        """Return YAML status after reading the file in the executor."""
        snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
        self.yaml_snapshot = snapshot
        return {"document": snapshot.document, "schema_version": snapshot.document.get("schema_version"), "file_version": snapshot.file_version, "last_modified": snapshot.last_modified, "exists": snapshot.exists, "valid": snapshot.valid, "error": snapshot.error, "backup_exists": await self.hass.async_add_executor_job(self.yaml_store.backup_path.is_file), "included": self.configuration_sources.get("manager_include", False), "active_mode": self.configuration_sources.get("active_mode"), "is_applied": False}

    def validate_draft(self, document: Any) -> dict[str, Any]:
        from .yaml_store import validate_document
        normalized = validate_document(document)
        known_bridges = {bridge.get("entry_id") for bridge in self.bridges}
        unknown_bridges = set(normalized["bridges"]) - known_bridges
        if unknown_bridges:
            raise ValueError("Unbekannte HomeKit-Bridge: " + ", ".join(sorted(unknown_bridges)))
        warnings = []
        known = {item["entity_id"] for item in self.inventory}
        for bridge in normalized["bridges"].values():
            warnings.extend({"entity_id": entity_id, "reason": "entity_not_in_current_inventory"} for entity_id in bridge["entities"] if entity_id not in known)
        for item in self.inventory:
            if item.get("compatibility", {}).get("status") == "unsupported" and any(item["entity_id"] in bridge["entities"] for bridge in normalized["bridges"].values()):
                warnings.append({"entity_id": item["entity_id"], "reason": "incompatible_entity"})
        return {"valid": True, "document": normalized, "warnings": warnings, "fingerprint": self.fingerprint}

    def preview(self, document: Any) -> dict[str, Any]:
        validated = self.validate_draft(document)
        if not validated["valid"]:
            return validated
        bridge = self.selected_bridge()
        entry_id = bridge.get("entry_id") if bridge else None
        result = plan_changes(bridge, validated["document"], self.inventory, entry_id)
        result.update({"valid": True, "fingerprint": self.fingerprint, "yaml_file_version": self.yaml_snapshot.file_version})
        return result

    def save_draft(self, document: Any, expected_file_version: str | None, expected_fingerprint: str | None) -> dict[str, Any]:
        if expected_fingerprint and expected_fingerprint != self.fingerprint:
            raise YamlVersionConflict("Live-Konfiguration oder Inventar wurde seit der Vorschau verändert")
        validated = self.validate_draft(document)
        snapshot = self.yaml_store.save(validated["document"], expected_file_version)
        self.yaml_snapshot = snapshot
        self.fingerprint = build_fingerprint(self.bridges, self.inventory, snapshot.document)
        self.history_entries.append(make_history_entry(snapshot.document, fingerprint=self.fingerprint, bridge_id=self.selected_bridge_id))
        self.history_entries = self.history_entries[-50:]
        self.hass.async_create_task(self.history_store.async_save(self.history_entries))
        _LOGGER.info(
            "HomeKit-Manager-Entwurf gespeichert: file_version=%s entities=%d",
            snapshot.file_version,
            sum(len(bridge["entities"]) for bridge in validated["document"]["bridges"].values()),
        )
        return self.yaml_status() | {"fingerprint": self.fingerprint, "warnings": validated["warnings"]}

    async def async_save_draft(self, document: Any, expected_file_version: str | None, expected_fingerprint: str | None) -> dict[str, Any]:
        """Validate and save a draft without synchronous I/O on the event loop."""
        if expected_fingerprint and expected_fingerprint != self.fingerprint:
            raise YamlVersionConflict("Live-Konfiguration oder Inventar wurde seit der Vorschau verändert")
        validated = self.validate_draft(document)
        snapshot = await self.hass.async_add_executor_job(
            self.yaml_store.save,
            validated["document"],
            expected_file_version,
        )
        self.yaml_snapshot = snapshot
        self.fingerprint = build_fingerprint(self.bridges, self.inventory, snapshot.document)
        self.history_entries.append(
            make_history_entry(
                snapshot.document,
                fingerprint=self.fingerprint,
                bridge_id=self.selected_bridge_id,
            )
        )
        self.history_entries = self.history_entries[-50:]
        await self.history_store.async_save(self.history_entries)
        _LOGGER.info(
            "HomeKit-Manager-Entwurf gespeichert: file_version=%s entities=%d",
            snapshot.file_version,
            sum(len(bridge["entities"]) for bridge in validated["document"]["bridges"].values()),
        )
        return await self.async_yaml_status() | {"fingerprint": self.fingerprint, "warnings": validated["warnings"]}

    def prepare_options_diff(self, document: Any) -> dict[str, Any]:
        """Prepare, but never apply, the native HomeKit options diff."""
        validated = self.validate_draft(document)
        bridge = self.selected_bridge()
        if bridge is None:
            raise ValueError("Die Ziel-Bridge ist nicht eindeutig")
        diff = build_options_diff(bridge, validated["document"], self.inventory)
        return diff.as_dict()

    async def async_apply_options_diff(
        self, document: Any, expected_fingerprint: str | None, request_id: str | None = None
    ) -> dict[str, Any]:
        """Apply a freshly validated diff to a supported SOURCE_USER bridge."""
        validated = self.validate_draft(document)
        bridge = self.selected_bridge()
        if bridge is None:
            raise ValueError("Die Ziel-Bridge ist nicht eindeutig")
        if bridge.get("source") != "user":
            raise HomeKitWriteBlocked("Nur reguläre SOURCE_USER-Bridges können angewendet werden")
        entry_id = bridge["entry_id"]
        request_id = request_id or uuid4().hex
        lock = self._activation_locks.setdefault(entry_id, asyncio.Lock())
        async with lock:
            if expected_fingerprint and expected_fingerprint != self.fingerprint:
                self._set_activation_status(entry_id, request_id, "failed", message="Fingerprint-Konflikt")
                raise YamlVersionConflict("Live-Konfiguration oder Inventar wurde seit der Vorschau verändert")
            diff = build_options_diff(bridge, validated["document"], self.inventory)
            existing = self.activation_statuses.get(entry_id)
            if existing and existing.get("request_id") == request_id:
                if existing["state"] in {"activating", "saved", "active", "failed", "unknown"}:
                    return existing | {
                        "applied": existing["state"] == "active",
                        "activation_status": existing["state"],
                        "warnings": validated["warnings"],
                    }
            self._set_activation_status(
                entry_id, request_id, "validated", fingerprint=self.fingerprint,
                changed_keys=list(diff.changed_keys),
            )
            if not diff.changed_keys:
                status = self._set_activation_status(
                    entry_id, request_id, "active", fingerprint=self.fingerprint,
                    idempotent=True, message="Der gewünschte Zustand ist bereits aktiv.",
                )
                return status | {"applied": False, "activation_status": "active", "warnings": validated["warnings"]}
            self._set_activation_status(
                entry_id, request_id, "activating", fingerprint=self.fingerprint,
                changed_keys=list(diff.changed_keys),
            )
            try:
                result = await HomeKitWriter(self.hass, allow_production=True).async_apply(diff)
                self._set_activation_status(entry_id, request_id, "saved", fingerprint=self.fingerprint)
                if self.selected_bridge_id != entry_id:
                    raise HomeKitActivationUnknown(
                        "Bridge-Kontext wurde während der Aktivierung gewechselt; Ergebnis muss erneut geprüft werden"
                    )
                await self.async_refresh()
                if self.last_error:
                    raise HomeKitActivationUnknown(
                        "Optionen gespeichert, aber der aktuelle Bridge-Zustand konnte nicht erneut gelesen werden"
                    )
                status = self._set_activation_status(
                    entry_id, request_id, "active", fingerprint=self.fingerprint,
                    activation_status=result.get("activation_status", "active"),
                )
                result["fingerprint"] = self.fingerprint
                result["warnings"] = validated["warnings"]
                result["activation_status"] = status["state"]
                result["request_id"] = request_id
                return result
            except asyncio.CancelledError:
                self._set_activation_status(entry_id, request_id, "unknown", message="Aktivierung unterbrochen")
                raise
            except HomeKitActivationUnknown as err:
                self._set_activation_status(entry_id, request_id, "unknown", message=str(err))
                raise
            except Exception as err:
                self._set_activation_status(entry_id, request_id, "failed", message=str(err))
                raise

    def reconcile(self, document: Any, baseline_fingerprint: str | None = None) -> dict[str, Any]:
        validated = self.validate_draft(document)
        bridge = self.selected_bridge()
        if bridge is None:
            raise ValueError("Die Ziel-Bridge ist nicht eindeutig")
        return reconcile_desired_state(validated["document"], bridge["entry_id"], self.inventory, baseline_fingerprint=baseline_fingerprint, current_fingerprint=self.fingerprint)

    def export(self, document: Any, format_name: str = "yaml") -> dict[str, Any]:
        validated = self.validate_draft(document)
        return {"format": format_name, "content": export_desired_state(validated["document"], format_name), "applied": False}

    async def async_shutdown(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
            self._refresh_task = None
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

