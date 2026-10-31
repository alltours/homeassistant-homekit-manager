"""Config flow for the read-only HomeKit Manager."""
from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a local read-only manager entry."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create the entry without credentials or external calls."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        if user_input is not None:
            return self.async_create_entry(title="HomeKit Manager", data={})
        return self.async_show_form(step_id="user")

