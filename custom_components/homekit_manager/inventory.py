"""Pure inventory assembly from Home Assistant registries and states."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


def _value(obj: Any, key: str, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)

def _items(registry: Any):
    if registry is None:
        return []
    value = _value(registry, "entities", registry)
    return value.values() if isinstance(value, Mapping) else value

def _lookup(registry: Any, key: str):
    if registry is None or key is None:
        return None
    # Home Assistant's current DeviceRegistry exposes async_get() and stores
    # entries in an internal collection, not a public ``devices`` mapping.
    getter = getattr(registry, "async_get", None)
    if callable(getter):
        return getter(key)
    values = _value(registry, "devices", registry)
    return values.get(key) if isinstance(values, Mapping) else None

def _device_status(registry: Any, device_id: str | None, device: Any) -> str:
    """Distinguish a displayed registry device from a synthetic lookup result.

    Since Core 2026.8, async_get can synthesize a pre-split composite device
    that is absent from the native device list. A successful lookup alone is
    therefore insufficient evidence that a device is listed in the UI.
    """
    if not device_id:
        return "none"
    if registry is None:
        return "unknown"
    if device is None:
        return "missing"
    if _value(device, "is_composite_device", False):
        return "composite"
    if _value(device, "parent_device_id") is not None:
        return "child"
    return "main"

def _availability_status(entry: Any, device: Any, device_status: str, state: str | None) -> str:
    """Return one exclusive user-facing status, with evidence-first priority."""
    if _value(entry, "disabled_by") is not None or _value(device, "disabled_by") is not None:
        return "disabled"
    # An unresolved device reference is evidence about the registry, not
    # proof that the entity is orphaned. A valid runtime state can still exist.
    if state is None:
        return "no_state"
    if state == "unavailable":
        return "unavailable"
    if state == "unknown":
        return "unknown"
    return "available"

@dataclass(frozen=True)
class InventoryEntity:
    entity_id: str
    name: str | None
    domain: str
    device_id: str | None
    device_registry_status: str
    availability_status: str
    device_name: str | None
    area_id: str | None
    area_name: str | None
    integration_domain: str | None
    device_class: str | None
    entity_category: str | None
    disabled_by: str | None
    hidden_by: str | None
    available: bool
    state: str | None
    attributes: dict[str, Any]
    config_entry_id: str | None
    registry_entry_present: bool
    state_present: bool
    area_source: str
    device_disabled_by: str | None
    device_area_id: str | None = None
    device_area_name: str | None = None
    def as_dict(self) -> dict[str, Any]:
        # Only the attributes container may hold nested mutable values. Deep
        # copying every scalar through dataclasses.asdict dominated the measured
        # 1,172-entity projection, while a selective copy keeps snapshots safe.
        result = dict(vars(self))
        result["attributes"] = deepcopy(self.attributes)
        return result

def build_inventory(entity_registry: Any, device_registry: Any = None,
                    area_registry: Any = None,
                    states: Mapping[str, Any] | None = None) -> list[InventoryEntity]:
    """Build one record per registry entity, including entries without state."""
    state_map = states or {}
    areas = _value(area_registry, "areas", area_registry) or {}
    result: list[InventoryEntity] = []
    seen_entity_ids: set[str] = set()
    device_cache: dict[str, Any] = {}
    for entry in sorted(_items(entity_registry), key=lambda item: _value(item, "entity_id", "")):
        entity_id = _value(entry, "entity_id", "")
        if not entity_id or "." not in entity_id:
            continue
        seen_entity_ids.add(entity_id)
        domain = entity_id.split(".", 1)[0]
        device_id = _value(entry, "device_id")
        if device_id and device_id not in device_cache:
            device_cache[device_id] = _lookup(device_registry, device_id)
        device = device_cache.get(device_id)
        device_status = _device_status(device_registry, device_id, device)
        device_area_id = _value(device, "area_id")
        area_id = _value(entry, "area_id") or device_area_id
        area_source = "entity" if _value(entry, "area_id") else "device" if _value(device, "area_id") else "none"
        area = areas.get(area_id) if isinstance(areas, Mapping) else None
        device_area = areas.get(device_area_id) if isinstance(areas, Mapping) else None
        state_obj = state_map.get(entity_id)
        state = _value(state_obj, "state")
        attributes = dict(_value(state_obj, "attributes", {}) or {})
        availability_status = _availability_status(entry, device, device_status, state)
        available = availability_status == "available"
        # Match the name a user normally sees in HA: registry override first,
        # then the live friendly name, then the integration's original name.
        name = _value(entry, "name") or attributes.get("friendly_name") or _value(entry, "original_name")
        result.append(InventoryEntity(
            entity_id=entity_id, name=name, domain=domain, device_id=device_id,
            device_registry_status=device_status, availability_status=availability_status,
            device_name=_value(device, "name_by_user") or _value(device, "name"), area_id=area_id,
            area_name=_value(area, "name"), integration_domain=_value(entry, "platform"),
            device_class=_value(entry, "device_class") or _value(entry, "original_device_class") or attributes.get("device_class"),
            entity_category=_value(entry, "entity_category"), disabled_by=_value(entry, "disabled_by"),
            hidden_by=_value(entry, "hidden_by"), available=available, state=state,
            attributes=attributes, config_entry_id=_value(entry, "config_entry_id"),
            registry_entry_present=True, state_present=state_obj is not None,
            area_source=area_source, device_disabled_by=_value(device, "disabled_by"),
            device_area_id=device_area_id, device_area_name=_value(device_area, "name"),
        ))
    for entity_id, state_obj in state_map.items():
        if entity_id in seen_entity_ids or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        attributes = dict(_value(state_obj, "attributes", {}) or {})
        state = _value(state_obj, "state")
        result.append(InventoryEntity(
            entity_id=entity_id,
            device_registry_status="none",
            availability_status=_availability_status(None, None, "none", state),
            name=attributes.get("friendly_name"),
            domain=domain,
            device_id=None,
            device_name=None,
            area_id=None,
            area_name=None,
            integration_domain=None,
            device_class=attributes.get("device_class"),
            entity_category=None,
            disabled_by=None,
            hidden_by=None,
            available=state not in (None, "unknown", "unavailable"),
            state=state,
            attributes=attributes,
            config_entry_id=None,
            registry_entry_present=False, state_present=True, area_source="none",
            device_disabled_by=None,
        ))
    return sorted(result, key=lambda item: item.entity_id)

