"""Persist migration-assistant metadata, never HomeKit configuration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.helpers.storage import Store


class MigrationStore:
    """Store a bounded, redacted migration-assistant status."""

    def __init__(self, hass) -> None:
        self._store = Store(hass, 1, "homekit_manager.migration_status")

    async def async_load(self) -> dict[str, Any] | None:
        data = await self._store.async_load()
        if not isinstance(data, dict) or not isinstance(data.get("status"), dict):
            return None
        status = dict(data["status"])
        updated = status.get("updated_at")
        try:
            timestamp = datetime.fromisoformat(str(updated))
        except (TypeError, ValueError):
            return {"state": "unknown", "message": "Historischer Status ist nicht zeitlich verifizierbar.", "stale": True}
        if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc) + timedelta(minutes=1):
            return {"state": "unknown", "message": "Historischer Status besitzt keinen verifizierbaren Zeitbezug.", "stale": True}
        if datetime.now(timezone.utc) - timestamp > timedelta(minutes=15):
            return {"state": "unknown", "message": "Historischer Migrationsstatus ist abgelaufen; keine automatische Wiederholung.", "stale": True, "updated_at": updated}
        return status

    async def async_save(self, status: dict[str, Any]) -> None:
        allowed = {"state", "progress", "step", "message", "bridge_entry_id", "source", "target", "changed", "migration_performed", "updated_at", "stale"}
        await self._store.async_save({"status": {key: value for key, value in status.items() if key in allowed}})
