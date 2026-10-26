"""Pure helpers for the non-persistent Phase 3 draft model."""
from __future__ import annotations

from collections.abc import Mapping


def serialize_draft(entry_id: str, draft: Mapping[str, str]) -> str:
    """Serialize a draft to the documented YAML shape without writing a file."""
    lines = ["schema_version: 1", "bridges:", f"  {entry_id}:", "    policy: explicit_overrides", "    entities:"]
    for entity_id in sorted(draft):
        value = draft[entity_id]
        if value in {"include", "exclude"}:
            lines.append(f"      {entity_id}: {value}")
    return "\n".join(lines) + "\n"
