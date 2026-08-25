from pathlib import Path

# Shared SDL physical-state helper.
sdl = Path("src/sdl_utils.h")
text = sdl.read_text(encoding="utf-8")
needle = '#include "sdl_wrappers.h"\n'
insert = '''#include "sdl_wrappers.h"\n\ninline bool is_middle_mouse_button_down()\n{\n    return ( SDL_GetMouseState( nullptr, nullptr ) & SDL_BUTTON( SDL_BUTTON_MIDDLE ) ) != 0;\n}\n'''
if text.count(needle) != 1:
    raise SystemExit("unexpected sdl_utils.h include layout")
if "is_middle_mouse_button_down" in text:
    raise SystemExit("middle mouse helper already exists")
text = text.replace(needle, insert, 1)
sdl.write_text(text, encoding="utf-8")

# Normal gameplay map: recover from both missed release and missed press events.
game = Path("src/game.cpp")
text = game.read_text(encoding="utf-8")
old = '''bool game::handle_mouseview( input_context &ctxt, std::string &action )\n{\n    action = ctxt.handle_input();\n#if defined(TILES)\n    if( action == "CAMERA_PAN_START" ) {\n'''
new = '''bool game::handle_mouseview( input_context &ctxt, std::string &action )\n{\n    action = ctxt.handle_input();\n#if defined(TILES)\n    const bool middle_mouse_down = is_middle_mouse_button_down();\n    if( camera_pan_active && !middle_mouse_down ) {\n        camera_pan_active = false;\n        camera_pan_anchor.reset();\n    }\n    if( action == "MOUSE_MOVE" && !camera_pan_active && middle_mouse_down ) {\n        camera_pan_anchor = ctxt.get_coordinates( w_terrain, ter_view_p.raw().xy(), true );\n        camera_pan_active = camera_pan_anchor.has_value();\n        if( camera_pan_active ) {\n            liveview.hide();\n        }\n        return true;\n    }\n    if( action == "CAMERA_PAN_START" ) {\n'''
if text.count(old) != 1:
    raise SystemExit(f"expected one gameplay pan entry block, found {text.count(old)}")
text = text.replace(old, new, 1)
game.write_text(text, encoding="utf-8")

# Vehicle editor: same physical-state recovery, scoped to the viewport.
veh = Path("src/veh_interact.cpp")
text = veh.read_text(encoding="utf-8")
include_needle = '#include "skill.h"\n'
include_insert = '''#include "skill.h"\n#if defined(TILES)\n#include "sdl_utils.h"\n#endif\n'''
if text.count(include_needle) != 1:
    raise SystemExit("unexpected veh_interact.cpp include layout")
if '#include "sdl_utils.h"' not in text:
    text = text.replace(include_needle, include_insert, 1)

old = '''    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );\n    const std::optional<point> parts_pos = mouse_pos_in( w_parts );\n    const std::optional<point> details_pos = mouse_pos_in( w_msg );\n\n    if( action == "CAMERA_PAN_START" ) {\n'''
new = '''    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );\n    const std::optional<point> parts_pos = mouse_pos_in( w_parts );\n    const std::optional<point> details_pos = mouse_pos_in( w_msg );\n\n#if defined(TILES)\n    const bool middle_mouse_down = is_middle_mouse_button_down();\n    if( viewport_dragging && !middle_mouse_down ) {\n        viewport_dragging = false;\n    }\n    if( action == "MOUSE_MOVE" && !viewport_dragging && middle_mouse_down && viewport_pos ) {\n        viewport_dragging = true;\n        viewport_drag_anchor = *viewport_pos;\n        viewport_drag_pan_origin = viewport_pan;\n        return true;\n    }\n#endif\n\n    if( action == "CAMERA_PAN_START" ) {\n'''
if text.count(old) != 1:
    raise SystemExit(f"expected one vehicle pan routing block, found {text.count(old)}")
text = text.replace(old, new, 1)
veh.write_text(text, encoding="utf-8")
