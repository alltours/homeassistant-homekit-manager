"""Small, deterministic performance and stability summaries."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any


def summarize_inventory(entities: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return bounded metrics useful for a live performance diagnosis."""
    entities = list(entities)
    domains = Counter(str(item.get("domain", "unknown")) for item in entities)
    unavailable = sum(not item.get("available", False) for item in entities)
    return {
        "entity_count": len(entities),
        "unavailable_count": unavailable,
        "domain_counts": dict(sorted(domains.items())),
        "recommended_page_size": 100 if len(entities) <= 2500 else 50,
        "virtualization_recommended": len(entities) > 2500,
        "refresh_model": "event-driven, debounced, no state-change inventory reload from frontend",
    }
