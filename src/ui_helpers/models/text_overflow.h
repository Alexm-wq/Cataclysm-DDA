#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_TEXT_OVERFLOW_H
#define CATA_SRC_UI_HELPERS_MODELS_TEXT_OVERFLOW_H

#include <map>
#include <optional>
#include <string>

#include "hit_map.h"

struct ui_overflow_text {
    inclusive_rectangle<point> bounds;
    std::string text;
};

/** Redraw-owned text targets. Refreshed windows occlude earlier windows, even
 * where the top window contains no text. Fitting labels also occlude old labels.
 */
class ui_text_overflow_model
{
    public:
        static bool clipped( const int text_width, const int available_width ) {
            return available_width > 0 && text_width > available_width;
        }

        void clear() {
            text_.clear();
            windows_.clear();
        }

        void erase_window( const void *window ) {
            text_.erase( window );
        }

        void record( const void *window, const inclusive_rectangle<point> &bounds,
                     const std::string &text, const int text_width, const int available_width ) {
            if( available_width > 0 ) {
                text_[window].add( bounds, clipped( text_width, available_width ) ? text : std::string() );
            }
        }

        void present( const void *window, const inclusive_rectangle<point> &bounds ) {
            windows_.add( bounds, window );
        }

        std::optional<ui_overflow_text> hit( const point &pos ) const {
            const auto window = windows_.hit( pos );
            if( !window ) {
                return std::nullopt;
            }
            const auto found = text_.find( *window );
            if( found == text_.end() ) {
                return std::nullopt;
            }
            const auto &regions = found->second.regions();
            for( auto it = regions.rbegin(); it != regions.rend(); ++it ) {
                if( it->bounds.contains( pos ) ) {
                    return it->target.empty() ? std::nullopt :
                           std::make_optional( ui_overflow_text{ it->bounds, it->target } );
                }
            }
            return std::nullopt;
        }

    private:
        std::map<const void *, ui_hit_map<std::string>> text_;
        ui_hit_map<const void *> windows_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_TEXT_OVERFLOW_H
