from pathlib import Path

CPP = Path("src/veh_interact.cpp")
HDR = Path("src/veh_interact.h")
cpp = CPP.read_text(encoding="utf-8")
hdr = HDR.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_function_block(text: str, start: str, next_start: str, new_block: str, label: str) -> str:
    start_count = text.count(start)
    next_count = text.count(next_start)
    if start_count != 1 or next_count < 1:
        raise SystemExit(f"{label}: bad markers start={start_count}, next={next_count}")
    begin = text.index(start)
    end = text.index(next_start, begin + len(start))
    return text[:begin] + new_block.rstrip() + "\n\n" + text[end:]

# ----- Header state and declarations -----
hdr = replace_once(
    hdr,
    '''        int viewport_zoom = 2;\n        int selected_part = -1;\n        int part_scroll = 0;\n        int part_detail_scroll = 0;\n        bool viewport_dragging = false;\n        bool viewport_initialized = false;\n''',
    '''        int viewport_zoom = 2;\n        int selected_part = -1;\n        int part_scroll = 0;\n        int part_detail_scroll = 0;\n        bool viewport_dragging = false;\n        bool viewport_initialized = false;\n\n        enum class editor_layer {\n            composite,\n            ground,\n            middle,\n            roof\n        };\n        enum class editor_system_filter {\n            all,\n            structural,\n            fuel,\n            electrical,\n            propulsion,\n            storage,\n            controls,\n            turrets\n        };\n        enum class editor_condition_filter {\n            all,\n            healthy,\n            damaged,\n            broken,\n            replacement\n        };\n        enum class editor_dropdown {\n            none,\n            system,\n            condition\n        };\n\n        editor_layer active_editor_layer = editor_layer::composite;\n        editor_system_filter active_system_filter = editor_system_filter::all;\n        editor_condition_filter active_condition_filter = editor_condition_filter::all;\n        editor_dropdown open_editor_dropdown = editor_dropdown::none;\n''',
    "header visual state",
)

hdr = replace_once(
    hdr,
    '''        point_rel_ms selected_mount() const;\n        point viewport_cell_size() const;\n        point mount_to_viewport( const point_rel_ms &mount ) const;\n        std::optional<point_rel_ms> viewport_to_mount( const point &screen ) const;\n        void center_viewport_on_vehicle();\n        void clamp_viewport_pan();\n        void ensure_selected_mount_visible();\n        void select_mount( map &here, const point_rel_ms &mount );\n        std::vector<int> inspector_parts() const;\n        void reset_part_selection();\n        void scroll_part_inspector( int delta );\n        void scroll_part_details( int delta );\n        bool handle_editor_mouse( map &here, const std::string &action );\n''',
    '''        point_rel_ms selected_mount() const;\n        point viewport_cell_size() const;\n        int editor_viewport_top() const;\n        point mount_to_viewport( const point_rel_ms &mount ) const;\n        std::optional<point_rel_ms> viewport_to_mount( const point &screen ) const;\n        void center_viewport_on_vehicle();\n        void clamp_viewport_pan();\n        void ensure_selected_mount_visible();\n        void select_mount( map &here, const point_rel_ms &mount );\n        bool part_matches_layer( const vehicle_part &vp ) const;\n        bool part_matches_system( const vehicle_part &vp ) const;\n        bool part_matches_condition( const vehicle_part &vp ) const;\n        std::string editor_layer_name( editor_layer layer ) const;\n        std::string editor_system_name( editor_system_filter filter ) const;\n        std::string editor_condition_name( editor_condition_filter filter ) const;\n        void editor_filter_button_geometry( editor_dropdown which, int &x, int &width ) const;\n        void editor_dropdown_geometry( editor_dropdown which, int &x, int &y, int &width, int &height ) const;\n        std::optional<std::pair<int, nc_color>> editor_mount_display( const point_rel_ms &mount ) const;\n        int editor_part_symbol( const vehicle_part &vp ) const;\n        nc_color editor_condition_color( const vehicle_part &vp ) const;\n        std::vector<int> inspector_parts() const;\n        void reset_part_selection();\n        void scroll_part_inspector( int delta );\n        void scroll_part_details( int delta );\n        bool handle_editor_controls_click( const point &pos );\n        bool handle_editor_mouse( map &here, const std::string &action );\n        void display_editor_controls();\n''',
    "header visual helpers",
)

# ----- Viewport geometry: reserve three rows for visual controls -----
cpp = replace_function_block(
    cpp,
    'point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const\n{',
    'void veh_interact::center_viewport_on_vehicle()\n{',
    r'''int veh_interact::editor_viewport_top() const
{
    // Header, layer tabs, and system/condition controls occupy the top rows.
    return std::min( 3, std::max( 1, getmaxy( w_disp ) - 1 ) );
}

point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const
{
    const point cell = viewport_cell_size();
    const int content_top = editor_viewport_top();
    const int content_height = std::max( 1, getmaxy( w_disp ) - content_top );
    const point center( getmaxx( w_disp ) / 2, content_top + content_height / 2 );

    // Use the exact live mount-to-map transform used by vehicle placement and
    // construction checks.  The editor therefore stays north-up and the vehicle
    // appears in the same direction it actually occupies in the world.
    const point grid_mount = veh->coord_translate( mount ).raw();
    const point grid_center = veh->coord_translate( viewport_center_mount ).raw();
    return center + viewport_pan + point( ( grid_mount.x - grid_center.x ) * cell.x,
                                          ( grid_mount.y - grid_center.y ) * cell.y );
}

std::optional<point_rel_ms> veh_interact::viewport_to_mount( const point &screen ) const
{
    if( screen.x < 0 || screen.y < editor_viewport_top() || screen.x >= getmaxx( w_disp ) ||
        screen.y >= getmaxy( w_disp ) ) {
        return std::nullopt;
    }

    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );
    const point cell = viewport_cell_size();
    std::optional<point_rel_ms> best_mount;
    long long best_distance = LLONG_MAX;

    for( int x = bounds.p1.x() - editor_margin; x <= bounds.p2.x() + editor_margin; ++x ) {
        for( int y = bounds.p1.y() - editor_margin; y <= bounds.p2.y() + editor_margin; ++y ) {
            const point_rel_ms mount( x, y );
            const point projected = mount_to_viewport( mount );
            const long long dx = static_cast<long long>( screen.x - projected.x ) * cell.y;
            const long long dy = static_cast<long long>( screen.y - projected.y ) * cell.x;
            const long long distance = dx * dx + dy * dy;
            if( distance < best_distance ) {
                best_distance = distance;
                best_mount = mount;
            }
        }
    }

    return best_mount;
}''',
    "viewport transform block",
)

cpp = replace_function_block(
    cpp,
    'void veh_interact::clamp_viewport_pan()\n{',
    'void veh_interact::ensure_selected_mount_visible()\n{',
    r'''void veh_interact::clamp_viewport_pan()
{
    if( getmaxx( w_disp ) <= 0 || getmaxy( w_disp ) <= editor_viewport_top() ) {
        return;
    }

    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );
    const int min_x = bounds.p1.x() - editor_margin;
    const int max_x = bounds.p2.x() + editor_margin;
    const int min_y = bounds.p1.y() - editor_margin;
    const int max_y = bounds.p2.y() + editor_margin;
    const std::array<point_rel_ms, 4> corners = { {
            point_rel_ms( min_x, min_y ), point_rel_ms( min_x, max_y ),
            point_rel_ms( max_x, min_y ), point_rel_ms( max_x, max_y )
        } };

    int min_grid_x = INT_MAX;
    int max_grid_x = INT_MIN;
    int min_grid_y = INT_MAX;
    int max_grid_y = INT_MIN;
    for( const point_rel_ms &corner : corners ) {
        const point grid = veh->coord_translate( corner ).raw();
        min_grid_x = std::min( min_grid_x, grid.x );
        max_grid_x = std::max( max_grid_x, grid.x );
        min_grid_y = std::min( min_grid_y, grid.y );
        max_grid_y = std::max( max_grid_y, grid.y );
    }

    const point grid_center = veh->coord_translate( viewport_center_mount ).raw();
    const point cell = viewport_cell_size();
    const int content_height = std::max( 1, getmaxy( w_disp ) - editor_viewport_top() );
    const point view_size( getmaxx( w_disp ), content_height );
    const point half( view_size.x / 2, view_size.y / 2 );

    const auto clamp_axis = []( int &pan, const int min_grid, const int max_grid,
    const int center_grid, const int pitch, const int half_view, const int view_size ) {
        const int canvas_min = ( min_grid - center_grid ) * pitch;
        const int canvas_max = ( max_grid - center_grid ) * pitch;
        const int low = pitch - half_view - canvas_max;
        const int high = view_size - pitch - half_view - canvas_min;
        if( low <= high ) {
            pan = std::clamp( pan, low, high );
        } else {
            pan = 0;
        }
    };

    clamp_axis( viewport_pan.x, min_grid_x, max_grid_x, grid_center.x, cell.x, half.x,
                view_size.x );
    clamp_axis( viewport_pan.y, min_grid_y, max_grid_y, grid_center.y, cell.y, half.y,
                view_size.y );
}''',
    "viewport clamp",
)

cpp = replace_function_block(
    cpp,
    'void veh_interact::ensure_selected_mount_visible()\n{',
    'void veh_interact::select_mount( map &here, const point_rel_ms &mount )\n{',
    r'''void veh_interact::ensure_selected_mount_visible()
{
    const point cell = viewport_cell_size();
    const point p = mount_to_viewport( selected_mount() );
    const int left = cell.x;
    const int right = getmaxx( w_disp ) - cell.x - 1;
    const int top = editor_viewport_top() + cell.y;
    const int bottom = getmaxy( w_disp ) - cell.y - 1;

    if( p.x < left ) {
        viewport_pan.x += left - p.x;
    } else if( p.x > right ) {
        viewport_pan.x -= p.x - right;
    }
    if( p.y < top ) {
        viewport_pan.y += top - p.y;
    } else if( p.y > bottom ) {
        viewport_pan.y -= p.y - bottom;
    }
    clamp_viewport_pan();
}''',
    "selected mount visibility",
)

# ----- Visual layer/filter model and filtered inspector -----
cpp = replace_function_block(
    cpp,
    'std::vector<int> veh_interact::inspector_parts() const\n{',
    'void veh_interact::reset_part_selection()\n{',
    r'''bool veh_interact::part_matches_layer( const vehicle_part &vp ) const
{
    if( active_editor_layer == editor_layer::composite ) {
        return true;
    }

    const std::string &location = vp.info().location;
    const bool ground = location == "under" || location == "engine_block" ||
                        location == "on_battery_mount" || location == "fuel_source";
    const bool roof = location == "roof" || location == "on_roof";

    switch( active_editor_layer ) {
        case editor_layer::ground:
            return ground;
        case editor_layer::roof:
            return roof;
        case editor_layer::middle:
            // New or modded locations default to the body/interior layer rather than
            // silently disappearing from all non-composite views.
            return !ground && !roof;
        case editor_layer::composite:
        default:
            return true;
    }
}

bool veh_interact::part_matches_system( const vehicle_part &vp ) const
{
    if( active_system_filter == editor_system_filter::all ) {
        return true;
    }

    const vpart_info &vpi = vp.info();
    switch( active_system_filter ) {
        case editor_system_filter::structural:
            return vpi.location == "structure" || vpi.location == "armor" ||
                   vpi.has_flag( VPFLAG_ARMOR );
        case editor_system_filter::fuel:
            return ( vp.is_fuel_store( false ) && !vp.is_battery() ) || vp.is_tank() ||
                   vp.is_reactor() ||
                   ( vp.is_engine() && !vpi.fuel_type.is_null() && vpi.fuel_type != fuel_type_battery );
        case editor_system_filter::electrical:
            return vp.is_battery() || vp.is_reactor() || vpi.epower != 0_W ||
                   vpi.has_flag( VPFLAG_ALTERNATOR ) || vpi.has_flag( VPFLAG_SOLAR_PANEL ) ||
                   vpi.has_flag( VPFLAG_POWER_TRANSFER ) || vpi.has_flag( VPFLAG_CABLE_PORTS ) ||
                   vpi.has_flag( VPFLAG_RECHARGE ) || vpi.has_flag( VPFLAG_ENABLED_DRAINS_EPOWER ) ||
                   ( vp.is_engine() && vpi.fuel_type == fuel_type_battery );
        case editor_system_filter::propulsion:
            return vp.is_engine() || vpi.has_flag( VPFLAG_WHEEL ) || vpi.has_flag( VPFLAG_ROTOR ) ||
                   vpi.has_flag( VPFLAG_FLOATS );
        case editor_system_filter::storage:
            return vpi.has_flag( VPFLAG_CARGO );
        case editor_system_filter::controls:
            return vpi.has_flag( VPFLAG_CONTROLS ) || vpi.has_flag( VPFLAG_TURRET_CONTROLS );
        case editor_system_filter::turrets:
            return vp.is_turret() || vpi.has_flag( VPFLAG_TURRET_CONTROLS );
        case editor_system_filter::all:
        default:
            return true;
    }
}

bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
{
    if( active_condition_filter == editor_condition_filter::all ) {
        return true;
    }

    const double health = vp.health_percent();
    const bool healthy = !vp.is_broken() && health >= 0.999;
    const bool damaged = !vp.is_broken() && health < 0.999 && vp.is_repairable();
    const bool replacement = !vp.is_broken() && health < 0.999 && !vp.is_repairable();

    switch( active_condition_filter ) {
        case editor_condition_filter::healthy:
            return healthy;
        case editor_condition_filter::damaged:
            return damaged;
        case editor_condition_filter::broken:
            return vp.is_broken();
        case editor_condition_filter::replacement:
            return replacement;
        case editor_condition_filter::all:
        default:
            return true;
    }
}

std::string veh_interact::editor_layer_name( const editor_layer layer ) const
{
    switch( layer ) {
        case editor_layer::ground:
            return _( "Ground" );
        case editor_layer::middle:
            return _( "Middle" );
        case editor_layer::roof:
            return _( "Roof" );
        case editor_layer::composite:
        default:
            return _( "Composite" );
    }
}

std::string veh_interact::editor_system_name( const editor_system_filter filter ) const
{
    switch( filter ) {
        case editor_system_filter::structural:
            return _( "Structural" );
        case editor_system_filter::fuel:
            return _( "Fuel" );
        case editor_system_filter::electrical:
            return _( "Electrical" );
        case editor_system_filter::propulsion:
            return _( "Propulsion" );
        case editor_system_filter::storage:
            return _( "Storage" );
        case editor_system_filter::controls:
            return _( "Controls" );
        case editor_system_filter::turrets:
            return _( "Turrets" );
        case editor_system_filter::all:
        default:
            return _( "All parts" );
    }
}

std::string veh_interact::editor_condition_name( const editor_condition_filter filter ) const
{
    switch( filter ) {
        case editor_condition_filter::healthy:
            return _( "Healthy" );
        case editor_condition_filter::damaged:
            return _( "Damaged" );
        case editor_condition_filter::broken:
            return _( "Broken" );
        case editor_condition_filter::replacement:
            return _( "Needs replacement" );
        case editor_condition_filter::all:
        default:
            return _( "All conditions" );
    }
}

void veh_interact::editor_filter_button_geometry( const editor_dropdown which, int &x, int &width ) const
{
    const std::string system_button = string_format( "[ %s ▼ ]", editor_system_name( active_system_filter ) );
    const int system_x = 9;
    if( which == editor_dropdown::system ) {
        x = system_x;
        width = utf8_width( system_button );
        return;
    }

    const int condition_label_x = system_x + utf8_width( system_button ) + 2;
    x = condition_label_x + utf8_width( _( "Condition: " ) );
    const std::string condition_button = string_format( "[ %s ▼ ]",
                                         editor_condition_name( active_condition_filter ) );
    width = utf8_width( condition_button );
}

void veh_interact::editor_dropdown_geometry( const editor_dropdown which, int &x, int &y,
        int &width, int &height ) const
{
    std::vector<std::string> options;
    if( which == editor_dropdown::system ) {
        for( int i = 0; i <= static_cast<int>( editor_system_filter::turrets ); ++i ) {
            options.push_back( editor_system_name( static_cast<editor_system_filter>( i ) ) );
        }
    } else {
        for( int i = 0; i <= static_cast<int>( editor_condition_filter::replacement ); ++i ) {
            options.push_back( editor_condition_name( static_cast<editor_condition_filter>( i ) ) );
        }
    }

    int button_width = 0;
    editor_filter_button_geometry( which, x, button_width );
    width = 4;
    for( const std::string &option : options ) {
        width = std::max( width, utf8_width( option ) + 4 );
    }
    width = std::min( width, std::max( 4, getmaxx( w_disp ) - 2 ) );
    if( x + width >= getmaxx( w_disp ) ) {
        x = std::max( 1, getmaxx( w_disp ) - width - 1 );
    }
    y = editor_viewport_top();
    height = static_cast<int>( options.size() ) + 2;
}

int veh_interact::editor_part_symbol( const vehicle_part &vp ) const
{
    const vpart_info &vpi = vp.info();
    if( vp.open && vpi.has_flag( VPFLAG_OPENABLE ) ) {
        return '\'';
    }

    auto variant = vpi.variants.find( vp.variant );
    if( variant == vpi.variants.end() ) {
        variant = vpi.variants.begin();
    }
    if( variant == vpi.variants.end() ) {
        return '?';
    }
    return variant->second.get_symbol_curses( 270_degrees - veh->face.dir(), vp.is_broken() );
}

nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
{
    if( vp.is_broken() ) {
        return c_light_red;
    }
    if( vp.health_percent() >= 0.999 ) {
        return c_light_green;
    }
    if( !vp.is_repairable() ) {
        return c_magenta;
    }
    return c_yellow;
}

std::optional<std::pair<int, nc_color>> veh_interact::editor_mount_display(
    const point_rel_ms &mount ) const
{
    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );
    if( all_parts.empty() ) {
        return std::nullopt;
    }

    const auto matches_filters = [&]( const int idx ) {
        const vehicle_part &part = veh->part( idx );
        return part_matches_system( part ) && part_matches_condition( part );
    };

    if( active_editor_layer == editor_layer::composite ) {
        const int displayed = veh->part_displayed_at( mount, false );
        if( displayed < 0 ) {
            return std::nullopt;
        }
        const vpart_display shown = veh->get_display_of_tile( mount, true, false );
        const bool any_match = std::any_of( all_parts.begin(), all_parts.end(), matches_filters );
        const bool filter_active = active_system_filter != editor_system_filter::all ||
                                   active_condition_filter != editor_condition_filter::all;
        return std::make_pair( shown.symbol_curses,
                               filter_active && !any_match ? c_dark_gray : shown.color );
    }

    int best_part = -1;
    int best_z = INT_MIN;
    int best_order = INT_MIN;
    for( const int idx : all_parts ) {
        const vehicle_part &part = veh->part( idx );
        if( !part_matches_layer( part ) ) {
            continue;
        }
        const vpart_info &info = part.info();
        if( info.z_order > best_z || ( info.z_order == best_z && info.list_order >= best_order ) ) {
            best_part = idx;
            best_z = info.z_order;
            best_order = info.list_order;
        }
    }

    if( best_part < 0 ) {
        // Keep the other layers as a faint composite silhouette for spatial context.
        const int displayed = veh->part_displayed_at( mount, false );
        if( displayed < 0 ) {
            return std::nullopt;
        }
        const vpart_display shown = veh->get_display_of_tile( mount, true, false );
        return std::make_pair( shown.symbol_curses, c_dark_gray );
    }

    const vehicle_part &part = veh->part( best_part );
    nc_color color = part.is_broken() ? part.info().color_broken : part.info().color;
    if( !matches_filters( best_part ) ) {
        color = c_dark_gray;
    }
    return std::make_pair( editor_part_symbol( part ), color );
}

std::vector<int> veh_interact::inspector_parts() const
{
    std::vector<int> result;
    for( const int idx : veh->parts_at_relative( selected_mount(), true, false ) ) {
        const vehicle_part &vp = veh->part( idx );
        if( part_matches_layer( vp ) && part_matches_system( vp ) && part_matches_condition( vp ) ) {
            result.push_back( idx );
        }
    }
    return result;
}''',
    "visual filter helpers",
)

cpp = replace_function_block(
    cpp,
    'void veh_interact::reset_part_selection()\n{',
    'void veh_interact::scroll_part_inspector( const int delta )\n{',
    r'''void veh_interact::reset_part_selection()
{
    const std::vector<int> parts = inspector_parts();
    const int previous_part = selected_part;
    selected_part = -1;
    if( previous_part >= 0 && std::find( parts.begin(), parts.end(), previous_part ) != parts.end() ) {
        selected_part = previous_part;
    } else if( cpart >= 0 && std::find( parts.begin(), parts.end(), cpart ) != parts.end() ) {
        selected_part = cpart;
    } else if( !parts.empty() ) {
        selected_part = parts.front();
    }
    part_scroll = 0;
    part_detail_scroll = 0;
}''',
    "part selection reset",
)

# ----- Mouse controls and dropdown click handling -----
cpp = replace_function_block(
    cpp,
    'bool veh_interact::handle_editor_mouse( map &here, const std::string &action )\n{',
    'void veh_interact::display_grid()\n{',
    r'''bool veh_interact::handle_editor_controls_click( const point &pos )
{
    if( pos.x < 0 || pos.x >= getmaxx( w_disp ) || pos.y < 0 || pos.y >= getmaxy( w_disp ) ) {
        return false;
    }

    // Layer tabs are intentionally always visible instead of being another dropdown.
    if( pos.y == 1 ) {
        int x = utf8_width( _( "Layer: " ) ) + 1;
        for( int i = 0; i <= static_cast<int>( editor_layer::roof ); ++i ) {
            const editor_layer layer = static_cast<editor_layer>( i );
            const std::string label = string_format( "[ %s ]", editor_layer_name( layer ) );
            const int width = utf8_width( label );
            if( pos.x >= x && pos.x < x + width ) {
                active_editor_layer = layer;
                open_editor_dropdown = editor_dropdown::none;
                reset_part_selection();
                return true;
            }
            x += width + 1;
        }
        return true;
    }

    if( pos.y == 2 ) {
        for( const editor_dropdown which : { editor_dropdown::system, editor_dropdown::condition } ) {
            int x = 0;
            int width = 0;
            editor_filter_button_geometry( which, x, width );
            if( pos.x >= x && pos.x < x + width ) {
                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;
                return true;
            }
        }
        return true;
    }

    if( open_editor_dropdown != editor_dropdown::none ) {
        int x = 0;
        int y = 0;
        int width = 0;
        int height = 0;
        editor_dropdown_geometry( open_editor_dropdown, x, y, width, height );
        if( pos.x >= x && pos.x < x + width && pos.y >= y && pos.y < y + height ) {
            const int option = pos.y - y - 1;
            if( option >= 0 && option < height - 2 ) {
                if( open_editor_dropdown == editor_dropdown::system ) {
                    active_system_filter = static_cast<editor_system_filter>( option );
                } else {
                    active_condition_filter = static_cast<editor_condition_filter>( option );
                }
                open_editor_dropdown = editor_dropdown::none;
                reset_part_selection();
            }
            return true;
        }
        // Standard dropdown behavior: the first click outside closes it without
        // also selecting a mount underneath the popup.
        open_editor_dropdown = editor_dropdown::none;
        return true;
    }

    return pos.y < editor_viewport_top();
}

bool veh_interact::handle_editor_mouse( map &here, const std::string &action )
{
    // get_coordinates_text() deliberately returns coordinates outside a window in
    // the tiles build, so pane routing must bounds-check the relative position.
    const auto mouse_pos_in = [&]( const catacurses::window & win ) -> std::optional<point> {
        const std::optional<point> pos = main_context.get_coordinates_text( win );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( win ) ||
            pos->y >= getmaxy( win ) ) {
            return std::nullopt;
        }
        return pos;
    };

    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );
    const std::optional<point> parts_pos = mouse_pos_in( w_parts );
    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_viewport_content = viewport_pos && viewport_pos->y >= editor_viewport_top();

#if defined(TILES)
    const bool middle_mouse_down = is_middle_mouse_button_down();
    const bool mouse_focused = has_sdl_mouse_focus();
    if( viewport_dragging && ( !middle_mouse_down || !mouse_focused ) ) {
        viewport_dragging = false;
        set_sdl_mouse_capture( false );
    }
    if( action == "MOUSE_MOVE" && !viewport_dragging && middle_mouse_down && mouse_focused &&
        over_viewport_content && open_editor_dropdown == editor_dropdown::none ) {
        viewport_dragging = true;
        viewport_drag_anchor = *viewport_pos;
        viewport_drag_pan_origin = viewport_pan;
        set_sdl_mouse_capture( true );
        return true;
    }
#endif

    if( action == "CAMERA_PAN_START" ) {
        if( over_viewport_content && open_editor_dropdown == editor_dropdown::none ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        return false;
    }
    if( action == "CAMERA_PAN_END" ) {
        if( viewport_dragging ) {
            viewport_dragging = false;
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            return true;
        }
#if defined(TILES)
        set_sdl_mouse_capture( false );
#endif
        return false;
    }
    if( action == "MOUSE_MOVE" && viewport_dragging ) {
        if( viewport_pos ) {
            viewport_pan = viewport_drag_pan_origin + ( *viewport_pos - viewport_drag_anchor );
            clamp_viewport_pan();
        }
        return true;
    }

    if( action == "SELECT" && !install_info && !remove_info ) {
        if( viewport_pos && handle_editor_controls_click( *viewport_pos ) ) {
            return true;
        }
        if( open_editor_dropdown != editor_dropdown::none ) {
            open_editor_dropdown = editor_dropdown::none;
            return true;
        }
        if( viewport_pos ) {
            if( const std::optional<point_rel_ms> mount = viewport_to_mount( *viewport_pos ) ) {
                select_mount( here, *mount );
            }
            return true;
        }
        if( parts_pos && parts_pos->y >= 3 ) {
            const std::vector<int> parts = inspector_parts();
            const int row = part_scroll + parts_pos->y - 3;
            if( row >= 0 && row < static_cast<int>( parts.size() ) ) {
                selected_part = parts[row];
                part_detail_scroll = 0;
            }
            return true;
        }
    }

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        if( open_editor_dropdown != editor_dropdown::none ) {
            return true;
        }
        const int direction = action == "SCROLL_UP" ? -1 : 1;
        if( !install_info && !remove_info && parts_pos ) {
            scroll_part_inspector( direction );
            return true;
        }
        if( !install_info && !remove_info && details_pos ) {
            scroll_part_details( direction );
            return true;
        }
        if( over_viewport_content ) {
            const std::optional<point_rel_ms> anchor = viewport_to_mount( *viewport_pos );
            const int old_zoom = viewport_zoom;
            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 3 );
            if( viewport_zoom != old_zoom && anchor ) {
                const point after = mount_to_viewport( *anchor );
                viewport_pan += *viewport_pos - after;
                clamp_viewport_pan();
            }
            return true;
        }
    }

    return false;
}''',
    "editor mouse routing",
)

# ----- Viewport visual rendering and controls -----
cpp = replace_function_block(
    cpp,
    'void veh_interact::display_veh( map &here )\n{',
    'void veh_interact::display_part_inspector()\n{',
    r'''void veh_interact::display_editor_controls()
{
    const int width = getmaxx( w_disp );
    if( width <= 2 ) {
        return;
    }

    // Layer tabs: persistent and directly clickable because there are only four.
    mvwprintz( w_disp, point( 1, 1 ), c_light_gray, _( "Layer: " ) );
    int layer_x = utf8_width( _( "Layer: " ) ) + 1;
    for( int i = 0; i <= static_cast<int>( editor_layer::roof ); ++i ) {
        const editor_layer layer = static_cast<editor_layer>( i );
        const std::string label = string_format( "[ %s ]", editor_layer_name( layer ) );
        const nc_color color = layer == active_editor_layer ? h_light_cyan : c_light_cyan;
        const int label_width = utf8_width( label );
        if( layer_x < width - 1 ) {
            trim_and_print( w_disp, point( layer_x, 1 ), std::max( 1, width - layer_x - 1 ), color, label );
        }
        layer_x += label_width + 1;
    }

    mvwprintz( w_disp, point( 1, 2 ), c_light_gray, _( "System: " ) );
    int system_x = 0;
    int system_width = 0;
    editor_filter_button_geometry( editor_dropdown::system, system_x, system_width );
    const std::string system_button = string_format( "[ %s ▼ ]",
                                      editor_system_name( active_system_filter ) );
    if( system_x < width - 1 ) {
        trim_and_print( w_disp, point( system_x, 2 ), std::max( 1, width - system_x - 1 ),
                        open_editor_dropdown == editor_dropdown::system ? h_light_cyan : c_light_cyan,
                        system_button );
    }

    const int condition_label_x = system_x + system_width + 2;
    if( condition_label_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_label_x, 2 ), std::max( 1, width - condition_label_x - 1 ),
                        c_light_gray, _( "Condition: " ) );
    }
    int condition_x = 0;
    int condition_width = 0;
    editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );
    const std::string condition_button = string_format( "[ %s ▼ ]",
                                         editor_condition_name( active_condition_filter ) );
    if( condition_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),
                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,
                        condition_button );
    }

    if( open_editor_dropdown == editor_dropdown::none ) {
        return;
    }

    int x = 0;
    int y = 0;
    int dropdown_width = 0;
    int dropdown_height = 0;
    editor_dropdown_geometry( open_editor_dropdown, x, y, dropdown_width, dropdown_height );
    const int max_height = std::max( 0, getmaxy( w_disp ) - y );
    dropdown_height = std::min( dropdown_height, max_height );
    if( dropdown_height < 3 ) {
        return;
    }

    const std::string blank( dropdown_width, ' ' );
    for( int row = 0; row < dropdown_height; ++row ) {
        trim_and_print( w_disp, point( x, y + row ), dropdown_width, c_black, blank );
    }
    wattron( w_disp, c_light_cyan );
    mvwhline( w_disp, point( x, y ), LINE_OXOX, dropdown_width );
    mvwhline( w_disp, point( x, y + dropdown_height - 1 ), LINE_OXOX, dropdown_width );
    mvwvline( w_disp, point( x, y ), LINE_XOXO, dropdown_height );
    mvwvline( w_disp, point( x + dropdown_width - 1, y ), LINE_XOXO, dropdown_height );
    wattroff( w_disp, c_light_cyan );
    mvwputch( w_disp, point( x, y ), c_light_cyan, LINE_OXXO );
    mvwputch( w_disp, point( x + dropdown_width - 1, y ), c_light_cyan, LINE_OOXX );
    mvwputch( w_disp, point( x, y + dropdown_height - 1 ), c_light_cyan, LINE_XXOO );
    mvwputch( w_disp, point( x + dropdown_width - 1, y + dropdown_height - 1 ),
              c_light_cyan, LINE_XOOX );

    const int option_count = dropdown_height - 2;
    for( int i = 0; i < option_count; ++i ) {
        std::string option;
        bool selected = false;
        if( open_editor_dropdown == editor_dropdown::system ) {
            const editor_system_filter filter = static_cast<editor_system_filter>( i );
            option = editor_system_name( filter );
            selected = filter == active_system_filter;
        } else {
            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );
            option = editor_condition_name( filter );
            selected = filter == active_condition_filter;
        }
        trim_and_print( w_disp, point( x + 2, y + 1 + i ), std::max( 1, dropdown_width - 4 ),
                        selected ? h_light_cyan : c_light_gray, option );
    }
}

/**
 * Draws the primary vehicle editor viewport.
 */
void veh_interact::display_veh( map &here )
{
    werase( w_disp );
    if( !viewport_initialized ) {
        center_viewport_on_vehicle();
    }
    clamp_viewport_pan();

    const point cell = viewport_cell_size();
    const int content_top = editor_viewport_top();
    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );

    for( int x = bounds.p1.x() - editor_margin; x <= bounds.p2.x() + editor_margin; ++x ) {
        for( int y = bounds.p1.y() - editor_margin; y <= bounds.p2.y() + editor_margin; ++y ) {
            const point_rel_ms mount( x, y );
            const point screen = mount_to_viewport( mount );
            if( screen.x >= 0 && screen.y >= content_top && screen.x < getmaxx( w_disp ) &&
                screen.y < getmaxy( w_disp ) ) {
                mvwputch( w_disp, screen, c_dark_gray, '.' );
                if( const std::optional<std::pair<int, nc_color>> shown = editor_mount_display( mount ) ) {
                    mvwputch( w_disp, screen, shown->second, shown->first );
                }
            }
        }
    }

    if( debug_mode ) {
        const point_rel_ms &pivot = veh->pivot_point( here );
        const point_rel_ms &com = veh->local_center_of_mass( here );
        const point com_s = mount_to_viewport( com );
        const point pivot_s = mount_to_viewport( pivot );
        if( com_s.x >= 0 && com_s.y >= content_top && com_s.x < getmaxx( w_disp ) &&
            com_s.y < getmaxy( w_disp ) ) {
            mvwputch( w_disp, com_s, c_green, 'C' );
        }
        if( pivot_s.x >= 0 && pivot_s.y >= content_top && pivot_s.x < getmaxx( w_disp ) &&
            pivot_s.y < getmaxy( w_disp ) ) {
            mvwputch( w_disp, pivot_s, c_red, 'P' );
        }
    }

    const point selected_screen = mount_to_viewport( selected_mount() );
    if( selected_screen.x >= 0 && selected_screen.y >= content_top &&
        selected_screen.x < getmaxx( w_disp ) && selected_screen.y < getmaxy( w_disp ) ) {
        int sym = '.';
        nc_color col = c_dark_gray;
        if( const std::optional<std::pair<int, nc_color>> shown = editor_mount_display( selected_mount() ) ) {
            sym = shown->first;
            col = shown->second;
        }

        const tripoint_bub_ms world_pos = veh->pos_bub( here ) + veh->coord_translate( selected_mount() );
        const optional_vpart_position ovp = here.veh_at( world_pos );
        col = hilite( col );
        if( here.impassable_ter_furn( world_pos ) || ( ovp && &ovp->vehicle() != veh ) ) {
            col = red_background( col );
        }

        mvwputch( w_disp, selected_screen, col, sym );
        if( selected_screen.x > 0 ) {
            mvwputch( w_disp, point( selected_screen.x - 1, selected_screen.y ), c_yellow, '[' );
        }
        if( selected_screen.x + 1 < getmaxx( w_disp ) ) {
            mvwputch( w_disp, point( selected_screen.x + 1, selected_screen.y ), c_yellow, ']' );
        }
        if( cell.y >= 2 && selected_screen.y > content_top ) {
            mvwputch( w_disp, point( selected_screen.x, selected_screen.y - 1 ), c_yellow, '^' );
        }
        if( cell.y >= 2 && selected_screen.y + 1 < getmaxy( w_disp ) ) {
            mvwputch( w_disp, point( selected_screen.x, selected_screen.y + 1 ), c_yellow, 'v' );
        }
    }

    mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
               _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%" ),
               selected_mount().x(), selected_mount().y(), viewport_zoom * 50 );
    display_editor_controls();
    wnoutrefresh( w_disp );
}''',
    "vehicle viewport rendering",
)

cpp = replace_function_block(
    cpp,
    'void veh_interact::display_part_inspector()\n{',
    'void veh_interact::display_part_details()\n{',
    r'''void veh_interact::display_part_inspector()
{
    werase( w_parts );
    const int width = getmaxx( w_parts );
    const int height = getmaxy( w_parts );
    const point_rel_ms mount = selected_mount();
    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );
    const std::vector<int> parts = inspector_parts();

    mvwprintz( w_parts, point( 1, 0 ), c_light_green, _( "Mount (%+d,%+d)" ), mount.x(), mount.y() );
    if( parts.size() == all_parts.size() ) {
        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d" ),
                   static_cast<int>( parts.size() ) );
    } else {
        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d/%d" ),
                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );
    }
    if( height > 2 ) {
        wattron( w_parts, c_dark_gray );
        mvwhline( w_parts, point( 1, 2 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_parts, c_dark_gray );
    }

    const int first_row = 3;
    const int visible = std::max( 1, height - first_row );
    const int max_scroll = std::max( 0, static_cast<int>( parts.size() ) - visible );
    part_scroll = std::clamp( part_scroll, 0, max_scroll );

    if( parts.empty() && first_row < height ) {
        trim_and_print( w_parts, point( 2, first_row ), std::max( 1, width - 4 ), c_dark_gray,
                        _( "No parts match this view." ) );
    }

    for( int row = 0; row < visible; ++row ) {
        const int idx = part_scroll + row;
        if( idx >= static_cast<int>( parts.size() ) ) {
            break;
        }
        const int part_idx = parts[idx];
        const vehicle_part &vp = veh->part( part_idx );
        const bool selected = part_idx == selected_part;
        const int health = static_cast<int>( std::lround( vp.health_percent() * 100.0 ) );
        nc_color name_color = vp.is_broken() ? c_dark_gray : c_light_gray;
        nc_color condition_color = editor_condition_color( vp );
        if( selected ) {
            name_color = hilite( name_color );
            condition_color = hilite( condition_color );
        }
        const int percent_x = std::max( 4, width - 6 );
        trim_and_print( w_parts, point( 2, first_row + row ), std::max( 1, percent_x - 3 ),
                        name_color, vp.name() );
        mvwprintz( w_parts, point( percent_x, first_row + row ), condition_color, "%3d%%", health );
    }

    if( static_cast<int>( parts.size() ) > visible ) {
        scrollbar().offset_x( width - 1 ).offset_y( first_row )
        .content_size( static_cast<int>( parts.size() ) ).viewport_pos( part_scroll )
        .viewport_size( visible ).apply( w_parts );
    }
    wnoutrefresh( w_parts );
}''',
    "part inspector rendering",
)

CPP.write_text(cpp, encoding="utf-8")
HDR.write_text(hdr, encoding="utf-8")
