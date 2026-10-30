"""Event-driven read-only coordinator."""
from __future__ import annotations
import asyncio
import logging
import time
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any
from homeassistant.core import callback
from .compatibility import classify_entity
from .homekit_reader import read_homekit_entries
from .inventory import build_inventory
from .device_reconciliation import reconcile_devices
from .change_planner import plan_changes
from .fingerprint import build_fingerprint
from .homekit_writer import build_options_diff, HomeKitWriteBlocked, HomeKitWriter as HomeKitWriter
from .reconcile import reconcile_desired_state
from .exporter import export_desired_state
from .yaml_store import (
    YamlSnapshot,
    YamlStore,
    YamlValidationError,
    YamlVersionConflict,
    YamlWriteError,
    empty_document,
)
from .const import MANAGEMENT_MODES, MODE_HOMEKIT_BRIDGE, MODE_HOMEKIT_MANAGER, MODE_YAML
from .mode_store import ModeStore
from .grouping import build_area_views, build_device_views
from .diagnostics import build_diagnostics, diagnostics_summary, group_diagnostics
from .history import make_history_entry, restore_as_draft
from .history_store import HistoryStore
from .config_source import inspect_configuration_sources
from .migration import build_migration_plan, build_migration_matrix
from .migration_store import MigrationStore
from .management_store import ManagementStore
from .activation_store import ActivationStore
from .safety import WRITE_LOCK_REASON, write_policy
from .homekit_writer import HomeKitWriteDisabled
from .operations import HomeKitOperationService
from .const import INTEGRATION_VERSION, NATIVE_FILTER_WRITE_CORE_VERSIONS
from homeassistant.const import __version__ as CORE_VERSION

_LOGGER = logging.getLogger(__name__)

class HomeKitManagerCoordinator:
    """Build and cache an inventory; never writes HomeKit configuration."""
    def __init__(self, hass):
        self.hass = hass
        self.inventory: list[dict[str, Any]] = []
        self.bridges: list[dict[str, Any]] = []
        self.devices: list[dict[str, Any]] = []
        self.device_reconciliation: dict[str, Any] = {}
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
        self.activation_store = ActivationStore(hass)
        # No writer authority exists by default. The optional native test mode
        # is in memory only; the existing local grant remains a separate path.
        self.operation_service = HomeKitOperationService(hass)
        self.operation_policy: dict[str, Any] = {"enabled": False, "reason": WRITE_LOCK_REASON, "automatic_retry": False}
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
        self.accessories: list[dict[str, Any]] = []
        self.other_homekit_entries: list[dict[str, Any]] = []
        self._refresh_lock = asyncio.Lock()
        self._refresh_pending = False
        self._stopping = False
        self.last_updated = None
        self.refresh_count = 0
        self.refresh_duration_ms = None
        self.refresh_cpu_ms = None
        self.refresh_phases_ms: dict[str, float] = {}
        self.events_seen = 0
        self.events_ignored = 0
        self.events_by_type: dict[str, int] = {}
        self.refresh_requests = 0
        self._last_refresh_monotonic = 0.0
        self._management_lock = asyncio.Lock()
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
        self.activation_statuses = await self.activation_store.async_load()
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
            self.configuration_sources = await self.hass.async_add_executor_job(
                lambda: inspect_configuration_sources(self._configuration_text, config_dir=self._config_dir, manager_file_exists=self._manager_file_exists, bridge_count=0)
            )

    def selected_bridge(self) -> dict[str, Any] | None:
        """Return the selected bridge, never an arbitrary bridge."""
        if self.selected_bridge_id is None:
            return self.bridges[0] if len(self.bridges) == 1 else None
        return next((bridge for bridge in self.bridges if bridge.get("entry_id") == self.selected_bridge_id), None)

    async def async_select_bridge(self, entry_id: str) -> dict[str, Any]:
        """Publish an entirely rebuilt bridge context, never a partial switch."""
        if not isinstance(entry_id, str) or not any(bridge.get("entry_id") == entry_id for bridge in self.bridges):
            raise ValueError("Unbekannte oder nicht verfügbare HomeKit-Bridge")
        await self.async_refresh(entry_id)
        if self.last_error or self.selected_bridge_id != entry_id:
            raise ValueError("Bridge-Kontext konnte nicht sicher aktualisiert werden")
        return {"selected_bridge_id": self.selected_bridge_id, "overview": self.overview()}

    def _subscribe_events(self) -> None:
        for event_type in ("state_changed", "entity_registry_updated", "device_registry_updated", "area_registry_updated"):
            self._unsubscribers.append(self.hass.bus.async_listen(event_type, self._event_received))

    @callback
    def _event_received(self, event) -> None:
        if self._stopping:
            return
        kind = getattr(event, "event_type", "unknown")
        self.events_seen += 1
        self.events_by_type[kind] = self.events_by_type.get(kind, 0) + 1
        if kind == "state_changed":
            data = getattr(event, "data", {}) or {}
            old, new = data.get("old_state"), data.get("new_state")
            if old is not None and new is not None and old.state == new.state and old.attributes == new.attributes:
                self.events_ignored += 1
                return
        self._refresh_pending = True
        if not self._refresh_task or self._refresh_task.done():
            self._refresh_task = self.hass.async_create_task(self._async_debounced_refresh())

    async def _async_debounced_refresh(self) -> None:
        """Coalesce bursts, retain events during I/O and cap background work."""
        while self._refresh_pending and not self._stopping:
            await asyncio.sleep(max(0.25, 1.0 - (time.monotonic() - self._last_refresh_monotonic)))
            self._refresh_pending = False
            await self.async_refresh()

    async def async_refresh(self, selected_entry_id: str | None = None) -> None:
        """Build a complete snapshot locally, then publish it atomically."""
        async with self._refresh_lock:
            self.refresh_requests += 1
            started = time.perf_counter()
            cpu_started = time.process_time()
            phase_started = started
            phases: dict[str, float] = {}
            def mark_phase(name: str) -> None:
                nonlocal phase_started
                now = time.perf_counter()
                phases[name] = round((now - phase_started) * 1000, 2)
                phase_started = now
            try:
                from homeassistant.helpers import area_registry, device_registry, entity_registry
                devices_registry = device_registry.async_get(self.hass)
                records = build_inventory(entity_registry.async_get(self.hass), devices_registry, area_registry.async_get(self.hass), {state.entity_id: state for state in self.hass.states.async_all()})
                device_reconciliation = reconcile_devices((vars(record) for record in records), devices_registry)
                mark_phase("registry_inventory")
                entries = read_homekit_entries(self.hass)
                bridges = [entry for entry in entries if entry.mode == "bridge"]
                bridge_ids = {bridge.entry_id for bridge in bridges}
                selected_id = selected_entry_id or self.selected_bridge_id
                if selected_id not in bridge_ids:
                    if selected_entry_id:
                        raise ValueError("Die gewählte Bridge ist nicht mehr verfügbar")
                    selected_id = next(iter(bridge_ids), None) if len(bridges) == 1 else None
                selected = next((entry for entry in bridges if entry.entry_id == selected_id), None)
                bridge_filter = selected.filter if selected else None
                from .filtering import evaluate_filter, build_core_filter
                core_filter = build_core_filter(bridge_filter)
                inventory = []
                for record in records:
                    item = record.as_dict()
                    item["compatibility"] = classify_entity(record, "bridge", (selected.entity_config or {}).get(record.entity_id, {}) if selected else {}, core_version=CORE_VERSION).as_dict(CORE_VERSION)
                    item["homekit"] = {"configured_by_filter": None, "current_status": "unknown", "filter_reason": "filter_unavailable", "published": "unknown", "apple_home_visible": "unknown"}
                    if bridge_filter is not None:
                        item["homekit"].update(evaluate_filter(record.entity_id, record.entity_category, record.hidden_by, bridge_filter, core_filter, state_present=record.state_present).as_dict())
                    configured = item["homekit"]["configured_by_filter"]
                    item["homekit"]["current_status"] = "included" if configured is True else "excluded" if configured is False else "unknown"
                    inventory.append(item)
                mark_phase("filter_compatibility")
                bridge_data = [entry.as_dict() | {"selected": entry.entry_id == selected_id} for entry in bridges]
                devices = build_device_views(inventory)
                areas = build_area_views(inventory)
                mark_phase("grouping")
                snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
                def read_sources():
                    configuration = self._config_dir / "configuration.yaml"
                    try:
                        text = configuration.read_text(encoding="utf-8")
                    except OSError:
                        text = ""
                    return inspect_configuration_sources(text, config_dir=self._config_dir, manager_file_exists=snapshot.exists, bridge_count=sum(entry.source == "user" for entry in bridges))
                sources = await self.hass.async_add_executor_job(read_sources)
                mark_phase("source_io")
                findings = build_diagnostics(inventory, bridge_data, {"valid": snapshot.valid, "error": snapshot.error})
                fingerprint = build_fingerprint(bridge_data, inventory, snapshot.document)
                operation_policy = await self.operation_service.authority_status(selected_id, selected.source) if selected else {"enabled": False, "reason": "Keine Bridge ausgewählt", "automatic_retry": False}
                if selected and selected.source == "import" and any(entry.source != "import" for entry in entries):
                    operation_policy = {"enabled": False, "reason": "Core homekit.reload würde auch native HomeKit-Entries neu laden", "automatic_retry": False}
                mark_phase("diagnostics_fingerprint")
                # No await beyond this point: readers see one consistent snapshot.
                self.inventory, self.bridges = inventory, bridge_data
                self.devices, self.areas = devices, areas
                self.device_reconciliation = device_reconciliation
                self.accessories = [entry.as_dict() for entry in entries if entry.mode == "accessory"]
                self.other_homekit_entries = [entry.as_dict() for entry in entries if entry.mode not in {"accessory", "bridge"}]
                self.selected_bridge_id = selected_id
                self.yaml_snapshot, self.configuration_sources = snapshot, sources
                self.diagnostic_findings, self.fingerprint = findings, fingerprint
                self.operation_policy = operation_policy
                self.last_error = None
                self.last_updated = datetime.now(timezone.utc).isoformat()
                self.refresh_count += 1
                self.refresh_duration_ms = round((time.perf_counter() - started) * 1000, 2)
                self.refresh_cpu_ms = round((time.process_time() - cpu_started) * 1000, 2)
                self.refresh_phases_ms = phases
                self._last_refresh_monotonic = time.monotonic()
                self.hass.bus.async_fire("homekit_manager_updated", {"revision": self.refresh_count})
            except Exception as err:
                self.last_error = str(err)
                _LOGGER.exception("HomeKit Manager Inventaraktualisierung fehlgeschlagen; letzter vollständiger Stand bleibt erhalten")

    def overview(self) -> dict[str, Any]:
        compatible = sum(item["compatibility"]["status"] == "supported" for item in self.inventory)
        configured = sum(item["homekit"]["configured_by_filter"] is True for item in self.inventory)
        excluded = sum(item["homekit"]["configured_by_filter"] is False for item in self.inventory)
        unknown = sum(item["homekit"]["configured_by_filter"] is None for item in self.inventory)
        filter_known = bool(self.bridges) and unknown == 0
        return {
            "total_entities": len(self.inventory),
            "active_entities": sum(item.get("availability_status") != "disabled" for item in self.inventory),
            "disabled_entities": sum(item.get("availability_status") == "disabled" for item in self.inventory),
            "unavailable_entities": sum(not item["available"] for item in self.inventory),
            "device_count": len({item["device_id"] for item in self.inventory if item["device_id"]}),
            "device_reconciliation": self.device_reconciliation,
            "availability_counts": {status: sum(item.get("availability_status") == status for item in self.inventory) for status in ("available", "unavailable", "unknown", "no_state", "disabled")},
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
            "last_updated": self.last_updated,
            "snapshot_stale": bool(self.last_error),
            "integration_version": INTEGRATION_VERSION,
            "core_version": CORE_VERSION,
            "accessories": len(self.accessories),
            "write_policy": write_policy(),
            "operation_policy": {"enabled": True, "reason": "Nur isolierte Testinstanz", "automatic_retry": False}
                                if self.operation_service._isolated_write_authority else self.operation_policy,
            "test_write_mode": self.operation_service.test_write_mode.status(),
            "refresh_count": self.refresh_count,
            "refresh_duration_ms": self.refresh_duration_ms,
            "refresh_cpu_ms": self.refresh_cpu_ms,
            "refresh_phases_ms": dict(self.refresh_phases_ms),
            "events_seen": self.events_seen,
            "events_ignored": self.events_ignored,
            "events_by_type": dict(self.events_by_type),
            "refresh_requests": self.refresh_requests,
            "diagnostics": diagnostics_summary(self.diagnostic_findings),
        }

    def diagnostics(self) -> dict[str, Any]:
        """Return the current diagnostic snapshot without applying corrections."""
        return {"findings": self.diagnostic_findings, "grouped_findings": group_diagnostics(self.diagnostic_findings), "summary": diagnostics_summary(self.diagnostic_findings), "fingerprint": self.fingerprint}

    def activation_status(self, entry_id: str | None = None, request_id: str | None = None) -> dict[str, Any]:
        """Report evidence without resolving unknown into success or failure."""
        entry_id = entry_id or self.selected_bridge_id
        stored = self.activation_statuses.get(entry_id or "")
        status = dict(stored) if stored else {"entry_id": entry_id, "request_id": request_id, "state": "unknown", "message": "Kein persistenter Aktivierungsnachweis vorhanden. Frühere Vorgänge können nicht nachträglich als erfolgreich bestätigt werden."}
        if request_id and status.get("request_id") != request_id:
            status = {"entry_id": entry_id, "request_id": request_id, "state": "unknown", "message": "Für diese Request-ID liegt kein Aktivierungsnachweis vor."}
        bridge = next((item for item in self.bridges if item["entry_id"] == entry_id), None)
        return status | {"has_operation": stored is not None, "persistent": stored is not None, "automatic_retry": False, "write_policy": write_policy(), "observations": {"bridge_state": bridge.get("state") if bridge else "unknown", "last_updated": self.last_updated, "snapshot_stale": bool(self.last_error)}, "verification_is_activation_proof": False}

    async def async_record_activation_status(self, entry_id: str, request_id: str, state: str, **details: Any) -> dict[str, Any]:
        """Durably record Manager evidence; never change HomeKit or retry it."""
        if state not in {"validated", "prepared", "activating", "saved", "active", "failed", "unknown"}:
            raise ValueError("Unbekannter Aktivierungszustand")
        status = {"entry_id": entry_id, "request_id": request_id, "state": state, "updated_at": datetime.now(timezone.utc).isoformat(), **details}
        statuses = self.activation_statuses | {entry_id: status}
        await self.activation_store.async_save(statuses)
        self.activation_statuses = statuses
        return dict(status)

    def history(self) -> dict[str, Any]:
        """Return bounded desired-state history without pairing material."""
        return {"entries": list(self.history_entries), "count": len(self.history_entries)}

    def restore_history(self, index: int) -> dict[str, Any]:
        if not isinstance(index, int) or index < 0 or index >= len(self.history_entries):
            raise ValueError("Historieneintrag nicht gefunden")
        entry = self.history_entries[index]
        result = restore_as_draft(entry)
        bridge_id = entry.get("bridge_id")
        if bridge_id and bridge_id in result["document"]["bridges"]:
            result["document"]["bridges"] = {bridge_id: result["document"]["bridges"][bridge_id]}
        return result | {"bridge_id": bridge_id}

    def _active_mode(self, bridge: dict[str, Any] | None) -> str:
        """Native entry source is authoritative; a draft file is not a source."""
        if bridge and not self.last_error:
            return MODE_HOMEKIT_BRIDGE if bridge.get("source") == "user" else MODE_YAML if bridge.get("source") == "import" else "unknown"
        return "unknown"

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
            "message": "Quellenmigration ist weder für 0.9.24 noch für 0.10.0 vorgesehen; bestehende Bridges behalten ihre Quelle.",
            "source_detection": self.configuration_sources,
        }

    def migration_plan(self, target: str | None = None) -> dict[str, Any]:
        """Return a non-executable legacy description without changing Home Assistant."""
        bridge = self.selected_bridge()
        source = self._active_mode(bridge)
        if source not in MANAGEMENT_MODES:
            source = MODE_HOMEKIT_BRIDGE if bridge else MODE_HOMEKIT_MANAGER
        target = target or self.desired_modes.get(bridge.get("entry_id") if bridge else "", source)
        return build_migration_plan(source, target, bridge.get("entry_id") if bridge else None) | {
            "active_mode": self._active_mode(bridge),
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
                "management_surface": "unknown",
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
        active = state == "active" and source == "home_assistant" and not self.last_error
        management_surface = "unknown" if state in {"unknown", "verifying"} or self.last_error else "homekit_manager" if active else "home_assistant"
        write_status = "locked"
        return {
            "entry_id": entry_id,
            "bridge_title": bridge.get("title"),
            "configuration_source": source,
            "configuration_source_label": "Home Assistant" if source == "home_assistant" else "YAML" if source == "yaml" else "Unbekannt",
            "management_surface": management_surface,
            "management_surface_label": "HomeKit Manager" if management_surface == "homekit_manager" else "Home Assistant" if management_surface == "home_assistant" else "Unbekannt",
            "write_policy": write_policy(),
            "state": state,
            "active": active,
            "write_status": write_status,
            "write_status_label": {"available": "Verfügbar", "locked": "Gesperrt", "unknown": "Status unbekannt"}[write_status],
            "bridge_state": bridge.get("state"),
            "supported": bridge.get("source") == "user" and bridge.get("state") == "loaded" and bridge.get("mode", "bridge") == "bridge" and not self.last_error and CORE_VERSION in NATIVE_FILTER_WRITE_CORE_VERSIONS and self.activation_statuses.get(entry_id, {}).get("state") not in {"unknown", "activating", "saved"},
            "message": status.get("message") or ("HomeKit Manager verwaltet diese Bridge jetzt." if active else "Die Verwaltung liegt bei Home Assistant. HomeKit Manager kann für diese Bridge aktiviert werden."),
            "step": status.get("step"),
            "request_id": status.get("request_id"),
            "updated_at": status.get("updated_at"),
        }

    async def async_enable_management(self, confirmed: bool = False, expected_entry_id: str | None = None) -> dict[str, Any]:
        return await self._async_change_management(True, confirmed, expected_entry_id)

    async def async_disable_management(self, confirmed: bool = False, expected_entry_id: str | None = None) -> dict[str, Any]:
        return await self._async_change_management(False, confirmed, expected_entry_id)

    async def _async_change_management(self, enabled: bool, confirmed: bool, expected_entry_id: str | None) -> dict[str, Any]:
        """Serialize metadata changes; persist the native source and verify context."""
        async with self._management_lock:
            bridge = self.selected_bridge()
            status = self.management_status()
            if expected_entry_id and (bridge is None or bridge["entry_id"] != expected_entry_id):
                raise ValueError("Die ausgewählte Bridge wurde geändert. Bitte erneut prüfen.")
            if bridge is None or not status.get("supported"):
                return status | {"state": "blocked", "message": "Nur eine geladene Bridge mit nativer Home-Assistant-Konfiguration kann durch HomeKit Manager verwaltet werden."}
            if not confirmed:
                return status | {"state": "awaiting_confirmation", "message": "Bestätigung erforderlich: Nur die Verwaltungszuordnung wird gespeichert; HomeKit bleibt unverändert."}
            entry_id = bridge["entry_id"]
            status.update(source=status["configuration_source"], updated_at=datetime.now(timezone.utc).isoformat(), state="verifying", step="validate", request_id=uuid4().hex, message="Verwaltungszuordnung wird unabhängig von der HomeKit-Konfiguration geprüft.")
            self.management_statuses[entry_id] = status.copy()
            try:
                await self.management_store.async_save(self.management_statuses)
                await self.async_refresh()
                verified = self.selected_bridge()
                if self.last_error or verified is None or verified.get("entry_id") != entry_id or verified.get("state") != "loaded" or verified.get("source") != "user":
                    status.update(state="unknown", step="verify", message="Bridge-Verifikation ist nicht eindeutig. Keine HomeKit-Änderung ausgelöst.")
                else:
                    status.update(state="active" if enabled else "inactive", step="complete", message="HomeKit Manager verwaltet diese Bridge jetzt." if enabled else "Die Verwaltung wurde auf Home Assistant zurückgestellt.")
                statuses = self.management_statuses | {entry_id: status.copy()}
                await self.management_store.async_save(statuses)
                self.management_statuses = statuses
            except Exception:
                self.management_statuses[entry_id] = status | {"state": "unknown", "message": "Verwaltungszuordnung konnte nicht dauerhaft bestätigt werden."}
                raise
            return self.management_status()

    async def async_start_migration(self, target: str, confirmed: bool = False) -> dict[str, Any]:
        """Legacy endpoint: no migration action is offered in 0.9.24."""
        plan = self.migration_plan(target)
        return plan | {"status": {"state": "blocked", "progress": None, "step": None,
                                  "message": "Quellenmigration ist weder für 0.9.24 noch 0.10.0 vorgesehen.",
                                  "bridge_entry_id": plan.get("bridge_entry_id"), "source": plan["source"],
                                  "target": plan["target"], "changed": False,
                                  "migration_performed": False, "automatic_retry": False}}

    async def async_set_mode(self, mode: str) -> dict[str, Any]:
        """Deprecated write endpoint; never persist a different source."""
        raise ValueError("Quellenmigration ist weder für 0.9.24 noch 0.10.0 vorgesehen")

    def _yaml_status_payload(self, snapshot, backup_exists=False):
        return {"document": snapshot.document, "schema_version": snapshot.document.get("schema_version"), "file_version": snapshot.file_version, "last_modified": snapshot.last_modified, "exists": snapshot.exists, "valid": snapshot.valid, "error": snapshot.error, "backup_exists": backup_exists, "included": self.configuration_sources.get("manager_include", False), "active_mode": self._active_mode(self.selected_bridge()), "fingerprint": self.fingerprint, "is_applied": False}

    async def async_yaml_status(self) -> dict[str, Any]:
        async with self._refresh_lock:
            snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
            backup = await self.hass.async_add_executor_job(self.yaml_store.backup_path.is_file)
            fingerprint = build_fingerprint(self.bridges, self.inventory, snapshot.document)
            self.yaml_snapshot, self.fingerprint = snapshot, fingerprint
            return self._yaml_status_payload(snapshot, backup)

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

    async def async_save_draft(self, document: Any, expected_file_version: str | None, expected_fingerprint: str | None) -> dict[str, Any]:
        """Merge the selected bridge draft, retaining all other bridge drafts."""
        async with self._refresh_lock:
            if self.configuration_sources.get("manager_include"):
                raise YamlWriteError("Die Entwurfsdatei ist als native HomeKit-Konfigurationsquelle eingebunden und wird nicht überschrieben.")
            if expected_fingerprint and expected_fingerprint != self.fingerprint:
                raise YamlVersionConflict("Live-Konfiguration oder Inventar wurde seit der Vorschau verändert")
            validated = self.validate_draft(document)
            bridge = self.selected_bridge()
            if bridge is None or set(validated["document"]["bridges"]) != {bridge["entry_id"]}:
                raise YamlValidationError("Ein Entwurf muss genau die ausgewählte Bridge betreffen")
            current = await self.hass.async_add_executor_job(self.yaml_store.load)
            merged = {"schema_version": 1, "bridges": current.document["bridges"] | validated["document"]["bridges"]}
            try:
                snapshot = await self.hass.async_add_executor_job(self.yaml_store.save, merged, expected_file_version)
            except OSError as err:
                raise YamlWriteError("Entwurf konnte nicht sicher gespeichert werden") from err
            fingerprint = build_fingerprint(self.bridges, self.inventory, snapshot.document)
            history = (self.history_entries + [make_history_entry(snapshot.document, fingerprint=fingerprint, bridge_id=bridge["entry_id"])])[-50:]
            self.yaml_snapshot, self.fingerprint = snapshot, fingerprint
            history_error = None
            try:
                await self.history_store.async_save(history)
                self.history_entries = history
            except Exception:
                history_error = "Entwurf gespeichert; die Historie konnte nicht dauerhaft ergänzt werden."
                _LOGGER.exception("HomeKit Manager: Entwurf gespeichert, Historie fehlgeschlagen")
            _LOGGER.info("HomeKit-Manager-Entwurf gespeichert: file_version=%s", snapshot.file_version)
            return self._yaml_status_payload(snapshot, current.exists) | {"warnings": validated["warnings"], "history_error": history_error}

    def prepare_options_diff(self, document: Any) -> dict[str, Any]:
        """Prepare, but never apply, the native HomeKit options diff."""
        validated = self.validate_draft(document)
        bridge = self.selected_bridge()
        if bridge is None:
            raise ValueError("Die Ziel-Bridge ist nicht eindeutig")
        diff = build_options_diff(bridge, validated["document"], self.inventory)
        return diff.as_dict()

    async def async_apply_options_diff(self, document: Any, expected_fingerprint: str | None, request_id: str | None = None) -> dict[str, Any]:
        """Hard lock before validation, status mutation or native entry access."""
        raise HomeKitWriteDisabled(WRITE_LOCK_REASON)

    async def async_plan_operation(self, document: Any, expected_fingerprint: str | None, entry_id: str) -> dict[str, Any]:
        if not expected_fingerprint or expected_fingerprint != self.fingerprint or self.last_error:
            raise ValueError("Inventar-Fingerprint ist veraltet oder unbekannt")
        bridge = self.selected_bridge()
        if bridge is None or bridge.get("entry_id") != entry_id:
            raise ValueError("Ziel-Bridge stimmt nicht mit der Auswahl überein")
        validated = self.validate_draft(document)
        result = await self.operation_service.plan_filter(entry_id=entry_id, bridge=bridge,
                                                          document=validated["document"], inventory=self.inventory)
        self.operation_policy = result["operation_policy"]
        return result

    async def async_apply_operation(self, operation_id: str, entry_id: str, source_revision: str,
                                    expected_fingerprint: str, confirmed_operation_id: str) -> dict[str, Any]:
        bridge = self.selected_bridge()
        if self.last_error or not bridge or bridge.get("entry_id") != entry_id or self.fingerprint != expected_fingerprint:
            raise HomeKitWriteBlocked("Bridge-Kontext oder Inventar-Fingerprint wurde geändert")
        policy = await self.operation_service.authority_status(entry_id, bridge.get("source", ""))
        if not policy["enabled"]:
            raise HomeKitWriteDisabled(policy["reason"])
        return await self.operation_service.apply(operation_id, entry_id=entry_id,
                                                  expected_revision=source_revision,
                                                  confirmed_operation_id=confirmed_operation_id, admin=True)

    async def async_enable_test_write_mode(self, entry_id: str, expected_fingerprint: str,
                                           confirmed_entry_id: str) -> dict[str, Any]:
        """Admin WebSocket activation; the authority vanishes on Core restart."""
        from .write_test_mode import TestModeBlocked

        bridge = self.selected_bridge()
        if (self.last_error or self.fingerprint != expected_fingerprint or bridge is None
                or bridge.get("entry_id") != entry_id or bridge.get("source") != "user"
                or bridge.get("mode") != "bridge" or bridge.get("state") != "loaded"):
            raise TestModeBlocked("Bridge-Kontext oder Inventarstand ist nicht mehr aktuell")
        records = await self.operation_service._records()
        if any(isinstance(item, dict) and item.get("entry_id") == entry_id
               and item.get("state") in {"applying", "unknown_outcome"}
               for item in records.values()):
            raise TestModeBlocked("Ungeklärten früheren Vorgang zuerst lesend abgleichen")
        authority = self.operation_service.test_write_mode.enable(self.hass, entry_id, confirmed_entry_id)
        self.operation_policy = await self.operation_service.authority_status(entry_id, "user")
        self.hass.bus.async_fire("homekit_manager_updated", {"revision": self.refresh_count})
        return {"enabled": True, "entry_id": entry_id, "expires_at": authority.expires_at.isoformat(),
                "persistent": False, "duration_minutes": 60}

    async def async_disable_test_write_mode(self) -> dict[str, Any]:
        """Revoke immediately; an in-flight writer rechecks before mutation."""
        self.operation_service.test_write_mode.disable()
        bridge = self.selected_bridge()
        self.operation_policy = (await self.operation_service.authority_status(
            bridge["entry_id"], bridge["source"]) if bridge else
            {"enabled": False, "reason": "Keine Bridge ausgewählt", "automatic_retry": False})
        self.hass.bus.async_fire("homekit_manager_updated", {"revision": self.refresh_count})
        return {"enabled": False, "persistent": False}

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
        self.operation_service.test_write_mode.disable()
        self._stopping = True
        self._refresh_pending = False
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            await asyncio.gather(self._refresh_task, return_exceptions=True)
            self._refresh_task = None
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

