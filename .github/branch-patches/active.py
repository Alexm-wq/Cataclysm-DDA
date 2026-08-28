from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one block in {path_str}, found {count}: {old[:180]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path_str: str, old: str, new: str, expected: int) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"expected {expected} blocks in {path_str}, found {count}: {old[:180]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# Part labels live on the serialized base item so they follow the exact component.
replace_once(
    "src/vehicle.h",
    '''        std::string name( bool with_prefix = true ) const;\n\n        struct carried_part_data {\n''',
    '''        std::string name( bool with_prefix = true ) const;\n\n        /** Optional player-defined label for this exact installed component. */\n        std::optional<std::string> get_label() const;\n        /** Set the component label; an empty string removes it. */\n        void set_label( const std::string &text );\n\n        struct carried_part_data {\n'''
)

replace_once(
    "src/vehicle_part.cpp",
    '''std::string vehicle_part::name( bool with_prefix ) const\n{\n''',
    '''std::optional<std::string> vehicle_part::get_label() const\n{\n    static const std::string key = "vehicle_part_label";\n    const std::string value = base.get_var( key );\n    return value.empty() ? std::nullopt : std::make_optional( value );\n}\n\nvoid vehicle_part::set_label( const std::string &text )\n{\n    static const std::string key = "vehicle_part_label";\n    if( text.empty() ) {\n        base.remove_var( key );\n    } else {\n        base.set_var( key, text );\n    }\n}\n\nstd::string vehicle_part::name( bool with_prefix ) const\n{\n'''
)

# Declare retained Relabel mode alongside Reshape.
replace_once(
    "src/veh_interact.h",
    '''        struct reshape_info_t;\n        struct refuel_info_t;\n''',
    '''        struct reshape_info_t;\n        struct relabel_info_t;\n        struct refuel_info_t;\n'''
)
replace_once(
    "src/veh_interact.h",
    '''        std::unique_ptr<reshape_info_t> reshape_info;\n        std::unique_ptr<refuel_info_t> refuel_info;\n''',
    '''        std::unique_ptr<reshape_info_t> reshape_info;\n        std::unique_ptr<relabel_info_t> relabel_info;\n        std::unique_ptr<refuel_info_t> refuel_info;\n'''
)
replace_once(
    "src/veh_interact.h",
    '''        bool handle_reshape_mouse( const std::string &action );\n        void display_reshape_pane();\n''',
    '''        bool handle_reshape_mouse( const std::string &action );\n        void display_reshape_pane();\n        void open_relabel_mode( bool part_mode );\n        void close_relabel_mode();\n        void sync_relabel_selection();\n        void edit_relabel_text();\n        bool apply_relabel();\n        bool handle_relabel_mouse( const std::string &action );\n        void display_relabel_pane();\n'''
)

# Explicitly use the list helper in the new submode.
replace_once(
    "src/veh_interact.cpp",
    '''#include "ui_helpers/controls/selection_panel.h"\n#include "ui_helpers/controls/text_input_dialog.h"\n''',
    '''#include "ui_helpers/controls/selection_panel.h"\n#include "ui_helpers/controls/selection_list.h"\n#include "ui_helpers/controls/text_input_dialog.h"\n'''
)

# Label-aware editor display without changing generic vehicle-part naming elsewhere.
replace_once(
    "src/veh_interact.cpp",
    '''static bool reshape_part_has_visible_variants( const vpart_info &vpi )\n{\n''',
    '''static std::string editor_part_display_name( const vehicle_part &part )\n{\n    const std::optional<std::string> label = part.get_label();\n    return label ? string_format( "%s (%s)", *label, part.name() ) : part.name();\n}\n\nstatic bool reshape_part_has_visible_variants( const vpart_info &vpi )\n{\n'''
)

replace_once(
    "src/veh_interact.cpp",
    '''struct veh_interact::reshape_info_t {\n    int target_part = -1;\n    int variant_pos = 0;\n    ui_scroll_model variant_scroll;\n    std::vector<std::string> variants;\n    std::string committed_variant;\n    ui_double_click_tracker<std::string> double_click;\n};\n\nstruct veh_interact::refuel_info_t {\n''',
    '''struct veh_interact::reshape_info_t {\n    int target_part = -1;\n    int variant_pos = 0;\n    ui_scroll_model variant_scroll;\n    std::vector<std::string> variants;\n    std::string committed_variant;\n    ui_double_click_tracker<std::string> double_click;\n};\n\nstruct veh_interact::relabel_info_t {\n    enum class target_t {\n        position,\n        part\n    };\n\n    target_t target = target_t::position;\n    point_rel_ms mount = point_rel_ms::zero;\n    bool initialized = false;\n    int target_part = -1;\n    std::vector<int> part_indices;\n    std::string draft;\n    std::string status;\n    ui_selection_list part_list;\n    ui_action_strip mode_strip;\n    ui_action_strip action_strip;\n    ui_text_field text_field;\n};\n\nstruct veh_interact::refuel_info_t {\n'''
)

# Never retain label helper state across ACT_VEHICLE pointer-bearing handoffs.
replace_once(
    "src/veh_interact.cpp",
    '''    remove_info.reset();\n    reshape_info.reset();\n    refuel_info.reset();\n''',
    '''    remove_info.reset();\n    reshape_info.reset();\n    relabel_info.reset();\n    refuel_info.reset();\n'''
)

# Resizes clear helper geometry; state is rebuilt on redraw.
replace_once(
    "src/veh_interact.cpp",
    '''    install_action_strip.clear();\n    reshape_action_strip.clear();\n    w_border = catacurses::newwin( TERMY, TERMX, point::zero );\n''',
    '''    install_action_strip.clear();\n    reshape_action_strip.clear();\n    if( relabel_info ) {\n        relabel_info->mode_strip.clear();\n        relabel_info->action_strip.clear();\n        relabel_info->text_field.clear();\n        relabel_info->initialized = false;\n    }\n    w_border = catacurses::newwin( TERMY, TERMX, point::zero );\n'''
)

# Draw the retained Relabel panes in exactly the same right-side regions as Reshape.
replace_once(
    "src/veh_interact.cpp",
    '''            if( reshape_info ) {\n                display_part_inspector();\n                display_reshape_pane();\n            } else if( !install_info && !remove_info ) {\n''',
    '''            if( reshape_info ) {\n                display_part_inspector();\n                display_reshape_pane();\n            } else if( relabel_info ) {\n                display_part_inspector();\n                display_relabel_pane();\n            } else if( !install_info && !remove_info ) {\n'''
)

# Keep relabel selection synchronized with keyboard/mouse mount changes.
replace_once(
    "src/veh_interact.cpp",
    '''        if( reshape_info ) {\n            sync_reshape_selection();\n        }\n        if( install_info ) {\n''',
    '''        if( reshape_info ) {\n            sync_reshape_selection();\n        }\n        if( relabel_info ) {\n            sync_relabel_selection();\n        }\n        if( install_info ) {\n'''
)

replace_once(
    "src/veh_interact.cpp",
    '''            if( reshape_info ) {\n                close_reshape_mode();\n                continue;\n            }\n            if( install_info ) {\n''',
    '''            if( reshape_info ) {\n                close_reshape_mode();\n                continue;\n            }\n            if( relabel_info ) {\n                close_relabel_mode();\n                continue;\n            }\n            if( install_info ) {\n'''
)

replace_once(
    "src/veh_interact.cpp",
    '''        if( action == "QUIT" && reshape_info ) {\n''',
    '''        if( action == "QUIT" && relabel_info ) {\n            close_relabel_mode();\n            continue;\n        }\n\n        if( action == "QUIT" && reshape_info ) {\n'''
)

replace_once(
    "src/veh_interact.cpp",
    '''        if( reshape_info && action == "CONFIRM" ) {\n            apply_reshape_variant();\n            continue;\n        }\n\n        if( install_info ) {\n''',
    '''        if( reshape_info && action == "CONFIRM" ) {\n            apply_reshape_variant();\n            continue;\n        }\n        if( relabel_info && action == "CONFIRM" ) {\n            apply_relabel();\n            continue;\n        }\n\n        if( install_info ) {\n'''
)

# Toolbar and keyboard routes enter one shared submode with different initial targets.
replace_once(
    "src/veh_interact.cpp",
    '''        } else if( action == "RELABEL" ) {\n            if( owned_by_player ) {\n                do_relabel( here );\n            } else if( owner_fac ) {\n                popup( _( "You cannot relabel this vehicle as it is owned by: %s." ), _( owner_fac->name ) );\n            }\n''',
    '''        } else if( action == "RELABEL" || action == "RELABEL_POSITION" ||\n                   action == "RELABEL_PART" ) {\n            if( owned_by_player ) {\n                open_relabel_mode( action == "RELABEL_PART" );\n            } else if( owner_fac ) {\n                popup( _( "You cannot relabel this vehicle as it is owned by: %s." ), _( owner_fac->name ) );\n            }\n'''
)

# Legacy entry now opens Position mode rather than an independent popup.
replace_once(
    "src/veh_interact.cpp",
    '''void veh_interact::do_relabel( const map &here )\n{\n    if( cant_do( here,  'a' ) == task_reason::INVALID_TARGET ) {\n        msg = _( "There are no parts here to label." );\n        return;\n    }\n\n    const vpart_position vp( *veh, cpart );\n    const std::optional<std::string> text = ui_query_text_input_dialog(\n                _( "Relabel part" ), _( "Label" ), vp.get_label().value_or( "" ), 20 );\n    if( text ) {\n        vp.set_label( *text );\n    }\n}\n''',
    '''void veh_interact::do_relabel( const map &here )\n{\n    ( void )here;\n    open_relabel_mode( false );\n}\n'''
)

# Full retained Relabel model/behavior.  The helper owns rows, hover, clicks and action buttons.
replace_once(
    "src/veh_interact.cpp",
    '''void veh_interact::close_refuel_mode()\n{\n''',
    r'''void veh_interact::open_relabel_mode( const bool part_mode )
{
    if( reshape_info ) {
        close_reshape_mode();
    }
    if( !relabel_info ) {
        relabel_info = std::make_unique<relabel_info_t>();
    }
    relabel_info->target = part_mode ? relabel_info_t::target_t::part :
                           relabel_info_t::target_t::position;
    relabel_info->initialized = false;
    relabel_info->status.clear();
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
    sync_relabel_selection();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}

void veh_interact::close_relabel_mode()
{
    if( !relabel_info ) {
        return;
    }
    relabel_info.reset();
    msg.reset();
    reset_part_selection();
    clamp_viewport_pan();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}

void veh_interact::sync_relabel_selection()
{
    if( !relabel_info ) {
        return;
    }
    relabel_info_t &info = *relabel_info;
    const point_rel_ms mount = selected_mount();
    std::vector<int> parts = veh->parts_at_relative( mount, true, false );
    parts.erase( std::remove_if( parts.begin(), parts.end(), [&]( const int idx ) {
        return idx < 0 || idx >= veh->part_count() || veh->part( idx ).removed;
    } ), parts.end() );

    if( info.target == relabel_info_t::target_t::part &&
        std::find( parts.begin(), parts.end(), selected_part ) == parts.end() ) {
        selected_part = parts.empty() ? -1 : parts.front();
    }
    const int target_part = info.target == relabel_info_t::target_t::part ? selected_part : -1;
    const bool changed = !info.initialized || info.mount != mount ||
                         info.target_part != target_part || info.part_indices != parts;
    if( !changed ) {
        return;
    }

    info.mount = mount;
    info.target_part = target_part;
    info.part_indices = parts;
    std::vector<ui_action_entry> entries;
    entries.reserve( parts.size() );
    const bool part_mode = info.target == relabel_info_t::target_t::part;
    for( const int idx : parts ) {
        entries.emplace_back( editor_part_display_name( veh->part( idx ) ), std::to_string( idx ),
                              part_mode, part_mode && idx == target_part,
                              part_mode ? std::string() :
                              _( "Position mode labels the whole mount, not an individual part." ) );
    }
    info.part_list.set_entries( std::move( entries ), false );
    info.part_list.activate_on_single_click();
    if( part_mode && target_part >= 0 ) {
        const auto found = std::find( parts.begin(), parts.end(), target_part );
        if( found != parts.end() ) {
            const int row = static_cast<int>( std::distance( parts.begin(), found ) );
            info.part_list.set_cursor( row );
            info.part_list.select_only( row );
        }
    }

    if( part_mode ) {
        info.draft = target_part >= 0 ? veh->part( target_part ).get_label().value_or( "" ) :
                     std::string();
    } else if( !parts.empty() ) {
        info.draft = vpart_position( *veh, parts.front() ).get_label().value_or( "" );
    } else {
        info.draft.clear();
    }
    info.status.clear();
    info.initialized = true;
}

void veh_interact::edit_relabel_text()
{
    if( !relabel_info ) {
        return;
    }
    relabel_info_t &info = *relabel_info;
    const bool part_mode = info.target == relabel_info_t::target_t::part;
    const std::optional<std::string> text = ui_query_text_input_dialog(
                part_mode ? _( "Relabel part" ) : _( "Relabel position" ),
                _( "Label" ), info.draft, 28 );
    if( text ) {
        info.draft = *text;
        info.status.clear();
    }
}

bool veh_interact::apply_relabel()
{
    if( !relabel_info ) {
        return false;
    }
    relabel_info_t &info = *relabel_info;
    if( info.target == relabel_info_t::target_t::position ) {
        if( info.part_indices.empty() ) {
            info.status = _( "Select an occupied vehicle position first." );
            return false;
        }
        vpart_position( *veh, info.part_indices.front() ).set_label( info.draft );
        info.status = info.draft.empty() ? _( "Position label removed." ) :
                      _( "Position label applied." );
    } else {
        if( info.target_part < 0 || info.target_part >= veh->part_count() ||
            veh->part( info.target_part ).removed || veh->part( info.target_part ).mount != selected_mount() ) {
            info.status = _( "Select a part to label first." );
            return false;
        }
        veh->part( info.target_part ).set_label( info.draft );
        info.status = info.draft.empty() ? _( "Part label removed." ) : _( "Part label applied." );
        info.initialized = false;
        sync_relabel_selection();
        info.status = info.draft.empty() ? _( "Part label removed." ) : _( "Part label applied." );
    }
    return true;
}

bool veh_interact::handle_relabel_mouse( const std::string &action )
{
    if( !relabel_info ) {
        return false;
    }
    relabel_info_t &info = *relabel_info;
    const auto pos_in = [&]( const catacurses::window &window ) -> std::optional<point> {
        const std::optional<point> pos = main_context.get_coordinates_text( window );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( window ) ||
            pos->y >= getmaxy( window ) ) {
            return std::nullopt;
        }
        return pos;
    };
    const std::optional<point> parts_pos = pos_in( w_parts );
    const std::optional<point> details_pos = pos_in( w_msg );

    if( parts_pos ) {
        const ui_action_result result = info.part_list.handle_input( action, main_context, parts_pos );
        if( result.type == ui_action_result_type::disabled ) {
            info.status = _( "Position mode labels the whole mount. Switch to Part to select a component." );
            return true;
        }
        if( result.type == ui_action_result_type::activated ) {
            const int row = info.part_list.cursor();
            if( row >= 0 && row < static_cast<int>( info.part_indices.size() ) ) {
                selected_part = info.part_indices[row];
                info.initialized = false;
                sync_relabel_selection();
            }
            return true;
        }
        if( result.consumed() ) {
            return true;
        }
        if( action == "SELECT" || action == "SEC_SELECT" ) {
            return true;
        }
    }

    if( !details_pos ) {
        return false;
    }
    const ui_action_result mode_result = info.mode_strip.handle_input( action, details_pos );
    if( mode_result.type == ui_action_result_type::activated && mode_result.entry ) {
        const bool part_mode = mode_result.entry->id == "RELABEL_MODE_PART";
        info.target = part_mode ? relabel_info_t::target_t::part : relabel_info_t::target_t::position;
        info.initialized = false;
        sync_relabel_selection();
        return true;
    }

    const ui_action_result action_result = info.action_strip.handle_input( action, details_pos );
    if( action_result.type == ui_action_result_type::disabled && action_result.entry ) {
        info.status = action_result.entry->disabled_reason;
        return true;
    }
    if( action_result.type == ui_action_result_type::activated && action_result.entry ) {
        if( action_result.entry->id == "RELABEL_EDIT" ) {
            edit_relabel_text();
        } else if( action_result.entry->id == "RELABEL_APPLY" ) {
            apply_relabel();
        } else if( action_result.entry->id == "RELABEL_BACK" ) {
            close_relabel_mode();
        }
        return true;
    }
    if( action == "SELECT" && info.text_field.hit_test( *details_pos ) == ui_text_field_hit::edit ) {
        edit_relabel_text();
        return true;
    }
    return action == "SELECT" || action == "SEC_SELECT" ||
           mode_result.consumed() || action_result.consumed();
}

void veh_interact::close_refuel_mode()
{
'''
)

# Relabel exposes every real part at the selected mount, independent of normal filters.
replace_once(
    "src/veh_interact.cpp",
    '''        if( reshape_info ) {\n            // Reshape is its own filter mode: ignore the normal layer/system/\n            // condition filters and expose only independently reshapeable parts.\n            if( !vp.removed && reshape_part_has_visible_variants( vp.info() ) ) {\n                result.push_back( idx );\n            }\n        } else if( part_matches_layer( vp ) && part_matches_system( vp ) &&\n''',
    '''        if( reshape_info ) {\n            // Reshape is its own filter mode: ignore the normal layer/system/\n            // condition filters and expose only independently reshapeable parts.\n            if( !vp.removed && reshape_part_has_visible_variants( vp.info() ) ) {\n                result.push_back( idx );\n            }\n        } else if( relabel_info ) {\n            if( !vp.removed ) {\n                result.push_back( idx );\n            }\n        } else if( part_matches_layer( vp ) && part_matches_system( vp ) &&\n'''
)

# Mount selection remains live while Relabel is open.
replace_once(
    "src/veh_interact.cpp",
    '''    if( install_info ) {\n        install_info->dirty = true;\n    }\n}\n\nveh_interact::editor_layer veh_interact::editor_layer_for_part''',
    '''    if( install_info ) {\n        install_info->dirty = true;\n    }\n    if( relabel_info ) {\n        relabel_info->initialized = false;\n        sync_relabel_selection();\n    }\n}\n\nveh_interact::editor_layer veh_interact::editor_layer_for_part'''
)

# Relabel, like Reshape, owns the editor filters while active.
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info && ( pos.y == 1 || pos.y == 2 ) ) {\n        return true;\n    }\n''',
    '''    if( ( reshape_info || relabel_info ) && ( pos.y == 1 || pos.y == 2 ) ) {\n        return true;\n    }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info ) {\n        editor_layer_strip.clear();\n        editor_filter_strip.clear();\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,\n                        _( "Filter: reshapeable parts only" ) );\n        return;\n    }\n''',
    '''    if( reshape_info || relabel_info ) {\n        editor_layer_strip.clear();\n        editor_filter_strip.clear();\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,\n                        reshape_info ? _( "Filter: reshapeable parts only" ) :\n                        _( "Relabel: all parts at selected position" ) );\n        return;\n    }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info || open_editor_dropdown == editor_dropdown::none ) {\n''',
    '''    if( reshape_info || relabel_info || open_editor_dropdown == editor_dropdown::none ) {\n'''
)

# Mouse routes new controls through helpers before generic inspector hit-testing.
replace_once(
    "src/veh_interact.cpp",
    '''    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n            return true;\n        }\n''',
    '''    if( !install_info && !remove_info && !relabel_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n            return true;\n        }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info ?\n                                         viewport_pos : std::nullopt );\n        editor_filter_strip.update_hover( viewport_pos && viewport_pos->y == 2 && !reshape_info ?\n''',
    '''        editor_layer_strip.update_hover( viewport_pos && viewport_pos->y == 1 && !reshape_info && !relabel_info ?\n                                         viewport_pos : std::nullopt );\n        editor_filter_strip.update_hover( viewport_pos && viewport_pos->y == 2 && !reshape_info && !relabel_info ?\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info && handle_reshape_mouse( action ) ) {\n        return true;\n    }\n''',
    '''    if( reshape_info && handle_reshape_mouse( action ) ) {\n        return true;\n    }\n    if( relabel_info && handle_relabel_mouse( action ) ) {\n        return true;\n    }\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( action == "SEC_SELECT" && !remove_info && !reshape_info ) {\n''',
    '''    if( action == "SEC_SELECT" && !remove_info && !reshape_info && !relabel_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( !install_info && parts_pos && parts_pos->y >= 3 ) {\n''',
    '''        if( !install_info && !relabel_info && parts_pos && parts_pos->y >= 3 ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( !install_info && parts_pos ) {\n            scroll_part_inspector( direction );\n            return true;\n        }\n        if( !install_info && details_pos ) {\n''',
    '''        if( !install_info && !relabel_info && parts_pos ) {\n            scroll_part_inspector( direction );\n            return true;\n        }\n        if( !install_info && !relabel_info && details_pos ) {\n'''
)

# Use same top-level mode title convention as Reshape.
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info && active_editor_view_mode == editor_view_mode::split ) {\n''',
    '''    if( relabel_info && active_editor_view_mode == editor_view_mode::split ) {\n        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,\n                   _( "Vehicle relabel  Mount (%+d,%+d)  Editor %d%% / Live %d%%" ),\n                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50,\n                   live_preview_zoom * 50 );\n    } else if( relabel_info ) {\n        const int shown_zoom = active_editor_view_mode == editor_view_mode::live ?\n                               live_preview_zoom : viewport_zoom;\n        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,\n                   _( "Vehicle relabel  Mount (%+d,%+d)  Zoom %d%%" ),\n                   selected_mount().x(), selected_mount().y(), shown_zoom * 50 );\n    } else if( reshape_info && active_editor_view_mode == editor_view_mode::split ) {\n'''
)

# Inspector: show mount label separately; Relabel's part rows are fully helper-driven.
replace_once(
    "src/veh_interact.cpp",
    '''    mvwprintz( w_parts, point( 1, 0 ), c_light_green, _( "Mount (%+d,%+d)" ), mount.x(), mount.y() );\n    if( reshape_info ) {\n''',
    '''    std::string mount_heading = string_format( _( "Mount (%+d,%+d)" ), mount.x(), mount.y() );\n    if( !all_parts.empty() ) {\n        if( const std::optional<std::string> label = vpart_position( *veh, all_parts.front() ).get_label() ) {\n            mount_heading += " — " + *label;\n        }\n    }\n    trim_and_print( w_parts, point( 1, 0 ), std::max( 1, width - 2 ), c_light_green, mount_heading );\n    if( reshape_info ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    } else if( parts.size() == all_parts.size() ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d" ),\n                   static_cast<int>( parts.size() ) );\n''',
    '''    } else if( relabel_info ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray,\n                   relabel_info->target == relabel_info_t::target_t::part ?\n                   _( "Select part: %d" ) : _( "Parts at position: %d" ),\n                   static_cast<int>( parts.size() ) );\n    } else if( parts.size() == all_parts.size() ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d" ),\n                   static_cast<int>( parts.size() ) );\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    const int first_row = 3;\n    const int visible = std::max( 1, height - first_row );\n    part_scroll.set_content_size( static_cast<int>( parts.size() ) )\n    .set_viewport_size( visible );\n\n    if( parts.empty() && first_row < height ) {\n''',
    '''    const int first_row = 3;\n    const int visible = std::max( 1, height - first_row );\n    if( relabel_info ) {\n        ui_selection_list_style list_style;\n        list_style.text = relabel_info->target == relabel_info_t::target_t::part ? c_light_gray : c_dark_gray;\n        list_style.disabled = c_dark_gray;\n        list_style.cursor = hilite( c_white );\n        relabel_info->part_list.draw( w_parts, point( 2, first_row ), std::max( 1, width - 3 ),\n                                      visible, list_style );\n        wnoutrefresh( w_parts );\n        return;\n    }\n    part_scroll.set_content_size( static_cast<int>( parts.size() ) )\n    .set_viewport_size( visible );\n\n    if( parts.empty() && first_row < height ) {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''                        name_color, vp.name() );\n''',
    '''                        name_color, editor_part_display_name( vp ) );\n'''
)

# New lower-right Relabel pane mirrors Reshape's title/separator/footer structure.
replace_once(
    "src/veh_interact.cpp",
    '''void veh_interact::display_part_details()\n{\n''',
    r'''void veh_interact::display_relabel_pane()
{
    werase( w_msg );
    if( !relabel_info ) {
        wnoutrefresh( w_msg );
        return;
    }
    sync_relabel_selection();
    relabel_info_t &info = *relabel_info;
    const int width = getmaxx( w_msg );
    const int height = getmaxy( w_msg );
    const bool part_mode = info.target == relabel_info_t::target_t::part;

    trim_and_print( w_msg, point( 1, 0 ), std::max( 1, width - 2 ), c_light_green, _( "Relabel" ) );
    std::vector<ui_action_entry> modes = {
        ui_action_entry( _( "Position" ), "RELABEL_MODE_POSITION", true, !part_mode ),
        ui_action_entry( _( "Part" ), "RELABEL_MODE_PART", true, part_mode )
    };
    ui_action_strip_style mode_style;
    mode_style.gap = 1;
    mode_style.group_gap = 1;
    info.mode_strip.configure( w_msg, point( 1, 1 ), std::move( modes ),
                               std::max( 1, width - 2 ), 1, mode_style );
    info.mode_strip.draw( w_msg );

    if( height > 2 ) {
        wattron( w_msg, c_dark_gray );
        mvwhline( w_msg, point( 1, 2 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_msg, c_dark_gray );
    }

    std::string target;
    if( part_mode ) {
        target = info.target_part >= 0 && info.target_part < veh->part_count() ?
                 editor_part_display_name( veh->part( info.target_part ) ) : _( "No part selected" );
    } else {
        target = string_format( _( "Position (%+d,%+d)" ), info.mount.x(), info.mount.y() );
    }
    if( height > 3 ) {
        trim_and_print( w_msg, point( 1, 3 ), std::max( 1, width - 2 ),
                        part_mode && info.target_part < 0 ? c_dark_gray : c_light_gray, target );
    }

    if( height > 4 ) {
        ui_text_field_style field_style;
        field_style.border = c_light_gray;
        field_style.text = c_white;
        field_style.placeholder = c_dark_gray;
        info.text_field.configure( w_msg, point( 1, 4 ), std::max( 4, width - 2 ),
                                   _( "Label: " ), info.draft, _( "No label" ), false, field_style );
        info.text_field.draw( w_msg );
    }
    if( height > 5 && !info.status.empty() ) {
        trim_and_print( w_msg, point( 1, 5 ), std::max( 1, width - 2 ), c_light_gray, info.status );
    }

    const int footer_y = std::max( 6, height - 2 );
    const bool valid_target = part_mode ? info.target_part >= 0 : !info.part_indices.empty();
    if( footer_y < height ) {
        std::vector<ui_action_strip_item> actions = {
            { ui_action_entry( _( "Edit" ), "RELABEL_EDIT", valid_target, false,
                               _( "Select an occupied position or part first." ) ),
              0, ui_action_alignment::left },
            { ui_action_entry( _( "Apply" ), "RELABEL_APPLY", valid_target, false,
                               _( "Select an occupied position or part first." ) ),
              0, ui_action_alignment::left },
            { ui_action_entry( _( "Back" ), "RELABEL_BACK" ), 1, ui_action_alignment::right }
        };
        ui_action_strip_style action_style;
        action_style.text = c_light_green;
        info.action_strip.configure( w_msg, point( 1, footer_y ), std::move( actions ),
                                     std::max( 1, width - 2 ), 1, action_style );
        info.action_strip.draw( w_msg );
    } else {
        info.action_strip.clear();
    }
    if( footer_y + 1 < height ) {
        trim_and_print( w_msg, point( 1, footer_y + 1 ), std::max( 1, width - 2 ), c_dark_gray,
                        part_mode ? _( "Click a part above, then edit/apply its label." ) :
                        _( "Parts are shown for context; the label applies to the whole position." ) );
    }
    wnoutrefresh( w_msg );
}

void veh_interact::display_part_details()
{
'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    trim_and_print( w_msg, point( 1, line++ ), std::max( 1, width - 2 ), c_light_green, vp.name() );\n''',
    '''    trim_and_print( w_msg, point( 1, line++ ), std::max( 1, width - 2 ), c_light_green,\n                    editor_part_display_name( vp ) );\n'''
)

# Toolbar mode owns Back just like Reshape, and presents two explicit relabel actions.
replace_once(
    "src/veh_interact.cpp",
    '''    if( reshape_info ) {\n        editor_toolbar_items.push_back( {\n''',
    '''    if( reshape_info || relabel_info ) {\n        editor_toolbar_items.push_back( {\n'''
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( action == "CHANGE_SHAPE" || action == "RELABEL" ) {\n        return selected() != nullptr;\n    }\n''',
    '''    if( action == "CHANGE_SHAPE" || action == "RELABEL_PART" ) {\n        return selected() != nullptr;\n    }\n    if( action == "RELABEL" || action == "RELABEL_POSITION" ) {\n        return cpart >= 0;\n    }\n'''
)
replace_count(
    "src/veh_interact.cpp",
    '''        add( _( "Relabel…" ), "RELABEL" );\n''',
    '''        add( _( "Relabel position…" ), "RELABEL_POSITION" );\n        add( _( "Relabel part…" ), "RELABEL_PART" );\n''',
    2
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Add retained vehicle relabel mode\n", encoding="utf-8"
)
