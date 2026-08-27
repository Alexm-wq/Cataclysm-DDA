#pragma once
#ifndef CATA_SRC_UI_HELPERS_DROPDOWN_H
#define CATA_SRC_UI_HELPERS_DROPDOWN_H

#include <algorithm>
#include <initializer_list>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "output.h"
#include "point.h"

/** A single row in a lightweight dropdown/context menu. */
struct ui_dropdown_entry {
    std::string label;
    std::string id;
    bool enabled = true;
    bool selected = false;
    // Keep disabled_reason before optional extension fields so existing aggregate
    // initializers retain their historical { label, id, enabled, selected, reason } layout.
    std::string disabled_reason;
    // When set, ui_dropdown renders a standard [x]/[ ] prefix.
    // This keeps checkbox presentation consistent for reusable filter menus.
    std::optional<bool> checked;
};

/** Visual policy for ui_dropdown.  Callers may override any color independently. */
struct ui_dropdown_style {
    nc_color border = c_light_cyan;
    nc_color text = c_light_gray;
    nc_color disabled = c_dark_gray;
    nc_color highlight = h_green;
};


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

/**
 * Reusable mouse-first dropdown/context-menu overlay.
 *
 * Coordinates are relative to a caller-owned parent window, but the menu renders
 * through its own tiny curses window.  That lets it safely sit above SDL-backed
 * Live/Split previews without refreshing an opaque full-screen parent window.
 */
class ui_dropdown
{
    public:
        void close() {
            entries_.clear();
            hovered_ = -1;
            pos_ = point::zero;
            width_ = 0;
            height_ = 0;
            window_ = catacurses::window();
        }

        bool is_open() const {
            return !entries_.empty() && width_ >= 3 && height_ >= 3;
        }

        void configure( const catacurses::window &parent, point pos,
                        std::vector<ui_dropdown_entry> entries,
                        int requested_width = 0,
                        const ui_dropdown_style &style = ui_dropdown_style() ) {
            std::string hovered_id;
            if( hovered_ >= 0 && hovered_ < static_cast<int>( entries_.size() ) ) {
                hovered_id = entries_[hovered_].id;
            }

            style_ = style;
            entries_ = std::move( entries );
            if( entries_.empty() || getmaxx( parent ) < 3 || getmaxy( parent ) < 3 ) {
                close();
                return;
            }

            int widest = 0;
            for( const ui_dropdown_entry &entry : entries_ ) {
                const int checkbox_width = entry.checked.has_value() ? 4 : 0;
                widest = std::max( widest, utf8_width( entry.label ) + checkbox_width );
            }
            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            width_ = requested_width > 0 ? requested_width : widest + 4;
            width_ = std::clamp( width_, 3, parent_width );
            height_ = std::min( static_cast<int>( entries_.size() ) + 2, parent_height );
            if( height_ < 3 ) {
                close();
                return;
            }
            if( static_cast<int>( entries_.size() ) > height_ - 2 ) {
                entries_.resize( height_ - 2 );
            }

            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_width - width_ ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height - height_ ) );
            pos_ = pos;

            hovered_ = -1;
            if( !hovered_id.empty() ) {
                for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                    if( entries_[i].id == hovered_id ) {
                        hovered_ = i;
                        break;
                    }
                }
            }
        }

        bool contains( const point &parent_pos ) const {
            return is_open() && parent_pos.x >= pos_.x && parent_pos.x < pos_.x + width_ &&
                   parent_pos.y >= pos_.y && parent_pos.y < pos_.y + height_;
        }

        std::optional<int> hit_test( const point &parent_pos ) const {
            if( !contains( parent_pos ) || parent_pos.x <= pos_.x ||
                parent_pos.x >= pos_.x + width_ - 1 ) {
                return std::nullopt;
            }
            const int row = parent_pos.y - pos_.y - 1;
            if( row < 0 || row >= static_cast<int>( entries_.size() ) ) {
                return std::nullopt;
            }
            return row;
        }

        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos ? hit_test( *parent_pos ).value_or( -1 ) : -1;
        }

        int hovered_index() const {
            return hovered_;
        }

        const ui_dropdown_entry *entry( const int index ) const {
            return index >= 0 && index < static_cast<int>( entries_.size() ) ? &entries_[index] : nullptr;
        }

        point pos() const {
            return pos_;
        }

        int width() const {
            return width_;
        }

        int height() const {
            return height_;
        }

        void draw( const catacurses::window &parent ) {
            if( !is_open() ) {
                window_ = catacurses::window();
                return;
            }

            const point screen_pos( getbegx( parent ) + pos_.x, getbegy( parent ) + pos_.y );
            const bool needs_window = !window_ || getmaxx( window_ ) != width_ ||
                                      getmaxy( window_ ) != height_ ||
                                      getbegx( window_ ) != screen_pos.x ||
                                      getbegy( window_ ) != screen_pos.y;
            if( needs_window ) {
                window_ = catacurses::newwin( height_, width_, screen_pos );
            }

            werase( window_ );
            draw_border( window_, style_.border );
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                const ui_dropdown_entry &row = entries_[i];
                const bool highlighted = i == hovered_ || row.selected;
                const nc_color color = !row.enabled ? style_.disabled :
                                       highlighted ? style_.highlight : style_.text;
                const std::string label = row.checked.has_value() ?
                                          string_format( *row.checked ? "[x] %s" : "[ ] %s", row.label ) :
                                          row.label;
                trim_and_print( window_, point( 1, i + 1 ), std::max( 1, width_ - 2 ), color,
                                label );
            }
            wnoutrefresh( window_ );
        }

    private:
        catacurses::window window_;
        std::vector<ui_dropdown_entry> entries_;
        ui_dropdown_style style_;
        point pos_ = point::zero;
        int width_ = 0;
        int height_ = 0;
        int hovered_ = -1;
};

#endif // CATA_SRC_UI_HELPERS_DROPDOWN_H
