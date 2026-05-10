"""Format a checklist [{label, done}, ...] as 'done/total' (offline)."""

from __future__ import annotations

import json
import sys


def main() -> None:
    inputs = json.loads(sys.argv[2])
    items = inputs.get("checklist") or []
    total = len(items)
    done = sum(1 for item in items if isinstance(item, dict) and item.get("done"))
    print(f"{done}/{total}")


if __name__ == "__main__":
    main()
