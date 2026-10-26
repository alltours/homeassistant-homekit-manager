"""Persistent, secret-free history storage for HomeKit Manager metadata."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store

from .const import HISTORY_SCHEMA_VERSION, MAX_HISTORY_ENTRIES
from .history import _safe_document


class HistoryStore:
    """Persist only validated draft history, never HomeKit credentials."""

    def __init__(self, hass) -> None:
        self._store = Store(hass, HISTORY_SCHEMA_VERSION, "homekit_manager.history")

    @staticmethod
    def _normalize_entry(entry: Any) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None
        try:
            document = _safe_document(entry.get("document", {}))
        except (TypeError, ValueError):
            return None
        bridge_ids = set(document["bridges"])
        bridge_id = entry.get("bridge_id")
        if bridge_id is not None and (not isinstance(bridge_id, str) or bridge_id not in bridge_ids):
            bridge_id = next(iter(bridge_ids), None)
        return {
            "timestamp": str(entry.get("timestamp", "")),
            "reason": str(entry.get("reason", "draft_saved")),
            "document": document,
            "fingerprint": entry.get("fingerprint") if isinstance(entry.get("fingerprint"), str) else None,
            "applied": False,
            "bridge_id": bridge_id,
        }

    async def async_load(self) -> list[dict[str, Any]]:
        data = await self._store.async_load() or {}
        raw = data.get("entries", []) if isinstance(data, dict) else []
        if not isinstance(raw, list):
            return []
        return [entry for raw_entry in raw if (entry := self._normalize_entry(raw_entry))][-MAX_HISTORY_ENTRIES:]

    async def async_save(self, entries: list[dict[str, Any]]) -> None:
        safe = [entry for raw_entry in entries[-MAX_HISTORY_ENTRIES:] if (entry := self._normalize_entry(raw_entry))]
        await self._store.async_save({"entries": safe})
