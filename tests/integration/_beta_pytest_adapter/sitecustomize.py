"""Test-only compatibility hook for Core 2026.11.0b0.

pytest-homeassistant-custom-component 0.13.375 imports this logger cleanup
helper, which was removed from the beta Core. The helper is not used by this
project's tests. This shim is loaded only by the beta integration runner and
is never included in the HomeKit Manager release archive.
"""

from homeassistant.components import logger

if not hasattr(logger, "_clear_logger_overwrites"):
    logger._clear_logger_overwrites = lambda: None
