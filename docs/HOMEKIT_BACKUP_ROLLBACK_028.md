# HomeKit Manager 0.10.28 – Backup and Rollback

## Backup

Use the regular Home Assistant backup mechanism. Keep one copy outside the running instance and verify that it is available before installation or upgrade. HomeKit pairing and HAP persistence must be recovered through the regular Home Assistant backup; do not edit `.storage` or HAP files manually.

Record the backup timestamp, Core version, Manager version, HomeKit Config Entry IDs, bridge MACs, ports and filters.

## Manager-only rollback

If the Manager fails to load or its panel/WebSocket is broken:

1. Save logs.
2. Stop Home Assistant normally.
3. Remove or restore only `custom_components/homekit_manager/`.
4. Start Home Assistant without the Manager.
5. Verify HomeKit bridges and pairings.

Do not remove HomeKit Config Entries and do not create a new pairing.

## Full restore trigger

Use a complete Home Assistant restore only if native HomeKit state, pairings, bridge identity or filters are unexpectedly changed and the cause cannot be excluded. A restore is a larger operation than removing the Manager and must follow the official Home Assistant recovery procedure.

An unexpected bridge, pairing request, source change or filter mutation is a stop condition, not an Apply failure to be retried.
