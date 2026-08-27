from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Generic dropdowns may know the trigger rectangle that opened them.  Outside pointer
# dismissal passes through everywhere except that trigger, where the click means close-only.
replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''#include "../../color.h"\n#include "../../cursesdef.h"\n''',
    '''#include "../../color.h"\n#include "../../cuboid_rectangle.h"\n#include "../../cursesdef.h"\n''',
    "dropdown trigger rectangle include",
)
replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''                                       const bool close_on_activate = true,\n                                       const ui_outside_click_policy outside_click =\n                                           ui_outside_click_policy::consume ) {\n            if( !is_open() ) {\n                return {};\n            }\n            const bool inside = parent_pos && contains( *parent_pos );\n            const bool pass_outside = outside_click == ui_outside_click_policy::passthrough;\n''',
    '''                                       const bool close_on_activate = true,\n                                       const ui_outside_click_policy outside_click =\n                                           ui_outside_click_policy::consume,\n                                       const std::optional<inclusive_rectangle<point>> &trigger_bounds =\n                                           std::nullopt ) {\n            if( !is_open() ) {\n                return {};\n            }\n            const bool inside = parent_pos && contains( *parent_pos );\n            const bool passthrough_policy = outside_click == ui_outside_click_policy::passthrough;\n            const bool over_trigger = parent_pos && trigger_bounds && trigger_bounds->contains( *parent_pos );\n            const bool pass_outside = passthrough_policy && !over_trigger;\n''',
    "dropdown trigger-aware policy signature",
)
replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                if( pass_outside && !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, true };\n                }\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n''',
    '''            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                if( passthrough_policy && !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, pass_outside };\n                }\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n''',
    "dropdown trigger-aware wheel dismissal",
)

replace_once(
    "src/ui_helpers/controls/tree_dropdown.h",
    '''#include "../../color.h"\n#include "../../cursesdef.h"\n''',
    '''#include "../../color.h"\n#include "../../cuboid_rectangle.h"\n#include "../../cursesdef.h"\n''',
    "tree dropdown trigger rectangle include",
)
replace_once(
    "src/ui_helpers/controls/tree_dropdown.h",
    '''                                       const bool close_on_activate = true,\n                                       const ui_outside_click_policy outside_click =\n                                           ui_outside_click_policy::consume ) {\n            if( !is_open() ) {\n                return {};\n            }\n            const bool inside = parent_pos && contains( *parent_pos );\n            const bool pass_outside = outside_click == ui_outside_click_policy::passthrough;\n''',
    '''                                       const bool close_on_activate = true,\n                                       const ui_outside_click_policy outside_click =\n                                           ui_outside_click_policy::consume,\n                                       const std::optional<inclusive_rectangle<point>> &trigger_bounds =\n                                           std::nullopt ) {\n            if( !is_open() ) {\n                return {};\n            }\n            const bool inside = parent_pos && contains( *parent_pos );\n            const bool passthrough_policy = outside_click == ui_outside_click_policy::passthrough;\n            const bool over_trigger = parent_pos && trigger_bounds && trigger_bounds->contains( *parent_pos );\n            const bool pass_outside = passthrough_policy && !over_trigger;\n''',
    "tree dropdown trigger-aware policy signature",
)
replace_once(
    "src/ui_helpers/controls/tree_dropdown.h",
    '''            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                if( pass_outside && !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, true };\n                }\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n''',
    '''            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n                if( passthrough_policy && !inside ) {\n                    close();\n                    return { ui_action_result_type::closed, std::nullopt, pass_outside };\n                }\n                scroll_.scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n''',
    "tree dropdown trigger-aware wheel dismissal",
)

# Crafting supplies only the trigger geometry; the dropdown helper decides close vs pass-through.
replace_once(
    "src/crafting_gui.cpp",
    '''        const std::optional<point> actions_pos = local_mouse( w_actions );\n\n        if( state.open_header_menu == "CATEGORIES" ) {\n''',
    '''        const std::optional<point> actions_pos = local_mouse( w_actions );\n        const auto header_trigger_bounds = [&]( const std::string & id )\n        -> std::optional<inclusive_rectangle<point>> {\n            const auto bounds = header_actions.bounds_for_id( id );\n            if( !bounds ) {\n                return std::nullopt;\n            }\n            const point offset( getbegx( w_header ), getbegy( w_header ) );\n            return inclusive_rectangle<point>( bounds->p_min + offset, bounds->p_max + offset );\n        };\n\n        if( state.open_header_menu == "CATEGORIES" ) {\n''',
    "crafting header trigger geometry adapter",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            const ui_action_result result = category_menu.handle_input(\n                                                action, screen_pos, false,\n                                                ui_outside_click_policy::passthrough );\n''',
    '''            const ui_action_result result = category_menu.handle_input(\n                                                action, screen_pos, false,\n                                                ui_outside_click_policy::passthrough,\n                                                header_trigger_bounds( "HEADER_CATEGORIES" ) );\n''',
    "crafting category trigger semantics",
)
replace_once(
    "src/crafting_gui.cpp",
    '''            const bool keep_open = state.open_header_menu == "FILTER";\n            const ui_action_result result = header_menu.handle_input(\n                                                action, screen_pos, !keep_open,\n                                                ui_outside_click_policy::passthrough );\n''',
    '''            const bool keep_open = state.open_header_menu == "FILTER";\n            const std::string trigger_id = state.open_header_menu == "FILTER" ? "HEADER_FILTER" :\n                                           state.open_header_menu == "SORT" ? "HEADER_SORT" : "HEADER_VIEW";\n            const ui_action_result result = header_menu.handle_input(\n                                                action, screen_pos, !keep_open,\n                                                ui_outside_click_policy::passthrough,\n                                                header_trigger_bounds( trigger_id ) );\n''',
    "crafting header trigger semantics",
)

# Vehicle filter dropdown triggers already share w_disp coordinates with the menu.
replace_once(
    "src/veh_interact.cpp",
    '''    if( open_editor_dropdown != editor_dropdown::none && editor_filter_dropdown_menu.is_open() ) {\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input(\n                                          action, viewport_pos, false,\n                                          ui_outside_click_policy::passthrough );\n''',
    '''    if( open_editor_dropdown != editor_dropdown::none && editor_filter_dropdown_menu.is_open() ) {\n        const std::string trigger_id = open_editor_dropdown == editor_dropdown::system ?\n                                       "FILTER_SYSTEM" : "FILTER_CONDITION";\n        const ui_action_result result = editor_filter_dropdown_menu.handle_input(\n                                          action, viewport_pos, false,\n                                          ui_outside_click_policy::passthrough,\n                                          editor_filter_strip.bounds_for_id( trigger_id ) );\n''',
    "vehicle filter trigger semantics",
)

# Toolbar menu and trigger use different parent windows; translate helper-produced strip bounds
# into w_border coordinates, then let ui_dropdown own the behavioral decision.
replace_once(
    "src/veh_interact.cpp",
    '''    const std::optional<point> pos = main_context.get_coordinates_text( w_border );\n    const ui_action_result result = editor_toolbar_dropdown_menu.handle_input(\n                                      action, pos, true, ui_outside_click_policy::passthrough );\n''',
    '''    const std::optional<point> pos = main_context.get_coordinates_text( w_border );\n    std::optional<inclusive_rectangle<point>> trigger_bounds;\n    if( const auto bounds = editor_toolbar_strip.bounds_for_id( open_editor_toolbar_dropdown ) ) {\n        const point offset( getbegx( w_mode ) - getbegx( w_border ),\n                            getbegy( w_mode ) - getbegy( w_border ) );\n        trigger_bounds = inclusive_rectangle<point>( bounds->p_min + offset, bounds->p_max + offset );\n    }\n    const ui_action_result result = editor_toolbar_dropdown_menu.handle_input(\n                                      action, pos, true, ui_outside_click_policy::passthrough,\n                                      trigger_bounds );\n''',
    "vehicle toolbar trigger semantics",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Make dropdown dismissal trigger-aware in shared helpers\n", encoding="utf-8"
)
