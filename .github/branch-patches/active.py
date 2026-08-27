from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Shared scroll model owns viewport-row/content-index translation and visibility.
replace_once(
    "src/ui_helpers/models/scroll_model.h",
    '''#include <algorithm>\n''',
    '''#include <algorithm>\n#include <optional>\n''',
    "scroll model optional include",
)
replace_once(
    "src/ui_helpers/models/scroll_model.h",
    '''        bool can_scroll() const {\n            return content_size_ > viewport_size_;\n        }\n\n''',
    '''        bool can_scroll() const {\n            return content_size_ > viewport_size_;\n        }\n        bool is_visible( int index ) const {\n            return index >= 0 && index < content_size_ && viewport_size_ > 0 &&\n                   index >= viewport_pos_ && index < viewport_pos_ + viewport_size_;\n        }\n        std::optional<int> index_at_viewport_row( int row ) const {\n            if( row < 0 || row >= viewport_size_ ) {\n                return std::nullopt;\n            }\n            const int index = viewport_pos_ + row;\n            return index >= 0 && index < content_size_ ? std::optional<int>( index ) : std::nullopt;\n        }\n\n''',
    "shared viewport row mapping API",
)

# Cover the shared invariant explicitly.
replace_once(
    "tests/ui_helpers_test.cpp",
    '''    scroll.scroll_to_end().scroll_by( 20 );\n    CHECK( scroll.viewport_pos() == 15 );\n}\n\n''',
    '''    scroll.scroll_to_end().scroll_by( 20 );\n    CHECK( scroll.viewport_pos() == 15 );\n}\n\nTEST_CASE( "ui_scroll_model_maps_visible_rows_to_content", "[ui][ui_helpers]" )\n{\n    ui_scroll_model scroll( 20, 5, 7 );\n\n    CHECK( scroll.is_visible( 7 ) );\n    CHECK( scroll.is_visible( 11 ) );\n    CHECK_FALSE( scroll.is_visible( 6 ) );\n    CHECK_FALSE( scroll.is_visible( 12 ) );\n\n    CHECK( scroll.index_at_viewport_row( 0 ) == 7 );\n    CHECK( scroll.index_at_viewport_row( 4 ) == 11 );\n    CHECK_FALSE( scroll.index_at_viewport_row( -1 ).has_value() );\n    CHECK_FALSE( scroll.index_at_viewport_row( 5 ).has_value() );\n\n    scroll.set_viewport_pos( 17 );\n    CHECK( scroll.viewport_pos() == 15 );\n    CHECK( scroll.index_at_viewport_row( 4 ) == 19 );\n}\n\n''',
    "shared scroll row mapping test",
)

# Crafting redraw uses the shared row mapping instead of hand-rolling viewport_pos + row.
replace_once(
    "src/crafting_gui.cpp",
    '''            for( int row = 0; row < visible; ++row ) {\n                const int index = state.recipe_scroll.viewport_pos() + row;\n                if( index >= static_cast<int>( recipe_rows.size() ) ) {\n                    break;\n                }\n                const browser_list_row &list_row = recipe_rows[index];\n''',
    '''            for( int row = 0; row < visible; ++row ) {\n                const std::optional<int> index = state.recipe_scroll.index_at_viewport_row( row );\n                if( !index ) {\n                    break;\n                }\n                const browser_list_row &list_row = recipe_rows[*index];\n''',
    "crafting shared row mapping",
)
replace_once(
    "src/crafting_gui.cpp",
    '''                recipe_hits.add( inclusive_rectangle<point>( point( 1, y ),\n                                 point( list_width - 2, y ) ), index );\n''',
    '''                recipe_hits.add( inclusive_rectangle<point>( point( 1, y ),\n                                 point( list_width - 2, y ) ), *index );\n''',
    "crafting shared hit index",
)

# Do not recenter selection after arbitrary/intermediate input. Keyboard selection paths and
# explicit list rebuilds already call ensure_visible() at the moment navigation requires it.
replace_once(
    "src/crafting_gui.cpp",
    '''        const int selected_row = selected_row_index();\n        state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )\n        .set_viewport_size( visible_recipes );\n        if( selected_row >= 0 ) {\n            state.recipe_scroll.ensure_visible( selected_row );\n        }\n''',
    '''        // Keep viewport clamping independent from selection.  In particular, an\n        // intermediate mouse-down/drag event must not recenter an off-screen selection\n        // before the matching SELECT resolves the row physically under the cursor.\n        state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )\n        .set_viewport_size( visible_recipes );\n''',
    "remove unconditional crafting recenter",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Keep mouse list clicks independent from selection scroll\n", encoding="utf-8"
)
