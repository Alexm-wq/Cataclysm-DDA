from pathlib import Path

cpp_path = Path("src/veh_interact.cpp")
hdr_path = Path("src/veh_interact.h")
cpp = cpp_path.read_text()
hdr = hdr_path.read_text()

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)

hdr = replace_once(
    hdr,
    """        bool install_available_materials_only_cache = false;
        std::string install_selected_part_cache;
""",
    """        bool install_available_materials_only_cache = false;
        bool install_show_all_cache = false;
        std::string install_selected_part_cache;
""",
    "show-all cache field",
)

cpp = replace_once(
    cpp,
    """    bool available_materials_only = false;
    bool dirty = true;
""",
    """    bool available_materials_only = false;
    bool show_all = false;
    bool dirty = true;
""",
    "show-all install state",
)

cpp = replace_once(
    cpp,
    """        install_info->filter = install_search_cache;
        install_info->available_materials_only = install_available_materials_only_cache;
""",
    """        install_info->filter = install_search_cache;
        install_info->available_materials_only = install_available_materials_only_cache;
        install_info->show_all = install_show_all_cache;
""",
    "restore show-all state",
)

cpp = replace_once(
    cpp,
    """        if( !veh->can_mount( selected_mount(), *part ).success() ) {
            continue;
        }
""",
    """        if( !install_info->show_all && !veh->can_mount( selected_mount(), *part ).success() ) {
            continue;
        }
""",
    "show incompatible candidates",
)

cpp = replace_once(
    cpp,
    """        install_available_materials_only_cache = install_info->available_materials_only;
        if( sel_vpart_info != nullptr ) {
""",
    """        install_available_materials_only_cache = install_info->available_materials_only;
        install_show_all_cache = install_info->show_all;
        if( sel_vpart_info != nullptr ) {
""",
    "cache show-all state",
)

cpp = replace_once(
    cpp,
    """        const bool has_install_for_layer = std::any_of( can_mount.begin(), can_mount.end(),
        [&]( const vpart_info *info ) {
            return info != nullptr && part_info_matches_layer( *info );
        } );
        add_entry( _( "Install…" ), "EDITOR_INSTALL", has_install_for_layer,
                   _( "No parts for the selected layer can be installed at this mount." ) );
""",
    """        add_entry( _( "Install…" ), "EDITOR_INSTALL" );
""",
    "always-open install context action",
)

old_handler = """            if( list_pos->y == 2 ) {
                if( list_pos->x >= close_x ) {
                    close_install_mode();
                    return true;
                }
                if( list_pos->x >= install_x && list_pos->x < close_x ) {
                    confirm_install( here );
                    return true;
                }
                install_info->available_materials_only = !install_info->available_materials_only;
                install_available_materials_only_cache = install_info->available_materials_only;
                install_info->pos = 0;
                install_info->dirty = true;
                refresh_install_candidates();
                sync_install_selection( here );
                return true;
            }
"""
new_handler = """            if( list_pos->y == 2 ) {
                if( list_pos->x >= close_x ) {
                    close_install_mode();
                    return true;
                }
                if( list_pos->x >= install_x && list_pos->x < close_x ) {
                    confirm_install( here );
                    return true;
                }

                const std::string availability_label = install_info->available_materials_only ?
                                                       _( "[x] Materials" ) : _( "[ ] Materials" );
                const std::string show_all_label = install_info->show_all ?
                                                   _( "[x] Show all" ) : _( "[ ] Show all" );
                const int availability_x = 1;
                const int show_all_x = availability_x + utf8_width( availability_label ) + 1;
                if( list_pos->x >= availability_x &&
                    list_pos->x < availability_x + utf8_width( availability_label ) ) {
                    install_info->available_materials_only = !install_info->available_materials_only;
                    install_available_materials_only_cache = install_info->available_materials_only;
                } else if( list_pos->x >= show_all_x &&
                           list_pos->x < show_all_x + utf8_width( show_all_label ) ) {
                    install_info->show_all = !install_info->show_all;
                    install_show_all_cache = install_info->show_all;
                } else {
                    return true;
                }
                install_info->pos = 0;
                install_info->dirty = true;
                refresh_install_candidates();
                sync_install_selection( here );
                return true;
            }
"""
cpp = replace_once(cpp, old_handler, new_handler, "install toggle mouse handling")

old_display = """    const std::string availability = install_info->available_materials_only ?
                                     _( "[x] Available materials only" ) :
                                     _( "[ ] Available materials only" );
    trim_and_print( w_list, point( 1, 2 ), std::max( 1, install_x - 2 ), c_light_cyan, availability );
    trim_and_print( w_list, point( install_x, 2 ), install_width,
                    install_info->selected_can_install ? c_light_green : c_dark_gray, install_button );
"""
new_display = """    const std::string availability = install_info->available_materials_only ?
                                     _( "[x] Materials" ) : _( "[ ] Materials" );
    const std::string show_all = install_info->show_all ?
                                 _( "[x] Show all" ) : _( "[ ] Show all" );
    const int show_all_x = 1 + utf8_width( availability ) + 1;
    trim_and_print( w_list, point( 1, 2 ), std::max( 1, install_x - 2 ), c_light_cyan, availability );
    if( show_all_x < install_x - 1 ) {
        trim_and_print( w_list, point( show_all_x, 2 ), std::max( 1, install_x - show_all_x - 1 ),
                        c_light_cyan, show_all );
    }
    trim_and_print( w_list, point( install_x, 2 ), install_width,
                    install_info->selected_can_install ? c_light_green : c_dark_gray, install_button );
"""
cpp = replace_once(cpp, old_display, new_display, "install toggle display")

cpp = replace_once(
    cpp,
    """        const bool materials = install_materials_available( info );
        nc_color col = materials ? c_white : c_dark_gray;
""",
    """        const bool materials = install_materials_available( info );
        const bool mount_compatible = veh->can_mount( selected_mount(), info ).success();
        nc_color col = materials && mount_compatible ? c_white : c_dark_gray;
""",
    "incompatible candidate color",
)

cpp = replace_once(
    cpp,
    """        msg = _( "No compatible parts match this mount, layer, system, and search filter." );
""",
    """        msg = _( "No parts match the current layer, system, search, and visibility filters." );
""",
    "empty candidate message",
)

cpp = replace_once(
    cpp,
    """                        _( "No compatible parts match the current mount/layer/filter." ) );
""",
    """                        _( "No parts match the current layer/system/search filters." ) );
""",
    "empty list message",
)

cpp_path.write_text(cpp)
hdr_path.write_text(hdr)
