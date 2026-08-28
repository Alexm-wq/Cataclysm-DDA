from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path_str: str, start: str, end: str, replacement: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(f"expected unique markers in {path_str}")
    begin = text.index(start)
    finish = text.index(end, begin)
    path.write_text(text[:begin] + replacement + text[finish:], encoding="utf-8")


# Pixel HUD controls are configured during normal redraws.  Re-registering an
# unchanged overlay must be a no-op; otherwise set_ui_pixel_icon_button() feeds
# needupdate on every frame and can create a redraw loop/flicker.
replace_once(
    "src/sdltiles.cpp",
    '''    if( found == ui_pixel_icon_buttons.end() ) {\n        ui_pixel_icon_buttons.push_back( layered );\n    } else {\n        *found = layered;\n    }\n    needupdate = true;\n''',
    '''    if( found == ui_pixel_icon_buttons.end() ) {\n        ui_pixel_icon_buttons.push_back( layered );\n        needupdate = true;\n        return;\n    }\n\n    const bool unchanged = found->parent == layered.parent &&\n                           found->pos_pixels == layered.pos_pixels &&\n                           found->size_pixels == layered.size_pixels &&\n                           found->border_color_pair == layered.border_color_pair &&\n                           found->fill_color_pair == layered.fill_color_pair &&\n                           found->icon_color_pair == layered.icon_color_pair &&\n                           found->icon == layered.icon;\n    if( unchanged ) {\n        return;\n    }\n\n    *found = layered;\n    needupdate = true;\n'''
)

# Staying in pixel mode should update the existing overlay in place.  Clearing
# it first guarantees two dirty transitions per redraw.  Invalid configuration,
# close(), and transitions back to curses still clear it explicitly.
replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void configure_pixel( const catacurses::window &parent, point pixel_pos, point pixel_size,\n                              ui_action_entry action, std::string icon,\n                              const ui_icon_button_style &style = ui_icon_button_style() ) {\n            clear_ui_pixel_icon_button( this );\n            overlay_.close();\n''',
    '''        void configure_pixel( const catacurses::window &parent, point pixel_pos, point pixel_size,\n                              ui_action_entry action, std::string icon,\n                              const ui_icon_button_style &style = ui_icon_button_style() ) {\n            overlay_.close();\n'''
)

# Make the shortcut picker a real modal UI.  A raw newwin/input loop is outside
# ui_manager's stack, so normal map redraws can race it and visibly alternate
# frames.  disable_uis_below gives the picker stable ownership until it closes.
new_picker = r'''static std::optional<action_id> query_safemode_corner_menu()
{
    int width = std::min( 68, TERMX - 4 );
    int height = std::min( 24, TERMY - 4 );
    if( width < 32 || height < 12 ) {
        return std::nullopt;
    }

    catacurses::window window;
    ui_text_field search_field;
    ui_action_strip categories;
    ui_action_strip navigation;
    ui_selection_list menu_list;
    menu_list.activate_on_single_click();

    input_context ctxt( "SAFE_CORNER_MENU_PICKER" );
    for( const std::string &action : { "UP", "DOWN", "PAGE_UP", "PAGE_DOWN",
                                      "HOME", "END", "CONFIRM", "QUIT", "SELECT",
                                      "MOUSE_MOVE", "SCROLL_UP", "SCROLL_DOWN" } ) {
        ctxt.register_action( action );
    }

    std::string search;
    const std::vector<safemode_corner_menu_candidate> candidates = safemode_corner_menu_candidates();
    const auto rebuild_list = [&]() {
        std::vector<ui_action_entry> entries;
        for( const safemode_corner_menu_candidate &candidate : candidates ) {
            if( !search.empty() && !lcmatch( candidate.label, search ) &&
                !lcmatch( candidate.category, search ) ) {
                continue;
            }
            entries.emplace_back( candidate.label, action_ident( candidate.action ) );
        }
        menu_list.set_entries( std::move( entries ), false );
    };
    rebuild_list();

    ui_adaptor ui( ui_adaptor::disable_uis_below{} );
    ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
        width = std::min( 68, TERMX - 4 );
        height = std::min( 24, TERMY - 4 );
        if( width < 32 || height < 12 ) {
            window = catacurses::window();
            adaptor.position( point::zero, point::zero );
            return;
        }
        const point origin( std::max( 0, ( TERMX - width ) / 2 ),
                            std::max( 0, ( TERMY - height ) / 2 ) );
        window = catacurses::newwin( height, width, origin );
        adaptor.position_from_window( window );
    } );
    ui.mark_resize();

    ui.on_redraw( [&]( ui_adaptor & adaptor ) {
        if( !window ) {
            return;
        }
        werase( window );
        draw_border( window, c_light_gray );
        trim_and_print( window, point( 2, 1 ), width - 4, c_light_green,
                        _( "Assign menu shortcut" ) );

        const std::vector<ui_action_strip_item> nav_items = {
            { ui_action_entry( _( "Back" ), "BACK" ), 0, ui_action_alignment::right }
        };
        navigation.configure( window, point( 2, 1 ), nav_items, width - 4, 1 );
        navigation.draw( window );

        search_field.configure( window, point( 2, 3 ), width - 4, _( "Search: " ), search,
                                _( "menu name" ), true );
        search_field.draw( window );

        ui_action_strip_style category_style;
        category_style.text = c_light_cyan;
        category_style.selected = h_light_cyan;
        category_style.disabled = c_dark_gray;
        categories.configure( window, point( 2, 5 ), {
            ui_action_entry( _( "All" ), "CATEGORY_ALL", true, true ),
            ui_action_entry( _( "Inventory" ), "CATEGORY_INVENTORY", false ),
            ui_action_entry( _( "Crafting" ), "CATEGORY_CRAFTING", false ),
            ui_action_entry( _( "World" ), "CATEGORY_WORLD", false ),
            ui_action_entry( _( "Character" ), "CATEGORY_CHARACTER", false ),
            ui_action_entry( _( "Info" ), "CATEGORY_INFO", false )
        }, width - 4, 2, category_style );
        categories.draw( window );

        trim_and_print( window, point( 2, 7 ), width - 4, c_light_gray,
                        _( "Available map menus" ) );
        menu_list.draw( window, point( 2, 8 ), width - 4, std::max( 1, height - 10 ) );
        adaptor.disable_cursor();
        wnoutrefresh( window );
    } );

    const auto edit_search = [&]() {
        string_input_popup popup;
        popup.window( window, search_field.edit_start(), search_field.edit_end_x() )
        .text( search )
        .max_length( 60 )
        .string_color( c_white )
        .cursor_color( h_light_gray )
        .underscore_color( c_light_gray );
        popup.query();
        if( !popup.canceled() ) {
            search = popup.text();
            rebuild_list();
        }
    };

    while( true ) {
        ui_manager::redraw();
        if( !window ) {
            return std::nullopt;
        }

        const std::string action = ctxt.handle_input();
        const std::optional<point> pos = ctxt.get_coordinates_text( window );
        if( action == "QUIT" ) {
            return std::nullopt;
        }

        if( action == "MOUSE_MOVE" || action == "SELECT" ) {
            const ui_action_result back_result = navigation.handle_input( action, pos );
            if( back_result.type == ui_action_result_type::activated ) {
                return std::nullopt;
            }
            const ui_action_result category_result = categories.handle_input( action, pos );
            if( action == "SELECT" && category_result.consumed() ) {
                continue;
            }
        }

        if( action == "SELECT" && pos ) {
            const ui_text_field_hit search_hit = search_field.hit_test( *pos );
            if( search_hit == ui_text_field_hit::clear ) {
                if( !search.empty() ) {
                    search.clear();
                    rebuild_list();
                }
                continue;
            }
            if( search_hit == ui_text_field_hit::edit ) {
                edit_search();
                continue;
            }
        }

        const ui_action_result list_result = menu_list.handle_input( action, ctxt, pos );
        if( list_result.type == ui_action_result_type::activated && list_result.entry ) {
            const action_id selected = look_up_action( list_result.entry->id );
            if( selected != ACTION_NULL ) {
                return selected;
            }
        }
    }
}

'''
replace_between(
    "src/game.cpp",
    "static std::optional<action_id> query_safemode_corner_menu()\n{\n",
    "void game::draw_safemode_mouse_controls()\n",
    new_picker,
)
