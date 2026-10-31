"""Diff preparation and a tightly authorized native Core filter writer.

Production use requires a narrow authority plus a complete expected Entry revision.
The retained ``allow_production`` shortcut rejects legacy callers.
"""
from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .change_planner import plan_changes
from .const import NATIVE_FILTER_WRITE_CORE_VERSIONS
from .filtering import evaluate_filter
from .positive_list import PositiveListEvidence
from .safety import WRITE_LOCK_REASON
from .source_model import revision


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


def _has_broad_rules(config: Mapping[str, Any]) -> bool:
    """Return whether Core could select entities not named explicitly."""
    return any(config.get(key) for key in (
        "include_domains", "exclude_domains", "include_entity_globs", "exclude_entity_globs"
    )) or not config.get("include_entities")


def _explicit_hidden_override_allowed(item: Mapping[str, Any]) -> bool:
    """Allow only an enabled, supported, non-technical hidden entity.

    Home Assistant's native EntityFilter accepts an exact include override for
    a hidden registry entry. This exception is deliberately not generalized to
    disabled, categorized, unsupported or unknown entries.
    """
    return bool(
        item.get("hidden_by")
        and not item.get("disabled_by")
        and not item.get("device_disabled_by")
        and not item.get("entity_category")
        and (item.get("compatibility") or {}).get("status") == "supported"
        and item.get("registry_entry_present") is True
        and item.get("state_present") is True
    )


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


def _positive_list_filter(current: Mapping[str, Any], desired: Mapping[str, str],
                          evidence: PositiveListEvidence | None) -> dict[str, Any]:
    """Build a nonempty whitelist; broad source rules need live HAP proof."""
    if set(current) - set(_FILTER_LIST_KEYS):
        raise HomeKitWriteBlocked("Unbekannte HomeKit-Filterfelder verhindern die Positivliste")
    broad = _has_broad_rules(current)
    if broad and evidence is None:
        raise HomeKitWriteBlocked("Bestehender breiter Filter benötigt eine gesondert nachgewiesene Positivlistenmigration")
    includes = sorted(entity_id for entity_id, status in desired.items() if status == "include")
    if not includes:
        raise HomeKitWriteBlocked("Eine leere HomeKit-Positivliste würde in Core alle Entitäten einschließen")
    # Keep all Core filter keys explicit.  In particular, an empty mapping is
    # not a safe whitelist: Core treats an empty filter as "include all".
    return {
        "include_entities": includes,
        "exclude_entities": [],
        "include_domains": [],
        "exclude_domains": [],
        "include_entity_globs": [],
        "exclude_entity_globs": [],
    }


def _unlisted_entity_default(config: Mapping[str, Any]) -> bool:
    """Selection of an entity matching no listed rule on supported Core versions.

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
    return bool(config.get("exclude_domains") or config.get("exclude_entity_globs"))


def _verify_scope(before: Mapping[str, Any], after: Mapping[str, Any], inventory: list[Mapping[str, Any]], desired: Mapping[str, str], *, allow_default_change: bool = False) -> None:
    """Ensure non-targeted entities keep the exact effective filter result."""
    from homeassistant.helpers.entityfilter import FILTER_SCHEMA

    if not allow_default_change and _unlisted_entity_default(before) != _unlisted_entity_default(after):
        raise HomeKitWriteBlocked("Filteränderung würde die Standardauswahl unbekannter Entitäten verändern")
    try:
        old_filter, new_filter = FILTER_SCHEMA(dict(before)), FILTER_SCHEMA(dict(after))
    except Exception as err:
        raise HomeKitWriteBlocked("HomeKit-Core-Filter-Schema lehnt den Filter ab") from err
    for item in inventory:
        entity_id = item.get("entity_id")
        if not entity_id or entity_id in desired:
            continue
        old = evaluate_filter(entity_id, item.get("entity_category"), item.get("hidden_by"), before, old_filter).configured
        new = evaluate_filter(entity_id, item.get("entity_category"), item.get("hidden_by"), after, new_filter).configured
        if old != new:
            raise HomeKitWriteBlocked(f"Filter-Diff verändert unbeabsichtigt {entity_id}")


def build_options_diff(
    bridge: Mapping[str, Any],
    desired_document: Mapping[str, Any],
    inventory: list[Mapping[str, Any]],
    *,
    core_options_validator: Callable[[dict[str, Any]], Any] | None = None,
    migration_evidence: PositiveListEvidence | None = None,
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
    positive_list = desired_document.get("bridges", {}).get(entry_id, {}).get("policy") == "positive_list"
    if migration_evidence is not None:
        if not positive_list or desired_document["bridges"][entry_id].get("migration_acknowledged") is not True:
            raise HomeKitWriteBlocked("Positivlistenmigration benötigt eine ausdrückliche Migrationsbestätigung")
        observed_selected = {item["entity_id"] for item in inventory
                             if item.get("homekit", {}).get("configured_by_filter") is True}
        if observed_selected != migration_evidence.selected_ids:
            raise HomeKitWriteBlocked("Aktueller Core-Filter und Inventar stimmen für die Migration nicht überein")
        item_by_id = {item.get("entity_id"): item for item in inventory}
        unsafe_includes = {
            entity_id for entity_id, status in desired.items()
            if status == "include"
        } & migration_evidence.registry_blocked_ids
        unsafe_includes = {
            entity_id for entity_id in unsafe_includes
            if not _explicit_hidden_override_allowed(item_by_id.get(entity_id, {}))
        }
        if unsafe_includes:
            raise HomeKitWriteBlocked("Positivliste würde deaktivierte, kategorisierte oder nicht verifizierte Entitäten neu veröffentlichen: " + ", ".join(sorted(unsafe_includes)))
    plan = plan_changes(dict(bridge) | {"filter": dict(current_filter)}, desired_document, inventory, entry_id)
    if plan["summary"]["blocked"]:
        raise HomeKitWriteBlocked("Änderungsplan ist blockiert")
    after = copy.deepcopy(options)
    after["filter"] = (_positive_list_filter(current_filter, desired, migration_evidence) if positive_list
                       else _candidate_filter(current_filter, desired))
    scope_desired = desired
    if positive_list:
        scope_desired = desired | {
            item["entity_id"]: "exclude" for item in inventory
            if item.get("entity_id") not in desired and item.get("homekit", {}).get("configured_by_filter") is True
        }
    _verify_scope(current_filter, after["filter"], inventory, scope_desired,
                  allow_default_change=migration_evidence is not None)
    from homeassistant.helpers.entityfilter import FILTER_SCHEMA
    try:
        FILTER_SCHEMA(after["filter"])
    except Exception as err:
        raise HomeKitWriteBlocked("HomeKit-Core-Filter-Schema lehnt den Entwurf ab") from err
    if core_options_validator is not None:
        core_options_validator(copy.deepcopy(after))
    changed_keys = tuple(sorted(key for key in set(options) | set(after) if options.get(key) != after.get(key)))
    changed_entities = tuple(
        change["entity_id"] for change in plan["changes"]
        if change["action"] in {"add", "remove"}
    )
    if not changed_entities and migration_evidence is None and not (positive_list and "filter" in changed_keys):
        raise HomeKitWriteBlocked("Der Entwurf enthält keine tatsächliche Entity-Filteränderung")
    return OptionsDiff(entry_id, options, after, changed_keys, changed_entities, plan)


class HomeKitWriter:
    """Core options writer gated by an isolated fixture or narrow authority.

    The retained allow_production argument deliberately rejects former callers.
    The authority is rechecked at the Core mutation boundary.
    """

    def __init__(self, hass: Any, *, test_environment: bool = False, apply_enabled: bool = False, allow_production: bool = False, production_grant: Any = None, expected_source_revision: str | None = None, pre_mutation_check: Callable[[], None] | None = None):
        self.hass = hass
        self.test_environment = test_environment
        self.apply_enabled = bool(apply_enabled)
        self.allow_production = bool(allow_production)
        self.production_grant = production_grant
        self.expected_source_revision = expected_source_revision
        self.pre_mutation_check = pre_mutation_check

    async def async_apply(self, diff: OptionsDiff) -> dict[str, Any]:
        """Apply a Core-validated filter diff only after backend authorization."""
        if self.allow_production or not ((self.test_environment and self.apply_enabled) or self.production_grant is not None):
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        if not isinstance(diff, OptionsDiff):
            raise HomeKitWriteBlocked("Ungültiger Options-Diff")
        if self.production_grant is not None:
            await self.production_grant.verify(self.hass, diff.entry_id, "user")
            if self.expected_source_revision is None:
                raise HomeKitWriteBlocked("Produktiver Native-Apply benötigt eine vollständige Entry-Revision")
        if not diff.changed_keys:
            raise HomeKitWriteBlocked("Options-Diff enthält keine Änderung")
        from homeassistant.config_entries import SOURCE_USER
        from homeassistant.const import __version__
        if __version__ not in NATIVE_FILTER_WRITE_CORE_VERSIONS:
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
        if (dict(entry.data) | dict(entry.options)).get("mode", "bridge") != "bridge":
            raise HomeKitWriteBlocked("Nur HomeKit-Entries im Bridge-Modus dürfen geändert werden")
        if diff.changed_keys != ("filter",):
            raise HomeKitWriteBlocked("Nur geprüfte HomeKit-Filterlisten sind für Apply freigegeben")
        candidate_filter = diff.after.get("filter")
        if not isinstance(candidate_filter, Mapping) or set(candidate_filter) - set(_FILTER_LIST_KEYS):
            raise HomeKitWriteBlocked("Filter enthält unbekannte oder ungültige Felder")
        if any(not isinstance(value, list) or any(not isinstance(item, str) for item in value)
               for value in candidate_filter.values()):
            raise HomeKitWriteBlocked("Filter muss String-Listen enthalten")
        from homeassistant.helpers.entityfilter import FILTER_SCHEMA
        try:
            FILTER_SCHEMA(dict(candidate_filter))
        except Exception as err:
            raise HomeKitWriteBlocked("HomeKit-Core-Filter-Schema lehnt den Diff ab") from err
        lock = _locks.setdefault(diff.entry_id, asyncio.Lock())
        async with lock:
            # The grant may have expired or been revoked while another apply
            # held this bridge lock. Recheck before the Core mutation.
            if self.production_grant is not None:
                await self.production_grant.verify(self.hass, diff.entry_id, "user")
            if self.hass.config_entries.async_get_entry(diff.entry_id) is not entry:
                raise HomeKitWriteBlocked("HomeKit-Config-Entry wurde seit der Vorschau ersetzt")
            if self.expected_source_revision is not None:
                current_revision = revision({"entry_id": entry.entry_id, "source": str(entry.source),
                                             "data": dict(entry.data), "options": dict(entry.options)})
                if current_revision != self.expected_source_revision:
                    raise HomeKitWriteBlocked("HomeKit-Config-Entry wurde seit der Vorschau verändert")
            current_options = dict(entry.options)
            current_data = dict(entry.data)
            for key in diff.changed_keys:
                current_value = current_options.get(key, current_data.get(key))
                if current_value != diff.before.get(key):
                    raise HomeKitWriteBlocked("HomeKit-Config-Entry wurde seit der Vorschau verändert")
            next_options = dict(current_options)
            for key in diff.changed_keys:
                next_options[key] = copy.deepcopy(diff.after[key])
            if self.pre_mutation_check is not None:
                self.pre_mutation_check()
            self.hass.config_entries.async_update_entry(entry, options=next_options)
            if hasattr(self.hass, "async_block_till_done"):
                try:
                    await asyncio.wait_for(
                        self.hass.async_block_till_done(), ACTIVATION_TIMEOUT
                    )
                except TimeoutError as err:
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
            "activation": "filter_options_adapter",
            "production_verified": False,
            "activation_status": "active" if state == "loaded" else "unknown",
            "entry_id": diff.entry_id,
            "apply_enabled": True,
            "core_version": __version__,
        }
