from pathlib import Path

cpp_path = Path('src/veh_interact.cpp')
h_path = Path('src/veh_interact.h')
cpp = cpp_path.read_text()
h = h_path.read_text()


def rep(text, old, new, label, count=1):
    found = text.count(old)
    if found != count:
        raise SystemExit(f'{label}: expected {count} match(es), got {found}')
    return text.replace(old, new, count)


# ----- header state / methods -----
h = rep(h,
'''        struct remove_info_t;\n\n        std::unique_ptr<remove_info_t> remove_info;\n\n        struct refuel_info_t;\n''',
'''        struct remove_info_t;\n\n        std::unique_ptr<remove_info_t> remove_info;\n\n        struct reshape_info_t;\n\n        std::unique_ptr<reshape_info_t> reshape_info;\n\n        struct refuel_info_t;\n''',
'reshape state declaration')

h = rep(h,
'''        void do_refill( map &here );\n        void refresh_refuel_sources( map &here );\n''',
'''        void do_refill( map &here );\n        void open_reshape_mode();\n        void close_reshape_mode();\n        void sync_reshape_selection();\n        void preview_reshape_variant( int index );\n        bool apply_reshape_variant();\n        bool handle_reshape_mouse( const std::string &action );\n        void refresh_refuel_sources( map &here );\n''',
'reshape task methods')

h = rep(h,
'''        void display_part_inspector();\n        void display_part_details();\n''',
'''        void display_part_inspector();\n        void display_part_details();\n        void display_reshape_pane();\n''',
'reshape display method')

# ----- cpp state -----
cpp = rep(cpp,
'''struct veh_interact::remove_info_t {\n    int pos = 0;\n    size_t tab = 0;\n};\n\nstruct veh_interact::refuel_info_t {\n''',
'''struct veh_interact::remove_info_t {\n    int pos = 0;\n    size_t tab = 0;\n};\n\nstruct veh_interact::reshape_info_t {\n    int target_part = -1;\n    int variant_pos = 0;\n    int variant_scroll = 0;\n    std::vector<std::string> variants;\n    std::string committed_variant;\n    int last_clicked_variant = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_click_time;\n};\n\nstruct veh_interact::refuel_info_t {\n''',
'reshape state definition')

# Activity re-entry cannot retain a cosmetic editor mode around a vehicle mutation.
cpp = rep(cpp,
'''    install_info.reset();\n    remove_info.reset();\n    refuel_info.reset();\n''',
'''    install_info.reset();\n    remove_info.reset();\n    reshape_info.reset();\n    refuel_info.reset();\n''',
'reset reshape on activity handoff')

# Draw reshape as the normal selectable part inspector plus a dedicated lower-right palette.
cpp = rep(cpp,
'''            if( !install_info && !remove_info ) {\n                display_part_inspector();\n                if( msg.has_value() ) {\n                    draw_message_window();\n                } else {\n                    display_part_details();\n                }\n            } else {\n''',
'''            if( reshape_info ) {\n                display_part_inspector();\n                display_reshape_pane();\n            } else if( !install_info && !remove_info ) {\n                display_part_inspector();\n                if( msg.has_value() ) {\n                    draw_message_window();\n                } else {\n                    display_part_details();\n                }\n            } else {\n''',
'reshape redraw branch')

# Keep the reshape target synchronized before every frame so mount/filter/part changes
# restore any uncommitted preview before selecting the new exact stacked part.
cpp = rep(cpp,
'''    while( !finish ) {\n        calc_overview( here );\n        if( install_info ) {\n''',
'''    while( !finish ) {\n        calc_overview( here );\n        if( reshape_info ) {\n            sync_reshape_selection();\n        }\n        if( install_info ) {\n''',
'sync reshape each frame')

# Reshape owns Back/Escape like the other persistent editor modes.
cpp = rep(cpp,
'''        if( action == "QUIT" && refuel_info ) {\n            close_refuel_mode();\n            continue;\n        }\n\n        // Escape dismisses transient editor menus before it is allowed to close\n''',
'''        if( action == "QUIT" && refuel_info ) {\n            close_refuel_mode();\n            continue;\n        }\n        if( action == "QUIT" && reshape_info ) {\n            close_reshape_mode();\n            continue;\n        }\n\n        // Escape dismisses transient editor menus before it is allowed to close\n''',
'reshape escape priority')

# Enter confirms the currently previewed variant without closing reshape, allowing rapid
# work across several parts on the same mount/vehicle.
cpp = rep(cpp,
'''        if( refuel_info ) {\n            using refuel_stage = refuel_info_t::stage_t;\n''',
'''        if( reshape_info && action == "CONFIRM" ) {\n            apply_reshape_variant();\n            continue;\n        }\n\n        if( refuel_info ) {\n            using refuel_stage = refuel_info_t::stage_t;\n''',
'reshape confirm handling')

# Change Shape now opens the embedded editor instead of leaving veh_interact for veh_shape.
cpp = rep(cpp,
'''        } else if( action == "CHANGE_SHAPE" ) {\n            sel_cmd = 'p';\n        } else if( action == "ASSIGN_CREW" ) {\n''',
'''        } else if( action == "CHANGE_SHAPE" ) {\n            open_reshape_mode();\n        } else if( action == "ASSIGN_CREW" ) {\n''',
'embedded reshape action')

# 200% zoom is a fourth schematic scale. Live preview remains on its existing camera scale.
cpp = rep(cpp,
'''point veh_interact::viewport_cell_size() const\n{\n    switch( viewport_zoom ) {\n        case 1:\n            return point( 2, 1 );\n        case 3:\n            return point( 6, 3 );\n        case 2:\n        default:\n            return point( 4, 2 );\n    }\n}\n''',
'''point veh_interact::viewport_cell_size() const\n{\n    switch( viewport_zoom ) {\n        case 1:\n            return point( 2, 1 );\n        case 3:\n            return point( 6, 3 );\n        case 4:\n            return point( 8, 4 );\n        case 2:\n        default:\n            return point( 4, 2 );\n    }\n}\n''',
'200 percent viewport scale')

cpp = rep(cpp,
'''int veh_interact::editor_schematic_width() const\n{\n    const int width = getmaxx( w_disp );\n    switch( active_editor_view_mode ) {\n''',
'''int veh_interact::editor_schematic_width() const\n{\n    const int width = getmaxx( w_disp );\n    // Reshape reuses the canonical schematic camera and transform, but always gives\n    // it the full left editor pane. This avoids creating a second camera/pan state\n    // for a mode whose right-hand shape browser already lives outside w_disp.\n    if( reshape_info ) {\n        return width;\n    }\n    switch( active_editor_view_mode ) {\n''',
'full schematic during reshape')

cpp = rep(cpp,
'''bool veh_interact::point_in_live_preview( const point &screen ) const\n{\n    if( screen.y < editor_viewport_top() || screen.y >= getmaxy( w_disp ) ||\n''',
'''bool veh_interact::point_in_live_preview( const point &screen ) const\n{\n    if( reshape_info ) {\n        return false;\n    }\n    if( screen.y < editor_viewport_top() || screen.y >= getmaxy( w_disp ) ||\n''',
'no live preview hit testing during reshape')

# Disable view-mode tab switching while reshape temporarily owns the full schematic.
cpp = rep(cpp,
'''    if( pos.y == 0 ) {\n        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{\n''',
'''    if( pos.y == 0 ) {\n        if( reshape_info ) {\n            return true;\n        }\n        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{\n''',
'disable view tabs in reshape')

# Add Reshape to the exact-part context menu only when that exact part has alternatives.
cpp = rep(cpp,
'''            const vpart_info &vpi = part.info();\n            const bool uninstallable = !vpi.has_flag( "NO_UNINSTALL" ) &&\n                                       veh->can_unmount( part ).success();\n            add_entry( _( "Remove" ), "EDITOR_REMOVE", uninstallable,\n''',
'''            const vpart_info &vpi = part.info();\n            if( vpi.variants.size() > 1 ) {\n                add_entry( _( "Reshape…" ), "EDITOR_RESHAPE" );\n            }\n            const bool uninstallable = !vpi.has_flag( "NO_UNINSTALL" ) &&\n                                       veh->can_unmount( part ).success();\n            add_entry( _( "Remove" ), "EDITOR_REMOVE", uninstallable,\n''',
'right click reshape action')

# Dispatch context reshape to the same embedded mode used by the toolbar.
cpp = rep(cpp,
'''    avatar &player_character = get_avatar();\n\n    if( selected_action == "EDITOR_REMOVE" ) {\n''',
'''    avatar &player_character = get_avatar();\n\n    if( selected_action == "EDITOR_RESHAPE" ) {\n        open_reshape_mode();\n        return true;\n    }\n\n    if( selected_action == "EDITOR_REMOVE" ) {\n''',
'context reshape dispatch')

# Route lower-right palette input before generic details scrolling. The regular upper-right
# part list and the vehicle viewport stay live/selectable underneath the mode.
cpp = rep(cpp,
'''    if( refuel_info ) {\n        return handle_refuel_mouse( here, action );\n    }\n\n    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {\n''',
'''    if( refuel_info ) {\n        return handle_refuel_mouse( here, action );\n    }\n    if( reshape_info && handle_reshape_mouse( action ) ) {\n        return true;\n    }\n\n    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {\n''',
'route reshape mouse palette')

# Context menus should not open on top of the reshape palette; reshape itself remains
# available from right click in the normal editor before entering the mode.
cpp = rep(cpp,
'''    if( action == "SEC_SELECT" && !remove_info ) {\n''',
'''    if( action == "SEC_SELECT" && !remove_info && !reshape_info ) {\n''',
'no context overlay inside reshape')

# Exact stacked-part clicks immediately retarget the reshape browser. sync_reshape_selection()
# restores any uncommitted preview from the previous part first.
cpp = rep(cpp,
'''            if( row >= 0 && row < static_cast<int>( parts.size() ) ) {\n                selected_part = parts[row];\n                part_detail_scroll = 0;\n            }\n            return true;\n''',
'''            if( row >= 0 && row < static_cast<int>( parts.size() ) ) {\n                selected_part = parts[row];\n                part_detail_scroll = 0;\n                if( reshape_info ) {\n                    sync_reshape_selection();\n                }\n            }\n            return true;\n''',
'retarget reshape from inspector click')

cpp = rep(cpp,
'''            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 3 );\n''',
'''            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 4 );\n''',
'200 percent wheel zoom')

# Force the embedded reshape viewport to render as the full schematic even if the player's
# normal editor preference is Live or Split. The preference itself is preserved for exit.
cpp = rep(cpp,
'''    if( active_editor_view_mode == editor_view_mode::split && schematic_width > 0 &&\n        schematic_width < getmaxx( w_disp ) ) {\n''',
'''    if( !reshape_info && active_editor_view_mode == editor_view_mode::split && schematic_width > 0 &&\n        schematic_width < getmaxx( w_disp ) ) {\n''',
'no split divider in reshape')

cpp = rep(cpp,
'''    if( active_editor_view_mode == editor_view_mode::split ) {\n        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,\n''',
'''    if( reshape_info ) {\n        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,\n                   _( "Vehicle reshape  Mount (%+d,%+d)  Zoom %d%%" ),\n                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50 );\n    } else if( active_editor_view_mode == editor_view_mode::split ) {\n        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,\n''',
'reshape viewport header')

cpp = rep(cpp,
'''#if defined(TILES)\n    if( active_editor_view_mode == editor_view_mode::editor ) {\n''',
'''#if defined(TILES)\n    if( reshape_info || active_editor_view_mode == editor_view_mode::editor ) {\n''',
'suppress live tile preview in reshape')

# Do not draw view tabs in reshape. Layer/system/condition controls remain available and
# continue to govern which stacked parts are selectable in the upper-right inspector.
old_views = '''    // View-mode tabs live at the top-right of the editor pane.  The renderer\n    // itself is switched separately; this state is shared by the forthcoming\n    // Editor / Live / Split viewport implementations.\n    const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{\n            { editor_view_mode::editor, _( "Editor" ) },\n            { editor_view_mode::live, _( "Live" ) },\n            { editor_view_mode::split, _( "Split" ) }\n        }};\n    int view_total_width = 0;\n    for( const auto &view : views ) {\n        view_total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;\n    }\n    int view_x = std::max( 1, width - view_total_width );\n    for( const auto &view : views ) {\n        const std::string label = string_format( "[ %s ]", view.second );\n        const int label_width = utf8_width( label );\n        if( view_x < width - 1 ) {\n            trim_and_print( w_disp, point( view_x, 0 ), std::max( 1, width - view_x - 1 ),\n                            view.first == active_editor_view_mode ? h_light_cyan : c_light_cyan,\n                            label );\n        }\n        view_x += label_width + 1;\n    }\n'''
new_views = '''    // View-mode tabs live at the top-right of the editor pane. Reshape temporarily\n    // owns the complete schematic width, while preserving the player's normal view mode.\n    if( !reshape_info ) {\n        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{\n                { editor_view_mode::editor, _( "Editor" ) },\n                { editor_view_mode::live, _( "Live" ) },\n                { editor_view_mode::split, _( "Split" ) }\n            }};\n        int view_total_width = 0;\n        for( const auto &view : views ) {\n            view_total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;\n        }\n        int view_x = std::max( 1, width - view_total_width );\n        for( const auto &view : views ) {\n            const std::string label = string_format( "[ %s ]", view.second );\n            const int label_width = utf8_width( label );\n            if( view_x < width - 1 ) {\n                trim_and_print( w_disp, point( view_x, 0 ), std::max( 1, width - view_x - 1 ),\n                                view.first == active_editor_view_mode ? h_light_cyan : c_light_cyan,\n                                label );\n            }\n            view_x += label_width + 1;\n        }\n    }\n'''
cpp = rep(cpp, old_views, new_views, 'hide view tabs in reshape')

# While reshape is active the toolbar becomes navigation-only; Apply lives beside the
# shape list where its effect is spatially obvious.
cpp = rep(cpp,
'''    const int width = getmaxx( w_mode );\n    if( width <= 2 ) {\n        return;\n    }\n\n    struct toolbar_candidate {\n''',
'''    const int width = getmaxx( w_mode );\n    if( width <= 2 ) {\n        return;\n    }\n    if( reshape_info ) {\n        const std::string label = _( "Back" );\n        const std::string text = string_format( "[ %s ]", label );\n        const int button_width = utf8_width( text );\n        editor_toolbar_buttons.push_back( { label, "QUIT",\n                                            point( std::max( 1, width - button_width - 1 ), 0 ),\n                                            button_width, true, 4 } );\n        return;\n    }\n\n    struct toolbar_candidate {\n''',
'reshape toolbar back only')

# Disabled direct buttons still populate the right inspector with the same canonical reason
# formatter as their right-click counterparts. Enabled Repair/Remove dispatch the exact
# selected stacked part through that already-working context action path.
cpp = rep(cpp,
'''        if( !button.enabled ) {\n            return true;\n        }\n        if( button.action == "QUIT" ) {\n''',
'''        if( !button.enabled ) {\n            if( button.action == "REPAIR" && selected_part >= 0 && selected_part < veh->part_count() ) {\n                vehicle_part &part = veh->part( selected_part );\n                if( !part.removed && part.mount == selected_mount() ) {\n                    set_editor_repair_requirements( here, part );\n                }\n            } else if( button.action == "REMOVE" && selected_part >= 0 &&\n                       selected_part < veh->part_count() ) {\n                const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;\n                const vpart_info *old_sel_vpart_info = sel_vpart_info;\n                can_remove_part( here, selected_part, get_avatar() );\n                sel_vehicle_part = old_sel_vehicle_part;\n                sel_vpart_info = old_sel_vpart_info;\n            }\n            return true;\n        }\n        if( button.action == "REPAIR" ) {\n            run_editor_context_action( here, "EDITOR_REPAIR" );\n            return true;\n        }\n        if( button.action == "REMOVE" ) {\n            run_editor_context_action( here, "EDITOR_REMOVE" );\n            return true;\n        }\n        if( button.action == "QUIT" ) {\n''',
'direct selected toolbar repair remove')

# ----- embedded reshape implementation -----
reshape_impl = r'''
void veh_interact::open_reshape_mode()
{
    if( reshape_info ) {
        return;
    }
    reshape_info = std::make_unique<reshape_info_t>();
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    viewport_dragging = false;
    live_preview_dragging = false;
#if defined(TILES)
    set_sdl_mouse_capture( false );
    clear_map_preview_window();
#endif
    live_preview_last_draw_mode.reset();
    msg.reset();
    sync_reshape_selection();
    ensure_selected_mount_visible();
}

void veh_interact::close_reshape_mode()
{
    if( !reshape_info ) {
        return;
    }
    const int target = reshape_info->target_part;
    if( target >= 0 && target < veh->part_count() ) {
        vehicle_part &part = veh->part( target );
        if( !part.removed ) {
            part.variant = reshape_info->committed_variant;
        }
    }
    reshape_info.reset();
    msg.reset();
    live_preview_last_draw_mode.reset();
    clamp_viewport_pan();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}

void veh_interact::sync_reshape_selection()
{
    if( !reshape_info || reshape_info->target_part == selected_part ) {
        return;
    }

    const int old_target = reshape_info->target_part;
    if( old_target >= 0 && old_target < veh->part_count() ) {
        vehicle_part &old_part = veh->part( old_target );
        if( !old_part.removed ) {
            old_part.variant = reshape_info->committed_variant;
        }
    }

    reshape_info->target_part = selected_part;
    reshape_info->variant_pos = 0;
    reshape_info->variant_scroll = 0;
    reshape_info->variants.clear();
    reshape_info->committed_variant.clear();
    reshape_info->last_clicked_variant = -1;
    reshape_info->last_click_time.reset();

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        return;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        return;
    }

    reshape_info->committed_variant = part.variant;
    const vpart_info &vpi = part.info();
    if( vpi.variants.size() <= 1 ) {
        return;
    }

    for( const auto &[variant_id, variant] : vpi.variants ) {
        ( void )variant;
        reshape_info->variants.push_back( variant_id );
    }

    const units::angle display_dir = 270_degrees - veh->face.dir();
    const auto symbol_rank = []( const int symbol ) {
        switch( symbol ) {
            case LINE_XOXO:
                return 0;
            case LINE_OXOX:
                return 1;
            case LINE_XOOX:
                return 2;
            case LINE_XXOO:
                return 3;
            case LINE_XXXX:
                return 4;
            case LINE_OXXO:
                return 5;
            case LINE_OOXX:
                return 6;
            default:
                return 1000 + symbol;
        }
    };
    std::stable_sort( reshape_info->variants.begin(), reshape_info->variants.end(),
    [&]( const std::string &lhs, const std::string &rhs ) {
        const vpart_variant &left = vpi.variants.at( lhs );
        const vpart_variant &right = vpi.variants.at( rhs );
        const int left_symbol = left.get_symbol_curses( display_dir, false );
        const int right_symbol = right.get_symbol_curses( display_dir, false );
        const int left_rank = symbol_rank( left_symbol );
        const int right_rank = symbol_rank( right_symbol );
        if( left_rank != right_rank ) {
            return left_rank < right_rank;
        }
        return localized_compare( left.get_label(), right.get_label() );
    } );

    const auto current = std::find( reshape_info->variants.begin(), reshape_info->variants.end(),
                                    part.variant );
    if( current != reshape_info->variants.end() ) {
        reshape_info->variant_pos = static_cast<int>( std::distance( reshape_info->variants.begin(), current ) );
    }
}

void veh_interact::preview_reshape_variant( const int index )
{
    if( !reshape_info || index < 0 || index >= static_cast<int>( reshape_info->variants.size() ) ||
        reshape_info->target_part < 0 || reshape_info->target_part >= veh->part_count() ) {
        return;
    }
    vehicle_part &part = veh->part( reshape_info->target_part );
    if( part.removed || part.mount != selected_mount() ) {
        return;
    }
    reshape_info->variant_pos = index;
    part.variant = reshape_info->variants[index];
}

bool veh_interact::apply_reshape_variant()
{
    if( !reshape_info || reshape_info->variants.empty() || reshape_info->target_part < 0 ||
        reshape_info->target_part >= veh->part_count() ) {
        return false;
    }
    vehicle_part &part = veh->part( reshape_info->target_part );
    if( part.removed || part.mount != selected_mount() ) {
        return false;
    }
    reshape_info->committed_variant = part.variant;
    reshape_info->last_clicked_variant = -1;
    reshape_info->last_click_time.reset();
    msg.reset();
    return true;
}

bool veh_interact::handle_reshape_mouse( const std::string &action )
{
    if( !reshape_info ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_msg );
    if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( w_msg ) ||
        pos->y >= getmaxy( w_msg ) ) {
        return false;
    }

    const int height = getmaxy( w_msg );
    constexpr int first_row = 3;
    const int footer_y = std::max( first_row, height - 2 );
    const int visible = std::max( 0, footer_y - first_row );

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        const int direction = action == "SCROLL_UP" ? -1 : 1;
        const int max_scroll = std::max( 0, static_cast<int>( reshape_info->variants.size() ) - visible );
        reshape_info->variant_scroll = std::clamp( reshape_info->variant_scroll + direction, 0, max_scroll );
        return true;
    }

    if( action != "SELECT" ) {
        return action == "SEC_SELECT";
    }

    if( pos->y >= first_row && pos->y < footer_y ) {
        const int index = reshape_info->variant_scroll + pos->y - first_row;
        if( index >= 0 && index < static_cast<int>( reshape_info->variants.size() ) ) {
            const auto now = std::chrono::steady_clock::now();
            const bool double_click = reshape_info->last_clicked_variant == index &&
                                      reshape_info->last_click_time &&
                                      now - *reshape_info->last_click_time <= std::chrono::milliseconds( 500 );
            preview_reshape_variant( index );
            if( double_click ) {
                apply_reshape_variant();
            } else {
                reshape_info->last_clicked_variant = index;
                reshape_info->last_click_time = now;
            }
        }
        return true;
    }

    if( pos->y == footer_y ) {
        const std::string apply_label = _( "[ Apply ]" );
        const std::string close_label = _( "[ Back ]" );
        const int close_x = std::max( 1, getmaxx( w_msg ) - utf8_width( close_label ) - 1 );
        if( pos->x >= 1 && pos->x < 1 + utf8_width( apply_label ) ) {
            apply_reshape_variant();
        } else if( pos->x >= close_x && pos->x < close_x + utf8_width( close_label ) ) {
            close_reshape_mode();
        }
        return true;
    }
    return true;
}

'''
cpp = rep(cpp,
'''void veh_interact::close_refuel_mode()\n{\n''',
reshape_impl + '''void veh_interact::close_refuel_mode()\n{\n''',
'insert reshape implementation')

reshape_display = r'''
void veh_interact::display_reshape_pane()
{
    werase( w_msg );
    const int width = getmaxx( w_msg );
    const int height = getmaxy( w_msg );
    if( !reshape_info ) {
        wnoutrefresh( w_msg );
        return;
    }

    trim_and_print( w_msg, point( 1, 0 ), std::max( 1, width - 2 ), c_light_green,
                    _( "Shapes / orientation" ) );

    if( reshape_info->target_part < 0 || reshape_info->target_part >= veh->part_count() ) {
        trim_and_print( w_msg, point( 1, 1 ), std::max( 1, width - 2 ), c_dark_gray,
                        _( "Select a vehicle tile, then choose a part above." ) );
    } else {
        const vehicle_part &part = veh->part( reshape_info->target_part );
        trim_and_print( w_msg, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray, part.name() );
    }

    if( height > 2 ) {
        wattron( w_msg, c_dark_gray );
        mvwhline( w_msg, point( 1, 2 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_msg, c_dark_gray );
    }

    constexpr int first_row = 3;
    const int footer_y = std::max( first_row, height - 2 );
    const int visible = std::max( 0, footer_y - first_row );

    if( reshape_info->variants.empty() ) {
        if( first_row < footer_y ) {
            trim_and_print( w_msg, point( 2, first_row ), std::max( 1, width - 4 ), c_dark_gray,
                            _( "This selected part has no alternate shapes." ) );
        }
    } else {
        const int max_scroll = std::max( 0, static_cast<int>( reshape_info->variants.size() ) - visible );
        reshape_info->variant_scroll = std::clamp( reshape_info->variant_scroll, 0, max_scroll );
        if( reshape_info->variant_pos < reshape_info->variant_scroll ) {
            reshape_info->variant_scroll = reshape_info->variant_pos;
        } else if( reshape_info->variant_pos >= reshape_info->variant_scroll + visible && visible > 0 ) {
            reshape_info->variant_scroll = reshape_info->variant_pos - visible + 1;
        }

        const vehicle_part &part = veh->part( reshape_info->target_part );
        const vpart_info &vpi = part.info();
        const units::angle display_dir = 270_degrees - veh->face.dir();
        for( int row = 0; row < visible; ++row ) {
            const int index = reshape_info->variant_scroll + row;
            if( index >= static_cast<int>( reshape_info->variants.size() ) ) {
                break;
            }
            const std::string &id = reshape_info->variants[index];
            const vpart_variant &variant = vpi.variants.at( id );
            const int symbol = variant.get_symbol_curses( display_dir, false );
            const bool selected = index == reshape_info->variant_pos;
            const bool committed = id == reshape_info->committed_variant;
            const std::string label = variant.get_label().empty() ? _( "Default" ) : variant.get_label();
            mvwputch( w_msg, point( 2, first_row + row ),
                      selected ? hilite( vpi.color ) : vpi.color, symbol );
            trim_and_print( w_msg, point( 4, first_row + row ), std::max( 1, width - 6 ),
                            selected ? hilite( c_light_gray ) : c_light_gray,
                            string_format( "%s%s", committed ? "* " : "  ", label ) );
        }
        if( static_cast<int>( reshape_info->variants.size() ) > visible && visible > 0 ) {
            scrollbar().offset_x( width - 1 ).offset_y( first_row )
            .content_size( static_cast<int>( reshape_info->variants.size() ) )
            .viewport_pos( reshape_info->variant_scroll ).viewport_size( visible ).apply( w_msg );
        }
    }

    if( footer_y < height ) {
        const std::string apply_label = _( "[ Apply ]" );
        const std::string back_label = _( "[ Back ]" );
        trim_and_print( w_msg, point( 1, footer_y ), utf8_width( apply_label ),
                        reshape_info->variants.empty() ? c_dark_gray : c_light_green, apply_label );
        const int back_x = std::max( 1, width - utf8_width( back_label ) - 1 );
        trim_and_print( w_msg, point( back_x, footer_y ), utf8_width( back_label ), c_light_gray, back_label );
    }
    if( footer_y + 1 < height ) {
        trim_and_print( w_msg, point( 1, footer_y + 1 ), std::max( 1, width - 2 ), c_dark_gray,
                        _( "Click = preview   Double-click / Apply = save" ) );
    }
    wnoutrefresh( w_msg );
}

'''
cpp = rep(cpp,
'''void veh_interact::display_part_details()\n{\n''',
reshape_display + '''void veh_interact::display_part_details()\n{\n''',
'insert reshape pane renderer')

# Sanity: the legacy external shape UI must no longer be reachable from CHANGE_SHAPE dispatch.
assert 'action == "CHANGE_SHAPE" ) {\n            sel_cmd = \'p\'' not in cpp
assert 'EDITOR_RESHAPE' in cpp
assert 'case 4:\n            return point( 8, 4 );' in cpp
assert 'viewport_zoom - direction, 1, 4' in cpp
assert 'display_reshape_pane();' in cpp
assert 'run_editor_context_action( here, "EDITOR_REMOVE" )' in cpp

cpp_path.write_text(cpp)
h_path.write_text(h)
print('vehicle direct-actions + embedded reshape patch applied')
