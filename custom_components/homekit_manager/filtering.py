"""HomeKit filter evaluation with explicit unknown handling."""
from __future__ import annotations
import fnmatch
from dataclasses import asdict, dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class FilterResult:
    configured: bool | None
    reason: str
    registry_eligible: bool | None = None
    runtime_candidate: bool | None = None
    registry_reason: str | None = None
    def as_dict(self):
        return asdict(self) | {"configured_by_filter": self.configured}

def _list(config: Mapping[str, Any], key: str) -> set[str]:
    return set(config.get(key, []) or [])


def build_core_filter(config: Mapping[str, Any] | None):
    """Build HA's own EntityFilter when the running Core exposes it."""
    if config is None:
        return None
    try:
        from homeassistant.helpers.entityfilter import FILTER_SCHEMA
        return FILTER_SCHEMA(dict(config))
    except (ImportError, TypeError, ValueError):
        return None

def evaluate_filter(entity_id: str, entity_category: str | None = None,
                    hidden_by: str | None = None,
                    config: Mapping[str, Any] | None = None,
                    core_filter: Any = None,
                    state_present: bool | None = None) -> FilterResult:
    """Mirror Core 2026.10.4's six filter cases and HomeKit registry gate.

    In particular, an entity-only include combined with a domain/glob exclude
    does *not* imply that all other entities are excluded. Core treats that as
    its fourth mixed-filter case. The registry gate in HomeKit's
    ``async_configure_accessories`` runs after the EntityFilter predicate.
    """
    if config is None:
        return FilterResult(None, "filter_unavailable")
    includes = _list(config, "include_entities")
    excludes = _list(config, "exclude_entities")
    include_domains = _list(config, "include_domains")
    exclude_domains = _list(config, "exclude_domains")
    include_globs = _list(config, "include_entity_globs")
    exclude_globs = _list(config, "exclude_entity_globs")
    domain = entity_id.split(".", 1)[0]
    has_include = bool(includes or include_domains or include_globs)
    has_exclude = bool(excludes or exclude_domains or exclude_globs)
    include_glob = any(fnmatch.fnmatchcase(entity_id, p) for p in include_globs)
    exclude_glob = any(fnmatch.fnmatchcase(entity_id, p) for p in exclude_globs)
    if entity_id in includes:
        result = FilterResult(True, "explicit_include")
    elif not has_include and not has_exclude:
        result = FilterResult(True, "default_include")
    elif has_include and not has_exclude:
        if domain in include_domains:
            result = FilterResult(True, "domain_include")
        elif include_glob:
            result = FilterResult(True, "glob_include")
        else:
            result = FilterResult(False, "not_in_include")
    elif not has_include:
        if entity_id in excludes:
            result = FilterResult(False, "explicit_exclude")
        elif domain in exclude_domains:
            result = FilterResult(False, "domain_exclude")
        elif exclude_glob:
            result = FilterResult(False, "glob_exclude")
        else:
            result = FilterResult(True, "default_include")
    elif include_domains or include_globs:
        if entity_id in excludes:
            result = FilterResult(False, "explicit_exclude")
        elif include_glob:
            result = FilterResult(True, "glob_include")
        elif exclude_glob:
            result = FilterResult(False, "glob_exclude")
        elif domain in include_domains:
            result = FilterResult(True, "domain_include")
        else:
            result = FilterResult(False, "not_in_include")
    elif exclude_domains or exclude_globs:
        if domain in exclude_domains:
            result = FilterResult(False, "domain_exclude")
        elif exclude_glob:
            result = FilterResult(False, "glob_exclude")
        elif entity_id in excludes:
            result = FilterResult(False, "explicit_exclude")
        else:
            result = FilterResult(True, "default_include")
    else:
        result = FilterResult(False, "not_in_include")
    return _apply_core_result(entity_id, result, entity_category, hidden_by, core_filter,
                              entity_id in includes or include_glob, state_present)


def _apply_core_result(
    entity_id: str,
    result: FilterResult,
    entity_category: str | None,
    hidden_by: str | None,
    core_filter: Any,
    explicitly_included: bool,
    state_present: bool | None,
) -> FilterResult:
    """Use the Core's predicate when available, preserving an audit reason."""
    if core_filter is not None:
        try:
            included = bool(core_filter.get_filter()(entity_id))
        except (AttributeError, TypeError, ValueError):
            included = result.configured
        if included != result.configured:
            result = FilterResult(included, "core_filter_result")
    # The predicate is the configuration selection. HomeKit subsequently
    # applies a separate entity-registry gate before creating accessories.
    # Core's explicitly_included() accepts an exact ID or include glob.
    registry_eligible = (entity_category is None and hidden_by is None) or explicitly_included
    registry_reason = "category_or_hidden_exclude" if not registry_eligible else "explicit_override" if (entity_category is not None or hidden_by is not None) else "registry_allowed"
    runtime_candidate = (False if not result.configured or not registry_eligible else
                         None if state_present is None else bool(state_present))
    return FilterResult(result.configured, result.reason, registry_eligible,
                        runtime_candidate, registry_reason)

