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

/** Visual and layout policy for an inline group of action buttons. */
struct ui_action_strip_style {
    nc_color text = c_light_cyan;
    nc_color disabled = c_dark_gray;
    nc_color highlight = h_light_cyan;
    nc_color selected = h_light_cyan;
    bool decorate = true;
    int gap = 1;
};

/**
 * Reusable wrapping action bar for toolbars, tabs, and compact inline controls.
 * Geometry is relative to a caller-owned parent window.
 */
class ui_action_strip
{
    public:
        void clear() {
            entries_.clear();
            labels_.clear();
            hits_.clear();
            hovered_ = -1;
            origin_ = point::zero;
            width_ = 0;
            rows_used_ = 0;
        }

        void configure( const catacurses::window &parent, const point &pos,
                        std::vector<ui_action_entry> entries, int requested_width = 0,
                        int max_rows = 1,
                        const ui_action_strip_style &style = ui_action_strip_style() ) {
            std::string hovered_id;
            if( const ui_action_entry *hovered = entry( hovered_ ) ) {
                hovered_id = hovered->id;
            }

            entries_ = std::move( entries );
            labels_.clear();
            hits_.clear();
            style_ = style;
            origin_ = pos;
            width_ = 0;
            rows_used_ = 0;

            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            if( entries_.empty() || pos.x < 0 || pos.y < 0 || pos.x >= parent_width ||
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

            labels_.reserve( entries_.size() );
            int x = pos.x;
            int y = pos.y;
            for( int index = 0; index < static_cast<int>( entries_.size() ); ++index ) {
                labels_.push_back( display_label( entries_[index] ) );
                int label_width = std::min( width_, utf8_width( labels_.back() ) );
                if( x > pos.x && x + label_width > pos.x + width_ ) {
                    x = pos.x;
                    ++y;
                }
                if( y >= pos.y + max_rows ) {
                    continue;
                }
                label_width = std::min( label_width, pos.x + width_ - x );
                if( label_width <= 0 ) {
                    continue;
                }
                hits_.add( inclusive_rectangle<point>( point( x, y ),
                                                       point( x + label_width - 1, y ) ), index );
                rows_used_ = std::max( rows_used_, y - pos.y + 1 );
                x += label_width + std::max( 0, style_.gap );
            }

            hovered_ = -1;
            if( !hovered_id.empty() ) {
                for( int index = 0; index < static_cast<int>( entries_.size() ); ++index ) {
                    if( entries_[index].id == hovered_id && is_visible( index ) ) {
                        hovered_ = index;
                        break;
                    }
                }
            }
        }

        std::optional<int> hit_test( const point &parent_pos ) const {
            return hits_.hit( parent_pos );
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
                const ui_action_entry &button = entries_[index];
                const nc_color color = !button.enabled ? style_.disabled :
                                       index == hovered_ ? style_.highlight :
                                       button.selected ? style_.selected : style_.text;
                const int width = region.bounds.p_max.x - region.bounds.p_min.x + 1;
                trim_and_print( parent, region.bounds.p_min, width, color, labels_[index] );
            }
        }

        const ui_action_entry *entry( const int index ) const {
            return index >= 0 && index < static_cast<int>( entries_.size() ) ?
                   &entries_[index] : nullptr;
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

    private:
        std::string display_label( const ui_action_entry &entry ) const {
            std::string label = entry.checked.has_value() ?
                                string_format( *entry.checked ? "[x] %s" : "[ ] %s", entry.label ) :
                                entry.label;
            if( style_.decorate ) {
                label = string_format( "[ %s ]", label );
            }
            return label;
        }

        std::vector<ui_action_entry> entries_;
        std::vector<std::string> labels_;
        ui_hit_map<int> hits_;
        ui_action_strip_style style_;
        point origin_ = point::zero;
        int width_ = 0;
        int rows_used_ = 0;
        int hovered_ = -1;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_ACTION_STRIP_H
