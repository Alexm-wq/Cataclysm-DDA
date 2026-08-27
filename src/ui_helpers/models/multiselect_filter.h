#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H
#define CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H

#include <algorithm>
#include <initializer_list>
#include <optional>
#include <set>
#include <vector>

/**
 * Reusable selection model for checkbox filter dropdowns.
 *
 * The model stores concrete options only; callers can expose a synthetic "All"
 * row and wire it directly to toggle_all().  It starts with every option selected,
 * matching the common "show everything" filter default.
 */
template<typename T>
class ui_multiselect_filter
{
    public:
        ui_multiselect_filter() = default;

        ui_multiselect_filter( std::initializer_list<T> options )
            : options_( options ), selected_( options.begin(), options.end() ) {}

        bool contains( const T &option ) const {
            return selected_.count( option ) > 0;
        }

        bool all_selected() const {
            return !options_.empty() && selected_.size() == options_.size();
        }

        bool none_selected() const {
            return selected_.empty();
        }

        std::size_t selected_count() const {
            return selected_.size();
        }

        std::optional<T> first_selected() const {
            for( const T &option : options_ ) {
                if( contains( option ) ) {
                    return option;
                }
            }
            return std::nullopt;
        }

        void select_all() {
            selected_.clear();
            selected_.insert( options_.begin(), options_.end() );
        }

        void clear() {
            selected_.clear();
        }

        void toggle_all() {
            if( all_selected() ) {
                clear();
            } else {
                select_all();
            }
        }

        void toggle( const T &option ) {
            if( std::find( options_.begin(), options_.end(), option ) == options_.end() ) {
                return;
            }
            if( selected_.erase( option ) == 0 ) {
                selected_.insert( option );
            }
        }

        const std::vector<T> &options() const {
            return options_;
        }

    private:
        std::vector<T> options_;
        std::set<T> selected_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H
