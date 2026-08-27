from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")

old = '''    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );

    if( action == "MOUSE_MOVE" ) {
'''
new = '''    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );

    // Refuel is a true modal overlay.  Route every mouse action to it before the
    // toolbar, layer tabs, filters, inspector, or viewport can observe the event.
    // Keyboard actions intentionally fall through because handle_refuel_mouse()
    // returns false for them and do_main_loop() owns the modal keyboard path.
    if( refuel_info ) {
        if( action == "MOUSE_MOVE" ) {
            editor_view_strip.update_hover( std::nullopt );
            editor_layer_strip.update_hover( std::nullopt );
            editor_toolbar_strip.update_hover( std::nullopt );
        }
        return handle_refuel_mouse( here, action );
    }

    if( action == "MOUSE_MOVE" ) {
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"early refuel routing anchor count: {count}")
text = text.replace(old, new, 1)

old = '''    if( refuel_info ) {
        return handle_refuel_mouse( here, action );
    }
    if( reshape_info && handle_reshape_mouse( action ) ) {
'''
new = '''    if( reshape_info && handle_reshape_mouse( action ) ) {
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"late refuel routing anchor count: {count}")
text = text.replace(old, new, 1)

old = '''void veh_interact::do_refill( map &here )
{
    if( refuel_info ) {
        refresh_refuel_sources( here );
        return;
    }

    switch( cant_do( here, 'f' ) ) {
'''
new = '''void veh_interact::do_refill( map &here )
{
    if( refuel_info ) {
        refresh_refuel_sources( here );
        return;
    }

    // Entering a modal always owns the transient UI stack.  This is deliberately
    // repeated here rather than relying on a particular toolbar/dropdown caller,
    // so keyboard Refuel and every future entry path get identical cleanup.
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    editor_filter_dropdown_menu.close();
    close_editor_toolbar_dropdown();
    editor_view_strip.update_hover( std::nullopt );
    editor_layer_strip.update_hover( std::nullopt );
    editor_toolbar_strip.update_hover( std::nullopt );

    switch( cant_do( here, 'f' ) ) {
'''
count = text.count(old)
if count != 1:
    raise SystemExit(f"refuel entry cleanup anchor count: {count}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Make vehicle refuel overlay modal for mouse input\n", encoding="utf-8"
)
