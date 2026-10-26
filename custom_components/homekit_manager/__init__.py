"""Read-only HomeKit Manager integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components import frontend

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration without mutating HomeKit."""
    if DOMAIN in hass.data:
        return True
    from .coordinator import HomeKitManagerCoordinator
    from .panel import async_register_panel
    from .websocket import async_register_websocket_commands

    coordinator = HomeKitManagerCoordinator(hass)
    hass.data[DOMAIN] = {"coordinator": coordinator}
    await coordinator.async_refresh()
    async_register_websocket_commands(hass, coordinator)
    await async_register_panel(hass)
    return True

async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up a read-only config entry."""
    if DOMAIN not in hass.data:
        if not await async_setup(hass, {}):
            return False
    hass.data[DOMAIN].setdefault("entries", set()).add(entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a read-only config entry."""
    domain_data = hass.data.get(DOMAIN)
    if not domain_data:
        return True
    entries = domain_data.get("entries", set())
    entries.discard(entry.entry_id)
    if not entries:
        coordinator = domain_data.get("coordinator")
        if coordinator is not None:
            await coordinator.async_shutdown()
        frontend.async_remove_panel(hass, DOMAIN, warn_if_unknown=False)
        hass.data.pop(DOMAIN, None)
    return True

