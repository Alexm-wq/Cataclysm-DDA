from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly 1 anchor, found {count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


def insert_after_once(path: str, anchor: str, addition: str, label: str) -> None:
    replace_once(path, anchor, anchor + addition, label)


# Shared delayed tooltip control.  The screen supplies geometry/text; the helper
# owns stationary-hover timing, transient overlay rendering, and visibility state.
tooltip = Path('src/ui_helpers/controls/tooltip.h')
if tooltip.exists():
    raise SystemExit('tooltip helper already exists; refusing to overwrite')
tooltip.write_text(r'''#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_TOOLTIP_H
#define CATA_SRC_UI_HELPERS_CONTROLS_TOOLTIP_H

#include <algorithm>
#include <chrono>
#include <optional>
#include <string>
#include <utility>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../output.h"
#include "../../point.h"
#include "../primitive/overlay.h"

/** Visual policy for a delayed tooltip overlay. */
struct ui_tooltip_style {
    nc_color border = c_dark_gray;
    nc_color text = c_light_gray;
};

/**
 * Reusable tooltip that appears after the pointer remains stationary over a
 * caller-provided target rectangle for a configured delay.
 *
 * The caller owns placement and text.  This helper owns hover dwell timing,
 * pointer-motion reset semantics, transient overlay rendering, and visibility.
 */
class ui_tooltip
{
    public:
        using clock = std::chrono::steady_clock;

        void configure( const catacurses::window &parent,
                        const inclusive_rectangle<point> &target_bounds,
                        point pos, std::string text,
                        const std::chrono::milliseconds delay = std::chrono::milliseconds( 1000 ),
                        const int requested_width = 0,
                        const ui_tooltip_style &style = ui_tooltip_style() ) {
            target_bounds_ = target_bounds;
            pos_ = pos;
            text_ = std::move( text );
            delay_ = std::max( std::chrono::milliseconds::zero(), delay );
            requested_width_ = requested_width;
            style_ = style;

            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            if( parent_width < 3 || parent_height < 3 || text_.empty() ) {
                reset();
            }
        }

        /**
         * Update the current pointer position.  Moving even within the same target
         * restarts the dwell timer, matching conventional delayed-tooltip behavior.
         * Returns true when visible state changed.
         */
        bool update_pointer( const std::optional<point> &parent_pos,
                             const clock::time_point now = clock::now() ) {
            const bool was_visible = visible_;
            if( !parent_pos || !target_bounds_ || !target_bounds_->contains( *parent_pos ) ) {
                clear_pointer_state();
                return was_visible != visible_;
            }

            if( !last_pointer_ || *last_pointer_ != *parent_pos ) {
                last_pointer_ = *parent_pos;
                hover_started_ = now;
                visible_ = delay_ == std::chrono::milliseconds::zero();
                if( !visible_ ) {
                    overlay_.hide();
                }
                return was_visible != visible_;
            }

            if( !hover_started_ ) {
                hover_started_ = now;
            }
            if( !visible_ && now - *hover_started_ >= delay_ ) {
                visible_ = true;
            }
            return was_visible != visible_;
        }

        /** Advance only wall-clock dwell time while the pointer remains stationary. */
        bool tick( const clock::time_point now = clock::now() ) {
            const bool was_visible = visible_;
            if( !visible_ && last_pointer_ && target_bounds_ &&
                target_bounds_->contains( *last_pointer_ ) && hover_started_ &&
                now - *hover_started_ >= delay_ ) {
                visible_ = true;
            }
            return was_visible != visible_;
        }

        /** Forget current hover/dwell state while retaining configured geometry. */
        bool clear_pointer() {
            const bool was_visible = visible_;
            clear_pointer_state();
            return was_visible != visible_;
        }

        void reset() {
            clear_pointer_state();
            target_bounds_.reset();
            text_.clear();
            pos_ = point::zero;
            requested_width_ = 0;
            overlay_.close();
        }

        bool visible() const {
            return visible_;
        }

        void draw( const catacurses::window &parent ) {
            if( !visible_ || !target_bounds_ || text_.empty() || getmaxx( parent ) < 3 ||
                getmaxy( parent ) < 3 ) {
                overlay_.hide();
                return;
            }

            const int preferred_width = requested_width_ > 0 ? requested_width_ : utf8_width( text_ ) + 4;
            const int width = std::clamp( preferred_width, 3, getmaxx( parent ) );
            overlay_.configure( parent, pos_, width, 3 );
            catacurses::window &window = overlay_.begin_draw( parent );
            if( !window ) {
                return;
            }
            draw_border( window, style_.border );
            trim_and_print( window, point( 1, 1 ), std::max( 1, width - 2 ), style_.text, text_ );
            overlay_.refresh();
        }

    private:
        void clear_pointer_state() {
            last_pointer_.reset();
            hover_started_.reset();
            visible_ = false;
            overlay_.hide();
        }

        ui_overlay overlay_;
        std::optional<inclusive_rectangle<point>> target_bounds_;
        std::optional<point> last_pointer_;
        std::optional<clock::time_point> hover_started_;
        point pos_ = point::zero;
        std::string text_;
        std::chrono::milliseconds delay_ = std::chrono::milliseconds( 1000 );
        int requested_width_ = 0;
        ui_tooltip_style style_;
        bool visible_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_TOOLTIP_H
''', encoding='utf-8')

# Inside-menu border clicks must never inherit the outside-click passthrough bit.
replace_once(
    'src/ui_helpers/controls/dropdown.h',
    '''            const bool pass_outside = ui_outside_pointer_passthrough( outside_click, over_trigger );''',
    '''            const bool pass_outside = !inside &&
                                      ui_outside_pointer_passthrough( outside_click, over_trigger );''',
    'dropdown inside/outside passthrough'
)

# game owns persistent helper state; layout remains in game.cpp.
insert_after_once(
    'src/game.h',
    '#include "type_id.h"\n',
    '#include "ui_helpers/controls/action_strip.h"\n'
    '#include "ui_helpers/controls/dropdown.h"\n'
    '#include "ui_helpers/controls/tooltip.h"\n'
    '#include "ui_helpers/primitive/overlay.h"\n',
    'game helper includes'
)

replace_once(
    'src/game.h',
    '''        /** Draw the persistent mouse safemode toggle and threat alert on the terrain HUD. */
        void draw_safemode_mouse_controls();
        /** Resolve a terrain-window click to a safemode HUD action, or ACTION_NULL. */
        action_id get_safemode_mouse_action( const point &p ) const;''',
    '''        /** Draw the compact pixel-minimap safemode menu and threat alert HUD. */
        void draw_safemode_mouse_controls();
        /** Keep helper hover/menu state synchronized with normal gameplay mouse input. */
        void update_safemode_mouse_hover( input_context &ctxt, const std::string &action );
        /** Open or refresh the five-row corner menu using current safemode state. */
        void configure_safemode_corner_menu();
        /** Resolve a screen-space click through the shared safemode UI controls. */
        action_id get_safemode_mouse_action( const point &p );''',
    'game safemode declarations'
)

insert_after_once(
    'src/game.h',
    '''        catacurses::window w_pixel_minimap; // NOLINT(cata-serialize)\n''',
    '''        ui_overlay safemode_corner_button_overlay; // NOLINT(cata-serialize)
        ui_action_strip safemode_corner_button; // NOLINT(cata-serialize)
        ui_dropdown safemode_corner_menu; // NOLINT(cata-serialize)
        ui_tooltip safemode_corner_tooltip; // NOLINT(cata-serialize)
''',
    'game safemode helper state'
)

# Reset the cached pixel-minimap window before panel composition so a disabled/moved
# panel cannot leave a stale button anchor behind.
replace_once(
    'src/game.cpp',
    '''    draw_panels( true );

    // Render safemode controls as independent curses windows after the normal''',
    '''    w_pixel_minimap = catacurses::window();
    draw_panels( true );

    // Render safemode controls as independent curses windows after the normal''',
    'pixel minimap anchor reset'
)

# Feed mouse movement and the existing 125 ms idle ticks into the shared delayed
# tooltip.  This makes the one-second tooltip appear while the pointer is stationary.
replace_once(
    'src/game.cpp',
    '''bool game::handle_mouseview( input_context &ctxt, std::string &action )
{
    action = ctxt.handle_input();
#if defined(TILES)''',
    '''bool game::handle_mouseview( input_context &ctxt, std::string &action )
{
    action = ctxt.handle_input();
    update_safemode_mouse_hover( ctxt, action );
#if defined(TILES)''',
    'game mouseview tooltip update'
)

old_safe_block = r'''static std::string safemode_mouse_hotkey( const action_id action )
{
    const std::optional<input_event> hotkey = hotkey_for_action(
            action, /*maximum_modifier_count=*/1, /*restrict_to_printable=*/false );
    return hotkey ? hotkey->short_description() : "?";
}

static std::string safemode_mouse_toggle_label( const bool enabled )
{
    return string_format( "[ %s %s (%s) ]", _( "SAFE" ), enabled ? _( "ON" ) : _( "OFF" ),
                          safemode_mouse_hotkey( ACTION_TOGGLE_SAFEMODE ) );
}

static std::string safemode_mouse_ignore_label()
{
    return string_format( "[ %s (%s) ]", _( "IGNORE" ),
                          safemode_mouse_hotkey( ACTION_IGNORE_ENEMY ) );
}

void game::draw_safemode_mouse_controls()
{
    // These controls are screen UI, not map tiles.  Always size and position them
    // in terminal cells so tile zoom can never scale the overlay geometry.
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ) {
        return;
    }

    const bool enabled = safe_mode != SAFE_MODE_OFF;
    const std::string toggle_label = safemode_mouse_toggle_label( enabled );
    const int toggle_left = 1;
    const int toggle_top = 0;
    const int toggle_width = std::min( utf8_width( toggle_label ), TERMX - toggle_left );
    if( toggle_width > 0 ) {
        catacurses::window toggle = catacurses::newwin( 1, toggle_width,
                                      point( toggle_left, toggle_top ) );
        werase( toggle );
        trim_and_print( toggle, point::zero, toggle_width,
                        enabled ? c_light_green : c_light_red, toggle_label );
        wnoutrefresh( toggle );
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

action_id game::get_safemode_mouse_action( const point &p ) const
{
    // p is a stdscr-relative terminal-cell coordinate.  Keep this layout exactly
    // matched to draw_safemode_mouse_controls().
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ) {
        return ACTION_NULL;
    }

    const int toggle_left = 1;
    const int toggle_top = 0;
    const std::string toggle_label = safemode_mouse_toggle_label( safe_mode != SAFE_MODE_OFF );
    const int toggle_width = std::min( utf8_width( toggle_label ), TERMX - toggle_left );
    if( p.y == toggle_top && p.x >= toggle_left && p.x < toggle_left + toggle_width ) {
        return ACTION_TOGGLE_SAFEMODE;
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
        // Deliberately return only the native ignore action here.  Its normal
        // SAFE_MODE_STOP branch marks the currently seen monsters ignored and
        // restores SAFE_MODE_ON; it never disables safemode.
        return ACTION_IGNORE_ENEMY;
    }

    // Consume clicks on the alert panel itself so they cannot leak through to map actions.
    if( p.x >= left && p.x < left + width && p.y >= top && p.y < top + 4 ) {
        return ACTION_CLICK_AND_DRAG;
    }
    return ACTION_NULL;
}
'''

new_safe_block = r'''static std::string safemode_mouse_hotkey( const action_id action )
{
    const std::optional<input_event> hotkey = hotkey_for_action(
            action, /*maximum_modifier_count=*/1, /*restrict_to_printable=*/false );
    return hotkey ? hotkey->short_description() : "?";
}

static std::string safemode_mouse_toggle_label( const bool enabled )
{
    return string_format( "[ %s %s (%s) ]", _( "SAFE" ), enabled ? _( "ON" ) : _( "OFF" ),
                          safemode_mouse_hotkey( ACTION_TOGGLE_SAFEMODE ) );
}

static std::string safemode_mouse_ignore_label()
{
    return string_format( "[ %s (%s) ]", _( "IGNORE" ),
                          safemode_mouse_hotkey( ACTION_IGNORE_ENEMY ) );
}

static constexpr int safemode_corner_button_width = 5;
static constexpr int safemode_corner_menu_width = 22;
static constexpr int safemode_corner_menu_rows = 5;

static point safemode_corner_button_pos( const catacurses::window &window )
{
    return point( std::max( 0, getmaxx( window ) - safemode_corner_button_width - 1 ),
                  std::max( 0, getmaxy( window ) - 2 ) );
}

static inclusive_rectangle<point> safemode_corner_button_bounds( const catacurses::window &window )
{
    const point pos = safemode_corner_button_pos( window );
    return inclusive_rectangle<point>( pos,
                                       point( pos.x + safemode_corner_button_width - 1, pos.y ) );
}

static std::vector<ui_dropdown_entry> safemode_corner_entries( const bool enabled )
{
    std::vector<ui_dropdown_entry> entries;
    entries.reserve( safemode_corner_menu_rows );
    for( int i = 0; i < safemode_corner_menu_rows - 1; ++i ) {
        entries.emplace_back( "—", string_format( "SAFE_RESERVED_%d", i ), false );
    }
    entries.emplace_back( string_format( "%s: %s", _( "Safe mode" ),
                                         enabled ? _( "ON" ) : _( "OFF" ) ),
                          "SAFE_MODE_TOGGLE" );
    return entries;
}

void game::configure_safemode_corner_menu()
{
    if( !w_pixel_minimap || getmaxx( w_pixel_minimap ) < safemode_corner_button_width + 3 ||
        getmaxy( w_pixel_minimap ) < 3 ) {
        safemode_corner_menu.close();
        return;
    }

    const point button_pos = safemode_corner_button_pos( w_pixel_minimap );
    const int available_left = std::max( 3, button_pos.x - 1 );
    const int menu_width = std::min( safemode_corner_menu_width, available_left );
    const int menu_height = safemode_corner_menu_rows + 2;
    const point menu_pos( std::max( 0, button_pos.x - menu_width - 1 ),
                          std::max( 0, button_pos.y - menu_height + 1 ) );
    safemode_corner_menu.configure( w_pixel_minimap, menu_pos,
                                    safemode_corner_entries( safe_mode != SAFE_MODE_OFF ),
                                    menu_width );
}

void game::draw_safemode_mouse_controls()
{
    // These controls are screen UI, not map tiles.  The persistent corner button
    // is anchored to the pixel-minimap panel but rendered through helper-owned
    // overlay windows so refreshing it cannot cover the SDL minimap surface.
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ) {
        safemode_corner_button_overlay.close();
        safemode_corner_button.clear();
        safemode_corner_menu.close();
        safemode_corner_tooltip.reset();
        return;
    }

    if( w_pixel_minimap && getmaxx( w_pixel_minimap ) >= safemode_corner_button_width + 3 &&
        getmaxy( w_pixel_minimap ) >= 3 ) {
        const bool enabled = safe_mode != SAFE_MODE_OFF;
        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );
        const inclusive_rectangle<point> button_bounds =
            safemode_corner_button_bounds( w_pixel_minimap );

        safemode_corner_button_overlay.configure( w_pixel_minimap, button_pos,
                safemode_corner_button_width, 1 );
        catacurses::window &button_window = safemode_corner_button_overlay.begin_draw( w_pixel_minimap );
        if( button_window ) {
            ui_action_strip_style button_style;
            const nc_color state_color = enabled ? c_light_green : c_light_red;
            button_style.text = state_color;
            button_style.highlight = state_color;
            button_style.selected = state_color;
            button_style.gap = 0;
            button_style.group_gap = 0;
            safemode_corner_button.configure( button_window, point::zero,
            { ui_action_entry( "!", "SAFE_CORNER_MENU", true,
                               safemode_corner_menu.is_open() ) },
            safemode_corner_button_width, 1, button_style );
            safemode_corner_button.draw( button_window );
            safemode_corner_button_overlay.refresh();
        }

        const std::string tooltip_text = _( "Safe mode" );
        const int tooltip_width = std::min( getmaxx( w_pixel_minimap ),
                                            std::max( 8, utf8_width( tooltip_text ) + 4 ) );
        const point tooltip_pos( std::max( 0, button_pos.x - tooltip_width - 1 ),
                                 std::max( 0, button_pos.y - 2 ) );
        safemode_corner_tooltip.configure( w_pixel_minimap, button_bounds, tooltip_pos,
                                           tooltip_text, std::chrono::milliseconds( 1000 ),
                                           tooltip_width );

        if( safemode_corner_menu.is_open() ) {
            safemode_corner_tooltip.clear_pointer();
            configure_safemode_corner_menu();
            safemode_corner_menu.draw( w_pixel_minimap );
        } else {
            safemode_corner_tooltip.draw( w_pixel_minimap );
        }
    } else {
        safemode_corner_button_overlay.close();
        safemode_corner_button.clear();
        safemode_corner_menu.close();
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
    if( uquit == QUIT_WATCH || !w_pixel_minimap ) {
        safemode_corner_tooltip.clear_pointer();
        return;
    }

    const std::optional<point> parent_pos = ctxt.get_coordinates_text( w_pixel_minimap );
    bool tooltip_changed = false;

    if( action == "TIMEOUT" ) {
        tooltip_changed = safemode_corner_tooltip.tick();
    } else if( parent_pos ) {
        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );
        const point button_local = *parent_pos - button_pos;
        safemode_corner_button.handle_input( "MOUSE_MOVE", button_local );
        if( safemode_corner_menu.is_open() ) {
            safemode_corner_menu.handle_input( "MOUSE_MOVE", parent_pos );
            tooltip_changed = safemode_corner_tooltip.clear_pointer();
        } else {
            tooltip_changed = safemode_corner_tooltip.update_pointer( parent_pos );
        }
    } else if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ) {
        safemode_corner_button.update_hover( std::nullopt );
        safemode_corner_menu.update_hover( std::nullopt );
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
    // p is a stdscr-relative terminal-cell coordinate.  Corner helper geometry is
    // pixel-minimap-relative; the threat alert below remains terminal-relative.
    if( uquit == QUIT_WATCH || TERMX < 12 || TERMY < 2 ) {
        return ACTION_NULL;
    }

    if( w_pixel_minimap && getmaxx( w_pixel_minimap ) >= safemode_corner_button_width + 3 &&
        getmaxy( w_pixel_minimap ) >= 3 ) {
        const point parent_pos( p.x - getbegx( w_pixel_minimap ),
                                p.y - getbegy( w_pixel_minimap ) );
        const inclusive_rectangle<point> trigger_bounds =
            safemode_corner_button_bounds( w_pixel_minimap );

        if( safemode_corner_menu.is_open() ) {
            const ui_action_result menu_result = safemode_corner_menu.handle_input(
                    "SELECT", parent_pos, true, ui_outside_click_policy::passthrough,
                    trigger_bounds );
            if( menu_result.type == ui_action_result_type::activated && menu_result.entry &&
                menu_result.entry->id == "SAFE_MODE_TOGGLE" ) {
                safemode_corner_tooltip.clear_pointer();
                invalidate_main_ui_adaptor();
                return ACTION_TOGGLE_SAFEMODE;
            }
            if( menu_result.type == ui_action_result_type::closed ) {
                invalidate_main_ui_adaptor();
            }
            if( menu_result.consumed() ) {
                return ACTION_CLICK_AND_DRAG;
            }
        }

        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );
        const ui_action_result button_result = safemode_corner_button.handle_input(
                "SELECT", parent_pos - button_pos );
        if( button_result.type == ui_action_result_type::activated ) {
            configure_safemode_corner_menu();
            safemode_corner_tooltip.clear_pointer();
            invalidate_main_ui_adaptor();
            return ACTION_CLICK_AND_DRAG;
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
        // Deliberately return only the native ignore action here.  Its normal
        // SAFE_MODE_STOP branch marks the currently seen monsters ignored and
        // restores SAFE_MODE_ON; it never disables safemode.
        return ACTION_IGNORE_ENEMY;
    }

    // Consume clicks on the alert panel itself so they cannot leak through to map actions.
    if( p.x >= left && p.x < left + width && p.y >= top && p.y < top + 4 ) {
        return ACTION_CLICK_AND_DRAG;
    }
    return ACTION_NULL;
}
'''

replace_once('src/game.cpp', old_safe_block, new_safe_block, 'safemode HUD block')

Path('/tmp/branch_patch_commit_message').write_text(
    'Add helper-driven safemode corner menu\n', encoding='utf-8'
)
