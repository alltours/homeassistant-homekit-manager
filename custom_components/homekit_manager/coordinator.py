"""Event-driven read-only coordinator."""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
from typing import Any
from homeassistant.core import callback
from .compatibility import classify_entity
from .homekit_reader import read_homekit_entries
from .inventory import build_inventory
from .change_planner import plan_changes
from .fingerprint import build_fingerprint
from .homekit_writer import OptionsDiff, build_options_diff
from .reconcile import reconcile_desired_state
from .exporter import export_desired_state
from .yaml_store import (
    YamlSnapshot,
    YamlStore,
    YamlValidationError,
    YamlVersionConflict,
    empty_document,
)

_LOGGER = logging.getLogger(__name__)

class HomeKitManagerCoordinator:
    """Build and cache an inventory; never writes HomeKit configuration."""
    def __init__(self, hass):
        self.hass = hass
        self.inventory: list[dict[str, Any]] = []
        self.bridges: list[dict[str, Any]] = []
        self.last_error: str | None = None
        self.fingerprint: str | None = None
        config_path = getattr(getattr(hass, "config", None), "path", None)
        yaml_path = config_path("homekit_manager.yaml") if callable(config_path) else "/config/homekit_manager.yaml"
        self.yaml_store = YamlStore(yaml_path)
        # File I/O is intentionally deferred to the executor.  The coordinator
        # is constructed during Home Assistant setup, which runs on the event
        # loop and must not perform synchronous filesystem reads.
        self.yaml_snapshot = YamlSnapshot(empty_document(), None, False, True, None, None)
        self._unsubscribers = []
        self._refresh_task: asyncio.Task | None = None
        self._subscribe_events()

    async def async_initialize(self) -> None:
        """Load the desired-state snapshot without blocking the event loop."""
        self.yaml_snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)

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
            bridge_filter = bridges[0].filter if len(bridges) == 1 else None
            self.inventory = []
            from .filtering import evaluate_filter
            from .filtering import build_core_filter
            core_filter = build_core_filter(bridge_filter)
            for record in records:
                item = record.as_dict()
                item["compatibility"] = classify_entity(record).as_dict()
                item["homekit"] = {"configured_by_filter": None, "filter_reason": "filter_unavailable", "published": "unknown", "apple_home_visible": "unknown"}
                if bridge_filter is not None:
                    item["homekit"].update(evaluate_filter(record.entity_id, record.entity_category, record.hidden_by, bridge_filter, core_filter).as_dict())
                self.inventory.append(item)
            self.bridges = [bridge.as_dict() for bridge in bridges]
            self.yaml_snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
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
            "fingerprint": self.fingerprint,
            "yaml_valid": self.yaml_snapshot.valid,
            "yaml_exists": self.yaml_snapshot.exists,
            "yaml_file_version": self.yaml_snapshot.file_version,
            "last_error": self.last_error,
        }

    def yaml_status(self) -> dict[str, Any]:
        snapshot = self.yaml_store.load()
        self.yaml_snapshot = snapshot
        return {"document": snapshot.document, "schema_version": snapshot.document.get("schema_version"), "file_version": snapshot.file_version, "last_modified": snapshot.last_modified, "exists": snapshot.exists, "valid": snapshot.valid, "error": snapshot.error, "is_applied": False}

    async def async_yaml_status(self) -> dict[str, Any]:
        """Return YAML status after reading the file in the executor."""
        snapshot = await self.hass.async_add_executor_job(self.yaml_store.load)
        self.yaml_snapshot = snapshot
        return {"document": snapshot.document, "schema_version": snapshot.document.get("schema_version"), "file_version": snapshot.file_version, "last_modified": snapshot.last_modified, "exists": snapshot.exists, "valid": snapshot.valid, "error": snapshot.error, "is_applied": False}

    def validate_draft(self, document: Any) -> dict[str, Any]:
        from .yaml_store import validate_document
        normalized = validate_document(document)
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
        entry_id = self.bridges[0].get("entry_id") if len(self.bridges) == 1 else None
        bridge = self.bridges[0] if len(self.bridges) == 1 else None
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
        _LOGGER.info(
            "HomeKit-Manager-Entwurf gespeichert: file_version=%s entities=%d",
            snapshot.file_version,
            sum(len(bridge["entities"]) for bridge in validated["document"]["bridges"].values()),
        )
        return await self.async_yaml_status() | {"fingerprint": self.fingerprint, "warnings": validated["warnings"]}

    def prepare_options_diff(self, document: Any) -> dict[str, Any]:
        """Prepare, but never apply, the native HomeKit options diff."""
        validated = self.validate_draft(document)
        if len(self.bridges) != 1:
            raise ValueError("Die Ziel-Bridge ist nicht eindeutig")
        diff = build_options_diff(self.bridges[0], validated["document"], self.inventory)
        return diff.as_dict()

    def reconcile(self, document: Any, baseline_fingerprint: str | None = None) -> dict[str, Any]:
        validated = self.validate_draft(document)
        if len(self.bridges) != 1:
            raise ValueError("Die Ziel-Bridge ist nicht eindeutig")
        return reconcile_desired_state(validated["document"], self.bridges[0]["entry_id"], self.inventory, baseline_fingerprint=baseline_fingerprint, current_fingerprint=self.fingerprint)

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

