# One-shot guarded patch for mouse-inventory-0-i-test.
from pathlib import Path

veh = Path("src/veh_interact.cpp")
text = veh.read_text(encoding="utf-8")
old = '''    const std::optional<point> viewport_pos = main_context.get_coordinates_text( w_disp );
    const std::optional<point> parts_pos = main_context.get_coordinates_text( w_parts );
    const std::optional<point> details_pos = main_context.get_coordinates_text( w_msg );
'''
new = '''    // get_coordinates_text() deliberately returns coordinates outside a window in
    // the tiles build, so pane routing must bounds-check the relative position.
    const auto mouse_pos_in = [&]( const catacurses::window & win ) -> std::optional<point> {
        const std::optional<point> pos = main_context.get_coordinates_text( win );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( win ) ||
            pos->y >= getmaxy( win ) ) {
            return std::nullopt;
        }
        return pos;
    };

    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );
    const std::optional<point> parts_pos = mouse_pos_in( w_parts );
    const std::optional<point> details_pos = mouse_pos_in( w_msg );
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected exactly one editor mouse position block, found {count}")
text = text.replace(old, new)
veh.write_text(text, encoding="utf-8")

keys = Path("data/raw/keybindings.json")
ktext = keys.read_text(encoding="utf-8")
if '"category": "VEH_INTERACT"' in ktext:
    raise SystemExit("VEH_INTERACT keybindings already exist; refusing duplicate insertion")
for required in ('"id": "CAMERA_PAN_START"', '"id": "CAMERA_PAN_END"'):
    if required not in ktext:
        raise SystemExit(f"missing expected existing keybinding {required}")
stripped = ktext.rstrip()
if not stripped.endswith("]"):
    raise SystemExit("keybindings.json does not end in a JSON array")
insert = r''',
  {
    "type": "keybinding",
    "id": "CAMERA_PAN_START",
    "category": "VEH_INTERACT",
    "name": "Start vehicle editor panning",
    "bindings": [ { "input_method": "mouse", "key": "MOUSE_MIDDLE_PRESSED" } ]
  },
  {
    "type": "keybinding",
    "id": "CAMERA_PAN_END",
    "category": "VEH_INTERACT",
    "name": "Stop vehicle editor panning",
    "bindings": [ { "input_method": "mouse", "key": "MOUSE_MIDDLE" } ]
  },
  {
    "type": "keybinding",
    "id": "MOUSE_MOVE",
    "category": "VEH_INTERACT",
    "name": "Move mouse in vehicle editor",
    "bindings": [ { "input_method": "mouse", "key": "MOUSE_MOVE" } ]
  }
]'''
ktext = stripped[:-1] + insert + "\n"
keys.write_text(ktext, encoding="utf-8")
