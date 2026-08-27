from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def function_span(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"missing function {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"missing function brace {signature}")
    depth = 0
    state = "normal"
    escaped = False
    i = brace
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "line":
            if ch == "\n":
                state = "normal"
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "normal"
                i += 1
        elif state == "string":
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                state = "normal"
        elif state == "char":
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                state = "normal"
        else:
            if ch == "/" and nxt == "/":
                state = "line"
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block"
                i += 1
            elif ch == '"':
                state = "string"
            elif ch == "'":
                state = "char"
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return start, i + 1
        i += 1
    raise SystemExit(f"unterminated function {signature}")


def replace_function(text: str, signature: str, replacement: str) -> str:
    start, end = function_span(text, signature)
    return text[:start] + replacement.rstrip() + text[end:]


# ---------------------------------------------------------------------------
# Generic helper extensions needed to preserve the vehicle editor's behavior.
# ---------------------------------------------------------------------------
action_path = Path("src/ui_helpers/controls/action_strip.h")
action = action_path.read_text()
action = replace_once(
    action,
    '''        std::optional<int> hit_test( const point &parent_pos ) const {\n            return hits_.hit( parent_pos );\n        }\n\n        void update_hover''',
    '''        std::optional<int> hit_test( const point &parent_pos ) const {\n            return hits_.hit( parent_pos );\n        }\n\n        std::optional<inclusive_rectangle<point>> bounds( const int index ) const {\n            for( const typename ui_hit_map<int>::hit_region &region : hits_.regions() ) {\n                if( region.target == index ) {\n                    return region.bounds;\n                }\n            }\n            return std::nullopt;\n        }\n\n        std::optional<inclusive_rectangle<point>> bounds_for_id( const std::string &id ) const {\n            for( int index = 0; index < static_cast<int>( items_.size() ); ++index ) {\n                if( items_[index].action.id == id ) {\n                    return bounds( index );\n                }\n            }\n            return std::nullopt;\n        }\n\n        void update_hover''',
    "action strip bounds API"
)
action_path.write_text(action)

dropdown_path = Path("src/ui_helpers/controls/dropdown.h")
dropdown = dropdown_path.read_text()
dropdown = replace_once(
    dropdown,
    '''            if( action == "MOUSE_MOVE" ) {\n                update_hover( parent_pos );\n                return { ui_action_result_type::handled, std::nullopt };\n            }''',
    '''            if( action == "MOUSE_MOVE" ) {\n                update_hover( parent_pos );\n                const bool inside = parent_pos && contains( *parent_pos );\n                return { inside ? ui_action_result_type::handled : ui_action_result_type::ignored,\n                         std::nullopt };\n            }''',
    "dropdown outside-hover semantics"
)
dropdown_path.write_text(dropdown)

# ---------------------------------------------------------------------------
# veh_interact declarations: generic models/controls own UI-only state.
# ---------------------------------------------------------------------------
h_path = Path("src/veh_interact.h")
h = h_path.read_text()
h = replace_once(
    h,
    '''#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/models/multiselect_filter.h"''',
    '''#include "ui_helpers/controls/action_strip.h"\n#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/models/double_click_tracker.h"\n#include "ui_helpers/models/multiselect_filter.h"\n#include "ui_helpers/models/scroll_model.h"\n#include "ui_helpers/primitive/overlay.h"''',
    "veh helper includes"
)
h = replace_once(
    h,
    '''        int selected_part = -1;\n        int part_scroll = 0;\n        int part_detail_scroll = 0;''',
    '''        int selected_part = -1;\n        ui_scroll_model part_scroll;\n        ui_scroll_model part_detail_scroll;''',
    "part scroll models"
)
h = replace_once(
    h,
    '''        struct editor_context_button {\n            std::string label;\n            point pos = point::zero;\n            int width = 0;\n            std::string action;\n            std::string disabled_reason;\n            bool enabled = true;\n        };\n        bool editor_test_mode = false;''',
    '''        bool editor_test_mode = false;''',
    "remove context button struct"
)
h = replace_once(
    h,
    '''        std::vector<editor_context_button> editor_context_buttons;''',
    '''        std::vector<ui_action_entry> editor_context_buttons;''',
    "context action entries"
)
h = replace_once(
    h,
    '''        struct editor_toolbar_button {\n            std::string label;\n            std::string action;\n            point pos = point::zero;\n            int width = 0;\n            bool enabled = true;\n            int group = 0;\n        };\n        std::vector<editor_toolbar_button> editor_toolbar_buttons;\n        int editor_toolbar_hover_button = -1;\n        std::string editor_toolbar_hover_action;''',
    '''        ui_action_strip editor_view_strip;\n        ui_action_strip editor_layer_strip;\n        ui_action_strip editor_toolbar_strip;\n        std::vector<ui_action_strip_item> editor_toolbar_items;\n        std::string editor_toolbar_hover_action;''',
    "toolbar action strip state"
)
h = replace_once(
    h,
    '''        std::vector<editor_context_button> editor_toolbar_dropdown_buttons;''',
    '''        std::vector<ui_action_entry> editor_toolbar_dropdown_buttons;''',
    "toolbar dropdown entries"
)
h = replace_once(
    h,
    '''        catacurses::window w_name;\n        catacurses::window w_refuel_overlay;''',
    '''        catacurses::window w_name;\n        ui_overlay refuel_overlay;''',
    "refuel overlay member"
)
h_path.write_text(h)

cpp_path = Path("src/veh_interact.cpp")
cpp = cpp_path.read_text()

# UI-only nested state uses generic scroll/double-click models.
cpp = replace_once(
    cpp,
    '''    std::map<std::string, bool> materials_available;\n    std::string last_clicked_part;\n    std::optional<std::chrono::steady_clock::time_point> last_click_time;''',
    '''    std::map<std::string, bool> materials_available;\n    ui_double_click_tracker<std::string> double_click;''',
    "install double click"
)
cpp = replace_once(
    cpp,
    '''    int variant_pos = 0;\n    int variant_scroll = 0;\n    std::vector<std::string> variants;\n    std::string committed_variant;\n    int last_clicked_variant = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_click_time;''',
    '''    int variant_pos = 0;\n    ui_scroll_model variant_scroll;\n    std::vector<std::string> variants;\n    std::string committed_variant;\n    ui_double_click_tracker<std::string> double_click;''',
    "reshape UI models"
)
cpp = replace_once(
    cpp,
    '''    int tank_pos = 0;\n    int tank_scroll = 0;\n    int tank_range_anchor = -1;\n    int last_clicked_tank_index = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_tank_click_time;''',
    '''    int tank_pos = 0;\n    ui_scroll_model tank_scroll;\n    int tank_range_anchor = -1;\n    ui_double_click_tracker<int> tank_double_click;''',
    "refuel tank models"
)
cpp = replace_once(
    cpp,
    '''    int source_pos = 0;\n    int source_scroll = 0;\n    int source_range_anchor = -1;\n    // Double-click is a UI-row gesture, not an item_location equivalence test.\n    // Multiple containers in the same cargo source can otherwise compare as the\n    // same effective location and turn two different row clicks into a double-click.\n    int last_clicked_source_index = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_source_click_time;''',
    '''    int source_pos = 0;\n    ui_scroll_model source_scroll;\n    int source_range_anchor = -1;\n    // Double-click remains keyed by the semantic row index.  item_location\n    // equivalence is deliberately not used because different containers can\n    // resolve to the same effective source location.\n    ui_double_click_tracker<int> source_double_click;''',
    "refuel source models"
)
cpp = replace_once(
    cpp,
    '''    std::vector<itype_id> quick_fuels;\n    int quick_fuel_pos = 0;\n    int quick_fuel_scroll = 0;''',
    '''    std::vector<itype_id> quick_fuels;\n    int quick_fuel_pos = 0;\n    ui_scroll_model quick_fuel_scroll;''',
    "quick refuel scroll model"
)

# Resize lifecycle: dropdown/action geometry is rebuilt and refuel is a small
# ui_overlay instead of a manually owned curses window.
cpp = replace_once(
    cpp,
    '''    editor_filter_dropdown_menu.close();\n    editor_context_dropdown_menu.close();\n    editor_toolbar_dropdown_menu.close();''',
    '''    editor_filter_dropdown_menu.close();\n    editor_context_dropdown_menu.close();\n    editor_toolbar_dropdown_menu.close();\n    editor_view_strip.clear();\n    editor_layer_strip.clear();\n    editor_toolbar_strip.clear();''',
    "resize helper reset"
)
cpp = replace_once(
    cpp,
    '''    // Refueling is a short transactional workflow, not a replacement editor.\n    // Keep it as a compact centered modal over the normal vehicle editor.\n    const int refuel_overlay_w = std::min( grid_w, std::clamp( grid_w * 55 / 100, 36, 64 ) );\n    const int refuel_overlay_h = std::min( page_size, std::clamp( page_size - 2, 12, 20 ) );\n    w_refuel_overlay = catacurses::newwin( refuel_overlay_h, refuel_overlay_w,\n                       point( grid.x + std::max( 0, ( grid_w - refuel_overlay_w ) / 2 ),\n                              pane_y + std::max( 0, ( page_size - refuel_overlay_h ) / 2 ) ) );''',
    '''    // Refueling is a short transactional workflow, not a replacement editor.\n    // Use the same small, flicker-safe overlay primitive as dropdowns so Live/Split\n    // remains visible behind the modal without refreshing a black parent slab.\n    const int refuel_overlay_w = std::min( grid_w, std::clamp( grid_w * 55 / 100, 36, 64 ) );\n    const int refuel_overlay_h = std::min( page_size, std::clamp( page_size - 2, 12, 20 ) );\n    refuel_overlay.configure( w_border,\n                              point( grid.x + std::max( 0, ( grid_w - refuel_overlay_w ) / 2 ),\n                                     pane_y + std::max( 0, ( page_size - refuel_overlay_h ) / 2 ) ),\n                              refuel_overlay_w, refuel_overlay_h );''',
    "refuel overlay allocation"
)

# Generic scroll models for inspector and detail panes.
cpp = replace_function(cpp, "void veh_interact::reset_part_selection()", r'''void veh_interact::reset_part_selection()
{
    const std::vector<int> parts = inspector_parts();
    const int previous_part = selected_part;
    selected_part = -1;
    if( previous_part >= 0 && std::find( parts.begin(), parts.end(), previous_part ) != parts.end() ) {
        selected_part = previous_part;
    } else if( cpart >= 0 && std::find( parts.begin(), parts.end(), cpart ) != parts.end() ) {
        selected_part = cpart;
    } else if( !parts.empty() ) {
        selected_part = parts.front();
    }
    part_scroll.scroll_to_start();
    part_detail_scroll.scroll_to_start();
}''')
cpp = replace_function(cpp, "void veh_interact::scroll_part_inspector( const int delta )", r'''void veh_interact::scroll_part_inspector( const int delta )
{
    const std::vector<int> parts = inspector_parts();
    const int visible = std::max( 1, getmaxy( w_parts ) - 3 );
    part_scroll.set_content_size( static_cast<int>( parts.size() ) )
    .set_viewport_size( visible ).scroll_by( delta );
}''')
cpp = replace_function(cpp, "void veh_interact::scroll_part_details( const int delta )", r'''void veh_interact::scroll_part_details( const int delta )
{
    part_detail_scroll.scroll_by( delta );
}''')
cpp = replace_once(
    cpp,
    '''    const int max_scroll = std::max( 0, static_cast<int>( parts.size() ) - visible );\n    part_scroll = std::clamp( part_scroll, 0, max_scroll );''',
    '''    part_scroll.set_content_size( static_cast<int>( parts.size() ) )\n    .set_viewport_size( visible );''',
    "inspector scroll setup"
)
cpp = replace_once(cpp, "        const int idx = part_scroll + row;",
                   "        const int idx = part_scroll.viewport_pos() + row;", "inspector row scroll")
cpp = replace_once(
    cpp,
    '''    if( static_cast<int>( parts.size() ) > visible ) {\n        scrollbar().offset_x( width - 1 ).offset_y( first_row )\n        .content_size( static_cast<int>( parts.size() ) ).viewport_pos( part_scroll )\n        .viewport_size( visible ).apply( w_parts );\n    }''',
    '''    if( part_scroll.can_scroll() ) {\n        scrollbar().offset_x( width - 1 ).offset_y( first_row )\n        .model( part_scroll ).apply( w_parts );\n    }''',
    "inspector scrollbar model"
)
cpp = replace_once(
    cpp,
    '''    const int max_scroll = std::max( 0, static_cast<int>( folded.size() ) - available );\n    part_detail_scroll = std::clamp( part_detail_scroll, 0, max_scroll );\n    fold_and_print_from( w_msg, point( 1, line ), std::max( 1, width - 3 ), part_detail_scroll,\n                         c_light_gray, description );\n    if( max_scroll > 0 ) {\n        scrollbar().offset_x( width - 1 ).offset_y( line )\n        .content_size( static_cast<int>( folded.size() ) ).viewport_pos( part_detail_scroll )\n        .viewport_size( available ).apply( w_msg );\n    }''',
    '''    part_detail_scroll.set_content_size( static_cast<int>( folded.size() ) )\n    .set_viewport_size( available );\n    fold_and_print_from( w_msg, point( 1, line ), std::max( 1, width - 3 ),\n                         part_detail_scroll.viewport_pos(), c_light_gray, description );\n    if( part_detail_scroll.can_scroll() ) {\n        scrollbar().offset_x( width - 1 ).offset_y( line )\n        .model( part_detail_scroll ).apply( w_msg );\n    }''',
    "detail scroll model"
)
cpp = cpp.replace("const int row = part_scroll + parts_pos->y - 3;",
                  "const int row = part_scroll.viewport_pos() + parts_pos->y - 3;")
cpp = cpp.replace("part_detail_scroll = 0;", "part_detail_scroll.scroll_to_start();")

# Install double-click uses the shared semantic tracker.
cpp = replace_once(
    cpp,
    '''                    const auto now = std::chrono::steady_clock::now();\n                    const bool double_click = !clicked_id.empty() &&\n                                              install_info->last_clicked_part == clicked_id &&\n                                              install_info->last_click_time.has_value() &&\n                                              now - *install_info->last_click_time <= std::chrono::milliseconds( 500 );''',
    '''                    const bool double_click = !clicked_id.empty() &&\n                                              install_info->double_click.click( clicked_id );''',
    "install double click detection"
)
cpp = replace_once(
    cpp,
    '''                    if( double_click ) {\n                        install_info->last_clicked_part.clear();\n                        install_info->last_click_time.reset();\n                        confirm_install( here );\n                    } else {\n                        install_info->last_clicked_part = clicked_id;\n                        install_info->last_click_time = now;\n                    }''',
    '''                    if( double_click ) {\n                        confirm_install( here );\n                    } else if( clicked_id.empty() ) {\n                        install_info->double_click.reset();\n                    }''',
    "install double click dispatch"
)

# Reshape free scrolling and double-click gesture move to shared models.
cpp = cpp.replace("reshape_info->variant_scroll = 0;", "reshape_info->variant_scroll.scroll_to_start();")
cpp = cpp.replace("reshape_info->last_clicked_variant = -1;\n    reshape_info->last_click_time.reset();",
                  "reshape_info->double_click.reset();")
cpp = replace_once(
    cpp,
    '''        const int max_scroll = std::max( 0, static_cast<int>( reshape_info->variants.size() ) - visible );\n        reshape_info->variant_scroll = std::clamp( reshape_info->variant_scroll, 0, max_scroll );''',
    '''        reshape_info->variant_scroll.set_content_size(\n            static_cast<int>( reshape_info->variants.size() ) ).set_viewport_size( visible );''',
    "reshape scroll setup"
)
cpp = cpp.replace("const int index = reshape_info->variant_scroll + row;",
                  "const int index = reshape_info->variant_scroll.viewport_pos() + row;")
cpp = replace_once(
    cpp,
    '''            scrollbar().offset_x( width - 1 ).offset_y( first_row )\n            .content_size( static_cast<int>( reshape_info->variants.size() ) )\n            .viewport_pos( reshape_info->variant_scroll ).viewport_size( visible ).apply( w_msg );''',
    '''            scrollbar().offset_x( width - 1 ).offset_y( first_row )\n            .model( reshape_info->variant_scroll ).apply( w_msg );''',
    "reshape scrollbar model"
)
cpp = replace_once(
    cpp,
    '''        const int direction = action == "SCROLL_UP" ? -1 : 1;\n        const int max_scroll = std::max( 0, static_cast<int>( reshape_info->variants.size() ) - visible );\n        reshape_info->variant_scroll = std::clamp( reshape_info->variant_scroll + direction, 0, max_scroll );''',
    '''        const int direction = action == "SCROLL_UP" ? -1 : 1;\n        reshape_info->variant_scroll.set_content_size(\n            static_cast<int>( reshape_info->variants.size() ) ).set_viewport_size( visible )\n        .scroll_by( direction );''',
    "reshape wheel model"
)
cpp = cpp.replace("const int index = reshape_info->variant_scroll + ( pos->y - first_row ) / entry_height;",
                  "const int index = reshape_info->variant_scroll.viewport_pos() + ( pos->y - first_row ) / entry_height;")
cpp = replace_once(
    cpp,
    '''            const auto now = std::chrono::steady_clock::now();\n            const bool double_click = reshape_info->last_clicked_variant == index &&\n                                      reshape_info->last_click_time &&\n                                      now - *reshape_info->last_click_time <= std::chrono::milliseconds( 500 );\n            preview_reshape_variant( index );\n            if( double_click ) {\n                apply_reshape_variant();\n            } else {\n                reshape_info->last_clicked_variant = index;\n                reshape_info->last_click_time = now;\n            }''',
    '''            const bool double_click = reshape_info->double_click.click(\n                                          reshape_info->variants[index] );\n            preview_reshape_variant( index );\n            if( double_click ) {\n                apply_reshape_variant();\n            }''',
    "reshape double click"
)

# Refuel overlay owns the transient window.  Keep a local alias named
# w_refuel_overlay inside the two functions to minimize domain-code churn.
start, end = function_span(cpp, "void veh_interact::display_refuel_pane( map &here )")
func = cpp[start:end]
func = replace_once(
    func,
    '''    if( !refuel_info || !w_refuel_overlay ) {\n        return;\n    }\n\n    werase( w_refuel_overlay );\n    draw_border( w_refuel_overlay, c_light_gray );''',
    '''    if( !refuel_info || !refuel_overlay.is_open() ) {\n        return;\n    }\n\n    catacurses::window &w_refuel_overlay = refuel_overlay.begin_draw( w_border );\n    if( !w_refuel_overlay ) {\n        return;\n    }\n    draw_border( w_refuel_overlay, c_light_gray );''',
    "refuel overlay begin draw"
)
func = func.replace("wnoutrefresh( w_refuel_overlay );", "refuel_overlay.refresh();")
# Tank/source/quick scrolling remains selection-following, but the generic model
# owns clamping and viewport state.
func = replace_once(
    func,
    '''        if( !refuel_info->tanks.empty() ) {\n            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );\n            if( refuel_info->tank_pos < refuel_info->tank_scroll ) {\n                refuel_info->tank_scroll = refuel_info->tank_pos;\n            } else if( refuel_info->tank_pos >= refuel_info->tank_scroll + visible ) {\n                refuel_info->tank_scroll = refuel_info->tank_pos - visible + 1;\n            }\n            refuel_info->tank_scroll = std::clamp( refuel_info->tank_scroll, 0,\n                                       std::max( 0, static_cast<int>( refuel_info->tanks.size() ) - visible ) );\n        }''',
    '''        refuel_info->tank_scroll.set_content_size( static_cast<int>( refuel_info->tanks.size() ) )\n        .set_viewport_size( visible );\n        if( !refuel_info->tanks.empty() ) {\n            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );\n            refuel_info->tank_scroll.ensure_visible( refuel_info->tank_pos );\n        }''',
    "refuel tank scroll setup"
)
func = func.replace("const int slot = refuel_info->tank_scroll + row;",
                    "const int slot = refuel_info->tank_scroll.viewport_pos() + row;")
func = replace_once(
    func,
    '''        if( !refuel_info->sources.empty() ) {\n            refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,\n                                      static_cast<int>( refuel_info->sources.size() ) - 1 );\n            if( refuel_info->source_pos < refuel_info->source_scroll ) {\n                refuel_info->source_scroll = refuel_info->source_pos;\n            } else if( refuel_info->source_pos >= refuel_info->source_scroll + visible ) {\n                refuel_info->source_scroll = refuel_info->source_pos - visible + 1;\n            }\n            refuel_info->source_scroll = std::clamp( refuel_info->source_scroll, 0,\n                                         std::max( 0, static_cast<int>( refuel_info->sources.size() ) - visible ) );\n        }''',
    '''        refuel_info->source_scroll.set_content_size( static_cast<int>( refuel_info->sources.size() ) )\n        .set_viewport_size( visible );\n        if( !refuel_info->sources.empty() ) {\n            refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,\n                                      static_cast<int>( refuel_info->sources.size() ) - 1 );\n            refuel_info->source_scroll.ensure_visible( refuel_info->source_pos );\n        }''',
    "refuel source scroll setup"
)
func = func.replace("const int index = refuel_info->source_scroll + row;",
                    "const int index = refuel_info->source_scroll.viewport_pos() + row;")
func = replace_once(
    func,
    '''        if( !refuel_info->quick_fuels.empty() ) {\n            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,\n                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n            if( refuel_info->quick_fuel_pos < refuel_info->quick_fuel_scroll ) {\n                refuel_info->quick_fuel_scroll = refuel_info->quick_fuel_pos;\n            } else if( refuel_info->quick_fuel_pos >= refuel_info->quick_fuel_scroll + visible ) {\n                refuel_info->quick_fuel_scroll = refuel_info->quick_fuel_pos - visible + 1;\n            }\n        }''',
    '''        refuel_info->quick_fuel_scroll.set_content_size(\n            static_cast<int>( refuel_info->quick_fuels.size() ) ).set_viewport_size( visible );\n        if( !refuel_info->quick_fuels.empty() ) {\n            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,\n                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n            refuel_info->quick_fuel_scroll.ensure_visible( refuel_info->quick_fuel_pos );\n        }''',
    "quick refuel scroll setup"
)
func = func.replace("const int index = refuel_info->quick_fuel_scroll + row;",
                    "const int index = refuel_info->quick_fuel_scroll.viewport_pos() + row;")
cpp = cpp[:start] + func + cpp[end:]

start, end = function_span(cpp, "bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )")
func = cpp[start:end]
func = replace_once(
    func,
    '''    if( !refuel_info ) {\n        return false;\n    }\n\n    // This helper must never consume keyboard actions''',
    '''    if( !refuel_info || !refuel_overlay.window() ) {\n        return false;\n    }\n    const catacurses::window &w_refuel_overlay = refuel_overlay.window();\n\n    // This helper must never consume keyboard actions''',
    "refuel mouse overlay window"
)
func = func.replace("const int slot = refuel_info->tank_scroll + pos->y - first_row;",
                    "const int slot = refuel_info->tank_scroll.viewport_pos() + pos->y - first_row;")
func = func.replace("const int index = refuel_info->source_scroll + pos->y - first_row;",
                    "const int index = refuel_info->source_scroll.viewport_pos() + pos->y - first_row;")
func = func.replace("const int index = refuel_info->quick_fuel_scroll + pos->y - first_row;",
                    "const int index = refuel_info->quick_fuel_scroll.viewport_pos() + pos->y - first_row;")
func = replace_once(
    func,
    '''            const auto now = std::chrono::steady_clock::now();\n            const bool double_click = !ctrl && !shift &&\n                                      refuel_info->last_clicked_tank_index == slot &&\n                                      refuel_info->last_tank_click_time &&\n                                      now - *refuel_info->last_tank_click_time <= std::chrono::milliseconds( 500 );''',
    '''            const bool double_click = !ctrl && !shift &&\n                                      refuel_info->tank_double_click.click( slot );''',
    "refuel tank double click detection"
)
func = replace_once(
    func,
    '''            if( ctrl || shift ) {\n                refuel_info->last_clicked_tank_index = -1;\n                refuel_info->last_tank_click_time.reset();\n            } else if( double_click ) {''',
    '''            if( ctrl || shift ) {\n                refuel_info->tank_double_click.reset();\n            } else if( double_click ) {''',
    "refuel tank modifier reset"
)
func = replace_once(
    func,
    '''                refuel_info->last_clicked_tank_index = -1;\n                refuel_info->last_tank_click_time.reset();\n                refuel_info->stage = refuel_stage::source;''',
    '''                refuel_info->stage = refuel_stage::source;''',
    "refuel tank double click reset"
)
func = replace_once(
    func,
    '''            } else {\n                refuel_info->last_clicked_tank_index = slot;\n                refuel_info->last_tank_click_time = now;\n            }''',
    '''            }''',
    "refuel tank tracker stores internally"
)
func = replace_once(
    func,
    '''            const auto now = std::chrono::steady_clock::now();\n            const bool double_click = !ctrl && !shift &&\n                                      refuel_info->last_clicked_source_index == index &&\n                                      refuel_info->last_source_click_time &&\n                                      now - *refuel_info->last_source_click_time <= std::chrono::milliseconds( 500 );''',
    '''            const bool double_click = !ctrl && !shift &&\n                                      refuel_info->source_double_click.click( index );''',
    "refuel source double click detection"
)
func = replace_once(
    func,
    '''            if( double_click ) {\n                refuel_info->last_clicked_source_index = -1;\n                refuel_info->last_source_click_time.reset();\n                queue_selected_refill_source( here );\n            } else {\n                refuel_info->last_clicked_source_index = index;\n                refuel_info->last_source_click_time = now;\n            }''',
    '''            if( ctrl || shift ) {\n                refuel_info->source_double_click.reset();\n            } else if( double_click ) {\n                queue_selected_refill_source( here );\n            }''',
    "refuel source double click dispatch"
)
func = func.replace("refuel_info->last_clicked_source_index = -1;\n                refuel_info->last_source_click_time.reset();",
                    "refuel_info->source_double_click.reset();")
cpp = cpp[:start] + func + cpp[end:]

# Remaining refuel model resets outside the mouse/render functions.
cpp = cpp.replace("refuel_info->last_clicked_source_index = -1;\n    refuel_info->last_source_click_time.reset();",
                  "refuel_info->source_double_click.reset();")
cpp = cpp.replace("refuel_info->source_scroll = 0;", "refuel_info->source_scroll.scroll_to_start();")
cpp = cpp.replace("refuel_info->quick_fuel_scroll = 0;", "refuel_info->quick_fuel_scroll.scroll_to_start();")
cpp = cpp.replace("refuel_info->last_clicked_tank_index = -1;\n", "refuel_info->tank_double_click.reset();\n")
cpp = cpp.replace("refuel_info->last_tank_click_time.reset();\n", "")
cpp = cpp.replace("refuel_info->last_source_click_time.reset();\n", "")

# Refuel keyboard page size now reads the overlay model rather than a removed window member.
cpp = cpp.replace("getmaxy( w_refuel_overlay ) - 8", "refuel_overlay.height() - 8")

# ---------------------------------------------------------------------------
# Context/dropdown entries and input routing use ui_action_entry/ui_dropdown.
# ---------------------------------------------------------------------------
cpp = replace_once(
    cpp,
    '''        editor_context_buttons.push_back( { label, point::zero, 0, action, disabled_reason, enabled } );''',
    '''        editor_context_buttons.emplace_back( label, action, enabled, false, disabled_reason );''',
    "context entry construction"
)
cpp = cpp.replace("for( const editor_context_button &button : editor_context_buttons )",
                  "for( const ui_action_entry &button : editor_context_buttons )")
cpp = cpp.replace("const editor_context_button *hovered = hovered_index >= 0 &&",
                  "const ui_action_entry *hovered = hovered_index >= 0 &&")
cpp = cpp.replace("hovered->action", "hovered->id")

cpp = replace_function(cpp, "bool veh_interact::handle_editor_context_click( map &here, const point &pos )", r'''bool veh_interact::handle_editor_context_click( map &here, const point &pos )
{
    if( !editor_context_open ) {
        return false;
    }
    const ui_action_result result = editor_context_dropdown_menu.handle_input( "SELECT", pos );
    if( result.type == ui_action_result_type::disabled && result.entry ) {
        msg = result.entry->disabled_reason.empty() ? _( "That action is not available." ) :
              result.entry->disabled_reason;
        return true;
    }
    if( result.type == ui_action_result_type::activated && result.entry ) {
        return run_editor_context_action( here, result.entry->id );
    }
    if( result.type == ui_action_result_type::closed ) {
        close_editor_context_menu();
    }
    return true;
}''')
cpp = replace_function(cpp, "void veh_interact::display_editor_context_menu()", r'''void veh_interact::display_editor_context_menu()
{
    if( !editor_context_open || editor_context_target == editor_context_surface::none ||
        editor_context_width <= 0 || editor_context_height < 3 ) {
        editor_context_dropdown_menu.close();
        return;
    }

    catacurses::window &target = editor_context_target == editor_context_surface::parts ? w_parts : w_disp;
    ui_dropdown_style style;
    style.border = c_light_gray; // right-click menus intentionally keep their gray border
    style.text = c_light_green;
    editor_context_dropdown_menu.configure( target, editor_context_pos, editor_context_buttons,
                                            editor_context_width, style );
    editor_context_dropdown_menu.update_hover( editor_mouse_pos );
    editor_context_dropdown_menu.draw( target );
}''')

# Filter dropdown activation is delegated to ui_dropdown but remains open while
# checkbox values are toggled.
old_filter_block = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        if( const std::optional<int> option = editor_filter_dropdown_menu.hit_test( pos ) ) {\n            toggle_editor_filter( open_editor_dropdown, *option );\n            return true;\n        }\n        if( editor_filter_dropdown_menu.contains( pos ) ) {\n            return true;\n        }\n        // Outside clicks dismiss with click-through semantics.\n        open_editor_dropdown = editor_dropdown::none;\n        editor_filter_dropdown_menu.close();\n        return false;\n    }'''
new_filter_block = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input( "SELECT", pos, false );\n        if( result.type == ui_action_result_type::activated && result.entry ) {\n            toggle_editor_filter( open_editor_dropdown, std::stoi( result.entry->id ) );\n            return true;\n        }\n        if( result.type == ui_action_result_type::closed ) {\n            open_editor_dropdown = editor_dropdown::none;\n            return false;\n        }\n        if( result.consumed() ) {\n            return true;\n        }\n    }'''
cpp = replace_once(cpp, old_filter_block, new_filter_block, "filter dropdown input")
cpp = replace_once(
    cpp,
    '''    if( open_editor_dropdown != editor_dropdown::none && viewport_pos ) {\n        editor_filter_dropdown_menu.update_hover( viewport_pos );\n        if( action == "MOUSE_MOVE" && editor_filter_dropdown_menu.contains( *viewport_pos ) ) {\n            return true;\n        }\n    }''',
    '''    if( open_editor_dropdown != editor_dropdown::none && action == "MOUSE_MOVE" ) {\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input(\n                                          action, viewport_pos, false );\n        if( result.consumed() ) {\n            return true;\n        }\n    }''',
    "filter hover routing"
)

# ---------------------------------------------------------------------------
# Main toolbar: helper owns geometry, hover, selected/open highlighting and hits.
# ---------------------------------------------------------------------------
cpp = replace_function(cpp, "void veh_interact::rebuild_editor_toolbar( const map &here )", r'''void veh_interact::rebuild_editor_toolbar( const map &here )
{
    editor_toolbar_items.clear();
    editor_toolbar_strip.clear();
    const int width = getmaxx( w_mode );
    if( width <= 2 ) {
        return;
    }

    ui_action_strip_style strip_style;
    strip_style.gap = 1;
    strip_style.group_gap = 3;
    const auto finish = [&]() {
        editor_toolbar_strip.configure( w_mode, point( 1, 0 ), editor_toolbar_items,
                                        std::max( 1, width - 2 ), 1, strip_style );
    };

    if( reshape_info ) {
        editor_toolbar_items.push_back( {
            ui_action_entry( _( "Back" ), "QUIT", true ), 4, ui_action_alignment::right
        } );
        finish();
        return;
    }

    struct toolbar_candidate {
        std::string label;
        std::string action;
        int group = 0;
    };
    const auto direct = []( const std::string &label, const std::string &action, const int group ) {
        return toolbar_candidate{ label, action, group };
    };
    const auto menu = []( const std::string &label, const std::string &menu_id, const int group ) {
        return toolbar_candidate{ label, menu_id, group };
    };
    const auto is_menu = []( const toolbar_candidate &entry ) {
        return entry.action.starts_with( "TOOLBAR_MENU_" );
    };
    const auto rendered = [&]( const toolbar_candidate &entry ) {
        return is_menu( entry ) ? string_format( "[ %s ▼ ]", entry.label ) :
               string_format( "[ %s ]", entry.label );
    };

    const toolbar_candidate back = direct( _( "Back" ), "QUIT", 4 );
    const int back_width = utf8_width( rendered( back ) );
    const std::vector<toolbar_candidate> wide = {
        direct( _( "Install" ), "INSTALL", 0 ), direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ), direct( _( "Refuel" ), "REFILL", 0 ),
        menu( _( "Modify" ), "TOOLBAR_MENU_MODIFY", 1 ), direct( _( "Crew" ), "ASSIGN_CREW", 2 ),
        direct( _( "Rename" ), "RENAME", 2 ), menu( _( "More" ), "TOOLBAR_MENU_MORE", 3 )
    };
    const std::vector<toolbar_candidate> medium = {
        direct( _( "Install" ), "INSTALL", 0 ), direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ), direct( _( "Refuel" ), "REFILL", 0 ),
        menu( _( "Modify" ), "TOOLBAR_MENU_MODIFY", 1 ), menu( _( "More" ), "TOOLBAR_MENU_MORE", 2 )
    };
    const std::vector<toolbar_candidate> narrow = {
        direct( _( "Install" ), "INSTALL", 0 ), direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ), menu( _( "Actions" ), "TOOLBAR_MENU_ACTIONS", 1 )
    };
    const std::vector<toolbar_candidate> tiny = { menu( _( "Actions" ), "TOOLBAR_MENU_ACTIONS", 0 ) };

    const auto required_width = [&]( const std::vector<toolbar_candidate> &entries ) {
        int total = 1 + back_width + 1;
        int previous_group = -1;
        for( const toolbar_candidate &entry : entries ) {
            if( previous_group >= 0 ) {
                total += entry.group == previous_group ? 1 : 3;
            }
            total += utf8_width( rendered( entry ) );
            previous_group = entry.group;
        }
        return total + 1;
    };

    const std::vector<toolbar_candidate> *chosen = &tiny;
    if( required_width( wide ) <= width ) {
        chosen = &wide;
    } else if( required_width( medium ) <= width ) {
        chosen = &medium;
    } else if( required_width( narrow ) <= width ) {
        chosen = &narrow;
    }

    for( const toolbar_candidate &entry : *chosen ) {
        const bool menu_button = is_menu( entry );
        const bool enabled = menu_button || editor_toolbar_action_enabled( here, entry.action );
        ui_action_entry action( menu_button ? entry.label + " ▼" : entry.label,
                                entry.action, enabled,
                                menu_button && open_editor_toolbar_dropdown == entry.action );
        editor_toolbar_items.push_back( { std::move( action ), entry.group,
                                          ui_action_alignment::left } );
    }
    editor_toolbar_items.push_back( {
        ui_action_entry( back.label, back.action, true ), back.group, ui_action_alignment::right
    } );
    finish();
}''')

cpp = replace_function(cpp, "void veh_interact::update_editor_toolbar_hover( map &here, const std::optional<point> &pos )", r'''void veh_interact::update_editor_toolbar_hover( map &here, const std::optional<point> &pos )
{
    editor_toolbar_strip.update_hover( pos );
    const ui_action_entry *hovered = editor_toolbar_strip.entry( editor_toolbar_strip.hovered_index() );
    std::string preview_action;
    if( hovered != nullptr && ( hovered->id == "REPAIR" || hovered->id == "REMOVE" ) ) {
        preview_action = hovered->id;
    }

    if( preview_action == editor_toolbar_hover_action ) {
        return;
    }
    const bool had_preview = !editor_toolbar_hover_action.empty();
    editor_toolbar_hover_action = preview_action;
    w_msg_scroll_offset = 0;
    if( preview_action.empty() ) {
        if( had_preview ) {
            msg.reset();
        }
        return;
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return;
    }
    if( preview_action == "REPAIR" ) {
        set_editor_repair_requirements( here, part );
        return;
    }

    const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
    const vpart_info *old_sel_vpart_info = sel_vpart_info;
    can_remove_part( here, selected_part, get_avatar() );
    sel_vehicle_part = old_sel_vehicle_part;
    sel_vpart_info = old_sel_vpart_info;
}''')

# Adapt toolbar menu population and anchoring to shared action entries/strip geometry.
start, end = function_span(cpp, "void veh_interact::open_editor_toolbar_menu( const map &here, const std::string &which )")
func = cpp[start:end]
func = func.replace("editor_toolbar_buttons.begin(), editor_toolbar_buttons.end()",
                    "editor_toolbar_items.begin(), editor_toolbar_items.end()")
func = func.replace("const editor_toolbar_button &button", "const ui_action_strip_item &button")
func = func.replace("!button.action.starts_with( \"TOOLBAR_MENU_\" ) && button.action == action",
                    "!button.action.id.starts_with( \"TOOLBAR_MENU_\" ) && button.action.id == action")
func = func.replace("editor_toolbar_dropdown_buttons.push_back( {\n            entry.label, point::zero, 0, entry.action, std::string(),\n            editor_toolbar_action_enabled( here, entry.action )\n        } );",
                    "editor_toolbar_dropdown_buttons.emplace_back( entry.label, entry.action,\n                editor_toolbar_action_enabled( here, entry.action ) );")
old_anchor = '''    int anchor_x = 1;\n    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {\n        if( button.action == which ) {\n            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );\n            break;\n        }\n    }'''
new_anchor = '''    int anchor_x = 1;\n    if( const auto bounds = editor_toolbar_strip.bounds_for_id( which ) ) {\n        anchor_x = getbegx( w_mode ) + bounds->p_min.x - getbegx( w_border );\n    }'''
func = replace_once(func, old_anchor, new_anchor, "toolbar menu anchor")
cpp = cpp[:start] + func + cpp[end:]

cpp = replace_function(cpp, "bool veh_interact::handle_editor_toolbar_dropdown_mouse( const std::string &action )", r'''bool veh_interact::handle_editor_toolbar_dropdown_mouse( const std::string &action )
{
    if( open_editor_toolbar_dropdown.empty() || !editor_toolbar_dropdown_menu.is_open() ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_border );
    const ui_action_result result = editor_toolbar_dropdown_menu.handle_input( action, pos );
    if( result.type == ui_action_result_type::disabled && result.entry ) {
        msg = result.entry->disabled_reason.empty() ?
              _( "That action is not available for the current selection." ) : result.entry->disabled_reason;
        return true;
    }
    if( result.type == ui_action_result_type::activated && result.entry ) {
        pending_editor_action = result.entry->id;
        close_editor_toolbar_dropdown();
        return false;
    }
    if( result.type == ui_action_result_type::closed ) {
        close_editor_toolbar_dropdown();
        return false;
    }
    return result.consumed();
}''')

cpp = replace_function(cpp, "void veh_interact::display_editor_toolbar_dropdown()", r'''void veh_interact::display_editor_toolbar_dropdown()
{
    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_buttons.empty() ) {
        editor_toolbar_dropdown_menu.close();
        return;
    }

    int anchor_x = editor_toolbar_dropdown_pos.x;
    if( const auto bounds = editor_toolbar_strip.bounds_for_id( open_editor_toolbar_dropdown ) ) {
        anchor_x = getbegx( w_mode ) + bounds->p_min.x - getbegx( w_border );
    }
    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );
    editor_toolbar_dropdown_pos.x = std::clamp( anchor_x, 1, max_x );
    const int desired_y = getbegy( w_disp ) - getbegy( w_border );
    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );
    editor_toolbar_dropdown_pos.y = std::clamp( desired_y, 1, max_y );

    editor_toolbar_dropdown_menu.configure( w_border, editor_toolbar_dropdown_pos,
                                            editor_toolbar_dropdown_buttons,
                                            editor_toolbar_dropdown_width );
    editor_toolbar_dropdown_menu.draw( w_border );
}''')

cpp = replace_function(cpp, "bool veh_interact::handle_editor_toolbar_mouse( map &here, const std::string &action,", r'''bool veh_interact::handle_editor_toolbar_mouse( map &here, const std::string &action,
        const std::optional<point> &pos )
{
    if( title.has_value() && !install_info ) {
        if( !editor_toolbar_hover_action.empty() ) {
            editor_toolbar_hover_action.clear();
        }
        return false;
    }

    rebuild_editor_toolbar( here );
    if( action == "MOUSE_MOVE" || !editor_toolbar_hover_action.empty() ) {
        update_editor_toolbar_hover( here, pos );
        if( action == "MOUSE_MOVE" && pos ) {
            return true;
        }
    }
    if( !pos ) {
        return false;
    }

    if( action == "SEC_SELECT" || action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        return true;
    }
    const ui_action_result result = editor_toolbar_strip.handle_input( action, pos );
    if( result.type == ui_action_result_type::ignored ) {
        return true;
    }
    if( result.type == ui_action_result_type::disabled && result.entry ) {
        const std::string &id = result.entry->id;
        if( id == "REPAIR" && selected_part >= 0 && selected_part < veh->part_count() ) {
            vehicle_part &part = veh->part( selected_part );
            if( !part.removed && part.mount == selected_mount() ) {
                set_editor_repair_requirements( here, part );
            }
        } else if( id == "REMOVE" && selected_part >= 0 && selected_part < veh->part_count() ) {
            const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
            const vpart_info *old_sel_vpart_info = sel_vpart_info;
            can_remove_part( here, selected_part, get_avatar() );
            sel_vehicle_part = old_sel_vehicle_part;
            sel_vpart_info = old_sel_vpart_info;
        }
        return true;
    }
    if( result.type != ui_action_result_type::activated || !result.entry ) {
        return true;
    }

    const std::string &id = result.entry->id;
    if( id.starts_with( "TOOLBAR_MENU_" ) ) {
        close_editor_context_menu();
        open_editor_dropdown = editor_dropdown::none;
        open_editor_toolbar_menu( here, id );
        return pending_editor_action.empty();
    }
    if( id == "REPAIR" ) {
        run_editor_context_action( here, "EDITOR_REPAIR" );
        return true;
    }
    if( id == "REMOVE" ) {
        run_editor_context_action( here, "EDITOR_REMOVE" );
        return true;
    }
    if( id == "QUIT" ) {
        close_editor_context_menu();
        open_editor_dropdown = editor_dropdown::none;
        close_editor_toolbar_dropdown();
    }
    pending_editor_action = id;
    return false;
}''')

cpp = replace_function(cpp, "void veh_interact::display_mode( const map &here )", r'''void veh_interact::display_mode( const map &here )
{
    werase( w_mode );

    if( title.has_value() && !install_info ) {
        close_editor_toolbar_dropdown();
        nc_color title_col = c_light_gray;
        print_colored_text( w_mode, point( 1, 0 ), title_col, title_col, title.value() );
        wnoutrefresh( w_mode );
        return;
    }

    rebuild_editor_toolbar( here );
    editor_toolbar_strip.draw( w_mode );
    wnoutrefresh( w_mode );
    display_editor_toolbar_dropdown();
}''')

# ---------------------------------------------------------------------------
# View and Layer button geometry/hit testing use ui_action_strip.
# ---------------------------------------------------------------------------
cpp = replace_function(cpp, "void veh_interact::display_editor_controls()", r'''void veh_interact::display_editor_controls()
{
    const int width = getmaxx( w_disp );
    if( width <= 2 ) {
        return;
    }

    std::vector<ui_action_strip_item> view_items;
    const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{
            { editor_view_mode::editor, _( "Editor" ) },
            { editor_view_mode::live, _( "Live" ) },
            { editor_view_mode::split, _( "Split" ) }
        }};
    for( int i = 0; i < static_cast<int>( views.size() ); ++i ) {
        view_items.push_back( { ui_action_entry( views[i].second, "VIEW_" + std::to_string( i ), true,
                                                views[i].first == active_editor_view_mode ),
                                0, ui_action_alignment::right } );
    }
    ui_action_strip_style view_style;
    view_style.gap = 1;
    view_style.group_gap = 1;
    editor_view_strip.configure( w_disp, point( 1, 0 ), std::move( view_items ),
                                 std::max( 1, width - 2 ), 1, view_style );
    editor_view_strip.draw( w_disp );

    if( reshape_info ) {
        editor_layer_strip.clear();
        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,
                        _( "Filter: reshapeable parts only" ) );
        return;
    }

    mvwprintz( w_disp, point( 1, 1 ), c_light_gray, _( "Layer: " ) );
    const int layer_x = utf8_width( _( "Layer: " ) ) + 1;
    std::vector<ui_action_entry> layer_entries;
    for( int i = 0; i <= static_cast<int>( editor_layer::roof ); ++i ) {
        const editor_layer layer = static_cast<editor_layer>( i );
        layer_entries.emplace_back( editor_layer_name( layer ), "LAYER_" + std::to_string( i ), true,
                                    layer == active_editor_layer );
    }
    ui_action_strip_style layer_style;
    layer_style.gap = 1;
    layer_style.group_gap = 1;
    editor_layer_strip.configure( w_disp, point( layer_x, 1 ), std::move( layer_entries ),
                                  std::max( 1, width - layer_x - 1 ), 1, layer_style );
    editor_layer_strip.draw( w_disp );

    mvwprintz( w_disp, point( 1, 2 ), c_light_gray, _( "System: " ) );
    int system_x = 0;
    int system_width = 0;
    editor_filter_button_geometry( editor_dropdown::system, system_x, system_width );
    const std::string system_button = string_format( "[ %s ▼ ]", editor_system_filter_summary() );
    if( system_x < width - 1 ) {
        trim_and_print( w_disp, point( system_x, 2 ), std::max( 1, width - system_x - 1 ),
                        open_editor_dropdown == editor_dropdown::system ? h_light_cyan : c_light_cyan,
                        system_button );
    }

    const int condition_label_x = system_x + system_width + 2;
    if( condition_label_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_label_x, 2 ), std::max( 1, width - condition_label_x - 1 ),
                        c_light_gray, _( "Condition: " ) );
    }
    int condition_x = 0;
    int condition_width = 0;
    editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );
    const std::string condition_button = string_format( "[ %s ▼ ]", editor_condition_filter_summary() );
    if( condition_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),
                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,
                        condition_button );
    }

    if( vehicle_editor_test_mode_visible ) {
        const int test_x = condition_x + condition_width + 2;
        const std::string test_label = editor_test_mode ? _( "[x] Test" ) : _( "[ ] Test" );
        if( test_x < width - 1 ) {
            trim_and_print( w_disp, point( test_x, 2 ), std::max( 1, width - test_x - 1 ),
                            editor_test_mode ? h_light_red : c_light_gray, test_label );
        }
    }
}''')

# Keep the filter/test rows identical; only the view/layer hit geometry is delegated.
start, end = function_span(cpp, "bool veh_interact::handle_editor_controls_click( const point &pos )")
old = cpp[start:end]
row2_start = old.find("    if( pos.y == 2 ) {")
filter_start = old.find("    if( open_editor_dropdown != editor_dropdown::none ) {")
if row2_start < 0 or filter_start < 0:
    raise SystemExit("controls click row2/filter blocks not found")
row2_and_filter = old[row2_start:]
# The final filter block was already migrated above in the whole source; recover the
# current version from the same function text after that replacement.
new_controls = r'''bool veh_interact::handle_editor_controls_click( const point &pos )
{
    if( pos.x < 0 || pos.x >= getmaxx( w_disp ) || pos.y < 0 || pos.y >= getmaxy( w_disp ) ) {
        return false;
    }

    if( pos.y == 0 ) {
        const ui_action_result result = editor_view_strip.handle_input( "SELECT", pos );
        if( result.type == ui_action_result_type::activated && result.entry ) {
            const int mode = std::stoi( result.entry->id.substr( 5 ) );
            active_editor_view_mode = static_cast<editor_view_mode>( std::clamp( mode, 0, 2 ) );
            vehicle_editor_view_mode_latched = static_cast<int>( active_editor_view_mode );
            open_editor_dropdown = editor_dropdown::none;
            close_editor_context_menu();
            viewport_dragging = false;
            live_preview_dragging = false;
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            if( active_editor_view_mode != editor_view_mode::live ) {
                ensure_selected_mount_visible();
            }
        }
        return true;
    }

    if( reshape_info && ( pos.y == 1 || pos.y == 2 ) ) {
        return true;
    }

    if( pos.y == 1 ) {
        const ui_action_result result = editor_layer_strip.handle_input( "SELECT", pos );
        if( result.type == ui_action_result_type::activated && result.entry ) {
            const int layer = std::stoi( result.entry->id.substr( 6 ) );
            active_editor_layer = static_cast<editor_layer>( std::clamp( layer, 0,
                                  static_cast<int>( editor_layer::roof ) ) );
            open_editor_dropdown = editor_dropdown::none;
            reset_part_selection();
            if( install_info ) {
                install_info->dirty = true;
            }
        }
        return true;
    }

'''
# Extract the current row2+filter tail from cpp after prior source substitutions.
current_start, current_end = function_span(cpp, "bool veh_interact::handle_editor_controls_click( const point &pos )")
current = cpp[current_start:current_end]
tail_pos = current.find("    if( pos.y == 2 ) {")
if tail_pos < 0:
    raise SystemExit("controls current row2 tail missing")
tail = current[tail_pos:]
cpp = cpp[:current_start] + new_controls + tail + cpp[current_end:]

# Mouse move updates helper hover state for the non-content control rows.
needle = '''    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );\n    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );'''
replacement = needle + '''\n\n    if( action == "MOUSE_MOVE" && viewport_pos ) {\n        if( viewport_pos->y == 0 ) {\n            editor_view_strip.update_hover( viewport_pos );\n        } else if( viewport_pos->y == 1 && !reshape_info ) {\n            editor_layer_strip.update_hover( viewport_pos );\n        }\n    }'''
cpp = replace_once(cpp, needle, replacement, "control hover update")

# Toolbar menu direct-action detection now reads generic strip items.
cpp = cpp.replace("editor_toolbar_buttons", "editor_toolbar_items")
cpp = cpp.replace("editor_toolbar_hover_button >= 0 || ", "")

# Escape closes the helper surface immediately as well as clearing owner state.
cpp = replace_once(
    cpp,
    '''        if( action == "QUIT" && open_editor_dropdown != editor_dropdown::none ) {\n            open_editor_dropdown = editor_dropdown::none;\n            continue;\n        }''',
    '''        if( action == "QUIT" && open_editor_dropdown != editor_dropdown::none ) {\n            open_editor_dropdown = editor_dropdown::none;\n            editor_filter_dropdown_menu.close();\n            continue;\n        }''',
    "filter escape close"
)

# Any remaining obsolete gesture fields indicate an incomplete migration.
for obsolete in [
    "last_clicked_part", "last_click_time", "last_clicked_variant",
    "last_clicked_tank_index", "last_tank_click_time",
    "last_clicked_source_index", "last_source_click_time",
    "editor_context_button", "editor_toolbar_button"
]:
    if obsolete in cpp:
        raise SystemExit(f"obsolete vehicle helper state remains in cpp: {obsolete}")

# Remaining w_refuel_overlay occurrences are allowed only as local aliases in
# display_refuel_pane/handle_refuel_mouse, never as a member/allocation.
if "w_refuel_overlay = catacurses::newwin" in cpp:
    raise SystemExit("manual refuel window allocation remains")

cpp_path.write_text(cpp)

# Header/source shape assertions before the workflow performs git diff checks.
final_h = h_path.read_text()
final_cpp = cpp_path.read_text()
assert "ui_action_strip editor_toolbar_strip" in final_h
assert "ui_overlay refuel_overlay" in final_h
assert "ui_scroll_model part_scroll" in final_h
assert "std::vector<ui_action_entry> editor_context_buttons" in final_h
assert "ui_double_click_tracker<std::string> double_click" in final_cpp
assert "ui_scroll_model variant_scroll" in final_cpp
assert "refuel_overlay.begin_draw" in final_cpp
assert "editor_toolbar_strip.handle_input" in final_cpp
assert "editor_view_strip.handle_input" in final_cpp
