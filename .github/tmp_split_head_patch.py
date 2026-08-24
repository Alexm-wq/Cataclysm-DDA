from pathlib import Path

path = Path("src/advanced_inv.cpp")
text = path.read_text()
old = """        if( split_recalc_guard ) {\n            redraw_pane( left );\n            redraw_pane( right );\n            redraw_sidebar();\n            recalc = false;\n        }\n"""
new = """        if( split_recalc_guard ) {\n            redraw_pane( left );\n            redraw_pane( right );\n            recalc = false;\n        }\n"""
count = text.count(old)
if count != 2:
    raise SystemExit(f"expected 2 split redraw blocks, found {count}")
path.write_text(text.replace(old, new))
