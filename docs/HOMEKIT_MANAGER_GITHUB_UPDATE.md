# HomeKit Manager GitHub update process

## Scope

This repository is private and cannot be installed or updated through HACS. HACS 2.0.5 can only use publicly available GitHub information, so the private repository returns a 404 from HACS even though the repository is valid and reachable with the authorized GitHub CLI account.

The supported update path is:

`GitHub (authenticated Mac) -> verified release archive -> Home Assistant File Editor or approved file transfer -> controlled restart -> live verification`

## Required properties

- Keep `alltours/homeassistant-homekit-manager` private.
- Use only a tagged GitHub release or a commit explicitly selected for deployment.
- Do not place GitHub credentials, tokens, `.storage` files, backups, or pairing data in the repository or release archive.
- Back up Home Assistant before replacing the integration directory.
- Replace only `custom_components/homekit_manager/`.
- Verify the file list and SHA-256 hashes after transfer.
- Do not modify the existing HomeKit config entry, HomeKit options, pairings, accessory identifiers, or `.storage`.
- Keep `apply_enabled = False`; `HomeKitWriter.async_apply()` must continue to reject changes.

## Mac-side update procedure

1. Authenticate with the official GitHub CLI on the Mac:

   ```text
   gh auth status
   ```

2. Select the desired release or commit. Do not use an unreviewed branch head for production.

3. Download the release archive through the authenticated CLI or GitHub UI and verify its SHA-256 against the repository release manifest.

4. Confirm the Home Assistant backup is complete.

5. Inspect the existing directory and create a complete, independently verifiable backup of:

   ```text
   /homeassistant/custom_components/homekit_manager/
   ```

6. Transfer the verified files into the same directory. Do not change any other custom integration.

7. Recompute hashes or perform a complete content comparison in the target directory.

8. Restart Home Assistant only if the selected release requires it and the restart is explicitly approved for that deployment.

9. Verify integration discovery, version, setup, panel loading, WebSocket behavior, inventory loading, and the unchanged HomeKit bridge.

## Rollback

If verification fails, stop further changes. Restore the previously verified HomeKit Manager directory from the pre-update backup, verify its hashes, and restart Home Assistant only if required and explicitly approved. This rollback must not touch HomeKit config entries, pairings, or `.storage`.

## Current repository state

- Repository: `alltours/homeassistant-homekit-manager`
- Default branch: `main`
- Current tested branch commit: `5bebeab8e5917a3f4495d6dd636032cbba22027a`
- CI: GitHub Actions successful for that commit
- HACS: not supported for this private repository
