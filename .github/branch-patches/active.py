from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''    const std::vector<Character *> crafting_group = crafter->get_crafting_group();\n    int crafter_i = find( crafting_group.begin(), crafting_group.end(), crafter ) -\n                    crafting_group.begin();\n''',
    '''    const std::vector<Character *> crafting_characters = crafter->get_crafting_group();\n    int crafter_i = find( crafting_characters.begin(), crafting_characters.end(), crafter ) -\n                    crafting_characters.begin();\n''',
    "modern crafting character vector",
)

text = replace_once(
    text,
    '''            const bool rec_valid = state.selected_recipe != nullptr;\n            const int new_crafter_i = choose_crafter( crafting_group, crafter_i,\n                                      state.selected_recipe, rec_valid );\n            if( new_crafter_i >= 0 && new_crafter_i != crafter_i ) {\n                crafter_i = new_crafter_i;\n                crafter = crafting_group[crafter_i];\n''',
    '''            const bool rec_valid = state.selected_recipe != nullptr;\n            const int new_crafter_i = choose_crafter( crafting_characters, crafter_i,\n                                      state.selected_recipe, rec_valid );\n            if( new_crafter_i >= 0 && new_crafter_i != crafter_i ) {\n                crafter_i = new_crafter_i;\n                crafter = crafting_characters[crafter_i];\n''',
    "modern crafter chooser",
)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix MSVC crafting group type shadowing\n", encoding="utf-8"
)
