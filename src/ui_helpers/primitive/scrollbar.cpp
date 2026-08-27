#include "ui_helpers/primitive/scrollbar.h"

#include <algorithm>
#include <cmath>

#include "input_context.h"
#include "output.h"

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
    scrollbar_area = inclusive_rectangle<point>( point( getbegx( window ) + offset_x_v,
                     getbegy( window ) + offset_y_v ), point( getbegx( window ) + offset_x_v,
                             getbegy( window ) + offset_y_v + viewport_size_v ) );
    if( viewport_size_v >= content_size_v || content_size_v <= 0 ) {
        // scrollbar not needed, optionally fill output area with vertical border line
        if( draw_unneeded ) {
            mvwvline( window, point( offset_x_v, offset_y_v ), border_color_v, LINE_XOXO, viewport_size_v );
        }
    } else {
        mvwputch( window, point( offset_x_v, offset_y_v ), arrow_color_v, '^' );
        mvwputch( window, point( offset_x_v, offset_y_v + viewport_size_v - 1 ), arrow_color_v, 'v' );

        int slot_size = viewport_size_v - 2;
        int bar_size = std::max( 2, slot_size * viewport_size_v / content_size_v );
        int scrollable_size = scroll_to_last_v ? content_size_v : content_size_v - viewport_size_v + 1;

        int bar_start;
        if( viewport_pos_v == 0 ) {
            bar_start = 0;
        } else if( scrollable_size > 2 ) {
            bar_start = ( slot_size - 1 - bar_size ) * ( viewport_pos_v - 1 ) / ( scrollable_size - 2 ) + 1;
        } else {
            bar_start = slot_size - bar_size;
        }
        int bar_end = bar_start + bar_size;
        nc_color temp_bar_color = dragging ? c_magenta_magenta : bar_color_v;

        mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v,   LINE_XOXO, bar_start );
        mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), temp_bar_color, LINE_XOXO,
                  bar_end - bar_start );
        mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v,   LINE_XOXO,
                  slot_size - bar_end );
    }
}

bool scrollbar::handle_dragging( const std::string &action, const std::optional<point> &coord,
                                 int &position )
{
    if( ( action != "MOUSE_MOVE" && action != "CLICK_AND_DRAG" ) && dragging ) {
        // Stopped dragging the scrollbar
        dragging = false;

        // We don't want to accidentally select something on mouse-up after dragging the scrollbar, so if
        // there's a mouse-up event, tell the UI that we've handled it
        return action == "SELECT";
    } else  if( action == "CLICK_AND_DRAG" && coord.has_value() &&
                scrollbar_area.contains( coord.value() ) ) {
        // Started dragging the scrollbar
        dragging = true;
        return true;
    } else if( action == "MOUSE_MOVE" && coord.has_value() && dragging ) {
        // Currently dragging the scrollbar.  Clamp cursor position to scrollbar area, then interpolate
        int clamped_cursor_pos = clamp( coord->y - scrollbar_area.p_min.y, 0,
                                        scrollbar_area.p_max.y - scrollbar_area.p_min.y - 1 );
        viewport_pos_v = clamped_cursor_pos * ( content_size_v - viewport_size_v ) /
                         ( scrollbar_area.p_max.y - scrollbar_area.p_min.y - 1 );
        position = viewport_pos_v;
#if !defined(TILES)
        // Tiles builds seem to trigger "SELECT" on mouse button-up (clearing "dragging") but curses does not
        dragging = false;
#endif //TILES
        return true;
    } else {
        // Not doing anything related to the scrollbar
        return false;
    }
}

void multiline_list::activate_entry( const size_t entry_pos, const bool exclusive )
{
    if( entry_pos >= entries.size() ) {
        debugmsg( "Unable to activate entry %d of %d", entry_pos, entries.size() );
        return;
    }

    const bool cur_value = entries[entry_pos].active;

    if( exclusive ) {
        for( multiline_list_entry &entry : entries ) {
            entry.active = false;
        }
    }

    entries[entry_pos].active = exclusive ? true : !cur_value;
}

void multiline_list::add_entry( const multiline_list_entry &entry )
{
    entries.emplace_back( entry );
    if( !has_prefix || entry.prefix.empty() ) {
        entries.back().prefix.clear();
        has_prefix = false;
    }
}

void multiline_list::create_entry_prep()
{
    entries.clear();
    has_prefix = true;
}

void multiline_list::fold_entries()
{
    int available_width = getmaxx( w ) - 2; // Border/scrollbar allowance
    entry_sizes.clear();
    total_length = 0;

    std::vector<std::string> folded;
    for( multiline_list_entry &entry : entries ) {
        entry.folded_text.clear();
        if( has_prefix ) {
            // Do a prefixed list (e.g. starting with a hotkey )
            const int prefix_width = utf8_width( entry.prefix, true );
            const int fold_width = available_width - prefix_width;
            folded = foldstring( entry.entry_text, fold_width );
            for( size_t j = 0; j < folded.size(); ++j ) {
                if( j == 0 ) {
                    entry.folded_text.emplace_back( entry.prefix + folded[j] );
                } else {
                    entry.folded_text.emplace_back( std::string( prefix_width, ' ' ).append( folded[j] ) );
                }
            }
        } else {
            folded = foldstring( entry.entry_text, available_width );
            for( const std::string &line : folded ) {
                entry.folded_text.emplace_back( line );
            }
        }
        entry_sizes.emplace_back( static_cast<int>( folded.size() ) );
        total_length += folded.size();
    }
    if( !entries.empty() ) {
        // Reset entry position at end, because the resulting offset depends on entry sizes
        set_entry_pos( 0, false );
    }
}

int multiline_list::get_entry_from_offset()
{
    return get_entry_from_offset( offset_position );
}

int multiline_list::get_entry_from_offset( const int offset )
{
    int offset_for_entry = 0;
    for( int i = 0; i < static_cast<int>( entry_sizes.size() ); ++i ) {
        /* If the last entry we scroll past before the end of the list is multiple lines,
         * we need to be able to jump past it.  So, if it's a single-line entry, we can
         * return it.  Otherwise, skip past it and return the next one
         */
        if( offset_for_entry + 1 > offset ) {
            return i;
        }
        offset_for_entry += entry_sizes[i];
        if( offset_for_entry > offset ) {
            return i + 1;
        }
    }
    return static_cast<int>( entry_sizes.size() ) - 1;
}
