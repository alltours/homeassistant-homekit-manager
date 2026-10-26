"""HomeKit filter evaluation with explicit unknown handling."""
from __future__ import annotations
import fnmatch
from dataclasses import asdict, dataclass
from typing import Any, Mapping

@dataclass(frozen=True)
class FilterResult:
    configured: bool | None
    reason: str
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
                    core_filter: Any = None) -> FilterResult:
    """Mirror HA include/exclude precedence for supported filter keys."""
    if config is None:
        return FilterResult(None, "filter_unavailable")
    includes = _list(config, "include_entities")
    excludes = _list(config, "exclude_entities")
    include_domains = _list(config, "include_domains")
    exclude_domains = _list(config, "exclude_domains")
    include_globs = _list(config, "include_entity_globs")
    exclude_globs = _list(config, "exclude_entity_globs")
    domain = entity_id.split(".", 1)[0]
    if entity_id in includes:
        result = FilterResult(True, "explicit_include")
        return _apply_core_result(entity_id, result, entity_category, hidden_by, core_filter)
    has_include = bool(includes or include_domains or include_globs)
    has_exclude = bool(excludes or exclude_domains or exclude_globs)
    if has_include:
        if entity_id in excludes:
            return _apply_core_result(entity_id, FilterResult(False, "explicit_exclude"), entity_category, hidden_by, core_filter)
        if any(fnmatch.fnmatch(entity_id, p) for p in include_globs):
            return _apply_core_result(entity_id, FilterResult(True, "glob_include"), entity_category, hidden_by, core_filter)
        if any(fnmatch.fnmatch(entity_id, p) for p in exclude_globs):
            return _apply_core_result(entity_id, FilterResult(False, "glob_exclude"), entity_category, hidden_by, core_filter)
        if domain in include_domains:
            return _apply_core_result(entity_id, FilterResult(True, "domain_include"), entity_category, hidden_by, core_filter)
        return _apply_core_result(entity_id, FilterResult(False, "not_in_include"), entity_category, hidden_by, core_filter)
    if has_exclude:
        if entity_id in excludes:
            return _apply_core_result(entity_id, FilterResult(False, "explicit_exclude"), entity_category, hidden_by, core_filter)
        if any(fnmatch.fnmatch(entity_id, p) for p in exclude_globs):
            return _apply_core_result(entity_id, FilterResult(False, "glob_exclude"), entity_category, hidden_by, core_filter)
        if domain in exclude_domains:
            return _apply_core_result(entity_id, FilterResult(False, "domain_exclude"), entity_category, hidden_by, core_filter)
        return _apply_core_result(entity_id, FilterResult(True, "default_include"), entity_category, hidden_by, core_filter)
    if entity_category is not None or hidden_by is not None:
        return _apply_core_result(entity_id, FilterResult(False, "default_category_or_hidden_exclude"), entity_category, hidden_by, core_filter)
    return _apply_core_result(entity_id, FilterResult(True, "default_include"), entity_category, hidden_by, core_filter)


def _apply_core_result(
    entity_id: str,
    result: FilterResult,
    entity_category: str | None,
    hidden_by: str | None,
    core_filter: Any,
) -> FilterResult:
    """Use the Core's predicate when available, preserving an audit reason."""
    if core_filter is None:
        return result
    try:
        included = bool(core_filter.get_filter()(entity_id))
        explicitly_included = bool(core_filter.explicitly_included(entity_id))
    except (AttributeError, TypeError, ValueError):
        return result
    if included and (entity_category is not None or hidden_by is not None) and not explicitly_included:
        return FilterResult(False, "core_category_or_hidden_exclude")
    if included == result.configured:
        return result
    return FilterResult(included, "core_filter_result")

