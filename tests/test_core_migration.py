from __future__ import annotations

import asyncio
from types import SimpleNamespace

from custom_components.homekit_manager.core_migration import (
    async_prepare,
    async_status,
    async_switch,
    capability,
)


def test_missing_core_boundary_fails_closed() -> None:
    result = capability(SimpleNamespace())
    assert result["available"] is False
    assert result["migration_enabled"] is False


def test_missing_core_boundary_never_prepares_or_switches() -> None:
    hass = SimpleNamespace()
    prepared = asyncio.run(async_prepare(hass, {"entry_id": "bridge"}))
    switched = asyncio.run(async_switch(hass, "transaction"))
    assert prepared["state"] == "BLOCKED"
    assert switched["state"] == "BLOCKED"


def test_missing_core_boundary_status_is_fail_closed() -> None:
    """A missing protocol cannot be mistaken for an idle migration."""
    status = asyncio.run(async_status(SimpleNamespace()))
    assert status["state"] == "BLOCKED"
    assert status["action"] == "manual_recovery"
