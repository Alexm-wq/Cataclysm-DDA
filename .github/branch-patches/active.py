from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one block in {path_str}, found {count}: {old[:180]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Mend remains the existing gameplay activity; the vehicle editor now owns selection/presentation.
replace_once(
    "src/veh_interact.cpp",
    '''static const activity_id ACT_VEHICLE( "ACT_VEHICLE" );\nstatic const activity_id ACT_VEHICLE_SIPHON( "ACT_VEHICLE_SIPHON" );\n''',
    '''static const activity_id ACT_MEND_ITEM( "ACT_MEND_ITEM" );\nstatic const activity_id ACT_VEHICLE( "ACT_VEHICLE" );\nstatic const activity_id ACT_VEHICLE_SIPHON( "ACT_VEHICLE_SIPHON" );\n'''
)

# Retained Mend state lives beside Reshape/Relabel.
replace_once(
    "src/veh_interact.h",
    '''        struct reshape_info_t;\n\n        std::unique_ptr<reshape_info_t> reshape_info;\n\n        struct relabel_info_t;\n''',
    '''        struct reshape_info_t;\n\n        std::unique_ptr<reshape_info_t> reshape_info;\n\n        struct mend_info_t;\n        std::unique_ptr<mend_info_t> mend_info;\n\n        struct relabel_info_t;\n'''
)
replace_once(
    "src/veh_interact.h",
    '''        bool handle_reshape_mouse( const std::string &action );\n        void open_relabel_mode( bool part_mode );\n''',
    '''        bool handle_reshape_mouse( const std::string &action );\n        bool part_has_mend_faults( const vehicle_part &part ) const;\n        void open_mend_mode();\n        void close_mend_mode();\n        void sync_mend_selection();\n        bool apply_mend();\n        bool handle_mend_mouse( const std::string &action );\n        void open_relabel_mode( bool part_mode );\n'''
)
replace_once(
    "src/veh_interact.h",
    '''        void display_reshape_pane();\n        void display_relabel_pane();\n''',
    '''        void display_reshape_pane();\n        void display_mend_pane();\n        void display_relabel_pane();\n'''
)

# Complete state is declared before allocate_windows(), just like Relabel.
replace_once(
    "src/veh_interact.cpp",
    '''// The resize path below needs the complete relabel state, not its forward declaration.\nstruct veh_interact::relabel_info_t {\n''',
    '''struct veh_interact::mend_info_t {\n    struct option_t {\n        fault_id fault;\n        fault_fix_id fix;\n        bool doable = false;\n        time_duration time_to_fix = 1_hours;\n    };\n\n    int target_part = -2;\n    int selected_option = -1;\n    std::vector<option_t> options;\n    std::vector<int> row_to_option;\n    ui_selection_list fix_list;\n    ui_action_strip action_strip;\n    ui_scroll_model detail_scroll;\n    scrollbar detail_scrollbar;\n    std::string status;\n};\n\n// The resize path below needs the complete relabel state, not its forward declaration.\nstruct veh_interact::relabel_info_t {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    reshape_action_strip.clear();\n    if( relabel_info ) {\n''',
    '''    reshape_action_strip.clear();\n    if( mend_info ) {\n        mend_info->action_strip.clear();\n        mend_info->target_part = -2;\n    }\n    if( relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    reshape_info.reset();\n    relabel_info.reset();\n''',
    '''    reshape_info.reset();\n    mend_info.reset();\n    relabel_info.reset();\n'''
)

# Draw/sync/close the new retained mode through the existing editor lifecycle.
replace_once(
    "src/veh_interact.cpp",
    '''            if( reshape_info ) {\n                display_part_inspector();\n                display_reshape_pane();\n            } else if( relabel_info ) {\n''',
    '''            if( reshape_info ) {\n                display_part_inspector();\n                display_reshape_pane();\n            } else if( mend_info ) {\n                display_part_inspector();\n                display_mend_pane();\n            } else if( relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( reshape_info ) {\n            sync_reshape_selection();\n        }\n        if( relabel_info ) {\n''',
    '''        if( reshape_info ) {\n            sync_reshape_selection();\n        }\n        if( mend_info ) {\n            sync_mend_selection();\n        }\n        if( relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''            if( reshape_info ) {\n                close_reshape_mode();\n                continue;\n            }\n            if( relabel_info ) {\n''',
    '''            if( reshape_info ) {\n                close_reshape_mode();\n                continue;\n            }\n            if( mend_info ) {\n                close_mend_mode();\n                continue;\n            }\n            if( relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( action == "QUIT" && relabel_info ) {\n''',
    '''        if( action == "QUIT" && mend_info ) {\n            close_mend_mode();\n            continue;\n        }\n\n        if( action == "QUIT" && relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( reshape_info && action == "CONFIRM" ) {\n            apply_reshape_variant();\n            continue;\n        }\n        if( relabel_info && action == "CONFIRM" ) {\n''',
    '''        if( reshape_info && action == "CONFIRM" ) {\n            apply_reshape_variant();\n            continue;\n        }\n        if( mend_info && action == "CONFIRM" ) {\n            apply_mend();\n            continue;\n        }\n        if( relabel_info && action == "CONFIRM" ) {\n'''
)

# Replace the old overview/uilist Mend path with a retained editor mode.
start = '''void veh_interact::do_mend( map &here )\n{\n'''
end = '''\n\n\nvoid veh_interact::open_reshape_mode()\n'''
p = Path("src/veh_interact.cpp")
s = p.read_text(encoding="utf-8")
a = s.find(start)
b = s.find(end, a)
if a < 0 or b < 0:
    raise SystemExit("could not locate do_mend block")
new_mend = r'''void veh_interact::do_mend( map &here )
{
    switch( cant_do( here, 'm' ) ) {
        case task_reason::LOW_MORALE:
            msg = _( "Your morale is too low to mend…" );
            return;
        case task_reason::LOW_LIGHT:
            msg = _( "It's too dark to see what you are doing…" );
            return;
        case task_reason::INVALID_TARGET:
            msg = _( "No faulty parts require mending." );
            return;
        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't mend stuff while driving." );
            return;
        default:
            break;
    }
    open_mend_mode();
}

bool veh_interact::part_has_mend_faults( const vehicle_part &part ) const
{
    return !part.removed && part.is_available() && !part.faults().empty();
}

void veh_interact::open_mend_mode()
{
    if( mend_info ) {
        return;
    }
    if( reshape_info ) {
        close_reshape_mode();
    }
    if( relabel_info ) {
        close_relabel_mode();
    }
    mend_info = std::make_unique<mend_info_t>();
    mend_info->detail_scrollbar.debug_name( "vehicle.mend.details" );
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    editor_filter_dropdown_menu.close();
    close_editor_toolbar_dropdown();
    viewport_dragging = false;
    live_preview_dragging = false;
#if defined(TILES)
    set_sdl_mouse_capture( false );
#endif
    reset_part_selection();
    sync_mend_selection();
    msg.reset();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}

void veh_interact::close_mend_mode()
{
    if( !mend_info ) {
        return;
    }
    mend_info.reset();
    msg.reset();
    reset_part_selection();
    clamp_viewport_pan();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}

void veh_interact::sync_mend_selection()
{
    if( !mend_info || mend_info->target_part == selected_part ) {
        return;
    }

    mend_info_t &info = *mend_info;
    info.target_part = selected_part;
    info.selected_option = -1;
    info.options.clear();
    info.row_to_option.clear();
    info.status.clear();
    info.detail_scroll.scroll_to_start();

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        info.fix_list.set_entries( {}, false );
        return;
    }
    const vehicle_part &part = veh->part( selected_part );
    if( part.mount != selected_mount() || !part_has_mend_faults( part ) ) {
        info.fix_list.set_entries( {}, false );
        return;
    }

    avatar &player_character = get_avatar();
    const inventory &inv = player_character.crafting_inventory();
    std::vector<ui_action_entry> entries;
    std::vector<ui_tree_node> nodes;
    std::vector<int> group_rows;

    for( const fault_id &fault : part.faults() ) {
        const int parent = static_cast<int>( entries.size() );
        group_rows.push_back( parent );
        entries.emplace_back( fault->name(), "MEND_FAULT_" + fault.str(), true );
        nodes.push_back( { -1, false } );
        info.row_to_option.push_back( -1 );

        for( const fault_fix_id &fix_id : fault->get_fixes() ) {
            const fault_fix &fix = *fix_id;
            bool doable = true;
            for( const auto &[skill, level] : fix.skills ) {
                if( player_character.get_greater_skill_or_knowledge_level( skill ) < level ) {
                    doable = false;
                    break;
                }
            }
            doable = doable && fix.get_requirements().can_make_with_inventory(
                         inv, is_crafting_component );
            if( editor_test_mode || player_character.has_trait( trait_DEBUG_HS ) ) {
                doable = true;
            }

            time_duration time_to_fix = fix.time;
            for( const auto &[flag, mult] : fix.time_save_flags ) {
                if( part.base.has_flag( flag ) ) {
                    time_to_fix *= mult;
                }
            }
            for( const auto &[proficiency, mult] : fix.time_save_profs ) {
                if( player_character.has_proficiency( proficiency ) ) {
                    time_to_fix *= mult;
                }
            }

            const int option_index = static_cast<int>( info.options.size() );
            info.options.push_back( { fault, fix_id, doable, time_to_fix } );
            entries.emplace_back( fix.name.translated(), "MEND_FIX_" + std::to_string( option_index ),
                                  doable, false,
                                  doable ? std::string() : _( "Requirements not met." ) );
            nodes.push_back( { parent, true } );
            info.row_to_option.push_back( option_index );
        }
    }

    info.fix_list.set_tree_entries( std::move( entries ), std::move( nodes ), false );
    for( const int group : group_rows ) {
        info.fix_list.set_expanded( group, true );
    }
    for( int row = 0; row < static_cast<int>( info.row_to_option.size() ); ++row ) {
        if( info.row_to_option[row] >= 0 ) {
            info.selected_option = info.row_to_option[row];
            info.fix_list.set_cursor( row );
            if( info.options[info.selected_option].doable ) {
                info.fix_list.select_only( row );
            }
            break;
        }
    }
}

bool veh_interact::apply_mend()
{
    if( !mend_info || mend_info->target_part < 0 ||
        mend_info->target_part >= veh->part_count() || mend_info->selected_option < 0 ||
        mend_info->selected_option >= static_cast<int>( mend_info->options.size() ) ) {
        return false;
    }
    mend_info_t &info = *mend_info;
    const mend_info_t::option_t option = info.options[info.selected_option];
    vehicle_part &part = veh->part( info.target_part );
    if( part.mount != selected_mount() || !part_has_mend_faults( part ) ||
        part.faults().count( option.fault ) == 0 ) {
        info.status = _( "That fault is no longer present." );
        return false;
    }
    if( !option.doable ) {
        info.status = _( "The requirements for this fix are not met." );
        return false;
    }

    avatar &player_character = get_avatar();
    item_location target = veh->part_base( info.target_part );
    player_character.assign_activity( ACT_MEND_ITEM, to_moves<int>( option.time_to_fix ) );
    player_character.activity.name = option.fault.str();
    player_character.activity.str_values.emplace_back( option.fix.str() );
    player_character.activity.targets.push_back( std::move( target ) );
    sel_cmd = 'q';
    return true;
}

bool veh_interact::handle_mend_mouse( const std::string &action )
{
    if( !mend_info ) {
        return false;
    }
    mend_info_t &info = *mend_info;
    const std::optional<point> pos = main_context.get_coordinates_text( w_msg );
    const bool inside = pos && pos->x >= 0 && pos->y >= 0 && pos->x < getmaxx( w_msg ) &&
                        pos->y < getmaxy( w_msg );

    const int height = getmaxy( w_msg );
    constexpr int first_row = 3;
    const int footer_y = std::max( first_row, height - 1 );
    const int available = std::max( 0, footer_y - first_row );
    const int list_height = std::max( 0, std::min( 5, available / 2 ) );
    const int detail_top = first_row + list_height + ( list_height > 0 ? 1 : 0 );

    const ui_action_result list_result = info.fix_list.handle_input(
                                         action, main_context, inside ? pos : std::nullopt );
    if( list_result.consumed() || list_result.type == ui_action_result_type::disabled ) {
        const int row = info.fix_list.cursor();
        if( row >= 0 && row < static_cast<int>( info.row_to_option.size() ) &&
            info.row_to_option[row] >= 0 ) {
            info.selected_option = info.row_to_option[row];
            info.detail_scroll.scroll_to_start();
        }
        if( action == "SELECT" || action == "MOUSE_MOVE" || action == "SCROLL_UP" ||
            action == "SCROLL_DOWN" || action == "UP" || action == "DOWN" ||
            action == "PAGE_UP" || action == "PAGE_DOWN" || action == "HOME" || action == "END" ) {
            return true;
        }
    }

    if( inside && pos->y >= detail_top && pos->y < footer_y &&
        info.detail_scrollbar.handle_input( action, main_context, info.detail_scroll ) ) {
        return true;
    }

    const ui_action_result action_result = info.action_strip.handle_input(
                                           action, inside ? pos : std::nullopt );
    if( action_result.type == ui_action_result_type::disabled && action_result.entry ) {
        info.status = action_result.entry->disabled_reason;
        return true;
    }
    if( action_result.type == ui_action_result_type::activated && action_result.entry &&
        action_result.entry->id == "MEND_APPLY" ) {
        apply_mend();
        return true;
    }
    return inside && action == "SELECT";
}
'''
s = s[:a] + new_mend + s[b:]
p.write_text(s, encoding="utf-8")

# Mount changes keep Mend live and immediately rebuild its fault/fix model.
replace_once(
    "src/veh_interact.cpp",
    '''    if( relabel_info ) {\n        relabel_info->initialized = false;\n        sync_relabel_selection();\n    }\n}\n\nveh_interact::editor_layer''',
    '''    if( mend_info ) {\n        mend_info->target_part = -2;\n        sync_mend_selection();\n    }\n    if( relabel_info ) {\n        relabel_info->initialized = false;\n        sync_relabel_selection();\n    }\n}\n\nveh_interact::editor_layer'''
)

# Fault-only viewport and inspector filtering ignores Layer/System/Condition, exactly like Reshape mode.
replace_once(
    "src/veh_interact.cpp",
    '''    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );\n    if( all_parts.empty() ) {\n        return std::nullopt;\n    }\n\n    // Use a shape that cannot be mistaken''',
    '''    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );\n    if( all_parts.empty() ) {\n        return std::nullopt;\n    }\n\n    if( mend_info ) {\n        int best_part = -1;\n        int best_z = INT_MIN;\n        int best_order = INT_MIN;\n        for( const int idx : all_parts ) {\n            const vehicle_part &part = veh->part( idx );\n            if( !part_has_mend_faults( part ) ) {\n                continue;\n            }\n            const vpart_info &part_info = part.info();\n            if( part_info.z_order > best_z ||\n                ( part_info.z_order == best_z && part_info.list_order >= best_order ) ) {\n                best_part = idx;\n                best_z = part_info.z_order;\n                best_order = part_info.list_order;\n            }\n        }\n        if( best_part < 0 ) {\n            return std::nullopt;\n        }\n        return std::make_pair( editor_part_symbol( veh->part( best_part ) ), c_light_red );\n    }\n\n    // Use a shape that cannot be mistaken'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        } else if( relabel_info ) {\n            if( !vp.removed ) {\n                result.push_back( idx );\n            }\n        } else if( part_matches_layer( vp ) && part_matches_system( vp ) &&\n''',
    '''        } else if( mend_info ) {\n            if( part_has_mend_faults( vp ) ) {\n                result.push_back( idx );\n            }\n        } else if( relabel_info ) {\n            if( !vp.removed ) {\n                result.push_back( idx );\n            }\n        } else if( part_matches_layer( vp ) && part_matches_system( vp ) &&\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( ( reshape_info || relabel_info ) && ( pos.y == 1 || pos.y == 2 ) ) {\n''',
    '''    if( ( reshape_info || mend_info || relabel_info ) && ( pos.y == 1 || pos.y == 2 ) ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info || relabel_info ) {\n        editor_layer_strip.clear();\n        editor_filter_strip.clear();\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,\n                        reshape_info ? _( "Filter: reshapeable parts only" ) :\n                        _( "Relabel: all parts at selected position" ) );\n        return;\n    }\n''',
    '''    if( reshape_info || mend_info || relabel_info ) {\n        editor_layer_strip.clear();\n        editor_filter_strip.clear();\n        const std::string mode_filter = reshape_info ? _( "Filter: reshapeable parts only" ) :\n                                        mend_info ? _( "Filter: faulty parts only" ) :\n                                        _( "Relabel: all parts at selected position" );\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray, mode_filter );\n        return;\n    }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info || relabel_info || open_editor_dropdown == editor_dropdown::none ) {\n''',
    '''    if( reshape_info || mend_info || relabel_info || open_editor_dropdown == editor_dropdown::none ) {\n'''
)

# Mouse routing: Mend owns the lower-right pane while normal inspector selection remains clickable.
replace_once(
    "src/veh_interact.cpp",
    '''        } else if( !msg.has_value() &&\n                   part_detail_scrollbar.handle_input( action, main_context, part_detail_scroll ) ) {\n''',
    '''        } else if( !mend_info && !msg.has_value() &&\n                   part_detail_scrollbar.handle_input( action, main_context, part_detail_scroll ) ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info && !relabel_info ?\n                                         viewport_pos : std::nullopt );\n        editor_filter_strip.update_hover( viewport_pos && viewport_pos->y == 2 && !reshape_info && !relabel_info ?\n''',
    '''        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info && !mend_info && !relabel_info ?\n                                         viewport_pos : std::nullopt );\n        editor_filter_strip.update_hover( viewport_pos && viewport_pos->y == 2 && !reshape_info && !mend_info && !relabel_info ?\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info && handle_reshape_mouse( action ) ) {\n        return true;\n    }\n    if( relabel_info && handle_relabel_mouse( action ) ) {\n''',
    '''    if( reshape_info && handle_reshape_mouse( action ) ) {\n        return true;\n    }\n    if( mend_info && handle_mend_mouse( action ) ) {\n        return true;\n    }\n    if( relabel_info && handle_relabel_mouse( action ) ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( action == "SEC_SELECT" && !remove_info && !reshape_info && !relabel_info ) {\n''',
    '''    if( action == "SEC_SELECT" && !remove_info && !reshape_info && !mend_info && !relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''                if( reshape_info ) {\n                    sync_reshape_selection();\n                }\n''',
    '''                if( reshape_info ) {\n                    sync_reshape_selection();\n                }\n                if( mend_info ) {\n                    sync_mend_selection();\n                }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( !install_info && !relabel_info && details_pos ) {\n            scroll_part_details( direction );\n''',
    '''        if( !install_info && !mend_info && !relabel_info && details_pos ) {\n            scroll_part_details( direction );\n'''
)

# Inspector calls out the active fault-only filter and shows fault count instead of health.
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Reshapeable parts: %d/%d" ),\n                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );\n    } else if( relabel_info ) {\n''',
    '''    if( reshape_info ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Reshapeable parts: %d/%d" ),\n                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );\n    } else if( mend_info ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Faulty parts: %d/%d" ),\n                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );\n    } else if( relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        const int health = static_cast<int>( std::lround( vp.health_percent() * 100.0 ) );\n        nc_color name_color = vp.is_broken() ? c_dark_gray : c_light_gray;\n        nc_color condition_color = editor_condition_color( vp );\n''',
    '''        const int health = static_cast<int>( std::lround( vp.health_percent() * 100.0 ) );\n        nc_color name_color = vp.is_broken() ? c_dark_gray : c_light_gray;\n        nc_color condition_color = mend_info ? c_light_red : editor_condition_color( vp );\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        mvwprintz( w_parts, point( percent_x, first_row + row ), condition_color, "%3d%%", health );\n''',
    '''        if( mend_info ) {\n            mvwprintz( w_parts, point( percent_x, first_row + row ), condition_color, "%2dF",\n                       static_cast<int>( vp.faults().size() ) );\n        } else {\n            mvwprintz( w_parts, point( percent_x, first_row + row ), condition_color, "%3d%%", health );\n        }\n'''
)

# Bottom-right Mend pane: helper tree for fault -> fix, scrollable requirements, one action.
replace_once(
    "src/veh_interact.cpp",
    '''void veh_interact::display_relabel_pane()\n{\n''',
    r'''void veh_interact::display_mend_pane()
{
    werase( w_msg );
    if( !mend_info ) {
        wnoutrefresh( w_msg );
        return;
    }
    sync_mend_selection();
    mend_info_t &info = *mend_info;
    const int width = getmaxx( w_msg );
    const int height = getmaxy( w_msg );

    trim_and_print( w_msg, point( 1, 0 ), std::max( 1, width - 2 ), c_light_green,
                    _( "Mend faults" ) );
    if( info.target_part >= 0 && info.target_part < veh->part_count() ) {
        trim_and_print( w_msg, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,
                        editor_part_display_name( veh->part( info.target_part ) ) );
    } else {
        trim_and_print( w_msg, point( 1, 1 ), std::max( 1, width - 2 ), c_dark_gray,
                        _( "Select a faulty part above." ) );
    }
    if( height > 2 ) {
        wattron( w_msg, c_dark_gray );
        mvwhline( w_msg, point( 1, 2 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_msg, c_dark_gray );
    }

    constexpr int first_row = 3;
    const int footer_y = std::max( first_row, height - 1 );
    const int available = std::max( 0, footer_y - first_row );
    const int list_height = std::max( 0, std::min( 5, available / 2 ) );
    ui_selection_list_style list_style;
    list_style.text = c_light_gray;
    list_style.disabled = c_dark_gray;
    list_style.disabled_cursor = h_dark_gray;
    list_style.disabled_hint = c_light_red;
    list_style.cursor = h_white;
    if( list_height > 0 ) {
        info.fix_list.draw( w_msg, point( 1, first_row ), std::max( 1, width - 2 ),
                            list_height, list_style );
    }

    const int detail_top = first_row + list_height + ( list_height > 0 ? 1 : 0 );
    if( list_height > 0 && detail_top - 1 < footer_y ) {
        wattron( w_msg, c_dark_gray );
        mvwhline( w_msg, point( 1, detail_top - 1 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_msg, c_dark_gray );
    }

    std::string detail;
    bool can_apply = false;
    if( info.selected_option >= 0 && info.selected_option < static_cast<int>( info.options.size() ) ) {
        const mend_info_t::option_t &option = info.options[info.selected_option];
        const fault_fix &fix = *option.fix;
        can_apply = option.doable;
        detail += string_format( "<color_light_red>%s</color>\n", option.fault->name() );
        if( !option.fault->description().empty() ) {
            detail += option.fault->description() + "\n";
        }
        detail += string_format( _( "Fix: <color_light_green>%s</color>\n" ), fix.name.translated() );
        std::string requirements;
        const bool formatted_ok = format_reqs( requirements, fix.get_requirements(), fix.skills,
                                               option.time_to_fix );
        can_apply = can_apply && ( formatted_ok || get_avatar().has_trait( trait_DEBUG_HS ) );
        detail += requirements;
        if( fix.mod_damage != 0 ) {
            detail += string_format( _( "Damage change: %d\n" ),
                                     fix.mod_damage / itype::damage_scale );
        }
    } else if( info.target_part >= 0 ) {
        detail = _( "This part has no available fault fix." );
    } else {
        detail = _( "Click a highlighted faulty mount, then select a faulty part." );
    }
    if( !info.status.empty() ) {
        detail = colorize( info.status, c_light_red ) + "\n" + detail;
    }

    const int detail_height = std::max( 0, footer_y - detail_top );
    if( detail_height > 0 ) {
        std::vector<std::string> lines;
        std::istringstream stream( detail );
        std::string source_line;
        while( std::getline( stream, source_line ) ) {
            const std::vector<std::string> folded = foldstring( source_line, std::max( 1, width - 3 ) );
            if( folded.empty() ) {
                lines.emplace_back();
            } else {
                lines.insert( lines.end(), folded.begin(), folded.end() );
            }
        }
        info.detail_scroll.set_content_size( static_cast<int>( lines.size() ) )
        .set_viewport_size( detail_height );
        for( int row = 0; row < detail_height; ++row ) {
            const std::optional<int> idx = info.detail_scroll.index_at_viewport_row( row );
            if( !idx ) {
                break;
            }
            nc_color dummy = c_unset;
            print_colored_text( w_msg, point( 1, detail_top + row ), dummy, c_light_gray, lines[*idx] );
        }
        info.detail_scrollbar.offset_x( std::max( 0, width - 1 ) ).offset_y( detail_top )
        .height( detail_height ).model( info.detail_scroll ).apply( w_msg );
    }

    if( footer_y < height ) {
        std::vector<ui_action_strip_item> actions = {
            { ui_action_entry( _( "Mend" ), "MEND_APPLY", can_apply, false,
                               _( "Select a fix whose skill, tool, and component requirements are met." ) ),
              0, ui_action_alignment::left }
        };
        ui_action_strip_style style;
        style.text = c_light_green;
        info.action_strip.configure( w_msg, point( 1, footer_y ), std::move( actions ),
                                     std::max( 1, width - 2 ), 1, style );
        info.action_strip.draw( w_msg );
    } else {
        info.action_strip.clear();
    }
    wnoutrefresh( w_msg );
}

void veh_interact::display_relabel_pane()
{
'''
)

# Relabel's lower pane no longer owns closing; top editor Back is authoritative.
replace_once(
    "src/veh_interact.cpp",
    '''            { ui_action_entry( _( "Apply" ), "RELABEL_APPLY", valid_target, false,\n                               _( "Select an occupied position or part first." ) ),\n              0, ui_action_alignment::left },\n            { ui_action_entry( _( "Back" ), "RELABEL_BACK" ), 1, ui_action_alignment::right }\n''',
    '''            { ui_action_entry( _( "Apply" ), "RELABEL_APPLY", valid_target, false,\n                               _( "Select an occupied position or part first." ) ),\n              0, ui_action_alignment::left }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        } else if( action_result.entry->id == "RELABEL_APPLY" ) {\n            apply_relabel();\n        } else if( action_result.entry->id == "RELABEL_BACK" ) {\n            close_relabel_mode();\n        }\n''',
    '''        } else if( action_result.entry->id == "RELABEL_APPLY" ) {\n            apply_relabel();\n        }\n'''
)

# The top Back toolbar is the sole visible mode close control for Mend/Relabel.
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info || relabel_info ) {\n''',
    '''    if( reshape_info || mend_info || relabel_info ) {\n'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Add retained fault-only vehicle mend mode\n", encoding="utf-8"
)
