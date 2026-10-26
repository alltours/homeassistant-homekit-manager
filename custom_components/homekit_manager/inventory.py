"""Pure inventory assembly from Home Assistant registries and states."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any, Mapping

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

@dataclass(frozen=True)
class InventoryEntity:
    entity_id: str
    name: str | None
    domain: str
    device_id: str | None
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
    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

def build_inventory(entity_registry: Any, device_registry: Any = None,
                    area_registry: Any = None,
                    states: Mapping[str, Any] | None = None) -> list[InventoryEntity]:
    """Build one record per registry entity, including entries without state."""
    state_map = states or {}
    areas = _value(area_registry, "areas", area_registry) or {}
    result: list[InventoryEntity] = []
    seen_entity_ids: set[str] = set()
    for entry in sorted(_items(entity_registry), key=lambda item: _value(item, "entity_id", "")):
        entity_id = _value(entry, "entity_id", "")
        if not entity_id or "." not in entity_id:
            continue
        seen_entity_ids.add(entity_id)
        domain = entity_id.split(".", 1)[0]
        device_id = _value(entry, "device_id")
        device = _lookup(device_registry, device_id)
        area_id = _value(entry, "area_id") or _value(device, "area_id")
        area = areas.get(area_id) if isinstance(areas, Mapping) else None
        state_obj = state_map.get(entity_id)
        state = _value(state_obj, "state")
        attributes = dict(_value(state_obj, "attributes", {}) or {})
        available = state not in (None, "unknown", "unavailable")
        name = _value(entry, "name") or _value(entry, "original_name") or attributes.get("friendly_name")
        result.append(InventoryEntity(
            entity_id=entity_id, name=name, domain=domain, device_id=device_id,
            device_name=_value(device, "name_by_user") or _value(device, "name"), area_id=area_id,
            area_name=_value(area, "name"), integration_domain=_value(entry, "platform"),
            device_class=_value(entry, "device_class") or _value(entry, "original_device_class") or attributes.get("device_class"),
            entity_category=_value(entry, "entity_category"), disabled_by=_value(entry, "disabled_by"),
            hidden_by=_value(entry, "hidden_by"), available=available, state=state,
            attributes=attributes, config_entry_id=_value(entry, "config_entry_id"),
        ))
    for entity_id, state_obj in state_map.items():
        if entity_id in seen_entity_ids or "." not in entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        attributes = dict(_value(state_obj, "attributes", {}) or {})
        state = _value(state_obj, "state")
        result.append(InventoryEntity(
            entity_id=entity_id,
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
        ))
    return sorted(result, key=lambda item: item.entity_id)

