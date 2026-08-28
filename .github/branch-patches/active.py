from pathlib import Path
import subprocess


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {path_str}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

# Associate pixel icon overlays with the curses window that owns their z-layer.
replace_once(
    "src/sdltiles.h",
    """struct ui_pixel_icon_button_overlay {\n    const void *owner = nullptr;\n    point pos_pixels = point::zero;\n""",
    """struct ui_pixel_icon_button_overlay {\n    const void *owner = nullptr;\n    const void *parent = nullptr;\n    point pos_pixels = point::zero;\n""",
)
replace_once(
    "src/sdltiles.h",
    """void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay );\n""",
    """void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay,\n                               const catacurses::window &parent );\n""",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    """                set_ui_pixel_icon_button( render );\n                return;\n""",
    """                set_ui_pixel_icon_button( render, parent );\n                return;\n""",
)

replace_once(
    "src/sdltiles.cpp",
    """void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay )\n{\n    if( overlay.owner == nullptr ) {\n        return;\n    }\n    const auto found = std::find_if( ui_pixel_icon_buttons.begin(), ui_pixel_icon_buttons.end(),\n    [&]( const ui_pixel_icon_button_overlay & existing ) {\n        return existing.owner == overlay.owner;\n    } );\n    if( found == ui_pixel_icon_buttons.end() ) {\n        ui_pixel_icon_buttons.push_back( overlay );\n    } else {\n        *found = overlay;\n    }\n    needupdate = true;\n}\n""",
    """void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay,\n                               const catacurses::window &parent )\n{\n    if( overlay.owner == nullptr || !parent ) {\n        return;\n    }\n    ui_pixel_icon_button_overlay layered = overlay;\n    layered.parent = parent.get<cata_cursesport::WINDOW>();\n    const auto found = std::find_if( ui_pixel_icon_buttons.begin(), ui_pixel_icon_buttons.end(),\n    [&]( const ui_pixel_icon_button_overlay & existing ) {\n        return existing.owner == layered.owner;\n    } );\n    if( found == ui_pixel_icon_buttons.end() ) {\n        ui_pixel_icon_buttons.push_back( layered );\n    } else {\n        *found = layered;\n    }\n    needupdate = true;\n}\n""",
)

replace_once(
    "src/sdltiles.cpp",
    """static void draw_ui_pixel_icon_buttons()\n{\n    for( const ui_pixel_icon_button_overlay &button : ui_pixel_icon_buttons ) {\n        if( button.owner == nullptr || button.size_pixels.x < 3 || button.size_pixels.y < 3 ) {\n            continue;\n        }\n""",
    """static bool draw_ui_pixel_icon_buttons( const cata_cursesport::WINDOW *parent )\n{\n    bool drew = false;\n    for( const ui_pixel_icon_button_overlay &button : ui_pixel_icon_buttons ) {\n        if( button.owner == nullptr || button.parent != parent ||\n            button.size_pixels.x < 3 || button.size_pixels.y < 3 ) {\n            continue;\n        }\n        drew = true;\n""",
)
replace_once(
    "src/sdltiles.cpp",
    """        draw_ui_pixel_button_bitmap( button, icon );\n    }\n}\n\nvoid refresh_display()\n""",
    """        draw_ui_pixel_button_bitmap( button, icon );\n    }\n    return drew;\n}\n\nvoid refresh_display()\n""",
)
replace_once(
    "src/sdltiles.cpp",
    """\n    // Pixel-space HUD controls are composited after the terminal framebuffer so\n    // their geometry is not quantized to character-cell aspect ratios.\n    draw_ui_pixel_icon_buttons();\n\n#if defined(__ANDROID__)\n""",
    """\n#if defined(__ANDROID__)\n""",
)
replace_once(
    "src/sdltiles.cpp",
    """    }\n    if( update ) {\n        needupdate = true;\n    }\n}\n\nstatic int alt_buffer = 0;\n""",
    """    }\n\n    // Pixel controls draw in the same window layer as their logical parent.\n    // Later modal/menu windows therefore cover them naturally instead of the\n    // controls being composited above the finished terminal framebuffer.\n    if( draw_ui_pixel_icon_buttons( win ) ) {\n        update = true;\n    }\n    if( update ) {\n        needupdate = true;\n    }\n}\n\nstatic int alt_buffer = 0;\n""",
)

# Safemode HUD is anchored to the pixel-minimap layer, not stdscr.  Geometry is
# still absolute pixel space, but the minimap parent gives the controls correct z-order.
replace_once(
    "src/game.cpp",
    """#if defined(TILES)\n    safemode_corner_launcher.configure_pixel(\n        catacurses::stdscr, launcher_pos, launcher_size,\n        ui_action_entry( \"\", \"SAFE_CORNER_EXPAND\" ), \"<\", launcher_style );\n#else\n    safemode_corner_launcher.configure_compact(\n        catacurses::stdscr, launcher_pos, launcher_size,\n        ui_action_entry( \"\", \"SAFE_CORNER_EXPAND\" ), \"<\", launcher_style );\n#endif\n    safemode_corner_launcher.draw( catacurses::stdscr );\n""",
    """#if defined(TILES)\n    safemode_corner_launcher.configure_pixel(\n        w_pixel_minimap, launcher_pos, launcher_size,\n        ui_action_entry( \"\", \"SAFE_CORNER_EXPAND\" ), \"<\", launcher_style );\n    safemode_corner_launcher.draw( w_pixel_minimap );\n#else\n    safemode_corner_launcher.configure_compact(\n        catacurses::stdscr, launcher_pos, launcher_size,\n        ui_action_entry( \"\", \"SAFE_CORNER_EXPAND\" ), \"<\", launcher_style );\n    safemode_corner_launcher.draw( catacurses::stdscr );\n#endif\n""",
)
replace_once(
    "src/game.cpp",
    """#if defined(TILES)\n            safemode_corner_buttons[i].configure_pixel(\n                catacurses::stdscr,\n                safemode_corner_palette_pixel_pos( w_pixel_minimap, i ),\n                button_size, std::move( action ), std::move( icon ), style );\n#else\n            safemode_corner_buttons[i].configure_compact(\n                catacurses::stdscr,\n                safemode_corner_palette_pos( w_pixel_minimap, i ),\n                button_size, std::move( action ), std::move( icon ), style );\n#endif\n            safemode_corner_buttons[i].draw( catacurses::stdscr );\n""",
    """#if defined(TILES)\n            safemode_corner_buttons[i].configure_pixel(\n                w_pixel_minimap,\n                safemode_corner_palette_pixel_pos( w_pixel_minimap, i ),\n                button_size, std::move( action ), std::move( icon ), style );\n            safemode_corner_buttons[i].draw( w_pixel_minimap );\n#else\n            safemode_corner_buttons[i].configure_compact(\n                catacurses::stdscr,\n                safemode_corner_palette_pos( w_pixel_minimap, i ),\n                button_size, std::move( action ), std::move( icon ), style );\n            safemode_corner_buttons[i].draw( catacurses::stdscr );\n#endif\n""",
)

subprocess.run(["git", "diff", "--check"], check=True)
