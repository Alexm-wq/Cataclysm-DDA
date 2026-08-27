from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")

old = '''        // Refuel is a modal workflow and owns Escape before any transient
        // editor UI hidden behind it.  Otherwise a stale editor dropdown can
        // consume Esc and make the fuel window appear impossible to close.
        if( action == "QUIT" && refuel_info ) {
'''
new = '''        // The visible Back button is a semantic action, not keyboard Escape.
        // Back always leaves the current vehicle-editor surface in one click,
        // while Escape retains its layered cancel/dismiss behavior below.
        if( action == "EDITOR_BACK" ) {
            close_editor_context_menu();
            open_editor_dropdown = editor_dropdown::none;
            editor_filter_dropdown_menu.close();
            close_editor_toolbar_dropdown();
            if( reshape_info ) {
                close_reshape_mode();
                continue;
            }
            if( refuel_info ) {
                close_refuel_mode();
                continue;
            }
            if( install_info ) {
                close_install_mode();
                continue;
            }
            finish = true;
            continue;
        }

        // Refuel is a modal workflow and owns Escape before any transient
        // editor UI hidden behind it.  Otherwise a stale editor dropdown can
        // consume Esc and make the fuel window appear impossible to close.
        if( action == "QUIT" && refuel_info ) {
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"main-loop Back anchor count: {count}")
text = text.replace(old, new, 1)

old = '''    if( reshape_info ) {
        editor_toolbar_items.push_back( {
            ui_action_entry( _( "Back" ), "QUIT", true ), 4, ui_action_alignment::right
        } );
'''
new = '''    if( reshape_info ) {
        editor_toolbar_items.push_back( {
            ui_action_entry( _( "Back" ), "EDITOR_BACK", true ), 4, ui_action_alignment::right
        } );
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"reshape toolbar Back anchor count: {count}")
text = text.replace(old, new, 1)

old = '''    const toolbar_candidate back = direct( _( "Back" ), "QUIT", 4 );
'''
new = '''    const toolbar_candidate back = direct( _( "Back" ), "EDITOR_BACK", 4 );
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"normal toolbar Back anchor count: {count}")
text = text.replace(old, new, 1)

old = '''    if( result.type == ui_action_result_type::closed ) {
        close_editor_toolbar_dropdown();
        return false;
    }
'''
new = '''    if( result.type == ui_action_result_type::closed ) {
        close_editor_toolbar_dropdown();
        // Closing a toolbar dropdown is itself the completed action.  In
        // particular Escape must not fall through as QUIT and close the editor
        // on the same keypress.
        return true;
    }
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"toolbar dropdown close anchor count: {count}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Separate vehicle Back from Escape semantics\n", encoding="utf-8"
)
