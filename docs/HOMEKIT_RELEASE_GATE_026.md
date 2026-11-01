# HomeKit Manager 0.10.26 – Release Gate

## Gate matrix

| Gate | Status | Evidence / limitation |
|---|---|---|
| A – official Core environment | **TEST VERIFIED** | Three fresh full-Core starts with HTTP/WebSocket, two HAP bridges and restart reconnects. |
| B – HACS installation | **BLOCKED** | HACS UI/authenticated onboarding was not executed; package-level custom integration loading was verified separately. |
| C – persistent upgrade | **TEST VERIFIED** for isolated 0.10.24→0.10.26 package replacement; **NOT VERIFIED** for HACS UI upgrade | Existing manager/HomeKit state and pairings survived a full Core restart. |
| D – real HAP Apply | **TEST VERIFIED** | Authenticated WebSocket plan/apply and independent aiohomekit comparison, three runs. |
| E – multi-bridge Apply isolation | **TEST VERIFIED** | Bridge B remained unchanged and reachable; exactly two HomeKit entries remained. |
| F – Stable regression | **FAILED** locally / **CI VERIFIED** only after the new job runs | 340 passed, 1 Chromium backend test failed locally under Node 24; WebKit passed. Existing Ubuntu Node 22 CI was green before this branch's new acceptance job. |
| G – CI | **NOT VERIFIED** | New acceptance workflow change requires a post-push run. Existing 0.10.25 stable CI was green, but it is not evidence for this commit. |
| H – reproducible release artifact | **TEST VERIFIED** | Two independent builds byte-identical; SHA-256 `9db7085b99adb8d4e20b6a63a0d8b4dc333140edcfcf23878b598daed337f6dc`; 58 integration files plus manifest. |

## Stable security boundary

Native UI↔YAML migration remains disabled. There is no production source
mutation, pairing reset, HAP persistence rewrite, or automatic re-pairing.
The tested Apply path is narrow, revision-bound, authenticated, grant-gated,
and independently verified against live HAP accessories.

## Release decision

**CONDITIONAL GO – limited Stable scope only.**

The read-only inventory/diagnostics/planning/export functionality and the
tested existing SOURCE_USER filter Apply path are technically supported by the
local acceptance evidence. A full release GO is not allowed yet because Gate B
(real HACS UI installation) and the new Gate G CI run are not verified. The
local macOS Chromium failure also prevents declaring the complete local Stable
suite green, although the known Ubuntu Node 22 CI baseline was green.

## Required before full GO

1. Execute and inspect the new official-Core acceptance GitHub Actions job.
2. Execute an authenticated HACS UI installation in an isolated browser/Core
   environment, or explicitly remove HACS UI installation from the release
   claim.
3. Repeat the persistent 0.10.24→0.10.26 upgrade through the accepted HACS
   update path.
4. Resolve or formally platform-scope the Node 24/macOS Chromium timeout; do
   not relabel it as a product pass.

No official release or merge is performed by this sprint.
