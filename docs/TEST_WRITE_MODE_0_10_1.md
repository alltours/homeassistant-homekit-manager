# HomeKit Manager 0.10.1: optional native filter test mode

This document describes a **development candidate**, not an instruction to
install it on an existing Home Assistant system. Installation and the first
productive Apply need separate, explicit approval. The published 0.10.0 release
continues to require its local grant file.

## Authorization boundary

The backend starts locked. A Home Assistant administrator can open
**Settings → Configuration → Productive filter test mode** and confirm the
selected Bridge's exact Entry ID. Activation is accepted only when the current
Core version is **2026.10.4**, the selected existing HomeKit Config Entry is
loaded, its source is `user`, its mode is `bridge`, the inventory fingerprint
still matches, and no unresolved operation for that Entry is applying or has
an unknown outcome. The test mode does not support YAML or accessory Entries.

The authority exists only in process memory for **60 minutes**. It is bound to
one Entry ID, source `user`, Core version and the filter writer. It is lost on
Home Assistant restart, expires automatically and can be revoked immediately
from the same Settings card. The local `.homekit_manager_write_grant.json` is
**not read or required** while this mode authorizes the selected Bridge. The
older local-grant route remains available independently for sites that use it.

Unlike the local grant, this mode gives an authenticated Home Assistant
administrator the ability to enable the filter writer from the UI. It does not
provide a second, out-of-band approval factor. Protect HA administrator
sessions accordingly. The UI's activation confirmation is distinct from the
confirmation of each specific filter operation.

Activation alone does not change Core HomeKit configuration, reload a Bridge,
reset HAP identity or alter pairings. It does not bypass the operation writer:
the server checks the exact Bridge/source, admin role, complete Entry revision,
Core filter schema, filter-only scope, operation ID and current authority.
The authority is rechecked after waiting for the Bridge lock immediately
before Core's `async_update_entry` call. The operation journal stores the
previous filter; it prevents duplicate operation IDs and supports read-only
reconciliation. An Apply through Core may trigger a HomeKit Entry reload.
Neither an isolated HAP test nor an `options` verification proves physical
Apple Home pairing preservation.

## Controlled use after an approved installation

1. Verify the **running** Core and Manager versions and a complete restorable
   backup, including the site's HomeKit persistence. If a Core update is in
   progress, stop. If Core is not 2026.10.4, the mode remains blocked until
   that version's HomeKit filter path is reviewed and isolated tests pass.
2. Confirm the selected Bridge Entry ID, `user` source, `bridge` mode and
   currently active filter. Prepare the intended entity changes as a draft.
3. In Settings → Configuration, activate the one-hour test mode for this Bridge.
   A new operation plan is required after activation. Inspect the exact diff,
   expected selection, Entry ID, source and operation ID.
4. Obtain separate approval for the **specific productive Apply**, including
   the HomeKit reload that Core may perform. Do not click Apply without it.
5. After an authorized Apply, inspect the verified Core options, operation
   journal, Bridge state and paired controller separately. Revoke the test
   mode immediately. An `unknown_outcome` must be reconciled read-only; never
   retry the operation automatically.

## Recovery

Click **Test mode revoke** to reject future operations. Revocation cannot undo
an update that Core already performed. If a connection is lost, use operation
status and read-only reconcile before taking any action. To reverse a filter
change, compare the active Entry's complete revision with the journal's saved
preimage and obtain separate authorization for a new, explicit operation.
Do not restore or modify `.storage/homekit.*` merely to reverse a filter.
Use a full Home Assistant backup only under the site's emergency restoration
procedure. No physical Apple Home pairing guarantee is made.
