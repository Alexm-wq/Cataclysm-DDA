#pragma once
#ifndef CATA_SRC_UI_HELPERS_OVERLAY_H
#define CATA_SRC_UI_HELPERS_OVERLAY_H

#include <algorithm>

#include "cursesdef.h"
#include "point.h"

/**
 * Lightweight transient curses surface for menus/panels drawn above another UI.
 *
 * The overlay always owns a window no larger than its requested rectangle.  This
 * is important for SDL-backed interfaces: refreshing a full-screen curses parent
 * after the map/tile preview has rendered would paint untouched cells as an opaque
 * black slab.  Callers render their normal UI/SDL preview first, then draw this
 * overlay last.
 *
 * Geometry is expressed relative to a caller-owned parent window.  The backing
 * curses window is recreated lazily when the parent moves/resizes or the requested
 * rectangle changes.
 */
class ui_overlay
{
    public:
        void close() {
            window_ = catacurses::window();
            pos_ = point::zero;
            width_ = 0;
            height_ = 0;
        }

        bool is_open() const {
            return width_ > 0 && height_ > 0;
        }

        void configure( const catacurses::window &parent, point pos, int width, int height ) {
            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            if( parent_width <= 0 || parent_height <= 0 || width <= 0 || height <= 0 ) {
                close();
                return;
            }

            width_ = std::clamp( width, 1, parent_width );
            height_ = std::clamp( height, 1, parent_height );
            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_width - width_ ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height - height_ ) );
            pos_ = pos;
        }

        bool contains( const point &parent_pos ) const {
            return is_open() && parent_pos.x >= pos_.x && parent_pos.x < pos_.x + width_ &&
                   parent_pos.y >= pos_.y && parent_pos.y < pos_.y + height_;
        }

        point pos() const {
            return pos_;
        }

        int width() const {
            return width_;
        }

        int height() const {
            return height_;
        }

        /**
         * Ensure the backing window matches the current parent geometry, erase it,
         * and return it for caller drawing.  The caller should invoke refresh()
         * after drawing its contents.
         */
        catacurses::window &begin_draw( const catacurses::window &parent ) {
            if( !is_open() ) {
                window_ = catacurses::window();
                return window_;
            }

            const point screen_pos( getbegx( parent ) + pos_.x, getbegy( parent ) + pos_.y );
            const bool needs_window = !window_ || getmaxx( window_ ) != width_ ||
                                      getmaxy( window_ ) != height_ ||
                                      getbegx( window_ ) != screen_pos.x ||
                                      getbegy( window_ ) != screen_pos.y;
            if( needs_window ) {
                window_ = catacurses::newwin( height_, width_, screen_pos );
            }
            werase( window_ );
            return window_;
        }

        void refresh() const {
            if( window_ ) {
                wnoutrefresh( window_ );
            }
        }

    private:
        catacurses::window window_;
        point pos_ = point::zero;
        int width_ = 0;
        int height_ = 0;
};

#endif // CATA_SRC_UI_HELPERS_OVERLAY_H
