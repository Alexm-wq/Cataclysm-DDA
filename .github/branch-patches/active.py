from __future__ import annotations

import subprocess

ORIGINAL_MIGRATION = "5352c3ef99cfe87ab42fe4052cee2c063336debc"

# Fetch and execute the exact original migration rather than relying on relative
# ancestry; each retry commit changes HEAD^ depth, while this SHA is immutable.
subprocess.run(
    ["git", "fetch", "origin", ORIGINAL_MIGRATION],
    check=True,
)
script = subprocess.check_output(
    ["git", "show", f"{ORIGINAL_MIGRATION}:.github/branch-patches/active.py"],
    text=True,
)
old = '''    2,\n    "crafting group reset",\n)'''
new = '''    1,\n    "crafting group reset",\n)'''
if script.count(old) != 1:
    raise SystemExit(f"reset retry anchor: expected 1, found {script.count(old)}")
script = script.replace(old, new, 1)
exec(compile(script, ".github/branch-patches/active.py[original]", "exec"))
