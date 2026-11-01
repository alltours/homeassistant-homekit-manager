# HomeKit Manager 0.10.24 – Release Readiness

## Current decision

`CONDITIONAL GO` for a Stable read-only/planning release candidate.

`NO-GO` for claiming that the complete Stable regression is finished until the
new Stable CI workflow completes successfully.

## Release artifact

The deterministic local archive is:

`homekit-manager-0.10.24.zip`

SHA-256:

`121e22e10defae3b28b91cf88e2f6172cdfbcd045918e4be6c2b173f75f85fb4`

It contains 58 integration files and was produced byte-identically in two
independent builds.

## Required release gates

- Stable Python tests pass in CI.
- Stable frontend tests pass in CI.
- Chromium and WebKit pass in CI.
- HACS and Hassfest pass in CI.
- Release archive is reproducible.
- Native migration remains blocked.
- No experimental Core patch is part of the Stable workflow or release ZIP.

Until all gates are green, the correct release decision is `CONDITIONAL GO`,
not `GO`.
