#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_LIST_H
#define CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_LIST_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "../../catacharset.h"
#include "../../input_context.h"
#include "../../input.h"
#include "../../output.h"
#include "../models/action_entry.h"
#include "../models/hit_map.h"
#include "../models/list_selection.h"
#include "../models/scroll_model.h"
#include "../models/tree_model.h"
#include "../primitive/scrollbar.h"

struct ui_selection_list_style {
    nc_color text = c_light_gray;
    nc_color disabled = c_dark_gray;
    nc_color disabled_cursor = h_dark_gray;
    nc_color disabled_hint = c_light_red;
    nc_color selected = h_white;
    nc_color cursor = c_white;
    nc_color positive = c_light_green;
    nc_color positive_selected = h_green;
    nc_color positive_cursor = h_green;
    int indent = 2;
    bool allow_label_colors = true;
};

/** Scrollable selection list; callers supply labels, eligibility and geometry.
 * Owns checkboxes, focus, hover, hit testing, Ctrl/Shift selection, double-click,
 * keyboard navigation and scrollbar capture. Optional tree rows share the same
 * control, with separate expander hitboxes. Wheel scrolling never selects.
 */
class ui_selection_list
{
    public:
        void set_entries( std::vector<ui_action_entry> entries, bool multiple = true ) {
            entries_ = std::move( entries );
            tree_.reset( std::vector<ui_tree_node>( entries_.size() ) );
            hierarchical_ = false;
            ensure_cursor_on_draw_ = false;
            multiple_ = multiple;
            selected_.assign( entries_.size(), false );
            for( size_t i = 0; i < entries_.size(); ++i ) {
                selected_[i] = entries_[i].enabled && entries_[i].selected;
            }
            selection_.reset();
            const auto first_selected = std::find( selected_.begin(), selected_.end(), true );
            if( first_selected != selected_.end() ) {
                selection_.set_anchor( static_cast<int>( first_selected - selected_.begin() ) );
            }
            cursor_ = 0;
            hovered_ = -1;
            scroll_.set_content_size( static_cast<int>( entries_.size() ) ).scroll_to_start();
            hits_.clear();
            expanders_.clear();
        }

        /** Supply depth-first rows and their parents. Groups cannot be selected;
         * disabled containers can still expand to expose usable descendants.
         */
        void set_tree_entries( std::vector<ui_action_entry> entries,
                               std::vector<ui_tree_node> nodes, bool multiple = false ) {
            set_entries( std::move( entries ), multiple );
            nodes.resize( entries_.size() );
            tree_.reset( std::move( nodes ) );
            hierarchical_ = true;
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                selected_[i] = selected_[i] && tree_.selectable( i );
                if( selected_[i] ) {
                    tree_.reveal( i );
                    cursor_ = i;
                }
            }
            scroll_.set_content_size( static_cast<int>( tree_.visible_indices().size() ) );
            ensure_cursor_on_draw_ = true;
        }

        bool expanded( const int index ) const {
            return tree_.expanded( index );
        }

        void set_expanded( const int index, const bool value ) {
            const int top = tree_.index_at( scroll_.viewport_pos() );
            if( tree_.set_expanded( index, value ) ) {
                sync_tree_view( top );
            }
        }

        const std::vector<int> &visible_indices() const {
            return tree_.visible_indices();
        }

        /** Opt in to immediate activation for single-select picker rows. */
        void activate_on_single_click( const bool value = true ) {
            activate_on_single_click_ = value;
        }

        void draw( const catacurses::window &window, const point &origin, int width, int height,
                   const ui_selection_list_style &style = ui_selection_list_style() ) {
            origin_ = origin;
            width_ = std::max( 0, std::min( width, getmaxx( window ) - origin.x ) );
            height_ = std::max( 0, std::min( height, getmaxy( window ) - origin.y ) );
            scroll_.set_viewport_size( height_ );
            if( ensure_cursor_on_draw_ && height_ > 0 ) {
                scroll_.ensure_visible( tree_.visible_position( cursor_ ) );
                ensure_cursor_on_draw_ = false;
            }
            hits_.clear();
            expanders_.clear();
            if( width_ < 2 || height_ == 0 ) {
                return;
            }
            for( int row = 0; row < height_; ++row ) {
                const std::optional<int> visible = scroll_.index_at_viewport_row( row );
                if( !visible ) {
                    break;
                }
                const int index = tree_.index_at( *visible );
                const ui_action_entry &entry = entries_[index];
                const point pos( origin.x, origin.y + row );
                hits_.add( inclusive_rectangle<point>( pos, pos + point( width_ - 2, 0 ) ), index );
                const bool positive = entry.tone == ui_action_tone::positive;
                const ui_list_row_highlight highlight = ui_list_highlight( index, cursor_, hovered_,
                                                       selected_[index], multiple_ );
                const bool focused = highlight != ui_list_row_highlight::none;
                const nc_color color = !entry.enabled ?
                                       ( focused ? style.disabled_cursor : style.disabled ) :
                                       highlight == ui_list_row_highlight::selected ?
                                       ( positive ? style.positive_selected : style.selected ) : focused ?
                                       ( positive ? style.positive_cursor : style.cursor ) :
                                       positive ? style.positive : style.text;
                std::string prefix;
                if( hierarchical_ ) {
                    // Keep expanders reachable even for deeply nested modded containers.
                    const int indent = std::min( tree_.depth( index ) * std::max( 0, style.indent ),
                                                 std::max( 0, width_ - 8 ) );
                    prefix = std::string( indent, ' ' );
                    if( tree_.expandable( index ) ) {
                        const point expander = pos + point( indent, 0 );
                        expanders_.add( inclusive_rectangle<point>( expander,
                                        expander + point( 1, 0 ) ), index );
                        prefix += tree_.expanded( index ) ? "▼ " : "▶ ";
                    } else {
                        prefix += "  ";
                    }
                }
                if( multiple_ ) {
                    prefix += !tree_.selectable( index ) ? "    " : selected_[index] ? "[x] " : "[ ] ";
                }
                // Screens can opt out of inventory colors; disabled rows always do.
                const bool label_colors = entry.enabled && style.allow_label_colors;
                const std::string label = prefix + ( label_colors ? entry.label :
                                          remove_color_tags( entry.label ) );
                const std::string hint = entry.enabled ? std::string() :
                                         remove_color_tags( entry.disabled_hint );
                const int hint_width = std::min( utf8_width( hint ), ( width_ - 2 ) / 2 );
                const int label_width = width_ - 1 - ( hint_width > 0 ? hint_width + 1 : 0 );
                const std::string shown_label = trim_by_length( label, label_width );
                trim_and_print( window, pos, label_width, color, shown_label );
                if( hint_width > 0 ) {
                    const int hint_x = utf8_width( remove_color_tags( shown_label ) ) + 1;
                    trim_and_print( window, pos + point( hint_x, 0 ), width_ - 1 - hint_x,
                                    style.disabled_hint, hint );
                }
            }
            scrollbar_.offset_x( origin.x + width_ - 1 ).offset_y( origin.y )
            .model( scroll_ ).apply( window );
        }

        ui_action_result handle_input( const std::string &action, input_context &context,
                                       const std::optional<point> &pos ) {
            if( scrollbar_.handle_input( action, context, scroll_ ) ) {
                hovered_ = -1;
                return { ui_action_result_type::handled, std::nullopt };
            }
            const bool inside = pos && pos->x >= origin_.x && pos->x < origin_.x + width_ &&
                                pos->y >= origin_.y && pos->y < origin_.y + height_;
            if( action == "MOUSE_MOVE" ) {
                hovered_ = pos ? hits_.hit( *pos ).value_or( -1 ) : -1;
                cursor_ = ui_list_cursor_after_hover( cursor_, hovered_, selected_, multiple_ );
                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
                if( inside ) {
                    scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );
                    hovered_ = -1;
                }
                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action == "UP" || action == "DOWN" || action == "PAGE_UP" || action == "PAGE_DOWN" ||
                action == "HOME" || action == "END" ) {
                const int delta = action == "UP" ? -1 : action == "DOWN" ? 1 :
                                  action == "PAGE_UP" ? -std::max( 1, height_ ) :
                                  action == "PAGE_DOWN" ? std::max( 1, height_ ) :
                                  action == "HOME" ? -static_cast<int>( tree_.visible_indices().size() ) :
                                  static_cast<int>( tree_.visible_indices().size() );
                const int last = std::max( 0, static_cast<int>( tree_.visible_indices().size() ) - 1 );
                const int next = std::clamp( tree_.visible_position( cursor_ ) + delta, 0, last );
                set_cursor( tree_.index_at( next ) );
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( hierarchical_ && ( action == "LEFT" || action == "RIGHT" ) ) {
                hovered_ = -1;
                if( action == "LEFT" ) {
                    if( tree_.expanded( cursor_ ) ) {
                        set_expanded( cursor_, false );
                    } else if( tree_.parent( cursor_ ) >= 0 ) {
                        set_cursor( tree_.parent( cursor_ ) );
                    }
                } else if( tree_.expandable( cursor_ ) ) {
                    if( !tree_.expanded( cursor_ ) ) {
                        set_expanded( cursor_, true );
                    } else {
                        set_cursor( tree_.index_at( tree_.visible_position( cursor_ ) + 1 ) );
                    }
                }
                return { ui_action_result_type::handled, std::nullopt };
            }
            bool activate = action == "CONFIRM";
            if( action == "SELECT" ) {
                const std::optional<int> index = pos ? hits_.hit( *pos ) : std::nullopt;
                if( !index ) {
                    return {};
                }
                cursor_ = *index;
                hovered_ = -1;
                if( ( pos && expanders_.hit( *pos ) ) || !tree_.selectable( cursor_ ) ) {
                    selection_.reset();
                    set_expanded( cursor_, !tree_.expanded( cursor_ ) );
                    return { ui_action_result_type::handled, std::nullopt };
                }
                if( !entries_[cursor_].enabled ) {
                    selection_.reset();
                    return { ui_action_result_type::disabled, entries_[cursor_] };
                }
                const input_event raw = context.get_raw_input();
                activate = selection_.click( selected_, cursor_, [&]( int i ) {
                    return entries_[i].enabled && tree_.selectable( i ) && tree_.visible_position( i ) >= 0;
                }, multiple_ && raw.modifiers.count( keymod_t::ctrl ) != 0,
                multiple_ && raw.modifiers.count( keymod_t::shift ) != 0 );
                if( !multiple_ ) {
                    select_only( cursor_ );
                    if( activate_on_single_click_ ) {
                        activate = true;
                    }
                }
            } else if( !activate ) {
                return {};
            }
            if( entries_.empty() ) {
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( !tree_.selectable( cursor_ ) ) {
                set_expanded( cursor_, !tree_.expanded( cursor_ ) );
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( !entries_[cursor_].enabled ) {
                return { ui_action_result_type::disabled, entries_[cursor_] };
            }
            if( activate && ( !multiple_ || selected_indices().empty() ) ) {
                select_only( cursor_ );
            }
            return { activate ? ui_action_result_type::activated : ui_action_result_type::handled,
                     entries_[cursor_] };
        }

        void select_only( int index ) {
            std::fill( selected_.begin(), selected_.end(), false );
            if( tree_.selectable( index ) && entries_[index].enabled ) {
                selected_[index] = true;
                set_cursor( index );
            }
        }

        void select_all() {
            for( size_t i = 0; i < entries_.size(); ++i ) {
                selected_[i] = entries_[i].enabled && tree_.selectable( i ) && tree_.visible_position( i ) >= 0;
            }
            selection_.reset();
        }

        void set_selected( int index, bool selected ) {
            if( index >= 0 && index < static_cast<int>( entries_.size() ) ) {
                selected_[index] = selected && entries_[index].enabled && tree_.selectable( index );
            }
        }

        void set_label( int index, std::string label ) {
            if( index >= 0 && index < static_cast<int>( entries_.size() ) ) {
                entries_[index].label = std::move( label );
            }
        }

        /** Restore focus after rebuilding rows without changing their selection. */
        void set_cursor( int index ) {
            cursor_ = std::clamp( index, 0, std::max( 0, static_cast<int>( entries_.size() ) - 1 ) );
            hovered_ = -1;
            tree_.reveal( cursor_ );
            scroll_.set_content_size( static_cast<int>( tree_.visible_indices().size() ) );
            scroll_.ensure_visible( tree_.visible_position( cursor_ ) );
            ensure_cursor_on_draw_ = height_ == 0;
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
        void sync_tree_view( const int previous_top ) {
            scroll_.set_content_size( static_cast<int>( tree_.visible_indices().size() ) );
            scroll_.set_viewport_pos( tree_.visible_position( tree_.visible_ancestor( previous_top ) ) );
            cursor_ = std::max( 0, tree_.visible_ancestor( cursor_ ) );
            hovered_ = -1;
            selection_.reset();
            hits_.clear();
            expanders_.clear();
        }

        std::vector<ui_action_entry> entries_;
        std::vector<bool> selected_;
        ui_tree_model tree_;
        ui_list_selection selection_;
        ui_scroll_model scroll_;
        scrollbar scrollbar_;
        ui_hit_map<int> hits_;
        ui_hit_map<int> expanders_;
        point origin_ = point::zero;
        int width_ = 0;
        int height_ = 0;
        int cursor_ = 0;
        int hovered_ = -1;
        bool multiple_ = true;
        bool activate_on_single_click_ = false;
        bool hierarchical_ = false;
        bool ensure_cursor_on_draw_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_LIST_H
