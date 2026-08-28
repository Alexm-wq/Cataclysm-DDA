from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_first(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_before(path_str: str, marker: str, addition: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise SystemExit(f"expected unique marker in {path_str}: {marker[:120]!r}")
    path.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")


replace_once(
    "src/game.cpp",
    '#include "ui_helpers/controls/action_strip.h"\n#include "ui_helpers/controls/selection_list.h"\n',
    '#include "ui_helpers/controls/action_strip.h"\n#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/controls/selection_list.h"\n'
)

replace_once(
    "src/uistate.h",
    '''        // Five configurable map-HUD menu shortcuts.  Store action identifiers,\n        // never display keys, so rebinding keys does not invalidate assignments.\n        std::vector<std::string> safemode_corner_menu_slots = std::vector<std::string>( 5 );\n''',
    '''        // Configurable map-HUD menu shortcuts.  The first five form the base column;\n        // additional slots grow in six-high columns to the left.  Store action identifiers,\n        // never display keys, so rebinding keys does not invalidate assignments.\n        std::vector<std::string> safemode_corner_menu_slots = std::vector<std::string>( 5 );\n'''
)
replace_once(
    "src/inventory_ui.cpp",
    '''    jo.read( "safemode_corner_menu_slots", safemode_corner_menu_slots );\n    if( safemode_corner_menu_slots.size() != 5 ) {\n        safemode_corner_menu_slots.resize( 5 );\n    }\n''',
    '''    jo.read( "safemode_corner_menu_slots", safemode_corner_menu_slots );\n    if( safemode_corner_menu_slots.size() < 5 ) {\n        safemode_corner_menu_slots.resize( 5 );\n    }\n'''
)

replace_once(
    "src/game.h",
    '''        ui_icon_button safemode_corner_launcher; // NOLINT(cata-serialize)\n        std::array<ui_icon_button, 6> safemode_corner_buttons; // NOLINT(cata-serialize)\n        ui_tooltip safemode_corner_tooltip; // NOLINT(cata-serialize)\n''',
    '''        ui_icon_button safemode_corner_launcher; // NOLINT(cata-serialize)\n        std::array<ui_icon_button, 6> safemode_corner_buttons; // NOLINT(cata-serialize)\n        std::vector<std::unique_ptr<ui_icon_button>> safemode_corner_extra_buttons; // NOLINT(cata-serialize)\n        ui_tooltip safemode_corner_tooltip; // NOLINT(cata-serialize)\n'''
)
replace_once(
    "src/game.h",
    '''        action_id get_safemode_mouse_action( const point &p,\n                const std::optional<point> &pixel_p = std::nullopt );\n''',
    '''        action_id get_safemode_mouse_action( const point &p,\n                const std::optional<point> &pixel_p = std::nullopt, bool secondary = false );\n'''
)

replace_once(
    "src/game.cpp",
    '''static constexpr int safemode_corner_button_count = 6;\nstatic constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;\n\nstatic action_id safemode_corner_menu_slot_action( const int index )\n{\n    if( index < 0 || index >= safemode_corner_safe_index ||\n        index >= static_cast<int>( uistate.safemode_corner_menu_slots.size() ) ) {\n        return ACTION_NULL;\n    }\n    return look_up_action( uistate.safemode_corner_menu_slots[index] );\n}\n\nstatic void assign_safemode_corner_menu_slot( const int index, const action_id action )\n{\n    if( index < 0 || index >= safemode_corner_safe_index ) {\n        return;\n    }\n    if( uistate.safemode_corner_menu_slots.size() != safemode_corner_safe_index ) {\n        uistate.safemode_corner_menu_slots.resize( safemode_corner_safe_index );\n    }\n    uistate.safemode_corner_menu_slots[index] = action_ident( action );\n}\n''',
    '''static constexpr int safemode_corner_button_count = 6;\nstatic constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;\nstatic constexpr int safemode_corner_base_slot_count = safemode_corner_safe_index;\nstatic constexpr int safemode_corner_extra_rows = 6;\n\nstatic action_id safemode_corner_menu_slot_action( const int index )\n{\n    if( index < 0 || index >= static_cast<int>( uistate.safemode_corner_menu_slots.size() ) ) {\n        return ACTION_NULL;\n    }\n    return look_up_action( uistate.safemode_corner_menu_slots[index] );\n}\n\nstatic void assign_safemode_corner_menu_slot( const int index, const action_id action )\n{\n    if( index < 0 ) {\n        return;\n    }\n    if( index >= static_cast<int>( uistate.safemode_corner_menu_slots.size() ) ) {\n        uistate.safemode_corner_menu_slots.resize( index + 1 );\n    }\n    uistate.safemode_corner_menu_slots[index] = action_ident( action );\n}\n\nstatic int safemode_corner_visible_menu_slot_count()\n{\n    int last_assigned = -1;\n    for( int i = static_cast<int>( uistate.safemode_corner_menu_slots.size() ) - 1; i >= 0; --i ) {\n        if( safemode_corner_menu_slot_action( i ) != ACTION_NULL ) {\n            last_assigned = i;\n            break;\n        }\n    }\n    return std::max( safemode_corner_base_slot_count, last_assigned + 2 );\n}\n\nstatic int safemode_corner_visible_extra_slot_count()\n{\n    return std::max( 0, safemode_corner_visible_menu_slot_count() -\n                     safemode_corner_base_slot_count );\n}\n'''
)

insert_before(
    "src/game.cpp",
    '''static point safemode_corner_launcher_pixel_pos( const catacurses::window &panel )\n''',
    '''static point safemode_corner_extra_pixel_pos( const catacurses::window &panel,\n        const int extra_index )\n{\n    const point safe_pos = safemode_corner_palette_pixel_pos( panel, safemode_corner_safe_index );\n    const point size = safemode_corner_button_pixel_size();\n    const int overlap = safemode_corner_ui_scale();\n    const int column = 1 + extra_index / safemode_corner_extra_rows;\n    const int row = extra_index % safemode_corner_extra_rows;\n    return point( safe_pos.x - column * ( size.x - overlap ),\n                  safe_pos.y - row * ( size.y - overlap ) );\n}\n\nstatic bool safemode_corner_extra_pixel_fits( const catacurses::window &panel,\n        const int extra_index )\n{\n    const window_dimensions screen_dim = get_window_dimensions( catacurses::stdscr );\n    const point pos = safemode_corner_extra_pixel_pos( panel, extra_index );\n    const point size = safemode_corner_button_pixel_size();\n    return pos.x >= 0 && pos.y >= 0 &&\n           pos.x + size.x <= screen_dim.window_size_pixel.x &&\n           pos.y + size.y <= screen_dim.window_size_pixel.y;\n}\n\n'''
)
insert_before(
    "src/game.cpp",
    '''#endif\n\nstatic bool safemode_corner_controls_fit( const catacurses::window &panel )\n''',
    '''static point safemode_corner_extra_pos( const catacurses::window &panel, const int extra_index )\n{\n    const point safe_pos = safemode_corner_palette_pos( panel, safemode_corner_safe_index );\n    const point size = safemode_corner_button_size();\n    const int column = 1 + extra_index / safemode_corner_extra_rows;\n    const int row = extra_index % safemode_corner_extra_rows;\n    return point( safe_pos.x - column * ( size.x - 1 ),\n                  safe_pos.y - row * ( size.y - 1 ) );\n}\n\nstatic bool safemode_corner_extra_fits( const catacurses::window &panel, const int extra_index )\n{\n    const point pos = safemode_corner_extra_pos( panel, extra_index );\n    const point size = safemode_corner_button_size();\n    return pos.x >= 0 && pos.y >= 0 &&\n           pos.x + size.x <= getmaxx( catacurses::stdscr ) &&\n           pos.y + size.y <= getmaxy( catacurses::stdscr );\n}\n#endif\n\n'''
)

insert_before(
    "src/game.cpp",
    '''void game::draw_safemode_mouse_controls()\n''',
    '''static bool query_safemode_corner_change_menu( const point &anchor )\n{\n    ui_dropdown menu;\n    ui_dropdown_style style;\n    style.border = c_light_gray;\n    style.text = c_light_gray;\n    style.highlight = h_light_gray;\n    style.selected = c_white;\n\n    input_context ctxt( "SAFE_CORNER_SLOT_CONTEXT" );\n    for( const std::string &action : { "UP", "DOWN", "CONFIRM", "QUIT", "SELECT",\n                                      "SEC_SELECT", "MOUSE_MOVE" } ) {\n        ctxt.register_action( action );\n    }\n\n    ui_adaptor ui( ui_adaptor::disable_uis_below{} );\n    ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {\n        adaptor.position_from_window( catacurses::stdscr );\n        menu.configure( catacurses::stdscr, anchor,\n                        { ui_dropdown_entry( _( "Change" ), "CHANGE" ) }, 0, style );\n    } );\n    ui.mark_resize();\n    ui.on_redraw( [&]( ui_adaptor & adaptor ) {\n        menu.draw( catacurses::stdscr );\n        adaptor.disable_cursor();\n    } );\n\n    while( true ) {\n        ui_manager::redraw();\n        if( !menu.is_open() ) {\n            return false;\n        }\n        const std::string action = ctxt.handle_input();\n        const std::optional<point> pos = ctxt.get_coordinates_text( catacurses::stdscr );\n        const ui_action_result result = menu.handle_input( action, pos );\n        if( result.type == ui_action_result_type::activated && result.entry ) {\n            return result.entry->id == "CHANGE";\n        }\n        if( result.type == ui_action_result_type::closed ) {\n            return false;\n        }\n    }\n}\n\n'''
)

# First occurrence is the early-return hide path; collapse is patched separately below.
replace_first(
    "src/game.cpp",
    '''        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.close();\n        }\n        safemode_corner_tooltip.reset();\n''',
    '''        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.close();\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            button->close();\n        }\n        safemode_corner_tooltip.reset();\n'''
)

insert_before(
    "src/game.cpp",
    '''        const auto safe_bounds = safemode_corner_buttons[safemode_corner_safe_index].bounds();\n''',
    '''        const int extra_count = safemode_corner_visible_extra_slot_count();\n        while( static_cast<int>( safemode_corner_extra_buttons.size() ) < extra_count ) {\n            safemode_corner_extra_buttons.push_back( std::make_unique<ui_icon_button>() );\n        }\n        for( int extra = 0; extra < static_cast<int>( safemode_corner_extra_buttons.size() ); ++extra ) {\n            ui_icon_button &button = *safemode_corner_extra_buttons[extra];\n            if( extra >= extra_count ) {\n                button.close();\n                continue;\n            }\n#if defined(TILES)\n            if( !safemode_corner_extra_pixel_fits( w_pixel_minimap, extra ) ) {\n                button.close();\n                continue;\n            }\n#else\n            if( !safemode_corner_extra_fits( w_pixel_minimap, extra ) ) {\n                button.close();\n                continue;\n            }\n#endif\n            const int slot = safemode_corner_base_slot_count + extra;\n            ui_icon_button_style style;\n            style.border = c_light_gray;\n            style.fill = c_black;\n            style.icon = c_light_gray;\n            style.hover_border = c_white;\n            style.hover_fill = c_black;\n            style.hover_icon = c_white;\n            style.selected_fill = c_black;\n            style.selected_icon = c_white;\n            style.disabled_fill = c_black;\n            ui_action_entry action( "", string_format( "SAFE_SLOT_%d", slot ) );\n            std::string icon = safemode_corner_action_icon( safemode_corner_menu_slot_action( slot ) );\n#if defined(TILES)\n            button.configure_pixel( w_pixel_minimap,\n                                    safemode_corner_extra_pixel_pos( w_pixel_minimap, extra ),\n                                    button_size, std::move( action ), std::move( icon ), style );\n            button.draw( w_pixel_minimap );\n#else\n            button.configure_compact( catacurses::stdscr,\n                                      safemode_corner_extra_pos( w_pixel_minimap, extra ),\n                                      button_size, std::move( action ), std::move( icon ), style );\n            button.draw( catacurses::stdscr );\n#endif\n        }\n\n'''
)

replace_once(
    "src/game.cpp",
    '''    } else {\n        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.close();\n        }\n        safemode_corner_tooltip.reset();\n    }\n''',
    '''    } else {\n        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.close();\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            button->close();\n        }\n        safemode_corner_tooltip.reset();\n    }\n'''
)

replace_once(
    "src/game.cpp",
    '''            for( ui_icon_button &button : safemode_corner_buttons ) {\n                button.handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );\n            }\n            tooltip_changed = mouse_pos ? safemode_corner_tooltip.update_pointer( mouse_pos ) :\n''',
    '''            for( ui_icon_button &button : safemode_corner_buttons ) {\n                button.handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );\n            }\n            for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n                button->handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );\n            }\n            tooltip_changed = mouse_pos ? safemode_corner_tooltip.update_pointer( mouse_pos ) :\n'''
)
replace_once(
    "src/game.cpp",
    '''            for( ui_icon_button &button : safemode_corner_buttons ) {\n                button.handle_input( "MOUSE_MOVE", mouse_pos );\n            }\n            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );\n''',
    '''            for( ui_icon_button &button : safemode_corner_buttons ) {\n                button.handle_input( "MOUSE_MOVE", mouse_pos );\n            }\n            for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n                button->handle_input( "MOUSE_MOVE", mouse_pos );\n            }\n            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );\n'''
)
replace_once(
    "src/game.cpp",
    '''        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.update_hover_pixel( std::nullopt );\n        }\n#else\n''',
    '''        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.update_hover_pixel( std::nullopt );\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            button->update_hover_pixel( std::nullopt );\n        }\n#else\n'''
)
replace_once(
    "src/game.cpp",
    '''        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.update_hover( std::nullopt );\n        }\n#endif\n''',
    '''        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.update_hover( std::nullopt );\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            button->update_hover( std::nullopt );\n        }\n#endif\n'''
)

start = '''action_id game::get_safemode_mouse_action( const point &p,\n        const std::optional<point> &pixel_p )\n{\n'''
end = '''    const bool threat_stopped = safe_mode == SAFE_MODE_STOP || u.has_effect( effect_laserlocked );\n'''
path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
if text.count(start) != 1:
    raise SystemExit("safemode mouse action start marker not found")
begin = text.index(start)
finish = text.index(end, begin)
new_head = r'''action_id game::get_safemode_mouse_action( const point &p,
        const std::optional<point> &pixel_p, const bool secondary )
{
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ) {
        return ACTION_NULL;
    }

    if( safemode_corner_controls_fit( w_pixel_minimap ) ) {
#if defined(TILES)
        const bool launcher_hit = pixel_p && safemode_corner_launcher.contains_pixel( *pixel_p );
#else
        const bool launcher_hit = safemode_corner_launcher.contains( p );
#endif
        if( launcher_hit ) {
            if( secondary ) {
                return ACTION_CLICK_AND_DRAG;
            }
#if defined(TILES)
            const ui_action_result launcher_result = safemode_corner_launcher.handle_pixel_input( "SELECT",
                    pixel_p );
#else
            const ui_action_result launcher_result = safemode_corner_launcher.handle_input( "SELECT", p );
#endif
            if( launcher_result.type == ui_action_result_type::activated ) {
                safemode_corner_expanded = !safemode_corner_expanded;
                safemode_corner_tooltip.clear_pointer();
                invalidate_main_ui_adaptor();
                return ACTION_CLICK_AND_DRAG;
            }
        }

        if( safemode_corner_expanded ) {
            for( int i = 0; i < safemode_corner_button_count; ++i ) {
#if defined(TILES)
                const bool hit = pixel_p && safemode_corner_buttons[i].contains_pixel( *pixel_p );
#else
                const bool hit = safemode_corner_buttons[i].contains( p );
#endif
                if( !hit ) {
                    continue;
                }
                safemode_corner_tooltip.clear_pointer();
                if( secondary ) {
                    if( i < safemode_corner_safe_index && query_safemode_corner_change_menu( p ) ) {
                        const std::optional<action_id> selected = query_safemode_corner_menu();
                        if( selected ) {
                            assign_safemode_corner_menu_slot( i, *selected );
                        }
                        invalidate_main_ui_adaptor();
                        ui_manager::redraw_invalidated();
                    }
                    return ACTION_CLICK_AND_DRAG;
                }
#if defined(TILES)
                const ui_action_result result = safemode_corner_buttons[i].handle_pixel_input( "SELECT",
                                                pixel_p );
#else
                const ui_action_result result = safemode_corner_buttons[i].handle_input( "SELECT", p );
#endif
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    if( result.entry->id == "SAFE_MODE_TOGGLE" ) {
                        invalidate_main_ui_adaptor();
                        return ACTION_TOGGLE_SAFEMODE;
                    }
                    if( i < safemode_corner_safe_index ) {
                        const action_id assigned = safemode_corner_menu_slot_action( i );
                        if( assigned != ACTION_NULL ) {
                            return assigned;
                        }
                        const std::optional<action_id> selected = query_safemode_corner_menu();
                        if( selected ) {
                            assign_safemode_corner_menu_slot( i, *selected );
                        }
                        invalidate_main_ui_adaptor();
                        ui_manager::redraw_invalidated();
                        return ACTION_CLICK_AND_DRAG;
                    }
                }
                return ACTION_CLICK_AND_DRAG;
            }

            for( int extra = 0; extra < static_cast<int>( safemode_corner_extra_buttons.size() ); ++extra ) {
                ui_icon_button &button = *safemode_corner_extra_buttons[extra];
#if defined(TILES)
                const bool hit = pixel_p && button.contains_pixel( *pixel_p );
#else
                const bool hit = button.contains( p );
#endif
                if( !hit ) {
                    continue;
                }
                const int slot = safemode_corner_base_slot_count + extra;
                safemode_corner_tooltip.clear_pointer();
                if( secondary ) {
                    if( query_safemode_corner_change_menu( p ) ) {
                        const std::optional<action_id> selected = query_safemode_corner_menu();
                        if( selected ) {
                            assign_safemode_corner_menu_slot( slot, *selected );
                        }
                        invalidate_main_ui_adaptor();
                        ui_manager::redraw_invalidated();
                    }
                    return ACTION_CLICK_AND_DRAG;
                }
                const action_id assigned = safemode_corner_menu_slot_action( slot );
                if( assigned != ACTION_NULL ) {
                    return assigned;
                }
                const std::optional<action_id> selected = query_safemode_corner_menu();
                if( selected ) {
                    assign_safemode_corner_menu_slot( slot, *selected );
                }
                invalidate_main_ui_adaptor();
                ui_manager::redraw_invalidated();
                return ACTION_CLICK_AND_DRAG;
            }
        }
    }

    if( secondary ) {
        return ACTION_NULL;
    }

'''
path.write_text(text[:begin] + new_head + text[finish:], encoding="utf-8")

replace_once(
    "src/handle_action.cpp",
    '''        if( act == ACTION_SELECT ) {\n            // Safemode controls are screen-space curses UI, not terrain-space map cells.\n            // Resolve the click against stdscr so tile zoom cannot move the hitboxes.\n            const std::optional<point> ui_mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );\n#if defined(TILES)\n            const std::optional<point> ui_mouse_pixel = ctxt.get_coordinates_pixel();\n#else\n            const std::optional<point> ui_mouse_pixel = std::nullopt;\n#endif\n            if( ui_mouse_pos ) {\n                const action_id safemode_action = get_safemode_mouse_action( *ui_mouse_pos,\n                                                  ui_mouse_pixel );\n                if( safemode_action != ACTION_NULL ) {\n                    act = safemode_action;\n                }\n            }\n        }\n''',
    '''        if( act == ACTION_SELECT || act == ACTION_SEC_SELECT ) {\n            // HUD controls own their screen-space hitboxes. Resolve both mouse buttons here\n            // before terrain targeting so clicks cannot leak through to map tiles underneath.\n            const std::optional<point> ui_mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );\n#if defined(TILES)\n            const std::optional<point> ui_mouse_pixel = ctxt.get_coordinates_pixel();\n#else\n            const std::optional<point> ui_mouse_pixel = std::nullopt;\n#endif\n            if( ui_mouse_pos ) {\n                const action_id safemode_action = get_safemode_mouse_action( *ui_mouse_pos,\n                                                  ui_mouse_pixel, act == ACTION_SEC_SELECT );\n                if( safemode_action != ACTION_NULL ) {\n                    act = safemode_action;\n                }\n            }\n        }\n'''
)
