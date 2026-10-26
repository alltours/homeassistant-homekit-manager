# HomeKit Manager GitHub update process

## Scope

This repository is public and can be installed or updated through HACS. HACS 2.0.5 uses publicly available GitHub information. The earlier private-repository state returned a 404 from HACS even though the repository itself was valid.

The supported update path is:

`Public GitHub release -> HACS -> controlled update -> controlled restart -> live verification`

## Required properties

- Keep the repository public only while the published source and history have passed the release gate.
- Use only a tagged GitHub release or a commit explicitly selected for deployment.
- Do not place GitHub credentials, tokens, `.storage` files, backups, or pairing data in the repository or release archive.
- Back up Home Assistant before replacing the integration directory.
- Replace only `custom_components/homekit_manager/`.
- Verify the file list and SHA-256 hashes after transfer.
- Do not modify the existing HomeKit config entry, HomeKit options, pairings, accessory identifiers, or `.storage`.
- Keep `apply_enabled = False`; `HomeKitWriter.async_apply()` must continue to reject changes.

## HACS update procedure

1. Confirm the existing HomeKit Manager directory and config entry before installing:

   Do not create a second installation.

2. Select the tested GitHub release in HACS.

3. Back up Home Assistant before replacing the integration directory.

4. Update only `custom_components/homekit_manager/` and verify the resulting files.

5. Restart Home Assistant only if HACS requests it and the restart is explicitly planned.

6. Verify integration discovery, version, setup, panel loading, WebSocket behavior, inventory loading, and the unchanged HomeKit bridge.

## Rollback

If verification fails, stop further changes. Restore the previously verified HomeKit Manager directory from the pre-update backup, verify its hashes, and restart Home Assistant only if required and explicitly approved. This rollback must not touch HomeKit config entries, pairings, or `.storage`.

## Current repository state

- Repository: `alltours/homeassistant-homekit-manager`
- Default branch: `main`
- Current tested branch commit: `5bebeab8e5917a3f4495d6dd636032cbba22027a`
- CI: GitHub Actions successful for that commit
- HACS: public repository path prepared; live update still requires the release and production acceptance steps below
