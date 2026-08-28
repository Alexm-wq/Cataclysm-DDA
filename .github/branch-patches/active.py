from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Keep the safemode palette on the shared icon-button helper, but make the
# screen-owned geometry match the compact connected mockup: smaller cells,
# shared borders, and a narrower attached launcher.
replace_once(
    "src/game.cpp",
    '''static const point safemode_corner_icon_pixels( 12, 12 );\n''',
    '''static const point safemode_corner_icon_pixels( 6, 6 );\n''',
    "safemode compact icon footprint",
)

replace_once(
    "src/game.cpp",
    '''static point safemode_corner_launcher_pos( const catacurses::window &panel )\n{\n    const point size = safemode_corner_button_size();\n    return point( getbegx( panel ),\n                  getbegy( panel ) + getmaxy( panel ) - size.y );\n}\n\nstatic point safemode_corner_palette_pos( const catacurses::window &panel, const int index )\n{\n    const point size = safemode_corner_button_size();\n    const point launcher = safemode_corner_launcher_pos( panel );\n    const int rows_above_bottom = safemode_corner_safe_index - index;\n    return point( getbegx( panel ) - size.x,\n                  launcher.y - rows_above_bottom * size.y );\n}\n''',
    '''static point safemode_corner_launcher_size()\n{\n    const point button_size = safemode_corner_button_size();\n    return point( std::max( 3, ( button_size.x + 1 ) / 2 ), button_size.y );\n}\n\nstatic point safemode_corner_launcher_pos( const catacurses::window &panel )\n{\n    const point size = safemode_corner_button_size();\n    // Share the launcher's left border with the bottom palette cell's right border.\n    return point( getbegx( panel ) - 1,\n                  getbegy( panel ) + getmaxy( panel ) - size.y );\n}\n\nstatic point safemode_corner_palette_pos( const catacurses::window &panel, const int index )\n{\n    const point size = safemode_corner_button_size();\n    const point launcher = safemode_corner_launcher_pos( panel );\n    const int rows_above_bottom = safemode_corner_safe_index - index;\n    // Adjacent cells overlap one border row so the stack reads as one connected grid.\n    return point( getbegx( panel ) - size.x,\n                  launcher.y - rows_above_bottom * ( size.y - 1 ) );\n}\n''',
    "safemode connected palette geometry",
)

replace_once(
    "src/game.cpp",
    '''    const point size = safemode_corner_button_size();\n    if( getmaxx( panel ) < size.x || getmaxy( panel ) < size.y ) {\n        return false;\n    }\n    const point launcher = safemode_corner_launcher_pos( panel );\n    const point top_button = safemode_corner_palette_pos( panel, 0 );\n    return launcher.x >= 0 && launcher.y >= 0 &&\n           launcher.x + size.x <= getmaxx( catacurses::stdscr ) &&\n           launcher.y + size.y <= getmaxy( catacurses::stdscr ) &&\n           top_button.x >= 0 && top_button.y >= 0;\n''',
    '''    const point size = safemode_corner_button_size();\n    const point launcher_size = safemode_corner_launcher_size();\n    if( getmaxx( panel ) < launcher_size.x || getmaxy( panel ) < size.y ) {\n        return false;\n    }\n    const point launcher = safemode_corner_launcher_pos( panel );\n    const point top_button = safemode_corner_palette_pos( panel, 0 );\n    return launcher.x >= 0 && launcher.y >= 0 &&\n           launcher.x + launcher_size.x <= getmaxx( catacurses::stdscr ) &&\n           launcher.y + launcher_size.y <= getmaxy( catacurses::stdscr ) &&\n           top_button.x >= 0 && top_button.y >= 0;\n''',
    "safemode compact fit check",
)

replace_once(
    "src/game.cpp",
    '''    const point button_size = safemode_corner_button_size();\n    const point launcher_pos = safemode_corner_launcher_pos( w_pixel_minimap );\n\n    ui_icon_button_style launcher_style;\n    launcher_style.border = c_light_gray;\n    launcher_style.fill = i_dark_gray;\n    launcher_style.icon = c_light_gray;\n    launcher_style.hover_border = c_white;\n    launcher_style.hover_fill = i_light_gray;\n    launcher_style.hover_icon = c_white;\n    safemode_corner_launcher.configure( catacurses::stdscr, launcher_pos, button_size,\n                                        ui_action_entry( "", "SAFE_CORNER_EXPAND" ),\n                                        "<", launcher_style );\n''',
    '''    const point button_size = safemode_corner_button_size();\n    const point launcher_size = safemode_corner_launcher_size();\n    const point launcher_pos = safemode_corner_launcher_pos( w_pixel_minimap );\n\n    ui_icon_button_style launcher_style;\n    launcher_style.border = c_light_gray;\n    launcher_style.fill = i_dark_gray;\n    launcher_style.icon = c_light_gray;\n    launcher_style.hover_border = c_white;\n    launcher_style.hover_fill = i_light_gray;\n    launcher_style.hover_icon = c_white;\n    safemode_corner_launcher.configure( catacurses::stdscr, launcher_pos, launcher_size,\n                                        ui_action_entry( "", "SAFE_CORNER_EXPAND" ),\n                                        "<", launcher_style );\n''',
    "safemode narrow launcher",
)

replace_once(
    "src/game.cpp",
    '''            ui_icon_button_style style;\n            ui_action_entry action( "", is_safe ? "SAFE_MODE_TOGGLE" :\n                                    string_format( "SAFE_RESERVED_%d", i ), is_safe );\n            std::string icon = is_safe ? "!" : " ";\n\n            if( is_safe ) {\n                const nc_color state_color = enabled ? c_light_green : c_light_red;\n                style.icon = state_color;\n                style.hover_icon = state_color;\n                style.selected_icon = state_color;\n            } else {\n                style.disabled_border = c_dark_gray;\n                style.disabled_fill = i_dark_gray;\n                style.disabled_icon = c_dark_gray;\n            }\n''',
    '''            ui_icon_button_style style;\n            ui_action_entry action( "", is_safe ? "SAFE_MODE_TOGGLE" :\n                                    string_format( "SAFE_RESERVED_%d", i ), is_safe );\n            std::string icon = is_safe ? "[!]" : "■";\n\n            style.border = c_light_gray;\n            style.fill = i_dark_gray;\n            style.hover_border = c_white;\n            style.hover_fill = i_light_gray;\n            if( is_safe ) {\n                const nc_color state_color = enabled ? c_light_green : c_light_red;\n                style.icon = state_color;\n                style.hover_icon = state_color;\n                style.selected_icon = state_color;\n            } else {\n                // Reserved cells stay disabled, but remain visually present as grey tiles.\n                style.disabled_border = c_light_gray;\n                style.disabled_fill = i_dark_gray;\n                style.disabled_icon = c_dark_gray;\n            }\n''',
    "safemode compact cell icons",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Refine compact safemode corner palette\n", encoding="utf-8"
)
