#include "clipped_text.h"

#include <algorithm>
#include <chrono>
#include <optional>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cursesdef.h"
#include "../../input_enums.h"
#include "../../output.h"
#include "../../ui_manager.h"
#include "../models/text_overflow.h"
#include "tooltip.h"
#if defined(TILES)
#include "../../sdltiles.h"
#endif

namespace
{
struct clipped_text_state {
    const void *owner = nullptr;
    rectangle<point> bounds{ point::zero, point::zero };
    bool recording = false;
    ui_text_overflow_model targets;
    std::optional<point> pointer;
    std::optional<ui_overflow_text> active;
    std::optional<point> tooltip_pos;
    catacurses::window parent;
    ui_tooltip tooltip;
};

clipped_text_state &state()
{
    static clipped_text_state value;
    return value;
}

point cell_size()
{
#if defined(TILES)
    return get_window_dimensions( point::zero, point( 1, 1 ) ).scaled_font_size;
#else
    return point( 1, 1 );
#endif
}

inclusive_rectangle<point> window_bounds( const catacurses::window &window )
{
#if defined(TILES)
    const window_dimensions dim = get_window_dimensions( window );
    return { dim.window_pos_pixel, dim.window_pos_pixel + dim.window_size_pixel - point( 1, 1 ) };
#else
    const point origin( getbegx( window ), getbegy( window ) );
    return { origin, origin + point( getmaxx( window ) - 1, getmaxy( window ) - 1 ) };
#endif
}

void invalidate_tooltip()
{
    const catacurses::window &window = state().tooltip.window();
    if( window ) {
        const auto bounds = window_bounds( window );
        ui_manager::invalidate( { bounds.p_min, bounds.p_max + point( 1, 1 ) }, false );
    }
}

bool update_target()
{
    clipped_text_state &s = state();
    const auto next = s.pointer ? s.targets.hit( *s.pointer ) : std::nullopt;
    std::optional<point> next_pos;
    if( next && s.parent ) {
        const point cell = cell_size();
        // Anchor beside the mouse, in the tooltip parent's text coordinates.
        // The shared overlay clamps the popup when it reaches a screen edge.
        next_pos = point( s.pointer->x / cell.x - getbegx( s.parent ) + 1,
                          s.pointer->y / cell.y - getbegy( s.parent ) + 1 );
    }
    const bool changed = s.active.has_value() != next.has_value() ||
                         s.tooltip_pos != next_pos ||
                         ( s.active && next && ( s.active->text != next->text ||
                                                 s.active->bounds.p_min != next->bounds.p_min ||
                                                 s.active->bounds.p_max != next->bounds.p_max ) );
    if( changed ) {
        invalidate_tooltip();
    }
    s.active = next;
    s.tooltip_pos = next_pos;
    if( !next || !next_pos ) {
        s.tooltip.reset();
        return changed;
    }
    ui_tooltip_style style;
    style.border = c_light_gray;
    // Immediate expansion is non-interactive; shortcut-button tooltips retain their dwell delay.
    s.tooltip.configure( s.parent, next->bounds, *next_pos, next->text,
                         std::chrono::milliseconds::zero(), 0, style );
    s.tooltip.update_pointer( s.pointer );
    return changed;
}
} // namespace

void ui_clipped_text::set_context( const void *owner, const rectangle<point> &bounds )
{
    clipped_text_state &s = state();
    if( s.owner == owner && s.bounds.p_min == bounds.p_min && s.bounds.p_max == bounds.p_max ) {
        return;
    }
    invalidate_tooltip();
    s = clipped_text_state();
    s.owner = owner;
    s.bounds = bounds;
    const point cell = cell_size();
    const point origin( std::max( 0, bounds.p_min.x ) / cell.x,
                        std::max( 0, bounds.p_min.y ) / cell.y );
    const point end( std::min( TERMX, bounds.p_max.x / cell.x ),
                     std::min( TERMY, bounds.p_max.y / cell.y ) );
    if( end.x - origin.x >= 3 && end.y - origin.y >= 3 ) {
        // Geometry only: this parent is never refreshed or painted over the owning UI.
        s.parent = catacurses::newwin( end.y - origin.y, end.x - origin.x, origin );
    }
}

void ui_clipped_text::forget_context( const void *owner )
{
    if( state().owner == owner ) {
        invalidate_tooltip();
        state() = clipped_text_state();
    }
}

void ui_clipped_text::begin_frame()
{
    state().targets.clear();
    state().recording = true;
}

void ui_clipped_text::end_frame()
{
    state().recording = false;
}

void ui_clipped_text::record( const catacurses::window &window, const point &pos,
                             const int width, const nc_color &base_color, const std::string &text )
{
    if( !state().recording || !window || pos.x < 0 || pos.y < 0 || pos.y >= getmaxy( window ) ) {
        return;
    }
    const int available = std::min( width, getmaxx( window ) - pos.x );
    if( available <= 0 ) {
        return;
    }
    const std::string plain = remove_color_tags( text );
    const int text_width = utf8_width( plain );
    const int visible_width = std::min( available, text_width );
    if( visible_width <= 0 ) {
        return;
    }
#if defined(TILES)
    const window_dimensions dim = get_window_dimensions( window );
    const point cell = dim.scaled_font_size;
    const point start = dim.window_pos_pixel + point( pos.x * cell.x, pos.y * cell.y );
#else
    const point cell( 1, 1 );
    const point start( getbegx( window ) + pos.x, getbegy( window ) + pos.y );
#endif
    state().targets.record( window.get<void>(),
                            { start, start + point( visible_width * cell.x - 1, cell.y - 1 ) },
                            colorize( text, base_color ), text_width, available );
}

void ui_clipped_text::erase_window( const catacurses::window &window )
{
    if( state().recording && window ) {
        state().targets.erase_window( window.get<void>() );
    }
}

void ui_clipped_text::present_window( const catacurses::window &window )
{
    if( state().recording && window && getmaxx( window ) > 0 && getmaxy( window ) > 0 ) {
        state().targets.present( window.get<void>(), window_bounds( window ) );
    }
}

bool ui_clipped_text::handle_input( const input_event &event )
{
    if( event.type == input_event_t::mouse &&
        event.get_first_input() == static_cast<int>( MouseInput::Move ) ) {
        state().pointer = event.mouse_pos;
    } else if( event.type != input_event_t::timeout && event.type != input_event_t::error ) {
        state().pointer.reset();
    }
    return update_target();
}

void ui_clipped_text::draw()
{
    update_target();
    if( state().parent ) {
        state().tooltip.draw( state().parent );
    }
}
