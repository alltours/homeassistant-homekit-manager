# HomeKit Manager 0.10.31 – Reconciliation Finalization

## Scope

0.10.31 is an isolated development version for diagnosing the 0.10.30
`manager_native_mismatch` finding and preparing a future explicit HomeKit
positive-list migration. It does not change native HomeKit filters, Manager
decisions, Config Entries, pairings, HAP persistence or `.storage`.

## Mismatch semantics

The legacy `explicit_overrides` policy can contain native explicit selections
without corresponding Manager decisions. Those rows are unresolved metadata,
not automatically a native-versus-desired set conflict. A true set conflict is
classified separately when an include/exclude decision, positive-list set or
verified runtime set disagrees with the observed native set.

Both states remain fail-closed for a later write or migration. The diagnostic
classification is not a permission change.

## Audit target

The concrete target list is installation-specific and must be supplied from a
local file outside the public repository. The repository contains only the
generic [target schema](reconciliation/positive_list_target.schema.json). The
target is planning-only evidence and is never loaded as the Manager's stored
decision document or included in the integration ZIP.

## Offline plan

Create a plan from a read-only export without contacting Home Assistant:

```sh
python scripts/plan_positive_list.py \
  --snapshot /path/to/reconciliation.json \
  --target /path/outside/repository/approved_selection.json \
  --output /path/to/positive-list-plan.json
```

The command has no write-capable Home Assistant dependency. A non-zero exit
status means the plan is blocked. A plan with 23 KEEP rows is still not an
Apply authorization; every blocker must be reviewed and a separate later
release must explicitly authorize any productive migration.
