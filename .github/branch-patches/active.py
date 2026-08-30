from pathlib import Path

p = Path("src/ui_helpers/controls/world_viewport.cpp")
s = p.read_text(encoding="utf-8")
old = '#include <algorithm>\n#include <limits>\n'
new = '#include <algorithm>\n#include <cstdlib>\n#include <limits>\n'
if s.count(old) != 1:
    raise RuntimeError(f"expected one viewport include block, found {s.count(old)}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
Path('/tmp/branch_patch_commit_message').write_text(
    'Include std::abs dependency for viewport zoom [skip ci]\n', encoding='utf-8'
)
