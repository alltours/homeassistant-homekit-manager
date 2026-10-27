"""Read-only HomeKit config-entry reader."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
from .const import UNKNOWN

@dataclass(frozen=True)
class BridgeInfo:
    entry_id: str
    title: str
    source: str | None
    state: str | None
    supports_options: bool
    supports_reconfigure: bool
    mode: str | None
    name: str | None
    port: int | None
    filter: dict[str, Any] | None
    entity_config: dict[str, Any] | None
    data: dict[str, Any]
    options: dict[str, Any]
    yaml_imported: bool
    published: str = UNKNOWN
    def as_dict(self):
        return asdict(self)

_SENSITIVE_KEYS = ("password", "token", "secret", "pin", "key", "pairing")


def _is_sensitive(key: Any) -> bool:
    lowered = str(key).casefold()
    return any(word in lowered for word in _SENSITIVE_KEYS)


def _redact(value: Any) -> Any:
    """Copy an options value without exposing nested pairing material."""
    if isinstance(value, dict):
        return {
            key: _redact(item)
            for key, item in value.items()
            if not _is_sensitive(key)
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


def _safe_options(entry) -> dict[str, Any]:
    options = dict(getattr(entry, "options", {}) or {})
    data = dict(getattr(entry, "data", {}) or {})
    merged = dict(data)
    merged.update(options)
    return _redact(merged)


def _safe_mapping(value: Any) -> dict[str, Any]:
    return _redact(dict(value or {}))

def read_homekit_entries(hass) -> list[BridgeInfo]:
    """Read metadata/options only; never update, reload, unpair, or reset."""
    result = []
    for entry in hass.config_entries.async_entries("homekit"):
        safe = _safe_options(entry)
        result.append(BridgeInfo(
            entry_id=entry.entry_id, title=entry.title, source=getattr(entry, "source", None),
            state=getattr(getattr(entry, "state", None), "value", getattr(entry, "state", None)),
            supports_options=bool(getattr(entry, "supports_options", True)),
            supports_reconfigure=bool(getattr(entry, "supports_reconfigure", False)),
            mode=safe.get("homekit_mode", safe.get("mode", "bridge")), name=safe.get("name"), port=safe.get("port"),
            filter=safe.get("filter") if "filter" in safe else None,
            entity_config=safe.get("entity_config") if "entity_config" in safe else None,
            data=_safe_mapping(getattr(entry, "data", {})),
            options=_safe_mapping(getattr(entry, "options", {})),
            yaml_imported=getattr(entry, "source", None) == "import",
        ))
    return result

