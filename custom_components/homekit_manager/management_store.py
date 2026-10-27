"""Persist only HomeKit Manager's management-surface metadata."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store


class ManagementStore:
    """Store explicit per-bridge management activation, not HomeKit state."""

    def __init__(self, hass) -> None:
        self._store = Store(hass, 1, "homekit_manager.management")

    async def async_load(self) -> dict[str, dict[str, Any]]:
        data = await self._store.async_load()
        entries = data.get("entries", {}) if isinstance(data, dict) else {}
        if not isinstance(entries, dict):
            return {}
        return {
            str(entry_id): {
                "state": value.get("state") if isinstance(value.get("state"), str) and value.get("state") in {"active", "inactive", "not_enabled", "verifying", "unknown"} else "unknown",
                "source": value.get("source", "unknown"),
                "management": value.get("management", "homekit_manager"),
                "updated_at": value.get("updated_at"),
                "request_id": value.get("request_id"),
                "step": value.get("step"),
                "message": value.get("message"),
            }
            for entry_id, value in entries.items()
            if isinstance(entry_id, str) and isinstance(value, dict)
        }

    async def async_save(self, entries: dict[str, dict[str, Any]]) -> None:
        allowed = {"state", "source", "management", "updated_at", "request_id", "step", "message"}
        await self._store.async_save({"entries": {
            entry_id: {key: value for key, value in status.items() if key in allowed}
            for entry_id, status in entries.items()
        }})
