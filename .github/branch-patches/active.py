from __future__ import annotations

from urllib.request import urlopen

ORIGINAL_MIGRATION = "5352c3ef99cfe87ab42fe4052cee2c063336debc"
url = (
    "https://raw.githubusercontent.com/Alexm-wq/Cataclysm-DDA/"
    f"{ORIGINAL_MIGRATION}/.github/branch-patches/active.py"
)
with urlopen(url, timeout=30) as response:
    script = response.read().decode("utf-8")

old = '''    2,\n    "crafting group reset",\n)'''
new = '''    1,\n    "crafting group reset",\n)'''
if script.count(old) != 1:
    raise SystemExit(f"reset retry anchor: expected 1, found {script.count(old)}")
script = script.replace(old, new, 1)
exec(compile(script, ".github/branch-patches/active.py[original]", "exec"))
