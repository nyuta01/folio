"""Map a country name to an ISO-3166-1 alpha-2 code (offline)."""

from __future__ import annotations

import json
import sys

ISO_BY_NAME = {
    "Japan": "JP",
    "United States": "US",
    "USA": "US",
    "Sweden": "SE",
    "Australia": "AU",
    "Germany": "DE",
    "France": "FR",
    "United Kingdom": "GB",
    "UK": "GB",
}


def main() -> None:
    inputs = json.loads(sys.argv[2])
    country = inputs.get("country", "")
    print(ISO_BY_NAME.get(country, "??"))


if __name__ == "__main__":
    main()
