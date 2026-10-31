"""Adapter for the experimental Core-owned HomeKit migration boundary.

The released integration deliberately remains read-only for native source
migration.  This adapter is only a capability boundary for the isolated
0.10.14 Core prototype: if the patched Core API is absent, every operation
fails closed and no ConfigEntry or YAML file is changed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CORE_MIGRATION_API = "homekit_core_source_migration_v1"


def _core_api() -> Any | None:
    """Return the experimental Core module, if this exact boundary exists."""
    try:
        from homeassistant.components.homekit import migration
    except (ImportError, ModuleNotFoundError):
        return None
    if not all(
        callable(getattr(migration, name, None))
        for name in (
            "async_prepare_source_migration",
            "async_switch_source",
            "async_recover_before_yaml_reconciliation",
        )
    ):
        return None
    return migration


def capability(hass: Any) -> dict[str, Any]:
    """Describe the Core boundary without enabling a migration."""
    del hass
    api = _core_api()
    if api is None:
        return {
            "api": CORE_MIGRATION_API,
            "available": False,
            "migration_enabled": False,
            "reason": "Core unterstützt die experimentelle HomeKit-Schnittstelle nicht.",
        }
    return {
        "api": CORE_MIGRATION_API,
        "available": True,
        "migration_enabled": False,
        "reason": "Core-Schnittstelle vorhanden; Aktivierung bleibt bis zur Freigabe gesperrt.",
    }


async def async_prepare(hass: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    """Persist a Core-owned request, but never mutate the native source."""
    api = _core_api()
    if api is None:
        return {
            "supported": False,
            "state": "BLOCKED",
            "reason": "Core-Schnittstelle fehlt; Quellenmigration bleibt gesperrt.",
        }
    try:
        result = await api.async_prepare_source_migration(hass, request)
    except Exception as err:  # noqa: BLE001  # Fail closed at the adapter boundary.
        return {
            "supported": True,
            "state": "BLOCKED",
            "reason": type(err).__name__,
        }
    return {"supported": True, "state": "PREPARED", **result}


async def async_switch(hass: Any, transaction_id: str) -> dict[str, Any]:
    """Apply a source switch only when an isolated caller explicitly invokes it."""
    api = _core_api()
    if api is None:
        return {
            "supported": False,
            "state": "BLOCKED",
            "reason": "Core-Schnittstelle fehlt; Quellenmigration bleibt gesperrt.",
        }
    try:
        entry = await api.async_switch_source(hass, transaction_id)
    except Exception as err:  # noqa: BLE001  # Never turn an uncertain result into success.
        return {"supported": True, "state": "BLOCKED", "reason": type(err).__name__}
    return {
        "supported": True,
        "state": "SOURCE_SWITCHED",
        "entry_id": entry.entry_id,
        "source": entry.source,
    }
