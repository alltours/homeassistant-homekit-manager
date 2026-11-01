# HomeKit Manager 0.10.25 – Multi-Bridge Acceptance

## Stable policy

The stable integration is read-only by default and does not migrate HomeKit
sources. Any supported filter operation is bridge-bound and must not change
another Config Entry or HAP bridge.

## Result

The existing 0.10.15–0.10.23 experimental multi-bridge evidence remains
outside the Stable 0.10.25 release gate. A fresh two-bridge test through the
official unmodified Core and the stable Apply path was not completed here.

Status: **NOT VERIFIED** for the new release gate.

No multi-bridge operation was performed against production or against a
non-isolated Home Assistant instance.

