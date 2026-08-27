#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H
#define CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H

#include <algorithm>
#include <initializer_list>
#include <optional>
#include <set>
#include <utility>
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

        explicit ui_multiselect_filter( std::vector<T> options )
            : options_( std::move( options ) ), selected_( options_.begin(), options_.end() ) {}

        /**
         * Replace the supported option set without forcing callers to reconstruct
         * selection state by hand. Existing selections are retained when still
         * supported. New options may optionally start selected.
         */
        void set_options( std::vector<T> options, const bool preserve_selection = true,
                          const bool select_new_options = false ) {
            const std::vector<T> old_options = options_;
            const std::set<T> old_selected = selected_;
            options_ = std::move( options );
            selected_.clear();

            for( const T &option : options_ ) {
                const bool existed = std::find( old_options.begin(), old_options.end(), option ) !=
                                     old_options.end();
                if( ( preserve_selection && old_selected.count( option ) > 0 ) ||
                    ( select_new_options && !existed ) ||
                    ( !preserve_selection && select_new_options ) ) {
                    selected_.insert( option );
                }
            }
        }

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
            if( !supports( option ) ) {
                return;
            }
            if( selected_.erase( option ) == 0 ) {
                selected_.insert( option );
            }
        }

        /** Restore or assign one concrete option without toggle-state reconstruction. */
        void set( const T &option, const bool selected ) {
            if( !supports( option ) ) {
                return;
            }
            if( selected ) {
                selected_.insert( option );
            } else {
                selected_.erase( option );
            }
        }

        bool supports( const T &option ) const {
            return std::find( options_.begin(), options_.end(), option ) != options_.end();
        }

        const std::vector<T> &options() const {
            return options_;
        }

    private:
        std::vector<T> options_;
        std::set<T> selected_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H
