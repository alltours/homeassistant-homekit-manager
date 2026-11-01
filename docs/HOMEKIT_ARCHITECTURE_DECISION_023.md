# HomeKit Manager 0.10.23 – Architecture Decision

## Decision matrix

| Variant | Safety | HACS installability | Core updateability | Product recommendation |
|---|---|---|---|---|
| A: HACS manager, no native migration | High within supported APIs | High | High | GO for stable product |
| B: HACS manager plus pinned experimental Core | Conditional; fail-closed but private APIs remain | Low/complex | Low | NO-GO for production; lab only |
| C: official Home Assistant Core API | Highest potential if contract is accepted and tested | Manager remains HACS-installable after minimum Core version | Highest after upstream maintenance | Recommended long-term path |

## Decision

Freeze native migration as an experimental research branch. Continue the stable Manager independently. Transfer the native-migration work into an upstream Core API proposal; do not broaden the private-API patch until the contract is accepted.

## Why additional tests are not enough

Tests can improve evidence for pairing, HAP structure, allowlists, and crash outcomes. They cannot make independent Config Entry, YAML, HAP, and journal stores one atomic transaction, nor can they guarantee a custom integration runs before native reconciliation on every future Core release. Those are architecture constraints.

## Product answers

* Stable Manager without native migration: suitable for production release preparation (`GO`, subject to ordinary release gates).
* Native migration on the experimental Core: technically useful and fail-closed in tested cases, but not production-ready (`NO-GO`).
* Native migration without an official Core API: not long-term maintainable at acceptable update risk (`NO-GO`).
* Official Core API: technically necessary for a durable product implementation, not merely desirable.
