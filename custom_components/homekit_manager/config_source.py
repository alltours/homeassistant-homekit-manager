"""Conservative detection of HomeKit configuration sources.

Detection is intentionally textual and read-only. It never treats a YAML
include as proof that the running bridge has adopted a configuration.
"""
from __future__ import annotations

import hashlib
import re
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
    include_directive = r"!include(?:_dir_merge_named|_dir_merge_list)?\b"
    has_direct_homekit = bool(
        re.search(rf"(?m)^\s*homekit\s*:(?!\s*{include_directive})\s*", text)
    )
    includes_manager = bool(re.search(r"(?m)^\s*homekit\s*:\s*!include\s+homekit_manager\.yaml\s*(?:#.*)?$", text))
    has_other_include = bool(
        re.search(rf"(?m)^\s*homekit\s*:\s*{include_directive}\s+[^\s#]+", text)
    ) and not includes_manager
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


_HOMEKIT_INCLUDE = re.compile(
    r"(?m)^\s*homekit\s*:\s*!(?P<kind>include|include_dir_merge_named|include_dir_merge_list)\s+(?P<path>[^\s#]+)"
)


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
    for match in _HOMEKIT_INCLUDE.finditer(configuration_text or ""):
        raw_path = match.group("path")
        include_kind = match.group("kind")
        unresolved_candidate = root / raw_path
        if unresolved_candidate.is_symlink():
            errors.append(f"Unsicherer Include-Symlink: {raw_path}")
            include_files.append(
                {
                    "path": raw_path,
                    "kind": "directory" if include_kind != "include" else "file",
                    "directive": f"!{include_kind}",
                    "exists": True,
                    "readable": False,
                    "symlink": True,
                }
            )
            continue
        candidate = unresolved_candidate.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"Include außerhalb des Konfigurationsverzeichnisses: {raw_path}")
            continue
        relative_path = str(candidate.relative_to(root))
        is_directory_include = include_kind != "include"
        item: dict[str, Any] = {
            "path": relative_path,
            "kind": "directory" if is_directory_include else "file",
            "directive": f"!{include_kind}",
            "exists": candidate.is_dir() if is_directory_include else candidate.is_file(),
            "readable": False,
        }
        if is_directory_include:
            _inspect_include_directory(candidate, item, errors)
        elif candidate.is_file():
            try:
                content = candidate.read_bytes()
                item.update({"readable": True, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
                try:
                    list(yaml.scan(content.decode("utf-8")))
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


def _inspect_include_directory(
    candidate: Path,
    item: dict[str, Any],
    errors: list[str],
) -> None:
    """Inspect a directory include without making it writable.

    Home Assistant's directory merge directives are valid YAML sources, but
    they do not identify one editable file.  We therefore expose deterministic
    read-only metadata for every regular YAML member and never infer a safe
    write target from the directory itself.
    """
    if not candidate.is_dir():
        errors.append(f"Include-Verzeichnis fehlt: {item['path']}")
        return
    try:
        members = sorted(
            (
                path
                for path in candidate.rglob("*")
                if not any(part.startswith(".") for part in path.relative_to(candidate).parts)
                and (
                    path.is_symlink()
                    or (
                        path.is_file()
                        and path.suffix == ".yaml"
                        and path.name != "secrets.yaml"
                    )
                )
            ),
            key=lambda path: path.relative_to(candidate).as_posix(),
        )
    except OSError as err:
        item["error"] = str(err)
        errors.append(f"Include-Verzeichnis nicht lesbar: {item['path']}")
        return

    item["members"] = []
    directory_errors = False
    for member in members:
        member_item: dict[str, Any] = {
            "path": str(member.relative_to(candidate.parent)),
            "regular_file": member.is_file() and not member.is_symlink(),
            "readable": False,
        }
        if member.is_symlink() or not member.is_file():
            errors.append(f"Unsicheres Include-Verzeichnismitglied: {member_item['path']}")
            directory_errors = True
        else:
            try:
                content = member.read_bytes()
                member_item.update(
                    {
                        "readable": True,
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "size": len(content),
                    }
                )
                try:
                    list(yaml.scan(content.decode("utf-8")))
                except (UnicodeDecodeError, yaml.YAMLError) as err:
                    member_item["parse_error"] = str(err)
                    errors.append(f"Ungültige YAML-Datei: {member_item['path']}")
                    directory_errors = True
            except OSError as err:
                member_item["error"] = str(err)
                errors.append(f"Include nicht lesbar: {member_item['path']}")
                directory_errors = True
        item["members"].append(member_item)

    item["readable"] = not directory_errors and all(
        member["readable"] for member in item["members"]
    )
