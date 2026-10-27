"""Read-only reconciliation of entity device references and the native list."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping


def _ids(items: Any) -> set[str]:
    if isinstance(items, Mapping):
        return set(items)
    return {item.id for item in items} if items is not None else set()


def reconcile_devices(inventory: Iterable[Mapping[str, Any]], registry: Any) -> dict[str, Any]:
    """Compare like-for-like IDs without claiming the native UI's active filters."""
    by_status: dict[str, set[str]] = defaultdict(set)
    for item in inventory:
        if device_id := item.get("device_id"):
            by_status[item.get("device_registry_status", "unknown")].add(device_id)
    referenced = set().union(*by_status.values()) if by_status else set()
    if isinstance(registry, Mapping):
        main = _ids(registry.get("devices", registry))
        child = _ids(registry.get("child_devices"))
        enumerated = True
    elif registry is not None and hasattr(registry, "devices"):
        main = _ids(registry.devices)
        child = _ids(getattr(registry, "child_devices", None))
        enumerated = True
    else:
        main, child, enumerated = set(), set(), False
    native = main | child
    # A composite ID may resolve through async_get(), but is not enumerable.
    return {
        "referenced_device_count": len(referenced),
        "registered_referenced_device_count": len(referenced & native) if enumerated else None,
        "native_registry_device_count": len(native) if enumerated else None,
        "native_registry_devices_without_inventory": len(native - referenced) if enumerated else None,
        "composite_reference_ids": sorted(by_status["composite"]),
        "missing_reference_ids": sorted(by_status["missing"]),
        "unlisted_reference_ids": sorted(referenced - native) if enumerated else [],
        "registry_enumerated": enumerated,
        "comparison_note": "Die native UI kann zusätzliche Such-, Integrations- und Anzeigefilter anwenden.",
    }
