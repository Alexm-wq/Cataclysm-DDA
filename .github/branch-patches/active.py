from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Parent WINDOW identities can change across modal open/close. Re-associate an
# otherwise identical pixel control with the new parent without treating that
# bookkeeping-only change as a visual change that schedules another frame.
replace_once(
    "src/sdltiles.cpp",
    '''    const bool unchanged = found->parent == layered.parent &&\n                           found->pos_pixels == layered.pos_pixels &&\n                           found->size_pixels == layered.size_pixels &&\n                           found->border_color_pair == layered.border_color_pair &&\n                           found->fill_color_pair == layered.fill_color_pair &&\n                           found->icon_color_pair == layered.icon_color_pair &&\n                           found->icon == layered.icon;\n    if( unchanged ) {\n        return;\n    }\n\n    *found = layered;\n    needupdate = true;\n''',
    '''    const bool visually_unchanged = found->pos_pixels == layered.pos_pixels &&\n                                    found->size_pixels == layered.size_pixels &&\n                                    found->border_color_pair == layered.border_color_pair &&\n                                    found->fill_color_pair == layered.fill_color_pair &&\n                                    found->icon_color_pair == layered.icon_color_pair &&\n                                    found->icon == layered.icon;\n    if( visually_unchanged ) {\n        // Modal open/close can recreate the curses WINDOW backing this layer.\n        // Keep the association current, but do not create a redraw feedback loop\n        // for a control whose on-screen pixels did not change.\n        found->parent = layered.parent;\n        return;\n    }\n\n    *found = layered;\n    needupdate = true;\n'''
)

# The SDL pixel registry is global, while the game/HUD controls are not. Explicitly
# unregister every safemode control before the game instance is destroyed so stale
# owner/parent pointers cannot survive save-and-quit into the main menu.
replace_once(
    "src/game.cpp",
    '''game::~game() = default;\n''',
    '''game::~game()\n{\n    safemode_corner_launcher.close();\n    for( ui_icon_button &button : safemode_corner_buttons ) {\n        button.close();\n    }\n    for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n        if( button ) {\n            button->close();\n        }\n    }\n}\n'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix pixel HUD lifetime after modal menus\n", encoding="utf-8"
)
