"""Pure aggregation helpers for device and area management."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any


def _device_key(item: dict[str, Any]) -> str | None:
    return item.get("device_id") or None


def build_device_views(entities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate the entity inventory into stable, read-only device views."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        device_id = _device_key(entity)
        if device_id:
            grouped[device_id].append(entity)

    result = []
    for device_id, members in grouped.items():
        members = sorted(members, key=lambda item: item.get("entity_id", ""))
        compatible = sum(item.get("compatibility", {}).get("status") == "supported" for item in members)
        configured = sum(item.get("homekit", {}).get("configured_by_filter") is True for item in members)
        result.append({
            "device_id": device_id,
            "name": next((item.get("device_name") for item in members if item.get("device_name")), device_id),
            "area_id": next((item.get("area_id") for item in members if item.get("area_id")), None),
            "area_name": next((item.get("area_name") for item in members if item.get("area_name")), None),
            "entity_ids": [item["entity_id"] for item in members],
            "entity_count": len(members),
            "available_count": sum(bool(item.get("available")) for item in members),
            "compatible_count": compatible,
            "configured_count": configured,
            "unavailable_count": sum(not item.get("available") for item in members),
            "conditional_count": sum(item.get("compatibility", {}).get("status") == "conditionally_supported" for item in members),
            "unknown_count": sum(item.get("homekit", {}).get("configured_by_filter") is None for item in members),
            "excluded_count": sum(item.get("homekit", {}).get("configured_by_filter") is False for item in members),
            "unassigned_entity_count": sum(not item.get("device_id") for item in members),
            "integrations": sorted({item.get("integration_domain") for item in members if item.get("integration_domain")}),
        })
    return sorted(result, key=lambda item: (str(item.get("name", "")).casefold(), item["device_id"]))


def build_area_views(entities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate the entity inventory into stable, read-only area views."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    without_area: list[dict[str, Any]] = []
    for entity in entities:
        area_id = entity.get("area_id")
        if area_id:
            grouped[area_id].append(entity)
        else:
            without_area.append(entity)

    result = []
    for area_id, members in grouped.items():
        members = sorted(members, key=lambda item: item.get("entity_id", ""))
        result.append({
            "area_id": area_id,
            "name": next((item.get("area_name") for item in members if item.get("area_name")), area_id),
            "device_ids": sorted({item["device_id"] for item in members if item.get("device_id")}),
            "entity_ids": [item["entity_id"] for item in members],
            "device_count": len({item["device_id"] for item in members if item.get("device_id")}),
            "entity_count": len(members),
            "compatible_count": sum(item.get("compatibility", {}).get("status") == "supported" for item in members),
            "configured_count": sum(item.get("homekit", {}).get("configured_by_filter") is True for item in members),
            "unavailable_count": sum(not item.get("available") for item in members),
            "conditional_count": sum(item.get("compatibility", {}).get("status") == "conditionally_supported" for item in members),
            "unknown_count": sum(item.get("homekit", {}).get("configured_by_filter") is None for item in members),
            "excluded_count": sum(item.get("homekit", {}).get("configured_by_filter") is False for item in members),
            "unassigned_entity_count": sum(not item.get("device_id") for item in members),
        })
    if without_area:
        result.append({
            "area_id": None,
            "name": "Kein Bereich",
            "device_ids": sorted({item["device_id"] for item in without_area if item.get("device_id")}),
            "entity_ids": [item["entity_id"] for item in sorted(without_area, key=lambda item: item.get("entity_id", ""))],
            "device_count": len({item["device_id"] for item in without_area if item.get("device_id")}),
            "entity_count": len(without_area),
            "compatible_count": sum(item.get("compatibility", {}).get("status") == "supported" for item in without_area),
            "configured_count": sum(item.get("homekit", {}).get("configured_by_filter") is True for item in without_area),
            "unavailable_count": sum(not item.get("available") for item in without_area),
            "conditional_count": sum(item.get("compatibility", {}).get("status") == "conditionally_supported" for item in without_area),
            "unknown_count": sum(item.get("homekit", {}).get("configured_by_filter") is None for item in without_area),
            "excluded_count": sum(item.get("homekit", {}).get("configured_by_filter") is False for item in without_area),
            "unassigned_entity_count": sum(not item.get("device_id") for item in without_area),
        })
    return sorted(result, key=lambda item: str(item.get("name", "")).casefold())
