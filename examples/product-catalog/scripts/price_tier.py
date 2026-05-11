"""Coarse price bucket - budget / mid / premium."""

import json
import sys

inputs = json.loads(sys.argv[2])
price = float(inputs.get("price_usd") or 0)
if price < 20:
    print("budget")
elif price < 100:
    print("mid")
else:
    print("premium")
