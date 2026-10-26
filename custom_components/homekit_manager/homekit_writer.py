"""Phase 4B write preparation with a hard production safety gate.

The HomeKit OptionsFlow is a user-facing flow, not a stable automation API
for submitting an arbitrary complete option document.  This module therefore
computes and validates the minimal diff, but deliberately refuses to apply it
from the custom integration.  A future isolated test harness may consume the
prepared diff through an explicit test adapter.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .change_planner import plan_changes
from .filtering import evaluate_filter


class HomeKitWriteError(Exception):
    """Base class for write preparation errors."""


class HomeKitWriteDisabled(HomeKitWriteError):
    """Applying HomeKit changes is intentionally disabled in Phase 4B."""


class HomeKitWriteBlocked(HomeKitWriteError):
    """The proposed diff is not provably safe."""


@dataclass(frozen=True)
class OptionsDiff:
    entry_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    changed_keys: tuple[str, ...]
    changed_entities: tuple[str, ...]
    plan: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "before": copy.deepcopy(self.before),
            "after": copy.deepcopy(self.after),
            "changed_keys": list(self.changed_keys),
            "changed_entities": list(self.changed_entities),
            "plan": copy.deepcopy(self.plan),
            "apply_enabled": False,
        }


_FILTER_LIST_KEYS = (
    "include_entities", "exclude_entities", "include_domains", "exclude_domains",
    "include_entity_globs", "exclude_entity_globs",
)
_locks: dict[str, asyncio.Lock] = {}


def _entry_options(bridge: Mapping[str, Any]) -> dict[str, Any]:
    data = bridge.get("data")
    options = bridge.get("options")
    if not isinstance(data, Mapping) or not isinstance(options, Mapping):
        raise HomeKitWriteBlocked("HomeKit-Optionen sind unbekannt")
    merged = copy.deepcopy(dict(data))
    merged.update(copy.deepcopy(dict(options)))
    return merged


def _candidate_filter(current: Mapping[str, Any], desired: Mapping[str, str]) -> dict[str, Any]:
    """Apply only explicit entity overrides while preserving every other rule."""
    result = {key: copy.deepcopy(value) for key, value in current.items()}
    for key in _FILTER_LIST_KEYS:
        result.setdefault(key, [])
        if not isinstance(result[key], list):
            raise HomeKitWriteBlocked(f"Filter-Schlüssel {key} ist nicht valide")
    includes = set(result["include_entities"])
    excludes = set(result["exclude_entities"])
    for entity_id, status in desired.items():
        if status == "include":
            excludes.discard(entity_id)
            includes.add(entity_id)
        elif status == "exclude":
            includes.discard(entity_id)
            excludes.add(entity_id)
    result["include_entities"] = sorted(includes)
    result["exclude_entities"] = sorted(excludes)
    return result


def _verify_scope(before: Mapping[str, Any], after: Mapping[str, Any], inventory: list[Mapping[str, Any]], desired: Mapping[str, str]) -> None:
    """Ensure non-targeted entities keep the exact effective filter result."""
    for item in inventory:
        entity_id = item.get("entity_id")
        if not entity_id or entity_id in desired:
            continue
        old = evaluate_filter(entity_id, item.get("entity_category"), item.get("hidden_by"), before).configured
        new = evaluate_filter(entity_id, item.get("entity_category"), item.get("hidden_by"), after).configured
        if old != new:
            raise HomeKitWriteBlocked(f"Filter-Diff verändert unbeabsichtigt {entity_id}")


def build_options_diff(
    bridge: Mapping[str, Any],
    desired_document: Mapping[str, Any],
    inventory: list[Mapping[str, Any]],
    *,
    core_options_validator: Callable[[dict[str, Any]], Any] | None = None,
) -> OptionsDiff:
    """Prepare a minimal options diff; never mutate the input bridge."""
    entry_id = bridge.get("entry_id")
    if not entry_id:
        raise HomeKitWriteBlocked("HomeKit-Config-Entry ist nicht eindeutig")
    options = _entry_options(bridge)
    current_filter = options.get("filter", bridge.get("filter"))
    if not isinstance(current_filter, Mapping):
        raise HomeKitWriteBlocked("HomeKit-Filter ist unbekannt")
    desired = dict(desired_document.get("bridges", {}).get(entry_id, {}).get("entities", {}))
    plan = plan_changes(dict(bridge) | {"filter": dict(current_filter)}, desired_document, inventory, entry_id)
    if plan["summary"]["blocked"]:
        raise HomeKitWriteBlocked("Änderungsplan ist blockiert")
    after = copy.deepcopy(options)
    after["filter"] = _candidate_filter(current_filter, desired)
    _verify_scope(current_filter, after["filter"], inventory, desired)
    if core_options_validator is not None:
        core_options_validator(copy.deepcopy(after))
    changed_keys = tuple(sorted(key for key in set(options) | set(after) if options.get(key) != after.get(key)))
    return OptionsDiff(entry_id, options, after, changed_keys, tuple(sorted(desired)), plan)


class HomeKitWriter:
    """Non-activatable writer facade for the Phase 4B safety boundary."""

    def __init__(self, hass: Any, *, test_environment: bool = False):
        self.hass = hass
        self.test_environment = test_environment

    async def async_apply(self, diff: OptionsDiff) -> dict[str, Any]:
        """Refuse application; no ConfigEntry or reload API is called."""
        raise HomeKitWriteDisabled(
            "HomeKit-Schreibpfad ist in Phase 4B gesperrt; nur isolierte Vorbereitung erlaubt"
        )
