from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/veh_interact.h",
    '''        scrollbar part_scrollbar;\n        scrollbar part_detail_scrollbar;\n        scrollbar reshape_scrollbar;\n''',
    '''        scrollbar part_scrollbar;\n        scrollbar part_detail_scrollbar;\n        scrollbar install_scrollbar;\n        scrollbar reshape_scrollbar;\n''',
    "install scrollbar member",
)

replace_once(
    "src/veh_interact.cpp",
    '''    part_scrollbar.debug_name( "vehicle.parts" );\n    part_detail_scrollbar.debug_name( "vehicle.details" );\n    reshape_scrollbar.debug_name( "vehicle.reshape" );\n''',
    '''    part_scrollbar.debug_name( "vehicle.parts" );\n    part_detail_scrollbar.debug_name( "vehicle.details" );\n    install_scrollbar.debug_name( "vehicle.install" );\n    reshape_scrollbar.debug_name( "vehicle.reshape" );\n''',
    "install scrollbar diagnostics",
)

replace_once(
    "src/veh_interact.cpp",
    '''struct veh_interact::install_info_t {\n    int pos = 0;\n    std::vector<const vpart_info *> tab_vparts;\n''',
    '''struct veh_interact::install_info_t {\n    int pos = 0;\n    ui_scroll_model scroll;\n    std::vector<const vpart_info *> tab_vparts;\n''',
    "install scroll model",
)

replace_once(
    "src/veh_interact.cpp",
    '''    install_info->pos = 0;\n    if( !previous_id.empty() ) {\n        const auto found = std::find_if( candidates.begin(), candidates.end(),\n        [&]( const vpart_info *part ) {\n            return part->id.str() == previous_id;\n        } );\n        if( found != candidates.end() ) {\n            install_info->pos = static_cast<int>( std::distance( candidates.begin(), found ) );\n        }\n    }\n    install_info->dirty = false;\n''',
    '''    install_info->scroll.set_content_size( static_cast<int>( candidates.size() ) );\n    install_info->pos = 0;\n    if( !previous_id.empty() ) {\n        const auto found = std::find_if( candidates.begin(), candidates.end(),\n        [&]( const vpart_info *part ) {\n            return part->id.str() == previous_id;\n        } );\n        if( found != candidates.end() ) {\n            install_info->pos = static_cast<int>( std::distance( candidates.begin(), found ) );\n        }\n    }\n    install_info->scroll.ensure_visible( install_info->pos );\n    install_info->dirty = false;\n''',
    "install candidate scroll sync",
)

replace_once(
    "src/veh_interact.cpp",
    '''    install_info->pos = std::clamp( install_info->pos, 0,\n                                    static_cast<int>( candidates.size() ) - 1 );\n    const std::string old_id = sel_vpart_info != nullptr ? sel_vpart_info->id.str() : std::string();\n''',
    '''    install_info->pos = std::clamp( install_info->pos, 0,\n                                    static_cast<int>( candidates.size() ) - 1 );\n    install_info->scroll.set_content_size( static_cast<int>( candidates.size() ) )\n    .ensure_visible( install_info->pos );\n    const std::string old_id = sel_vpart_info != nullptr ? sel_vpart_info->id.str() : std::string();\n''',
    "install selection visibility",
)

replace_once(
    "src/veh_interact.cpp",
    '''    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n''',
    '''    if( install_info && install_scrollbar.handle_input( action, main_context, install_info->scroll ) ) {\n        return true;\n    }\n\n    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n''',
    "install scrollbar input routing",
)

replace_once(
    "src/veh_interact.cpp",
    '''            constexpr int first_row = 4;\n            if( list_pos->y >= first_row ) {\n                const int lines_per_page = std::max( 1, getmaxy( w_list ) - first_row );\n                const int page = install_info->pos / lines_per_page;\n                const int row = page * lines_per_page + list_pos->y - first_row;\n                if( row >= 0 && row < static_cast<int>( install_info->tab_vparts.size() ) ) {\n''',
    '''            constexpr int first_row = 4;\n            if( list_pos->y >= first_row ) {\n                const std::optional<int> clicked_index =\n                    install_info->scroll.index_at_viewport_row( list_pos->y - first_row );\n                if( clicked_index ) {\n                    const int row = *clicked_index;\n''',
    "install row hit mapping",
)

replace_once(
    "src/veh_interact.cpp",
    '''        if( install_info && list_pos ) {\n            if( !install_info->tab_vparts.empty() ) {\n                install_info->pos = std::clamp(\n                                        install_info->pos + direction, 0,\n                                        static_cast<int>( install_info->tab_vparts.size() ) - 1 );\n                sync_install_selection( here );\n            }\n            return true;\n        }\n''',
    '''        if( install_info && list_pos ) {\n            install_info->scroll.scroll_by( direction );\n            return true;\n        }\n''',
    "install free wheel scrolling",
)

replace_once(
    "src/veh_interact.cpp",
    '''    const int lines_per_page = std::max( 1, height - first_row );\n    const size_t page = pos / lines_per_page;\n    const size_t begin = page * lines_per_page;\n\n    if( list.empty() && first_row < height ) {\n''',
    '''    const int lines_per_page = std::max( 1, height - first_row );\n    install_info->scroll.set_content_size( static_cast<int>( list.size() ) )\n    .set_viewport_size( lines_per_page );\n    const int begin = install_info->scroll.viewport_pos();\n\n    if( list.empty() && first_row < height ) {\n''',
    "install viewport draw model",
)

replace_once(
    "src/veh_interact.cpp",
    '''    for( size_t i = begin; i < begin + lines_per_page && i < list.size(); ++i ) {\n        const vpart_info &info = *list[i];\n        const vpart_variant &vv = info.variants.at( info.variant_default );\n        const int y = static_cast<int>( i - begin ) + first_row;\n''',
    '''    for( int i = begin; i < begin + lines_per_page && i < static_cast<int>( list.size() ); ++i ) {\n        const vpart_info &info = *list[i];\n        const vpart_variant &vv = info.variants.at( info.variant_default );\n        const int y = i - begin + first_row;\n''',
    "install viewport row loop",
)

replace_once(
    "src/veh_interact.cpp",
    '''        trim_and_print( w_list, point( 3, y ), std::max( 1, width - 4 ),\n                        pos == i ? hilite( col ) : col, label );\n    }\n\n    if( static_cast<int>( list.size() ) > lines_per_page ) {\n        scrollbar().offset_x( width - 1 ).offset_y( first_row )\n        .content_size( static_cast<int>( list.size() ) )\n        .viewport_pos( static_cast<int>( begin ) )\n        .viewport_size( lines_per_page ).apply( w_list );\n    }\n''',
    '''        trim_and_print( w_list, point( 3, y ), std::max( 1, width - 4 ),\n                        pos == static_cast<size_t>( i ) ? hilite( col ) : col, label );\n    }\n\n    install_scrollbar.offset_x( width - 1 ).offset_y( first_row )\n    .model( install_info->scroll ).apply( w_list );\n''',
    "install persistent scrollbar draw",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Move vehicle install scrolling onto UI helpers\n", encoding="utf-8"
)
