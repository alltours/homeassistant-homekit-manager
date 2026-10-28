# Upgrade and rollback: 0.9.24 → 0.10.0

This guide describes a **later, separately approved** installation. Publishing 0.10.0 does not install it, restart Home Assistant or enable a productive writer. Only Core 2026.10.4 is within the verified writer contract.

## Before a later installation

1. Read the [capability limits](RELEASE_0_10_0.md) and [Core/Pillow security decision](SECURITY_PYTHON_DEPENDENCIES_0_10_0.md). Verify the live Core and installed Manager versions using authorized read-only access. Do not assume the existing installation matches the test system.
2. Make a restorable, access-restricted backup of the existing `custom_components/homekit_manager` directory, Home Assistant configuration and existing HomeKit persistence using the site's normal backup process. Do not move, edit or publish `.storage/homekit.*` or pairing secrets. Record the currently published 0.9.24 ZIP and SHA-256 (`88954598b4b61b1669065c40bc19f16afb97e7bd1c6f975afebc783496c23a5b`).
3. Download the **published** 0.10.0 release ZIP and its `.sha256` asset. Verify its SHA-256 and inspect the archive paths before copying any files. The archive contains `custom_components/homekit_manager/` and `RELEASE_MANIFEST.json` only.
4. Schedule the installation and any Home Assistant restart separately. The current development/release task does not authorize either on the productive host.

## Installation when separately approved

1. Replace only `custom_components/homekit_manager/` from the verified ZIP. Keep the existing Core HomeKit Entry source, HomeKit YAML, `.storage/homekit.*`, Pairings, AID/IID persistence and Apple Home settings untouched. No YAML↔UI migration is part of this release.
2. Start/restart Home Assistant under the site's change procedure. Confirm Core and Manager versions, bridge source, mode, entry count, inventories and read-only panel behavior. Check HomeKit/Manager logs for errors without exposing secrets.
3. **Do not create a write-grant file by default.** Test the UI, draft and preview read-only first. A controlled productive filter test requires its own later authorization, one Bridge, verified live backup, exact diff and the narrow grant process in [write authorization](WRITE_AUTHORIZATION_0_10_0.md).

## Rollback when separately approved

1. Revoke any local `.homekit_manager_write_grant.json` by removing it through the authorized site procedure. Stop new Apply operations and reconcile any `unknown_outcome` **read-only** before changing software.
2. Restore the verified 0.9.24 integration files from the saved release ZIP or local backup, then restart Home Assistant under the site's change procedure. Avoid restoring or editing HomeKit pairing files merely to roll back the Manager. Check the loaded Bridge and existing Apple Home controller separately.
3. If a 0.10.0 filter change had already been applied, software rollback alone does **not** reverse the Core HomeKit filter. Compare the active Entry/YAML revision with the operation journal and protected backup. Restore a previous filter only after explicit authorization and a fresh revision check; an uncertain outcome must not trigger an automatic second write.

No procedure here promises physical Apple Home pairing preservation. The release's MAC/AID/IID evidence comes from isolated Core and HAP testcontroller cases only.
