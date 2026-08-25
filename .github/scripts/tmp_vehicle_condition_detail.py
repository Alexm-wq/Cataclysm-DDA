from pathlib import Path
p = Path('src/veh_interact.cpp')
s = p.read_text()
old = '''    const nc_color health_col = health >= 75 ? c_light_green : health >= 40 ? c_yellow : c_light_red;\n'''
new = '''    const nc_color health_col = editor_condition_color( vp );\n'''
if s.count(old) != 1:
    raise SystemExit(f'expected one health color anchor, found {s.count(old)}')
p.write_text(s.replace(old, new, 1))
