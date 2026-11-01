# HomeKit Manager 0.10.24 – Stable Security Audit

## Result

The stable integration does not execute the experimental native source
migration. The production write boundary remains fail-closed unless the
explicit operation and authorization checks succeed.

## Verified controls

- Config Flow creates only the Manager entry and does not create a HomeKit
  Bridge.
- WebSocket commands require Home Assistant administrator access.
- Bridge selection is bound to a concrete Config Entry ID.
- Plans include a source revision and are rejected after external changes.
- Apply requires the exact operation ID and explicit confirmation.
- The write grant is bridge-bound, source-bound, time-limited and restricted
  to filter fields.
- YAML writes reject ambiguous includes, symlinks, unsafe permissions,
  comments in the edited filter and unsupported Core schemas.
- Native source migration is always reported as blocked.
- Pairing data and native HAP persistence are outside the stable write path.
- No automatic Apply retry is performed after an unknown outcome.

## Remaining limitations

The filter writer necessarily relies on Home Assistant's supported Config Entry
option update path and the HomeKit reload behavior of the supported Core
version. It is not a source migration transaction and it does not claim
cross-store atomicity.

Apple Home acceptance, physical storage failure and production deployment are
outside this local validation.
