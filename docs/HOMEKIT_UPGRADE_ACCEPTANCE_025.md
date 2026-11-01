# HomeKit Manager 0.10.25 – Upgrade Acceptance

## Scope

The upgrade gate must preserve an existing Manager Config Entry and all
observed HomeKit metadata without changing HomeKit source, pairing or HAP
persistence.

## Intended test

1. Install a previous reproducible Manager archive in a fresh official Core
   configuration.
2. Create the Manager Config Entry through the real Config Flow.
3. Record Manager entry ID, options, bridge association and filter draft.
4. Replace only the Manager integration with the 0.10.25 archive.
5. Restart the same isolated Core.
6. Compare entry, options, inventory, panel, WebSocket and diagnostics.
7. Restart once more and compare again.

## Result

The upgrade run was not completed because the isolated local Core onboarding
environment did not finish its pending HTTP configuration transition. No
productive data was touched and no existing HAP data was used.

Status: **NOT VERIFIED**.

The release must not claim upgrade acceptance until this test is completed in a
working official-Core environment.

