from pathlib import Path
import subprocess

# Re-run the original full migration with its intentionally repeated UI call
# sites made explicit.  This runner does not build the game; it only applies
# guarded source edits and lets the permanent workflow run git diff --check.
subprocess.run(
    ["git", "fetch", "--deepen=2", "origin", "mouse-inventory-0-i-test"],
    check=True,
    stdout=subprocess.DEVNULL,
)
script = subprocess.check_output(
    ["git", "show", "HEAD^^:.github/branch-patches/active.py"], text=True
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

# This predicate is used by both pointer and keyboard palette routing.
old = '''replace_once(\n    "src/construction_ui.cpp",\n    ''' + "'''    if( palette_window && operation == construction_operation::build ) {\\n'''" + ''',\n    ''' + "'''    if( palette_window && operation != construction_operation::remove ) {\\n'''" + '''\n)'''
new = old.replace("replace_once(", "replace_all(", 1)
if old not in script:
    raise RuntimeError("palette routing migration block not found")
script = script.replace(old, new, 1)

# last_construction is updated from both mouse and keyboard selection paths.
old = '''replace_once(\n    "src/construction_ui.cpp",\n    ''' + "'''            uistate.last_construction = selected_group;\\n            refresh_active_target();\\n'''" + ''',\n    ''' + "'''            if( operation == construction_operation::build ) {\\n                uistate.last_construction = selected_group;\\n            }\\n            refresh_active_target();\\n'''" + '''\n)'''
new = old.replace("replace_once(", "replace_all(", 1)
if old not in script:
    raise RuntimeError("last-construction migration block not found")
script = script.replace(old, new, 1)

# The all-path migration above subsumes this more-specific keyboard-only block.
start = script.find("# There is a second keyboard selection path with the same assignment.\n")
if start < 0:
    raise RuntimeError("redundant keyboard-selection marker not found")
end = script.find(
    "replace_once(\n    \"src/construction_ui.cpp\",\n    '''        if( contextual_result.type",
    start,
)
if end < 0:
    raise RuntimeError("end of redundant keyboard-selection patch not found")
script = script[:start] + script[end:]

# draw_header() is replaced wholesale earlier and already uses the correct
# compact-mode predicate, so this old follow-up guard would see zero matches.
start = script.find("# Avoid stale selection on operation switches in compact layouts")
if start >= 0:
    end = script.find("Path(\"/tmp/branch_patch_commit_message\")", start)
    if end < 0:
        raise RuntimeError("end of redundant compact-mode patch not found")
    script = script[:start] + script[end:]

exec(compile(script, "construction_catalog_semantic_cleanup.py", "exec"))
