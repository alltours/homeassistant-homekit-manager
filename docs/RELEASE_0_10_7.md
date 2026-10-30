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
