"""Persist Manager operation evidence, never native HomeKit data or keys."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store

_STATES = {"validated", "prepared", "activating", "saved", "active", "failed", "unknown"}
_FIELDS = {"entry_id", "request_id", "state", "updated_at", "fingerprint", "message", "options_saved"}


class ActivationStore:
    """Bounded journal; an interrupted operation always recovers as unknown."""

    def __init__(self, hass):
        self._store = Store(hass, 1, "homekit_manager.activations")

    @staticmethod
    def normalize(raw: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(raw, dict):
            return {}
        result = {}
        for entry_id, value in list(raw.items())[-100:]:
            if not isinstance(entry_id, str) or not isinstance(value, dict):
                continue
            state = value.get("state")
            if not isinstance(state, str) or state not in _STATES:
                result[entry_id] = {"entry_id": entry_id, "state": "unknown", "message": "Gespeicherter Vorgangsstatus ist ungültig; keine automatische Wiederholung."}
                continue
            item = {key: value[key] for key in _FIELDS if key in value and isinstance(value[key], (str, bool, type(None)))}
            item["entry_id"] = entry_id
            if state in {"activating", "saved"}:
                item.update(state="unknown", message="Unterbrochener Vorgang: Das Ergebnis muss unabhängig geprüft werden.")
            result[entry_id] = item
        return result

    async def async_load(self):
        data = await self._store.async_load()
        return self.normalize(data.get("entries") if isinstance(data, dict) else None)

    async def async_save(self, entries):
        # Do not normalize in-flight states here: their interrupted state is
        # interpreted only when recovered by a later process.
        safe = {}
        for entry_id, item in list(entries.items())[-100:]:
            if isinstance(entry_id, str) and isinstance(item, dict):
                safe[entry_id] = {key: value for key, value in item.items() if key in _FIELDS and isinstance(value, (str, bool, type(None)))}
        await self._store.async_save({"entries": safe})
