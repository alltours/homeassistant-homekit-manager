"""Read-only diagnostics for the active native HomeKit runtime.

Home Assistant does not expose a stable public Entity -> HAP mapping API.  The
adapter therefore uses feature detection and never calls lifecycle methods or
touches HAP persistence.  It returns partial evidence instead of turning an
ambiguous mapping into a false negative.
"""
from __future__ import annotations

from hashlib import sha256
import json
import logging
from typing import Any, Iterable, Mapping


_LOGGER = logging.getLogger(__name__)

RUNTIME_STATES = frozenset({
    "published_verified",
    "not_published_verified",
    "unknown",
    "unsupported",
    "mapping_ambiguous",
})


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _items(value: Any) -> list[Any] | None:
    if isinstance(value, Mapping):
        return list(value.items())
    if isinstance(value, (list, tuple)):
        return [(index, item) for index, item in enumerate(value)]
    return None


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()[:20]


def _safe_type(obj: Any, *keys: str) -> str | None:
    for key in keys:
        value = _value(obj, key)
        if isinstance(value, str) and value:
            return value
    name = getattr(obj, "__class__", type(obj)).__name__
    return name if name not in {"dict", "list", "tuple"} else None


def _service_details(service: Any) -> tuple[dict[str, Any], int, list[str], bool]:
    characteristics = _items(_value(service, "characteristics"))
    characteristic_types: list[str] = []
    characteristic_iids: list[Any] = []
    if characteristics is None:
        complete = False
        characteristics = []
    else:
        complete = True
        for _, characteristic in characteristics:
            characteristic_types.append(_safe_type(characteristic, "characteristic_type", "type") or "unknown")
            iid = _value(characteristic, "iid")
            if iid is not None:
                characteristic_iids.append(iid)
    iid = _value(service, "iid")
    iid_values = [iid, *characteristic_iids]
    detail = {
        "type": _safe_type(service, "service_type", "type") or "unknown",
        "display_name": _value(service, "display_name") or _value(service, "name"),
        "characteristic_types": sorted(characteristic_types),
        "characteristic_count": len(characteristic_types),
        "iid_fingerprint": _fingerprint(iid_values) if iid_values else None,
    }
    return detail, len(characteristic_types), characteristic_types, complete


def diagnose_runtime(
    hass: Any,
    entry: Any,
    inventory: Iterable[Mapping[str, Any]] | Iterable[str],
) -> dict[str, Any]:
    """Inspect the active bridge without allocating or mutating HAP objects."""
    inventory_items = list(inventory)
    inventory_ids = {
        item.get("entity_id") if isinstance(item, Mapping) else item
        for item in inventory_items
    }
    inventory_ids = {entity_id for entity_id in inventory_ids if isinstance(entity_id, str)}
    result: dict[str, Any] = {
        "state": "unknown",
        "completeness": "unknown",
        "source": "homeassistant.runtime_data.homekit.bridge",
        "reason": "Die laufende HAP-Zuordnung ist nicht lesbar.",
        "entry_id": getattr(entry, "entry_id", None),
        "accessory_count": None,
        "mapped_accessory_count": 0,
        "ambiguous_accessory_count": 0,
        "service_count": None,
        "characteristic_count": None,
        "accessories": [],
        "entity_status": {},
    }
    runtime_data = getattr(entry, "runtime_data", None)
    homekit = getattr(runtime_data, "homekit", None)
    bridge = getattr(homekit, "bridge", None)
    driver = getattr(homekit, "driver", None)
    accessories = _items(getattr(bridge, "accessories", None))
    if homekit is None or bridge is None or accessories is None:
        result["reason"] = "Core stellt keine vollständige laufende Bridge-Accessory-Sammlung bereit."
        result["entity_status"] = {entity_id: "unknown" for entity_id in sorted(inventory_ids)}
        return result

    # Core's HAP accessory objects normally expose ``entity_id``.  Some Core
    # versions/ accessory implementations only expose the AID, however, while
    # the persistent AID store remains the authoritative entity mapping.  Use
    # that store as a read-only fallback.  Calling the allocation lookup does
    # not allocate, save, initialize, or otherwise mutate HAP state.
    aid_to_entity: dict[str, str] = {}
    aid_collisions: set[str] = set()
    aid_storage = getattr(homekit, "aid_storage", None)
    aid_lookup = getattr(aid_storage, "get_allocated_aid_for_entity_id", None)
    if callable(aid_lookup):
        for entity_id in sorted(inventory_ids):
            try:
                aid = aid_lookup(entity_id)
            except Exception:  # pragma: no cover - defensive Core adapter boundary
                _LOGGER.debug("AID lookup failed for %s", entity_id, exc_info=True)
                continue
            if aid is None:
                continue
            aid_key = str(aid)
            previous = aid_to_entity.get(aid_key)
            if previous is not None and previous != entity_id:
                aid_collisions.add(aid_key)
            else:
                aid_to_entity[aid_key] = entity_id

    mapped: set[str] = set()
    ambiguous: list[dict[str, Any]] = []
    accessory_rows: list[dict[str, Any]] = []
    service_count = 0
    characteristic_count = 0
    services_complete = True
    for key, accessory in sorted(accessories, key=lambda item: str(item[0])):
        raw_entity_id = _value(accessory, "entity_id")
        aid = _value(accessory, "aid", key)
        aid_key = str(aid) if aid is not None else None
        mapped_entity_id = aid_to_entity.get(aid_key) if aid_key not in aid_collisions else None
        entity_id = raw_entity_id if isinstance(raw_entity_id, str) else mapped_entity_id
        mapping_source = "accessory.entity_id" if isinstance(raw_entity_id, str) else (
            "aid_storage" if mapped_entity_id else "unresolved"
        )
        if isinstance(raw_entity_id, str) and mapped_entity_id and raw_entity_id != mapped_entity_id:
            mapping_source = "mapping_ambiguous"
        services = _items(_value(accessory, "services"))
        if services is None:
            services_complete = False
            services = []
        service_rows: list[dict[str, Any]] = []
        for _, service in services:
            detail, chars, _, complete = _service_details(service)
            service_rows.append(detail)
            service_count += 1
            characteristic_count += chars
            services_complete = services_complete and complete
        row = {
            "accessory_id_fingerprint": _fingerprint({"entry_id": getattr(entry, "entry_id", None), "aid": key}),
            "entity_id": entity_id if isinstance(entity_id, str) else None,
            "mapping_source": mapping_source,
            "name": _value(accessory, "display_name") or _value(accessory, "name"),
            "category": _value(accessory, "category"),
            "services": service_rows,
            "service_count": len(service_rows),
            "characteristic_count": sum(item["characteristic_count"] for item in service_rows),
        }
        if (mapping_source == "mapping_ambiguous" or not isinstance(entity_id, str)
                or entity_id not in inventory_ids or entity_id in mapped):
            ambiguous.append(row)
        else:
            mapped.add(entity_id)
        accessory_rows.append(row)

    complete_mapping = not ambiguous
    state = "verified" if complete_mapping else "partial"
    if not accessory_rows:
        state = "verified"
    result.update({
        "state": state,
        "completeness": "verified" if complete_mapping and services_complete else "partial",
        "reason": "Alle laufenden HAP-Accessories eindeutig Entity-IDs zugeordnet."
        if complete_mapping else "Ein Teil der laufenden HAP-Accessories ist keiner eindeutigen Entity-ID zugeordnet.",
        "accessory_count": len(accessory_rows),
        "mapped_accessory_count": len(mapped),
        "ambiguous_accessory_count": len(ambiguous),
        "service_count": service_count if services_complete else None,
        "characteristic_count": characteristic_count if services_complete else None,
        "accessories": accessory_rows,
        "ambiguous_accessories": ambiguous,
        "driver_loaded": driver is not None,
    })
    if complete_mapping:
        result["entity_status"] = {
            entity_id: "published_verified" if entity_id in mapped else "not_published_verified"
            for entity_id in sorted(inventory_ids)
        }
    else:
        result["entity_status"] = {
            entity_id: "published_verified" if entity_id in mapped else "unknown"
            for entity_id in sorted(inventory_ids)
        }
    compatibility_by_entity = {
        item.get("entity_id"): item.get("compatibility", {}).get("status")
        for item in inventory_items
        if isinstance(item, Mapping) and isinstance(item.get("entity_id"), str)
    }
    result["entity_status"] = {
        entity_id: (
            "unsupported"
            if compatibility_by_entity.get(entity_id) == "unsupported"
            else status
        )
        for entity_id, status in result["entity_status"].items()
    }
    return result


def runtime_publication_summary(diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the legacy reconciliation contract while exposing richer evidence."""
    statuses = diagnosis.get("entity_status", {})
    published = sorted(entity_id for entity_id, state in statuses.items() if state == "published_verified")
    return {
        "state": "verified" if diagnosis.get("completeness") == "verified" else "unknown",
        "entity_ids": published,
        "entity_count": len(published),
        "reason": diagnosis.get("reason"),
        "diagnosis_state": diagnosis.get("state"),
        "completeness": diagnosis.get("completeness"),
        "accessory_count": diagnosis.get("accessory_count"),
        "mapped_accessory_count": diagnosis.get("mapped_accessory_count", 0),
        "ambiguous_accessory_count": diagnosis.get("ambiguous_accessory_count", 0),
        "service_count": diagnosis.get("service_count"),
        "characteristic_count": diagnosis.get("characteristic_count"),
    }
