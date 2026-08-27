from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)

# Revert the fractional-glyph experiment. Keep the browser-style proportional
# thumb, dragging, track clicks and exact viewport mapping, but render it as a
# normal whole-cell scrollbar again.
h = Path("src/ui_helpers/primitive/scrollbar.h")
text = h.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        // scrollbar bar color\n        scrollbar &bar_color( nc_color bar_c );\n        // foreground color used for the fractional leading edge of the thumb\n        scrollbar &fractional_bar_color( nc_color bar_c );\n        // can viewport_pos go beyond (content_size - viewport_size)?\n''',
    '''        // scrollbar bar color\n        scrollbar &bar_color( nc_color bar_c );\n        // can viewport_pos go beyond (content_size - viewport_size)?\n''',
    "remove fractional color API",
)
text = replace_once(
    text,
    '''        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v, fractional_bar_color_v;\n''',
    '''        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;\n''',
    "remove fractional color member",
)
h.write_text(text, encoding="utf-8")

cpp = Path("src/ui_helpers/primitive/scrollbar.cpp")
text = cpp.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''      border_color_v( BORDER_COLOR ), arrow_color_v( c_light_green ),\n      slot_color_v( c_white ), bar_color_v( c_cyan_cyan ), fractional_bar_color_v( c_cyan ),\n      scroll_to_last_v( false )\n''',
    '''      border_color_v( BORDER_COLOR ), arrow_color_v( c_light_green ),\n      slot_color_v( c_white ), bar_color_v( c_cyan_cyan ), scroll_to_last_v( false )\n''',
    "remove fractional color initialization",
)
text = replace_once(
    text,
    '''scrollbar &scrollbar::fractional_bar_color( nc_color bar_c )\n{\n    fractional_bar_color_v = bar_c;\n    return *this;\n}\n\n''',
    '''''',
    "remove fractional color setter",
)
old = '''    const int travel = std::max( 0, slot_size - bar_size );\n    const int clamped_position = clamp( viewport_pos_v, 0, max_position );\n    const double exact_bar_start = max_position > 0 && travel > 0 ?\n                                   static_cast<double>( clamped_position ) *\n                                   static_cast<double>( travel ) /\n                                   static_cast<double>( max_position ) : 0.0;\n    const int bar_start = std::clamp( static_cast<int>( std::floor( exact_bar_start ) ), 0, travel );\n    const double fractional_start = std::clamp( exact_bar_start - static_cast<double>( bar_start ),\n                                    0.0, 0.999999 );\n    const int fractional_step = std::clamp(\n                                    static_cast<int>( std::floor( fractional_start * 8.0 ) ), 0, 7 );\n    const int bar_end = bar_start + bar_size;\n    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),\n                 point( absolute_x, absolute_y + bar_end ) );\n\n    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;\n    const nc_color current_fractional_color = dragging ? c_magenta : fractional_bar_color_v;\n    static constexpr const char *fractional_blocks[8] = {\n        "█", "▇", "▆", "▅", "▄", "▃", "▂", "▁"\n    };\n\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );\n    if( fractional_step == 0 ) {\n        mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color,\n                  LINE_XOXO, bar_size );\n    } else {\n        mvwputch( window, point( offset_x_v, offset_y_v + 1 + bar_start ),\n                  current_fractional_color, fractional_blocks[fractional_step] );\n        if( bar_size > 1 ) {\n            mvwvline( window, point( offset_x_v, offset_y_v + 2 + bar_start ), current_bar_color,\n                      LINE_XOXO, bar_size - 1 );\n        }\n    }\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,\n              slot_size - bar_end );\n'''
new = '''    const int travel = std::max( 0, slot_size - bar_size );\n    const int clamped_position = clamp( viewport_pos_v, 0, max_position );\n    // viewport_pos_v is an entry index.  Map that exact entry position across\n    // the available thumb travel; rendering is quantized only by terminal rows.\n    const int bar_start = max_position > 0 && travel > 0 ?\n                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *\n                                  static_cast<double>( travel ) /\n                                  static_cast<double>( max_position ) ) ) : 0;\n    const int bar_end = bar_start + bar_size;\n    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),\n                 point( absolute_x, absolute_y + bar_end ) );\n\n    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,\n              bar_size );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,\n              slot_size - bar_end );\n'''
text = replace_once(text, old, new, "restore whole-cell proportional thumb")
cpp.write_text(text, encoding="utf-8")

# Crafting wheel input should advance one rendered row/entry per notch.  The
# shared scrollbar then reflects that viewport entry index proportionally.
craft = Path("src/crafting_gui.cpp")
text = craft.read_text(encoding="utf-8")
old_scroll = '''        if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n            const int direction = action == "SCROLL_UP" ? -1 : 1;\n            if( compact_layout ) {\n                if( state.focused_pane == crafting_browser_pane::recipes ) {\n                    state.recipe_scroll.scroll_by( direction * 3 );\n                } else {\n                    state.inspector_scroll.scroll_by( direction * 3 );\n                }\n            } else if( recipes_pos ) {\n                state.recipe_scroll.scroll_by( direction * 3 );\n            } else if( inspector_pos ) {\n                state.inspector_scroll.scroll_by( direction * 3 );\n            }\n            continue;\n        }\n'''
new_scroll = '''        if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n            const int direction = action == "SCROLL_UP" ? -1 : 1;\n            if( compact_layout ) {\n                if( state.focused_pane == crafting_browser_pane::recipes ) {\n                    state.recipe_scroll.scroll_by( direction );\n                } else {\n                    state.inspector_scroll.scroll_by( direction );\n                }\n            } else if( recipes_pos ) {\n                state.recipe_scroll.scroll_by( direction );\n            } else if( inspector_pos ) {\n                state.inspector_scroll.scroll_by( direction );\n            }\n            continue;\n        }\n'''
text = replace_once(text, old_scroll, new_scroll, "one-entry crafting wheel scroll")
craft.write_text(text, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Make crafting scrolling entry based\n", encoding="utf-8"
)
