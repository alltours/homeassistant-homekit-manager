"""Diff preparation and an explicitly isolated native Core options adapter.

The coordinator rejects production writes in 0.9.24. This module rejects
allow_production=True independently. Only an explicitly enabled test fixture
can exercise ConfigEntry options; it cannot establish Apple Home compatibility.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .change_planner import plan_changes
from .const import SUPPORTED_CORE_VERSION
from .filtering import evaluate_filter
from .safety import WRITE_LOCK_REASON


class HomeKitWriteError(Exception):
    """Base class for write preparation errors."""


class HomeKitWriteDisabled(HomeKitWriteError):
    """Production HomeKit application is disabled."""


class HomeKitWriteBlocked(HomeKitWriteError):
    """The proposed diff is not provably safe."""


class HomeKitActivationUnknown(HomeKitWriteError):
    """The options may be saved, but activation cannot be confirmed."""


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
ACTIVATION_TIMEOUT = 30.0


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
    if set(current) - set(_FILTER_LIST_KEYS):
        raise HomeKitWriteBlocked("Unbekannte Filterfelder dürfen nicht geschrieben werden")
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


def _unlisted_entity_default(config: Mapping[str, Any]) -> bool:
    """Core 2026.10.4's selection of an entity matching no listed rule.

    Entity-only edits must not switch the default for unobserved entities.
    Inventory comparison alone cannot detect that future or unloaded entities
    would suddenly be published after a filter-case transition.
    """
    has_include = any(config.get(key) for key in ("include_entities", "include_domains", "include_entity_globs"))
    has_exclude = any(config.get(key) for key in ("exclude_entities", "exclude_domains", "exclude_entity_globs"))
    if not has_include:
        return True
    if not has_exclude:
        return False
    if config.get("include_domains") or config.get("include_entity_globs"):
        return False
    if config.get("exclude_domains") or config.get("exclude_entity_globs"):
        return True
    return False


def _verify_scope(before: Mapping[str, Any], after: Mapping[str, Any], inventory: list[Mapping[str, Any]], desired: Mapping[str, str]) -> None:
    """Ensure non-targeted entities keep the exact effective filter result."""
    if _unlisted_entity_default(before) != _unlisted_entity_default(after):
        raise HomeKitWriteBlocked("Filteränderung würde die Standardauswahl unbekannter Entitäten verändern")
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
    """Disabled for production; explicit isolated tests can exercise Core options.

    The retained allow_production argument deliberately rejects former callers.
    No normal coordinator endpoint enables this test adapter in 0.9.24.
    """

    def __init__(self, hass: Any, *, test_environment: bool = False, apply_enabled: bool = False, allow_production: bool = False):
        self.hass = hass
        self.test_environment = test_environment
        self.apply_enabled = bool(apply_enabled)
        self.allow_production = bool(allow_production)

    async def async_apply(self, diff: OptionsDiff) -> dict[str, Any]:
        """Exercise only explicitly enabled isolated fixtures."""
        if self.allow_production or not (self.test_environment and self.apply_enabled):
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        if not isinstance(diff, OptionsDiff):
            raise HomeKitWriteBlocked("Ungültiger Options-Diff")
        if not diff.changed_keys:
            raise HomeKitWriteBlocked("Options-Diff enthält keine Änderung")
        from homeassistant.const import __version__
        from homeassistant.config_entries import SOURCE_USER
        if __version__ != SUPPORTED_CORE_VERSION:
            raise HomeKitWriteBlocked(
                f"Core-Version {__version__} wird für den isolierten Adapter nicht unterstützt"
            )
        entry = self.hass.config_entries.async_get_entry(diff.entry_id)
        if entry is None or getattr(entry, "domain", None) != "homekit":
            raise HomeKitWriteBlocked("HomeKit-Config-Entry nicht gefunden")
        if getattr(entry, "source", None) != SOURCE_USER:
            raise HomeKitWriteBlocked(
                "Nur reguläre HomeKit-Config-Entries vom Typ SOURCE_USER werden unterstützt"
            )
        allowed = {"filter", "entity_config", "homekit_mode", "devices"}
        if any(key not in allowed for key in diff.changed_keys):
            raise HomeKitWriteBlocked("Options-Diff enthält nicht freigegebene Schlüssel")
        lock = _locks.setdefault(diff.entry_id, asyncio.Lock())
        async with lock:
            current_options = dict(entry.options)
            current_data = dict(entry.data)
            for key in diff.changed_keys:
                current_value = current_options.get(key, current_data.get(key))
                if current_value != diff.before.get(key):
                    raise HomeKitWriteBlocked("HomeKit-Config-Entry wurde seit der Vorschau verändert")
            next_options = dict(current_options)
            for key in diff.changed_keys:
                next_options[key] = copy.deepcopy(diff.after[key])
            self.hass.config_entries.async_update_entry(entry, options=next_options)
            if hasattr(self.hass, "async_block_till_done"):
                try:
                    await asyncio.wait_for(
                        self.hass.async_block_till_done(), ACTIVATION_TIMEOUT
                    )
                except asyncio.TimeoutError as err:
                    raise HomeKitActivationUnknown(
                        "Aktivierung wurde nicht innerhalb des Zeitlimits bestätigt"
                    ) from err
            # Check Core's persisted entry view after its update listener has
            # run.  A successful call alone does not prove the intended value.
            observed = self.hass.config_entries.async_get_entry(diff.entry_id)
            if observed is None or dict(observed.data) != current_data:
                raise HomeKitActivationUnknown("Entry-Identität oder data wurden während Apply verändert")
            for key in diff.changed_keys:
                if dict(observed.options).get(key) != diff.after.get(key):
                    raise HomeKitActivationUnknown("Gespeicherte HomeKit-Optionen weichen vom Plan ab")
            entry = observed
        state = getattr(getattr(entry, "state", None), "value", getattr(entry, "state", None))
        if state != "loaded":
            reason = getattr(entry, "reason", None)
            detail = f" ({reason})" if reason else ""
            raise HomeKitWriteBlocked(
                "HomeKit-Bridge wurde nach der Optionsänderung nicht erfolgreich aktiviert"
                + detail
            )
        return {
            "applied": True,
            "options_saved": True,
            "activation": "isolated_options_adapter",
            "production_verified": False,
            "activation_status": "active" if state == "loaded" else "unknown",
            "entry_id": diff.entry_id,
            "apply_enabled": True,
            "core_version": __version__,
        }
