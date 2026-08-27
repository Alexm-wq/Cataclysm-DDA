from __future__ import annotations

import subprocess

# Reuse the full guarded migration staged in the parent commit; this wrapper
# only corrects the branch-specific reset anchor count discovered by the first
# dry run.  Keeping the migration itself immutable makes the retry auditable.
script = subprocess.check_output(
    ["git", "show", "HEAD^:.github/branch-patches/active.py"], text=True
)
old = '''    2,\n    "crafting group reset",\n)'''
new = '''    1,\n    "crafting group reset",\n)'''
if script.count(old) != 1:
    raise SystemExit(f"reset retry anchor: expected 1, found {script.count(old)}")
script = script.replace(old, new, 1)
exec(compile(script, ".github/branch-patches/active.py[parent]", "exec"))
