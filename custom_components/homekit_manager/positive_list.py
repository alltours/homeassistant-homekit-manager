"""Read-only evidence for converting a broad Core filter to an entity whitelist.

The runtime check uses Core's live Bridge and AID lookup without allocating an
AID or reading/writing HomeKit storage files. It proves only the current Core
runtime, never visibility on a physical Apple Home controller.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from .runtime_diagnostics import diagnose_runtime, runtime_publication_summary


class PositiveListBlocked(ValueError):
    """The existing export set cannot be proven sufficiently for migration."""


def read_runtime_publication(hass: Any, entry: Any, inventory_ids: frozenset[str]) -> dict[str, Any]:
    """Read the currently constructed bridge without touching storage files.

    The result is deliberately conservative: an unreadable or ambiguous HAP
    mapping is ``unknown`` rather than an empty publication.
    """
    diagnosis = diagnose_runtime(hass, entry, inventory_ids)
    return runtime_publication_summary(diagnosis)


@dataclass(frozen=True)
class PositiveListEvidence:
    signature: str
    selected_ids: frozenset[str]
    published_ids: frozenset[str]
    registry_blocked_ids: frozenset[str]
    mac: str
    paired: bool
    published_aids: tuple[tuple[str, int], ...]
    iid_hashes: tuple[tuple[str, str], ...]


def collect_migration_evidence(
    hass: Any, entry: Any, inventory_ids: frozenset[str], current_filter: Mapping[str, Any]
) -> PositiveListEvidence:
    """Compare complete HA IDs, Core selection and live HAP accessories."""
    if (entry is None or entry.domain != "homekit" or entry.source != "user"
            or (dict(entry.data) | dict(entry.options)).get("mode", "bridge") != "bridge"
            or getattr(entry.state, "value", entry.state) != "loaded"):
        raise PositiveListBlocked("Nur eine geladene native Bridge kann in eine Positivliste überführt werden")
    if (dict(entry.data) | dict(entry.options)).get("devices"):
        raise PositiveListBlocked("Geräte-Trigger-Accessories verhindern einen eindeutigen Exportabgleich")
    state_order = [state.entity_id for state in hass.states.async_all()]
    state_ids = frozenset(state_order)
    registry = er.async_get(hass)
    registry_ids = frozenset(registry.entities)
    if not state_ids | registry_ids <= inventory_ids:
        raise PositiveListBlocked("Inventar enthält nicht alle aktuellen State- und Registry-Entitäten")
    try:
        core_filter = FILTER_SCHEMA(dict(current_filter))
        predicate = core_filter.get_filter()
    except Exception as err:
        raise PositiveListBlocked("Core kann den aktuellen HomeKit-Filter nicht auswerten") from err
    selected = frozenset(entity_id for entity_id in state_ids | registry_ids if predicate(entity_id))
    if not selected:
        raise PositiveListBlocked("Eine leere Positivliste würde in Core alle Entitäten freigeben")
    registry_blocked = frozenset(entity_id for entity_id in selected
                                 if (record := registry.async_get(entity_id)) is not None
                                 and (record.entity_category is not None or record.hidden_by is not None)
                                 and not core_filter.explicitly_included(entity_id))
    runtime = getattr(getattr(entry, "runtime_data", None), "homekit", None)
    bridge = getattr(runtime, "bridge", None)
    storage = getattr(runtime, "aid_storage", None)
    driver = getattr(runtime, "driver", None)
    iid_storage = getattr(runtime, "iid_storage", None)
    if (bridge is None or storage is None or driver is None or iid_storage is None
            or not isinstance(getattr(bridge, "accessories", None), dict)):
        raise PositiveListBlocked("Aktuelle HAP-Bridge und AID-Zuordnung sind nicht lesbar")
    runtime_aids = frozenset(bridge.accessories)
    published: set[str] = set()
    aid_map: dict[int, str] = {}
    iid_hashes: list[tuple[str, str]] = []
    for aid in runtime_aids:
        matches = [entity_id for entity_id in state_ids
                   if storage.get_allocated_aid_for_entity_id(entity_id) == aid]
        if len(matches) != 1 or matches[0] not in selected:
            raise PositiveListBlocked("Ein HAP-Accessory kann keiner ausgewählten Entität eindeutig zugeordnet werden")
        published.add(matches[0])
        aid_map[aid] = matches[0]
        iids = iid_storage.allocations.get(str(aid))
        if not isinstance(iids, dict):
            raise PositiveListBlocked("HAP-IID-Zuordnung eines veröffentlichten Accessories fehlt")
        iid_hashes.append((matches[0], sha256(json.dumps(iids, sort_keys=True).encode()).hexdigest()))
    mac = driver.state.mac
    paired = bool(driver.state.paired)
    signature = sha256(json.dumps({
        "entry_id": entry.entry_id, "state_order": state_order,
        "registry_ids": sorted(registry_ids), "selected": sorted(selected),
        "runtime_aids": sorted(runtime_aids), "published": sorted(published),
        "aid_map": sorted(aid_map.items()), "registry_blocked": sorted(registry_blocked),
        "iid_hashes": sorted(iid_hashes), "mac": mac, "paired": paired,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PositiveListEvidence(signature, selected, frozenset(published), registry_blocked,
                                mac, paired, tuple(sorted((entity_id, aid) for aid, entity_id in aid_map.items())),
                                tuple(sorted(iid_hashes)))


def verify_migration_runtime(before: PositiveListEvidence, after: PositiveListEvidence,
                             included_ids: frozenset[str]) -> None:
    """Require retained accessories, bridge identity and IID map to survive."""
    if before.mac != after.mac or before.paired != after.paired:
        raise PositiveListBlocked("HAP-Identität oder Pairing-Zustand hat sich nach Apply verändert")
    if after.published_ids - included_ids:
        raise PositiveListBlocked("Nicht ausgewählte Entitäten sind nach Apply als HAP-Accessories registriert")
    retained = before.published_ids & included_ids
    if not retained <= after.published_ids:
        raise PositiveListBlocked("Bisheriges HAP-Accessory fehlt trotz Beibehaltung in der Positivliste")
    before_aids, after_aids = dict(before.published_aids), dict(after.published_aids)
    before_iids, after_iids = dict(before.iid_hashes), dict(after.iid_hashes)
    if any(before_aids[entity_id] != after_aids[entity_id]
           or before_iids[entity_id] != after_iids[entity_id] for entity_id in retained):
        raise PositiveListBlocked("AID- oder IID-Zuordnung eines beibehaltenen Accessories hat sich verändert")
