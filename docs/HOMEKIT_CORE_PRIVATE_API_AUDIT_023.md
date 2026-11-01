# HomeKit Manager 0.10.23 – Core Private API Audit

## Reviewed patch surface

The experimental Core patch changes:

* `homeassistant/components/homekit/migration.py` – transaction journal, recovery, source transition, rollback, pre-publish identity checks.
* `homeassistant/components/homekit/__init__.py` – pre-reconciliation call and HAP validation before registration/start.
* `homeassistant/config_entries.py` – `async_update_entry_source` transaction boundary.
* `tests/components/homekit/test_migration.py` – protocol tests.

## Dependency matrix

| Access | Purpose | Public alternative | Risk | Recommendation |
|---|---|---|---|---|
| `hass.config_entries._store.async_save(...)` | force source/config durability before continuing | no public immediate Config Entry commit API | HIGH; internal store shape may change | add Core-owned transactional save API |
| `hass.config_entries._data_to_save()` | obtain complete current Config Entry payload | no public snapshot/commit method | HIGH; cache/store divergence risk | move ownership into ConfigEntries |
| `entry.async_update_entry_source` / patched manager | source transition | no supported native source migration contract | MEDIUM/HIGH until upstreamed | keep only behind versioned Core API |
| HomeKit importer ordering | recover before YAML reconciliation | no custom-integration guarantee | HIGH lifecycle coupling | native HomeKit coordinator hook |
| `driver.state`, `accessories_hash`, pairing data | HAP identity verification | no stable migration-level HAP identity API | MEDIUM; aiohomekit schema coupling | expose redacted Core identity snapshot |

## Assessment

The patch is understandable and testable but not update-stable as a HACS-only implementation. A Core update can change private store serialization, loader order, or pyhap state fields without a public compatibility contract. The minimum sustainable upstream design is a HomeKit-owned coordinator that owns the journal, source transition, reconciliation gate, and final HAP verification.
