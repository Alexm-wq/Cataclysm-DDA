from pathlib import Path

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
old = '''static int safemode_corner_visible_menu_slot_count()\n{\n    int last_assigned = -1;\n    for( int i = static_cast<int>( uistate.safemode_corner_menu_slots.size() ) - 1; i >= 0; --i ) {\n        if( safemode_corner_menu_slot_action( i ) != ACTION_NULL ) {\n            last_assigned = i;\n            break;\n        }\n    }\n    return std::max( safemode_corner_base_slot_count, last_assigned + 2 );\n}\n'''
new = '''static int safemode_corner_visible_menu_slot_count()\n{\n    // The original five slots are always present. Do not grow the palette until\n    // every one of them has actually been assigned.\n    for( int i = 0; i < safemode_corner_base_slot_count; ++i ) {\n        if( safemode_corner_menu_slot_action( i ) == ACTION_NULL ) {\n            return safemode_corner_base_slot_count;\n        }\n    }\n\n    // Once the base column is full, retain any persisted extra assignments and\n    // expose exactly one additional empty slot after the highest assigned extra.\n    int last_assigned = safemode_corner_base_slot_count - 1;\n    for( int i = static_cast<int>( uistate.safemode_corner_menu_slots.size() ) - 1;\n         i >= safemode_corner_base_slot_count; --i ) {\n        if( safemode_corner_menu_slot_action( i ) != ACTION_NULL ) {\n            last_assigned = i;\n            break;\n        }\n    }\n    return last_assigned + 2;\n}\n'''
if text.count(old) != 1:
    raise SystemExit("expected shortcut visibility block not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
