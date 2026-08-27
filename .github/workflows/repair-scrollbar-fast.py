from pathlib import Path

out_path = Path('src/output.cpp')
scroll_path = Path('src/ui_helpers/primitive/scrollbar.cpp')
out = out_path.read_text()
scroll = scroll_path.read_text()

marker = 'void multiline_list::activate_entry'
misplaced = scroll.find(marker)
if misplaced < 0:
    raise SystemExit('expected misplaced multiline_list block not found')

# Everything after this marker was accidentally captured from the original
# contiguous output.cpp section. Put it immediately before the first remaining
# multiline_list method in output.cpp and keep scrollbar.cpp scrollbar-only.
tail = scroll[misplaced:].rstrip() + '\n\n'
scroll = scroll[:misplaced].rstrip() + '\n'
insert_at = out.find('multiline_list::')
if insert_at < 0:
    raise SystemExit('remaining multiline_list implementation not found')
line_start = out.rfind('\n', 0, insert_at) + 1
out = out[:line_start] + tail + out[line_start:]

if '#include "cata_utility.h"' not in scroll:
    scroll = scroll.replace('#include <cmath>\n\n', '#include <cmath>\n\n#include "cata_utility.h"\n', 1)

out_path.write_text(out)
scroll_path.write_text(scroll)

assert marker not in scroll
assert out.count(marker) == 1
assert 'scrollbar::scrollbar()' not in out
assert scroll.count('scrollbar::scrollbar()') == 1
print('repaired current-tree scrollbar extraction')
