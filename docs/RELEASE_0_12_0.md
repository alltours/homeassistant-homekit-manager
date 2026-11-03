# HomeKit Manager 0.12.0

## Migration Removal & Cleanup

HomeKit Manager 0.12.0 removes the experimental bidirectional UI↔YAML
source-migration path. The product does not move Home Assistant HomeKit
Config Entries between `SOURCE_USER` and `SOURCE_IMPORT` and does not apply
Core patches for that purpose.

The release retains:

- read-only detection and display of UI- and YAML-configured HomeKit bridges;
- supported YAML configuration display, validation, projection and safe YAML
  filter management;
- Selection Drafts, Reconciliation, positive-list planning and guarded Native
  Apply with its existing write grants, locking, journaling, recovery,
  rollback and HAP checks.

The cleanup does not load, delete or migrate old experimental migration stores.
It does not change Config Entries, native filters, HAP persistence, pairings or
registry data. Existing HomeKit identities remain outside the cleanup scope.

Native Apply is not Source Migration: an explicitly confirmed Native Apply can
change the supported native filter of an existing bridge, subject to all
existing safety gates. A UI↔YAML source change is not offered.
