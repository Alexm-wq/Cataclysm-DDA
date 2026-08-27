from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Keep the generic text field self-contained rather than relying on transitive includes.
replace_once(
    "src/ui_helpers/controls/text_field.h",
    '''#include <optional>\n#include <string>\n''',
    '''#include <optional>\n#include <string>\n#include <utility>\n''',
    "text field utility include",
)

# Vehicle transient controls should retain semantic state only; ui_dropdown owns popup geometry.
replace_once(
    "src/veh_interact.h",
    '''        point editor_context_anchor = point::zero;\n        point editor_context_pos = point::zero;\n        point editor_mouse_pos = point::zero;\n        int editor_context_width = 0;\n        int editor_context_height = 0;\n''',
    '''        point editor_context_anchor = point::zero;\n        point editor_mouse_pos = point::zero;\n''',
    "remove vehicle context popup geometry state",
)
replace_once(
    "src/veh_interact.h",
    '''        std::string pending_editor_action;\n        std::string open_editor_toolbar_dropdown;\n        point editor_toolbar_dropdown_pos = point::zero;\n        int editor_toolbar_dropdown_width = 0;\n        int editor_toolbar_dropdown_height = 0;\n        std::vector<ui_action_entry> editor_toolbar_dropdown_buttons;\n''',
    '''        std::string pending_editor_action;\n        std::string open_editor_toolbar_dropdown;\n        std::vector<ui_action_entry> editor_toolbar_dropdown_buttons;\n''',
    "remove vehicle toolbar popup geometry state",
)

replace_once(
    "src/veh_interact.cpp",
    '''    editor_context_target = editor_context_surface::none;\n    editor_context_buttons.clear();\n    editor_context_width = 0;\n    editor_context_height = 0;\n    editor_context_dropdown_menu.close();\n''',
    '''    editor_context_target = editor_context_surface::none;\n    editor_context_buttons.clear();\n    editor_context_dropdown_menu.close();\n''',
    "vehicle context close geometry cleanup",
)

# Remove the manual context-menu sizing/flipping/truncation block.  The helper computes width,
# height, clamping, and scrolling from the semantic entries.
path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")
start_marker = '''    editor_context_open = true;\n\n    const catacurses::window &target = surface == editor_context_surface::parts ? w_parts : w_disp;\n'''
start = text.find(start_marker)
end_marker = '''    editor_context_pos = point( menu_x, menu_y );\n}\n\nbool veh_interact::set_editor_repair_requirements'''
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("vehicle context geometry block not found")
replacement = '''    editor_context_open = true;\n}\n\nbool veh_interact::set_editor_repair_requirements'''
text = text[:start] + replacement + text[end + len(end_marker):]
path.write_text(text, encoding="utf-8")

replace_once(
    "src/veh_interact.cpp",
    '''void veh_interact::display_editor_context_menu()\n{\n    if( !editor_context_open || editor_context_target == editor_context_surface::none ||\n        editor_context_width <= 0 || editor_context_height < 3 ) {\n        editor_context_dropdown_menu.close();\n        return;\n    }\n\n    catacurses::window &target = editor_context_target == editor_context_surface::parts ? w_parts : w_disp;\n    ui_dropdown_style style;\n    style.border = c_light_gray; // right-click menus intentionally keep their gray border\n    style.text = c_light_green;\n    editor_context_dropdown_menu.configure( target, editor_context_pos, editor_context_buttons,\n                                            editor_context_width, style );\n    editor_context_dropdown_menu.update_hover( editor_mouse_pos );\n    editor_context_dropdown_menu.draw( target );\n}\n''',
    '''void veh_interact::display_editor_context_menu()\n{\n    if( !editor_context_open || editor_context_target == editor_context_surface::none ||\n        editor_context_buttons.empty() ) {\n        editor_context_dropdown_menu.close();\n        return;\n    }\n\n    catacurses::window &target = editor_context_target == editor_context_surface::parts ? w_parts : w_disp;\n    ui_dropdown_style style;\n    style.border = c_light_gray; // style override; sizing/input behavior remains helper-owned\n    style.text = c_light_green;\n    editor_context_dropdown_menu.configure( target, editor_context_anchor + point( 2, 0 ),\n                                            editor_context_buttons, 0, style );\n    editor_context_dropdown_menu.update_hover( editor_mouse_pos );\n    editor_context_dropdown_menu.draw( target );\n}\n''',
    "vehicle context helper geometry",
)

# Toolbar dropdown opening retains only semantic entries.  No menu-local popup dimensions.
path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")
old = '''    int widest = 0;\n    for( const toolbar_menu_entry &entry : entries ) {\n        widest = std::max( widest, utf8_width( entry.label ) );\n        editor_toolbar_dropdown_buttons.emplace_back( entry.label, entry.action,\n                editor_toolbar_action_enabled( here, entry.action ) );\n    }\n    editor_toolbar_dropdown_width = std::clamp( widest + 4, 14,\n                                    std::max( 14, getmaxx( w_border ) - 2 ) );\n    editor_toolbar_dropdown_height = static_cast<int>( editor_toolbar_dropdown_buttons.size() ) + 2;\n\n    int anchor_x = 1;\n    if( const auto bounds = editor_toolbar_strip.bounds_for_id( which ) ) {\n        anchor_x = getbegx( w_mode ) + bounds->p_min.x - getbegx( w_border );\n    }\n    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );\n    const int x = std::clamp( anchor_x, 1, max_x );\n    const int desired_y = getbegy( w_disp ) - getbegy( w_border );\n    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );\n    const int y = std::clamp( desired_y, 1, max_y );\n    editor_toolbar_dropdown_pos = point( x, y );\n'''
new = '''    for( const toolbar_menu_entry &entry : entries ) {\n        editor_toolbar_dropdown_buttons.emplace_back( entry.label, entry.action,\n                editor_toolbar_action_enabled( here, entry.action ) );\n    }\n'''
if text.count(old) != 1:
    raise SystemExit(f"vehicle toolbar geometry: expected 1 anchor, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "src/veh_interact.cpp",
    '''    open_editor_toolbar_dropdown.clear();\n    editor_toolbar_dropdown_buttons.clear();\n    editor_toolbar_dropdown_width = 0;\n    editor_toolbar_dropdown_height = 0;\n    editor_toolbar_dropdown_pos = point::zero;\n    editor_toolbar_dropdown_menu.close();\n''',
    '''    open_editor_toolbar_dropdown.clear();\n    editor_toolbar_dropdown_buttons.clear();\n    editor_toolbar_dropdown_menu.close();\n''',
    "vehicle toolbar close geometry cleanup",
)

# Toolbar dropdown outside pointer events use the same pass-through policy as filter dropdowns.
replace_once(
    "src/veh_interact.cpp",
    '''    const std::optional<point> pos = main_context.get_coordinates_text( w_border );\n    const ui_action_result result = editor_toolbar_dropdown_menu.handle_input( action, pos );\n''',
    '''    const std::optional<point> pos = main_context.get_coordinates_text( w_border );\n    const ui_action_result result = editor_toolbar_dropdown_menu.handle_input(\n                                      action, pos, true, ui_outside_click_policy::passthrough );\n''',
    "vehicle toolbar dropdown pass-through policy",
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( result.type == ui_action_result_type::closed ) {\n        close_editor_toolbar_dropdown();\n        // Closing a toolbar dropdown is itself the completed action.  In\n        // particular Escape must not fall through as QUIT and close the editor\n        // on the same keypress.\n        return true;\n    }\n''',
    '''    if( result.type == ui_action_result_type::closed ) {\n        const bool pass_through = result.passes_through();\n        close_editor_toolbar_dropdown();\n        // Keyboard dismissal is consumed; outside pointer dismissal may continue\n        // to the underlying helper/list/scrollbar on the same event.\n        return !pass_through;\n    }\n''',
    "vehicle toolbar close pass-through",
)

replace_once(
    "src/veh_interact.cpp",
    '''void veh_interact::display_editor_toolbar_dropdown()\n{\n    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_buttons.empty() ) {\n        editor_toolbar_dropdown_menu.close();\n        return;\n    }\n\n    int anchor_x = editor_toolbar_dropdown_pos.x;\n    if( const auto bounds = editor_toolbar_strip.bounds_for_id( open_editor_toolbar_dropdown ) ) {\n        anchor_x = getbegx( w_mode ) + bounds->p_min.x - getbegx( w_border );\n    }\n    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );\n    editor_toolbar_dropdown_pos.x = std::clamp( anchor_x, 1, max_x );\n    const int desired_y = getbegy( w_disp ) - getbegy( w_border );\n    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );\n    editor_toolbar_dropdown_pos.y = std::clamp( desired_y, 1, max_y );\n\n    editor_toolbar_dropdown_menu.configure( w_border, editor_toolbar_dropdown_pos,\n                                            editor_toolbar_dropdown_buttons,\n                                            editor_toolbar_dropdown_width );\n    editor_toolbar_dropdown_menu.draw( w_border );\n}\n''',
    '''void veh_interact::display_editor_toolbar_dropdown()\n{\n    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_buttons.empty() ) {\n        editor_toolbar_dropdown_menu.close();\n        return;\n    }\n\n    int anchor_x = 1;\n    if( const auto bounds = editor_toolbar_strip.bounds_for_id( open_editor_toolbar_dropdown ) ) {\n        anchor_x = getbegx( w_mode ) + bounds->p_min.x - getbegx( w_border );\n    }\n    const int anchor_y = getbegy( w_disp ) - getbegy( w_border );\n    editor_toolbar_dropdown_menu.configure( w_border, point( anchor_x, anchor_y ),\n                                            editor_toolbar_dropdown_buttons );\n    editor_toolbar_dropdown_menu.draw( w_border );\n}\n''',
    "vehicle toolbar helper geometry",
)

# Route toolbar dropdowns before scrollbars, exactly like filter dropdowns.  This lets a click
# dismiss the menu and start a shared scrollbar drag with the same CLICK_AND_DRAG event.
replace_once(
    "src/veh_interact.cpp",
    '''    if( open_editor_dropdown != editor_dropdown::none && editor_filter_dropdown_menu.is_open() ) {\n''',
    '''    if( !open_editor_toolbar_dropdown.empty() && editor_toolbar_dropdown_menu.is_open() ) {\n        const bool dropdown_handled = handle_editor_toolbar_dropdown_mouse( action );\n        if( !pending_editor_action.empty() ) {\n            return false;\n        }\n        if( dropdown_handled ) {\n            return true;\n        }\n    }\n\n    if( open_editor_dropdown != editor_dropdown::none && editor_filter_dropdown_menu.is_open() ) {\n''',
    "vehicle toolbar dropdown before scrollbars",
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( !open_editor_toolbar_dropdown.empty() ) {\n        const bool dropdown_handled = handle_editor_toolbar_dropdown_mouse( action );\n        if( !pending_editor_action.empty() ) {\n            return false;\n        }\n        if( dropdown_handled ) {\n            return true;\n        }\n    }\n\n''',
    '''''',
    "remove late vehicle toolbar dropdown routing",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Finish shared transient UI behavior migration\n", encoding="utf-8"
)
