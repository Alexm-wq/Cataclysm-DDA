#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_SCROLL_VIEW_H
#define CATA_SRC_UI_HELPERS_CONTROLS_SCROLL_VIEW_H

#include <algorithm>
#include <optional>
#include <string>

#include "../../cursesdef.h"
#include "../../input_context.h"
#include "../models/scroll_model.h"
#include "../primitive/scrollbar.h"

/** Independent viewport for caller-rendered text and inline controls. Owns
 * wheel routing, scrollbar capture, keyboard paging and content clipping. */
class ui_scroll_view
{
    public:
        ui_scroll_model &model() {
            return scroll_;
        }
        bool has_capture() const {
            return scrollbar_.has_capture();
        }
        void hide() {
            width_ = height_ = 0;
            scrollbar_ = scrollbar();
        }
        void configure( point origin, int width, int height, int content_size ) {
            origin_ = origin;
            width_ = std::max( 0, width );
            height_ = std::max( 0, height );
            scroll_.set_content_size( content_size ).set_viewport_size( height_ );
        }
        bool contains( const std::optional<point> &pos ) const {
            return pos && pos->x >= origin_.x && pos->x < origin_.x + width_ &&
                   pos->y >= origin_.y && pos->y < origin_.y + height_;
        }
        std::optional<point> position( int line ) const {
            return width_ > 1 && scroll_.is_visible( line ) ?
                   std::optional<point>( origin_ + point( 0, line - scroll_.viewport_pos() ) ) : std::nullopt;
        }
        void draw_scrollbar( const catacurses::window &window ) {
            if( width_ > 1 && height_ > 0 ) {
                scrollbar_.offset_x( origin_.x + width_ - 1 ).offset_y( origin_.y )
                          .model( scroll_ ).apply( window );
            }
        }
        bool handle_input( const std::string &action, const input_context &context,
                           const std::optional<point> &pos, bool keyboard = false ) {
            if( width_ <= 1 || height_ <= 0 ) {
                return false;
            }
            if( scrollbar_.handle_input( action, context, scroll_ ) ) {
                return true;
            }
            if( ( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) && contains( pos ) ) {
                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );
                return true;
            }
            if( !keyboard ) {
                return false;
            }
            if( action == "UP" || action == "DOWN" ) {
                scroll_.scroll_by( action == "UP" ? -1 : 1 );
            } else if( action == "PAGE_UP" || action == "PAGE_DOWN" ) {
                scroll_.page_by( action == "PAGE_UP" ? -1 : 1 );
            } else if( action == "HOME" ) {
                scroll_.scroll_to_start();
            } else if( action == "END" ) {
                scroll_.scroll_to_end();
            } else {
                return false;
            }
            return true;
        }

    private:
        ui_scroll_model scroll_;
        scrollbar scrollbar_;
        point origin_ = point::zero;
        int width_ = 0;
        int height_ = 0;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_SCROLL_VIEW_H
