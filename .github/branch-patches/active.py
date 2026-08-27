from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Shared scrollbar diagnostic name, so logs identify the concrete caller.
replace_once(
    "src/ui_helpers/primitive/scrollbar.h",
    '''        // visual scrollbar height in terminal rows; defaults to viewport_size\n        scrollbar &height( int rows );\n        // window border color\n''',
    '''        // visual scrollbar height in terminal rows; defaults to viewport_size\n        scrollbar &height( int rows );\n        // diagnostic label written by shared scrollbar input tracing\n        scrollbar &debug_name( std::string name );\n        // window border color\n''',
    "scrollbar debug-name API",
)
replace_once(
    "src/ui_helpers/primitive/scrollbar.h",
    '''        int content_size_v, viewport_pos_v, viewport_size_v, drawn_height_v;\n        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;\n''',
    '''        int content_size_v, viewport_pos_v, viewport_size_v, drawn_height_v;\n        std::string debug_name_v;\n        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;\n''',
    "scrollbar debug-name member",
)

replace_once(
    "src/ui_helpers/primitive/scrollbar.cpp",
    '''#include "../../cata_utility.h"\n#include "../../input_context.h"\n''',
    '''#include "../../cata_utility.h"\n#include "../../debug.h"\n#include "../../input_context.h"\n''',
    "scrollbar debug include",
)
replace_once(
    "src/ui_helpers/primitive/scrollbar.cpp",
    '''scrollbar &scrollbar::height( int rows )\n{\n    drawn_height_v = std::max( 0, rows );\n    return *this;\n}\n\n''',
    '''scrollbar &scrollbar::height( int rows )\n{\n    drawn_height_v = std::max( 0, rows );\n    return *this;\n}\n\nscrollbar &scrollbar::debug_name( std::string name )\n{\n    debug_name_v = std::move( name );\n    return *this;\n}\n\n''',
    "scrollbar debug-name setter",
)

old_handle = '''bool scrollbar::handle_input( const std::string &action, const input_context &ctxt,\n                              ui_scroll_model &state )\n{\n    int position = state.viewport_pos();\n    const std::optional<point> text_coord = ctxt.get_coordinates_text( catacurses::stdscr );\n    const bool owns_pointer = text_coord && scrollbar_area.contains( *text_coord );\n#if defined(TILES)\n    if( pixel_thumb_area ) {\n        // Pixel coordinates refine vertical position only after the normal cell\n        // hitbox has established ownership. This prevents scaling/window-origin\n        // discrepancies from turning an ordinary list click into a scrollbar jump.\n        if( !dragging && !owns_pointer ) {\n            return false;\n        }\n        const bool handled = handle_pixel_dragging( action, ctxt.get_coordinates_pixel(), position );\n        if( handled ) {\n            state.set_viewport_pos( position );\n        }\n        return handled;\n    }\n#endif\n    if( !dragging && !owns_pointer ) {\n        return false;\n    }\n    const bool handled = handle_dragging( action, text_coord, position );\n    if( handled ) {\n        state.set_viewport_pos( position );\n    }\n    return handled;\n}\n'''
new_handle = '''bool scrollbar::handle_input( const std::string &action, const input_context &ctxt,\n                              ui_scroll_model &state )\n{\n    const int viewport_before = state.viewport_pos();\n    int position = viewport_before;\n    const std::optional<point> text_coord = ctxt.get_coordinates_text( catacurses::stdscr );\n    const bool owns_pointer = text_coord && scrollbar_area.contains( *text_coord );\n    const bool dragging_before = dragging;\n    const bool trace_event = action == "SELECT" || action == "CLICK_AND_DRAG" ||\n                             ( dragging && action == "MOUSE_MOVE" );\n#if defined(TILES)\n    const std::optional<point> pixel_coord = ctxt.get_coordinates_pixel();\n#endif\n\n    if( trace_event ) {\n        DebugLog( D_INFO, D_MAIN ) << "[UI_SCROLLBAR] input name="\n                                  << ( debug_name_v.empty() ? "unnamed" : debug_name_v )\n                                  << " action=" << action\n                                  << " viewport=" << viewport_before\n                                  << " content=" << content_size_v\n                                  << " visible=" << viewport_size_v\n                                  << " drawn_height=" << drawn_height_v\n                                  << " dragging=" << dragging_before\n                                  << " owns_cell=" << owns_pointer\n                                  << " cell="\n                                  << ( text_coord ? string_format( "(%d,%d)", text_coord->x, text_coord->y ) : "none" )\n                                  << " cell_area=(" << scrollbar_area.p_min.x << "," << scrollbar_area.p_min.y\n                                  << ")-(" << scrollbar_area.p_max.x << "," << scrollbar_area.p_max.y << ")"\n                                  << " cell_thumb="\n                                  << ( thumb_area ? string_format( "(%d,%d)-(%d,%d)", thumb_area->p_min.x,\n                                          thumb_area->p_min.y, thumb_area->p_max.x, thumb_area->p_max.y ) : "none" );\n#if defined(TILES)\n        DebugLog( D_INFO, D_MAIN ) << "[UI_SCROLLBAR] pixel name="\n                                  << ( debug_name_v.empty() ? "unnamed" : debug_name_v )\n                                  << " action=" << action\n                                  << " pixel="\n                                  << ( pixel_coord ? string_format( "(%d,%d)", pixel_coord->x, pixel_coord->y ) : "none" )\n                                  << " pixel_area=(" << pixel_scrollbar_area.p_min.x << ","\n                                  << pixel_scrollbar_area.p_min.y << ")-(" << pixel_scrollbar_area.p_max.x << ","\n                                  << pixel_scrollbar_area.p_max.y << ")"\n                                  << " pixel_track=(" << pixel_track_area.p_min.x << ","\n                                  << pixel_track_area.p_min.y << ")-(" << pixel_track_area.p_max.x << ","\n                                  << pixel_track_area.p_max.y << ")"\n                                  << " pixel_thumb="\n                                  << ( pixel_thumb_area ? string_format( "(%d,%d)-(%d,%d)",\n                                          pixel_thumb_area->p_min.x, pixel_thumb_area->p_min.y,\n                                          pixel_thumb_area->p_max.x, pixel_thumb_area->p_max.y ) : "none" );\n#endif\n    }\n\n    bool handled = false;\n#if defined(TILES)\n    if( pixel_thumb_area ) {\n        // Pixel coordinates refine vertical position only after the normal cell\n        // hitbox has established ownership. This prevents scaling/window-origin\n        // discrepancies from turning an ordinary list click into a scrollbar jump.\n        if( dragging || owns_pointer ) {\n            handled = handle_pixel_dragging( action, pixel_coord, position );\n        }\n    } else\n#endif\n    if( dragging || owns_pointer ) {\n        handled = handle_dragging( action, text_coord, position );\n    }\n\n    if( handled ) {\n        state.set_viewport_pos( position );\n    }\n    if( trace_event || ( handled && state.viewport_pos() != viewport_before ) ) {\n        DebugLog( D_INFO, D_MAIN ) << "[UI_SCROLLBAR] result name="\n                                  << ( debug_name_v.empty() ? "unnamed" : debug_name_v )\n                                  << " action=" << action\n                                  << " handled=" << handled\n                                  << " dragging=" << dragging_before << "->" << dragging\n                                  << " viewport=" << viewport_before << "->" << state.viewport_pos();\n    }\n    return handled;\n}\n'''
replace_once(
    "src/ui_helpers/primitive/scrollbar.cpp",
    old_handle,
    new_handle,
    "scrollbar input trace",
)

# Give crafting scrollbars stable names and log the semantic row selected by a list click.
replace_once(
    "src/crafting_gui.cpp",
    '''    scrollbar recipe_scrollbar;\n    scrollbar inspector_scrollbar;\n    recipe_scrollbar.set_draggable( ctxt );\n    inspector_scrollbar.set_draggable( ctxt );\n''',
    '''    scrollbar recipe_scrollbar;\n    scrollbar inspector_scrollbar;\n    recipe_scrollbar.debug_name( "crafting.recipes" ).set_draggable( ctxt );\n    inspector_scrollbar.debug_name( "crafting.inspector" ).set_draggable( ctxt );\n''',
    "crafting scrollbar debug names",
)
replace_once(
    "src/crafting_gui.cpp",
    '''                if( hit && *hit >= 0 && *hit < static_cast<int>( recipe_rows.size() ) &&\n                    recipe_rows[*hit].rec != nullptr ) {\n                    const browser_list_row &clicked_row = recipe_rows[*hit];\n                    const recipe *clicked = clicked_row.rec;\n                    const bool double_click = state.recipe_clicks.click( clicked );\n                    const int viewport_before_click = state.recipe_scroll.viewport_pos();\n                    select_index( clicked_row.recipe_index, true );\n                    state.recipe_scroll.set_viewport_pos( viewport_before_click );\n''',
    '''                if( hit && *hit >= 0 && *hit < static_cast<int>( recipe_rows.size() ) &&\n                    recipe_rows[*hit].rec != nullptr ) {\n                    const browser_list_row &clicked_row = recipe_rows[*hit];\n                    const recipe *clicked = clicked_row.rec;\n                    const bool double_click = state.recipe_clicks.click( clicked );\n                    const int viewport_before_click = state.recipe_scroll.viewport_pos();\n                    DebugLog( D_INFO, D_MAIN ) << "[CRAFTING_MOUSE] row-hit local=("\n                                              << recipes_pos->x << "," << recipes_pos->y << ")"\n                                              << " rendered_row=" << *hit\n                                              << " recipe_index=" << clicked_row.recipe_index\n                                              << " recipe=" << clicked->ident().str()\n                                              << " viewport_before=" << viewport_before_click;\n                    select_index( clicked_row.recipe_index, true );\n                    const int viewport_after_select = state.recipe_scroll.viewport_pos();\n                    state.recipe_scroll.set_viewport_pos( viewport_before_click );\n                    DebugLog( D_INFO, D_MAIN ) << "[CRAFTING_MOUSE] row-selected recipe="\n                                              << clicked->ident().str()\n                                              << " viewport_after_select=" << viewport_after_select\n                                              << " restored=" << state.recipe_scroll.viewport_pos();\n''',
    "crafting row click trace",
)

# Name the persistent vehicle scrollbars. No behavior changes here.
replace_once(
    "src/veh_interact.cpp",
    '''    main_context.register_action( "HELP_KEYBINDINGS" );\n    main_context.register_action( "FILTER" );\n    part_scrollbar.set_draggable( main_context );\n''',
    '''    main_context.register_action( "HELP_KEYBINDINGS" );\n    main_context.register_action( "FILTER" );\n    part_scrollbar.debug_name( "vehicle.parts" );\n    part_detail_scrollbar.debug_name( "vehicle.details" );\n    reshape_scrollbar.debug_name( "vehicle.reshape" );\n    part_scrollbar.set_draggable( main_context );\n''',
    "vehicle scrollbar debug names",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Add targeted scrollbar interaction diagnostics\n", encoding="utf-8"
)
