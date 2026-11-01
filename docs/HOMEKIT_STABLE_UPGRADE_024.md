# HomeKit Manager 0.10.24 – Upgrade and Rollback

The integration stores Manager metadata separately from Home Assistant's native
HomeKit Config Entries and HAP persistence. An upgrade must not recreate a
Bridge or alter an existing pairing.

Before upgrading:

- retain the existing Home Assistant backup;
- verify that no test-mode authority is active;
- export the Manager draft if one is needed for review.

After upgrading:

- confirm that the HomeKit Manager Config Entry remains present;
- confirm that the administrator panel loads;
- inspect the read-only diagnostics and management status;
- verify that native migration remains blocked;
- verify that any local write grant is still valid, or recreate it explicitly
  if its expiry or revision no longer matches.

If the Manager fails to load, remove or revert only the custom integration
files through the normal HACS rollback mechanism. Do not remove HomeKit Config
Entries, HAP persistence or pairing data as an upgrade workaround.
