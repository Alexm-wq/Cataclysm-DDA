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
new_defs = '''defs: dict[str, dict] = {}\nfor _, _, obj in records:\n    if obj.get("type") not in {"recipe", "practice", "nested_category"}:\n        continue\n    for key in ("abstract", "id"):\n        value = obj.get(key)\n        if isinstance(value, str):\n            defs.setdefault(value, obj)\n    result = obj.get("result")\n    if isinstance(result, str):\n        defs.setdefault(result, obj)\n        variant = obj.get("variant")\n        if isinstance(variant, str) and variant:\n            defs.setdefault(result + "_" + variant, obj)\n        suffix = obj.get("id_suffix")\n        if isinstance(suffix, str) and suffix:\n            defs.setdefault(result + "_" + suffix, obj)\n'''
if script.count(old_defs) != 1:
    raise SystemExit(f"recipe inheritance anchor: expected 1, found {script.count(old_defs)}")
script = script.replace(old_defs, new_defs, 1)

old_suffix = '''        suffix = effective.get("id_suffix")\n        if isinstance(suffix, str) and suffix:\n            rid += "_" + suffix\n'''
new_suffix = '''        # id_suffix is an instruction applied by this JSON object; unlike\n        # stored recipe fields it is not inherited from copy-from.\n        suffix = raw.get("id_suffix")\n        if isinstance(suffix, str) and suffix:\n            rid += "_" + suffix\n'''
if script.count(old_suffix) != 1:
    raise SystemExit(f"id suffix anchor: expected 1, found {script.count(old_suffix)}")
script = script.replace(old_suffix, new_suffix, 1)

exec(compile(script, ".github/branch-patches/active.py[original]", "exec"))
