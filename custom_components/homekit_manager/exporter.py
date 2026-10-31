"""Explicit desired-state exports that never claim HomeKit was updated."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import yaml

from .yaml_store import validate_document


def export_desired_state(document: Mapping[str, Any], format_name: str = "yaml") -> str:
    """Export validated desired state as YAML, JSON, or a text list."""
    normalized = validate_document(document)
    if format_name == "yaml":
        return yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False, default_flow_style=False)
    if format_name == "json":
        return json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if format_name == "text":
        lines = ["# HomeKit Manager Soll-Zustand – nicht angewendet"]
        for entry_id in sorted(normalized["bridges"]):
            for entity_id, status in normalized["bridges"][entry_id]["entities"].items():
                lines.append(f"{status}\t{entity_id}")
        return "\n".join(lines) + "\n"
    raise ValueError("Unbekanntes Exportformat")
