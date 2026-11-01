# HomeKit Manager 0.10.23 – Core API Proposal

## Proposed ownership

Home Assistant Core should own the critical transaction. The Manager should submit a validated, user-approved migration request and receive a durable status object. The Manager must not write Config Entry source, YAML reconciliation state, HAP persistence, or the Core transaction journal directly.

## Minimal contract

```python
plan = await hass.components.homekit.migration.async_prepare(
    entry_id=entry_id,
    target_source=SOURCE_IMPORT | SOURCE_USER,
    target_yaml=validated_projection,
    expected_revision=revision,
)
result = await plan.async_commit()  # COMMITTED, ROLLED_BACK, or MANUAL_RECOVERY_REQUIRED
status = await hass.components.homekit.migration.async_status(entry_id)
```

The Core contract must provide:

1. bridge-scoped journal and recovery generation;
2. durable prepare before unload or source mutation;
3. a Core-owned Config Entry persistence boundary;
4. controlled YAML reconciliation suppression/association;
5. HAP identity and allowlist snapshot before publication;
6. explicit `COMMITTED`, `ROLLED_BACK`, and `MANUAL_RECOVERY_REQUIRED` outcomes;
7. idempotent startup recovery before HomeKit YAML import;
8. conflict detection for external YAML/Config Entry changes;
9. no pairing reset or implicit bridge recreation;
10. capability discovery so older Core versions remain fail-closed.

## Trust boundary

The Core validates schema, entry identity, revision, YAML provenance, HAP identity, and authorization. The Manager supplies intent and presentation only. Arbitrary Manager journals must never be executable Core instructions.

## Compatibility

Older Core versions may continue to run the stable read-only Manager. Native migration must remain unavailable when the Core capability is absent.
