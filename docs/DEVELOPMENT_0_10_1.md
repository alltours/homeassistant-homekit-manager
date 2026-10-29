# 0.10.1 native test-mode checkpoint

This patch branch starts from published `v0.10.0`; it does not replace that tag.
The one-hour, in-memory, native Bridge filter authority is disabled by default.
The existing local grant route remains available; this mode does not read the
grant file while authorizing its selected Bridge. See
[`TEST_WRITE_MODE_0_10_1.md`](TEST_WRITE_MODE_0_10_1.md) for the trust boundary.

## Verified locally on 2026-10-28

- Isolated Home Assistant Core 2026.10.4 tests cover activation, admin WebSocket
  rejection, exact Entry binding, expiry, restart loss, revocation during a
  Bridge-lock wait, a successful filter-only Apply without a grant file, and
  duplicate/reconcile behavior through the existing writer tests.
- Chromium and WebKit browser fixtures cover explicit opt-in, cancellation,
  concrete Apply confirmation and revocation. They are not a live iPhone test.
- The Python runtime audit reports 39 previously reviewed Pillow 12.3.0 Core
  platform advisories under the pinned policy. New findings fail the gate.
- The builder produces byte-identical `0.10.1` ZIPs from two clean output
  directories. The release manifest is checked against every integration byte.
- A separate Core 2026.11.0b0 bootstrap with a loopback HAP testcontroller
  applied the four requested sensor exclusions through the Manager's native
  operation service. It verified Core's filter result, options persistence,
  post-Apply reload, stable existing MAC/AID/IID, and controller reconnect
  after a full second-process Core bootstrap. This is not Apple Home hardware.

## Productive boundary and next actions

The existing productive installation, Bridge and HomeKit persistence were not
modified. A new read-only browser session on 2026-10-29 confirmed Manager
0.10.0 and Core **2026.11.0b0**. Bridge `01KTHHYVPZ1T9804NQTJSCCXFJ` was
loaded as `SOURCE_USER`, mode `bridge`, port 21064. Its filter included the
`sensor` domain and had no entity exclusions. The Home Assistant backup UI
reported **zero available backups**, contradicting the earlier user report
that a new encrypted backup had been created. Treat backup availability and
restorability as unresolved; do not install until a complete current backup
and its off-host recovery key are verified. The native test-mode version gate
is extended only to the exact tested beta; YAML writing stays on 2026.10.4.

Before any productive installation, verify the backup, finish CI on the
committed patch branch, then obtain the user's
separate installation approval. Installation may require a controlled Core
restart; that needs its own explicit approval. Activation of the mode and the
first productive Apply are further, separate actions. The intended draft is
to exclude `sensor.blaue_tonne`, `sensor.braune_tonne`,
`sensor.gelbe_tonne`, and `sensor.graue_tonne` only after the installed code
and active filter are read and the exact diff is inspected. Apply must stop
for explicit user confirmation, including any Core-triggered HomeKit reload.
