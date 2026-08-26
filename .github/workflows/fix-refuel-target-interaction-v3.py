from pathlib import Path

p = Path('.github/workflows/fix-refuel-target-interaction.py')
s = p.read_text()
old = '''def rep(old: str, new: str, label: str) -> None:\n    global s\n    count = s.count(old)\n    if count != 1:\n        raise SystemExit(f'{label}: expected 1 match, got {count}')\n    s = s.replace(old, new, 1)\n'''
new = '''def rep(old: str, new: str, label: str) -> None:\n    global s\n    count = s.count(old)\n    expected = 2 if label == 'tank stage double-click hint' else 1\n    if count != expected:\n        raise SystemExit(f'{label}: expected {expected} match(es), got {count}')\n    s = s.replace(old, new, 1)\n'''
if s.count(old) != 1:
    raise SystemExit(f'patch helper definition: expected 1 match, got {s.count(old)}')
p.write_text(s.replace(old, new, 1))
print('repaired refuel patch helper')
