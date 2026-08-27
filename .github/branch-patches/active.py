from pathlib import Path

p = Path("src/crafting_gui.cpp")
text = p.read_text(encoding="utf-8")
old = '''        const int new_index = selected_index();\n        state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )\n        .set_viewport_size( visible_recipes );\n        if( new_index >= 0 ) {\n            state.recipe_scroll.ensure_visible( new_index );\n        }\n'''
new = '''        const int selected_row = selected_row_index();\n        state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )\n        .set_viewport_size( visible_recipes );\n        if( selected_row >= 0 ) {\n            state.recipe_scroll.ensure_visible( selected_row );\n        }\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"crafting end-of-loop row sync: expected 1 anchor, found {count}")
p.write_text(text.replace(old, new, 1), encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix crafting viewport row synchronization\n", encoding="utf-8"
)
