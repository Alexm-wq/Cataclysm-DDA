from pathlib import Path

p = Path('.github/workflows/fix-refuel-target-interaction.py')
s = p.read_text()
old = '''# Make the tank stage explain double click again.\nrep(\n''' + "'''" + '''                        _( \\\"Click = select one   Ctrl+click = toggle   Shift+click = range\\\" ) );\\n''' + "'''" + ''',\n''' + "'''" + '''                        _( \\\"Click = select one   Ctrl+click = toggle   Shift+click = range   Double-click = continue\\\" ) );\\n''' + "'''" + ''',\n'tank stage double-click hint')\n'''
new = '''# Make only the first (tank-stage) copy explain double click; the source-stage\n# instruction intentionally remains unchanged.\nhint_old = '                        _( \\\"Click = select one   Ctrl+click = toggle   Shift+click = range\\\" ) );\\\\n'\nhint_new = '                        _( \\\"Click = select one   Ctrl+click = toggle   Shift+click = range   Double-click = continue\\\" ) );\\\\n'\nif s.count(hint_old) != 2:\n    raise SystemExit(f'tank stage double-click hint: expected 2 source copies, got {s.count(hint_old)}')\ns = s.replace(hint_old, hint_new, 1)\n'''
if old not in s:
    raise SystemExit('could not locate original tank-stage hint patch block')
p.write_text(s.replace(old, new, 1))
print('repaired temporary refuel patch script')
