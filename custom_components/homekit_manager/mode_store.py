"""Persist the manager's desired administration mode safely.

The official Home Assistant Store persists only HomeKit Manager metadata. This
does not update Home Assistant config entries, HomeKit pairing data, or any
HomeKit integration state. The store is intentionally separate from the
HomeKit configuration and contains no pairing or credential material.
"""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store

from .const import MANAGEMENT_MODES, MODE_SCHEMA_VERSION


class ModeStore:
    """Small Home Assistant Store wrapper for per-bridge mode choices."""

    def __init__(self, hass) -> None:
        self._store = Store(hass, MODE_SCHEMA_VERSION, "homekit_manager.modes")

    async def async_load(self) -> dict[str, str]:
        """Load validated desired modes."""
        data = await self._store.async_load() or {}
        modes = data.get("modes", {}) if isinstance(data, dict) else {}
        if not isinstance(modes, dict):
            return {}
        return {
            str(entry_id): str(mode)
            for entry_id, mode in modes.items()
            if isinstance(entry_id, str) and mode in MANAGEMENT_MODES
        }

    async def async_save(self, modes: dict[str, str]) -> None:
        """Persist only known modes."""
        await self._store.async_save({"modes": {
            entry_id: mode for entry_id, mode in modes.items()
            if mode in MANAGEMENT_MODES
        }})
