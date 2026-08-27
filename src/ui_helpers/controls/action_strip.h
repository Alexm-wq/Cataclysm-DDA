#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_ACTION_STRIP_H
#define CATA_SRC_UI_HELPERS_CONTROLS_ACTION_STRIP_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cursesdef.h"
#include "../../output.h"
#include "../../point.h"
#include "../models/action_entry.h"
#include "../models/hit_map.h"

/** Side of the strip an action is anchored to. */
enum class ui_action_alignment : int {
    left,
    right
};

/** Layout metadata kept separate from renderer-independent ui_action_entry. */
struct ui_action_strip_item {
    ui_action_entry action;
    int group = 0;
    ui_action_alignment alignment = ui_action_alignment::left;
};

/** Visual and layout policy for an inline group of action buttons. */
struct ui_action_strip_style {
    nc_color text = c_light_cyan;
    nc_color disabled = c_dark_gray;
    nc_color highlight = h_light_cyan;
    nc_color selected = h_light_cyan;
    bool decorate = true;
    int gap = 1;
    int group_gap = 3;
};

/**
 * Reusable wrapping action bar for toolbars, tabs, and compact inline controls.
 * Geometry is relative to a caller-owned parent window.
 *
 * Entries may carry semantic groups and can be pinned to the right edge.  This
 * allows responsive toolbars to preserve group spacing and a fixed Back action
 * while drawing and hit-testing from the same geometry.
 */
class ui_action_strip
{
    public:
        void clear() {
            items_.clear();
            labels_.clear();
            hits_.clear();
            hovered_ = -1;
            origin_ = point::zero;
            width_ = 0;
            rows_used_ = 0;
        }

        /** Compatibility overload for ordinary left-aligned strips. */
        void configure( const catacurses::window &parent, const point &pos,
                        std::vector<ui_action_entry> entries, int requested_width = 0,
                        int max_rows = 1,
                        const ui_action_strip_style &style = ui_action_strip_style() ) {
            std::vector<ui_action_strip_item> items;
            items.reserve( entries.size() );
            for( ui_action_entry &entry : entries ) {
                items.push_back( { std::move( entry ), 0, ui_action_alignment::left } );
            }
            configure( parent, pos, std::move( items ), requested_width, max_rows, style );
        }

        void configure( const catacurses::window &parent, const point &pos,
                        std::vector<ui_action_strip_item> items, int requested_width = 0,
                        int max_rows = 1,
                        const ui_action_strip_style &style = ui_action_strip_style() ) {
            std::string hovered_id;
            if( const ui_action_entry *hovered = entry( hovered_ ) ) {
                hovered_id = hovered->id;
            }

            items_ = std::move( items );
            labels_.clear();
            hits_.clear();
            style_ = style;
            origin_ = pos;
            width_ = 0;
            rows_used_ = 0;

            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            if( items_.empty() || pos.x < 0 || pos.y < 0 || pos.x >= parent_width ||
                pos.y >= parent_height ) {
                hovered_ = -1;
                return;
            }

            const int available_width = parent_width - pos.x;
            width_ = requested_width > 0 ? std::min( requested_width, available_width ) :
                     available_width;
            const int available_rows = parent_height - pos.y;
            max_rows = max_rows > 0 ? std::min( max_rows, available_rows ) : available_rows;
            if( width_ <= 0 || max_rows <= 0 ) {
                hovered_ = -1;
                return;
            }

            labels_.reserve( items_.size() );
            for( const ui_action_strip_item &item : items_ ) {
                labels_.push_back( display_label( item.action ) );
            }

            const auto item_width = [&]( const int index ) {
                return std::min( width_, utf8_width( labels_[index] ) );
            };
            const auto add_hit = [&]( const int index, const int x, const int y, const int max_x ) {
                const int actual_width = std::min( item_width( index ), max_x - x );
                if( actual_width <= 0 || y < pos.y || y >= pos.y + max_rows ) {
                    return false;
                }
                hits_.add( inclusive_rectangle<point>( point( x, y ),
                                                       point( x + actual_width - 1, y ) ), index );
                rows_used_ = std::max( rows_used_, y - pos.y + 1 );
                return true;
            };

            // Lay out right-aligned items backwards so their original order is
            // preserved when viewed left-to-right.
            int right_start = pos.x + width_;
            int next_group = -1;
            bool have_right = false;
            for( int index = static_cast<int>( items_.size() ) - 1; index >= 0; --index ) {
                if( items_[index].alignment != ui_action_alignment::right ) {
                    continue;
                }
                const int gap = have_right ?
                                ( items_[index].group == next_group ? std::max( 0, style_.gap ) :
                                  std::max( 0, style_.group_gap ) ) : 0;
                const int width = item_width( index );
                const int x = right_start - gap - width;
                if( x < pos.x ) {
                    continue;
                }
                if( add_hit( index, x, pos.y, pos.x + width_ ) ) {
                    right_start = x;
                    next_group = items_[index].group;
                    have_right = true;
                }
            }

            int x = pos.x;
            int y = pos.y;
            int previous_group = -1;
            for( int index = 0; index < static_cast<int>( items_.size() ); ++index ) {
                if( items_[index].alignment != ui_action_alignment::left ) {
                    continue;
                }
                const int gap = previous_group < 0 ? 0 :
                                ( items_[index].group == previous_group ? std::max( 0, style_.gap ) :
                                  std::max( 0, style_.group_gap ) );
                int row_limit = pos.x + width_;
                if( y == pos.y && have_right ) {
                    row_limit = std::max( pos.x, right_start - std::max( 0, style_.gap ) );
                }
                const int width = item_width( index );
                if( x > pos.x && x + gap + width > row_limit ) {
                    x = pos.x;
                    ++y;
                    previous_group = -1;
                    row_limit = pos.x + width_;
                }
                if( y >= pos.y + max_rows ) {
                    continue;
                }
                if( previous_group >= 0 ) {
                    x += gap;
                }
                if( x + width > row_limit ) {
                    continue;
                }
                if( add_hit( index, x, y, row_limit ) ) {
                    x += width;
                    previous_group = items_[index].group;
                }
            }

            hovered_ = -1;
            if( !hovered_id.empty() ) {
                for( int index = 0; index < static_cast<int>( items_.size() ); ++index ) {
                    if( items_[index].action.id == hovered_id && is_visible( index ) ) {
                        hovered_ = index;
                        break;
                    }
                }
            }
        }

        std::optional<int> hit_test( const point &parent_pos ) const {
            return hits_.hit( parent_pos );
        }

        std::optional<inclusive_rectangle<point>> bounds( const int index ) const {
            for( const typename ui_hit_map<int>::hit_region &region : hits_.regions() ) {
                if( region.target == index ) {
                    return region.bounds;
                }
            }
            return std::nullopt;
        }

        std::optional<inclusive_rectangle<point>> bounds_for_id( const std::string &id ) const {
            for( int index = 0; index < static_cast<int>( items_.size() ); ++index ) {
                if( items_[index].action.id == id ) {
                    return bounds( index );
                }
            }
            return std::nullopt;
        }

        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos ? hit_test( *parent_pos ).value_or( -1 ) : -1;
        }

        ui_action_result handle_input( const std::string &action,
                                       const std::optional<point> &parent_pos ) {
            if( action == "MOUSE_MOVE" ) {
                update_hover( parent_pos );
                return { hovered_ >= 0 ? ui_action_result_type::handled :
                         ui_action_result_type::ignored, std::nullopt };
            }
            if( action != "SELECT" && action != "CONFIRM" ) {
                return {};
            }

            const int index = action == "SELECT" && parent_pos ?
                              hit_test( *parent_pos ).value_or( -1 ) : hovered_;
            const ui_action_entry *selected_entry = entry( index );
            if( selected_entry == nullptr || !is_visible( index ) ) {
                return {};
            }
            return { selected_entry->enabled ? ui_action_result_type::activated :
                     ui_action_result_type::disabled, *selected_entry };
        }

        void draw( const catacurses::window &parent ) const {
            for( const typename ui_hit_map<int>::hit_region &region : hits_.regions() ) {
                const int index = region.target;
                const ui_action_entry &button = items_[index].action;
                const nc_color color = !button.enabled ? style_.disabled :
                                       index == hovered_ ? style_.highlight :
                                       button.selected ? style_.selected : style_.text;
                const int width = region.bounds.p_max.x - region.bounds.p_min.x + 1;
                trim_and_print( parent, region.bounds.p_min, width, color, labels_[index] );
            }
        }

        const ui_action_entry *entry( const int index ) const {
            return index >= 0 && index < static_cast<int>( items_.size() ) ?
                   &items_[index].action : nullptr;
        }

        int hovered_index() const {
            return hovered_;
        }

        int rows_used() const {
            return rows_used_;
        }

        point origin() const {
            return origin_;
        }

        int width() const {
            return width_;
        }

        bool is_visible( const int index ) const {
            for( const typename ui_hit_map<int>::hit_region &region : hits_.regions() ) {
                if( region.target == index ) {
                    return true;
                }
            }
            return false;
        }

        static std::string format_label( const ui_action_entry &entry,
                                         const ui_action_strip_style &style = ui_action_strip_style() ) {
            std::string label = entry.checked.has_value() ?
                                string_format( *entry.checked ? "[x] %s" : "[ ] %s", entry.label ) :
                                entry.label;
            if( entry.dropdown ) {
                label += " ▼";
            }
            if( style.decorate && !entry.checked.has_value() ) {
                label = string_format( "[ %s ]", label );
            }
            return label;
        }

    private:
        std::string display_label( const ui_action_entry &entry ) const {
            return format_label( entry, style_ );
        }

        std::vector<ui_action_strip_item> items_;
        std::vector<std::string> labels_;
        ui_hit_map<int> hits_;
        ui_action_strip_style style_;
        point origin_ = point::zero;
        int width_ = 0;
        int rows_used_ = 0;
        int hovered_ = -1;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_ACTION_STRIP_H
