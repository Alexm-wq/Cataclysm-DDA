from pathlib import Path
import subprocess

# The full guarded migration is in the immediately preceding staging commit.
# Keep this correction tiny: deepen one commit, load that script, and fix the
# three guard assumptions that become ambiguous/redundant after earlier edits.
subprocess.run(
    ["git", "fetch", "--deepen=1", "origin", "mouse-inventory-0-i-test"],
    check=True,
    stdout=subprocess.DEVNULL,
)
script = subprocess.check_output(
    ["git", "show", "HEAD^:.github/branch-patches/active.py"], text=True
)

script = script.replace(
    "def replace_between(path: str, start: str, end: str, new: str) -> None:\n",
    "def replace_all(path: str, old: str, new: str) -> None:\n"
    "    p = Path(path)\n"
    "    text = p.read_text()\n"
    "    count = text.count(old)\n"
    "    if count < 1:\n"
    "        raise RuntimeError(f'{path}: expected at least one match, found {count}')\n"
    "    p.write_text(text.replace(old, new))\n\n\n"
    "def replace_between(path: str, start: str, end: str, new: str) -> None:\n",
    1,
)

script = script.replace(
    '''replace_once(\n    "src/construction_ui.cpp",\n    ''' + "'''    if( palette_window && operation == construction_operation::build ) {\\n'''" + ''',\n    ''' + "'''    if( palette_window && operation != construction_operation::remove ) {\\n'''" + '''\n)''',
    '''replace_all(\n    "src/construction_ui.cpp",\n    ''' + "'''    if( palette_window && operation == construction_operation::build ) {\\n'''" + ''',\n    ''' + "'''    if( palette_window && operation != construction_operation::remove ) {\\n'''" + '''\n)''',
    1,
)

# The first selection-path migration now intentionally handles both mouse and
# keyboard paths, so remove the redundant second guarded replacement.
start = script.find("# There is a second keyboard selection path with the same assignment.\n")
if start >= 0:
    end = script.find("replace_once(\n    \"src/construction_ui.cpp\",\n    '''        if( contextual_result.type", start)
    if end < 0:
        raise RuntimeError("could not locate end of redundant keyboard-selection patch")
    script = script[:start] + script[end:]

# draw_header() is replaced wholesale earlier and already contains this change.
redundant = '''# Avoid stale selection on operation switches in compact layouts and make the\n# palette header/filters redraw immediately.\nreplace_once(\n    "src/construction_ui.cpp",\n    ''' + "'''    if( compact && operation == construction_operation::build ) {\\n'''" + ''',\n    ''' + "'''    if( compact && operation != construction_operation::remove ) {\\n'''" + '''\n)\n\n'''
script = script.replace(redundant, "", 1)

exec(compile(script, "construction_catalog_semantic_cleanup.py", "exec"))
