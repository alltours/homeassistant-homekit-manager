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

## Productive boundary and next actions

The existing productive installation, Bridge and HomeKit persistence were not
modified. The live HA browser was inaccessible while the Mac was locked. The
last earlier read reported Core 2026.10.4 with a `2026.11.0b0` update in
progress, so the **currently running** Core version is unconfirmed. The test
mode remains hard blocked outside 2026.10.4. Do not relax that check without
reviewing and testing that Core version's HomeKit filter path.

Before any productive installation, verify the running Core version and
backup, finish CI on the committed patch branch, then obtain the user's
separate installation approval. Installation may require a controlled Core
restart; that needs its own explicit approval. Activation of the mode and the
first productive Apply are further, separate actions. The intended draft is
to exclude `sensor.blaue_tonne`, `sensor.braune_tonne`,
`sensor.gelbe_tonne`, and `sensor.graue_tonne` only after the installed code
and active filter are read and the exact diff is inspected. Apply must stop
for explicit user confirmation, including any Core-triggered HomeKit reload.
