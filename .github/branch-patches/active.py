from pathlib import Path

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

old = '''        const int next_recipe_index = row.recipe_indices[method_index];
        row.recipe_index = next_recipe_index;
        row.rec = current[next_recipe_index];
        select_index( next_recipe_index, false );
        workspace_status = string_format( _( "Recipe %d of %d selected." ), method_index + 1,
                                          static_cast<int>( row.recipe_indices.size() ) );
'''
new = '''        const int next_recipe_index = row.recipe_indices[method_index];
        row.recipe_index = next_recipe_index;
        row.rec = current[next_recipe_index];
        const int viewport_before_cycle = state.recipe_scroll.viewport_pos();
        select_index( next_recipe_index, false );
        state.recipe_scroll.set_viewport_pos( viewport_before_cycle );
        workspace_status = string_format( _( "Recipe %d of %d selected." ), method_index + 1,
                                          static_cast<int>( row.recipe_indices.size() ) );
'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f"recipe cycle viewport patch: expected exactly one match, found {count}")

path.write_text(text.replace(old, new, 1), encoding="utf-8")
