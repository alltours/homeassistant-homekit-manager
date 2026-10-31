"""Real filesystem exercises of the supported YAML sources."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

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


def test_yaml_accessory_entry_and_source_are_read_only(yaml_files):
    root, file = yaml_files
    before = file.read_bytes()
    adapter = YamlHomeKitAdapter(root)
    accessory = imported_entry()
    accessory.options = {"mode": "accessory"}
    with pytest.raises(YamlAdapterBlocked, match="Bridge-Modus"):
        adapter.plan_filter(accessory, {"include_entities": ["camera.front"]})
    accessory.options = {"mode": "bridge"}
    file.write_bytes(before.replace(b"- name: Bridge One\n", b"- name: Bridge One\n  mode: accessory\n"))
    with pytest.raises(YamlAdapterBlocked, match="Accessory-Modus"):
        adapter.plan_filter(accessory, {"include_entities": ["camera.front"]})
    assert b"mode: accessory" in file.read_bytes()


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


def test_yaml_apply_rejects_shared_backup_directory_without_changing_its_mode(yaml_files):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    backup_dir = root / ".storage" / "homekit_manager_backups"
    backup_dir.mkdir(parents=True)
    backup_dir.chmod(0o755)
    with pytest.raises(YamlAdapterBlocked, match="Backup-Verzeichnis"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert backup_dir.stat().st_mode & 0o777 == 0o755
    assert source.read_bytes() == before


def test_yaml_apply_rejects_shared_writable_storage_before_backup_creation(yaml_files):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    storage = root / ".storage"
    storage.mkdir()
    storage.chmod(0o777)
    with pytest.raises(YamlAdapterBlocked, match="Backup-Verzeichnis"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert not (storage / "homekit_manager_backups").exists()
    assert source.read_bytes() == before


def test_yaml_apply_rejects_hardlinked_journal(yaml_files):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    backup_dir = root / ".storage" / "homekit_manager_backups"
    backup_dir.mkdir(parents=True, mode=0o700)
    other = root / "unrelated-private-file"
    other.write_text("keep")
    other.chmod(0o600)
    os.link(other, backup_dir / "journal.jsonl")
    with pytest.raises(YamlAdapterBlocked, match="Journal"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert other.read_text() == "keep"
    assert source.read_bytes() == before


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ACL semantics")
def test_macos_source_acl_is_read_only(yaml_files):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    applied = subprocess.run(["/bin/chmod", "+a", "everyone allow write", str(source)],
                             capture_output=True, check=False)
    if applied.returncode:
        pytest.skip("Testdateisystem unterstützt keine macOS-ACL")
    with pytest.raises(YamlAdapterBlocked, match="ACL"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert source.read_bytes() == before
    assert not (root / ".storage").exists()


def test_conflict_blocks_stale_file_and_restore(yaml_files):
    root, file = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.changed"]})
    file.write_bytes(file.read_bytes() + b"# concurrent edit\n")
    with pytest.raises(YamlAdapterConflict):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert adapter.operation_state(plan) == "unknown_outcome"
    assert not (root / ".storage").exists()


def test_direct_configuration_yaml_preserves_unrelated_bytes_and_restores(tmp_path):
    root = tmp_path / "configuration.yaml"
    before = (
        b"default_config:\n"
        b"# Keep this unrelated comment exactly\n"
        b"homekit:\n"
        b"  - name: Bridge One\n"
        b"    port: 21070\n"
        b"    filter:\n"
        b"      include_entities:\n"
        b"        - light.one\n"
        b"  - name: Bridge Two\n"
        b"    port: 21071\n"
        b"    filter:\n"
        b"      include_entities:\n"
        b"        - light.two\n"
        b"logger:\n"
        b"  default: warning\n"
    )
    root.write_bytes(before)
    adapter = YamlHomeKitAdapter(tmp_path)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.one", "light.new"]})
    assert plan.source_path == root
    assert plan.after_bytes.startswith(b"default_config:\n# Keep this unrelated comment exactly\n")
    assert plan.after_bytes.endswith(b"logger:\n  default: warning\n")
    assert b"- light.two\n" in plan.after_bytes
    result = adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert result.state == "verified_file"
    assert result.backup_path.read_bytes() == before
    assert adapter.recover(result, isolated_authority=True) == "verified_file_restore"
    assert root.read_bytes() == before


def test_direct_source_rejects_forged_unrelated_comment_edit(tmp_path):
    root = tmp_path / "configuration.yaml"
    root.write_text("# preserved\nhomekit:\n  name: Bridge One\n  port: 21070\n  filter:\n    include_entities:\n    - light.one\n")
    adapter = YamlHomeKitAdapter(tmp_path)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    tampered = plan.after_bytes.replace(b"# preserved", b"# altered")
    forged = replace(plan, after_bytes=tampered, target_revision=sha256(tampered).hexdigest())
    with pytest.raises(YamlAdapterBlocked, match="unbeteiligte YAML-Bytes"):
        adapter.apply(forged, expected_revision=plan.source_revision, isolated_authority=True)
    assert root.read_bytes() == plan.before_bytes


def test_direct_source_with_external_tag_or_symlink_is_read_only(tmp_path):
    root = tmp_path / "configuration.yaml"
    root.write_text(
        "homekit:\n  name: Bridge One\n  port: 21070\n  filter:\n    include_entities:\n    - light.one\n"
        "logger: !secret log_config\n"
    )
    adapter = YamlHomeKitAdapter(tmp_path)
    with pytest.raises(YamlAdapterBlocked):
        adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    root.unlink()
    external = tmp_path / "external.yaml"
    external.write_text("homekit:\n  name: Bridge One\n  port: 21070\n")
    root.symlink_to(external)
    with pytest.raises(YamlAdapterBlocked, match="Symlink"):
        adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})


def test_direct_source_hardlink_is_not_atomically_replaced(tmp_path):
    root = tmp_path / "configuration.yaml"
    root.write_text("homekit:\n  name: Bridge One\n  port: 21070\n  filter:\n    include_entities:\n    - light.one\n")
    adapter = YamlHomeKitAdapter(tmp_path)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    os.link(root, tmp_path / "other-link.yaml")
    with pytest.raises(YamlAdapterBlocked, match="Dateiknoten"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert root.read_bytes() == plan.before_bytes
    assert not (tmp_path / ".storage").exists()


def test_source_inode_swap_after_open_is_blocked(yaml_files, monkeypatch):
    from custom_components.homekit_manager import yaml_adapter

    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    real_flock = yaml_adapter.fcntl.flock
    swapped = False

    def replace_before_lock(descriptor, operation):
        nonlocal swapped
        if operation == yaml_adapter.fcntl.LOCK_EX and not swapped:
            replacement = root / "replacement.yaml"
            replacement.write_bytes(before)
            os.replace(replacement, source)
            swapped = True
        return real_flock(descriptor, operation)

    monkeypatch.setattr(yaml_adapter.fcntl, "flock", replace_before_lock)
    with pytest.raises(YamlAdapterConflict, match="Dateiknoten"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert swapped and source.read_bytes() == before
    assert not (root / ".storage").exists()


@pytest.mark.parametrize("mode", [0o444, 0o664])
def test_read_only_or_shared_writable_source_is_blocked_before_backup(yaml_files, mode):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    os.chmod(source, mode)
    with pytest.raises(YamlAdapterBlocked, match="schreibgeschützt|andere Benutzer"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert source.read_bytes() == before
    assert not (root / ".storage").exists()


def test_extended_attributes_are_not_silently_dropped(yaml_files):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    before = source.read_bytes()
    try:
        if sys.platform == "darwin":
            libc = ctypes.CDLL(None, use_errno=True)
            setxattr = libc.setxattr
            setxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                                 ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
            setxattr.restype = ctypes.c_int
            value = ctypes.create_string_buffer(b"keep")
            if setxattr(os.fsencode(source), b"user.homekit_manager_test", value, 4, 0, 0x0001) != 0:
                raise OSError(ctypes.get_errno(), "setxattr failed")
        else:
            os.setxattr(source, "user.homekit_manager_test", b"keep")
    except (AttributeError, OSError):
        pytest.skip("Testdateisystem unterstützt keine benutzerdefinierten Dateiattribute")
    with pytest.raises(YamlAdapterBlocked, match="Dateiattribute"):
        adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    assert source.read_bytes() == before
    assert not (root / ".storage").exists()


def test_corrupted_yaml_backup_refuses_recovery(yaml_files):
    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    result = adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    result.backup_path.write_bytes(b"corrupted backup")
    with pytest.raises(YamlAdapterBlocked, match="Backup-Integrität"):
        adapter.recover(result, isolated_authority=True)
    assert source.read_bytes() == plan.after_bytes


def test_restore_source_inode_swap_after_open_is_blocked(yaml_files, monkeypatch):
    from custom_components.homekit_manager import yaml_adapter

    root, source = yaml_files
    adapter = YamlHomeKitAdapter(root)
    plan = adapter.plan_filter(imported_entry(), {"include_entities": ["light.new"]})
    result = adapter.apply(plan, expected_revision=plan.source_revision, isolated_authority=True)
    real_flock = yaml_adapter.fcntl.flock
    swapped = False

    def replace_before_lock(descriptor, operation):
        nonlocal swapped
        if operation == yaml_adapter.fcntl.LOCK_EX and not swapped:
            replacement = root / "restore-replacement.yaml"
            replacement.write_bytes(plan.after_bytes)
            os.replace(replacement, source)
            swapped = True
        return real_flock(descriptor, operation)

    monkeypatch.setattr(yaml_adapter.fcntl, "flock", replace_before_lock)
    with pytest.raises(YamlAdapterConflict, match="Dateiknoten"):
        adapter.recover(result, isolated_authority=True)
    assert swapped and source.read_bytes() == plan.after_bytes


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
