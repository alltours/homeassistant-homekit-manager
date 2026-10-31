# HomeKit Manager 0.10.9

## Scope

0.10.9 is a hardening release on top of 0.10.8. It improves diagnosis when
Home Assistant Core exposes the entity-to-accessory relationship only through
the read-only AID allocation table, and prevents stored Manager exclusions
from being silently copied into a positive-list migration baseline.

The release does not apply a filter, reload HomeKit, change pairings, change
bridge identity, or write HomeKit persistence. Production Apply remains a
separate, explicitly authorized operation.

## Runtime mapping

The runtime adapter first uses the accessory object's explicit `entity_id`.
When that field is absent, it consults Core's existing
`get_allocated_aid_for_entity_id` lookup for the inventory snapshot. The lookup
is read-only and does not allocate or save AIDs. A conflicting explicit and
persistent mapping is reported as ambiguous; it is never treated as a verified
mapping.

## Positive-list migration

When preparing a migration from a broad native filter, entities with a stored
Manager `exclude` decision are left out of the automatically built baseline.
They remain visible as exclusions. Any later explicit override remains a
concrete draft change and must pass the existing server-side validation,
revision binding, operation confirmation and native filter safety gates.

New entities are not added by the migration baseline. An empty positive list
continues to be blocked because Home Assistant Core can interpret an empty
filter as include-all.

## Verification boundary

The adapter reports a complete runtime mapping only when every visible HAP
accessory is uniquely mapped and service/characteristic enumeration is
complete. Partial, missing or conflicting data remains unknown or ambiguous.
The panel never claims Apple Home visibility from these local observations.
