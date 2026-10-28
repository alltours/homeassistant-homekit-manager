"""A narrowly scoped native adapter over Core's config-entry update contract.

Only filter-list changes are supported. Production apply requires a local grant;
automatic recovery and rollback remain unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
import asyncio
from typing import Any, Mapping
from uuid import uuid4

from homeassistant.helpers.storage import Store

from .homekit_writer import HomeKitWriter, HomeKitWriteBlocked, OptionsDiff, build_options_diff
from .source_model import HomeKitSource, native_source, revision


_OPERATION_LOCKS: dict[str, asyncio.Lock] = {}


def _context_revision(entry: Any) -> str:
    options = dict(entry.options)
    options.pop("filter", None)
    return revision({"data": dict(entry.data), "options_except_filter": options})


@dataclass(frozen=True)
class NativeFilterPlan:
    entry_id: str
    source_revision: str
    context_revision: str
    diff: OptionsDiff = field(repr=False)
    operation_id: str = field(default_factory=lambda: uuid4().hex)


class NativeHomeKitAdapter:
    def __init__(self, hass: Any, *, isolated_test_authority: bool = False, production_grant: Any = None):
        self.hass = hass
        self._isolated_test_authority = isolated_test_authority
        self._production_grant = production_grant
        self._store = Store(hass, 1, "homekit_manager.native_operations")

    async def _records(self) -> dict[str, Any]:
        value = await self._store.async_load() or {}
        return dict(value.get("operations", {})) if isinstance(value, dict) else {}

    async def _record(self, plan: NativeFilterPlan, state: str) -> None:
        records = await self._records()
        records[plan.operation_id] = {
            "entry_id": plan.entry_id,
            "source_revision": plan.source_revision,
            "context_revision": plan.context_revision,
            "before_filter": deepcopy(plan.diff.before.get("filter")),
            "target_filter": deepcopy(plan.diff.after.get("filter")),
            "state": state,
        }
        await self._store.async_save({"operations": dict(list(records.items())[-100:])})

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
        return NativeFilterPlan(snapshot.entry_id, snapshot.revision, _context_revision(current), diff)

    def reconcile(self, plan: NativeFilterPlan) -> str:
        snapshot = self.read(plan.entry_id)
        entry = self.hass.config_entries.async_get_entry(plan.entry_id)
        if _context_revision(entry) != plan.context_revision:
            return "unknown_outcome"
        options = dict(entry.options)
        if all(options.get(key) == plan.diff.after.get(key) for key in plan.diff.changed_keys):
            return "verified_options" if getattr(entry.state, "value", entry.state) == "loaded" else "unknown_outcome"
        if snapshot.revision == plan.source_revision:
            return "not_applied"
        return "unknown_outcome"

    async def apply(self, plan: NativeFilterPlan) -> dict[str, Any]:
        if not self._isolated_test_authority and self._production_grant is None:
            from .homekit_writer import HomeKitWriteDisabled
            from .safety import WRITE_LOCK_REASON
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        if self._production_grant is not None:
            await self._production_grant.verify(self.hass, plan.entry_id, "user")
        lock = _OPERATION_LOCKS.setdefault(plan.entry_id, asyncio.Lock())
        async with lock:
            records = await self._records()
            if plan.operation_id in records:
                raise HomeKitWriteBlocked("Operation-ID bereits vorhanden; zuerst lesend abgleichen")
            if self.read(plan.entry_id).revision != plan.source_revision:
                raise HomeKitWriteBlocked("Native Config-Entry-Revision ist veraltet")
            await self._record(plan, "applying")
            try:
                result = await HomeKitWriter(self.hass, test_environment=self._isolated_test_authority,
                                             apply_enabled=self._isolated_test_authority,
                                             production_grant=self._production_grant,
                                             expected_source_revision=plan.source_revision).async_apply(plan.diff)
                if self.reconcile(plan) != "verified_options":
                    raise HomeKitWriteBlocked("Native Nachverifikation fehlgeschlagen")
            except Exception:
                await self._record(plan, "unknown_outcome")
                raise
            await self._record(plan, "verified_options")
            return result | {"verification": "verified_options", "pairing_verified": False, "operation_id": plan.operation_id}

    async def reconcile_operation(self, operation_id: str) -> str:
        """Recover status after a lost response; never repeat a write."""
        record = (await self._records()).get(operation_id)
        if not isinstance(record, dict):
            raise HomeKitWriteBlocked("Operation-ID ist nicht bekannt")
        entry = self.hass.config_entries.async_get_entry(record["entry_id"])
        if entry is None or _context_revision(entry) != record["context_revision"]:
            return "unknown_outcome"
        current = dict(entry.options).get("filter")
        if current == record["target_filter"] and getattr(entry.state, "value", entry.state) == "loaded":
            return "verified_options"
        if current == record["before_filter"]:
            return "not_applied"
        return "unknown_outcome"

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
        await self._record(plan, "verified_options_restore")
        return "verified_options_restore"
