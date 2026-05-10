"""Count words in the body field (offline)."""

from __future__ import annotations

import json
import sys


def main() -> None:
    inputs = json.loads(sys.argv[2])
    body = inputs.get("body", "") or ""
    count = len([word for word in body.split() if word.strip()])
    print(count)


if __name__ == "__main__":
    main()
