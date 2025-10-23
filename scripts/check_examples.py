#!/usr/bin/env python3
import glob
import zipfile
import sys

whls = sorted(glob.glob("dist/*.whl"))
if not whls:
    sys.exit("ERROR: no wheel built in dist/")

wh = whls[0]
print("Inspecting", wh)

with zipfile.ZipFile(wh) as z:
    files = [n for n in z.namelist() if n.startswith("team_digest/examples/")]
    print("\n".join(files) or "NO_EXAMPLES_FOUND")
    if not files:
        sys.exit("ERROR: examples/ missing from wheel")
