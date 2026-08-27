from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text()

old = '''            if( refuel_info ) {\n                // Preserve the regular editor behind the compact modal.\n                display_part_inspector();\n                display_part_details();\n                display_refuel_pane( here );\n                display_mode( here );\n#if defined(TILES)\n                // SDL map previews are outside curses window ordering and can\n                // otherwise draw over the modal.\n                clear_map_preview_window();\n#endif\n                return;\n            }\n'''
new = '''            if( refuel_info ) {\n                // Preserve the regular editor and its SDL-backed Live/Split preview\n                // behind the compact refuel modal.  w_refuel_overlay is already a\n                // dedicated small window, so draw/register the preview first and\n                // refresh only the modal + toolbar on top.\n                display_part_inspector();\n                display_part_details();\n                display_live_preview( here );\n                display_refuel_pane( here );\n                display_mode( here );\n                return;\n            }\n'''
if text.count(old) != 1:
    raise SystemExit(f'refuel redraw block: expected 1 match, got {text.count(old)}')
text = text.replace(old, new, 1)

old2 = '''bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )\n{\n    if( !refuel_info ) {\n        return false;\n    }\n    const std::optional<point> pos = main_context.get_coordinates_text( w_refuel_overlay );\n'''
new2 = '''bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )\n{\n    if( !refuel_info ) {\n        return false;\n    }\n\n    // This helper must never consume keyboard actions merely because the last\n    // mouse position happens to lie over the modal.  In particular QUIT/Escape,\n    // arrows, Confirm and Refuel belong to do_main_loop()'s refuel keyboard path.\n    const bool mouse_action = action == "MOUSE_MOVE" || action == "SELECT" ||\n                              action == "SEC_SELECT" || action == "SCROLL_UP" ||\n                              action == "SCROLL_DOWN";\n    if( !mouse_action ) {\n        return false;\n    }\n\n    const std::optional<point> pos = main_context.get_coordinates_text( w_refuel_overlay );\n'''
if text.count(old2) != 1:
    raise SystemExit(f'refuel mouse header: expected 1 match, got {text.count(old2)}')
text = text.replace(old2, new2, 1)

assert 'clear_map_preview_window();\n#endif\n                return;' not in text[text.find('if( refuel_info ) {'):text.find('const auto draw_message_window')]
assert 'display_live_preview( here );\n                display_refuel_pane( here );' in text
assert 'if( !mouse_action ) {\n        return false;' in text
assert 'if( action == "QUIT" && refuel_info ) {\n            close_refuel_mode();' in text

path.write_text(text)
print('fixed refuel Live/Split redraw and keyboard Escape routing')
