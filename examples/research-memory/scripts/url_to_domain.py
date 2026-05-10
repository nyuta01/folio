"""Extract a normalized hostname from a URL (offline)."""

from __future__ import annotations

import json
import sys
from urllib.parse import urlparse


def main() -> None:
    inputs = json.loads(sys.argv[2])
    url = inputs.get("url", "") or ""
    host = urlparse(url).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    print(host)


if __name__ == "__main__":
    main()
