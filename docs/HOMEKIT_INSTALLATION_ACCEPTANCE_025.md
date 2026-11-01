# HomeKit Manager 0.10.25 – Installation Acceptance

## Scope

This document covers a real isolated Home Assistant Core 2026.10.4 start and
the stable integration package. It does not enable native UI↔YAML migration.

## Environment

- Core: Home Assistant 2026.10.4
- Python: 3.14.9
- OS: macOS arm64
- Core executable: `/Users/felixalshut/Documents/ChatGPT/.hkm-core-314/bin/hass`
- Configuration: isolated temporary directory under `/tmp/hkm025-*`
- Package: reproducible HomeKit Manager archive
- Experimental Core patch: not installed

## Evidence

The real Core process reached HTTP readiness on an isolated loopback port and
returned `302 Found` to `/onboarding.html`. The independent full-Core HAP worker
also created a synthetic bridge, paired an `aiohomekit` controller and
reconnected it in a second Core process.

Status: **TEST VERIFIED** for Core/HAP bootstrap.

The first CLI attempt exposed a five-minute pending-HTTP-confirmation timeout.
That was an onboarding/configuration issue and was not counted as a successful
installation. A browser onboarding session was started against the isolated
instance; no productive account or service was involved.

The complete HACS UI installation, Config Flow completion and panel verification
could not be completed after the isolated HTTP process restarted during the
pending configuration transition.

Status: **BLOCKED** for full installation acceptance.

A second isolated CLI run installed the 0.10.25 archive under
`config/custom_components/homekit_manager`, loaded it in the official Core
process and reached HTTP readiness (`302 Found` to onboarding). The process
was then stopped as a test service. This confirms archive loading and Core
startup, but not a completed authenticated UI Config Flow.

## Required reproduction

```text
python3 scripts/build_release.py --output /tmp/hkm025-release
unzip /tmp/hkm025-release/homekit-manager-0.10.25.zip -d <isolated-config>
<official-core-venv>/bin/hass -c <isolated-config> --skip-pip --log-no-color
```

No production configuration, pairing or HAP persistence was used.

