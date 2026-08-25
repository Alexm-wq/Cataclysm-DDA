from pathlib import Path

TARGET = "89a0f6d8621d4479af655c8ac8744ef179b74db8"
h = Path("src/veh_interact.h")
c = Path("src/veh_interact.cpp")
hs = h.read_text()
cs = c.read_text()

old_enum = '''        enum class editor_system_filter {
            all,
            structural,
            fuel,
            electrical,
            propulsion,
            storage,
            controls,
            turrets
        };'''
new_enum = '''        enum class editor_system_filter {
            all,
            structural,
            propulsion,
            fuel,
            electrical,
            storage,
            controls,
            passenger,
            lighting,
            utility,
            turrets,
            combat,
            other
        };'''
assert old_enum in hs
hs = hs.replace(old_enum, new_enum, 1)

old_decl = '        bool part_matches_system( const vehicle_part &vp ) const;\n'
new_decl = ('        editor_system_filter primary_system_for_part( const vehicle_part &vp ) const;\n'
            '        bool part_matches_system( const vehicle_part &vp ) const;\n')
assert old_decl in hs
hs = hs.replace(old_decl, new_decl, 1)

start = cs.index('bool veh_interact::part_matches_system( const vehicle_part &vp ) const\n{')
end = cs.index('\nbool veh_interact::part_matches_condition', start)
new_system = r'''veh_interact::editor_system_filter veh_interact::primary_system_for_part(
    const vehicle_part &vp ) const
{
    const vpart_info &vpi = vp.info();

    // The editor uses one semantic identity per part.  CDDA vehicle parts can
    // advertise several installation categories/capabilities at once (for example
    // seats are PASSENGERS + OPERATIONS and also have a small CARGO pocket), so
    // broad capability matching makes the diagnostic view misleading.
    if( vp.is_turret() || vpi.has_flag( VPFLAG_TURRET_CONTROLS ) ) {
        return editor_system_filter::turrets;
    }
    if( vpi.has_category( "passengers" ) ) {
        return editor_system_filter::passenger;
    }
    if( vpi.has_category( "cargo" ) ) {
        return editor_system_filter::storage;
    }
    // Fuel/fluid tanks share CDDA's movement installation category with engines.
    // Split them before the general movement rule so engines and wheels remain
    // propulsion while actual tanks become Fuel.
    if( vpi.has_category( "movement" ) && vpi.has_flag( VPFLAG_FLUIDTANK ) ) {
        return editor_system_filter::fuel;
    }
    if( vpi.has_category( "movement" ) ) {
        return editor_system_filter::propulsion;
    }
    if( vpi.has_category( "operations" ) ) {
        return editor_system_filter::controls;
    }
    if( vpi.has_category( "energy" ) ) {
        return editor_system_filter::electrical;
    }
    if( vpi.has_category( "lighting" ) ) {
        return editor_system_filter::lighting;
    }
    if( vpi.has_category( "utility" ) ) {
        return editor_system_filter::utility;
    }
    if( vpi.has_category( "hull" ) ) {
        return editor_system_filter::structural;
    }
    if( vpi.has_category( "warfare" ) ) {
        return editor_system_filter::combat;
    }
    return editor_system_filter::other;
}

bool veh_interact::part_matches_system( const vehicle_part &vp ) const
{
    return active_system_filter == editor_system_filter::all ||
           primary_system_for_part( vp ) == active_system_filter;
}
'''
cs = cs[:start] + new_system + cs[end:]

old_condition = r'''bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
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
'''
new_condition = r'''bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
{
    if( active_condition_filter == editor_condition_filter::all ) {
        return true;
    }

    const double health = vp.health_percent();
    const bool healthy = health >= 0.999;
    const bool replacement = health < 0.999 && !vp.is_repairable();
    const bool broken = vp.is_broken() && vp.is_repairable();
    const bool damaged = !vp.is_broken() && health < 0.999 && vp.is_repairable();

    switch( active_condition_filter ) {
        case editor_condition_filter::healthy:
            return healthy;
        case editor_condition_filter::damaged:
            return damaged;
        case editor_condition_filter::broken:
            return broken;
        case editor_condition_filter::replacement:
            return replacement;
        case editor_condition_filter::all:
        default:
            return true;
    }
}
'''
assert old_condition in cs
cs = cs.replace(old_condition, new_condition, 1)

start = cs.index('std::string veh_interact::editor_system_name( const editor_system_filter filter ) const\n{')
end = cs.index('\nstd::string veh_interact::editor_condition_name', start)
new_names = r'''std::string veh_interact::editor_system_name( const editor_system_filter filter ) const
{
    switch( filter ) {
        case editor_system_filter::structural:
            return _( "Structural" );
        case editor_system_filter::propulsion:
            return _( "Propulsion" );
        case editor_system_filter::fuel:
            return _( "Fuel" );
        case editor_system_filter::electrical:
            return _( "Electrical" );
        case editor_system_filter::storage:
            return _( "Storage" );
        case editor_system_filter::controls:
            return _( "Controls" );
        case editor_system_filter::passenger:
            return _( "Passenger" );
        case editor_system_filter::lighting:
            return _( "Lighting" );
        case editor_system_filter::utility:
            return _( "Utility" );
        case editor_system_filter::turrets:
            return _( "Turrets" );
        case editor_system_filter::combat:
            return _( "Combat" );
        case editor_system_filter::other:
            return _( "Other" );
        case editor_system_filter::all:
        default:
            return _( "All parts" );
    }
}
'''
cs = cs[:start] + new_names + cs[end:]

cs = cs.replace('static_cast<int>( editor_system_filter::turrets )',
                'static_cast<int>( editor_system_filter::other )')

old_cond_color = r'''nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
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
new_cond_color = r'''nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
{
    // Reserved condition palette: healthy green, damaged yellow, broken orange,
    // irreparable/needs-replacement red.  Irreparable wins even at zero HP.
    if( vp.health_percent() < 0.999 && !vp.is_repairable() ) {
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
assert old_cond_color in cs
cs = cs.replace(old_cond_color, new_cond_color, 1)

old_switch = r'''        switch( active_system_filter ) {
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
'''
new_switch = r'''        switch( active_system_filter ) {
            case editor_system_filter::structural:
                return c_white;
            case editor_system_filter::propulsion:
                return c_magenta;
            case editor_system_filter::fuel:
                return c_light_blue;
            case editor_system_filter::electrical:
                return c_light_cyan;
            case editor_system_filter::storage:
                return c_pink;
            case editor_system_filter::controls:
                return c_cyan;
            case editor_system_filter::passenger:
                return c_blue;
            case editor_system_filter::lighting:
                return c_light_gray;
            case editor_system_filter::utility:
                return c_magenta;
            case editor_system_filter::turrets:
                return c_cyan;
            case editor_system_filter::combat:
                return c_pink;
            case editor_system_filter::other:
                return c_light_gray;
            case editor_system_filter::all:
            default:
                return c_white;
        }
'''
assert old_switch in cs
cs = cs.replace(old_switch, new_switch, 1)

# Under an active filter, show the actual matching part glyph instead of coloring
# an unrelated composite top glyph at the same mount.
old_composite_match = r'''        const auto match = std::find_if( all_parts.begin(), all_parts.end(), matches_filters );
        if( match == all_parts.end() ) {
            return std::make_pair( ghost_symbol, c_dark_gray );
        }
        return std::make_pair( shown.symbol_curses, filtered_color( veh->part( *match ) ) );
'''
new_composite_match = r'''        int best_match = -1;
        int best_match_z = INT_MIN;
        int best_match_order = INT_MIN;
        for( const int idx : all_parts ) {
            if( !matches_filters( idx ) ) {
                continue;
            }
            const vpart_info &info = veh->part( idx ).info();
            if( info.z_order > best_match_z ||
                ( info.z_order == best_match_z && info.list_order >= best_match_order ) ) {
                best_match = idx;
                best_match_z = info.z_order;
                best_match_order = info.list_order;
            }
        }
        if( best_match < 0 ) {
            return std::make_pair( ghost_symbol, c_dark_gray );
        }
        const vehicle_part &match_part = veh->part( best_match );
        return std::make_pair( editor_part_symbol( match_part ), filtered_color( match_part ) );
'''
assert old_composite_match in cs
cs = cs.replace(old_composite_match, new_composite_match, 1)

h.write_text(hs)
c.write_text(cs)
