# HomeKit Manager 0.10.25 – Stable Release Gate

## Verified gates

- Version metadata and stable migration boundary: **CODE VERIFIED**
- 0.10.24 Stable CI `41294603808`: **CI VERIFIED**
- HACS/Hassfest `41294603782`: **CI VERIFIED**
- Python tests, frontend tests, Ruff and syntax in Stable CI: **CI VERIFIED**
- Chromium and WebKit in Stable CI: **CI VERIFIED**
- Reproducible release build: **TEST VERIFIED**
- Official Core 2026.10.4 real HTTP readiness: **TEST VERIFIED**
- Real isolated HAP pair/reconnect worker: **TEST VERIFIED**
- HAP loopback: 2 passed; YAML loopback: 1 passed; write-grant/operation: 18 passed: **TEST VERIFIED**
- Native migration disabled in Stable path: **CODE VERIFIED**
- Full local Stable collection: 341 collected, 339 passed, 2 failed in Chromium/WebKit backend worker: **FAILED** locally on macOS

## Open gates

- Real HACS UI installation and completed Config Flow: **BLOCKED**
- Upgrade with an existing Manager entry: **NOT VERIFIED**
- Fresh 25-plus-25 live HAP allowlist Apply: **NOT VERIFIED**
- Fresh two-bridge Stable Apply isolation: **NOT VERIFIED**

The local Chromium failure is a 75-second Node/Playwright subprocess timeout on
macOS (reproduced with Node 24.13.0 and Node 22.23.4); WebKit passes under Node
22. The previously completed Ubuntu 0.10.24 Browser CI job passed Chromium and
WebKit, but that is not a new 0.10.25 CI result.

## Decision

**CONDITIONAL GO** for a Stable release candidate limited to inventory,
diagnostics, planning, preview, export and explicitly authorized filter paths.

**NO-GO** for native UI↔YAML migration.

An unconditional GO requires completion of all open gates above. No official
release was published by this sprint.

