from pathlib import Path

path = Path("src/construction_ui.cpp")
text = path.read_text(encoding="utf-8")
old = "    if( show_context_actions ) {    if( show_context_actions ) {\n"
if text.count(old) != 1:
    raise RuntimeError(f"expected one duplicated context guard, found {text.count(old)}")
text = text.replace(old, "    if( show_context_actions ) {\n", 1)
path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix construction action strip guard\n", encoding="utf-8"
)
