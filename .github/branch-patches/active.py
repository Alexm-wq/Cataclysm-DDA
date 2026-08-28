from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Keep the pixel-HUD teardown in one place. turn_handler::cleanup_at_end is already
# a friend of game, so this helper can remain private instead of becoming a new
# public lifecycle API.
replace_once(
    "src/game.h",
    '''    private:\n        bool is_looking = false; // NOLINT(cata-serialize)\n''',
    '''    private:\n        void clear_safemode_mouse_controls();\n        bool is_looking = false; // NOLINT(cata-serialize)\n'''
)

replace_once(
    "src/game.cpp",
    '''game::~game()\n{\n    safemode_corner_launcher.close();\n    for( ui_icon_button &button : safemode_corner_buttons ) {\n        button.close();\n    }\n    for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n        if( button ) {\n            button->close();\n        }\n    }\n}\n''',
    '''void game::clear_safemode_mouse_controls()\n{\n    safemode_corner_launcher.close();\n    for( ui_icon_button &button : safemode_corner_buttons ) {\n        button.close();\n    }\n    for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n        if( button ) {\n            button->close();\n        }\n    }\n    safemode_corner_tooltip.reset();\n    safemode_corner_expanded = false;\n}\n\ngame::~game()\n{\n    clear_safemode_mouse_controls();\n}\n'''
)

# The global game object survives save-and-quit and is reused by the main-menu
# loop, so destructor cleanup is too late. Remove SDL registrations at the real
# gameplay-session teardown boundary as well.
replace_once(
    "src/do_turn.cpp",
    '''#if defined(__ANDROID__)\n    quick_shortcuts_map.clear();\n#endif\n    return true;\n}\n''',
    '''#if defined(__ANDROID__)\n    quick_shortcuts_map.clear();\n#endif\n\n    g->clear_safemode_mouse_controls();\n    return true;\n}\n'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Clear pixel HUD at gameplay session end\n", encoding="utf-8"
)
