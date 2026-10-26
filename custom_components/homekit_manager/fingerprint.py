"""Deterministic, secret-free conflict fingerprints."""
from __future__ import annotations

import hashlib
import json
from typing import Any

_SENSITIVE = ("password", "token", "secret", "pin", "key", "pairing")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if not any(word in str(key).casefold() for word in _SENSITIVE)
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_safe(item) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_fingerprint(bridges: list[dict[str, Any]], inventory: list[dict[str, Any]], yaml_document: dict[str, Any]) -> str:
    """Hash all relevant observable state without exposing secret values."""
    source = {
        "bridges": bridges,
        "entities": [
            {key: item.get(key) for key in (
                "entity_id", "name", "domain", "device_id", "area_id",
                "integration_domain", "device_class", "entity_category",
                "disabled_by", "hidden_by", "config_entry_id", "homekit",
            )}
            for item in inventory
        ],
        "yaml": yaml_document,
    }
    encoded = json.dumps(_safe(source), sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
