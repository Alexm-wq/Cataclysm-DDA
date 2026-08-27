#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_TREE_DROPDOWN_H
#define CATA_SRC_UI_HELPERS_CONTROLS_TREE_DROPDOWN_H

#include <algorithm>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../output.h"
#include "../../point.h"
#include "../models/action_entry.h"
#include "../models/scroll_model.h"
#include "../primitive/overlay.h"
#include "../primitive/scrollbar.h"

/** Semantic checkbox state for hierarchical multi-selection. */
enum class ui_tree_check_state : int {
    unchecked,
    partial,
    checked
};

/** One semantic row in a hierarchical dropdown. */
struct ui_tree_dropdown_entry {
    ui_action_entry action;
    int depth = 0;
    std::string parent_id;
    bool expandable = false;
    ui_tree_check_state check_state = ui_tree_check_state::unchecked;
};

/** Visual/layout policy for ui_tree_dropdown. */
struct ui_tree_dropdown_style {
    nc_color border = c_light_cyan;
    nc_color text = c_light_gray;
    nc_color disabled = c_dark_gray;
    nc_color highlight = h_light_cyan;
    nc_color checked = c_light_green;
    nc_color partial = c_yellow;
    nc_color unchecked = c_light_red;
    int indent = 2;
};

/**
 * Scrollable hierarchical dropdown with helper-owned expansion state and
 * tri-state checkbox presentation.
 *
 * The caller supplies the semantic tree every redraw. Expansion/collapse,
 * pointer hit testing, keyboard navigation, scrolling and overlay rendering are
 * retained by the control. Clicking an expander only changes expansion;
 * clicking the rest of a row activates that semantic entry.
 */
class ui_tree_dropdown
{
    public:
        void close() {
            entries_.clear();
            visible_.clear();
            hovered_ = -1;
            pos_ = point::zero;
            width_ = 0;
            height_ = 0;
            parent_width_ = 0;
            parent_height_ = 0;
            scroll_ = ui_scroll_model();
            overlay_.close();
        }

        bool is_open() const {
            return !entries_.empty() && width_ >= 3 && height_ >= 3;
        }

        bool expanded( const std::string &id ) const {
            return expanded_.count( id ) > 0;
        }

        void set_expanded( const std::string &id, const bool value ) {
            if( value ) {
                expanded_.insert( id );
            } else {
                expanded_.erase( id );
            }
            rebuild_visible();
        }

        void collapse_all() {
            expanded_.clear();
            rebuild_visible();
        }

        void configure( const catacurses::window &parent, point pos,
                        std::vector<ui_tree_dropdown_entry> entries,
                        int requested_width = 0,
                        const ui_tree_dropdown_style &style = ui_tree_dropdown_style() ) {
            std::string hovered_id;
            const int previous_scroll = scroll_.viewport_pos();
            if( const ui_tree_dropdown_entry *hovered = entry( hovered_ ) ) {
                hovered_id = hovered->action.id;
            }

            style_ = style;
            entries_ = std::move( entries );
            parent_width_ = getmaxx( parent );
            parent_height_ = getmaxy( parent );
            if( entries_.empty() || parent_width_ < 3 || parent_height_ < 3 ) {
                close();
                return;
            }

            rebuild_visible();
            int widest = 0;
            for( const int index : visible_ ) {
                const ui_tree_dropdown_entry &row = entries_[index];
                const int prefix = std::max( 0, row.depth ) * std::max( 0, style_.indent ) + 7;
                widest = std::max( widest, prefix + utf8_width( row.action.label ) );
            }
            width_ = requested_width > 0 ? requested_width : widest + 2;
            width_ = std::clamp( width_, 3, parent_width_ );
            update_height( previous_scroll );

            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_width_ - width_ ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height_ - height_ ) );
            pos_ = pos;

            hovered_ = -1;
            if( !hovered_id.empty() ) {
                for( const int index : visible_ ) {
                    if( entries_[index].action.id == hovered_id ) {
                        hovered_ = index;
                        ensure_hover_visible();
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
            if( row < 0 || row >= scroll_.viewport_size() ) {
                return std::nullopt;
            }
            const int visible_index = scroll_.viewport_pos() + row;
            return visible_index >= 0 && visible_index < static_cast<int>( visible_.size() ) ?
                   std::optional<int>( visible_[visible_index] ) : std::nullopt;
        }

        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos ? hit_test( *parent_pos ).value_or( -1 ) : -1;
        }

        int hovered_index() const {
            return hovered_;
        }

        const ui_tree_dropdown_entry *entry( const int index ) const {
            return index >= 0 && index < static_cast<int>( entries_.size() ) ? &entries_[index] : nullptr;
        }

        ui_action_result handle_input( const std::string &action,
                                       const std::optional<point> &parent_pos,
                                       const bool close_on_activate = true,
                                       const ui_outside_click_policy outside_click =
                                           ui_outside_click_policy::consume,
                                       const std::optional<inclusive_rectangle<point>> &trigger_bounds =
                                           std::nullopt ) {
            if( !is_open() ) {
                return {};
            }
            const bool inside = parent_pos && contains( *parent_pos );
            const bool passthrough_policy = outside_click == ui_outside_click_policy::passthrough;
            const bool over_trigger = parent_pos && trigger_bounds && trigger_bounds->contains( *parent_pos );
            const bool pass_outside = ui_outside_pointer_passthrough( outside_click, over_trigger );
            if( action == "QUIT" || action == "SEC_SELECT" ) {
                close();
                return { ui_action_result_type::closed, std::nullopt };
            }
            if( action == "MOUSE_MOVE" ) {
                update_hover( parent_pos );
                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action == "CLICK_AND_DRAG" ) {
                if( !inside ) {
                    close();
                    return { ui_action_result_type::closed, std::nullopt, pass_outside };
                }
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
                if( passthrough_policy && !inside ) {
                    close();
                    return { ui_action_result_type::closed, std::nullopt, pass_outside };
                }
                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );
                update_hover( parent_pos );
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( action == "UP" || action == "DOWN" ) {
                if( visible_.empty() ) {
                    return { ui_action_result_type::handled, std::nullopt };
                }
                const int current = visible_position( hovered_ );
                const int direction = action == "UP" ? -1 : 1;
                const int next = current < 0 ? ( direction > 0 ? 0 : static_cast<int>( visible_.size() ) - 1 ) :
                                 std::clamp( current + direction, 0,
                                             static_cast<int>( visible_.size() ) - 1 );
                hovered_ = visible_[next];
                ensure_hover_visible();
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( action == "PAGE_UP" || action == "PAGE_DOWN" ) {
                const int direction = action == "PAGE_UP" ? -1 : 1;
                const int current = visible_position( hovered_ );
                scroll_.page_by( direction );
                if( current >= 0 && !visible_.empty() ) {
                    const int next = std::clamp( current + direction * scroll_.viewport_size(), 0,
                                                static_cast<int>( visible_.size() ) - 1 );
                    hovered_ = visible_[next];
                    ensure_hover_visible();
                }
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( action == "HOME" || action == "END" ) {
                if( !visible_.empty() ) {
                    hovered_ = action == "HOME" ? visible_.front() : visible_.back();
                    ensure_hover_visible();
                }
                return { ui_action_result_type::handled, std::nullopt };
            }
            if( ( action == "LEFT" || action == "RIGHT" ) && hovered_ >= 0 ) {
                const ui_tree_dropdown_entry *row = entry( hovered_ );
                if( row != nullptr && row->expandable ) {
                    const bool want_open = action == "RIGHT";
                    if( expanded( row->action.id ) != want_open ) {
                        set_expanded( row->action.id, want_open );
                    }
                    return { ui_action_result_type::handled, std::nullopt };
                }
            }

            int activated_index = -1;
            if( action == "SELECT" ) {
                if( parent_pos ) {
                    activated_index = hit_test( *parent_pos ).value_or( -1 );
                    if( activated_index >= 0 && expander_hit( activated_index, *parent_pos ) ) {
                        const ui_tree_dropdown_entry *row = entry( activated_index );
                        if( row != nullptr && row->expandable ) {
                            set_expanded( row->action.id, !expanded( row->action.id ) );
                            hovered_ = activated_index;
                            return { ui_action_result_type::handled, std::nullopt };
                        }
                    }
                }
                if( activated_index < 0 ) {
                    close();
                    return { ui_action_result_type::closed, std::nullopt, pass_outside };
                }
            } else if( action == "CONFIRM" ) {
                activated_index = hovered_;
            } else {
                return {};
            }

            const ui_tree_dropdown_entry *selected = entry( activated_index );
            if( selected == nullptr ) {
                return { ui_action_result_type::handled, std::nullopt };
            }
            const ui_action_entry result_entry = selected->action;
            if( !result_entry.enabled ) {
                return { ui_action_result_type::disabled, result_entry };
            }
            if( close_on_activate ) {
                close();
            }
            return { ui_action_result_type::activated, result_entry };
        }

        void draw( const catacurses::window &parent ) {
            if( !is_open() ) {
                overlay_.close();
                return;
            }
            overlay_.configure( parent, pos_, width_, height_ );
            catacurses::window &window = overlay_.begin_draw( parent );
            if( !window ) {
                return;
            }

            draw_border( window, style_.border );
            for( int row_index = 0; row_index < scroll_.viewport_size(); ++row_index ) {
                const int visible_index = scroll_.viewport_pos() + row_index;
                if( visible_index >= static_cast<int>( visible_.size() ) ) {
                    break;
                }
                const int entry_index = visible_[visible_index];
                const ui_tree_dropdown_entry &row = entries_[entry_index];
                nc_color color = state_color( row.check_state );
                if( !row.action.enabled ) {
                    color = style_.disabled;
                } else if( entry_index == hovered_ ) {
                    color = style_.highlight;
                }

                const int indent = std::max( 0, row.depth ) * std::max( 0, style_.indent );
                const std::string expander = row.expandable ?
                                             ( expanded( row.action.id ) ? "-" : "+" ) : " ";
                const char *check = row.check_state == ui_tree_check_state::checked ? "[x]" :
                                    row.check_state == ui_tree_check_state::partial ? "[/]" : "[ ]";
                const std::string label = std::string( indent, ' ' ) + expander + " " + check + " " +
                                          row.action.label;
                trim_and_print( window, point( 1, row_index + 1 ), std::max( 1, width_ - 2 ), color,
                                label );
            }
            if( scroll_.can_scroll() && scroll_.viewport_size() >= 3 ) {
                scrollbar_.offset_x( width_ - 1 ).offset_y( 1 ).model( scroll_ ).apply( window );
            }
            overlay_.refresh();
        }

    private:
        nc_color state_color( const ui_tree_check_state state ) const {
            switch( state ) {
                case ui_tree_check_state::checked:
                    return style_.checked;
                case ui_tree_check_state::partial:
                    return style_.partial;
                case ui_tree_check_state::unchecked:
                default:
                    return style_.unchecked;
            }
        }

        int find_id( const std::string &id ) const {
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                if( entries_[i].action.id == id ) {
                    return i;
                }
            }
            return -1;
        }

        bool row_visible( const int index ) const {
            if( index < 0 || index >= static_cast<int>( entries_.size() ) ) {
                return false;
            }
            const std::string &parent = entries_[index].parent_id;
            if( parent.empty() ) {
                return true;
            }
            const int parent_index = find_id( parent );
            return parent_index >= 0 && expanded( parent ) && row_visible( parent_index );
        }

        void rebuild_visible() {
            visible_.clear();
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                if( row_visible( i ) ) {
                    visible_.push_back( i );
                }
            }
            update_height( scroll_.viewport_pos() );
            if( hovered_ >= 0 && visible_position( hovered_ ) < 0 ) {
                hovered_ = -1;
            }
        }

        void update_height( const int requested_scroll ) {
            if( parent_height_ < 3 ) {
                height_ = 0;
                return;
            }
            height_ = std::min( static_cast<int>( visible_.size() ) + 2, parent_height_ );
            height_ = std::max( 3, height_ );
            scroll_.set_content_size( static_cast<int>( visible_.size() ) )
            .set_viewport_size( height_ - 2 ).set_viewport_pos( requested_scroll );
        }

        int visible_position( const int entry_index ) const {
            const auto found = std::find( visible_.begin(), visible_.end(), entry_index );
            return found == visible_.end() ? -1 : static_cast<int>( found - visible_.begin() );
        }

        void ensure_hover_visible() {
            const int pos = visible_position( hovered_ );
            if( pos >= 0 ) {
                scroll_.ensure_visible( pos );
            }
        }

        bool expander_hit( const int entry_index, const point &parent_pos ) const {
            const ui_tree_dropdown_entry *row = entry( entry_index );
            if( row == nullptr || !row->expandable ) {
                return false;
            }
            const int expander_x = pos_.x + 1 + std::max( 0, row->depth ) *
                                   std::max( 0, style_.indent );
            return parent_pos.x == expander_x;
        }

        ui_overlay overlay_;
        scrollbar scrollbar_;
        std::vector<ui_tree_dropdown_entry> entries_;
        std::vector<int> visible_;
        std::set<std::string> expanded_;
        ui_tree_dropdown_style style_;
        point pos_ = point::zero;
        int width_ = 0;
        int height_ = 0;
        int parent_width_ = 0;
        int parent_height_ = 0;
        int hovered_ = -1;
        ui_scroll_model scroll_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_TREE_DROPDOWN_H
