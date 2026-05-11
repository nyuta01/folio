"""True when this product has at least one unit on hand."""

import json
import sys

inputs = json.loads(sys.argv[2])
stock = inputs.get("stock") or 0
print("true" if int(stock) > 0 else "false")
