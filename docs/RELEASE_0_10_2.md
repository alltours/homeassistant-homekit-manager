# HomeKit Manager 0.10.2

## Fix

Background inventory updates previously rebuilt the entire panel while a
native filter dropdown was focused. Removing the active `<select>` closed its
browser menu before a normal selection was possible. Version 0.10.2 defers
passive view replacement until selection or focus leaves the dropdown. It also
restores focus after an explicit selection. Device filters and the diagnostic
filter share this fix. No HomeKit writer, authorization or configuration source
behavior changed from 0.10.1.

The regression test first failed on the 0.10.1 source because a focused select
was detached by a background refresh. It passes with the fix in Chromium and
WebKit. Additional tests cover waiting with the menu focused, an inventory
event, option selection, another filter, keyboard focus navigation, an outside
click, diagnostic filtering and mobile touch. Native menu appearance itself
remains subject to browser and operating-system behavior. The productive HA
screen could not be inspected during this work because the Mac browser was
locked; the reproduction and fix were verified in isolated browser fixtures.

## Compatibility and safety

The 0.10.1 capability boundaries are unchanged: native `SOURCE_USER` Bridge
filter writing is version-pinned to Core 2026.10.4 and 2026.11.0b0; supported
YAML writing remains pinned to 2026.10.4. Accessory mode, source migration and
unsupported YAML structures remain blocked. The optional one-hour native
test mode stays disabled by default and requires administrator, exact Bridge
and diff confirmation. Installing this patch does not activate it. Physical
Apple Home pairing preservation is not claimed.

## Upgrade and rollback

Install the ZIP only after a separately approved, restorable HA backup. Replace
only `custom_components/homekit_manager` and restart Core only with explicit
authorization. After restart, check the Manager version and dropdown behavior
read-only before enabling any write mode. To roll back before any Apply,
restore the verified 0.10.1 integration files and restart only with approval.
Code rollback after an Apply does not reverse a Core filter; reconcile the
operation and use a separately confirmed filter operation if reversal is safe.
Never edit `.storage/homekit.*` to undo a filter change.
