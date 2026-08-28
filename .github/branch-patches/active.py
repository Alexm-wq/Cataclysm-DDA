from pathlib import Path

path = Path("src/sdltiles.cpp")
text = path.read_text(encoding="utf-8")
old = "static void draw_ui_pixel_button_bitmap( const cata_cursesport::pixel_icon_button_overlay &button,\n"
new = "static void draw_ui_pixel_button_bitmap( const ui_pixel_icon_button_overlay &button,\n"
if text.count(old) != 1:
    raise SystemExit(f"expected one stale pixel icon type, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix geometry-layer HUD overlay type\n", encoding="utf-8"
)
