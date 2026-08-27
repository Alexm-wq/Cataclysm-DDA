#pragma once
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
