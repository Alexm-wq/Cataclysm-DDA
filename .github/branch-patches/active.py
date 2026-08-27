from pathlib import Path

p = Path("src/cursesport.cpp")
s = p.read_text(encoding="utf-8")
a = """    for( int j = 0; j < win->height; j++ ) {\n        win->line[j].chars.assign( win->width, cata_cursesport::cursecell() );\n        win->line[j].touched = true;\n    }\n    win->draw = true;\n"""
b = """    // Pixel overlays belong to the contents being rebuilt by this erase.\n    // Callers that redraw a scrollbar immediately register its fresh geometry.\n    win->pixel_scrollbars.clear();\n    for( int j = 0; j < win->height; j++ ) {\n        win->line[j].chars.assign( win->width, cata_cursesport::cursecell() );\n        win->line[j].touched = true;\n    }\n    win->draw = true;\n"""
if s.count(a) != 1:
    raise SystemExit(f"werase overlay anchor: expected 1, found {s.count(a)}")
p.write_text(s.replace(a, b, 1), encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text("Clear pixel scrollbars with window erase\n", encoding="utf-8")
