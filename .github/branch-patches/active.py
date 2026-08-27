from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Shared semantic action metadata and transient-control pass-through.
replace_once(
    "src/ui_helpers/models/action_entry.h",
    '''    std::string disabled_reason;\n    std::optional<bool> checked;\n\n    ui_action_entry() = default;\n    ui_action_entry( std::string label, std::string id, const bool enabled = true,\n                     const bool selected = false, std::string disabled_reason = std::string(),\n                     const std::optional<bool> checked = std::nullopt ) :\n        label( std::move( label ) ), id( std::move( id ) ), enabled( enabled ), selected( selected ),\n        disabled_reason( std::move( disabled_reason ) ), checked( checked ) {}\n};\n\nenum class ui_action_result_type : int {\n''',
    '''    std::string disabled_reason;\n    std::optional<bool> checked;\n    // Semantic affordance: this action opens a transient dropdown/menu.\n    bool dropdown = false;\n\n    ui_action_entry() = default;\n    ui_action_entry( std::string label, std::string id, const bool enabled = true,\n                     const bool selected = false, std::string disabled_reason = std::string(),\n                     const std::optional<bool> checked = std::nullopt, const bool dropdown = false ) :\n        label( std::move( label ) ), id( std::move( id ) ), enabled( enabled ), selected( selected ),\n        disabled_reason( std::move( disabled_reason ) ), checked( checked ), dropdown( dropdown ) {}\n};\n\nenum class ui_outside_click_policy : int {\n    consume,\n    passthrough\n};\n\nenum class ui_action_result_type : int {\n''',
    "action dropdown semantic",
)
replace_once(
    "src/ui_helpers/models/action_entry.h",
    '''struct ui_action_result {\n    ui_action_result_type type = ui_action_result_type::ignored;\n    std::optional<ui_action_entry> entry;\n\n    bool consumed() const {\n        return type != ui_action_result_type::ignored;\n    }\n};\n''',
    '''struct ui_action_result {\n    ui_action_result_type type = ui_action_result_type::ignored;\n    std::optional<ui_action_entry> entry;\n    // A transient control may close while allowing this same pointer event to\n    // continue to the list, scrollbar, or action underneath it.\n    bool passthrough = false;\n\n    bool consumed() const {\n        return type != ui_action_result_type::ignored && !passthrough;\n    }\n    bool passes_through() const {\n        return passthrough;\n    }\n};\n''',
    "action passthrough result",
)

# ui_action_strip owns the dropdown marker; callers only say that an action is a dropdown.
replace_once(
    "src/ui_helpers/controls/action_strip.h",
    '''        bool is_visible( const int index ) const {\n            for( const typename ui_hit_map<int>::hit_region &region : hits_.regions() ) {\n                if( region.target == index ) {\n                    return true;\n                }\n            }\n            return false;\n        }\n\n    private:\n        std::string display_label( const ui_action_entry &entry ) const {\n            std::string label = entry.checked.has_value() ?\n                                string_format( *entry.checked ? "[x] %s" : "[ ] %s", entry.label ) :\n                                entry.label;\n            if( style_.decorate ) {\n                label = string_format( "[ %s ]", label );\n            }\n            return label;\n        }\n''',
    '''        bool is_visible( const int index ) const {\n            for( const typename ui_hit_map<int>::hit_region &region : hits_.regions() ) {\n                if( region.target == index ) {\n                    return true;\n                }\n            }\n            return false;\n        }\n\n        static std::string format_label( const ui_action_entry &entry,\n                                         const ui_action_strip_style &style = ui_action_strip_style() ) {\n            std::string label = entry.checked.has_value() ?\n                                string_format( *entry.checked ? "[x] %s" : "[ ] %s", entry.label ) :\n                                entry.label;\n            if( entry.dropdown ) {\n                label += " ▼";\n            }\n            if( style.decorate ) {\n                label = string_format( "[ %s ]", label );\n            }\n            return label;\n        }\n\n    private:\n        std::string display_label( const ui_action_entry &entry ) const {\n            return format_label( entry, style_ );\n        }\n''',
    "action strip dropdown marker",
)

# ui_dropdown owns outside-pointer dismissal semantics, including the initial drag event.
replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''        ui_action_result handle_input( const std::string &action,\n                                       const std::optional<point> &parent_pos,\n                                       const bool close_on_activate = true ) {\n            if( !is_open() ) {\n                return {};\n            }\n            if( action == "QUIT" || action == "SEC_SELECT" ) {\n                close();\n                return { ui_action_result_type::closed, std::nullopt };\n            }\n            if( action == "MOUSE_MOVE" ) {\n                update_hover( parent_pos );\n                const bool inside = parent_pos && contains( *parent_pos );\n                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,\n                         std::nullopt };\n            }\n            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n                update_hover( parent_pos );\n                return { ui_action_result_type::handled, std::nullopt };\n            }\n''',
    '''        ui_action_result handle_input( const std::string &action,\n                                       const std::optional<point> &parent_pos,\n                                       const bool close_on_activate = true,\n                                       const ui_outside_click_policy outside_click =\n                                           ui_outside_click_policy::consume ) {\n            if( !is_open() ) {\n                return {};\n            }\n            const bool inside = parent_pos && contains( *parent_pos );\n            const bool pass_outside = outside_click == ui_outside_click_policy::passthrough;\n            if( action == "QUIT" || action == "SEC_SELECT" ) {\n                close();\n                return { ui_action_result_type::closed, std::nullopt };\n            }\n            if( action == "MOUSE_MOVE" ) {\n                update_hover( parent_pos );\n                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,\n                         std::nullopt };\n            }\n            if( action == "CLICK_AND_DRAG" ) {\n                if( !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, pass_outside };\n                }\n                return { ui_action_result_type::handled, std::nullopt };\n            }\n            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                if( pass_outside && !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, true };\n                }\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n                update_hover( parent_pos );\n                return { ui_action_result_type::handled, std::nullopt };\n            }\n''',
    "dropdown outside-pointer policy",
)
replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''                if( activated_index < 0 ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt };\n                }\n''',
    '''                if( activated_index < 0 ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, pass_outside };\n                }\n''',
    "dropdown SELECT passthrough",
)

# Hierarchical dropdown gets the same invariant.
replace_once(
    "src/ui_helpers/controls/tree_dropdown.h",
    '''        ui_action_result handle_input( const std::string &action,\n                                       const std::optional<point> &parent_pos,\n                                       const bool close_on_activate = true ) {\n            if( !is_open() ) {\n                return {};\n            }\n            if( action == "QUIT" || action == "SEC_SELECT" ) {\n                close();\n                return { ui_action_result_type::closed, std::nullopt };\n            }\n            if( action == "MOUSE_MOVE" ) {\n                update_hover( parent_pos );\n                return { parent_pos && contains( *parent_pos ) ? ui_action_result_type::handled :\n                         ui_action_result_type::ignored, std::nullopt };\n            }\n            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n                update_hover( parent_pos );\n                return { ui_action_result_type::handled, std::nullopt };\n            }\n''',
    '''        ui_action_result handle_input( const std::string &action,\n                                       const std::optional<point> &parent_pos,\n                                       const bool close_on_activate = true,\n                                       const ui_outside_click_policy outside_click =\n                                           ui_outside_click_policy::consume ) {\n            if( !is_open() ) {\n                return {};\n            }\n            const bool inside = parent_pos && contains( *parent_pos );\n            const bool pass_outside = outside_click == ui_outside_click_policy::passthrough;\n            if( action == "QUIT" || action == "SEC_SELECT" ) {\n                close();\n                return { ui_action_result_type::closed, std::nullopt };\n            }\n            if( action == "MOUSE_MOVE" ) {\n                update_hover( parent_pos );\n                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,\n                         std::nullopt };\n            }\n            if( action == "CLICK_AND_DRAG" ) {\n                if( !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, pass_outside };\n                }\n                return { ui_action_result_type::handled, std::nullopt };\n            }\n            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                if( pass_outside && !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, true };\n                }\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n                update_hover( parent_pos );\n                return { ui_action_result_type::handled, std::nullopt };\n            }\n''',
    "tree dropdown outside-pointer policy",
)
replace_once(
    "src/ui_helpers/controls/tree_dropdown.h",
    '''                if( activated_index < 0 ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt };\n                }\n''',
    '''                if( activated_index < 0 ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, pass_outside };\n                }\n''',
    "tree dropdown SELECT passthrough",
)

# Generic compact text field: renderer/hit geometry only.  The caller still owns its value
# and chooses colors/width/labels through configuration.
Path("src/ui_helpers/controls/text_field.h").write_text(r'''#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_TEXT_FIELD_H
#define CATA_SRC_UI_HELPERS_CONTROLS_TEXT_FIELD_H

#include <algorithm>
#include <optional>
#include <string>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../output.h"
#include "../../point.h"

struct ui_text_field_style {
    nc_color label = c_light_gray;
    nc_color border = c_light_cyan;
    nc_color text = c_white;
    nc_color placeholder = c_dark_gray;
    nc_color clear = c_light_red;
    nc_color clear_disabled = c_dark_gray;
};

enum class ui_text_field_hit : int {
    none,
    edit,
    clear
};

class ui_text_field
{
    public:
        void clear() {
            configured_ = false;
            edit_hit_.reset();
            clear_hit_.reset();
        }

        void configure( const catacurses::window &parent, const point &pos, const int requested_width,
                        std::string label, std::string value, std::string placeholder,
                        const bool clearable = true,
                        const ui_text_field_style &style = ui_text_field_style() ) {
            clear();
            const int available = getmaxx( parent ) - pos.x;
            if( available < 4 || pos.y < 0 || pos.y >= getmaxy( parent ) ) {
                return;
            }
            style_ = style;
            pos_ = pos;
            label_ = std::move( label );
            value_ = std::move( value );
            placeholder_ = std::move( placeholder );
            width_ = std::clamp( requested_width, 4, available );
            const int label_width = std::min( utf8_width( label_ ), std::max( 0, width_ - 4 ) );
            field_x_ = pos_.x + label_width;
            field_width_ = std::max( 4, pos_.x + width_ - field_x_ );
            field_width_ = std::min( field_width_, getmaxx( parent ) - field_x_ );
            if( field_width_ < 4 ) {
                return;
            }
            const int clear_width = clearable && field_width_ >= 7 ? 3 : 0;
            const int edit_right = field_x_ + field_width_ - 2 - clear_width;
            edit_hit_ = inclusive_rectangle<point>( point( field_x_, pos_.y ),
                        point( std::max( field_x_, edit_right ), pos_.y ) );
            if( clear_width > 0 ) {
                const int clear_x = field_x_ + field_width_ - 4;
                clear_hit_ = inclusive_rectangle<point>( point( clear_x, pos_.y ),
                             point( clear_x + 2, pos_.y ) );
            }
            configured_ = true;
        }

        void draw( const catacurses::window &parent ) const {
            if( !configured_ ) {
                return;
            }
            trim_and_print( parent, pos_, std::max( 0, field_x_ - pos_.x ), style_.label, label_ );
            mvwputch( parent, point( field_x_, pos_.y ), style_.border, '[' );
            mvwputch( parent, point( field_x_ + field_width_ - 1, pos_.y ), style_.border, ']' );
            const int text_width = std::max( 1, field_width_ - 2 - ( clear_hit_ ? 3 : 0 ) );
            trim_and_print( parent, point( field_x_ + 1, pos_.y ), text_width,
                            value_.empty() ? style_.placeholder : style_.text,
                            value_.empty() ? placeholder_ : value_ );
            if( clear_hit_ ) {
                trim_and_print( parent, clear_hit_->p_min, 3,
                                value_.empty() ? style_.clear_disabled : style_.clear, "[x]" );
            }
        }

        ui_text_field_hit hit_test( const point &parent_pos ) const {
            if( clear_hit_ && clear_hit_->contains( parent_pos ) ) {
                return ui_text_field_hit::clear;
            }
            if( edit_hit_ && edit_hit_->contains( parent_pos ) ) {
                return ui_text_field_hit::edit;
            }
            return ui_text_field_hit::none;
        }

        point edit_start() const {
            return configured_ ? point( field_x_ + 1, pos_.y ) : point::zero;
        }
        int edit_end_x() const {
            return configured_ ? ( clear_hit_ ? clear_hit_->p_min.x - 1 : field_x_ + field_width_ - 2 ) : 0;
        }

    private:
        ui_text_field_style style_;
        point pos_ = point::zero;
        std::string label_;
        std::string value_;
        std::string placeholder_;
        int width_ = 0;
        int field_x_ = 0;
        int field_width_ = 0;
        bool configured_ = false;
        std::optional<inclusive_rectangle<point>> edit_hit_;
        std::optional<inclusive_rectangle<point>> clear_hit_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_TEXT_FIELD_H
''', encoding="utf-8")

# Tests for helper-owned semantic behavior.
replace_once(
    "tests/ui_helpers_test.cpp",
    '''#include "point.h"\n#include "ui_helpers/models/double_click_tracker.h"\n''',
    '''#include "point.h"\n#include "ui_helpers/controls/action_strip.h"\n#include "ui_helpers/models/double_click_tracker.h"\n''',
    "helper test include",
)
replace_once(
    "tests/ui_helpers_test.cpp",
    '''TEST_CASE( "ui_multiselect_filter_supports_explicit_restore", "[ui][ui_helpers]" )\n''',
    '''TEST_CASE( "ui_transient_control_can_close_with_pointer_passthrough", "[ui][ui_helpers]" )\n{\n    const ui_action_result consumed_close{ ui_action_result_type::closed, std::nullopt };\n    const ui_action_result passthrough_close{ ui_action_result_type::closed, std::nullopt, true };\n\n    CHECK( consumed_close.consumed() );\n    CHECK_FALSE( consumed_close.passes_through() );\n    CHECK_FALSE( passthrough_close.consumed() );\n    CHECK( passthrough_close.passes_through() );\n}\n\nTEST_CASE( "ui_action_strip_owns_dropdown_affordance", "[ui][ui_helpers]" )\n{\n    const ui_action_entry plain( "Filter", "FILTER" );\n    const ui_action_entry dropdown( "Filter", "FILTER", true, false, std::string(),\n                                    std::nullopt, true );\n\n    CHECK( ui_action_strip::format_label( plain ) == "[ Filter ]" );\n    CHECK( ui_action_strip::format_label( dropdown ) == "[ Filter ▼ ]" );\n}\n\nTEST_CASE( "ui_multiselect_filter_supports_explicit_restore", "[ui][ui_helpers]" )\n''',
    "helper behavior tests",
)

# Crafting: shared search field, semantic dropdown affordances, top-right Back.
replace_once(
    "src/crafting_gui.cpp",
    '''#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/controls/tree_dropdown.h"\n''',
    '''#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/controls/text_field.h"\n#include "ui_helpers/controls/tree_dropdown.h"\n''',
    "crafting text field include",
)
replace_once(
    "src/crafting_gui.cpp",
    '''    inclusive_rectangle<point> search_hit;\n    inclusive_rectangle<point> search_clear_hit;\n    point search_edit_start;\n    int search_edit_end = 0;\n''',
    '''    ui_text_field search_field;\n''',
    "crafting shared search state",
)
replace_once(
    "src/crafting_gui.cpp",
    '''        std::vector<ui_action_entry> header_entries = {\n            { category_summary(), "HEADER_CATEGORIES", true, state.open_header_menu == "CATEGORIES" },\n            { filter_summary(), "HEADER_FILTER", true, state.open_header_menu == "FILTER" },\n            { sort_summary(), "HEADER_SORT", true, state.open_header_menu == "SORT" },\n            { scope_summary(), "HEADER_VIEW", true, state.open_header_menu == "VIEW" }\n        };\n        header_actions.configure( w_header, point( 2, 1 ), std::move( header_entries ),\n                                  std::max( 1, browser_width - 4 ), 2 );\n        header_actions.draw( w_header );\n\n        const int search_y = 3;\n        const int search_x = 2;\n        const int search_width = std::max( 16, browser_width - 4 );\n        const std::string search_label = _( "Search: " );\n        mvwprintz( w_header, point( search_x, search_y ), c_light_gray, "%s", search_label );\n        const int field_x = search_x + utf8_width( search_label );\n        const int field_width = std::max( 8, search_width - utf8_width( search_label ) );\n        mvwputch( w_header, point( field_x, search_y ), c_light_cyan, '[' );\n        mvwputch( w_header, point( field_x + field_width - 1, search_y ), c_light_cyan, ']' );\n        const bool has_search = !state.search_query.empty();\n        const std::string shown_search = has_search ? state.search_query : _( "Search recipes…" );\n        trim_and_print( w_header, point( field_x + 1, search_y ), std::max( 1, field_width - 5 ),\n                        has_search ? c_white : c_dark_gray, shown_search );\n        trim_and_print( w_header, point( field_x + field_width - 4, search_y ), 3,\n                        has_search ? c_light_red : c_dark_gray, "[x]" );\n        search_hit = inclusive_rectangle<point>( point( field_x, search_y ),\n                     point( field_x + field_width - 5, search_y ) );\n        search_clear_hit = inclusive_rectangle<point>( point( field_x + field_width - 4, search_y ),\n                           point( field_x + field_width - 2, search_y ) );\n        search_edit_start = point( field_x + 1, search_y );\n        search_edit_end = field_x + field_width - 5;\n''',
    '''        std::vector<ui_action_strip_item> header_items = {\n            { ui_action_entry( category_summary(), "HEADER_CATEGORIES", true,\n                               state.open_header_menu == "CATEGORIES", std::string(), std::nullopt, true ),\n              0, ui_action_alignment::left },\n            { ui_action_entry( filter_summary(), "HEADER_FILTER", true,\n                               state.open_header_menu == "FILTER", std::string(), std::nullopt, true ),\n              0, ui_action_alignment::left },\n            { ui_action_entry( sort_summary(), "HEADER_SORT", true,\n                               state.open_header_menu == "SORT", std::string(), std::nullopt, true ),\n              0, ui_action_alignment::left },\n            { ui_action_entry( scope_summary(), "HEADER_VIEW", true,\n                               state.open_header_menu == "VIEW", std::string(), std::nullopt, true ),\n              0, ui_action_alignment::left },\n            { ui_action_entry( _( "Back" ), "HEADER_BACK" ), 1, ui_action_alignment::right }\n        };\n        header_actions.configure( w_header, point( 2, 1 ), std::move( header_items ),\n                                  std::max( 1, browser_width - 4 ), 2 );\n        header_actions.draw( w_header );\n\n        const int search_width = std::min( browser_width - 4,\n                                           std::clamp( browser_width / 3, 28, 48 ) );\n        search_field.configure( w_header, point( 2, 3 ), search_width, _( "Search: " ),\n                                state.search_query, _( "Search recipes…" ) );\n        search_field.draw( w_header );\n''',
    "crafting helper-driven header",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            { _( "Compare" ), "COMPARE", normal_recipe, false,\n              _( "Choose a concrete recipe first." ) },\n            { _( "Back" ), "QUIT" }\n        };\n''',
    '''            { _( "Compare" ), "COMPARE", normal_recipe, false,\n              _( "Choose a concrete recipe first." ) }\n        };\n''',
    "crafting remove bottom Back",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            const ui_action_result result = category_menu.handle_input( action, screen_pos, false );\n''',
    '''            const ui_action_result result = category_menu.handle_input(\n                                                action, screen_pos, false,\n                                                ui_outside_click_policy::passthrough );\n''',
    "crafting category passthrough",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            if( result.type == ui_action_result_type::closed ) {\n                state.open_header_menu.clear();\n                continue;\n            }\n            if( result.consumed() ) {\n                continue;\n            }\n        } else if( !state.open_header_menu.empty() ) {\n''',
    '''            if( result.type == ui_action_result_type::closed ) {\n                state.open_header_menu.clear();\n                if( !result.passes_through() ) {\n                    continue;\n                }\n            }\n            if( result.consumed() ) {\n                continue;\n            }\n        } else if( !state.open_header_menu.empty() ) {\n''',
    "crafting category dismissal",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            const ui_action_result result = header_menu.handle_input( action, screen_pos, !keep_open );\n''',
    '''            const ui_action_result result = header_menu.handle_input(\n                                                action, screen_pos, !keep_open,\n                                                ui_outside_click_policy::passthrough );\n''',
    "crafting header passthrough",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            if( result.type == ui_action_result_type::closed ) {\n                state.open_header_menu.clear();\n                continue;\n            }\n            if( result.consumed() ) {\n                continue;\n            }\n        }\n\n        if( state.context_open ) {\n''',
    '''            if( result.type == ui_action_result_type::closed ) {\n                state.open_header_menu.clear();\n                if( !result.passes_through() ) {\n                    continue;\n                }\n            }\n            if( result.consumed() ) {\n                continue;\n            }\n        }\n\n        if( state.context_open ) {\n''',
    "crafting header dismissal",
)
replace_once(
    "src/crafting_gui.cpp",
    '''                    const std::string requested = id == "HEADER_CATEGORIES" ? "CATEGORIES" :\n                                                  id == "HEADER_FILTER" ? "FILTER" :\n                                                  id == "HEADER_SORT" ? "SORT" :\n                                                  id == "HEADER_VIEW" ? "VIEW" : "";\n                    if( !requested.empty() ) {\n                        state.open_header_menu = state.open_header_menu == requested ? std::string() : requested;\n                        category_menu.close();\n                        header_menu.close();\n                        state.context_open = false;\n                        context_menu.close();\n                    }\n''',
    '''                    if( id == "HEADER_BACK" ) {\n                        action = "QUIT";\n                        state.open_header_menu.clear();\n                        category_menu.close();\n                        header_menu.close();\n                    } else {\n                        const std::string requested = id == "HEADER_CATEGORIES" ? "CATEGORIES" :\n                                                      id == "HEADER_FILTER" ? "FILTER" :\n                                                      id == "HEADER_SORT" ? "SORT" :\n                                                      id == "HEADER_VIEW" ? "VIEW" : "";\n                        if( !requested.empty() ) {\n                            state.open_header_menu = state.open_header_menu == requested ? std::string() : requested;\n                            category_menu.close();\n                            header_menu.close();\n                            state.context_open = false;\n                            context_menu.close();\n                        }\n                    }\n''',
    "crafting top-right back",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            if( !handled && header_pos && search_clear_hit.contains( *header_pos ) ) {\n                action = "RESET_FILTER";\n                handled = true;\n            } else if( !handled && header_pos && search_hit.contains( *header_pos ) ) {\n                action = "FILTER";\n                handled = true;\n            }\n''',
    '''            if( !handled && header_pos ) {\n                const ui_text_field_hit search_target = search_field.hit_test( *header_pos );\n                if( search_target == ui_text_field_hit::clear ) {\n                    action = "RESET_FILTER";\n                    handled = true;\n                } else if( search_target == ui_text_field_hit::edit ) {\n                    action = "FILTER";\n                    handled = true;\n                }\n            }\n''',
    "crafting shared search hit test",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            popup.window( w_header, search_edit_start, search_edit_end )\n''',
    '''            popup.window( w_header, search_field.edit_start(), search_field.edit_end_x() )\n''',
    "crafting shared search edit geometry",
)

# Vehicle: remaining generic filter controls become ui_action_strip semantics.
replace_once(
    "src/veh_interact.h",
    '''        ui_action_strip editor_view_strip;\n        ui_action_strip editor_layer_strip;\n        ui_action_strip editor_toolbar_strip;\n''',
    '''        ui_action_strip editor_view_strip;\n        ui_action_strip editor_layer_strip;\n        ui_action_strip editor_filter_strip;\n        ui_action_strip editor_toolbar_strip;\n''',
    "vehicle filter strip member",
)
replace_once(
    "src/veh_interact.h",
    '''        void editor_filter_button_geometry( editor_dropdown which, int &x, int &width ) const;\n        void editor_dropdown_geometry( editor_dropdown which, int &x, int &y, int &width, int &height ) const;\n''',
    '''''',
    "vehicle manual filter geometry declarations",
)

vp = Path("src/veh_interact.cpp")
text = vp.read_text(encoding="utf-8")
start = text.find("void veh_interact::editor_filter_button_geometry(")
end = text.find("int veh_interact::editor_part_symbol(", start)
if start < 0 or end < 0:
    raise SystemExit("vehicle manual filter geometry block not found")
vp.write_text(text[:start] + text[end:], encoding="utf-8")

replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info ) {\n        editor_layer_strip.clear();\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,\n                        _( "Filter: reshapeable parts only" ) );\n        return;\n    }\n''',
    '''    if( reshape_info ) {\n        editor_layer_strip.clear();\n        editor_filter_strip.clear();\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,\n                        _( "Filter: reshapeable parts only" ) );\n        return;\n    }\n''',
    "vehicle reshape clears filter strip",
)
old = '''    mvwprintz( w_disp, point( 1, 2 ), c_light_gray, _( "System: " ) );\n    int system_x = 0;\n    int system_width = 0;\n    editor_filter_button_geometry( editor_dropdown::system, system_x, system_width );\n    const std::string system_button = string_format( "[ %s ▼ ]", editor_system_filter_summary() );\n    if( system_x < width - 1 ) {\n        trim_and_print( w_disp, point( system_x, 2 ), std::max( 1, width - system_x - 1 ),\n                        open_editor_dropdown == editor_dropdown::system ? h_light_cyan : c_light_cyan,\n                        system_button );\n    }\n\n    const int condition_label_x = system_x + system_width + 2;\n    if( condition_label_x < width - 1 ) {\n        trim_and_print( w_disp, point( condition_label_x, 2 ), std::max( 1, width - condition_label_x - 1 ),\n                        c_light_gray, _( "Condition: " ) );\n    }\n    int condition_x = 0;\n    int condition_width = 0;\n    editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );\n    const std::string condition_button = string_format( "[ %s ▼ ]", editor_condition_filter_summary() );\n    if( condition_x < width - 1 ) {\n        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),\n                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,\n                        condition_button );\n    }\n\n    if( vehicle_editor_test_mode_visible ) {\n        const int test_x = condition_x + condition_width + 2;\n        const std::string test_label = editor_test_mode ? _( "[x] Test" ) : _( "[ ] Test" );\n        if( test_x < width - 1 ) {\n            trim_and_print( w_disp, point( test_x, 2 ), std::max( 1, width - test_x - 1 ),\n                            editor_test_mode ? h_light_red : c_light_gray, test_label );\n        }\n    }\n'''
new = '''    std::vector<ui_action_strip_item> filter_items = {\n        { ui_action_entry( string_format( _( "System: %s" ), editor_system_filter_summary() ),\n                           "FILTER_SYSTEM", true, open_editor_dropdown == editor_dropdown::system,\n                           std::string(), std::nullopt, true ), 0, ui_action_alignment::left },\n        { ui_action_entry( string_format( _( "Condition: %s" ), editor_condition_filter_summary() ),\n                           "FILTER_CONDITION", true, open_editor_dropdown == editor_dropdown::condition,\n                           std::string(), std::nullopt, true ), 0, ui_action_alignment::left }\n    };\n    if( vehicle_editor_test_mode_visible ) {\n        filter_items.push_back( { ui_action_entry( _( "Test" ), "FILTER_TEST", true, editor_test_mode ),\n                                  1, ui_action_alignment::left } );\n    }\n    ui_action_strip_style filter_style;\n    filter_style.gap = 1;\n    filter_style.group_gap = 2;\n    editor_filter_strip.configure( w_disp, point( 1, 2 ), std::move( filter_items ),\n                                   std::max( 1, width - 2 ), 1, filter_style );\n    editor_filter_strip.draw( w_disp );\n'''
replace_once("src/veh_interact.cpp", old, new, "vehicle helper filter drawing")

old = '''    if( pos.y == 2 ) {\n        for( const editor_dropdown which : { editor_dropdown::system, editor_dropdown::condition } ) {\n            int x = 0;\n            int width = 0;\n            editor_filter_button_geometry( which, x, width );\n            if( pos.x >= x && pos.x < x + width ) {\n                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;\n                close_editor_context_menu();\n                close_editor_toolbar_dropdown();\n                return true;\n            }\n        }\n        if( vehicle_editor_test_mode_visible ) {\n            int condition_x = 0;\n            int condition_width = 0;\n            editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );\n            const int test_x = condition_x + condition_width + 2;\n            const int test_width = utf8_width( _( "[ ] Test" ) );\n            if( pos.x >= test_x && pos.x < test_x + test_width ) {\n                editor_test_mode = !editor_test_mode;\n                vehicle_editor_test_mode_latched = editor_test_mode;\n                open_editor_dropdown = editor_dropdown::none;\n                close_editor_context_menu();\n                if( install_info ) {\n                    install_info->materials_available.clear();\n                    install_info->dirty = true;\n                }\n                msg = editor_test_mode ?\n                      _( "Test mode enabled: components, tools, and skill requirements are ignored; vehicle legality still applies." ) :\n                      _( "Test mode disabled." );\n                return true;\n            }\n        }\n        return true;\n    }\n\n    if( open_editor_dropdown != editor_dropdown::none ) {\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input( "SELECT", pos, false );\n        if( result.type == ui_action_result_type::activated && result.entry ) {\n            toggle_editor_filter( open_editor_dropdown, std::stoi( result.entry->id ) );\n            return true;\n        }\n        if( result.type == ui_action_result_type::closed ) {\n            open_editor_dropdown = editor_dropdown::none;\n            return false;\n        }\n        if( result.consumed() ) {\n            return true;\n        }\n    }\n\n    return pos.y < editor_viewport_top();\n'''
new = '''    if( pos.y == 2 ) {\n        const ui_action_result result = editor_filter_strip.handle_input( "SELECT", pos );\n        if( result.type == ui_action_result_type::activated && result.entry ) {\n            if( result.entry->id == "FILTER_SYSTEM" || result.entry->id == "FILTER_CONDITION" ) {\n                const editor_dropdown requested = result.entry->id == "FILTER_SYSTEM" ?\n                                                  editor_dropdown::system : editor_dropdown::condition;\n                open_editor_dropdown = open_editor_dropdown == requested ? editor_dropdown::none : requested;\n                close_editor_context_menu();\n                close_editor_toolbar_dropdown();\n                return true;\n            }\n            if( result.entry->id == "FILTER_TEST" ) {\n                editor_test_mode = !editor_test_mode;\n                vehicle_editor_test_mode_latched = editor_test_mode;\n                open_editor_dropdown = editor_dropdown::none;\n                close_editor_context_menu();\n                if( install_info ) {\n                    install_info->materials_available.clear();\n                    install_info->dirty = true;\n                }\n                msg = editor_test_mode ?\n                      _( "Test mode enabled: components, tools, and skill requirements are ignored; vehicle legality still applies." ) :\n                      _( "Test mode disabled." );\n                return true;\n            }\n        }\n        return true;\n    }\n\n    return pos.y < editor_viewport_top();\n'''
replace_once("src/veh_interact.cpp", old, new, "vehicle helper filter clicks")

# Replace filter dropdown geometry with helper-owned anchor/auto-size/scrolling.
path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")
start = text.find("void veh_interact::display_editor_filter_dropdown()\n{")
end = text.find("\n/**\n * Draws the primary vehicle editor viewport.", start)
if start < 0 or end < 0:
    raise SystemExit("vehicle filter dropdown function not found")
replacement = r'''void veh_interact::display_editor_filter_dropdown()
{
    if( reshape_info || open_editor_dropdown == editor_dropdown::none ) {
        editor_filter_dropdown_menu.close();
        return;
    }

    std::vector<ui_dropdown_entry> entries;
    if( open_editor_dropdown == editor_dropdown::system ) {
        for( int i = 0; i <= static_cast<int>( editor_system_filter::other ); ++i ) {
            const editor_system_filter filter = static_cast<editor_system_filter>( i );
            const bool checked = filter == editor_system_filter::all ?
                                 active_system_filters.all_selected() : active_system_filters.contains( filter );
            ui_dropdown_entry entry;
            entry.id = std::to_string( i );
            entry.label = filter == editor_system_filter::all ? _( "All" ) : editor_system_name( filter );
            entry.checked = checked;
            entries.push_back( std::move( entry ) );
        }
    } else {
        for( int i = 0; i <= static_cast<int>( editor_condition_filter::replacement ); ++i ) {
            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );
            const bool checked = filter == editor_condition_filter::all ?
                                 active_condition_filters.all_selected() : active_condition_filters.contains( filter );
            ui_dropdown_entry entry;
            entry.id = std::to_string( i );
            entry.label = filter == editor_condition_filter::all ? _( "All" ) : editor_condition_name( filter );
            entry.checked = checked;
            entries.push_back( std::move( entry ) );
        }
    }

    const std::string anchor_id = open_editor_dropdown == editor_dropdown::system ?
                                  "FILTER_SYSTEM" : "FILTER_CONDITION";
    point pos( 1, editor_viewport_top() );
    if( const auto bounds = editor_filter_strip.bounds_for_id( anchor_id ) ) {
        pos.x = bounds->p_min.x;
    }
    editor_filter_dropdown_menu.configure( w_disp, pos, std::move( entries ) );
    editor_filter_dropdown_menu.draw( w_disp );
}
'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

# Hover for the vehicle filter strip is helper-owned too.
replace_once(
    "src/veh_interact.cpp",
    '''        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info ?\n                                         viewport_pos : std::nullopt );\n    }\n''',
    '''        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info ?\n                                         viewport_pos : std::nullopt );\n        editor_filter_strip.update_hover( viewport_pos && viewport_pos->y == 2 && !reshape_info ?\n                                          viewport_pos : std::nullopt );\n    }\n''',
    "vehicle filter hover",
)

# Route open vehicle dropdowns before shared scrollbars.  Helper decides whether the event
# is consumed or passed through to the scrollbar/list underneath.
replace_once(
    "src/veh_interact.cpp",
    '''    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n            return true;\n        }\n''',
    '''    if( open_editor_dropdown != editor_dropdown::none && editor_filter_dropdown_menu.is_open() ) {\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input(\n                                          action, viewport_pos, false,\n                                          ui_outside_click_policy::passthrough );\n        if( result.type == ui_action_result_type::activated && result.entry ) {\n            toggle_editor_filter( open_editor_dropdown, std::stoi( result.entry->id ) );\n            return true;\n        }\n        if( result.type == ui_action_result_type::closed ) {\n            open_editor_dropdown = editor_dropdown::none;\n            if( !result.passes_through() ) {\n                return true;\n            }\n        } else if( result.consumed() ) {\n            return true;\n        }\n    }\n\n    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n            return true;\n        }\n''',
    "vehicle dropdown before scrollbars",
)
# The old filter MOUSE_MOVE block is redundant after the shared pre-router.
replace_once(
    "src/veh_interact.cpp",
    '''    if( open_editor_dropdown != editor_dropdown::none && action == "MOUSE_MOVE" ) {\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input(\n                                          action, viewport_pos, false );\n        if( result.consumed() ) {\n            return true;\n        }\n    }\n\n''',
    '''''',
    "remove old vehicle filter hover routing",
)
# The post-control manual click-through block is no longer needed; helper already closed/passed it.
replace_once(
    "src/veh_interact.cpp",
    '''        if( open_editor_dropdown != editor_dropdown::none ) {\n            open_editor_dropdown = editor_dropdown::none;\n            const bool click_selects_schematic = over_schematic_content;\n            const bool click_selects_part = !install_info && parts_pos && parts_pos->y >= 3;\n            if( !click_selects_schematic && !click_selects_part ) {\n                return true;\n            }\n            // Selection targets get click-through semantics: dismiss the open\n            // dropdown and apply this same left click to the tile/part below it.\n        }\n''',
    '''''',
    "remove vehicle manual filter clickthrough",
)

# Vehicle toolbar dropdown markers use the same semantic action-strip formatting.
replace_once(
    "src/veh_interact.cpp",
    '''    const auto rendered = [&]( const toolbar_candidate &entry ) {\n        return is_menu( entry ) ? string_format( "[ %s ▼ ]", entry.label ) :\n               string_format( "[ %s ]", entry.label );\n    };\n''',
    '''    const auto rendered = [&]( const toolbar_candidate &entry ) {\n        return ui_action_strip::format_label(\n                   ui_action_entry( entry.label, entry.action, true, false, std::string(),\n                                    std::nullopt, is_menu( entry ) ) );\n    };\n''',
    "vehicle toolbar helper label sizing",
)
replace_once(
    "src/veh_interact.cpp",
    '''        ui_action_entry action( menu_button ? entry.label + " ▼" : entry.label,\n                                entry.action, enabled,\n                                menu_button && open_editor_toolbar_dropdown == entry.action );\n''',
    '''        ui_action_entry action( entry.label, entry.action, enabled,\n                                menu_button && open_editor_toolbar_dropdown == entry.action,\n                                std::string(), std::nullopt, menu_button );\n''',
    "vehicle toolbar semantic dropdown",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Move crafting and vehicle UI behavior into shared helpers\n", encoding="utf-8"
)
