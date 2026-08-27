from pathlib import Path
import subprocess

BASE = '67a68e73e0d2d6c4473a1d994517cb2a66285e61'
old = subprocess.check_output(['git', 'show', f'{BASE}:src/output.cpp'], text=True)

start = old.find('scrollbar::scrollbar()')
end = old.find('void multiline_list::activate_entry', start)
if start < 0 or end < 0:
    raise SystemExit('unable to locate original scrollbar implementation block')
scrollbar_methods = old[start:end].rstrip()

# Restore output.cpp from the known-good pre-refactor source, removing only the
# contiguous scrollbar implementation block. This guarantees no neighboring
# multiline_list implementation was accidentally moved.
repaired_output = old[:start] + old[end:]
Path('src/output.cpp').write_text(repaired_output)

scrollbar_cpp = '''#include "ui_helpers/primitive/scrollbar.h"\n\n#include <algorithm>\n#include <cmath>\n\n#include "cata_utility.h"\n#include "input_context.h"\n#include "output.h"\n\n''' + scrollbar_methods + '\n'
Path('src/ui_helpers/primitive/scrollbar.cpp').write_text(scrollbar_cpp)

assert 'void multiline_list::activate_entry' not in scrollbar_cpp
assert 'scrollbar::scrollbar()' not in repaired_output
assert repaired_output.count('void multiline_list::activate_entry') == 1
assert scrollbar_cpp.count('scrollbar::scrollbar()') == 1
print('repaired scrollbar extraction boundaries')
