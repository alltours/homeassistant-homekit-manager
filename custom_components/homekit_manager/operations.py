"""Common operation state machine for native and YAML filter writers.

The normal coordinator has no authority without a local grant or a deliberately
enabled, short-lived native test mode. Only secret-free metadata is persisted.
An interrupted apply is unknown until a separate read-only reconcile; it is
never retried automatically.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.helpers.storage import Store

from .const import NATIVE_FILTER_WRITE_CORE_VERSIONS
from .homekit_writer import (
    HomeKitWriteBlocked,
    HomeKitWriteDisabled,
    OptionsDiff,
    build_options_diff,
)
from .native_adapter import NativeFilterPlan, NativeHomeKitAdapter, _context_revision
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
    recovered_after_restart: bool = False


JOURNAL_SCHEMA_VERSION = 2
_JOURNAL_PRIVATE_KEYS = {"integrity"}


def _filter_fingerprint(value: Mapping[str, Any] | None) -> str:
    """Return a stable, secret-free fingerprint for one native filter."""
    payload = json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _journal_integrity(record: Mapping[str, Any]) -> str:
    """Hash all persisted journal fields except the integrity field itself."""
    payload = {key: value for key, value in record.items() if key not in _JOURNAL_PRIVATE_KEYS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _recovery_phase(state: str) -> str:
    return {
        "validated": "validated",
        "applying": "mutation_pending",
        "verified": "target_verified",
        "verification_incomplete": "target_options_verified",
        "unknown_outcome": "manual_reconciliation_required",
        "not_applied": "reconciled_not_applied",
        "rolling_back": "rollback_pending",
        "rolled_back": "rollback_verified",
        "rollback_unknown": "manual_rollback_reconciliation_required",
    }.get(state, "unknown")


class HomeKitOperationService:
    """Prepare and verify supported filter edits without a third config source."""

    def __init__(self, hass: Any, *, isolated_write_authority: bool = False, fault_injector: Callable[[str], None] | None = None):
        self.hass = hass
        self._isolated_write_authority = isolated_write_authority
        # Fault injection is dependency-injected by isolated tests only.  The
        # normal coordinator never supplies this callback.
        self._fault_injector = fault_injector
        self._store = Store(hass, 1, "homekit_manager.operations")
        self._plans: dict[str, OperationPlan] = {}
        self._lock = asyncio.Lock()
        # Recovery challenges are deliberately process-local and therefore
        # cannot survive a restart.  A recovered rollback always needs a new
        # challenge and a newly verified authority.
        self._recovery_challenges: dict[str, str] = {}
        self._journal_errors: dict[str, str] = {}
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
        if self._journal_errors.get("__store__"):
            return {"enabled": False, "reason": "Operationsjournal ist nicht vertrauenswürdig", "automatic_retry": False}
        if any(
            self._journal_errors.get(operation_id)
            for operation_id, item in records.items()
            if isinstance(item, dict) and item.get("entry_id") == entry_id
        ):
            return {"enabled": False, "reason": "Operationsjournal der Bridge ist nicht vertrauenswürdig", "automatic_retry": False}
        if any(isinstance(item, dict) and item.get("entry_id") == entry_id
               and item.get("state") in {"applying", "prepared", "unknown_outcome", "rolling_back", "rollback_unknown"}
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
        self._journal_errors = {}
        if not isinstance(data, dict):
            self._journal_errors["__store__"] = "Journalwurzel ist kein Objekt"
            return {}
        records = data.get("operations", {}) if isinstance(data, dict) else {}
        if not isinstance(records, dict):
            self._journal_errors["__store__"] = "Operationsjournal ist kein Objekt"
            return {}
        if data.get("schema_version", JOURNAL_SCHEMA_VERSION) not in {JOURNAL_SCHEMA_VERSION}:
            self._journal_errors["__store__"] = "Unbekannte Journalschema-Version"
        result: dict[str, dict[str, Any]] = {}
        for operation_id, record in records.items():
            if not isinstance(record, dict):
                self._journal_errors[str(operation_id)] = "Journal-Eintrag ist kein Objekt"
                continue
            result[str(operation_id)] = dict(record)
            if record.get("journal_schema") != JOURNAL_SCHEMA_VERSION:
                self._journal_errors[str(operation_id)] = "Altes oder unbekanntes Journalschema"
            elif not isinstance(record.get("integrity"), str) or not hmac.compare_digest(
                record["integrity"], _journal_integrity(record)
            ):
                self._journal_errors[str(operation_id)] = "Journalintegrität konnte nicht bestätigt werden"
        return result

    async def _save_records(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        """Persist one bounded, versioned journal through HA's atomic Store."""
        await self._store.async_save({
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "operations": dict(list(records.items())[-100:]),
        })

    def _journal_error(self, operation_id: str) -> str | None:
        return self._journal_errors.get(operation_id) or self._journal_errors.get("__store__")

    def _ensure_journal_record(self, record: Mapping[str, Any], operation_id: str) -> None:
        error = self._journal_error(operation_id)
        if error:
            raise HomeKitWriteBlocked(f"Operation-Journal ist nicht vertrauenswürdig: {error}")
        if record.get("operation_id") != operation_id:
            raise HomeKitWriteBlocked("Journal-Operation-ID stimmt nicht mit der Anfrage überein")
        if record.get("operation_type") != "native_filter_apply":
            raise HomeKitWriteBlocked("Unbekannter Operationstyp im Journal")

    async def _persist_record_state(
        self,
        record: Mapping[str, Any],
        state: str,
        *,
        detail: str | None = None,
    ) -> dict[str, Any]:
        """Write a state transition with a fresh integrity digest."""
        updated = dict(record)
        updated["state"] = state
        updated["recovery_phase"] = _recovery_phase(state)
        updated["detail"] = detail
        updated["updated_at"] = datetime.now(UTC).isoformat()
        updated["integrity"] = _journal_integrity(updated)
        records = await self._records()
        records[updated["operation_id"]] = updated
        await self._save_records(records)
        return updated

    async def _set_state(self, plan: OperationPlan, state: str, *, detail: str | None = None, grant_id: str | None = None) -> None:
        records = await self._records()
        previous = records.get(plan.operation_id, {})
        if not isinstance(previous, dict):
            raise HomeKitWriteBlocked("Gespeichertes Operation-Journal ist beschädigt")
        if self._journal_error(plan.operation_id):
            raise HomeKitWriteBlocked("Gespeichertes Operation-Journal ist nicht vertrauenswürdig")
        now = datetime.now(UTC).isoformat()
        record = {
            "journal_schema": JOURNAL_SCHEMA_VERSION,
            "operation_id": plan.operation_id,
            "operation_type": "native_filter_apply",
            "entry_id": plan.entry_id,
            "source": plan.source,
            "source_revision": plan.source_revision,
            "context_revision": (
                plan.payload.context_revision if isinstance(plan.payload, NativeFilterPlan)
                else None
            ),
            "changed_entities": list(plan.changed_entities),
            "change_type": "filter",
            "authority_kind": plan.authority_kind,
            "authority_id": plan.authority_id,
            "grant_id": grant_id or previous.get("grant_id"),
            "before_filter": (
                copy.deepcopy(plan.payload.diff.before.get("filter"))
                if isinstance(plan.payload, NativeFilterPlan) else None
            ),
            "target_filter": (
                copy.deepcopy(plan.payload.diff.after.get("filter"))
                if isinstance(plan.payload, NativeFilterPlan)
                else copy.deepcopy(plan.payload.after_filter)
                if isinstance(plan.payload, YamlFilterPlan) else None
            ),
            "before_fingerprint": (
                _filter_fingerprint(plan.payload.diff.before.get("filter"))
                if isinstance(plan.payload, NativeFilterPlan) else None
            ),
            "target_fingerprint": (
                _filter_fingerprint(plan.payload.diff.after.get("filter"))
                if isinstance(plan.payload, NativeFilterPlan) else None
            ),
            "target_revision": plan.payload.target_revision if isinstance(plan.payload, YamlFilterPlan) else None,
            "created_at": previous.get("created_at", now),
            "source_file": plan.payload.source_path.name if isinstance(plan.payload, YamlFilterPlan) else None,
            "state": state,
            "recovery_phase": _recovery_phase(state),
            "detail": detail,
            "confirmed_at": previous.get("confirmed_at", now) if state in {"applying", "rolling_back"} else previous.get("confirmed_at"),
            "integrity": "",
        }
        record["integrity"] = _journal_integrity(record)
        records[plan.operation_id] = record
        await self._save_records(records)

    @staticmethod
    def _public(record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value for key, value in record.items()
            if key not in {"before_filter", "target_filter", "source_file", "integrity"}
        } | {"automatic_retry": False}

    def _reconstruct_native_plan(self, record: Mapping[str, Any]) -> OperationPlan:
        """Reconstruct only a fully authenticated native plan from the journal."""
        operation_id = str(record.get("operation_id", ""))
        self._ensure_journal_record(record, operation_id)
        if record.get("source") != "user":
            raise HomeKitWriteBlocked("Nur native SOURCE_USER-Vorgänge dürfen wiederhergestellt werden")
        before = record.get("before_filter")
        target = record.get("target_filter")
        source_revision = record.get("source_revision")
        context_revision = record.get("context_revision")
        if not isinstance(before, Mapping) or not isinstance(target, Mapping):
            raise HomeKitWriteBlocked("Journal enthält keinen vollständigen Native-Filter-Plan")
        if not isinstance(source_revision, str) or not isinstance(context_revision, str):
            raise HomeKitWriteBlocked("Journal enthält keine vollständigen Revisionsdaten")
        if record.get("before_fingerprint") != _filter_fingerprint(before):
            raise HomeKitWriteBlocked("Ausgangsfilter-Prüfsumme des Journals ist ungültig")
        if record.get("target_fingerprint") != _filter_fingerprint(target):
            raise HomeKitWriteBlocked("Zielfilter-Prüfsumme des Journals ist ungültig")
        entry = self.hass.config_entries.async_get_entry(str(record.get("entry_id", "")))
        if entry is None or entry.domain != "homekit" or entry.source != "user":
            raise HomeKitWriteBlocked("Gespeicherter Config Entry ist nicht mehr eindeutig vorhanden")
        changed_keys = ("filter",)
        changed_entities = tuple(str(item) for item in record.get("changed_entities", ()) if isinstance(item, str))
        diff = OptionsDiff(
            entry.entry_id,
            {"filter": copy.deepcopy(dict(before))},
            {"filter": copy.deepcopy(dict(target))},
            changed_keys,
            changed_entities,
            {"changes": []},
        )
        payload = NativeFilterPlan(
            entry.entry_id,
            source_revision,
            context_revision,
            diff,
            operation_id=operation_id,
        )
        return OperationPlan(
            operation_id,
            entry.entry_id,
            "user",
            source_revision,
            changed_entities,
            payload,
            str(record.get("authority_kind", "blocked")),
            record.get("grant_id"),
            (),
            True,
        )

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
        if record and self._journal_error(operation_id):
            return self._public(record) | {
                "journal_integrity": "invalid",
                "recovery_blocked": True,
                "recovery_reason": self._journal_error(operation_id),
            }
        if record and record.get("state") in {"applying", "prepared", "rolling_back"} and operation_id not in self._plans:
            return self._public(record | {"state": "unknown_outcome"})
        if not record:
            return None
        result = self._public(record) | {"journal_integrity": "verified"}
        if operation_id not in self._plans and record.get("state") in {"verified", "verification_incomplete"}:
            try:
                self._reconstruct_native_plan(record)
            except HomeKitWriteBlocked as err:
                result |= {"recovery_blocked": True, "recovery_reason": str(err)}
            else:
                challenge = self._recovery_challenges.setdefault(operation_id, secrets.token_urlsafe(32))
                result |= {
                    "recovery_required": True,
                    "recovery_confirmation": challenge,
                    "automatic_retry": False,
                }
        return result

    async def apply(self, operation_id: str, *, entry_id: str, expected_revision: str, confirmed_operation_id: str, admin: bool = False) -> dict[str, Any]:
        """Execute once after admin, confirmation, revision and write-grant gates."""
        if not admin or not operation_id or confirmed_operation_id != operation_id:
            raise HomeKitWriteBlocked("Adminberechtigung und Bestätigung der konkreten Operation erforderlich")
        if self._fault_injector is not None:
            self._fault_injector("after_confirmation")
            self._fault_injector("before_lock")
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
            if self._fault_injector is not None:
                self._fault_injector("after_write_grant_check")
                self._fault_injector("after_lock")
                self._fault_injector("before_apply_journal")
            await self._set_state(plan, "applying", grant_id=grant.grant_id if grant else None)
            if self._fault_injector is not None:
                self._fault_injector("after_apply_journal_checkpoint")
                self._fault_injector("after_snapshot")
            try:
                runtime_verification = "verified"
                if isinstance(plan.payload, NativeFilterPlan):
                    result = await NativeHomeKitAdapter(self.hass, isolated_test_authority=self._isolated_write_authority,
                                                        production_grant=grant, fault_injector=self._fault_injector).apply(plan.payload)
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
            if self._fault_injector is not None:
                self._fault_injector("before_apply_journal_final")
            await self._set_state(plan, result_state,
                                  detail=None if result_state == "verified" else "Native Optionen verifiziert; laufende HAP-Veröffentlichung nicht vollständig lesbar")
            if self._fault_injector is not None:
                self._fault_injector("after_apply_journal")
            return {"operation_id": plan.operation_id, "entry_id": plan.entry_id, "state": result_state,
                    "runtime_verification": runtime_verification, "pairing_verified": False}

    async def rollback(self, operation_id: str, *, entry_id: str,
                       confirmed_operation_id: str, admin: bool = False) -> dict[str, Any]:
        """Restore one verified native operation, never an arbitrary filter.

        The operation must have completed successfully and the live native
        filter must still equal the exact target written by that operation.
        YAML source rollback remains isolated-only because Core reload scope is
        not production-safe on the supported Core versions.
        """
        if not admin or not operation_id:
            raise HomeKitWriteBlocked("Adminberechtigung und Bestätigung der konkreten Operation erforderlich")
        if operation_id in self._plans and confirmed_operation_id != operation_id:
            raise HomeKitWriteBlocked("Adminberechtigung und Bestätigung der konkreten Operation erforderlich")
        if self._fault_injector is not None:
            self._fault_injector("rollback_before_lock")
        async with self._lock:
            record = (await self._records()).get(operation_id)
            self._ensure_journal_record(record or {}, operation_id)
            recovered = operation_id not in self._plans
            plan = self._plans.get(operation_id)
            if record is None or record.get("state") not in {"verified", "verification_incomplete"}:
                raise HomeKitWriteBlocked("Nur ein vollständig verifiziertes Apply kann wiederhergestellt werden")
            if plan is None:
                if self._recovery_challenges.get(operation_id) != confirmed_operation_id:
                    raise HomeKitWriteBlocked("Nach Neustart ist eine neue Recovery-Bestätigung erforderlich")
                plan = self._reconstruct_native_plan(record)
            if self._fault_injector is not None:
                self._fault_injector("rollback_after_confirmation")
            if plan is None:
                raise HomeKitWriteBlocked("Nur ein vollständig verifiziertes Apply kann wiederhergestellt werden")
            if plan.entry_id != entry_id:
                raise HomeKitWriteBlocked("Bridge weicht vom bestätigten Vorgang ab")
            if not isinstance(plan.payload, NativeFilterPlan):
                raise HomeKitWriteBlocked("YAML-Quellenrollback ist im produktiven Workflow gesperrt")
            policy = await self.authority_status(entry_id, plan.source)
            if not policy["enabled"]:
                raise HomeKitWriteDisabled(policy["reason"])
            if plan.authority_kind != policy.get("authority") or plan.authority_id != policy.get("grant_id"):
                if not recovered or plan.authority_kind == "isolated":
                    raise HomeKitWriteDisabled("Schreibfreigabe hat sich seit dem Apply geändert")
                if (
                    policy.get("authority") != plan.authority_kind
                    or not policy.get("grant_id")
                    or policy.get("grant_id") == record.get("grant_id")
                ):
                    raise HomeKitWriteDisabled("Nach Neustart ist eine neue, unabhängige Schreibfreigabe erforderlich")
            grant = None if self._isolated_write_authority else await self._production_grant(entry_id, plan.source)
            if self._fault_injector is not None:
                self._fault_injector("rollback_after_write_grant_check")
                self._fault_injector("rollback_after_lock")
                self._fault_injector("rollback_before_journal")
            await self._set_state(plan, "rolling_back", grant_id=grant.grant_id if grant else None)
            if self._fault_injector is not None:
                self._fault_injector("rollback_after_journal_checkpoint")
            try:
                adapter = NativeHomeKitAdapter(
                    self.hass,
                    isolated_test_authority=self._isolated_write_authority,
                    production_grant=grant,
                    fault_injector=self._fault_injector,
                )
                state = await adapter.recover(plan.payload)
                if state != "verified_options_restore":
                    raise HomeKitWriteBlocked("Wiederherstellung wurde nicht verifiziert")
            except Exception:
                await self._set_state(plan, "rollback_unknown", detail="Wiederherstellung lesend abgleichen; kein automatischer Retry")
                raise
            if self._fault_injector is not None:
                self._fault_injector("rollback_before_journal_final")
            await self._set_state(plan, "rolled_back")
            if self._fault_injector is not None:
                self._fault_injector("rollback_after_journal")
            return {"operation_id": operation_id, "entry_id": entry_id,
                    "state": "rolled_back", "pairing_verified": False,
                    "automatic_retry": False}

    async def reconcile(self, operation_id: str) -> dict[str, Any]:
        """Read actual state after a lost response; never call a writer."""
        # An in-flight apply holds this lock. Reconcile must not classify the
        # pre-write revision as "not_applied" while that apply is still running.
        async with self._lock:
            return await self._reconcile_locked(operation_id)

    def _classify_persisted_native_record(self, record: Mapping[str, Any]) -> str:
        """Classify a persisted native operation without calling a writer."""
        entry = self.hass.config_entries.async_get_entry(str(record.get("entry_id", "")))
        if entry is None:
            return "config_entry_missing"
        if entry.domain != "homekit" or entry.source != "user":
            return "external_change"
        if record.get("context_revision") != _context_revision(entry):
            return "external_change"
        current = dict(entry.options).get("filter")
        if record.get("state") in {"rolling_back", "rollback_unknown", "rolled_back"}:
            if current == record.get("before_filter") and getattr(entry.state, "value", entry.state) == "loaded":
                return "rollback_verified"
            if current == record.get("target_filter"):
                return "rollback_not_applied" if record.get("state") != "rolled_back" else "rollback_unknown"
            return "rollback_unknown"
        if current == record.get("target_filter") and getattr(entry.state, "value", entry.state) == "loaded":
            return "verified_options"
        if current == record.get("before_filter"):
            return "not_applied"
        return "unknown_outcome"

    async def _reconcile_locked(self, operation_id: str) -> dict[str, Any]:
        plan = self._plans.get(operation_id)
        record = (await self._records()).get(operation_id)
        if record is None:
            raise HomeKitWriteBlocked("Operation-ID ist nicht bekannt")
        self._ensure_journal_record(record, operation_id)
        if plan is None:
            if record.get("source") == "user":
                actual = self._classify_persisted_native_record(record)
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
            if actual in {"verified_options", "verified_core"}:
                state = "verified"
            elif actual == "rollback_verified":
                state = "rolled_back"
            elif actual == "rollback_not_applied":
                state = "rollback_unknown"
            elif actual == "not_applied" and record.get("state") == "rolled_back":
                state = "rolled_back"
            elif actual == "not_applied":
                state = "not_applied"
            else:
                state = "unknown_outcome"
            updated = await self._persist_record_state(record, state, detail=f"read_only_reconcile:{actual}")
            return self._public(updated) | {"journal_integrity": "verified", "recovery_result": actual}
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
