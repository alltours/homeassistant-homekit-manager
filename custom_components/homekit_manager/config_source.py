"""Conservative detection of HomeKit configuration sources.

Detection is intentionally textual and read-only. It never treats a YAML
include as proof that the running bridge has adopted a configuration.
"""
from __future__ import annotations

import re
from typing import Any


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
