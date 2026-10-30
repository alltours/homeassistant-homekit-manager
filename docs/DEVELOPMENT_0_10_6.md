# HomeKit Manager 0.10.6 development checkpoint

## Basis und Ziel

- Branch `feature/homekit-manager-0.10.6-ux` from published `v0.10.5`
  (`9cf373300aa67ba14a4080c1868bf1a608e56724`).
- Scope: compact UX only; no backend filter, authorization or pairing changes.
- Productive Home Assistant was not modified. Its browser was unavailable while
  the Mac was locked. The user said access may become available later.

## Isolated visual evidence

- Chromium dark fixture, 390 × 844: two closed area cards measured 290.58 px
  each before and 119.84 px each after. This is 170.74 px, or 58.8%, less
  height. See [raw measurements](screenshots/0.10.6/measurements.json).
- With the same viewport, no complete area card fit before; two fit after.
- The separate display-options card measured 261 px before; the collapsed
  filter panel measures 58 px after. Options remain reachable inside it.
- [Before](screenshots/0.10.6/before-devices.png) and
  [after](screenshots/0.10.6/after-devices.png) captures show the devices view.
  The directory includes before/after captures for HomeKit, devices, a closed
  area, an expanded area, a closed device, an expanded device, filter panel,
  empty and populated Changes, and Settings. Reproduce them with
  `python3 -m http.server 4173 --bind 127.0.0.1` and
  `node scripts/capture_ux_0_10_6.mjs`. They are fixture captures, not
  evidence of productive installation.

## Release gates still to close

- Local Python suite: 254 passed on Core 2026.10.4, including isolated
  authenticated backend/browser integration. New backend logic was not added.
- Local Chromium/WebKit browser suite: 102 passed, including 320/375/390/393,
  tablet/desktop layout, filter state, draft and write-mode regressions,
  5,000 entities and 5,000 device references.
- Frontend unit, JavaScript syntax, integration-source Ruff, Bandit, `pip
  check` and `npm audit --audit-level=high` passed. A broader ad hoc Ruff run
  over all historical test files reports six unrelated existing test-style
  findings; the repository's CI-scoped Ruff check remains the release gate.
- Two independent local archive builds produced the same SHA-256:
  `32358f816f8a3200af2b697c57b9b9db5c049730267afc6bb2c0c1e4af9f58d0`.
- The five-minute browser stability observation is running.
- HACS/hassfest and final CI remain to be verified on the pushed commit.
- PR review and merge according to repository rules; release only after GO.
