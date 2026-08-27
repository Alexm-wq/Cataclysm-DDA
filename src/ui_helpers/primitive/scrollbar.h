#pragma once
#ifndef CATA_SRC_UI_HELPERS_PRIMITIVE_SCROLLBAR_H
#define CATA_SRC_UI_HELPERS_PRIMITIVE_SCROLLBAR_H

#include <optional>
#include <string>

#include "../../color.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../point.h"
#include "../models/scroll_model.h"

class input_context;

class scrollbar
{
    public:
        scrollbar();
        // relative position of the scrollbar to the window
        scrollbar &offset_x( int offx );
        scrollbar &offset_y( int offy );
        // total number of lines
        scrollbar &content_size( int csize );
        // index of the beginning line
        scrollbar &viewport_pos( int vpos );
        // number of lines shown
        scrollbar &viewport_size( int vsize );
        // window border color
        scrollbar &border_color( nc_color border_c );
        // scrollbar arrow color
        scrollbar &arrow_color( nc_color arrow_c );
        // scrollbar slot color
        scrollbar &slot_color( nc_color slot_c );
        // scrollbar bar color
        scrollbar &bar_color( nc_color bar_c );
        // can viewport_pos go beyond (content_size - viewport_size)?
        scrollbar &scroll_to_last( bool scr2last );
        // Sets up ability for the scrollbar to be dragged with the mouse
        scrollbar &set_draggable( input_context &ctxt );
        // draw the scrollbar to the window
        void apply( const catacurses::window &window, bool draw_unneeded = false );
        // Checks if the user is dragging the scrollbar with the mouse (set_draggable first)
        bool handle_dragging( const std::string &action, const std::optional<point> &coord,
                              int &position );

        /** Copy renderer-independent scroll state into this visual scrollbar. */
        scrollbar &model( const ui_scroll_model &state ) {
            return content_size( state.content_size() )
                   .viewport_pos( state.viewport_pos() )
                   .viewport_size( state.viewport_size() );
        }

        /** Drag directly into a renderer-independent scroll model. */
        bool handle_dragging( const std::string &action, const std::optional<point> &coord,
                              ui_scroll_model &state ) {
            int position = state.viewport_pos();
            const bool handled = handle_dragging( action, coord, position );
            if( handled ) {
                state.set_viewport_pos( position );
            }
            return handled;
        }

    private:
        int offset_x_v, offset_y_v;
        int content_size_v, viewport_pos_v, viewport_size_v;
        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;
        bool scroll_to_last_v;
        bool dragging = false;
        int drag_grab_offset = 0;
        inclusive_rectangle<point> scrollbar_area;
        std::optional<inclusive_rectangle<point>> thumb_area;
};

#endif // CATA_SRC_UI_HELPERS_PRIMITIVE_SCROLLBAR_H
