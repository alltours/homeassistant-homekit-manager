"""Deterministic, read-only HomeKit Manager diagnostics."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any


def _finding(code: str, severity: str, title: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, "title": title, "detail": detail, **extra}


def build_diagnostics(
    inventory: Iterable[Mapping[str, Any]],
    bridges: Iterable[Mapping[str, Any]],
    yaml_status: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return reproducible findings without claiming Apple Home visibility."""
    entities = list(inventory)
    known = {item.get("entity_id") for item in entities}
    findings: list[dict[str, Any]] = []

    for item in entities:
        entity_id = item.get("entity_id")
        compatibility = item.get("compatibility", {})
        included = item.get("homekit", {}).get("configured_by_filter")
        if compatibility.get("status") == "unsupported":
            findings.append(_finding(
                "unsupported_entity", "critical" if included is True else "info", "Nicht unterstützte Entität",
                compatibility.get("reason") or "Für diese Entität ist kein sicherer HomeKit-Pfad bekannt.",
                entity_id=entity_id, filter_included=included,
                published="unknown", apple_home_visible="unknown",
                recommendation="Bridge-Filter und HomeKit-Zuordnung prüfen; Veröffentlichung ist nicht nachgewiesen." if included is True else "Nur Inventarhinweis; diese Entität ist für die ausgewählte Bridge nicht nachweislich eingeschlossen.",
            ))
        elif compatibility.get("status") in {"conditionally_supported", "unknown"} and included is True:
            findings.append(_finding(
                "uncertain_compatibility", "warning", "Kompatibilität nicht eindeutig",
                compatibility.get("reason") or "Die HomeKit-Darstellung muss zur Laufzeit geprüft werden.",
                entity_id=entity_id, recommendation="Device Class, Einheit und HomeKit-Zuordnung prüfen.",
            ))
        status = item.get("availability_status", "available" if item.get("available") else "unavailable")
        if status != "available" and included is True:
            findings.append(_finding(
                "entity_unavailable", "warning", "Entitätsstatus prüfen",
                f"Inventarstatus: {status}.",
                entity_id=entity_id, recommendation="Integration und Gerät prüfen; keine automatische Freigabe.",
            ))

    assignments: dict[str, list[str]] = defaultdict(list)
    for bridge in bridges:
        bridge_id = bridge.get("entry_id") or bridge.get("title") or "unbekannte Bridge"
        filter_data = bridge.get("filter") or {}
        for entity_id in filter_data.get("include_entities", []) or []:
            assignments[entity_id].append(str(bridge_id))
        for entity_id in filter_data.get("exclude_entities", []) or []:
            if entity_id not in known:
                findings.append(_finding(
                    "stale_filter_reference", "warning", "Veraltete Filterreferenz",
                    "Eine Ausschlussreferenz ist im aktuellen Entity-Inventar nicht vorhanden.",
                    entity_id=entity_id, bridge=str(bridge_id), recommendation="Referenz prüfen; nicht automatisch entfernen.",
                ))
    for entity_id, bridge_ids in sorted(assignments.items()):
        if entity_id not in known:
            findings.append(_finding(
                "stale_filter_reference", "warning", "Veraltete Filterreferenz",
                "Eine Einschlussreferenz ist im aktuellen Entity-Inventar nicht vorhanden.",
                entity_id=entity_id, bridge=bridge_ids, recommendation="Referenz prüfen; nicht automatisch entfernen.",
            ))
        if len(set(bridge_ids)) > 1:
            findings.append(_finding(
                "duplicate_bridge_assignment", "warning", "Entität in mehreren Bridge-Filtern",
                "Die Entität ist in mehreren Bridge-Filtern explizit eingeschlossen.",
                entity_id=entity_id, bridges=sorted(set(bridge_ids)), recommendation="Bridge-Zuordnung manuell vergleichen.",
            ))

    if yaml_status and not yaml_status.get("valid", True):
        findings.append(_finding(
            "invalid_yaml", "critical", "YAML-Konfiguration ungültig",
            yaml_status.get("error") or "Die gespeicherte YAML-Konfiguration konnte nicht validiert werden.",
            recommendation="YAML im Entwurf reparieren; Aktivierung bleibt gesperrt.",
        ))

    severity_order = {"critical": 0, "warning": 1, "info": 2, "success": 3}
    return sorted(findings, key=lambda item: (severity_order.get(item["severity"], 9), item["code"], str(item.get("entity_id", ""))))


def diagnostics_summary(findings: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    summary = {"critical": 0, "warning": 0, "info": 0, "success": 0, "total": 0}
    for finding in findings:
        severity = finding.get("severity", "info")
        summary[severity] = summary.get(severity, 0) + 1
        summary["total"] += 1
    return summary


def group_diagnostics(findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group identical diagnostics while retaining affected entity details."""
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for finding in findings:
        key = tuple(finding.get(name) for name in ("code", "severity", "title", "detail", "recommendation"))
        group = groups.setdefault(key, {
            "code": finding.get("code"),
            "severity": finding.get("severity", "info"),
            "title": finding.get("title", "Diagnose"),
            "detail": finding.get("detail", ""),
            "recommendation": finding.get("recommendation", ""),
            "count": 0,
            "entity_ids": [],
            "details": [],
        })
        group["count"] += 1
        entity_id = finding.get("entity_id")
        if entity_id and entity_id not in group["entity_ids"]:
            group["entity_ids"].append(entity_id)
        group["details"].append(dict(finding))
    return sorted(groups.values(), key=lambda item: (item["severity"], item["code"], item["title"]))
