# HomeKit Manager 0.10.7

0.10.7 hardens the HomeKit selection boundary around an explicit entity
positive list. Existing broad Core filters are not silently reinterpreted or
modified during installation. A separate, user-confirmed migration plan is
required before a native filter can be replaced.

The panel now distinguishes the saved Manager intent, the native Home Assistant
filter and the readable running bridge publication. A mismatch is shown even
when there are no unsaved local UI changes. Core options verification and HAP
runtime verification are reported separately; an unknown runtime observation is
never presented as a successful Apple Home publication.

The release does not install itself, reload Home Assistant, change a native
filter, change pairings or change a bridge identity. Existing `explicit_overrides`
drafts remain drafts until a separately authorized migration is reviewed and
confirmed. A failed or interrupted operation is reconciled read-only and is
never retried automatically.

## Empty-selection boundary

Selecting every entity for exclusion is not represented as an empty Home
Assistant filter. Core interprets an empty filter as the default broad
selection, so the Manager blocks an empty positive list with an explicit error.
There is no fallback that attempts to remove every accessory through a broad
filter. The user must keep at least one explicitly included entity or manage a
complete removal through a separately verified native Home Assistant workflow.

## Isolated verification

The test suite covers a migration-shaped reconciliation with seven included
domains, 60 saved Manager exclusions and an entity appearing after the draft;
the new entity is never added to the desired positive list. Isolated Core/HAP
tests preserve Bridge MAC, pairing state and retained AID/IID allocations.
Migration rollback is available only under isolated test authority and verifies
the restored native filter plus the retained runtime identity. Apple Home
visibility is deliberately not claimed as verified.
