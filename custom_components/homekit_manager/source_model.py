"""Immutable internal descriptions of the one authoritative HomeKit source.

This model is deliberately a view of Core's entry or its YAML provenance.  It
does not store a second effective configuration. Raw Core values must never be
serialized to the UI or a journal because Core may add sensitive fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from .const import NATIVE_FILTER_WRITE_CORE_VERSIONS


def revision(value: Mapping[str, Any]) -> str:
    """Fingerprint complete values, including unknown fields, for conflict checks."""
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class SourceCapabilities:
    read: bool
    filter_write: bool
    export: bool
    reason: str | None = None


@dataclass(frozen=True)
class HomeKitSource:
    entry_id: str
    source: str
    core_version: str
    mode: str
    name: str | None
    port: int | None
    data: Mapping[str, Any] = field(repr=False)
    options: Mapping[str, Any] = field(repr=False)
    provenance: str | None
    revision: str
    capabilities: SourceCapabilities


def native_source(entry: Any, core_version: str) -> HomeKitSource:
    """Describe one Core entry without confusing SOURCE_USER and SOURCE_IMPORT."""
    from homeassistant.config_entries import SOURCE_USER

    data, options = dict(entry.data), dict(entry.options)
    effective = data | options
    source = str(entry.source)
    writable = source == SOURCE_USER and core_version in NATIVE_FILTER_WRITE_CORE_VERSIONS and effective.get("mode", "bridge") == "bridge"
    return HomeKitSource(
        entry_id=entry.entry_id,
        source=source,
        core_version=core_version,
        mode=str(effective.get("mode", "bridge")),
        name=data.get("name"),
        port=data.get("port"),
        data=_freeze(data),
        options=_freeze(options),
        provenance=None,
        revision=revision({"entry_id": entry.entry_id, "source": source, "data": data, "options": options}),
        capabilities=SourceCapabilities(True, writable, True, None if writable else "Native Filter nur für SOURCE_USER im Bridge-Modus auf einer verifizierten Core-Version"),
    )


def yaml_source(entry: Any, core_version: str, *, provenance: str | None, file_revision: str | None) -> HomeKitSource:
    """Describe an imported entry; a proven file node is required to edit."""
    from homeassistant.config_entries import SOURCE_IMPORT

    if entry.source != SOURCE_IMPORT:
        raise ValueError("Entry ist keine YAML-importierte HomeKit-Quelle")
    data, options = dict(entry.data), dict(entry.options)
    effective = data | options
    writable = bool(provenance and file_revision and core_version == "2026.10.4" and effective.get("mode", "bridge") == "bridge")
    return HomeKitSource(
        entry_id=entry.entry_id,
        source=str(entry.source),
        core_version=core_version,
        mode=str(effective.get("mode", "bridge")),
        name=data.get("name"),
        port=data.get("port"),
        data=_freeze(data),
        options=_freeze(options),
        provenance=provenance,
        revision=revision({"entry_id": entry.entry_id, "source": entry.source,
                           "data": data, "options": options, "file_revision": file_revision}),
        capabilities=SourceCapabilities(True, writable, True, None if writable else "YAML-Provenienz, Bridge-Modus oder Core-Version nicht verifiziert"),
    )
