from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Shared scrollbar: expose a foreground edge color and render the thumb's
# fractional top edge at eighth-cell resolution.  This makes proportional
# movement visible even when a long list advances by less than one text row.
h = Path("src/ui_helpers/primitive/scrollbar.h")
text = h.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        scrollbar &bar_color( nc_color bar_c );\n        // can viewport_pos go beyond (content_size - viewport_size)?\n''',
    '''        scrollbar &bar_color( nc_color bar_c );\n        // foreground color used for the fractional leading edge of the thumb\n        scrollbar &fractional_bar_color( nc_color bar_c );\n        // can viewport_pos go beyond (content_size - viewport_size)?\n''',
    "fractional bar color declaration",
)
text = replace_once(
    text,
    '''        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;\n''',
    '''        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v, fractional_bar_color_v;\n''',
    "fractional bar color member",
)
h.write_text(text, encoding="utf-8")

cpp = Path("src/ui_helpers/primitive/scrollbar.cpp")
text = cpp.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''      border_color_v( BORDER_COLOR ), arrow_color_v( c_light_green ),\n      slot_color_v( c_white ), bar_color_v( c_cyan_cyan ), scroll_to_last_v( false )\n''',
    '''      border_color_v( BORDER_COLOR ), arrow_color_v( c_light_green ),\n      slot_color_v( c_white ), bar_color_v( c_cyan_cyan ), fractional_bar_color_v( c_cyan ),\n      scroll_to_last_v( false )\n''',
    "fractional bar color initialization",
)
text = replace_once(
    text,
    '''scrollbar &scrollbar::bar_color( nc_color bar_c )\n{\n    bar_color_v = bar_c;\n    return *this;\n}\n\n''',
    '''scrollbar &scrollbar::bar_color( nc_color bar_c )\n{\n    bar_color_v = bar_c;\n    return *this;\n}\n\nscrollbar &scrollbar::fractional_bar_color( nc_color bar_c )\n{\n    fractional_bar_color_v = bar_c;\n    return *this;\n}\n\n''',
    "fractional bar color setter",
)
old_geometry = '''    const int travel = std::max( 0, slot_size - bar_size );\n    const int clamped_position = clamp( viewport_pos_v, 0, max_position );\n    const int bar_start = max_position > 0 && travel > 0 ?\n                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *\n                                  static_cast<double>( travel ) /\n                                  static_cast<double>( max_position ) ) ) : 0;\n    const int bar_end = bar_start + bar_size;\n    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),\n                 point( absolute_x, absolute_y + bar_end ) );\n\n    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,\n              bar_size );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,\n              slot_size - bar_end );\n'''
new_geometry = '''    const int travel = std::max( 0, slot_size - bar_size );\n    const int clamped_position = clamp( viewport_pos_v, 0, max_position );\n    const double exact_bar_start = max_position > 0 && travel > 0 ?\n                                   static_cast<double>( clamped_position ) *\n                                   static_cast<double>( travel ) /\n                                   static_cast<double>( max_position ) : 0.0;\n    const int bar_start = std::clamp( static_cast<int>( std::floor( exact_bar_start ) ), 0, travel );\n    const double fractional_start = std::clamp( exact_bar_start - static_cast<double>( bar_start ),\n                                    0.0, 0.999999 );\n    const int fractional_step = std::clamp(\n                                    static_cast<int>( std::floor( fractional_start * 8.0 ) ), 0, 7 );\n    const int bar_end = bar_start + bar_size;\n    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),\n                 point( absolute_x, absolute_y + bar_end ) );\n\n    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;\n    const nc_color current_fractional_color = dragging ? c_magenta : fractional_bar_color_v;\n    static constexpr const char *fractional_blocks[8] = {\n        "█", "▇", "▆", "▅", "▄", "▃", "▂", "▁"\n    };\n\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );\n    if( fractional_step == 0 ) {\n        mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color,\n                  LINE_XOXO, bar_size );\n    } else {\n        mvwputch( window, point( offset_x_v, offset_y_v + 1 + bar_start ),\n                  current_fractional_color, fractional_blocks[fractional_step] );\n        if( bar_size > 1 ) {\n            mvwvline( window, point( offset_x_v, offset_y_v + 2 + bar_start ), current_bar_color,\n                      LINE_XOXO, bar_size - 1 );\n        }\n    }\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,\n              slot_size - bar_end );\n'''
text = replace_once(text, old_geometry, new_geometry, "fractional scrollbar geometry")
cpp.write_text(text, encoding="utf-8")


# Crafting browser: opt both persistent scrollbars into the shared mouse
# interaction state machine, route absolute mouse coordinates to them before
# row/button hit-testing, and always refresh geometry so stale hitboxes clear.
craft = Path("src/crafting_gui.cpp")
text = craft.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    scrollbar recipe_scrollbar;\n    scrollbar inspector_scrollbar;\n\n    catacurses::window w_header;\n''',
    '''    scrollbar recipe_scrollbar;\n    scrollbar inspector_scrollbar;\n    recipe_scrollbar.set_draggable( ctxt );\n    inspector_scrollbar.set_draggable( ctxt );\n\n    catacurses::window w_header;\n''',
    "crafting draggable scrollbar registration",
)
text = replace_once(
    text,
    '''            if( static_cast<int>( recipe_rows.size() ) > visible ) {\n                recipe_scrollbar.offset_x( list_width - 1 ).offset_y( first_row )\n                .model( state.recipe_scroll ).apply( w_recipes );\n            }\n\n            if( state.context_open && state.selected_recipe != nullptr ) {\n''',
    '''            recipe_scrollbar.offset_x( list_width - 1 ).offset_y( first_row )\n            .model( state.recipe_scroll ).apply( w_recipes );\n\n            if( state.context_open && state.selected_recipe != nullptr ) {\n''',
    "always refresh recipe scrollbar geometry",
)
# Make inspector geometry/model lifecycle explicit and unconditional.
text = replace_once(
    text,
    '''            const int inspector_width = getmaxx( w_inspector );\n            const int inspector_height = getmaxy( w_inspector );\n            if( state.selected_recipe == nullptr ) {\n''',
    '''            const int inspector_width = getmaxx( w_inspector );\n            const int inspector_height = getmaxy( w_inspector );\n            const int inspector_first_row = 5;\n            const int inspector_visible = std::max( 1, inspector_height - inspector_first_row - 1 );\n            state.inspector_scroll.set_viewport_size( inspector_visible );\n            if( state.selected_recipe == nullptr ) {\n                state.inspector_scroll.set_content_size( 0 );\n''',
    "inspector scrollbar lifecycle setup",
)
text = replace_once(
    text,
    '''                if( avail != nullptr ) {\n                    const std::string qry = trim( state.search_query );\n                    const std::string qry_comps = qry.rfind( "c:", 0 ) == 0 ? qry.substr( 2 ) : "";\n                    const int fold_width = std::max( 10, inspector_width - 3 );\n                    const std::vector<std::string> &info = cached_recipe_info(\n                                r_info_cache, *state.selected_recipe, *avail, *crafter, qry_comps,\n                                state.batch_size, fold_width, avail->color( true ), crafting_characters );\n                    const int first_row = 5;\n                    const int visible = std::max( 1, inspector_height - first_row - 1 );\n                    state.inspector_scroll.set_content_size( static_cast<int>( info.size() ) )\n                    .set_viewport_size( visible );\n                    for( int row = 0; row < visible; ++row ) {\n                        const int index = state.inspector_scroll.viewport_pos() + row;\n                        if( index >= static_cast<int>( info.size() ) ) {\n                            break;\n                        }\n                        nc_color dummy = c_light_gray;\n                        print_colored_text( w_inspector, point( 1, first_row + row ), dummy,\n                                            c_light_gray, info[index] );\n                    }\n                    if( static_cast<int>( info.size() ) > visible ) {\n                        inspector_scrollbar.offset_x( inspector_width - 1 ).offset_y( first_row )\n                        .model( state.inspector_scroll ).apply( w_inspector );\n                    }\n                }\n            }\n            wnoutrefresh( w_inspector );\n''',
    '''                if( avail != nullptr ) {\n                    const std::string qry = trim( state.search_query );\n                    const std::string qry_comps = qry.rfind( "c:", 0 ) == 0 ? qry.substr( 2 ) : "";\n                    const int fold_width = std::max( 10, inspector_width - 3 );\n                    const std::vector<std::string> &info = cached_recipe_info(\n                                r_info_cache, *state.selected_recipe, *avail, *crafter, qry_comps,\n                                state.batch_size, fold_width, avail->color( true ), crafting_characters );\n                    state.inspector_scroll.set_content_size( static_cast<int>( info.size() ) );\n                    for( int row = 0; row < inspector_visible; ++row ) {\n                        const int index = state.inspector_scroll.viewport_pos() + row;\n                        if( index >= static_cast<int>( info.size() ) ) {\n                            break;\n                        }\n                        nc_color dummy = c_light_gray;\n                        print_colored_text( w_inspector, point( 1, inspector_first_row + row ), dummy,\n                                            c_light_gray, info[index] );\n                    }\n                } else {\n                    state.inspector_scroll.set_content_size( 0 );\n                }\n            }\n            inspector_scrollbar.offset_x( inspector_width - 1 ).offset_y( inspector_first_row )\n            .model( state.inspector_scroll ).apply( w_inspector );\n            wnoutrefresh( w_inspector );\n''',
    "always refresh inspector scrollbar geometry",
)
text = replace_once(
    text,
    '''        if( action == "MOUSE_MOVE" ) {\n            state.hovered_recipe = nullptr;\n''',
    '''        const bool recipes_visible = !compact_layout ||\n                                     state.focused_pane == crafting_browser_pane::recipes;\n        const bool inspector_visible = !compact_layout ||\n                                       state.focused_pane == crafting_browser_pane::inspector;\n        if( recipes_visible &&\n            recipe_scrollbar.handle_dragging( action, screen_pos, state.recipe_scroll ) ) {\n            continue;\n        }\n        if( inspector_visible &&\n            inspector_scrollbar.handle_dragging( action, screen_pos, state.inspector_scroll ) ) {\n            continue;\n        }\n\n        if( action == "MOUSE_MOVE" ) {\n            state.hovered_recipe = nullptr;\n''',
    "crafting scrollbar interaction routing",
)
craft.write_text(text, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Wire crafting into browser-like shared scrollbars\n", encoding="utf-8"
)
