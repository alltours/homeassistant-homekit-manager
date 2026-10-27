"""Core 2026.10.4 source/identity contracts, with no HAP driver start."""
import inspect

from homeassistant.config_entries import ConfigEntries
from homeassistant.components.homekit.util import (
    get_aid_storage_filename_for_entry_id,
    get_iid_storage_filename_for_entry_id,
    get_persist_filename_for_entry_id,
)


def test_public_config_entry_update_has_no_source_mutation():
    assert "source" not in inspect.signature(ConfigEntries.async_update_entry).parameters
    assert {"data", "options"} <= set(inspect.signature(ConfigEntries.async_update_entry).parameters)


def test_homekit_identity_files_share_entry_id_without_claiming_pairing_survival():
    assert get_persist_filename_for_entry_id("isolated-entry") == "homekit.isolated-entry.state"
    assert get_aid_storage_filename_for_entry_id("isolated-entry") == "homekit.isolated-entry.aids"
    assert get_iid_storage_filename_for_entry_id("isolated-entry") == "homekit.isolated-entry.iids"
