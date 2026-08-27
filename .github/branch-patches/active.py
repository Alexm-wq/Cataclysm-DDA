from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")

old = '''    if( action == "MOUSE_MOVE" && viewport_pos ) {
        if( viewport_pos->y == 0 ) {
            editor_view_strip.update_hover( viewport_pos );
        } else if( viewport_pos->y == 1 && !reshape_info ) {
            editor_layer_strip.update_hover( viewport_pos );
        }
    }
'''
new = '''    if( action == "MOUSE_MOVE" ) {
        // Each strip must see the cursor leave as well as enter.  Passing nullopt
        // clears the helper's transient hover while preserving the selected tab.
        editor_view_strip.update_hover( viewport_pos && viewport_pos->y == 0 ?
                                        viewport_pos : std::nullopt );
        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info ?
                                         viewport_pos : std::nullopt );
    }
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"layer hover anchor count: {count}")
text = text.replace(old, new, 1)

old = '''        open_editor_dropdown = editor_dropdown::none;
        open_editor_toolbar_menu( here, id );
        return pending_editor_action.empty();
    }
    if( id == "REPAIR" ) {
'''
new = '''        open_editor_dropdown = editor_dropdown::none;
        open_editor_toolbar_menu( here, id );
        return pending_editor_action.empty();
    }

    // Direct toolbar actions are mutually exclusive with every transient menu.
    // Close and repaint before dispatch because the action may immediately open
    // a retained overlay/modal (Refuel, Rename, etc.).  Otherwise the old dropdown
    // can remain visually composited underneath the new modal.
    const bool had_transient_menu = editor_context_open ||
                                    open_editor_dropdown != editor_dropdown::none ||
                                    !open_editor_toolbar_dropdown.empty();
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    close_editor_toolbar_dropdown();
    if( had_transient_menu && ui ) {
        ui->invalidate_ui();
        ui_manager::redraw_invalidated();
    }

    if( id == "REPAIR" ) {
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"toolbar direct action anchor count: {count}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix vehicle dropdown cleanup and stale layer hover\n", encoding="utf-8"
)
