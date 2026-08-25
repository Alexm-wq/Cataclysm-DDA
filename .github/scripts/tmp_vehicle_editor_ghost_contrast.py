from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text(encoding='utf-8')
old = 'return std::make_pair( ghost_symbol, c_dark_gray );'
count = text.count(old)
if count != 3:
    raise SystemExit(f'Expected exactly 3 ghost returns, found {count}')
text = text.replace(old, 'return std::make_pair( ghost_symbol, c_light_gray );')
path.write_text(text, encoding='utf-8')
