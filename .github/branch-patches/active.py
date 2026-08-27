from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")

old = '''    const ui_action_result result = editor_toolbar_strip.handle_input( action, pos );
    if( result.type == ui_action_result_type::ignored ) {
        return true;
    }
'''
new = '''    const ui_action_result result = editor_toolbar_strip.handle_input( action, pos );
    if( result.type == ui_action_result_type::ignored ) {
        // Pointer position must not make the toolbar consume unrelated keyboard
        // actions.  In particular QUIT/Escape must continue to the active modal
        // (refuel/reshape/etc.) and then to do_main_loop().  Only an actual mouse
        // selection on blank toolbar space is intentionally swallowed here.
        return action == "SELECT";
    }
'''

count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one toolbar ignored-result block, found {count}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix toolbar Escape input routing\n", encoding="utf-8"
)
