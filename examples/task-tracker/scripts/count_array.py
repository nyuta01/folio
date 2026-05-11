"""Length of the single input field, treated as an array.

Folio python kind contract:
  argv[1] = record id
  argv[2] = JSON string of inputs declared on the derivation
  stdout  = the value for the target field

The derivation declares exactly one input; we count its length. None
and missing values both count as zero.
"""

import json
import sys

inputs = json.loads(sys.argv[2])
# A derivation that uses this script declares exactly one input.
(value,) = inputs.values()
if value is None:
    print(0)
else:
    print(len(value))
