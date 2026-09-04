from pathlib import Path

path = Path("src/inventory_ui.cpp")
text = path.read_text(encoding="utf-8")
old = '''void inventory_selector::draw_grab_indicator()\n{\n    draw_ui_grab_item_indicator( w_inv, ctxt.get_coordinates_text( w_inv ), grabbed_item );\n}\n'''
new = '''void inventory_selector::draw_grab_indicator()\n{\n    if( !grabbed_item ) {\n        return;\n    }\n    draw_ui_grab_item_indicator( w_inv, ctxt.get_coordinates_text( w_inv ), grabbed_item );\n}\n'''
if text.count(old) != 1:
    raise RuntimeError(f"grab draw guard: expected one match, found {text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

assert 'if( !grabbed_item )' in text
Path("/tmp/branch_patch_commit_message").write_text(
    "Guard grabbed-item preview cleanup\n", encoding="utf-8"
)
