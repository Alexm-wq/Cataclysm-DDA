from pathlib import Path

path = Path("src/ui_helpers/controls/world_viewport.h")
s = path.read_text()
old = '''            if( action == "SCROLL_UP" ) {\n                return { ui_world_viewport_action_type::zoom_in, position, std::nullopt };\n            }\n            if( action == "SCROLL_DOWN" ) {\n                return { ui_world_viewport_action_type::zoom_out, position, std::nullopt };\n            }\n'''
new = '''            if( action == "SCROLL_UP" ) {\n                hovered_ = position;\n                return { ui_world_viewport_action_type::zoom_in, position, std::nullopt };\n            }\n            if( action == "SCROLL_DOWN" ) {\n                hovered_ = position;\n                return { ui_world_viewport_action_type::zoom_out, position, std::nullopt };\n            }\n'''
if s.count(old) != 1:
    raise SystemExit(f"wheel anchor: expected 1 match, found {s.count(old)}")
path.write_text(s.replace(old, new, 1))
Path("/tmp/branch_patch_commit_message").write_text(
    "Keep auxiliary viewport zoom cursor-anchored [skip ci]\n"
)
