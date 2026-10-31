"""Common operation state machine for native and YAML filter writers.

The normal coordinator has no authority without a local grant or a deliberately
enabled, short-lived native test mode. Only secret-free metadata is persisted.
An interrupted apply is unknown until a separate read-only reconcile; it is
never retried automatically.
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.helpers.storage import Store

from .const import NATIVE_FILTER_WRITE_CORE_VERSIONS
from .homekit_writer import (
    HomeKitWriteBlocked,
    HomeKitWriteDisabled,
    build_options_diff,
)
from .native_adapter import NativeFilterPlan, NativeHomeKitAdapter
from .safety import WRITE_LOCK_REASON
from .write_grant import GrantBlocked, ProductionWriteGrant, read_production_grant
from .write_test_mode import TestModeAuthority, TestModeBlocked, TestWriteMode
from .yaml_adapter import YamlFilterPlan, YamlHomeKitAdapter


@dataclass(frozen=True)
class OperationPlan:
    operation_id: str
    entry_id: str
    source: str
    source_revision: str
    changed_entities: tuple[str, ...]
    payload: NativeFilterPlan | YamlFilterPlan
    authority_kind: str = "blocked"
    authority_id: str | None = None
    change_details: tuple[dict[str, Any], ...] = ()


class HomeKitOperationService:
    """Prepare and verify supported filter edits without a third config source."""

    def __init__(self, hass: Any, *, isolated_write_authority: bool = False):
        self.hass = hass
        self._isolated_write_authority = isolated_write_authority
        self._store = Store(hass, 1, "homekit_manager.operations")
        self._plans: dict[str, OperationPlan] = {}
        self._lock = asyncio.Lock()
        self.test_write_mode = TestWriteMode()

    async def authority_status(self, entry_id: str, source: str) -> dict[str, Any]:
        if self._isolated_write_authority:
            return {"enabled": True, "reason": "Nur isolierte Testinstanz", "authority": "isolated", "automatic_retry": False}
        from homeassistant.const import __version__

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if (entry is None or entry.domain != "homekit" or entry.source != source
                or (dict(entry.data) | dict(entry.options)).get("mode", "bridge") != "bridge"
                or getattr(entry.state, "value", entry.state) != "loaded"):
            return {"enabled": False, "reason": "Nur eine geladene bestehende HomeKit-Bridge darf geändert werden", "automatic_retry": False}
        if ((source == "user" and __version__ not in NATIVE_FILTER_WRITE_CORE_VERSIONS)
                or (source == "import" and __version__ != "2026.10.4")
                or source not in {"user", "import"}):
            return {"enabled": False, "reason": "Filter-Apply ist für diese Quelle/Core-Version nicht verifiziert", "automatic_retry": False}
        records = await self._records()
        if any(isinstance(item, dict) and item.get("entry_id") == entry_id
               and item.get("state") in {"applying", "prepared", "unknown_outcome"}
               for item in records.values()):
            return {"enabled": False, "reason": "Früheren ungeklärten Vorgang zuerst lesend abgleichen", "automatic_retry": False}
        if source == "import":
            if any(item.source != "import" for item in self.hass.config_entries.async_entries("homekit")):
                return {"enabled": False, "reason": "Core homekit.reload würde auch native HomeKit-Entries neu laden", "automatic_retry": False}
            try:
                await self.hass.async_add_executor_job(lambda: YamlHomeKitAdapter(self.hass.config.config_dir).current_revision())
            except (OSError, ValueError) as err:
                return {"enabled": False, "reason": f"YAML-Provenienz ist nicht sicher: {err}", "automatic_retry": False}
        test_authority = self.test_write_mode.current(entry_id, source)
        if test_authority is not None:
            try:
                await test_authority.verify(self.hass, entry_id, source)
            except TestModeBlocked as err:
                return {"enabled": False, "reason": str(err), "automatic_retry": False}
            return {"enabled": True, "reason": "Befristeter nativer Testmodus aktiv",
                    "authority": "test_mode", "grant_id": test_authority.grant_id,
                    "expires_at": test_authority.expires_at.isoformat(),
                    "automatic_retry": False}
        try:
            grant = await read_production_grant(self.hass)
            if grant is not None:
                await grant.verify(self.hass, entry_id, source)
        except GrantBlocked as err:
            return {"enabled": False, "reason": str(err), "automatic_retry": False}
        if grant is not None:
            return {"enabled": True, "reason": "Lokale, befristete Filter-Schreibfreigabe aktiv", "authority": "local_grant", "automatic_retry": False,
                    "grant_id": grant.grant_id, "expires_at": grant.expires_at.isoformat()}
        return {"enabled": False, "reason": WRITE_LOCK_REASON, "automatic_retry": False}

    async def _production_grant(self, entry_id: str, source: str) -> ProductionWriteGrant | TestModeAuthority:
        test_authority = self.test_write_mode.current(entry_id, source)
        if test_authority is not None:
            await test_authority.verify(self.hass, entry_id, source)
            return test_authority
        grant = await read_production_grant(self.hass)
        if grant is None:
            raise HomeKitWriteDisabled(WRITE_LOCK_REASON)
        await grant.verify(self.hass, entry_id, source)
        return grant

    async def _records(self) -> dict[str, dict[str, Any]]:
        data = await self._store.async_load() or {}
        records = data.get("operations", {}) if isinstance(data, dict) else {}
        return dict(records) if isinstance(records, dict) else {}

    async def _set_state(self, plan: OperationPlan, state: str, *, detail: str | None = None, grant_id: str | None = None) -> None:
        records = await self._records()
        previous = records.get(plan.operation_id, {})
        if not isinstance(previous, dict):
            raise HomeKitWriteBlocked("Gespeichertes Operation-Journal ist beschädigt")
        records[plan.operation_id] = {
            "operation_id": plan.operation_id,
            "entry_id": plan.entry_id,
            "source": plan.source,
            "source_revision": plan.source_revision,
            "changed_entities": list(plan.changed_entities),
            "change_type": "filter",
            "grant_id": grant_id or previous.get("grant_id"),
            "target_revision": plan.payload.target_revision if isinstance(plan.payload, YamlFilterPlan) else None,
            "target_filter": dict(plan.payload.after_filter) if isinstance(plan.payload, YamlFilterPlan) else None,
            "source_file": plan.payload.source_path.name if isinstance(plan.payload, YamlFilterPlan) else None,
            "state": state,
            "detail": detail,
            "updated_at": datetime.now(UTC).isoformat(),
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
        if (dict(entry.data) | dict(entry.options)).get("mode", "bridge") != "bridge":
            raise HomeKitWriteBlocked("Nur HomeKit-Entries im Bridge-Modus dürfen geändert werden")
        if entry.source == "user":
            adapter = NativeHomeKitAdapter(self.hass)
            payload = adapter.plan_filter(bridge, document, inventory)
            entities = payload.diff.changed_entities
            details = payload.diff.plan["changes"]
        elif entry.source == "import":
            from homeassistant.const import __version__
            if __version__ != "2026.10.4":
                raise HomeKitWriteBlocked("YAML-Apply ist für diese Core-Version nicht verifiziert")
            if any(item.source != "import" for item in self.hass.config_entries.async_entries("homekit")):
                raise HomeKitWriteBlocked("Core homekit.reload würde auch native HomeKit-Entries neu laden")
            current = dict(bridge) | {"data": dict(entry.data), "options": dict(entry.options)}
            diff = build_options_diff(current, document, inventory)
            if not diff.changed_keys:
                raise HomeKitWriteBlocked("Änderungsplan enthält keine YAML-Filteränderung")
            adapter = YamlHomeKitAdapter(self.hass.config.config_dir)
            payload = await self.hass.async_add_executor_job(lambda: adapter.plan_filter(entry, diff.after["filter"]))
            entities = diff.changed_entities
            details = diff.plan["changes"]
        else:
            raise HomeKitWriteBlocked("Unbekannte HomeKit-Konfigurationsquelle")
        policy = await self.authority_status(entry_id, str(entry.source))
        plan = OperationPlan(payload.operation_id, entry_id, str(entry.source), payload.source_revision,
                             tuple(entities), payload, policy.get("authority", "blocked"), policy.get("grant_id"),
                             tuple(item for item in details if item["action"] in {"add", "remove"}))
        async with self._lock:
            self._plans[plan.operation_id] = plan
            await self._set_state(plan, "validated")
        migration = None
        if isinstance(payload, NativeFilterPlan) and payload.migration_evidence is not None:
            retained = set(payload.diff.after["filter"]["include_entities"])
            migration = {
                "selected_before": len(payload.migration_evidence.selected_ids),
                "hap_published_before": len(payload.migration_evidence.published_ids),
                "published_removals": sorted(payload.migration_evidence.published_ids - retained),
                "future_entities_excluded": True,
                "apple_home_verified": False,
            }
        return {"operation_id": plan.operation_id, "entry_id": entry_id, "source": plan.source,
                "source_revision": plan.source_revision, "changed_entities": list(plan.changed_entities),
                "change_details": list(plan.change_details),
                "migration": migration,
                "state": "validated", "apply_enabled": policy["enabled"], "reason": policy["reason"],
                "operation_policy": policy}

    async def status(self, operation_id: str) -> dict[str, Any] | None:
        record = (await self._records()).get(operation_id)
        if record and record.get("state") in {"applying", "prepared"} and operation_id not in self._plans:
            return self._public(record | {"state": "unknown_outcome"})
        return self._public(record) if record else None

    async def apply(self, operation_id: str, *, entry_id: str, expected_revision: str, confirmed_operation_id: str, admin: bool = False) -> dict[str, Any]:
        """Execute once after admin, confirmation, revision and write-grant gates."""
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
            policy = await self.authority_status(entry_id, plan.source)
            if not policy["enabled"]:
                raise HomeKitWriteDisabled(policy["reason"])
            if plan.authority_kind != policy.get("authority") or plan.authority_id != policy.get("grant_id"):
                raise HomeKitWriteDisabled("Schreibfreigabe hat sich seit der Vorschau geändert")
            grant = None if self._isolated_write_authority else await self._production_grant(entry_id, plan.source)
            await self._set_state(plan, "applying", grant_id=grant.grant_id if grant else None)
            try:
                runtime_verification = "verified"
                if isinstance(plan.payload, NativeFilterPlan):
                    result = await NativeHomeKitAdapter(self.hass, isolated_test_authority=self._isolated_write_authority,
                                                        production_grant=grant).apply(plan.payload)
                    verified = result.get("verification") == "verified_options"
                    runtime_verification = result.get("runtime_verification", "incomplete")
                else:
                    adapter = YamlHomeKitAdapter(self.hass.config.config_dir)
                    result = await adapter.async_apply_with_core(self.hass, entry, plan.payload,
                                                                 isolated_authority=self._isolated_write_authority,
                                                                 production_grant=grant)
                    verified = result.state == "verified_core"
                if not verified:
                    raise HomeKitWriteBlocked("Nachverifikation nicht bestätigt")
            except Exception:
                await self._set_state(plan, "unknown_outcome", detail="Apply-Ausgang lesend abgleichen; kein automatischer Retry")
                raise
            result_state = "verified" if runtime_verification == "verified" else "verification_incomplete"
            await self._set_state(plan, result_state,
                                  detail=None if result_state == "verified" else "Native Optionen verifiziert; laufende HAP-Veröffentlichung nicht vollständig lesbar")
            return {"operation_id": plan.operation_id, "entry_id": plan.entry_id, "state": result_state,
                    "runtime_verification": runtime_verification, "pairing_verified": False}

    async def reconcile(self, operation_id: str) -> dict[str, Any]:
        """Read actual state after a lost response; never call a writer."""
        # An in-flight apply holds this lock. Reconcile must not classify the
        # pre-write revision as "not_applied" while that apply is still running.
        async with self._lock:
            return await self._reconcile_locked(operation_id)

    async def _reconcile_locked(self, operation_id: str) -> dict[str, Any]:
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
            records[operation_id] = record | {"state": state, "updated_at": datetime.now(UTC).isoformat()}
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
