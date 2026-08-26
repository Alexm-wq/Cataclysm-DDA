from pathlib import Path

p = Path('.github/workflows/polish-reshape-toolbar.py')
s = p.read_text()
old = "\npreserve toolbar dropdown over live preview')"
new = "\n'preserve toolbar dropdown over live preview')"
if old not in s:
    raise SystemExit('broken live-preview label not found')
s = s.replace(old, new, 1)
p.write_text(s)
print('repaired polish helper quoting')
