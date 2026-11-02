#!/usr/bin/env python3
"""Create an offline, read-only HomeKit positive-list plan from an export."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load the pure planning module without importing Home Assistant's integration
# bootstrap.  This keeps the offline tool independent of a running Core and
# makes its read-only boundary explicit.
package = "custom_components.homekit_manager"
if package not in sys.modules:
    module = types.ModuleType(package)
    module.__path__ = [str(ROOT / "custom_components" / "homekit_manager")]
    sys.modules[package] = module

from custom_components.homekit_manager.positive_list_planning import build_positive_list_plan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    target_document = json.loads(args.target.read_text(encoding="utf-8"))
    target_ids = target_document.get("entity_ids", [])
    plan = build_positive_list_plan(
        target_ids,
        snapshot,
        target_source=target_document.get("source", "user_explicit_decision"),
    )
    encoded = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(encoded)
    return 0 if plan["summary"]["blocking_reason_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
