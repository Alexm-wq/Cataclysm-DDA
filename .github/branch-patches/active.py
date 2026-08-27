from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text(encoding="utf-8")

old = '''    const auto filtered_color = [&]( const vehicle_part &part ) -> nc_color {
        // Condition takes precedence when both filters are active so the reserved
        // health colors always keep one unambiguous meaning.
        if( condition_active ) {
            return editor_condition_color( part );
        }
        if( system_active ) {
            return system_color( primary_system_for_part( part ) );
        }
        return part.is_broken() ? part.info().color_broken : part.info().color;
    };
'''
new = '''    const auto filtered_color = [&]( const vehicle_part &part ) -> nc_color {
        // Condition takes precedence when both filters are active so the reserved
        // health colors always keep one unambiguous meaning.
        if( condition_active ) {
            return editor_condition_color( part );
        }
        if( system_active ) {
            return system_color( primary_system_for_part( part ) );
        }
        return part.is_broken() ? part.info().color_broken : part.info().color;
    };

    // A mount can contain several stacked parts.  Geometry/symbol selection still
    // follows z/list ordering, but condition coloring must represent the worst
    // visible matching part so a healthy top part cannot hide damage underneath.
    // Higher values are intentionally more urgent.
    const auto condition_priority = []( const vehicle_part &part ) {
        if( part.is_broken() ) {
            return part.is_repairable() ? 2 : 3;
        }
        return part.health_percent() < 0.999 ? 1 : 0;
    };
'''
if text.count(old) != 1:
    raise SystemExit(f"filtered_color anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

old = '''        int best_match = -1;
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
            return std::make_pair( ghost_symbol, c_light_gray );
        }
        const vehicle_part &match_part = veh->part( best_match );
        return std::make_pair( editor_part_symbol( match_part ), filtered_color( match_part ) );
'''
new = '''        int best_match = -1;
        int best_match_z = INT_MIN;
        int best_match_order = INT_MIN;
        int worst_condition_match = -1;
        int worst_condition_priority = -1;
        for( const int idx : all_parts ) {
            if( !matches_filters( idx ) ) {
                continue;
            }
            const vehicle_part &candidate = veh->part( idx );
            const vpart_info &info = candidate.info();
            if( info.z_order > best_match_z ||
                ( info.z_order == best_match_z && info.list_order >= best_match_order ) ) {
                best_match = idx;
                best_match_z = info.z_order;
                best_match_order = info.list_order;
            }
            const int priority = condition_priority( candidate );
            if( priority > worst_condition_priority ) {
                worst_condition_match = idx;
                worst_condition_priority = priority;
            }
        }
        if( best_match < 0 ) {
            return std::make_pair( ghost_symbol, c_light_gray );
        }
        const vehicle_part &match_part = veh->part( best_match );
        const nc_color color = condition_active && worst_condition_match >= 0 ?
                               editor_condition_color( veh->part( worst_condition_match ) ) :
                               filtered_color( match_part );
        return std::make_pair( editor_part_symbol( match_part ), color );
'''
if text.count(old) != 1:
    raise SystemExit(f"composite anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

old = '''    int best_part = -1;
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
        return std::make_pair( ghost_symbol, c_light_gray );
    }

    const vehicle_part &part = veh->part( best_part );
    if( filter_active && !matches_filters( best_part ) ) {
        return std::make_pair( ghost_symbol, c_light_gray );
    }
    return std::make_pair( editor_part_symbol( part ), filtered_color( part ) );
'''
new = '''    int best_part = -1;
    int best_z = INT_MIN;
    int best_order = INT_MIN;
    int worst_condition_part = -1;
    int worst_condition_priority = -1;
    for( const int idx : all_parts ) {
        const vehicle_part &part = veh->part( idx );
        if( !part_matches_layer( part ) || ( filter_active && !matches_filters( idx ) ) ) {
            continue;
        }
        const vpart_info &info = part.info();
        if( info.z_order > best_z || ( info.z_order == best_z && info.list_order >= best_order ) ) {
            best_part = idx;
            best_z = info.z_order;
            best_order = info.list_order;
        }
        const int priority = condition_priority( part );
        if( priority > worst_condition_priority ) {
            worst_condition_part = idx;
            worst_condition_priority = priority;
        }
    }

    if( best_part < 0 ) {
        return std::make_pair( ghost_symbol, c_light_gray );
    }

    const vehicle_part &part = veh->part( best_part );
    const nc_color color = condition_active && worst_condition_part >= 0 ?
                           editor_condition_color( veh->part( worst_condition_part ) ) :
                           filtered_color( part );
    return std::make_pair( editor_part_symbol( part ), color );
'''
if text.count(old) != 1:
    raise SystemExit(f"layer anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Prioritize worst vehicle condition color per mount\n", encoding="utf-8"
)
