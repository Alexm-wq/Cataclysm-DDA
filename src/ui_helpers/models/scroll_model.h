#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_SCROLL_MODEL_H
#define CATA_SRC_UI_HELPERS_MODELS_SCROLL_MODEL_H

#include <algorithm>

/**
 * Renderer-independent viewport state for scrollable UI controls.
 *
 * Selection is intentionally not part of this model.  Callers explicitly request
 * ensure_visible() when selection/focus should move the viewport.  This keeps free
 * mouse-wheel scrolling independent from the current selected row.
 */
class ui_scroll_model
{
    public:
        ui_scroll_model() = default;
        ui_scroll_model( int content_size, int viewport_size, int viewport_pos = 0 ) {
            set_content_size( content_size );
            set_viewport_size( viewport_size );
            set_viewport_pos( viewport_pos );
        }

        int content_size() const {
            return content_size_;
        }
        int viewport_size() const {
            return viewport_size_;
        }
        int viewport_pos() const {
            return viewport_pos_;
        }
        int max_viewport_pos() const {
            return std::max( 0, content_size_ - viewport_size_ );
        }
        bool can_scroll() const {
            return content_size_ > viewport_size_;
        }

        ui_scroll_model &set_content_size( int value ) {
            content_size_ = std::max( 0, value );
            clamp();
            return *this;
        }
        ui_scroll_model &set_viewport_size( int value ) {
            viewport_size_ = std::max( 0, value );
            clamp();
            return *this;
        }
        ui_scroll_model &set_viewport_pos( int value ) {
            viewport_pos_ = value;
            clamp();
            return *this;
        }
        ui_scroll_model &scroll_by( int delta ) {
            return set_viewport_pos( viewport_pos_ + delta );
        }
        ui_scroll_model &page_by( int pages ) {
            return scroll_by( pages * std::max( 1, viewport_size_ ) );
        }
        ui_scroll_model &scroll_to_start() {
            viewport_pos_ = 0;
            return *this;
        }
        ui_scroll_model &scroll_to_end() {
            viewport_pos_ = max_viewport_pos();
            return *this;
        }
        ui_scroll_model &ensure_visible( int index ) {
            if( index < 0 || content_size_ <= 0 || viewport_size_ <= 0 ) {
                return *this;
            }
            if( index < viewport_pos_ ) {
                viewport_pos_ = index;
            } else if( index >= viewport_pos_ + viewport_size_ ) {
                viewport_pos_ = index - viewport_size_ + 1;
            }
            clamp();
            return *this;
        }

    private:
        void clamp() {
            viewport_pos_ = std::clamp( viewport_pos_, 0, max_viewport_pos() );
        }

        int content_size_ = 0;
        int viewport_size_ = 0;
        int viewport_pos_ = 0;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_SCROLL_MODEL_H
