"""Length of the tags array; 0 when null or missing."""

import json
import sys

inputs = json.loads(sys.argv[2])
tags = inputs.get("tags") or []
print(len(tags))
