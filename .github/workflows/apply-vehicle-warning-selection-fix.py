from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: {label}: expected 1 match, got {count}")
    path.write_text(text.replace(old, new, 1))


header = Path("src/veh_interact.h")
replace_once(
    header,
    '''        static void discard_persistent_editor();\n\n        /** Prompt for a part matching the selector function */\n''',
    '''        static void discard_persistent_editor();\n        /** Temporarily remove the retained editor while a game-level distraction query owns the screen. */\n        static void suspend_persistent_editor_for_query();\n        /** Restore the untouched retained editor after a distraction query continues the activity. */\n        static void restore_persistent_editor_after_query();\n\n        /** Prompt for a part matching the selector function */\n''',
    "persistent query hooks",
)

cpp = Path("src/veh_interact.cpp")
replace_once(
    cpp,
    '''void veh_interact::discard_persistent_editor()\n{\n    if( persistent_editor != nullptr ) {\n        delete persistent_editor;\n        persistent_editor = nullptr;\n    }\n}\n\nvoid veh_interact::begin_activity_handoff()\n''',
    '''void veh_interact::discard_persistent_editor()\n{\n    if( persistent_editor != nullptr ) {\n        delete persistent_editor;\n        persistent_editor = nullptr;\n    }\n}\n\nvoid veh_interact::suspend_persistent_editor_for_query()\n{\n    if( persistent_editor == nullptr || !persistent_editor->activity_handoff ||\n        persistent_editor->ui_hidden || !persistent_editor->ui ) {\n        return;\n    }\n\n    // Match the old modal-warning behavior without throwing away the persistent\n    // editor state.  The distraction popup should own a clean game frame, not\n    // be composited over a frozen editor/refuel overlay.\n    persistent_editor->ui_hidden = true;\n    persistent_editor->ui->mark_resize();\n    persistent_editor->ui->invalidate_ui();\n    g->invalidate_main_ui_adaptor();\n    ui_manager::redraw_invalidated();\n}\n\nvoid veh_interact::restore_persistent_editor_after_query()\n{\n    if( persistent_editor == nullptr || !persistent_editor->activity_handoff ||\n        !persistent_editor->ui_hidden || !persistent_editor->ui ) {\n        return;\n    }\n\n    // The query only suspended rendering; camera, selected mount/part, refuel\n    // stage, source selection, filters, and every other editor state remain\n    // untouched.  Repaint that exact frame if the activity continues.\n    persistent_editor->ui_hidden = false;\n    persistent_editor->ui->mark_resize();\n    persistent_editor->ui->set_disable_uis_below( true );\n    persistent_editor->ui->invalidate_ui();\n    ui_manager::redraw_invalidated();\n    persistent_editor->ui->set_disable_uis_below( false );\n    g->invalidate_main_ui_adaptor();\n}\n\nvoid veh_interact::begin_activity_handoff()\n''',
    "query suspend restore implementation",
)
replace_once(
    cpp,
    '''            nc_color color = source.selected ? c_light_cyan : c_light_gray;\n            if( index == refuel_info->source_pos ) {\n                color = hilite( color );\n            }\n            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );\n''',
    '''            // Match the unified inventory selection convention: both the active\n            // cursor row and every effective multi-selection get the blue hilite\n            // overlay.  Do not encode multi-selection as teal foreground text.\n            const bool selected = source.selected || index == refuel_info->source_pos;\n            const nc_color color = selected ? hilite( c_white ) : c_light_gray;\n            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );\n''',
    "inventory-style refuel selection highlight",
)

game = Path("src/game.cpp")
replace_once(
    game,
    '''    const std::string &action = query_popup()\n                                .preferred_keyboard_mode( keyboard_mode::keycode )\n                                .context( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" )\n''',
    '''    // Persistent vehicle editing intentionally survives ACT_VEHICLE, but a\n    // distraction warning must retain the old modal behavior: remove the editor\n    // while the warning owns the screen, then restore the exact frozen editor\n    // state only if the activity continues.  Cancellation destroys it normally.\n    veh_interact::suspend_persistent_editor_for_query();\n    on_out_of_scope restore_vehicle_editor_after_query( []() {\n        veh_interact::restore_persistent_editor_after_query();\n    } );\n\n    const std::string &action = query_popup()\n                                .preferred_keyboard_mode( keyboard_mode::keycode )\n                                .context( "CANCEL_ACTIVITY_OR_IGNORE_QUERY" )\n''',
    "distraction query editor suspension",
)

status = Path("doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md")
replace_once(
    status,
    '''- [x] The first post-activity editor frame uses the same temporary lower-UI redraw barrier pattern proven by the persistent inventory workspace, preventing a one-frame map flash while preserving normal activity timing and completion mechanics.\n''',
    '''- [x] The first post-activity editor frame uses the same temporary lower-UI redraw barrier pattern proven by the persistent inventory workspace, preventing a one-frame map flash while preserving normal activity timing and completion mechanics.\n- [x] Game-level distraction warnings temporarily suspend the retained editor so the warning gets the traditional clean game frame; Ignore/continue restores the exact frozen editor/refuel state, while cancellation follows normal retained-editor cleanup.\n''',
    "warning behavior status",
)

print("vehicle warning and refuel selection patch applied")
