#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_LIST_H
#define CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_LIST_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "../../input_context.h"
#include "../../input.h"
#include "../../output.h"
#include "../models/action_entry.h"
#include "../models/hit_map.h"
#include "../models/list_selection.h"
#include "../models/scroll_model.h"
#include "../primitive/scrollbar.h"

struct ui_selection_list_style {
    nc_color text = c_light_gray;
    nc_color disabled = c_dark_gray;
    nc_color selected = h_white;
    nc_color cursor = c_white;
};

/** Scrollable selection list; callers supply labels, eligibility and geometry.
 * Owns checkboxes, focus, hover, hit testing, Ctrl/Shift selection, double-click,
 * keyboard navigation and scrollbar capture. Wheel scrolling never selects.
 */
class ui_selection_list
{
    public:
        void set_entries( std::vector<ui_action_entry> entries, bool multiple = true ) {
            entries_ = std::move( entries );
            multiple_ = multiple;
            selected_.assign( entries_.size(), false );
            for( size_t i = 0; i < entries_.size(); ++i ) {
                selected_[i] = entries_[i].enabled && entries_[i].selected;
            }
            selection_.reset();
            cursor_ = 0;
            hovered_ = -1;
            scroll_.set_content_size( static_cast<int>( entries_.size() ) ).scroll_to_start();
            hits_.clear();
        }

        void draw( const catacurses::window &window, const point &origin, int width, int height,
                   const ui_selection_list_style &style = ui_selection_list_style() ) {
            origin_ = origin;
            width_ = std::max( 0, std::min( width, getmaxx( window ) - origin.x ) );
            height_ = std::max( 0, std::min( height, getmaxy( window ) - origin.y ) );
            scroll_.set_viewport_size( height_ );
            hits_.clear();
            if( width_ < 2 || height_ == 0 ) {
                return;
            }
            for( int row = 0; row < height_; ++row ) {
                const std::optional<int> index = scroll_.index_at_viewport_row( row );
                if( !index ) {
                    break;
                }
                const ui_action_entry &entry = entries_[*index];
                const point pos( origin.x, origin.y + row );
                hits_.add( inclusive_rectangle<point>( pos, pos + point( width_ - 2, 0 ) ), *index );
                const nc_color color = !entry.enabled ? style.disabled : selected_[*index] ?
                                       style.selected : *index == cursor_ || *index == hovered_ ?
                                       style.cursor : style.text;
                const std::string label = multiple_ ? ( selected_[*index] ? "[x] " : "[ ] " ) +
                                          entry.label : entry.label;
                trim_and_print( window, pos, width_ - 1, color, label );
            }
            scrollbar_.offset_x( origin.x + width_ - 1 ).offset_y( origin.y )
            .model( scroll_ ).apply( window );
        }

        ui_action_result handle_input( const std::string &action, input_context &context,
                                       const std::optional<point> &pos ) {
            if( scrollbar_.handle_input( action, context, scroll_ ) ) {
                return { ui_action_result_type::handled, std::nullopt };
            }
            const bool inside = pos && pos->x >= origin_.x && pos->x < origin_.x + width_ &&
                                pos->y >= origin_.y && pos->y < origin_.y + height_;
            if( action == "MOUSE_MOVE" ) {
                hovered_ = pos ? hits_.hit( *pos ).value_or( -1 ) : -1;
                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
                if( inside ) {
                    scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );
                }
                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action == "UP" || action == "DOWN" || action == "PAGE_UP" || action == "PAGE_DOWN" ||
                action == "HOME" || action == "END" ) {
                const int delta = action == "UP" ? -1 : action == "DOWN" ? 1 :
                                  action == "PAGE_UP" ? -height_ : action == "PAGE_DOWN" ? height_ :
                                  action == "HOME" ? -static_cast<int>( entries_.size() ) :
                                  static_cast<int>( entries_.size() );
                cursor_ = std::clamp( cursor_ + delta, 0,
                                     std::max( 0, static_cast<int>( entries_.size() ) - 1 ) );
                scroll_.ensure_visible( cursor_ );
                return { ui_action_result_type::handled, std::nullopt };
            }
            bool activate = action == "CONFIRM";
            if( action == "SELECT" ) {
                const std::optional<int> index = pos ? hits_.hit( *pos ) : std::nullopt;
                if( !index ) {
                    return {};
                }
                cursor_ = *index;
                const input_event raw = context.get_raw_input();
                activate = selection_.click( selected_, cursor_, [&]( int i ) {
                    return entries_[i].enabled;
                }, multiple_ && raw.modifiers.count( keymod_t::ctrl ) != 0,
                multiple_ && raw.modifiers.count( keymod_t::shift ) != 0 );
                if( !multiple_ ) {
                    select_only( cursor_ );
                }
            } else if( !activate ) {
                return {};
            }
            if( entries_.empty() ) {
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( !entries_[cursor_].enabled ) {
                return { ui_action_result_type::disabled, entries_[cursor_] };
            }
            if( activate && selected_indices().empty() ) {
                select_only( cursor_ );
            }
            return { activate ? ui_action_result_type::activated : ui_action_result_type::handled,
                     entries_[cursor_] };
        }

        void select_only( int index ) {
            std::fill( selected_.begin(), selected_.end(), false );
            if( index >= 0 && index < static_cast<int>( entries_.size() ) && entries_[index].enabled ) {
                selected_[index] = true;
                cursor_ = index;
                scroll_.ensure_visible( index );
            }
        }

        void select_all() {
            for( size_t i = 0; i < entries_.size(); ++i ) {
                selected_[i] = entries_[i].enabled;
            }
            selection_.reset();
        }

        void set_selected( int index, bool selected ) {
            if( index >= 0 && index < static_cast<int>( entries_.size() ) ) {
                selected_[index] = selected && entries_[index].enabled;
            }
        }

        void set_label( int index, std::string label ) {
            if( index >= 0 && index < static_cast<int>( entries_.size() ) ) {
                entries_[index].label = std::move( label );
            }
        }

        std::vector<int> selected_indices() const {
            std::vector<int> result;
            for( size_t i = 0; i < selected_.size(); ++i ) {
                if( selected_[i] ) {
                    result.push_back( static_cast<int>( i ) );
                }
            }
            return result;
        }

        int cursor() const {
            return cursor_;
        }

    private:
        std::vector<ui_action_entry> entries_;
        std::vector<bool> selected_;
        ui_list_selection selection_;
        ui_scroll_model scroll_;
        scrollbar scrollbar_;
        ui_hit_map<int> hits_;
        point origin_ = point::zero;
        int width_ = 0;
        int height_ = 0;
        int cursor_ = 0;
        int hovered_ = -1;
        bool multiple_ = true;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_LIST_H
