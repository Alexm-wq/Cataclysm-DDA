from __future__ import annotations

import os
import subprocess

# The full migration is three commits behind this retry wrapper.  Deepen only
# enough to recover it without changing the permanent branch-patch workflow.
subprocess.run(
    ["git", "fetch", "--deepen=3", "origin", os.environ["GITHUB_REF_NAME"]],
    check=True,
)
script = subprocess.check_output(
    ["git", "show", "HEAD^^^:.github/branch-patches/active.py"], text=True
)
old = '''    2,\n    "crafting group reset",\n)'''
new = '''    1,\n    "crafting group reset",\n)'''
if script.count(old) != 1:
    raise SystemExit(f"reset retry anchor: expected 1, found {script.count(old)}")
script = script.replace(old, new, 1)
exec(compile(script, ".github/branch-patches/active.py[original]", "exec"))
