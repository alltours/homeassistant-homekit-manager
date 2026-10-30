# HomeKit Manager 0.10.5 development checkpoint

## Starting point

- Base: released v0.10.4, commit `94d8e30` on `origin/main`.
- Branch: `feature/homekit-manager-0.10.5-production`.
- Productive Home Assistant, HomeKit configuration and pairing state were not modified.

## Completed, 2026-10-29

- Operation-bound filter writes and migration evidence were committed and pushed in `1c11bd1`.
- The backend resolves complete area, device and selection bulk scopes from its own current inventory. Hidden, disabled, diagnostic, configuration, missing-registry, missing-state, unsupported, conditional and unverified entities are excluded from automatic changes. Forged new includes are rejected by the server-side planner.
- The filter-reason wire field now matches the UI. A regression test covers the alias.
- Core 2026.11.0b0 compatibility classification is version-gated and includes the added ozone and sulphur-dioxide mappings; future Core versions remain unknown. Native filter-Apply beta validation and positive-list migration have separate capability gates.
- The devices view groups real areas and devices without synthetic cards for device-less entities, offers separate include/exclude actions and display options, shows scoped status/counts and keeps technical details collapsible.
- Full Core 2026.10.4 Python suite: 253 passed. Full Chromium/WebKit browser suite: 86 passed. The isolated full HA/HAP process restart and reconnect test passed in 104 seconds after raising the macOS subprocess timeout from 90 to 240 seconds. A separate local Core 2026.11.0b0 full-bootstrap attempt timed out after 240 seconds during its initial pair phase and is not counted as a pass; the GitHub Linux Core-beta-native pair/filter/reconnect job passed on the release candidate. Frontend unit, JS syntax, Ruff, Bandit, pip check and npm audit passed. A second ZIP build matched byte-for-byte.
- Release candidate `be6ef2426bcf43b7feaf035432b5f4dc00ef84c5` was pushed; draft PR #18 is open. Its final CI quality and browser jobs are still running. The productive installation was read-only checked: Manager 0.10.4 on Core 2026.11.0b0, one loaded native bridge, writer locked. No productive 0.10.5 test or installation occurred.
- Final PR #18 CI on `b71a7ad` passed quality, browser and Core-beta-native jobs; HACS and hassfest passed. The final diff review then found that a confirmed operation alone had inadvertently become production write authority. This violated the existing fail-closed default. The fallback authority was removed; without a time-limited test mode or local grant, Apply is blocked server-side. Targeted operation, grant, bulk and test-mode regression tests: 45 passed. Final CI must be rerun on the corrective commit before merge.

## Open release gates

1. Review the final CI quality and browser jobs, HACS/hassfest and dependency audit on the pushed release candidate. Address any findings without broadening the feature scope.
2. Review required PR approvals and branch protection before any merge or release; download and verify remote release assets only after a true GO.
3. Physical Apple Home validation and productive 0.10.5 installation are not authorized or claimed.

## Next concrete step

Wait for final PR CI on the checkpoint commit, inspect protection and reviews, then merge and publish only if every mandatory gate has evidence.
