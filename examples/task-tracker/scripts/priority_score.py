"""Numeric weight for sorting tasks by priority.

Folio python kind contract:
  argv[1] = record id
  argv[2] = JSON string of inputs declared on the derivation
  stdout  = the value for the target field
"""

import json
import sys

WEIGHTS = {"P0": 100, "P1": 10, "P2": 1, "P3": 0}

inputs = json.loads(sys.argv[2])
print(WEIGHTS.get(inputs.get("priority", ""), 0))
