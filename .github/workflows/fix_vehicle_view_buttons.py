from pathlib import Path

hpp = Path('src/veh_interact.h')
cpp = Path('src/veh_interact.cpp')
htext = hpp.read_text()
ctext = cpp.read_text()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, got {count}')
    return text.replace(old, new, 1)

htext = replace_once(
    htext,
'''        enum class editor_layer {
            composite,
            ground,
            middle,
            roof
        };
''',
'''        enum class editor_view_mode {
            editor,
            live,
            split
        };
        enum class editor_layer {
            composite,
            ground,
            middle,
            roof
        };
''',
    'editor view enum',
)

htext = replace_once(
    htext,
'''        editor_layer active_editor_layer = editor_layer::composite;
        editor_system_filter active_system_filter = editor_system_filter::all;
''',
'''        editor_view_mode active_editor_view_mode = editor_view_mode::editor;
        editor_layer active_editor_layer = editor_layer::composite;
        editor_system_filter active_system_filter = editor_system_filter::all;
''',
    'active editor view state',
)

ctext = replace_once(
    ctext,
'''bool veh_interact::handle_editor_controls_click( const point &pos )
{
    if( pos.x < 0 || pos.x >= getmaxx( w_disp ) || pos.y < 0 || pos.y >= getmaxy( w_disp ) ) {
        return false;
    }

    if( pos.y == 1 ) {
''',
'''bool veh_interact::handle_editor_controls_click( const point &pos )
{
    if( pos.x < 0 || pos.x >= getmaxx( w_disp ) || pos.y < 0 || pos.y >= getmaxy( w_disp ) ) {
        return false;
    }

    if( pos.y == 0 ) {
        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{
                { editor_view_mode::editor, _( "Editor" ) },
                { editor_view_mode::live, _( "Live" ) },
                { editor_view_mode::split, _( "Split" ) }
            }};
        int total_width = 0;
        for( const auto &view : views ) {
            total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;
        }
        int x = std::max( 1, getmaxx( w_disp ) - total_width );
        for( const auto &view : views ) {
            const std::string label = string_format( "[ %s ]", view.second );
            const int label_width = utf8_width( label );
            if( pos.x >= x && pos.x < x + label_width ) {
                active_editor_view_mode = view.first;
                open_editor_dropdown = editor_dropdown::none;
                close_editor_context_menu();
                viewport_dragging = false;
                return true;
            }
            x += label_width + 1;
        }
        return false;
    }

    if( pos.y == 1 ) {
''',
    'viewport button click handling',
)

ctext = replace_once(
    ctext,
'''    // Layer tabs: persistent and directly clickable because there are only four.
    mvwprintz( w_disp, point( 1, 1 ), c_light_gray, _( "Layer: " ) );
''',
'''    // View-mode tabs live at the top-right of the editor pane.  The renderer
    // itself is switched separately; this state is shared by the forthcoming
    // Editor / Live / Split viewport implementations.
    const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{
            { editor_view_mode::editor, _( "Editor" ) },
            { editor_view_mode::live, _( "Live" ) },
            { editor_view_mode::split, _( "Split" ) }
        }};
    int view_total_width = 0;
    for( const auto &view : views ) {
        view_total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;
    }
    int view_x = std::max( 1, width - view_total_width );
    for( const auto &view : views ) {
        const std::string label = string_format( "[ %s ]", view.second );
        const int label_width = utf8_width( label );
        if( view_x < width - 1 ) {
            trim_and_print( w_disp, point( view_x, 0 ), std::max( 1, width - view_x - 1 ),
                            view.first == active_editor_view_mode ? h_light_cyan : c_light_cyan,
                            label );
        }
        view_x += label_width + 1;
    }

    // Layer tabs: persistent and directly clickable because there are only four.
    mvwprintz( w_disp, point( 1, 1 ), c_light_gray, _( "Layer: " ) );
''',
    'viewport button rendering',
)

hpp.write_text(htext)
cpp.write_text(ctext)
