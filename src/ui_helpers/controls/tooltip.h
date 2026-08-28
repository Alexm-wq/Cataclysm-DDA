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
#include "../models/hover_dwell.h"
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
 * The caller owns placement and text. Target bounds and update_pointer() must
 * share a coordinate space (pixels or parent text cells); placement is always
 * in parent text cells. This helper owns dwell timing, pointer-motion reset,
 * transient overlay rendering and visibility.
 */
class ui_tooltip
{
    public:
        using clock = ui_hover_dwell::clock;

        void configure( const catacurses::window &parent,
                        const inclusive_rectangle<point> &target_bounds,
                        point pos, std::string text,
                        const std::chrono::milliseconds delay = std::chrono::milliseconds( 1000 ),
                        const int requested_width = 0,
                        const ui_tooltip_style &style = ui_tooltip_style() ) {
            dwell_.configure( target_bounds, delay, text );
            if( !dwell_.visible() ) {
                overlay_.hide();
            }
            pos_ = pos;
            text_ = std::move( text );
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
            const bool changed = dwell_.update_pointer( parent_pos, now );
            if( !dwell_.visible() ) {
                overlay_.hide();
            }
            return changed;
        }

        /** Advance only wall-clock dwell time while the pointer remains stationary. */
        bool tick( const clock::time_point now = clock::now() ) {
            return dwell_.tick( now );
        }

        /** Forget current hover/dwell state while retaining configured geometry. */
        bool clear_pointer() {
            overlay_.hide();
            return dwell_.clear_pointer();
        }

        void reset() {
            dwell_.reset();
            text_.clear();
            pos_ = point::zero;
            requested_width_ = 0;
            overlay_.close();
        }

        bool visible() const {
            return dwell_.visible();
        }

        void draw( const catacurses::window &parent ) {
            if( !visible() || text_.empty() || getmaxx( parent ) < 3 ||
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
            overlay_.draw_border( style_.border, true );
            trim_and_print( window, point( 1, 1 ), std::max( 1, width - 2 ), style_.text, text_ );
            overlay_.refresh();
        }

    private:
        ui_overlay overlay_;
        ui_hover_dwell dwell_;
        point pos_ = point::zero;
        std::string text_;
        int requested_width_ = 0;
        ui_tooltip_style style_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_TOOLTIP_H
