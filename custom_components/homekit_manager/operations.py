"""Common isolated operation state machine for native and YAML writers.

The production coordinator does not instantiate this with write authority.
Only secret-free metadata is persisted. An interrupted apply is unknown until a
separate read-only reconcile; it is never retried automatically.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from homeassistant.helpers.storage import Store

from .homekit_writer import HomeKitWriteBlocked, HomeKitWriteDisabled, build_options_diff
from .native_adapter import NativeFilterPlan, NativeHomeKitAdapter
from .safety import WRITE_LOCK_REASON
from .yaml_adapter import YamlFilterPlan, YamlHomeKitAdapter


@dataclass(frozen=True)
class OperationPlan:
    operation_id: str
    entry_id: str
    source: str
    source_revision: str
    changed_entities: tuple[str, ...]
    payload: NativeFilterPlan | YamlFilterPlan


class HomeKitOperationService:
    """Prepare and verify supported filter edits without a third config source."""

    def __init__(self, hass: Any, *, isolated_write_authority: bool = False):
        self.hass = hass
        self._isolated_write_authority = isolated_write_authority
        self._store = Store(hass, 1, "homekit_manager.operations")
        self._plans: dict[str, OperationPlan] = {}
        self._lock = asyncio.Lock()

    async def _records(self) -> dict[str, dict[str, Any]]:
        data = await self._store.async_load() or {}
        records = data.get("operations", {}) if isinstance(data, dict) else {}
        return dict(records) if isinstance(records, dict) else {}

    async def _set_state(self, plan: OperationPlan, state: str, *, detail: str | None = None) -> None:
        records = await self._records()
        records[plan.operation_id] = {
            "operation_id": plan.operation_id,
            "entry_id": plan.entry_id,
            "source": plan.source,
            "source_revision": plan.source_revision,
            "changed_entities": list(plan.changed_entities),
            "target_revision": plan.payload.target_revision if isinstance(plan.payload, YamlFilterPlan) else None,
            "target_filter": dict(plan.payload.after_filter) if isinstance(plan.payload, YamlFilterPlan) else None,
            "source_file": plan.payload.source_path.name if isinstance(plan.payload, YamlFilterPlan) else None,
            "state": state,
            "detail": detail,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._store.async_save({"operations": dict(list(records.items())[-100:])})

    @staticmethod
    def _public(record: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key not in {"target_filter", "source_file"}} | {"automatic_retry": False}

    async def plan_filter(self, *, entry_id: str, bridge: Mapping[str, Any], document: Mapping[str, Any], inventory: list[Mapping[str, Any]]) -> dict[str, Any]:
        """Validate exact source and produce a server-held plan without writing."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != "homekit" or bridge.get("entry_id") != entry_id:
            raise HomeKitWriteBlocked("Ziel-Bridge ist nicht eindeutig")
        if entry.source == "user":
            adapter = NativeHomeKitAdapter(self.hass)
            payload = adapter.plan_filter(bridge, document, inventory)
            entities = payload.diff.changed_entities
        elif entry.source == "import":
            current = dict(bridge) | {"data": dict(entry.data), "options": dict(entry.options)}
            diff = build_options_diff(current, document, inventory)
            if not diff.changed_keys:
                raise HomeKitWriteBlocked("Änderungsplan enthält keine YAML-Filteränderung")
            adapter = YamlHomeKitAdapter(self.hass.config.config_dir)
            payload = await self.hass.async_add_executor_job(lambda: adapter.plan_filter(entry, diff.after["filter"]))
            entities = diff.changed_entities
        else:
            raise HomeKitWriteBlocked("Unbekannte HomeKit-Konfigurationsquelle")
        plan = OperationPlan(payload.operation_id, entry_id, str(entry.source), payload.source_revision, tuple(entities), payload)
        self._plans[plan.operation_id] = plan
        await self._set_state(plan, "validated")
        return {"operation_id": plan.operation_id, "entry_id": entry_id, "source": plan.source,
                "source_revision": plan.source_revision, "changed_entities": list(plan.changed_entities),
                "state": "validated", "apply_enabled": False, "reason": WRITE_LOCK_REASON}

    async def status(self, operation_id: str) -> dict[str, Any] | None:
        record = (await self._records()).get(operation_id)
        if record and record.get("state") in {"applying", "prepared"} and operation_id not in self._plans:
            return self._public(record | {"state": "unknown_outcome"})
        return self._public(record) if record else None

    async def apply(self, operation_id: str, *, entry_id: str, expected_revision: str, confirmed_operation_id: str, admin: bool = False) -> dict[str, Any]:
        """Execute only in an explicit isolated harness after every backend gate."""
        if not self._isolated_write_authority:
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        if not admin or not operation_id or confirmed_operation_id != operation_id:
            raise HomeKitWriteBlocked("Adminberechtigung und Bestätigung der konkreten Operation erforderlich")
        async with self._lock:
            plan = self._plans.get(operation_id)
            record = (await self._records()).get(operation_id)
            if plan is None or record is None or record.get("state") != "validated":
                raise HomeKitWriteBlocked("Operation ist unbekannt oder wurde bereits begonnen")
            if plan.entry_id != entry_id or plan.source_revision != expected_revision:
                raise HomeKitWriteBlocked("Bridge oder Revision weicht vom validierten Plan ab")
            entry = self.hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != "homekit" or entry.source != plan.source:
                raise HomeKitWriteBlocked("Config-Entry-Quelle wurde geändert")
            await self._set_state(plan, "applying")
            try:
                if isinstance(plan.payload, NativeFilterPlan):
                    result = await NativeHomeKitAdapter(self.hass, isolated_test_authority=True).apply(plan.payload)
                    verified = result.get("verification") == "verified_options"
                else:
                    adapter = YamlHomeKitAdapter(self.hass.config.config_dir)
                    result = await adapter.async_apply_with_core(self.hass, entry, plan.payload, isolated_authority=True)
                    verified = result.state == "verified_core"
                if not verified:
                    raise HomeKitWriteBlocked("Nachverifikation nicht bestätigt")
            except Exception:
                await self._set_state(plan, "unknown_outcome", detail="Apply-Ausgang lesend abgleichen; kein automatischer Retry")
                raise
            await self._set_state(plan, "verified")
            return {"operation_id": plan.operation_id, "entry_id": plan.entry_id, "state": "verified", "pairing_verified": False}

    async def reconcile(self, operation_id: str) -> dict[str, Any]:
        """Read actual state after a lost response; never call a writer."""
        plan = self._plans.get(operation_id)
        record = (await self._records()).get(operation_id)
        if record is None:
            raise HomeKitWriteBlocked("Operation-ID ist nicht bekannt")
        if plan is None:
            if record.get("source") == "user":
                try:
                    actual = await NativeHomeKitAdapter(self.hass).reconcile_operation(operation_id)
                except HomeKitWriteBlocked:
                    actual = "unknown_outcome"
            elif record.get("source") == "import" and record.get("source_file"):
                try:
                    name, current = await self.hass.async_add_executor_job(lambda: YamlHomeKitAdapter(self.hass.config.config_dir).current_revision())
                    if name != record["source_file"]:
                        actual = "unknown_outcome"
                    elif current == record.get("source_revision"):
                        actual = "not_applied"
                    elif current == record.get("target_revision"):
                        entry = self.hass.config_entries.async_get_entry(record["entry_id"])
                        expected = record.get("target_filter") or {}
                        observed = entry.options.get("filter") if entry and entry.source == "import" else None
                        actual = "verified_core" if entry and getattr(entry.state, "value", entry.state) == "loaded" and isinstance(observed, Mapping) and all(observed.get(key, []) == value for key, value in expected.items()) else "unknown_outcome"
                    else:
                        actual = "unknown_outcome"
                except (OSError, ValueError):
                    actual = "unknown_outcome"
            else:
                actual = "unknown_outcome"
            state = "verified" if actual in {"verified_options", "verified_core"} else "not_applied" if actual == "not_applied" else "unknown_outcome"
            records = await self._records()
            records[operation_id] = record | {"state": state, "updated_at": datetime.now(timezone.utc).isoformat()}
            await self._store.async_save({"operations": dict(list(records.items())[-100:])})
            return self._public(records[operation_id])
        if isinstance(plan.payload, NativeFilterPlan):
            actual = NativeHomeKitAdapter(self.hass).reconcile(plan.payload)
        else:
            actual = await self.hass.async_add_executor_job(lambda: YamlHomeKitAdapter(self.hass.config.config_dir).operation_state(plan.payload))
            if actual == "verified_file":
                entry = self.hass.config_entries.async_get_entry(plan.entry_id)
                expected = plan.payload.after_filter
                observed = entry.options.get("filter") if entry and entry.source == "import" else None
                if entry and getattr(entry.state, "value", entry.state) == "loaded" and isinstance(observed, Mapping) and all(observed.get(key, []) == value for key, value in expected.items()):
                    actual = "verified_core"
                else:
                    actual = "unknown_outcome"
        state = "verified" if actual in {"verified_options", "verified_core"} else "not_applied" if actual == "not_applied" else "unknown_outcome"
        await self._set_state(plan, state)
        return (await self.status(operation_id)) or {"state": "unknown_outcome"}
