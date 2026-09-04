from pathlib import Path

cpp_path = Path("src/inventory_ui.cpp")
h_path = Path("src/inventory_ui.h")
helper_path = Path("src/ui_helpers/controls/grab_indicator.h")

cpp = cpp_path.read_text(encoding="utf-8")
hdr = h_path.read_text(encoding="utf-8")


def replace_exact(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    return text.replace(old, new)

cpp = replace_exact(cpp, '#include "ui_helpers/controls/grab_indicator.h"\n', '', 1,
                    "grab indicator include")

cpp = replace_exact(
    cpp,
    '''void inventory_selector::draw_grab_indicator()\n{\n    if( !grabbed_item ) {\n        return;\n    }\n    draw_ui_grab_item_indicator( w_inv, ctxt.get_coordinates_text( w_inv ), grabbed_item );\n}\n\nvoid inventory_selector::clear_grab_indicator()\n{\n    const bool was_active = static_cast<bool>( grabbed_item );\n    grabbed_item = item_location();\n    if( was_active ) {\n        clear_ui_grab_item_indicator();\n    }\n}\n\n''',
    '', 1, "grab indicator methods")

cpp = replace_exact(
    cpp,
    '''        current_ui->on_redraw( [this]( const ui_adaptor & ) {\n            refresh_window();\n            draw_grab_indicator();\n        } );\n''',
    '''        current_ui->on_redraw( [this]( const ui_adaptor & ) {\n            refresh_window();\n        } );\n''',
    1, "grab redraw hook")

cpp = replace_exact(
    cpp,
    '''inventory_selector::~inventory_selector()\n{\n    clear_grab_indicator();\n    item_name_cache_users--;\n''',
    '''inventory_selector::~inventory_selector()\n{\n    item_name_cache_users--;\n''',
    1, "grab teardown")

cpp = replace_exact(
    cpp,
    '''                    startDragItem = input.entry->locations.front();\n                    grabbed_item = startDragItem;\n''',
    '''                    startDragItem = input.entry->locations.front();\n''',
    2, "grab start state")

cpp = replace_exact(
    cpp,
    '''                startDragItem = item_location();\n                clear_grab_indicator();\n''',
    '''                startDragItem = item_location();\n''',
    2, "grab finish state")

hdr = replace_exact(
    hdr,
    '''\n        // Pointer-following feedback for the item currently owned by a drag.\n        // Kept on the selector rather than inferred from row highlight so a\n        // held item remains visually stable while the pointer crosses rows.\n        item_location grabbed_item;\n        void draw_grab_indicator();\n        void clear_grab_indicator();\n''',
    '', 1, "selector grab state")

if not helper_path.exists():
    raise RuntimeError("grab_indicator.h is already missing")
helper_path.unlink()

cpp_path.write_text(cpp, encoding="utf-8")
h_path.write_text(hdr, encoding="utf-8")

assert 'grab_indicator.h' not in cpp
assert 'grabbed_item' not in cpp
assert 'grabbed_item' not in hdr
assert not helper_path.exists()

Path("/tmp/branch_patch_commit_message").write_text(
    "Revert grabbed-item cursor indicator\n", encoding="utf-8"
)
