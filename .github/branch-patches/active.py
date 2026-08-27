from __future__ import annotations

import os
import subprocess

# The branch-patch checkout is intentionally shallow.  Fetch exactly one more
# commit so the full migration staged in the parent can be reused verbatim.
subprocess.run(
    ["git", "fetch", "--deepen=1", "origin", os.environ["GITHUB_REF_NAME"]],
    check=True,
)
script = subprocess.check_output(
    ["git", "show", "HEAD^:.github/branch-patches/active.py"], text=True
)
old = '''    2,\n    "crafting group reset",\n)'''
new = '''    1,\n    "crafting group reset",\n)'''
if script.count(old) != 1:
    raise SystemExit(f"reset retry anchor: expected 1, found {script.count(old)}")
script = script.replace(old, new, 1)
exec(compile(script, ".github/branch-patches/active.py[parent]", "exec"))
