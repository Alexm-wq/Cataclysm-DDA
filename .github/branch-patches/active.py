from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Keep only the helpers actually used by the compact corner palette.
replace_once(
    "src/game.h",
    '''#include "ui_helpers/controls/action_strip.h"\n#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/controls/icon_button.h"\n#include "ui_helpers/controls/tooltip.h"\n#include "ui_helpers/primitive/overlay.h"\n''',
    '''#include "ui_helpers/controls/icon_button.h"\n#include "ui_helpers/controls/tooltip.h"\n''',
    "game helper includes",
)

replace_once(
    "src/game.h",
    '''        /** Draw the compact pixel-minimap safemode menu and threat alert HUD. */\n        void draw_safemode_mouse_controls();\n        /** Keep helper hover/menu state synchronized with normal gameplay mouse input. */\n        void update_safemode_mouse_hover( input_context &ctxt, const std::string &action );\n        /** Open or refresh the five-row corner menu using current safemode state. */\n        void configure_safemode_corner_menu();\n        /** Resolve a screen-space click through the shared safemode UI controls. */\n        action_id get_safemode_mouse_action( const point &p );\n''',
    '''        /** Draw the compact pixel-minimap safemode palette and threat alert HUD. */\n        void draw_safemode_mouse_controls();\n        /** Keep helper hover/tooltip state synchronized with normal gameplay mouse input. */\n        void update_safemode_mouse_hover( input_context &ctxt, const std::string &action );\n        /** Resolve a screen-space click through the shared safemode UI controls. */\n        action_id get_safemode_mouse_action( const point &p );\n''',
    "safemode declarations",
)

replace_once(
    "src/game.h",
    '''        ui_icon_button safemode_corner_button; // NOLINT(cata-serialize)\n        ui_dropdown safemode_corner_menu; // NOLINT(cata-serialize)\n        ui_tooltip safemode_corner_tooltip; // NOLINT(cata-serialize)\n''',
    '''        ui_icon_button safemode_corner_launcher; // NOLINT(cata-serialize)\n        std::array<ui_icon_button, 5> safemode_corner_buttons; // NOLINT(cata-serialize)\n        ui_tooltip safemode_corner_tooltip; // NOLINT(cata-serialize)\n        bool safemode_corner_expanded = false; // NOLINT(cata-serialize)\n''',
    "safemode helper state",
)

p = Path("src/game.cpp")
text = p.read_text(encoding="utf-8")
start_marker = "static constexpr int safemode_corner_menu_width = 22;"
end_marker = "void game::draw_vehicle_mouse_controls()"
if text.count(start_marker) != 1:
    raise SystemExit(f"safemode block start: expected 1 anchor, found {text.count(start_marker)}")
if text.count(end_marker) != 1:
    raise SystemExit(f"safemode block end: expected 1 anchor, found {text.count(end_marker)}")
start = text.index(start_marker)
end = text.index(end_marker, start)

new_block = r'''static constexpr int safemode_corner_button_count = 5;
static constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;
static const point safemode_corner_icon_pixels( 12, 12 );

static point safemode_corner_button_size()
{
    return ui_icon_button::square_size_for_icon( catacurses::stdscr,
            safemode_corner_icon_pixels );
}

// The pixel minimap is only the anchor.  All controls render against stdscr so
// the expanded column is free to sit immediately outside the panel's left edge.
static point safemode_corner_launcher_pos( const catacurses::window &panel )
{
    const point size = safemode_corner_button_size();
    return point( getbegx( panel ),
                  getbegy( panel ) + getmaxy( panel ) - size.y );
}

static point safemode_corner_palette_pos( const catacurses::window &panel, const int index )
{
    const point size = safemode_corner_button_size();
    const point launcher = safemode_corner_launcher_pos( panel );
    const int rows_above_bottom = safemode_corner_safe_index - index;
    return point( getbegx( panel ) - size.x,
                  launcher.y - rows_above_bottom * size.y );
}

static bool safemode_corner_controls_fit( const catacurses::window &panel )
{
    if( !panel || !catacurses::stdscr ) {
        return false;
    }
    const point size = safemode_corner_button_size();
    if( getmaxx( panel ) < size.x || getmaxy( panel ) < size.y ) {
        return false;
    }
    const point launcher = safemode_corner_launcher_pos( panel );
    const point top_button = safemode_corner_palette_pos( panel, 0 );
    return launcher.x >= 0 && launcher.y >= 0 &&
           launcher.x + size.x <= getmaxx( catacurses::stdscr ) &&
           launcher.y + size.y <= getmaxy( catacurses::stdscr ) &&
           top_button.x >= 0 && top_button.y >= 0;
}

void game::draw_safemode_mouse_controls()
{
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ||
        !safemode_corner_controls_fit( w_pixel_minimap ) ) {
        safemode_corner_launcher.close();
        for( ui_icon_button &button : safemode_corner_buttons ) {
            button.close();
        }
        safemode_corner_tooltip.reset();
        safemode_corner_expanded = false;
        return;
    }

    const point button_size = safemode_corner_button_size();
    const point launcher_pos = safemode_corner_launcher_pos( w_pixel_minimap );

    ui_icon_button_style launcher_style;
    launcher_style.border = c_light_gray;
    launcher_style.fill = i_dark_gray;
    launcher_style.icon = c_light_gray;
    launcher_style.hover_border = c_white;
    launcher_style.hover_fill = i_light_gray;
    launcher_style.hover_icon = c_white;
    safemode_corner_launcher.configure( catacurses::stdscr, launcher_pos, button_size,
                                        ui_action_entry( "", "SAFE_CORNER_EXPAND" ),
                                        "<", launcher_style );
    safemode_corner_launcher.draw( catacurses::stdscr );

    if( safemode_corner_expanded ) {
        const bool enabled = safe_mode != SAFE_MODE_OFF;
        for( int i = 0; i < safemode_corner_button_count; ++i ) {
            const bool is_safe = i == safemode_corner_safe_index;
            ui_icon_button_style style;
            ui_action_entry action( "", is_safe ? "SAFE_MODE_TOGGLE" :
                                    string_format( "SAFE_RESERVED_%d", i ), is_safe );
            std::string icon = is_safe ? "!" : " ";

            if( is_safe ) {
                const nc_color state_color = enabled ? c_light_green : c_light_red;
                style.icon = state_color;
                style.hover_icon = state_color;
                style.selected_icon = state_color;
            } else {
                style.disabled_border = c_dark_gray;
                style.disabled_fill = i_dark_gray;
                style.disabled_icon = c_dark_gray;
            }

            safemode_corner_buttons[i].configure(
                catacurses::stdscr,
                safemode_corner_palette_pos( w_pixel_minimap, i ),
                button_size, std::move( action ), std::move( icon ), style );
            safemode_corner_buttons[i].draw( catacurses::stdscr );
        }

        const auto safe_bounds = safemode_corner_buttons[safemode_corner_safe_index].bounds();
        if( safe_bounds ) {
            const std::string tooltip_text = string_format( "%s: %s", _( "Safe mode" ),
                                             enabled ? _( "ON" ) : _( "OFF" ) );
            const int tooltip_width = std::min( getmaxx( catacurses::stdscr ),
                                                std::max( 8, utf8_width( tooltip_text ) + 4 ) );
            const point safe_pos = safemode_corner_palette_pos(
                                       w_pixel_minimap, safemode_corner_safe_index );
            const point tooltip_pos( std::max( 0, safe_pos.x - tooltip_width - 1 ),
                                     std::max( 0, safe_pos.y - 1 ) );
            safemode_corner_tooltip.configure( catacurses::stdscr, *safe_bounds, tooltip_pos,
                                               tooltip_text, std::chrono::milliseconds( 1000 ),
                                               tooltip_width );
            safemode_corner_tooltip.draw( catacurses::stdscr );
        }
    } else {
        for( ui_icon_button &button : safemode_corner_buttons ) {
            button.close();
        }
        safemode_corner_tooltip.reset();
    }

    const bool threat_stopped = safe_mode == SAFE_MODE_STOP || u.has_effect( effect_laserlocked );
    if( !threat_stopped || TERMX < 28 || TERMY < 6 ) {
        return;
    }

    const int left = 1;
    const int top = 2;
    const int width = std::min( 56, TERMX - left );
    const int inner_width = width - 2;
    if( inner_width < 20 ) {
        return;
    }

    catacurses::window alert = catacurses::newwin( 4, width, point( left, top ) );
    werase( alert );
    wborder( alert, LINE_XOXO, LINE_XOXO, LINE_OXOX, LINE_OXOX,
             LINE_OXXO, LINE_OOXX, LINE_XXOO, LINE_XOOX );

    trim_and_print( alert, point( 2, 1 ), inner_width - 2, c_yellow,
                    _( "[!] Enemy spotted - safe mode paused" ) );

    const std::string alert_toggle = safemode_mouse_toggle_label( true );
    const std::string ignore_label = safemode_mouse_ignore_label();
    const int alert_toggle_width = utf8_width( alert_toggle );
    const int ignore_width = utf8_width( ignore_label );
    const int available = inner_width - 2;

    int x = 2;
    if( alert_toggle_width + 1 + ignore_width <= available ) {
        trim_and_print( alert, point( x, 2 ), alert_toggle_width, c_light_green,
                        alert_toggle );
        x += alert_toggle_width + 1;
    }
    if( ignore_width <= width - 1 - x ) {
        trim_and_print( alert, point( x, 2 ), ignore_width, c_yellow, ignore_label );
    }
    wnoutrefresh( alert );
}

void game::update_safemode_mouse_hover( input_context &ctxt, const std::string &action )
{
    if( uquit == QUIT_WATCH || !safemode_corner_controls_fit( w_pixel_minimap ) ) {
        safemode_corner_tooltip.clear_pointer();
        return;
    }

    const std::optional<point> mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );
    bool tooltip_changed = false;

    if( action == "TIMEOUT" ) {
        tooltip_changed = safemode_corner_tooltip.tick();
    } else if( mouse_pos ) {
        safemode_corner_launcher.handle_input( "MOUSE_MOVE", mouse_pos );
        if( safemode_corner_expanded ) {
            for( ui_icon_button &button : safemode_corner_buttons ) {
                button.handle_input( "MOUSE_MOVE", mouse_pos );
            }
            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );
        } else {
            tooltip_changed = safemode_corner_tooltip.clear_pointer();
        }
    } else if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ) {
        safemode_corner_launcher.update_hover( std::nullopt );
        for( ui_icon_button &button : safemode_corner_buttons ) {
            button.update_hover( std::nullopt );
        }
        tooltip_changed = safemode_corner_tooltip.clear_pointer();
    }

    if( tooltip_changed ) {
        invalidate_main_ui_adaptor();
        if( action == "TIMEOUT" ) {
            ui_manager::redraw();
        }
    }
}

action_id game::get_safemode_mouse_action( const point &p )
{
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ) {
        return ACTION_NULL;
    }

    if( safemode_corner_controls_fit( w_pixel_minimap ) ) {
        const ui_action_result launcher_result = safemode_corner_launcher.handle_input( "SELECT", p );
        if( launcher_result.type == ui_action_result_type::activated ) {
            safemode_corner_expanded = !safemode_corner_expanded;
            safemode_corner_tooltip.clear_pointer();
            invalidate_main_ui_adaptor();
            return ACTION_CLICK_AND_DRAG;
        }

        if( safemode_corner_expanded ) {
            for( int i = 0; i < safemode_corner_button_count; ++i ) {
                const ui_action_result result = safemode_corner_buttons[i].handle_input( "SELECT", p );
                if( result.type == ui_action_result_type::activated && result.entry &&
                    result.entry->id == "SAFE_MODE_TOGGLE" ) {
                    safemode_corner_tooltip.clear_pointer();
                    invalidate_main_ui_adaptor();
                    return ACTION_TOGGLE_SAFEMODE;
                }
                if( result.type == ui_action_result_type::disabled ) {
                    return ACTION_CLICK_AND_DRAG;
                }
            }
        }
    }

    const bool threat_stopped = safe_mode == SAFE_MODE_STOP || u.has_effect( effect_laserlocked );
    if( !threat_stopped || TERMX < 28 || TERMY < 6 ) {
        return ACTION_NULL;
    }

    const int left = 1;
    const int top = 2;
    const int width = std::min( 56, TERMX - left );
    const int inner_width = width - 2;
    if( inner_width < 20 ) {
        return ACTION_NULL;
    }

    const std::string alert_toggle = safemode_mouse_toggle_label( true );
    const std::string ignore_label = safemode_mouse_ignore_label();
    const int alert_toggle_width = utf8_width( alert_toggle );
    const int ignore_width = utf8_width( ignore_label );
    const int available = inner_width - 2;

    int x = left + 2;
    if( alert_toggle_width + 1 + ignore_width <= available ) {
        if( p.y == top + 2 && p.x >= x && p.x < x + alert_toggle_width ) {
            return ACTION_TOGGLE_SAFEMODE;
        }
        x += alert_toggle_width + 1;
    }
    if( p.y == top + 2 && p.x >= x && p.x < x + ignore_width &&
        x + ignore_width <= left + width - 1 ) {
        return ACTION_IGNORE_ENEMY;
    }

    if( p.x >= left && p.x < left + width && p.y >= top && p.y < top + 4 ) {
        return ACTION_CLICK_AND_DRAG;
    }
    return ACTION_NULL;
}

'''

p.write_text(text[:start] + new_block + text[end:], encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix safemode corner palette geometry\n", encoding="utf-8"
)
