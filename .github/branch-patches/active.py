from __future__ import annotations

from urllib.request import urlopen

ORIGINAL_MIGRATION = "5352c3ef99cfe87ab42fe4052cee2c063336debc"
url = (
    "https://raw.githubusercontent.com/Alexm-wq/Cataclysm-DDA/"
    f"{ORIGINAL_MIGRATION}/.github/branch-patches/active.py"
)
with urlopen(url, timeout=30) as response:
    script = response.read().decode("utf-8")

old_reset = '''    2,\n    "crafting group reset",\n)'''
new_reset = '''    1,\n    "crafting group reset",\n)'''
if script.count(old_reset) != 1:
    raise SystemExit(f"reset retry anchor: expected 1, found {script.count(old_reset)}")
script = script.replace(old_reset, new_reset, 1)

old_defs = '''defs: dict[str, dict] = {}\nfor _, _, obj in records:\n    for key in ("abstract", "id"):\n        value = obj.get(key)\n        if isinstance(value, str):\n            defs.setdefault(value, obj)\n    result = obj.get("result")\n    if isinstance(result, str):\n        defs.setdefault(result, obj)\n'''
new_defs = '''defs: dict[str, dict] = {}\nfor _, _, obj in records:\n    # Recipe copy-from names live in the recipe inheritance namespace.  Item,\n    # furniture, mutation, etc. ids frequently collide with recipe result ids\n    # and must never become recipe parents.\n    if obj.get("type") not in {"recipe", "practice", "nested_category"}:\n        continue\n    for key in ("abstract", "id"):\n        value = obj.get(key)\n        if isinstance(value, str):\n            defs.setdefault(value, obj)\n    result = obj.get("result")\n    if isinstance(result, str):\n        defs.setdefault(result, obj)\n'''
if script.count(old_defs) != 1:
    raise SystemExit(f"recipe inheritance anchor: expected 1, found {script.count(old_defs)}")
script = script.replace(old_defs, new_defs, 1)

exec(compile(script, ".github/branch-patches/active.py[original]", "exec"))
