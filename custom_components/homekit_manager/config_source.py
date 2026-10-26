"""Conservative detection of HomeKit configuration sources.

Detection is intentionally textual and read-only. It never treats a YAML
include as proof that the running bridge has adopted a configuration.
"""
from __future__ import annotations

import re
import hashlib
from pathlib import Path
from typing import Any

import yaml


def detect_configuration_sources(
    configuration_text: str,
    *,
    manager_file_exists: bool,
    bridge_count: int,
) -> dict[str, Any]:
    """Classify observed sources without attempting a migration."""
    text = configuration_text or ""
    has_direct_homekit = bool(re.search(r"(?m)^\s*homekit\s*:(?!\s*!include\b)\s*", text))
    includes_manager = bool(re.search(r"(?m)^\s*homekit\s*:\s*!include\s+homekit_manager\.yaml\s*(?:#.*)?$", text))
    has_other_include = bool(re.search(r"(?m)^\s*homekit\s*:\s*!include\s+[^\s#]+", text)) and not includes_manager
    observed = []
    if bridge_count:
        observed.append("homekit_bridge")
    if has_direct_homekit:
        observed.append("yaml")
    if includes_manager:
        observed.append("homekit_manager")
    if has_other_include:
        observed.append("yaml_include")
    unique = list(dict.fromkeys(observed))
    mixed = len(unique) > 1 or has_other_include
    active = unique[0] if len(unique) == 1 else "mixed" if mixed else "unknown"
    return {
        "sources": unique,
        "active_mode": active,
        "mixed": mixed,
        "ambiguous": active in {"mixed", "unknown"},
        "direct_yaml": has_direct_homekit,
        "manager_include": includes_manager,
        "manager_file_exists": manager_file_exists,
        "message": (
            "Mehrere HomeKit-Quellen erkannt; Migration ist blockiert."
            if mixed else
            "Keine eindeutige HomeKit-Konfigurationsquelle erkannt."
            if active == "unknown" else
            "Quelle erkannt; eine Aktivierung wird nicht behauptet."
        ),
    }


_HOMEKIT_INCLUDE = re.compile(r"(?m)^\s*homekit\s*:\s*!include(?:_dir_merge_named|_dir_merge_list)?\s+([^\s#]+)")


def inspect_configuration_sources(
    configuration_text: str,
    *,
    config_dir: str | Path,
    manager_file_exists: bool,
    bridge_count: int,
) -> dict[str, Any]:
    """Inspect include targets without treating them as active migrations.

    The returned metadata is intentionally limited to paths, readability,
    hashes, and parser errors. File contents are never returned to the UI.
    Include paths escaping the Home Assistant config directory are rejected.
    """
    result = detect_configuration_sources(
        configuration_text,
        manager_file_exists=manager_file_exists,
        bridge_count=bridge_count,
    )
    root = Path(config_dir).resolve()
    include_files: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw_path in _HOMEKIT_INCLUDE.findall(configuration_text or ""):
        candidate = (root / raw_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"Include außerhalb des Konfigurationsverzeichnisses: {raw_path}")
            continue
        item: dict[str, Any] = {"path": str(candidate.relative_to(root)), "exists": candidate.is_file(), "readable": False}
        if candidate.is_file():
            try:
                content = candidate.read_bytes()
                item.update({"readable": True, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
                try:
                    yaml.safe_load(content.decode("utf-8"))
                except (UnicodeDecodeError, yaml.YAMLError) as err:
                    item["parse_error"] = str(err)
                    errors.append(f"Ungültige YAML-Datei: {item['path']}")
            except OSError as err:
                item["error"] = str(err)
                errors.append(f"Include nicht lesbar: {item['path']}")
        else:
            errors.append(f"Include-Datei fehlt: {item['path']}")
        include_files.append(item)
    result["include_files"] = include_files
    result["include_errors"] = errors
    result["includes_readable"] = not errors and all(item["readable"] for item in include_files)
    result["manager_file"] = {
        "path": "homekit_manager.yaml",
        "exists": manager_file_exists,
        "included": result["manager_include"],
    }
    if result["manager_include"] and not manager_file_exists:
        result.update(
            active_mode="unknown",
            ambiguous=True,
            message="HomeKit-Manager-Include verweist auf eine fehlende Datei; Aktivierung ist unklar.",
        )
    elif errors and result["active_mode"] != "mixed":
        result.update(
            active_mode="unknown",
            ambiguous=True,
            message="Eine HomeKit-Include-Datei konnte nicht sicher gelesen werden; Migration ist blockiert.",
        )
    return result
