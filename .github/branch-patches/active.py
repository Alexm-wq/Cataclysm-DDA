from pathlib import Path

p = Path("src/advanced_inv.cpp")
text = p.read_text()
old = '''    if( entry.focus && *entry.focus ) {\n        advanced_inventory_pane &focus_pane = panes[src];\n        focus_pane.target_item_after_recalc = *entry.focus;\n'''
new = '''    if( entry.focus && *entry.focus ) {\n        advanced_inventory_pane &focus_pane = panes[src];\n        // Pickup normally prefers ground items when a tile contains both ground\n        // objects and vehicle cargo.  An exact context-menu focus must override\n        // that heuristic so a cargo container opens in the vehicle pane it belongs to.\n        if( entry.focus->where() == item_location::type::vehicle ) {\n            const aim_location focus_area = target_area();\n            focus_pane.container = item_location::nowhere;\n            focus_pane.container_base_loc = NUM_AIM_LOCATIONS;\n            focus_pane.set_area( squares[focus_area], true );\n            focus_pane.index = 0;\n            focus_pane.recalc = true;\n        }\n        focus_pane.target_item_after_recalc = *entry.focus;\n'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected exactly one advanced inventory focus block, found {count}")
p.write_text(text.replace(old, new, 1))
print("exact vehicle-container focus patched")
