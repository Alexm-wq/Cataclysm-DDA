from pathlib import Path

cpp_path = Path('src/veh_interact.cpp')
h_path = Path('src/veh_interact.h')
cpp = cpp_path.read_text()
h = h_path.read_text()


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    return text.replace(old, new, 1)


def replace_function(text, signature, replacement, label):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'{label}: signature not found')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'{label}: opening brace not found')
    depth = 0
    in_string = False
    in_char = False
    escape = False
    i = brace
    while i < len(text):
        ch = text[i]
        if escape:
            escape = False
        elif ch == '\\' and (in_string or in_char):
            escape = True
        elif ch == '"' and not in_char:
            in_string = not in_string
        elif ch == "'" and not in_string:
            in_char = not in_char
        elif not in_string and not in_char:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[:start] + replacement.rstrip() + text[i + 1:]
        i += 1
    raise SystemExit(f'{label}: unterminated function')

h = replace_once(
    h,
    '''        catacurses::window w_name;\n        catacurses::window w_refuel_overlay;\n''',
    '''        catacurses::window w_name;\n        catacurses::window w_refuel_overlay;\n        // Small transient overlay for Modify/More.  This must not reuse w_border:\n        // refreshing the full-screen border after the SDL map preview masks Live/Split.\n        catacurses::window w_toolbar_dropdown;\n''',
    'toolbar dropdown window member')

cpp = replace_once(
    cpp,
    '''    w_border = catacurses::newwin( TERMY, TERMX, point::zero );\n''',
    '''    // Any transient toolbar window references the old terminal geometry.\n    // Recreate it lazily on the next dropdown redraw after a resize.\n    w_toolbar_dropdown = catacurses::window();\n    w_border = catacurses::newwin( TERMY, TERMX, point::zero );\n''',
    'reset dropdown window on resize')

cpp = replace_once(
    cpp,
    '''    editor_toolbar_dropdown_height = 0;\n    editor_toolbar_dropdown_pos = point::zero;\n}\n''',
    '''    editor_toolbar_dropdown_height = 0;\n    editor_toolbar_dropdown_pos = point::zero;\n    w_toolbar_dropdown = catacurses::window();\n}\n''',
    'destroy dropdown window on close')

replacement = r'''void veh_interact::display_editor_toolbar_dropdown()
{
    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_buttons.empty() ) {
        w_toolbar_dropdown = catacurses::window();
        return;
    }

    // Re-anchor after resize/responsive toolbar changes while keeping the menu
    // attached to the button that opened it.  Hit-test coordinates remain in
    // w_border space; the actual curses overlay is a tiny independent window.
    int anchor_x = editor_toolbar_dropdown_pos.x;
    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {
        if( button.action == open_editor_toolbar_dropdown ) {
            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );
            break;
        }
    }
    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );
    editor_toolbar_dropdown_pos.x = std::clamp( anchor_x, 1, max_x );
    const int desired_y = getbegy( w_disp ) - getbegy( w_border );
    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );
    editor_toolbar_dropdown_pos.y = std::clamp( desired_y, 1, max_y );

    for( int i = 0; i < static_cast<int>( editor_toolbar_dropdown_buttons.size() ); ++i ) {
        editor_toolbar_dropdown_buttons[i].pos = editor_toolbar_dropdown_pos + point( 1, 1 + i );
        editor_toolbar_dropdown_buttons[i].width = std::max( 1, editor_toolbar_dropdown_width - 2 );
    }

    const point screen_pos( getbegx( w_border ) + editor_toolbar_dropdown_pos.x,
                            getbegy( w_border ) + editor_toolbar_dropdown_pos.y );
    const bool needs_window = !w_toolbar_dropdown ||
                              getmaxx( w_toolbar_dropdown ) != editor_toolbar_dropdown_width ||
                              getmaxy( w_toolbar_dropdown ) != editor_toolbar_dropdown_height ||
                              getbegx( w_toolbar_dropdown ) != screen_pos.x ||
                              getbegy( w_toolbar_dropdown ) != screen_pos.y;
    if( needs_window ) {
        w_toolbar_dropdown = catacurses::newwin( editor_toolbar_dropdown_height,
                             editor_toolbar_dropdown_width, screen_pos );
    }

    werase( w_toolbar_dropdown );
    mvwhline( w_toolbar_dropdown, point::zero, c_light_cyan, LINE_OXOX,
              editor_toolbar_dropdown_width );
    mvwhline( w_toolbar_dropdown, point( 0, editor_toolbar_dropdown_height - 1 ),
              c_light_cyan, LINE_OXOX, editor_toolbar_dropdown_width );
    mvwvline( w_toolbar_dropdown, point::zero, c_light_cyan, LINE_XOXO,
              editor_toolbar_dropdown_height );
    mvwvline( w_toolbar_dropdown, point( editor_toolbar_dropdown_width - 1, 0 ),
              c_light_cyan, LINE_XOXO, editor_toolbar_dropdown_height );
    mvwputch( w_toolbar_dropdown, point::zero, c_light_cyan, LINE_OXXO );
    mvwputch( w_toolbar_dropdown, point( editor_toolbar_dropdown_width - 1, 0 ),
              c_light_cyan, LINE_OOXX );
    mvwputch( w_toolbar_dropdown, point( 0, editor_toolbar_dropdown_height - 1 ),
              c_light_cyan, LINE_XXOO );
    mvwputch( w_toolbar_dropdown,
              point( editor_toolbar_dropdown_width - 1, editor_toolbar_dropdown_height - 1 ),
              c_light_cyan, LINE_XOOX );

    for( int i = 0; i < static_cast<int>( editor_toolbar_dropdown_buttons.size() ); ++i ) {
        const editor_context_button &button = editor_toolbar_dropdown_buttons[i];
        trim_and_print( w_toolbar_dropdown, point( 1, 1 + i ),
                        std::max( 1, editor_toolbar_dropdown_width - 2 ),
                        button.enabled ? c_light_gray : c_dark_gray, button.label );
    }
    wnoutrefresh( w_toolbar_dropdown );
}'''
cpp = replace_function(cpp, 'void veh_interact::display_editor_toolbar_dropdown()', replacement,
                       'dedicated toolbar dropdown renderer')

# Make sure the previous full-screen overlay path is gone and Live/Split remains registered.
assert 'trim_and_print( w_border, button.pos' not in cpp
assert 'mvwhline( w_border, editor_toolbar_dropdown_pos' not in cpp
assert 'w_toolbar_dropdown = catacurses::newwin' in cpp
assert 'display_live_preview( here );\n            display_mode( here );' in cpp
assert 'set_map_preview_window( preview, world_center, live_preview_zoom * 8 );' in cpp

cpp_path.write_text(cpp)
h_path.write_text(h)
print('toolbar dropdown moved to dedicated small curses window')
