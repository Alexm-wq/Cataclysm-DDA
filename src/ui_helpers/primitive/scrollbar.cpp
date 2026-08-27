#include "scrollbar.h"

#include <algorithm>
#include <cmath>

#include "../../cata_utility.h"
#include "../../debug.h"
#include "../../input_context.h"
#include "../../output.h"
#if defined(TILES)
#include "../../cursesport.h"
#include "../../sdltiles.h"
#endif

scrollbar::scrollbar()
    : offset_x_v( 0 ), offset_y_v( 0 ), content_size_v( 0 ),
      viewport_pos_v( 0 ), viewport_size_v( 0 ), drawn_height_v( 0 ),
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

scrollbar &scrollbar::height( int rows )
{
    drawn_height_v = std::max( 0, rows );
    return *this;
}

scrollbar &scrollbar::debug_name( std::string name )
{
    debug_name_v = std::move( name );
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
    const int drawn_height = std::max( 1, drawn_height_v > 0 ? drawn_height_v : viewport_size_v );
    scrollbar_area = inclusive_rectangle<point>( point( absolute_x, absolute_y ),
                     point( absolute_x, absolute_y + drawn_height - 1 ) );
    thumb_area.reset();

#if defined(TILES)
    cata_cursesport::WINDOW *const raw_window = window.get<cata_cursesport::WINDOW>();
    const auto overlay_for_this = [&]() {
        return std::find_if( raw_window->pixel_scrollbars.begin(), raw_window->pixel_scrollbars.end(),
        [&]( const cata_cursesport::pixel_scrollbar_overlay & overlay ) {
            return overlay.owner == this;
        } );
    };
    const auto clear_pixel_overlay = [&]() {
        const auto found = overlay_for_this();
        if( found != raw_window->pixel_scrollbars.end() ) {
            raw_window->pixel_scrollbars.erase( found );
            raw_window->draw = true;
        }
        pixel_thumb_area.reset();
    };
#endif

    if( viewport_size_v >= content_size_v || content_size_v <= 0 || drawn_height < 3 ) {
        dragging = false;
#if defined(TILES)
        clear_pixel_overlay();
#endif
        if( draw_unneeded && drawn_height > 0 ) {
            mvwvline( window, point( offset_x_v, offset_y_v ), border_color_v, LINE_XOXO,
                      drawn_height );
        }
        return;
    }

    mvwputch( window, point( offset_x_v, offset_y_v ), arrow_color_v, '^' );
    mvwputch( window, point( offset_x_v, offset_y_v + drawn_height - 1 ), arrow_color_v, 'v' );

    const int slot_size = drawn_height - 2;
    const int bar_size = std::clamp(
                             static_cast<int>( std::lround( static_cast<double>( slot_size ) *
                                     static_cast<double>( viewport_size_v ) /
                                     static_cast<double>( content_size_v ) ) ), 1, slot_size );
    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :
                             std::max( 0, content_size_v - viewport_size_v );
    const int travel = std::max( 0, slot_size - bar_size );
    const int clamped_position = clamp( viewport_pos_v, 0, max_position );
    const int bar_start = max_position > 0 && travel > 0 ?
                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *
                                  static_cast<double>( travel ) /
                                  static_cast<double>( max_position ) ) ) : 0;
    const int bar_end = bar_start + bar_size;
    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),
                 point( absolute_x, absolute_y + bar_end ) );

#if defined(TILES)
    // SDL can represent positions between terminal rows.  Keep text arrows and a
    // neutral cell track for compatibility, then composite the thumb in pixels.
    const window_dimensions input_dim = get_window_dimensions( point( absolute_x, absolute_y ),
                                        point( 1, drawn_height ) );
    const int input_cell_width = std::max( 1, input_dim.scaled_font_size.x );
    const int input_cell_height = std::max( 1, input_dim.scaled_font_size.y );
    const int input_track_height = slot_size * input_cell_height;
    const int input_minimum_thumb = std::min( input_track_height, std::max( 4, input_cell_height / 3 ) );
    const int input_bar_size = std::clamp(
                                   static_cast<int>( std::lround( static_cast<double>( input_track_height ) *
                                           static_cast<double>( viewport_size_v ) /
                                           static_cast<double>( content_size_v ) ) ),
                                   input_minimum_thumb, input_track_height );
    const int input_travel = std::max( 0, input_track_height - input_bar_size );
    const int input_bar_start = max_position > 0 && input_travel > 0 ?
                                static_cast<int>( std::lround( static_cast<double>( clamped_position ) *
                                        static_cast<double>( input_travel ) /
                                        static_cast<double>( max_position ) ) ) : 0;
    const int input_x_min = input_dim.window_pos_pixel.x;
    const int input_y_min = input_dim.window_pos_pixel.y;
    const int input_track_top = input_y_min + input_cell_height;
    pixel_scrollbar_area = inclusive_rectangle<point>(
                               point( input_x_min, input_y_min ),
                               point( input_x_min + input_cell_width - 1,
                                      input_y_min + drawn_height * input_cell_height - 1 ) );
    pixel_track_area = inclusive_rectangle<point>(
                           point( input_x_min, input_track_top ),
                           point( input_x_min + input_cell_width - 1,
                                  input_track_top + input_track_height - 1 ) );
    pixel_thumb_area = inclusive_rectangle<point>(
                           point( input_x_min, input_track_top + input_bar_start ),
                           point( input_x_min + input_cell_width - 1,
                                  input_track_top + input_bar_start + input_bar_size - 1 ) );

    const int pixel_track_height = slot_size * fontheight;
    const int minimum_thumb = std::min( pixel_track_height, std::max( 4, fontheight / 3 ) );
    const int pixel_bar_size = std::clamp(
                                   static_cast<int>( std::lround( static_cast<double>( pixel_track_height ) *
                                           static_cast<double>( viewport_size_v ) /
                                           static_cast<double>( content_size_v ) ) ),
                                   minimum_thumb, pixel_track_height );
    const int pixel_travel = std::max( 0, pixel_track_height - pixel_bar_size );
    const int pixel_bar_start = max_position > 0 && pixel_travel > 0 ?
                                static_cast<int>( std::lround( static_cast<double>( clamped_position ) *
                                        static_cast<double>( pixel_travel ) /
                                        static_cast<double>( max_position ) ) ) : 0;

    cata_cursesport::pixel_scrollbar_overlay overlay;
    overlay.owner = this;
    overlay.x_cell = offset_x_v;
    overlay.track_top_px = ( offset_y_v + 1 ) * fontheight;
    overlay.track_height_px = pixel_track_height;
    overlay.thumb_top_px = overlay.track_top_px + pixel_bar_start;
    overlay.thumb_height_px = pixel_bar_size;
    overlay.dragging = dragging;
    const auto found = overlay_for_this();
    if( found == raw_window->pixel_scrollbars.end() ) {
        raw_window->pixel_scrollbars.push_back( overlay );
    } else {
        *found = overlay;
    }
    raw_window->draw = true;
    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, slot_size );
#else
    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;
    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );
    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,
              bar_size );
    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,
              slot_size - bar_end );
#endif
}

#if defined(TILES)
bool scrollbar::handle_pixel_dragging( const std::string &action, const std::optional<point> &coord,
                                       int &position )
{
    if( !pixel_thumb_area ) {
        dragging = false;
        return false;
    }

    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :
                             std::max( 0, content_size_v - viewport_size_v );
    const int track_min = pixel_track_area.p_min.y;
    const int track_max = pixel_track_area.p_max.y;
    const int thumb_size = pixel_thumb_area->p_max.y - pixel_thumb_area->p_min.y + 1;
    const int travel = std::max( 0, track_max - track_min + 1 - thumb_size );

    const auto publish = [&]( const int requested ) {
        viewport_pos_v = clamp( requested, 0, max_position );
        position = viewport_pos_v;
    };
    const auto drag_to = [&]( const int cursor_y ) {
        const int thumb_start = clamp( cursor_y - pixel_drag_grab_offset, track_min,
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
        pixel_drag_grab_offset = 0;
        return true;
    }
    if( dragging ) {
        if( ( action == "MOUSE_MOVE" || action == "CLICK_AND_DRAG" ) && coord ) {
            drag_to( coord->y );
            return true;
        }
        if( action != "MOUSE_MOVE" && action != "CLICK_AND_DRAG" ) {
            dragging = false;
            pixel_drag_grab_offset = 0;
        }
        return false;
    }
    if( action == "CLICK_AND_DRAG" && coord && pixel_thumb_area->contains( *coord ) ) {
        dragging = true;
        pixel_drag_grab_offset = clamp( coord->y - pixel_thumb_area->p_min.y, 0, thumb_size - 1 );
        return true;
    }
    if( action == "SELECT" && coord && pixel_scrollbar_area.contains( *coord ) ) {
        if( coord->y < track_min ) {
            publish( position - 1 );
        } else if( coord->y > track_max ) {
            publish( position + 1 );
        } else if( coord->y < pixel_thumb_area->p_min.y ) {
            publish( position - std::max( 1, viewport_size_v ) );
        } else if( coord->y > pixel_thumb_area->p_max.y ) {
            publish( position + std::max( 1, viewport_size_v ) );
        }
        return true;
    }
    return false;
}
#endif

bool scrollbar::handle_input( const std::string &action, const input_context &ctxt,
                              ui_scroll_model &state )
{
    const int viewport_before = state.viewport_pos();
    int position = viewport_before;
    const std::optional<point> text_coord = ctxt.get_coordinates_text( catacurses::stdscr );
    const bool owns_pointer = text_coord && scrollbar_area.contains( *text_coord );
    const bool dragging_before = dragging;
    const bool trace_event = action == "SELECT" || action == "CLICK_AND_DRAG" ||
                             ( dragging && action == "MOUSE_MOVE" );
#if defined(TILES)
    const std::optional<point> pixel_coord = ctxt.get_coordinates_pixel();
#endif

    if( trace_event ) {
        DebugLog( D_INFO, D_MAIN ) << "[UI_SCROLLBAR] input name="
                                  << ( debug_name_v.empty() ? "unnamed" : debug_name_v )
                                  << " action=" << action
                                  << " viewport=" << viewport_before
                                  << " content=" << content_size_v
                                  << " visible=" << viewport_size_v
                                  << " drawn_height=" << drawn_height_v
                                  << " dragging=" << dragging_before
                                  << " owns_cell=" << owns_pointer
                                  << " cell="
                                  << ( text_coord ? string_format( "(%d,%d)", text_coord->x, text_coord->y ) : "none" )
                                  << " cell_area=(" << scrollbar_area.p_min.x << "," << scrollbar_area.p_min.y
                                  << ")-(" << scrollbar_area.p_max.x << "," << scrollbar_area.p_max.y << ")"
                                  << " cell_thumb="
                                  << ( thumb_area ? string_format( "(%d,%d)-(%d,%d)", thumb_area->p_min.x,
                                          thumb_area->p_min.y, thumb_area->p_max.x, thumb_area->p_max.y ) : "none" );
#if defined(TILES)
        DebugLog( D_INFO, D_MAIN ) << "[UI_SCROLLBAR] pixel name="
                                  << ( debug_name_v.empty() ? "unnamed" : debug_name_v )
                                  << " action=" << action
                                  << " pixel="
                                  << ( pixel_coord ? string_format( "(%d,%d)", pixel_coord->x, pixel_coord->y ) : "none" )
                                  << " pixel_area=(" << pixel_scrollbar_area.p_min.x << ","
                                  << pixel_scrollbar_area.p_min.y << ")-(" << pixel_scrollbar_area.p_max.x << ","
                                  << pixel_scrollbar_area.p_max.y << ")"
                                  << " pixel_track=(" << pixel_track_area.p_min.x << ","
                                  << pixel_track_area.p_min.y << ")-(" << pixel_track_area.p_max.x << ","
                                  << pixel_track_area.p_max.y << ")"
                                  << " pixel_thumb="
                                  << ( pixel_thumb_area ? string_format( "(%d,%d)-(%d,%d)",
                                          pixel_thumb_area->p_min.x, pixel_thumb_area->p_min.y,
                                          pixel_thumb_area->p_max.x, pixel_thumb_area->p_max.y ) : "none" );
#endif
    }

    bool handled = false;
#if defined(TILES)
    if( pixel_thumb_area ) {
        // Pixel coordinates refine vertical position only after the normal cell
        // hitbox has established ownership. This prevents scaling/window-origin
        // discrepancies from turning an ordinary list click into a scrollbar jump.
        if( dragging || owns_pointer ) {
            handled = handle_pixel_dragging( action, pixel_coord, position );
        }
    } else
#endif
    if( dragging || owns_pointer ) {
        handled = handle_dragging( action, text_coord, position );
    }

    if( handled ) {
        state.set_viewport_pos( position );
    }
    if( trace_event || ( handled && state.viewport_pos() != viewport_before ) ) {
        DebugLog( D_INFO, D_MAIN ) << "[UI_SCROLLBAR] result name="
                                  << ( debug_name_v.empty() ? "unnamed" : debug_name_v )
                                  << " action=" << action
                                  << " handled=" << handled
                                  << " dragging=" << dragging_before << "->" << dragging
                                  << " viewport=" << viewport_before << "->" << state.viewport_pos();
    }
    return handled;
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
