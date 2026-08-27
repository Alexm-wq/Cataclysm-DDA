#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_DOUBLE_CLICK_TRACKER_H
#define CATA_SRC_UI_HELPERS_MODELS_DOUBLE_CLICK_TRACKER_H

#include <chrono>
#include <optional>

/** Tracks double-clicks by semantic target instead of screen coordinates. */
template<typename T, typename Clock = std::chrono::steady_clock>
class ui_double_click_tracker
{
    public:
        using clock = Clock;
        using time_point = typename clock::time_point;
        using duration = typename clock::duration;

        explicit ui_double_click_tracker(
            const duration interval = std::chrono::milliseconds( 500 ) ) : interval_( interval ) {}

        bool click( const T &target, const time_point now = clock::now() ) {
            if( last_target_ && last_time_ && *last_target_ == target &&
                now >= *last_time_ && now - *last_time_ <= interval_ ) {
                reset();
                return true;
            }
            last_target_ = target;
            last_time_ = now;
            return false;
        }

        void reset() {
            last_target_.reset();
            last_time_.reset();
        }

        const std::optional<T> &last_target() const {
            return last_target_;
        }

        duration interval() const {
            return interval_;
        }

    private:
        duration interval_;
        std::optional<T> last_target_;
        std::optional<time_point> last_time_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_DOUBLE_CLICK_TRACKER_H
