from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Coordinates belong only to the input event that actually supplied them.
# Previously every returned action marked coordinate_input_received=true, so
# keyboard/non-mouse actions could expose a default/stale mouse_pos to controls.
replace_once(
    "src/input_context_base.cpp.inc",
    '''    next_action.type = input_event_t::error;\n    const std::string *result = &CATA_ERROR;\n    while( true ) {\n\n        next_action = inp_mngr.get_input_event( preferred_keyboard_mode );\n''',
    '''    next_action.type = input_event_t::error;\n    coordinate_input_received = false;\n    const std::string *result = &CATA_ERROR;\n    while( true ) {\n\n        next_action = inp_mngr.get_input_event( preferred_keyboard_mode );\n        coordinate_input_received = false;\n''',
    "reset coordinate validity",
)
replace_once(
    "src/input_context_base.cpp.inc",
    '''        coordinate_input_received = true;\n        coordinate = next_action.mouse_pos;\n\n        if( action != CATA_ERROR ) {\n''',
    '''        if( next_action.type == input_event_t::mouse ) {\n            coordinate_input_received = true;\n            coordinate = next_action.mouse_pos;\n        }\n\n        if( action != CATA_ERROR ) {\n''',
    "mouse-only coordinate validity",
)

# Pixel Y gives us smooth thumb precision, but it must never decide which
# control owns a click. Gate new scrollbar interactions with the established
# text-cell scrollbar rectangle first. Active drags retain pointer capture so
# they can continue if the cursor strays horizontally outside the column.
replace_once(
    "src/ui_helpers/primitive/scrollbar.cpp",
    '''bool scrollbar::handle_input( const std::string &action, const input_context &ctxt,\n                              ui_scroll_model &state )\n{\n    int position = state.viewport_pos();\n#if defined(TILES)\n    if( pixel_thumb_area ) {\n        const bool handled = handle_pixel_dragging( action, ctxt.get_coordinates_pixel(), position );\n        if( handled ) {\n            state.set_viewport_pos( position );\n        }\n        return handled;\n    }\n#endif\n    const bool handled = handle_dragging( action, ctxt.get_coordinates_text( catacurses::stdscr ),\n                                          position );\n''',
    '''bool scrollbar::handle_input( const std::string &action, const input_context &ctxt,\n                              ui_scroll_model &state )\n{\n    int position = state.viewport_pos();\n    const std::optional<point> text_coord = ctxt.get_coordinates_text( catacurses::stdscr );\n    const bool owns_pointer = text_coord && scrollbar_area.contains( *text_coord );\n#if defined(TILES)\n    if( pixel_thumb_area ) {\n        // Pixel coordinates refine vertical position only after the normal cell\n        // hitbox has established ownership. This prevents scaling/window-origin\n        // discrepancies from turning an ordinary list click into a scrollbar jump.\n        if( !dragging && !owns_pointer ) {\n            return false;\n        }\n        const bool handled = handle_pixel_dragging( action, ctxt.get_coordinates_pixel(), position );\n        if( handled ) {\n            state.set_viewport_pos( position );\n        }\n        return handled;\n    }\n#endif\n    if( !dragging && !owns_pointer ) {\n        return false;\n    }\n    const bool handled = handle_dragging( action, text_coord, position );\n''',
    "scrollbar cell ownership gate",
)

# Crafting hit regions identify the visual row actually drawn, not an index in
# the separately ordered recipe vector. Mouse selection preserves the viewport.
p = Path("src/crafting_gui.cpp")
text = p.read_text(encoding="utf-8")
old = '''                recipe_hits.add( inclusive_rectangle<point>( point( 1, y ),\n                                 point( list_width - 2, y ) ), recipe_index );\n'''
new = '''                recipe_hits.add( inclusive_rectangle<point>( point( 1, y ),\n                                 point( list_width - 2, y ) ), index );\n'''
if text.count(old) != 1:
    raise SystemExit(f"crafting visual hit payload: expected 1 anchor, found {text.count(old)}")
text = text.replace(old, new, 1)

old_hover = '''                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit && *hit >= 0 && *hit < static_cast<int>( current.size() ) ) {\n                    state.hovered_recipe = current[*hit];\n                }\n'''
new_hover = '''                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit && *hit >= 0 && *hit < static_cast<int>( recipe_rows.size() ) ) {\n                    state.hovered_recipe = recipe_rows[*hit].rec;\n                }\n'''
if text.count(old_hover) != 1:
    raise SystemExit(f"crafting hover visual row: expected 1 anchor, found {text.count(old_hover)}")
text = text.replace(old_hover, new_hover, 1)

old_select = '''                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit ) {\n                    const recipe *clicked = current[*hit];\n                    const bool double_click = state.recipe_clicks.click( clicked );\n                    select_index( *hit, true );\n                    if( double_click ) {\n                        action = "CONFIRM";\n                    }\n                    handled = true;\n                }\n'''
new_select = '''                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit && *hit >= 0 && *hit < static_cast<int>( recipe_rows.size() ) &&\n                    recipe_rows[*hit].rec != nullptr ) {\n                    const browser_list_row &clicked_row = recipe_rows[*hit];\n                    const recipe *clicked = clicked_row.rec;\n                    const bool double_click = state.recipe_clicks.click( clicked );\n                    const int viewport_before_click = state.recipe_scroll.viewport_pos();\n                    select_index( clicked_row.recipe_index, true );\n                    state.recipe_scroll.set_viewport_pos( viewport_before_click );\n                    if( double_click ) {\n                        action = "CONFIRM";\n                    }\n                    handled = true;\n                }\n'''
if text.count(old_select) != 1:
    raise SystemExit(f"crafting mouse selection: expected 1 anchor, found {text.count(old_select)}")
text = text.replace(old_select, new_select, 1)

old_secondary = '''                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit ) {\n                    select_index( *hit, false );\n                    state.context_open = true;\n                    state.context_pos = *recipes_pos;\n                }\n'''
new_secondary = '''                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit && *hit >= 0 && *hit < static_cast<int>( recipe_rows.size() ) &&\n                    recipe_rows[*hit].rec != nullptr ) {\n                    const int viewport_before_click = state.recipe_scroll.viewport_pos();\n                    select_index( recipe_rows[*hit].recipe_index, false );\n                    state.recipe_scroll.set_viewport_pos( viewport_before_click );\n                    state.context_open = true;\n                    state.context_pos = *recipes_pos;\n                }\n'''
if text.count(old_secondary) != 1:
    raise SystemExit(f"crafting secondary selection: expected 1 anchor, found {text.count(old_secondary)}")
text = text.replace(old_secondary, new_secondary, 1)
p.write_text(text, encoding="utf-8")

# Shape clicks target already-visible entries and therefore must not recenter.
replace_once(
    "src/veh_interact.cpp",
    '''            const bool double_click = reshape_info->double_click.click(\n                                          reshape_info->variants[index] );\n            preview_reshape_variant( index );\n            if( double_click ) {\n''',
    '''            const bool double_click = reshape_info->double_click.click(\n                                          reshape_info->variants[index] );\n            const int viewport_before_click = reshape_info->variant_scroll.viewport_pos();\n            preview_reshape_variant( index );\n            reshape_info->variant_scroll.set_viewport_pos( viewport_before_click );\n            if( double_click ) {\n''',
    "reshape click preserves viewport",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Stabilize scrollbar click ownership and list selection\n", encoding="utf-8"
)

# Retry after a transient GitHub push failure; source transformation unchanged.
