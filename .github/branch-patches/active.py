from pathlib import Path

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

old = """    const auto rebuild_recipe_list = [&]() {\n        const recipe *previous_recipe = state.selected_recipe;\n        const int previous_index = selected_index();\n"""
new = """    const auto rebuild_recipe_list = [&]() {\n        const recipe *previous_recipe = state.selected_recipe;\n"""

if text.count(old) != 1:
    raise RuntimeError(f"obsolete previous_index: expected one match, found {text.count(old)}")
text = text.replace(old, new, 1)

required = (
    'std::vector<int> recipe_indices;',
    'first->result() == rec->result() && first->variant() == rec->variant()',
    'name += string_format( " (%d)", static_cast<int>( list_row.recipe_indices.size() ) );',
    '"RECIPE_PREV"',
    '"RECIPE_NEXT"',
    'recipe_method_actions.handle_input( action, inspector_pos )',
    'state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )',
)
for fragment in required:
    if fragment not in text:
        raise RuntimeError(f"missing recipe-collapse fragment: {fragment}")

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Clean up collapsed crafting recipe selection\n", encoding="utf-8"
)
