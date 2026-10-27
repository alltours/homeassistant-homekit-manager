"""Native Home Assistant side-panel registration for HomeKit Manager."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_STATIC_URL = f"/{DOMAIN}_static"
_PANEL_NAME = f"{DOMAIN.replace('_', '-')}-panel"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the local, admin-only panel and its static module."""
    www_path = Path(__file__).parent / "www"
    if not hass.data.get(f"{DOMAIN}_static_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_STATIC_URL, str(www_path), cache_headers=False)]
        )
        hass.data[f"{DOMAIN}_static_registered"] = True
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=_PANEL_NAME,
        frontend_url_path=DOMAIN,
        module_url=f"{_STATIC_URL}/homekit-manager.js",
        sidebar_title="HomeKit Manager",
        sidebar_icon="mdi:home-automation",
        require_admin=True,
        config={},
    )
