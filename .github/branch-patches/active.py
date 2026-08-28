from pathlib import Path
import subprocess


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Persist semantic action identifiers in normal UI state.  The HUD resolves the
# current keybinding at draw time, so key remaps automatically change the glyph.
replace_once(
    "src/uistate.h",
    """        int crafting_browser_batch_size = 1;\n        int crafting_browser_focused_pane = 1;\n\n        bionic_ui_sort_mode bionic_sort_mode = bionic_ui_sort_mode::POWER;\n""",
    """        int crafting_browser_batch_size = 1;\n        int crafting_browser_focused_pane = 1;\n\n        // Five configurable map-HUD menu shortcuts.  Store action identifiers,\n        // never display keys, so rebinding keys does not invalidate assignments.\n        std::vector<std::string> safemode_corner_menu_slots = std::vector<std::string>( 5 );\n\n        bionic_ui_sort_mode bionic_sort_mode = bionic_ui_sort_mode::POWER;\n""",
)
replace_once(
    "src/inventory_ui.cpp",
    """    json.member( \"crafting_browser_batch_size\", crafting_browser_batch_size );\n    json.member( \"crafting_browser_focused_pane\", crafting_browser_focused_pane );\n    json.member( \"bionic_ui_sort_mode\", bionic_sort_mode );\n""",
    """    json.member( \"crafting_browser_batch_size\", crafting_browser_batch_size );\n    json.member( \"crafting_browser_focused_pane\", crafting_browser_focused_pane );\n    json.member( \"safemode_corner_menu_slots\", safemode_corner_menu_slots );\n    json.member( \"bionic_ui_sort_mode\", bionic_sort_mode );\n""",
)
replace_once(
    "src/inventory_ui.cpp",
    """    jo.read( \"crafting_browser_batch_size\", crafting_browser_batch_size );\n    jo.read( \"crafting_browser_focused_pane\", crafting_browser_focused_pane );\n    jo.read( \"bionic_ui_sort_mode\", bionic_sort_mode );\n""",
    """    jo.read( \"crafting_browser_batch_size\", crafting_browser_batch_size );\n    jo.read( \"crafting_browser_focused_pane\", crafting_browser_focused_pane );\n    jo.read( \"safemode_corner_menu_slots\", safemode_corner_menu_slots );\n    if( safemode_corner_menu_slots.size() != 5 ) {\n        safemode_corner_menu_slots.resize( 5 );\n    }\n    jo.read( \"bionic_ui_sort_mode\", bionic_sort_mode );\n""",
)

# Replace the process-local action array with helpers backed by uistate strings.
replace_once(
    "src/game.cpp",
    """#include <algorithm>\n#include <array>\n#include <bitset>\n""",
    """#include <algorithm>\n#include <bitset>\n""",
)
replace_once(
    "src/game.cpp",
    """static constexpr int safemode_corner_button_count = 6;\nstatic constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;\nstatic std::array<action_id, safemode_corner_safe_index> safemode_corner_menu_slots{};\n\nstruct safemode_corner_menu_candidate {\n""",
    """static constexpr int safemode_corner_button_count = 6;\nstatic constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;\n\nstatic action_id safemode_corner_menu_slot_action( const int index )\n{\n    if( index < 0 || index >= safemode_corner_safe_index ||\n        index >= static_cast<int>( uistate.safemode_corner_menu_slots.size() ) ) {\n        return ACTION_NULL;\n    }\n    return look_up_action( uistate.safemode_corner_menu_slots[index] );\n}\n\nstatic void assign_safemode_corner_menu_slot( const int index, const action_id action )\n{\n    if( index < 0 || index >= safemode_corner_safe_index ) {\n        return;\n    }\n    if( uistate.safemode_corner_menu_slots.size() != safemode_corner_safe_index ) {\n        uistate.safemode_corner_menu_slots.resize( safemode_corner_safe_index );\n    }\n    uistate.safemode_corner_menu_slots[index] = action_ident( action );\n}\n\nstruct safemode_corner_menu_candidate {\n""",
)
replace_once(
    "src/game.cpp",
    """            const std::string icon = is_safe ? \"[!]\" :\n                                     safemode_corner_action_icon( safemode_corner_menu_slots[i] );\n""",
    """            const std::string icon = is_safe ? \"[!]\" :\n                                     safemode_corner_action_icon( safemode_corner_menu_slot_action( i ) );\n""",
)
replace_once(
    "src/game.cpp",
    """                    if( i < safemode_corner_safe_index ) {\n                        if( safemode_corner_menu_slots[i] != ACTION_NULL ) {\n                            return safemode_corner_menu_slots[i];\n                        }\n                        const std::optional<action_id> selected = query_safemode_corner_menu();\n                        if( selected ) {\n                            safemode_corner_menu_slots[i] = *selected;\n                        }\n""",
    """                    if( i < safemode_corner_safe_index ) {\n                        const action_id assigned = safemode_corner_menu_slot_action( i );\n                        if( assigned != ACTION_NULL ) {\n                            return assigned;\n                        }\n                        const std::optional<action_id> selected = query_safemode_corner_menu();\n                        if( selected ) {\n                            assign_safemode_corner_menu_slot( i, *selected );\n                        }\n""",
)

subprocess.run(["git", "diff", "--check"], check=True)
