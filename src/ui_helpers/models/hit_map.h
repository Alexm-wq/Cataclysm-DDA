#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_HIT_MAP_H
#define CATA_SRC_UI_HELPERS_MODELS_HIT_MAP_H

#include <cstddef>
#include <optional>
#include <utility>
#include <vector>

#include "../../cuboid_rectangle.h"
#include "../../point.h"

/** Maps redraw-generated rectangles to stable semantic targets. */
template<typename T>
class ui_hit_map
{
    public:
        struct hit_region {
            inclusive_rectangle<point> bounds;
            T target;
        };

        void clear() {
            regions_.clear();
        }

        void reserve( const std::size_t count ) {
            regions_.reserve( count );
        }

        void add( const inclusive_rectangle<point> &bounds, T target ) {
            regions_.push_back( { bounds, std::move( target ) } );
        }

        std::optional<T> hit( const point &pos ) const {
            // Later regions are visually on top of earlier regions.
            for( auto iter = regions_.rbegin(); iter != regions_.rend(); ++iter ) {
                if( iter->bounds.contains( pos ) ) {
                    return iter->target;
                }
            }
            return std::nullopt;
        }

        bool empty() const {
            return regions_.empty();
        }

        std::size_t size() const {
            return regions_.size();
        }

        const std::vector<hit_region> &regions() const {
            return regions_;
        }

    private:
        std::vector<hit_region> regions_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_HIT_MAP_H
