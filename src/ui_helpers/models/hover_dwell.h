#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_HOVER_DWELL_H
#define CATA_SRC_UI_HELPERS_MODELS_HOVER_DWELL_H

#include <algorithm>
#include <chrono>
#include <optional>
#include <string>

#include "../../cuboid_rectangle.h"
#include "../../point.h"

/** Renderer-independent delayed hover. Bounds and pointer positions must use
 * the same coordinate space (pixels or text cells). Repeated configuration of
 * the same target preserves dwell; changing its identity or geometry resets it.
 */
class ui_hover_dwell
{
    public:
        using clock = std::chrono::steady_clock;

        void configure( const inclusive_rectangle<point> &bounds,
                        const std::chrono::milliseconds delay = std::chrono::milliseconds( 1000 ),
                        const std::string &identity = std::string() ) {
            const auto next_delay = std::max( std::chrono::milliseconds::zero(), delay );
            if( !bounds_ || bounds_->p_min != bounds.p_min || bounds_->p_max != bounds.p_max ||
                delay_ != next_delay || identity_ != identity ) {
                clear_pointer();
            }
            bounds_ = bounds;
            delay_ = next_delay;
            identity_ = identity;
        }

        bool update_pointer( const std::optional<point> &pos,
                             const clock::time_point now = clock::now() ) {
            if( !pos || !bounds_ || !bounds_->contains( *pos ) ) {
                return clear_pointer();
            }
            if( !last_pointer_ || *last_pointer_ != *pos ) {
                const bool was_visible = visible_;
                last_pointer_ = *pos;
                hover_started_ = now;
                visible_ = delay_ == std::chrono::milliseconds::zero();
                return was_visible != visible_;
            }
            return tick( now );
        }

        /** Idle timeouts advance the delay without needing another mouse move. */
        bool tick( const clock::time_point now = clock::now() ) {
            const bool was_visible = visible_;
            if( !visible_ && hover_started_ && now - *hover_started_ >= delay_ ) {
                visible_ = true;
            }
            return was_visible != visible_;
        }

        bool clear_pointer() {
            const bool was_visible = visible_;
            last_pointer_.reset();
            hover_started_.reset();
            visible_ = false;
            return was_visible;
        }

        void reset() {
            clear_pointer();
            bounds_.reset();
            identity_.clear();
        }

        bool visible() const {
            return visible_;
        }

    private:
        std::optional<inclusive_rectangle<point>> bounds_;
        std::optional<point> last_pointer_;
        std::optional<clock::time_point> hover_started_;
        std::chrono::milliseconds delay_ = std::chrono::milliseconds( 1000 );
        std::string identity_;
        bool visible_ = false;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_HOVER_DWELL_H
