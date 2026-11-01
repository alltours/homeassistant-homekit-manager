# HomeKit Manager 0.10.27 → 0.10.28 – Upgrade

Use only an isolated or backed-up Home Assistant instance for the first upgrade.

## Before upgrade

Record the Manager Config Entry ID, Manager settings, HomeKit Config Entry IDs, bridge MACs, ports, sources, filters, active accessories and pairing fingerprints. Create and externally store a complete Home Assistant backup.

## Procedure

1. Confirm the package checksum.
2. Stop Home Assistant normally.
3. Replace only the Manager custom-component directory with the 0.10.28 directory, or update through the approved HACS procedure.
4. Start Home Assistant.
5. Verify the Manager Config Entry, panel, WebSocket and diagnostics.
6. Verify every HomeKit bridge, MAC, port, filter and pairing with the existing controller.
7. Restart Home Assistant once more and repeat the checks.

## Required invariants

- No Manager Config Entry is recreated.
- No HomeKit Config Entry is recreated.
- No source changes occur.
- No pairing is deleted or regenerated.
- No third bridge appears.
- No filter is expanded silently.
- Native UI↔YAML migration remains unavailable.

If any invariant fails, stop. Do not delete and recreate the HomeKit entry and do not pair again as a workaround. Follow the backup/rollback procedure.
