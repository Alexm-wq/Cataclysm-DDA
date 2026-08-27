from pathlib import Path

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

old = '''        const int index = selected_index();\n        const int row_index = selected_row_index();\n'''
new = '''        const int row_index = selected_row_index();\n'''
if text.count(old) != 1:
    raise SystemExit(f"unused recipe index cleanup: expected 1, found {text.count(old)}")
text = text.replace(old, new, 1)

old = '''            if( ( !compact_layout || state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {\n                state.hovered_recipe = nullptr;\n                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n'''
new = '''            if( ( !compact_layout || state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {\n                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n'''
if text.count(old) != 1:
    raise SystemExit(f"hover reset cleanup: expected 1, found {text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Clean up crafting section browser migration\n", encoding="utf-8"
)
