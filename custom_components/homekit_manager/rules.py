"""Deterministic, suggestion-only entity rules."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _matches(entity: Mapping[str, Any], match: Mapping[str, Any]) -> bool:
    for key, wanted in match.items():
        if key == "compatibility":
            actual = entity.get("compatibility", {}).get("status")
        elif key == "available":
            actual = bool(entity.get("available"))
        elif key == "entity_id_prefix":
            actual = entity.get("entity_id")
        else:
            actual = entity.get(key)
        if isinstance(wanted, list):
            if actual not in wanted:
                return False
        elif key == "entity_id_prefix":
            if not str(actual or "").startswith(str(wanted)):
                return False
        elif actual != wanted:
            return False
    return True


def evaluate_rules(
    entities: Iterable[Mapping[str, Any]],
    rules: Iterable[Mapping[str, Any]],
    manual: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Evaluate rules deterministically; output is never applied automatically."""
    normalized = []
    if not isinstance(rules, (list, tuple)):
        raise ValueError("Regeln müssen als Liste angegeben werden")  # noqa: TRY004 - public validation contract
    for index, rule in enumerate(rules):
        if not isinstance(rule, Mapping) or not isinstance(rule.get("match", {}), Mapping):
            raise ValueError(f"Regel {index} muss gültige Filter enthalten")  # noqa: TRY004 - public validation contract
        priority = rule.get("priority", 0)
        if type(priority) is not int or not isinstance(rule.get("enabled", True), bool):
            raise ValueError(f"Regel {index} hat eine ungültige Priorität oder Aktivierung")
        action = rule.get("action")
        if not isinstance(action, str) or action not in {"include", "exclude"}:
            raise ValueError(f"Regel {rule.get('id', index)} hat keine gültige Aktion")
        normalized.append((-(int(rule.get("priority", 0))), str(rule.get("id", index)), index, rule))
    normalized.sort()
    manual = dict(manual or {})
    if any(not isinstance(key, str) or not isinstance(value, str) or value not in {"include", "exclude"} for key, value in manual.items()):
        raise ValueError("Manuelle Regeln benötigen Entity-IDs und include/exclude")
    decisions = []
    conflicts = []
    for entity in sorted(entities, key=lambda item: str(item.get("entity_id", ""))):
        entity_id = entity.get("entity_id")
        if not entity_id:
            continue
        if manual.get(entity_id) in {"include", "exclude"}:
            decisions.append({"entity_id": entity_id, "decision": manual[entity_id], "source": "manual", "matched_rules": []})
            continue
        matches = [rule for _, _, _, rule in normalized if rule.get("enabled", True) and _matches(entity, rule.get("match", {}))]
        actions = {rule["action"] for rule in matches}
        if len(actions) > 1:
            conflicts.append({"entity_id": entity_id, "rules": [str(rule.get("id")) for rule in matches], "reason": "rules disagree"})
            decisions.append({"entity_id": entity_id, "decision": "unknown", "source": "conflict", "matched_rules": [str(rule.get("id")) for rule in matches]})
        elif matches:
            winner = matches[0]
            decisions.append({"entity_id": entity_id, "decision": winner["action"], "source": "rule", "matched_rules": [str(rule.get("id")) for rule in matches]})
        else:
            decisions.append({"entity_id": entity_id, "decision": "unchanged", "source": "default", "matched_rules": []})
    return {"decisions": decisions, "conflicts": conflicts, "applied": False, "rule_count": len(normalized)}
