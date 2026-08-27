from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")

replacements = {
    "    // Match the editor's three zoom levels: 50%, 100%, and 150%.\n":
        "    // Match the editor's four zoom levels: 50%, 100%, 150%, and 200%.\n",
    "            const int new_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );\n":
        "            const int new_zoom = std::clamp( live_preview_zoom - direction, 1, 4 );\n",
    "            live_preview_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );\n":
        "            live_preview_zoom = std::clamp( live_preview_zoom - direction, 1, 4 );\n",
    "    if( result.type == ui_action_result_type::activated && result.entry ) {\n        pending_editor_action = result.entry->id;\n        close_editor_toolbar_dropdown();\n        return false;\n    }\n":
        "    if( result.type == ui_action_result_type::activated && result.entry ) {\n        pending_editor_action = result.entry->id;\n        close_editor_toolbar_dropdown();\n        // The selected action may immediately open another modal (Refuel, Rename, etc.).\n        // Repaint the retained editor now so the destroyed dropdown window cannot remain\n        // visually composited underneath that modal until the next input-loop frame.\n        if( ui ) {\n            ui->invalidate_ui();\n            ui_manager::redraw_invalidated();\n        }\n        return false;\n    }\n",
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one occurrence, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix vehicle live zoom and dropdown modal cleanup\n", encoding="utf-8"
)
