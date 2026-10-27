"""A narrowly scoped native adapter over Core's config-entry update contract.

Only filter-list changes are supported.  The production coordinator does not
instantiate an enabled writer; apply and recovery remain isolated operations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Any, Mapping

from .homekit_writer import HomeKitWriter, HomeKitWriteBlocked, OptionsDiff, build_options_diff
from .source_model import HomeKitSource, native_source


@dataclass(frozen=True)
class NativeFilterPlan:
    entry_id: str
    source_revision: str
    diff: OptionsDiff = field(repr=False)


class NativeHomeKitAdapter:
    def __init__(self, hass: Any, *, isolated_test_authority: bool = False):
        self.hass = hass
        self._isolated_test_authority = isolated_test_authority

    def read(self, entry_id: str) -> HomeKitSource:
        from homeassistant.const import __version__
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != "homekit":
            raise HomeKitWriteBlocked("HomeKit-Entry ist nicht vorhanden")
        return native_source(entry, __version__)

    def plan_filter(self, bridge: Mapping[str, Any], desired_document: Mapping[str, Any], inventory: list[Mapping[str, Any]]) -> NativeFilterPlan:
        snapshot = self.read(str(bridge.get("entry_id", "")))
        if not snapshot.capabilities.filter_write:
            raise HomeKitWriteBlocked(snapshot.capabilities.reason or "Native Quelle nicht editierbar")
        if snapshot.source != bridge.get("source") or snapshot.entry_id != bridge.get("entry_id"):
            raise HomeKitWriteBlocked("Bridge-Kontext stimmt nicht mit Core überein")
        current = self.hass.config_entries.async_get_entry(snapshot.entry_id)
        accurate = dict(bridge) | {"data": deepcopy(dict(current.data)), "options": deepcopy(dict(current.options))}
        diff = build_options_diff(accurate, desired_document, inventory)
        if not diff.changed_keys:
            raise HomeKitWriteBlocked("Änderungsplan enthält keine native Optionsänderung")
        return NativeFilterPlan(snapshot.entry_id, snapshot.revision, diff)

    def reconcile(self, plan: NativeFilterPlan) -> str:
        snapshot = self.read(plan.entry_id)
        entry = self.hass.config_entries.async_get_entry(plan.entry_id)
        options = dict(entry.options)
        if all(options.get(key) == plan.diff.after.get(key) for key in plan.diff.changed_keys):
            return "verified_options" if getattr(entry.state, "value", entry.state) == "loaded" else "unknown_outcome"
        if snapshot.revision == plan.source_revision:
            return "not_applied"
        return "unknown_outcome"

    async def apply(self, plan: NativeFilterPlan) -> dict[str, Any]:
        if not self._isolated_test_authority:
            from .homekit_writer import HomeKitWriteDisabled
            from .safety import WRITE_LOCK_REASON
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        if self.read(plan.entry_id).revision != plan.source_revision:
            raise HomeKitWriteBlocked("Native Config-Entry-Revision ist veraltet")
        result = await HomeKitWriter(self.hass, test_environment=True, apply_enabled=True).async_apply(plan.diff)
        if self.reconcile(plan) != "verified_options":
            raise HomeKitWriteBlocked("Native Nachverifikation fehlgeschlagen")
        return result | {"verification": "verified_options", "pairing_verified": False}

    async def recover(self, plan: NativeFilterPlan) -> str:
        """Isolated option reversal; not a guarantee for HAP or Apple Home."""
        if not self._isolated_test_authority:
            from .homekit_writer import HomeKitWriteDisabled
            from .safety import WRITE_LOCK_REASON
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        if self.reconcile(plan) != "verified_options":
            raise HomeKitWriteBlocked("Aktuelle native Optionen entsprechen nicht exakt dem Plan")
        inverse = OptionsDiff(plan.entry_id, deepcopy(plan.diff.after), deepcopy(plan.diff.before),
                              plan.diff.changed_keys, plan.diff.changed_entities, plan.diff.plan)
        await HomeKitWriter(self.hass, test_environment=True, apply_enabled=True).async_apply(inverse)
        if self.read(plan.entry_id).revision != plan.source_revision:
            raise HomeKitWriteBlocked("Native Options-Wiederherstellung nicht verifiziert")
        return "verified_options_restore"
