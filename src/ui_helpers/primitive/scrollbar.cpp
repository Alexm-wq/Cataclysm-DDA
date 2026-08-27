#include "scrollbar.h"

#include <algorithm>
#include <cmath>

#include "../../cata_utility.h"
#include "../../input_context.h"
#include "../../output.h"

scrollbar::scrollbar()
    : offset_x_v( 0 ), offset_y_v( 0 ), content_size_v( 0 ),
      viewport_pos_v( 0 ), viewport_size_v( 0 ),
      border_color_v( BORDER_COLOR ), arrow_color_v( c_light_green ),
      slot_color_v( c_white ), bar_color_v( c_cyan_cyan ), scroll_to_last_v( false )
{
}

scrollbar &scrollbar::offset_x( int offx )
{
    offset_x_v = offx;
    return *this;
}

scrollbar &scrollbar::offset_y( int offy )
{
    offset_y_v = offy;
    return *this;
}

scrollbar &scrollbar::content_size( int csize )
{
    content_size_v = csize;
    return *this;
}

scrollbar &scrollbar::viewport_pos( int vpos )
{
    viewport_pos_v = vpos;
    return *this;
}

scrollbar &scrollbar::viewport_size( int vsize )
{
    viewport_size_v = vsize;
    return *this;
}

scrollbar &scrollbar::border_color( nc_color border_c )
{
    border_color_v = border_c;
    return *this;
}

scrollbar &scrollbar::arrow_color( nc_color arrow_c )
{
    arrow_color_v = arrow_c;
    return *this;
}

scrollbar &scrollbar::slot_color( nc_color slot_c )
{
    slot_color_v = slot_c;
    return *this;
}

scrollbar &scrollbar::bar_color( nc_color bar_c )
{
    bar_color_v = bar_c;
    return *this;
}

scrollbar &scrollbar::scroll_to_last( bool scr2last )
{
    scroll_to_last_v = scr2last;
    return *this;
}

scrollbar &scrollbar::set_draggable( input_context &ctxt )
{
    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "CLICK_AND_DRAG" );
    ctxt.register_action( "SELECT" ); // Not directly used yet, but required for mouse-up reaction
    return *this;
}

void scrollbar::apply( const catacurses::window &window, const bool draw_unneeded )
{
    const int absolute_x = getbegx( window ) + offset_x_v;
    const int absolute_y = getbegy( window ) + offset_y_v;
    const int drawn_height = std::max( 1, viewport_size_v );
    scrollbar_area = inclusive_rectangle<point>( point( absolute_x, absolute_y ),
                     point( absolute_x, absolute_y + drawn_height - 1 ) );
    thumb_area.reset();

    if( viewport_size_v >= content_size_v || content_size_v <= 0 || viewport_size_v < 3 ) {
        dragging = false;
        if( draw_unneeded && viewport_size_v > 0 ) {
            mvwvline( window, point( offset_x_v, offset_y_v ), border_color_v, LINE_XOXO,
                      viewport_size_v );
        }
        return;
    }

    mvwputch( window, point( offset_x_v, offset_y_v ), arrow_color_v, '^' );
    mvwputch( window, point( offset_x_v, offset_y_v + viewport_size_v - 1 ), arrow_color_v, 'v' );

    const int slot_size = viewport_size_v - 2;
    const int bar_size = std::clamp(
                             static_cast<int>( std::lround( static_cast<double>( slot_size ) *
                                     static_cast<double>( viewport_size_v ) /
                                     static_cast<double>( content_size_v ) ) ), 1, slot_size );
    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :
                             std::max( 0, content_size_v - viewport_size_v );
    const int travel = std::max( 0, slot_size - bar_size );
    const int clamped_position = clamp( viewport_pos_v, 0, max_position );
    // viewport_pos_v is an entry index.  Map that exact entry position across
    // the available thumb travel; rendering is quantized only by terminal rows.
    const int bar_start = max_position > 0 && travel > 0 ?
                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *
                                  static_cast<double>( travel ) /
                                  static_cast<double>( max_position ) ) ) : 0;
    const int bar_end = bar_start + bar_size;
    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),
                 point( absolute_x, absolute_y + bar_end ) );

    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;
    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );
    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,
              bar_size );
    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,
              slot_size - bar_end );
}

bool scrollbar::handle_dragging( const std::string &action, const std::optional<point> &coord,
                                 int &position )
{
    if( !thumb_area ) {
        dragging = false;
        return false;
    }

    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :
                             std::max( 0, content_size_v - viewport_size_v );
    const int track_min = scrollbar_area.p_min.y + 1;
    const int track_max = scrollbar_area.p_max.y - 1;
    const int thumb_size = thumb_area->p_max.y - thumb_area->p_min.y + 1;
    const int travel = std::max( 0, track_max - track_min + 1 - thumb_size );

    const auto publish = [&]( const int requested ) {
        viewport_pos_v = clamp( requested, 0, max_position );
        position = viewport_pos_v;
    };
    const auto drag_to = [&]( const int cursor_y ) {
        const int thumb_start = clamp( cursor_y - drag_grab_offset, track_min,
                                      track_min + travel );
        const int thumb_offset = thumb_start - track_min;
        const int requested = travel > 0 && max_position > 0 ?
                              static_cast<int>( std::lround( static_cast<double>( thumb_offset ) *
                                      static_cast<double>( max_position ) /
                                      static_cast<double>( travel ) ) ) : 0;
        publish( requested );
    };

    if( dragging && action == "SELECT" ) {
        dragging = false;
        drag_grab_offset = 0;
        return true;
    }
    if( dragging ) {
        if( ( action == "MOUSE_MOVE" || action == "CLICK_AND_DRAG" ) && coord ) {
            drag_to( coord->y );
            return true;
        }
        if( action != "MOUSE_MOVE" && action != "CLICK_AND_DRAG" ) {
            dragging = false;
            drag_grab_offset = 0;
        }
        return false;
    }
    if( action == "CLICK_AND_DRAG" && coord && thumb_area->contains( *coord ) ) {
        dragging = true;
        drag_grab_offset = clamp( coord->y - thumb_area->p_min.y, 0, thumb_size - 1 );
        return true;
    }
    if( action == "SELECT" && coord && scrollbar_area.contains( *coord ) ) {
        if( coord->y == scrollbar_area.p_min.y ) {
            publish( position - 1 );
        } else if( coord->y == scrollbar_area.p_max.y ) {
            publish( position + 1 );
        } else if( coord->y < thumb_area->p_min.y ) {
            publish( position - std::max( 1, viewport_size_v ) );
        } else if( coord->y > thumb_area->p_max.y ) {
            publish( position + std::max( 1, viewport_size_v ) );
        }
        return true;
    }
    return false;
}
