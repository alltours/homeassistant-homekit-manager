# HomeKit Manager 0.10.24 – Stable Scope

## Product boundary

0.10.24 is a standalone HACS custom integration for the official Home
Assistant Core. It does not require a modified Core checkout and does not
perform native UI↔YAML source migration.

## Supported stable functions

The stable product provides:

- HomeKit Bridge discovery and source-aware inventory.
- Device, area, floor and entity views.
- Search, pagination and filter previews.
- Positive-list planning with explicit include/exclude decisions.
- Draft validation, preview and export.
- Read-only runtime diagnostics and HAP evidence where Core exposes it.
- Administrator-only WebSocket commands and panel registration.
- Explicitly authorized, revision-bound filter operations where the official
  Core contract and local write grant are both valid.

## Permanently excluded from stable scope

- UI↔YAML source migration.
- Config Entry source mutation.
- Pairing recreation or pairing migration.
- HAP identity migration.
- Experimental Core journals or rollback executors.
- Implicit retries after an unknown Apply outcome.

The migration plan and status endpoints are retained only as read-only,
fail-closed compatibility reporting. They never mutate Home Assistant state.

## Write policy

The legacy direct Apply path is disabled. A filter write requires an
administrator, an exact server-held operation, a complete revision match, a
concrete confirmation and a separate narrow local grant or isolated test
authority. Missing or invalid authority keeps the operation in preview/export
mode.

An empty positive list is rejected because Home Assistant Core interprets an
empty HomeKit filter as broad publication. Ambiguous YAML provenance, mixed
native/YAML reload scope and unsupported Core versions remain read-only.
