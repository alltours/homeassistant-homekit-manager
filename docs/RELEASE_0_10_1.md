# HomeKit Manager 0.10.1 release candidate

## Change from 0.10.0

An HA administrator can deliberately enable a one-hour, one-Bridge native
filter test mode in Settings. It begins disabled, requires explicit Bridge-ID
confirmation, expires or can be revoked, and needs no local grant file. Every
Apply still needs a freshly validated operation, current complete Entry
revision, filter-only Core schema validation and confirmation of the exact
entity diff. An ambiguous result is reconciled read-only and never retried
automatically. The original local-grant path is retained independently.

Native `SOURCE_USER` Bridge filter writing is tested on Core **2026.10.4** and
**2026.11.0b0**. Core 2026.11.0b0 changed one filter precedence case; the
writer's non-target impact check now asks the running Core's actual predicate.
The beta's native update listener still reloads that Entry. An isolated paired
HAP testcontroller reconnected after a filter Apply and full Core restart with
the existing Bridge MAC/AID/IID unchanged. Physical Apple Home pairing was not
tested. YAML filter writing remains limited to Core 2026.10.4; the beta does
not gain broader accessory compatibility claims.

## Upgrade and rollback

The release ZIP updates `custom_components/homekit_manager` only. Replacing
files does not update a running HA process; a separately authorized Core
restart may be needed. Installation, test-mode activation and the first
productive Apply require distinct decisions. The test mode is never persisted
across restart. Existing native/YAML HomeKit configuration sources and HAP
storage are not migrated or reset.

Before an installation, verify a complete restorable HA backup containing
HomeKit persistence and an off-host recovery key. After installation, first
verify read-only Manager/version/Bridge status. To roll back before any Apply,
restore the 0.10.0 integration files from the verified release and restart HA
only with authorization. After an Apply, restoring code does not reverse the
Core filter; first reconcile the operation and compare the complete Entry
revision. Any filter reversal is a new, separately approved operation. Do not
edit `.storage/homekit.*` merely to reverse a filter.

## Current productive gate

On 2026-10-29 the existing installation still reported Manager 0.10.0 and
Core 2026.11.0b0. The HA backup UI showed no available backups. This is an
installation blocker until a current complete backup is located or created
and its restoration path verified. No productive installation, reload, Core
restart, grant activation or Apply was performed while preparing this candidate.
