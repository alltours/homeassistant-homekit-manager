"""Real filesystem exercises of the narrowly supported YAML writer."""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from custom_components.homekit_manager.yaml_adapter import (
    YamlAdapterBlocked,
    YamlAdapterConflict,
    YamlHomeKitAdapter,
)


def imported_entry(name="Bridge One", port=21070, entry_id="import-one"):
    return SimpleNamespace(domain="homekit", source="import", entry_id=entry_id, data={"name": name, "port": port})


@pytest.fixture
def yaml_files(tmp_path):
    (tmp_path / "configuration.yaml").write_text("homekit: !include bridges.yaml\n")
    bridge_file = tmp_path / "bridges.yaml"
    bridge_file.write_text(
        "# preserved bridge list\n"
        "- name: Bridge One\n"
        "  port: 21070\n"
        "  filter:\n"
        "    include_entities:\n"
        "    - light.one\n"
        "- name: Bridge Two\n"
        "  port: 21071\n"
        "  filter:\n"
        "    include_entities:\n"
        "    - light.two\n"
    )
    return tmp_path, bridge_file


def test_real_file_apply_backup_and_restore_preserve_other_bridge(yaml_files):
    root, file = yaml_files
    before = file.read_bytes()
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.one", "light.new"]})
    assert b"# preserved bridge list" in plan.after_bytes
    assert b"- name: Bridge Two\n  port: 21071\n  filter:\n    include_entities:\n    - light.two\n" in plan.after_bytes
    with pytest.raises(YamlAdapterBlocked):
        adapter.apply(plan, expected_revision=plan.source_revision)
    result = adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert result.state == "verified_file"
    assert adapter.operation_state(plan) == "verified_file"
    with pytest.raises(YamlAdapterConflict):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert file.read_bytes() == plan.after_bytes
    assert result.backup_path.read_bytes() == before
    assert result.backup_path.stat().st_mode & 0o777 == 0o600
    assert sha256(file.read_bytes()).hexdigest() == plan.target_revision
    journal = (root / ".storage" / "homekit_manager_backups" / "journal.jsonl").read_text()
    assert '"state": "applying"' in journal and '"state": "verified_file"' in journal
    assert "light.one" not in journal
    assert adapter.recover(result, isolated_authority=True) == "verified_file_restore"
    assert file.read_bytes() == before
    assert adapter.operation_state(plan) == "not_applied"


def test_conflict_blocks_stale_file_and_restore(yaml_files):
    root, file = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.changed"]})
    file.write_bytes(file.read_bytes() + b"# concurrent edit\n")
    with pytest.raises(YamlAdapterConflict):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert adapter.operation_state(plan) == "unknown_outcome"
    assert not (root / ".storage").exists()


@pytest.mark.parametrize("root_yaml", [
    "homekit: !include_dir_list homekit\n",
    "homekit: !include ../other.yaml\n",
    "homekit:\n  - name: Bridge One\n",
    "homekit: !include bridges.yaml\nhomeassistant:\n  packages: !include_dir_named packages\n",
    "homekit: !include bridges.yaml\nhomekit: !include duplicate.yaml\n",
])
def test_unproven_provenance_is_read_only(yaml_files, root_yaml):
    root, _ = yaml_files
    (root / "configuration.yaml").write_text(root_yaml)
    with pytest.raises(YamlAdapterBlocked):
        YamlHomeKitAdapter(root).plan_filter(imported_entry(), {"include_entities": ["light.one"]})


@pytest.mark.parametrize("contents", [
    "- name: Bridge One\n  port: 21070\n  filter: !secret hk_filter\n",
    "- name: Bridge One\n  port: 21070\n  filter: &hk\n    include_entities:\n    - light.one\n",
    "- name: Bridge One\n  port: 21070\n  filter:\n    include_entities:\n      - light.one\n",
    "- name: Bridge One\n  port: 21070\n  filter:\n    future_rule:\n    - light.one\n",
    "- name: Bridge One\n  port: 21070\n  filter:\n    include_entities:\n    - light.one # keep this comment\n",
])
def test_unsupported_structure_or_unknown_field_is_read_only(yaml_files, contents):
    root, file = yaml_files
    file.write_text(contents)
    with pytest.raises(YamlAdapterBlocked):
        YamlHomeKitAdapter(root).plan_filter(imported_entry(), {"include_entities": ["light.new"]})


def test_wrong_source_or_symlink_is_read_only(yaml_files, tmp_path):
    root, file = yaml_files
    adapter = YamlHomeKitAdapter(root)
    native = imported_entry()
    native.source = "user"
    with pytest.raises(YamlAdapterBlocked):
        adapter.plan_filter(native, {"include_entities": ["light.one"]})
    file.unlink()
    file.symlink_to(tmp_path / "outside.yaml")
    with pytest.raises(YamlAdapterBlocked):
        adapter.plan_filter(imported_entry(), {"include_entities": ["light.one"]})


def test_two_sessions_cannot_apply_same_revision_twice(yaml_files):
    root, file = yaml_files
    adapter = YamlHomeKitAdapter(root)
    first = adapter.plan_filter(imported_entry(), {"include_entities": ["light.first"]})
    second = adapter.plan_filter(imported_entry(), {"include_entities": ["light.second"]})
    def execute(plan):
        try:
            return adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True).state
        except YamlAdapterConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(execute, [first, second]))
    assert sorted(outcomes) == ["conflict", "verified_file"]
    assert b"light.first" in file.read_bytes() or b"light.second" in file.read_bytes()


def test_lost_response_after_replace_requires_reconciliation(yaml_files, monkeypatch):
    from custom_components.homekit_manager import yaml_adapter
    root, file = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    sync_dir = yaml_adapter._sync_dir
    def fail_source_sync(path):
        if path == root:
            raise OSError("simulated crash after atomic replace")
        sync_dir(path)
    monkeypatch.setattr(yaml_adapter, "_sync_dir", fail_source_sync)
    with pytest.raises(OSError):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert file.read_bytes() == plan.after_bytes
    assert adapter.operation_state(plan) == "verified_file"
    with pytest.raises(YamlAdapterConflict):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)


def test_forged_plan_cannot_change_other_bridge(yaml_files):
    root, file = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    tampered = plan.after_bytes.replace(b"- light.two", b"- light.tampered")
    forged = replace(plan, after_bytes=tampered, target_revision=sha256(tampered).hexdigest())
    before = file.read_bytes()
    with pytest.raises(YamlAdapterBlocked, match="unbeteiligte"):
        adapter.apply(forged, expected_revision=plan.source_revision, isolated_authority=True)
    assert file.read_bytes() == before
