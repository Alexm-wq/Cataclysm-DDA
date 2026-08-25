from pathlib import Path

path = Path('src/veh_interact.cpp')
s = path.read_text()

old_condition = '''nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
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
'''
new_condition = '''nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
{
    // Keep these colors reserved for condition so they never collide with the
    // system-category palette used by the editor filters.
    if( !vp.is_broken() && vp.health_percent() < 0.999 && !vp.is_repairable() ) {
        return c_light_red;
    }
    if( vp.is_broken() ) {
        return c_brown;
    }
    if( vp.health_percent() >= 0.999 ) {
        return c_light_green;
    }
    return c_yellow;
}
'''
assert s.count(old_condition) == 1, 'condition color block changed unexpectedly'
s = s.replace(old_condition, new_condition)

start = s.index('std::optional<std::pair<int, nc_color>> veh_interact::editor_mount_display(')
end = s.index('\nstd::vector<int> veh_interact::inspector_parts() const', start)
new_display = '''std::optional<std::pair<int, nc_color>> veh_interact::editor_mount_display(
    const point_rel_ms &mount ) const
{
    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );
    if( all_parts.empty() ) {
        return std::nullopt;
    }

    // Use a shape that cannot be mistaken for a normal vehicle part when a mount
    // belongs to the vehicle but is outside the current layer/filter view.
    const int ghost_symbol = vpart_variant::get_symbol_curses( U'▒' );
    const bool system_active = active_system_filter != editor_system_filter::all;
    const bool condition_active = active_condition_filter != editor_condition_filter::all;
    const bool filter_active = system_active || condition_active;

    const auto matches_filters = [&]( const int idx ) {
        const vehicle_part &part = veh->part( idx );
        return part_matches_system( part ) && part_matches_condition( part );
    };

    // System colors deliberately avoid green/yellow/brown/red, which are reserved
    // for health state: healthy, damaged, broken, and needs replacement.
    const auto system_color = [&]() -> nc_color {
        switch( active_system_filter ) {
            case editor_system_filter::structural:
                return c_white;
            case editor_system_filter::fuel:
                return c_light_blue;
            case editor_system_filter::electrical:
                return c_light_cyan;
            case editor_system_filter::propulsion:
                return c_magenta;
            case editor_system_filter::storage:
                return c_pink;
            case editor_system_filter::controls:
                return c_cyan;
            case editor_system_filter::turrets:
                return c_light_gray;
            case editor_system_filter::all:
            default:
                return c_white;
        }
    };

    const auto filtered_color = [&]( const vehicle_part &part ) -> nc_color {
        // Condition takes precedence when both filters are active so the reserved
        // health colors always keep one unambiguous meaning.
        if( condition_active ) {
            return editor_condition_color( part );
        }
        if( system_active ) {
            return system_color();
        }
        return part.is_broken() ? part.info().color_broken : part.info().color;
    };

    if( active_editor_layer == editor_layer::composite ) {
        const int displayed = veh->part_displayed_at( mount, false );
        if( displayed < 0 ) {
            return std::nullopt;
        }
        const vpart_display shown = veh->get_display_of_tile( mount, true, false );

        // With no filters, Composite is exactly the normal in-game vehicle display.
        if( !filter_active ) {
            return std::make_pair( shown.symbol_curses, shown.color );
        }

        const auto match = std::find_if( all_parts.begin(), all_parts.end(), matches_filters );
        if( match == all_parts.end() ) {
            return std::make_pair( ghost_symbol, c_dark_gray );
        }
        return std::make_pair( shown.symbol_curses, filtered_color( veh->part( *match ) ) );
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
        return std::make_pair( ghost_symbol, c_dark_gray );
    }

    const vehicle_part &part = veh->part( best_part );
    if( filter_active && !matches_filters( best_part ) ) {
        return std::make_pair( ghost_symbol, c_dark_gray );
    }
    return std::make_pair( editor_part_symbol( part ), filtered_color( part ) );
}
'''
s = s[:start] + new_display + s[end:]
path.write_text(s)
