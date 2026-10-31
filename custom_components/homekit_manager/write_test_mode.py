"""Ephemeral, bridge-bound authority for a deliberately enabled native test.

This mode is never persisted. A Home Assistant restart, expiry or explicit
revocation returns the writer to its default locked state.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .const import NATIVE_FILTER_WRITE_CORE_VERSIONS

TEST_MODE_SECONDS = 60 * 60


class TestModeBlocked(ValueError):
    """The native test authority is absent or no longer valid."""


@dataclass(frozen=True)
class TestModeAuthority:
    manager: TestWriteMode
    grant_id: str
    entry_id: str
    source: str
    expires_at: datetime
    deadline: float

    async def verify(self, hass: Any, entry_id: str, source: str) -> None:
        """Recheck at the writer boundary, including after a bridge lock wait."""
        from homeassistant.config_entries import SOURCE_USER
        from homeassistant.const import __version__

        if (self.manager._authority is not self or time.monotonic() >= self.deadline
                or __version__ not in NATIVE_FILTER_WRITE_CORE_VERSIONS or entry_id != self.entry_id
                or source != self.source):
            raise TestModeBlocked("HomeKit-Testmodus ist abgelaufen oder widerrufen")
        entry = hass.config_entries.async_get_entry(entry_id)
        if (entry is None or entry.domain != "homekit" or entry.source != SOURCE_USER
                or (dict(entry.data) | dict(entry.options)).get("mode", "bridge") != "bridge"
                or getattr(entry.state, "value", entry.state) != "loaded"):
            raise TestModeBlocked("Die freigegebene native HomeKit-Bridge ist nicht mehr geladen oder gültig")


class TestWriteMode:
    """One in-memory native bridge authority, never a general writer toggle."""

    def __init__(self) -> None:
        self._authority: TestModeAuthority | None = None

    def current(self, entry_id: str, source: str) -> TestModeAuthority | None:
        authority = self._authority
        if (authority is None or time.monotonic() >= authority.deadline
                or authority.entry_id != entry_id or authority.source != source):
            return None
        return authority

    def status(self, entry_id: str | None = None) -> dict[str, Any]:
        authority = self._authority
        enabled = bool(authority and time.monotonic() < authority.deadline
                       and (entry_id is None or authority.entry_id == entry_id))
        return {"enabled": enabled, "entry_id": authority.entry_id if enabled else None,
                "expires_at": authority.expires_at.isoformat() if enabled else None,
                "persistent": False, "duration_minutes": TEST_MODE_SECONDS // 60}

    def enable(self, hass: Any, entry_id: str, confirmed_entry_id: str) -> TestModeAuthority:
        from homeassistant.config_entries import SOURCE_USER
        from homeassistant.const import __version__

        if not entry_id or confirmed_entry_id != entry_id:
            raise TestModeBlocked("Die konkrete Bridge-ID muss bestätigt werden")
        if __version__ not in NATIVE_FILTER_WRITE_CORE_VERSIONS:
            raise TestModeBlocked("Diese Home-Assistant-Core-Version ist für den Testmodus nicht verifiziert")
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != "homekit" or entry.source != SOURCE_USER:
            raise TestModeBlocked("Nur eine bestehende native HomeKit-Bridge ist zulässig")
        if (dict(entry.data) | dict(entry.options)).get("mode", "bridge") != "bridge":
            raise TestModeBlocked("Der HomeKit-Entry muss im Bridge-Modus sein")
        if getattr(entry.state, "value", entry.state) != "loaded":
            raise TestModeBlocked("Die HomeKit-Bridge muss geladen sein")
        if self._authority is not None and time.monotonic() < self._authority.deadline:
            raise TestModeBlocked("Ein Testmodus ist bereits aktiv; zuerst widerrufen")
        now = datetime.now(UTC)
        authority = TestModeAuthority(self, uuid4().hex, entry_id, "user",
                                      now + timedelta(seconds=TEST_MODE_SECONDS),
                                      time.monotonic() + TEST_MODE_SECONDS)
        self._authority = authority
        return authority

    def disable(self) -> None:
        self._authority = None
