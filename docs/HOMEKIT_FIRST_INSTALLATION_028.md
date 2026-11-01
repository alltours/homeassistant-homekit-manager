# HomeKit Manager 0.10.28 – Installation

## Scope

HomeKit Manager 0.10.28 is a stable custom integration for the official Home Assistant Core. It provides bridge inventory, diagnostics, planning, preview, export and an explicitly authorized filter-only Apply path for existing bridges.

Native UI↔YAML migration, Config Entry source changes, bridge creation, pairing reset and direct HAP-persistence changes are not supported and remain disabled.

## Before installation

1. Confirm the current Home Assistant Core version and record existing HomeKit Config Entries, sources, bridge names, MACs, ports and filters.
2. Create a complete Home Assistant backup and store a copy outside the instance.
3. Verify that the backup is available and readable.
4. Verify the package SHA-256 before extraction.
5. Confirm that no experimental Core patch is installed.
6. Do not create `.homekit_manager_write_grant.json` for the first start.

## Package installation

Stop Home Assistant through the normal administrator procedure. Extract `homekit-manager-0.10.28.zip` and copy only `custom_components/homekit_manager/` into the instance's `custom_components/` directory. Do not copy test data, `.storage` files, pairing data or Core patches.

Start Home Assistant and add HomeKit Manager through its Config Flow. The first start must be read-only: no grant, no test mode, no Apply and no source migration.

## First-start checks

- The integration loads without errors.
- The Config Entry is present.
- The authenticated panel and WebSocket connection work.
- Existing HomeKit Config Entries are unchanged.
- No new HomeKit bridge or pairing is created.
- No HAP persistence is changed by the Manager.
- The Apply action is locked without explicit authorization.

Stop immediately if a new bridge, pairing request, source change or unexpected filter change appears.

## HACS distinction

The release is HACS-compatible and passes HACS/Hassfest validation. A HACS UI installation is a separate operational step and must not be confused with extracting the release ZIP or installing the custom component manually.
