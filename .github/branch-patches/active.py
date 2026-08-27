from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_all(path: str, old: str, new: str, expected: int, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} anchors, found {count}")
    p.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "src/veh_interact.h",
    '''        ui_scroll_model part_scroll;\n        ui_scroll_model part_detail_scroll;\n        scrollbar part_scrollbar;\n        scrollbar part_detail_scrollbar;\n''',
    '''        ui_scroll_model part_scroll;\n        ui_scroll_model part_detail_scroll;\n        ui_scroll_model message_scroll;\n        scrollbar part_scrollbar;\n        scrollbar part_detail_scrollbar;\n        scrollbar message_scrollbar;\n''',
    "message scroll helper members",
)
replace_once(
    "src/veh_interact.h",
    '''        /* starting offset for installation scrolling */\n        int w_msg_scroll_offset = 0;\n''',
    '''        /* Requirement/status message scrolling is owned by message_scroll. */\n''',
    "remove legacy message page offset",
)

replace_once(
    "src/veh_interact.cpp",
    '''    part_scrollbar.debug_name( "vehicle.parts" );\n    part_detail_scrollbar.debug_name( "vehicle.details" );\n    install_scrollbar.debug_name( "vehicle.install" );\n''',
    '''    part_scrollbar.debug_name( "vehicle.parts" );\n    part_detail_scrollbar.debug_name( "vehicle.details" );\n    message_scrollbar.debug_name( "vehicle.message" );\n    install_scrollbar.debug_name( "vehicle.install" );\n''',
    "message scrollbar diagnostics",
)

replace_once(
    "src/veh_interact.cpp",
    '''                    const int page_height = std::max( 1, height - 1 );\n                    const int pages = static_cast<int>( buffer.size() / page_height );\n                    w_msg_scroll_offset = clamp( w_msg_scroll_offset, 0, pages );\n                    for( int line = 0; line < height; ++line ) {\n                        const int idx = w_msg_scroll_offset * page_height + line;\n                        if( static_cast<size_t>( idx ) >= buffer.size() ) {\n                            break;\n                        }\n                        nc_color dummy = c_unset;\n                        print_colored_text( w_msg, point( 1, line ), dummy, c_unset, buffer[idx] );\n                    }\n''',
    '''                    message_scroll.set_content_size( static_cast<int>( buffer.size() ) )\n                    .set_viewport_size( std::max( 1, height ) );\n                    for( int line = 0; line < height; ++line ) {\n                        const std::optional<int> idx = message_scroll.index_at_viewport_row( line );\n                        if( !idx ) {\n                            break;\n                        }\n                        nc_color dummy = c_unset;\n                        print_colored_text( w_msg, point( 1, line ), dummy, c_unset, buffer[*idx] );\n                    }\n                    message_scrollbar.offset_x( std::max( 0, getmaxx( w_msg ) - 1 ) ).offset_y( 0 )\n                    .model( message_scroll ).apply( w_msg );\n''',
    "message pane helper scrolling draw",
)

replace_once(
    "src/veh_interact.cpp",
    '''            if( action == "DESC_LIST_DOWN" ) {\n                ++w_msg_scroll_offset;\n                continue;\n            }\n            if( action == "DESC_LIST_UP" ) {\n                w_msg_scroll_offset = std::max( 0, w_msg_scroll_offset - 1 );\n                continue;\n            }\n''',
    '''            if( action == "DESC_LIST_DOWN" ) {\n                message_scroll.page_by( 1 );\n                continue;\n            }\n            if( action == "DESC_LIST_UP" ) {\n                message_scroll.page_by( -1 );\n                continue;\n            }\n''',
    "message pane keyboard scrolling",
)

replace_once(
    "src/veh_interact.cpp",
    '''    if( install_info && install_scrollbar.handle_input( action, main_context, install_info->scroll ) ) {\n        return true;\n    }\n''',
    '''    if( msg.has_value() && message_scrollbar.handle_input( action, main_context, message_scroll ) ) {\n        return true;\n    }\n    if( install_info && install_scrollbar.handle_input( action, main_context, install_info->scroll ) ) {\n        return true;\n    }\n''',
    "message scrollbar input routing",
)

replace_once(
    "src/veh_interact.cpp",
    '''        if( install_info && details_pos ) {\n            w_msg_scroll_offset = std::max( 0, w_msg_scroll_offset + direction );\n            return true;\n        }\n        if( !install_info && parts_pos ) {\n            scroll_part_inspector( direction );\n            return true;\n        }\n        if( !install_info && details_pos ) {\n            scroll_part_details( direction );\n            return true;\n        }\n''',
    '''        if( details_pos && msg.has_value() ) {\n            message_scroll.scroll_by( direction );\n            return true;\n        }\n        if( !install_info && parts_pos ) {\n            scroll_part_inspector( direction );\n            return true;\n        }\n        if( !install_info && details_pos ) {\n            scroll_part_details( direction );\n            return true;\n        }\n''',
    "message pane free wheel scrolling",
)

replace_all(
    "src/veh_interact.cpp",
    '''w_msg_scroll_offset = 0;''',
    '''message_scroll.scroll_to_start();''',
    7,
    "message scroll resets",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Move vehicle message scrolling onto UI helpers\n", encoding="utf-8"
)
