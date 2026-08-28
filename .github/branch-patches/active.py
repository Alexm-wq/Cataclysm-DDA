from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


# Make siphon history reflect transfers that actually completed, not only the
# plan that existed when the button was pressed.
p = Path("src/activity_actor_definitions.h")
s = p.read_text()
s = replace_once(
    s,
    '''        vehicle_siphon_activity_actor( std::vector<player_activity> transfers,
                                      tripoint_abs_ms vehicle_pos, point_rel_ms editor_cursor ) :
            transfers( std::move( transfers ) ), vehicle_pos( vehicle_pos ), editor_cursor( editor_cursor ) {}
''',
    '''        vehicle_siphon_activity_actor( std::vector<player_activity> transfers,
                                      tripoint_abs_ms vehicle_pos, point_rel_ms editor_cursor,
                                      itype_id fuel_type = itype_id::NULL_ID(),
                                      std::vector<int> transfer_source_parts = {},
                                      std::vector<std::string> transfer_source_labels = {},
                                      std::vector<int> transfer_destination_slots = {},
                                      std::vector<std::string> destination_labels = {},
                                      std::vector<int> destination_kinds = {} ) :
            transfers( std::move( transfers ) ), vehicle_pos( vehicle_pos ), editor_cursor( editor_cursor ),
            fuel_type( std::move( fuel_type ) ), transfer_source_parts( std::move( transfer_source_parts ) ),
            transfer_source_labels( std::move( transfer_source_labels ) ),
            transfer_destination_slots( std::move( transfer_destination_slots ) ),
            destination_labels( std::move( destination_labels ) ),
            destination_kinds( std::move( destination_kinds ) ) {}
''',
    "siphon actor constructor",
)
s = replace_once(
    s,
    '''        std::vector<player_activity> transfers;
        tripoint_abs_ms vehicle_pos;
        point_rel_ms editor_cursor;
        int next_transfer = 0;
''',
    '''        std::vector<player_activity> transfers;
        tripoint_abs_ms vehicle_pos;
        point_rel_ms editor_cursor;
        itype_id fuel_type = itype_id::NULL_ID();
        std::vector<int> transfer_source_parts;
        std::vector<std::string> transfer_source_labels;
        std::vector<int> transfer_destination_slots;
        std::vector<std::string> destination_labels;
        // 0 = item container, 1 = vehicle tank.
        std::vector<int> destination_kinds;
        std::vector<int> used_transfers;
        int transferred_charges = 0;
        int next_transfer = 0;
''',
    "siphon actor fields",
)
p.write_text(s)


p = Path("src/activity_actor.cpp")
s = p.read_text()
s = replace_once(
    s,
    '''        who.add_msg_if_player( m_info, _( "You can no longer siphon from this vehicle." ) );
        veh_interact::clear_staged_editor_action();
        veh_interact::discard_persistent_editor();
''',
    '''        who.add_msg_if_player( m_info, _( "You can no longer siphon from this vehicle." ) );
        veh_interact::discard_persistent_editor();
''',
    "remove siphon staged clear",
)
s = replace_once(
    s,
    '''    if( next_transfer >= 0 && next_transfer < static_cast<int>( transfers.size() ) ) {
        player_activity &transfer = transfers[next_transfer];
        // The liquid handler revalidates reach for both containers and vehicle tanks.
        activity_handlers::fill_liquid_do_turn( &transfer, &who );
        if( transfer.is_null() ) {
            ++next_transfer;
        }
    }
''',
    '''    if( next_transfer >= 0 && next_transfer < static_cast<int>( transfers.size() ) ) {
        const int transfer_index = next_transfer;
        player_activity &transfer = transfers[transfer_index];
        int source_before = -1;
        if( transfer_index < static_cast<int>( transfer_source_parts.size() ) ) {
            const int source_part = transfer_source_parts[transfer_index];
            if( source_part >= 0 && source_part < source->vehicle().part_count() &&
                !source->vehicle().part( source_part ).removed ) {
                source_before = source->vehicle().part( source_part ).ammo_remaining();
            }
        }
        // The liquid handler revalidates reach for both containers and vehicle tanks.
        activity_handlers::fill_liquid_do_turn( &transfer, &who );
        if( source_before >= 0 && transfer_index < static_cast<int>( transfer_source_parts.size() ) ) {
            const int source_part = transfer_source_parts[transfer_index];
            if( source_part >= 0 && source_part < source->vehicle().part_count() &&
                !source->vehicle().part( source_part ).removed ) {
                const int moved = std::max( 0, source_before -
                                            source->vehicle().part( source_part ).ammo_remaining() );
                if( moved > 0 ) {
                    transferred_charges += moved;
                    if( std::find( used_transfers.begin(), used_transfers.end(), transfer_index ) ==
                        used_transfers.end() ) {
                        used_transfers.push_back( transfer_index );
                    }
                }
            }
        }
        if( transfer.is_null() ) {
            ++next_transfer;
        }
    }
''',
    "track completed siphon charges",
)
s = replace_once(
    s,
    '''    if( source && who.is_avatar() ) {
        veh_interact::commit_staged_editor_action( &source->vehicle() );
        here.invalidate_map_cache( here.get_abs_sub().z() );
''',
    '''    if( source && who.is_avatar() ) {
        if( transferred_charges > 0 && !fuel_type.is_null() && !used_transfers.empty() ) {
            std::set<int> used_sources;
            std::set<int> used_destinations;
            for( const int transfer_index : used_transfers ) {
                if( transfer_index >= 0 &&
                    transfer_index < static_cast<int>( transfer_source_parts.size() ) ) {
                    used_sources.insert( transfer_source_parts[transfer_index] );
                }
                if( transfer_index >= 0 &&
                    transfer_index < static_cast<int>( transfer_destination_slots.size() ) ) {
                    used_destinations.insert( transfer_destination_slots[transfer_index] );
                }
            }

            std::string source_summary;
            if( used_sources.size() == 1 ) {
                const int source_part = *used_sources.begin();
                for( size_t i = 0; i < transfer_source_parts.size() &&
                     i < transfer_source_labels.size(); ++i ) {
                    if( transfer_source_parts[i] == source_part ) {
                        source_summary = transfer_source_labels[i];
                        break;
                    }
                }
            } else {
                source_summary = string_format( _( "%d tanks" ), static_cast<int>( used_sources.size() ) );
            }

            std::string destination_summary;
            if( used_destinations.size() == 1 ) {
                const int slot = *used_destinations.begin();
                if( slot >= 0 && slot < static_cast<int>( destination_labels.size() ) ) {
                    destination_summary = destination_labels[slot];
                }
            } else {
                int containers = 0;
                int tanks = 0;
                for( const int slot : used_destinations ) {
                    if( slot >= 0 && slot < static_cast<int>( destination_kinds.size() ) &&
                        destination_kinds[slot] == 1 ) {
                        ++tanks;
                    } else {
                        ++containers;
                    }
                }
                if( tanks == 0 ) {
                    destination_summary = string_format( _( "%d containers" ), containers );
                } else if( containers == 0 ) {
                    destination_summary = string_format( _( "%d tanks" ), tanks );
                } else {
                    destination_summary = string_format( _( "%d destinations" ),
                                                         static_cast<int>( used_destinations.size() ) );
                }
            }

            item transferred_liquid( fuel_type );
            transferred_liquid.charges = transferred_charges;
            veh_interact::record_editor_action( source->vehicle(), string_format(
                    _( "Siphoned %1$.1f L of %2$s from %3$s to %4$s" ),
                    units::to_liter( transferred_liquid.volume() ), item::nname( fuel_type ),
                    source_summary, destination_summary ) );
        }
        here.invalidate_map_cache( here.get_abs_sub().z() );
''',
    "commit actual siphon summary",
)
s = replace_once(
    s,
    '''void vehicle_siphon_activity_actor::canceled( player_activity &, Character & )
{
    veh_interact::clear_staged_editor_action();
    veh_interact::discard_persistent_editor();
}
''',
    '''void vehicle_siphon_activity_actor::canceled( player_activity &, Character & )
{
    veh_interact::discard_persistent_editor();
}
''',
    "remove siphon staged cancel clear",
)
s = replace_once(
    s,
    '''    jsout.member( "transfers", transfers );
    jsout.member( "vehicle_pos", vehicle_pos );
    jsout.member( "editor_cursor", editor_cursor );
    jsout.member( "next_transfer", next_transfer );
''',
    '''    jsout.member( "transfers", transfers );
    jsout.member( "vehicle_pos", vehicle_pos );
    jsout.member( "editor_cursor", editor_cursor );
    jsout.member( "fuel_type", fuel_type );
    jsout.member( "transfer_source_parts", transfer_source_parts );
    jsout.member( "transfer_source_labels", transfer_source_labels );
    jsout.member( "transfer_destination_slots", transfer_destination_slots );
    jsout.member( "destination_labels", destination_labels );
    jsout.member( "destination_kinds", destination_kinds );
    jsout.member( "used_transfers", used_transfers );
    jsout.member( "transferred_charges", transferred_charges );
    jsout.member( "next_transfer", next_transfer );
''',
    "serialize siphon history state",
)
s = replace_once(
    s,
    '''    data.read( "transfers", actor.transfers );
    data.read( "vehicle_pos", actor.vehicle_pos );
    data.read( "editor_cursor", actor.editor_cursor );
    data.read( "next_transfer", actor.next_transfer );
''',
    '''    data.read( "transfers", actor.transfers );
    data.read( "vehicle_pos", actor.vehicle_pos );
    data.read( "editor_cursor", actor.editor_cursor );
    data.read( "fuel_type", actor.fuel_type );
    data.read( "transfer_source_parts", actor.transfer_source_parts );
    data.read( "transfer_source_labels", actor.transfer_source_labels );
    data.read( "transfer_destination_slots", actor.transfer_destination_slots );
    data.read( "destination_labels", actor.destination_labels );
    data.read( "destination_kinds", actor.destination_kinds );
    data.read( "used_transfers", actor.used_transfers );
    data.read( "transferred_charges", actor.transferred_charges );
    data.read( "next_transfer", actor.next_transfer );
''',
    "deserialize siphon history state",
)
p.write_text(s)


p = Path("src/veh_interact.cpp")
s = p.read_text()
s = replace_once(
    s,
    '''    std::vector<int> capacity;
    for( const auto &destination : destinations ) {
        capacity.push_back( liquid_handler::siphon_destination_capacity( destination, *info.liquid, who ) );
    }
    std::vector<player_activity> transfers;
    std::vector<int> used_sources;
    std::set<size_t> used_destinations;
    int total_transfer_charges = 0;
    int64_t remaining_total = 0;
''',
    '''    std::vector<int> capacity;
    std::vector<std::string> destination_labels;
    std::vector<int> destination_kinds;
    for( const auto &destination : destinations ) {
        capacity.push_back( liquid_handler::siphon_destination_capacity( destination, *info.liquid, who ) );
        if( destination.container ) {
            destination_labels.push_back( destination.container->display_name() );
            destination_kinds.push_back( 0 );
        } else if( destination.tank ) {
            destination_labels.push_back( string_format( _( "%1$s on %2$s" ),
                                          editor_part_display_name( destination.tank->part() ),
                                          destination.tank->vehicle().name ) );
            destination_kinds.push_back( 1 );
        } else {
            destination_labels.emplace_back();
            destination_kinds.push_back( 0 );
        }
    }
    std::vector<player_activity> transfers;
    std::vector<int> transfer_source_parts;
    std::vector<std::string> transfer_source_labels;
    std::vector<int> transfer_destination_slots;
    int64_t remaining_total = 0;
''',
    "prepare siphon actor metadata",
)
s = replace_once(
    s,
    '''        int remaining = veh->part( source ).ammo_remaining();
        bool source_used = false;
        for( size_t i = 0; i < destinations.size() && remaining > 0; ++i ) {
''',
    '''        int remaining = veh->part( source ).ammo_remaining();
        for( size_t i = 0; i < destinations.size() && remaining > 0; ++i ) {
''',
    "remove planned source-used flag",
)
s = replace_once(
    s,
    '''                transfers.push_back( liquid_handler::siphon_transfer( *veh, source, destinations[i], amount ) );
                source_used = true;
                used_destinations.insert( i );
                total_transfer_charges += amount;
                capacity[i] -= amount;
                remaining -= amount;
''',
    '''                transfers.push_back( liquid_handler::siphon_transfer( *veh, source, destinations[i], amount ) );
                transfer_source_parts.push_back( source );
                transfer_source_labels.push_back( editor_part_display_name( veh->part( source ) ) );
                transfer_destination_slots.push_back( static_cast<int>( i ) );
                capacity[i] -= amount;
                remaining -= amount;
''',
    "store siphon per-transfer metadata",
)
s = replace_once(
    s,
    '''        if( source_used ) {
            used_sources.push_back( source );
        }
        remaining_total += remaining;
''',
    '''        remaining_total += remaining;
''',
    "remove planned source collection",
)
start = '''    std::string source_summary;
    if( used_sources.size() == 1 ) {
        source_summary = editor_part_display_name( veh->part( used_sources.front() ) );
    } else {
        source_summary = string_format( _( "%d tanks" ), static_cast<int>( used_sources.size() ) );
    }

    std::string destination_summary;
    if( used_destinations.size() == 1 ) {
        const liquid_handler::siphon_destination &destination = destinations[*used_destinations.begin()];
        if( destination.container ) {
            destination_summary = destination.container->display_name();
        } else if( destination.tank ) {
            destination_summary = string_format( _( "%1$s on %2$s" ),
                                                 editor_part_display_name( destination.tank->part() ),
                                                 destination.tank->vehicle().name );
        }
    } else {
        int containers = 0;
        int tanks = 0;
        for( const size_t index : used_destinations ) {
            if( destinations[index].container ) {
                ++containers;
            } else if( destinations[index].tank ) {
                ++tanks;
            }
        }
        if( tanks == 0 ) {
            destination_summary = string_format( _( "%d containers" ), containers );
        } else if( containers == 0 ) {
            destination_summary = string_format( _( "%d tanks" ), tanks );
        } else {
            destination_summary = string_format( _( "%d destinations" ),
                                                 static_cast<int>( used_destinations.size() ) );
        }
    }

    item transferred_liquid( *info.liquid );
    transferred_liquid.charges = total_transfer_charges;
    stage_editor_action( *veh, string_format(
                             _( "Siphoned %1$.1f L of %2$s from %3$s to %4$s" ),
                             units::to_liter( transferred_liquid.volume() ),
                             item::nname( info.liquid->typeId() ), source_summary, destination_summary ) );
    resource_transfer_activity = player_activity( vehicle_siphon_activity_actor(
                                     std::move( transfers ), veh->abs_part_pos( 0 ), dd ) );
'''
replacement = '''    resource_transfer_activity = player_activity( vehicle_siphon_activity_actor(
                                     std::move( transfers ), veh->abs_part_pos( 0 ), dd,
                                     info.liquid->typeId(), std::move( transfer_source_parts ),
                                     std::move( transfer_source_labels ),
                                     std::move( transfer_destination_slots ),
                                     std::move( destination_labels ), std::move( destination_kinds ) ) );
'''
s = replace_once(s, start, replacement, "move siphon summary to completion actor")

s = replace_once(
    s,
    '''                    const int qty = src->charges;
                    vp.base.reload( you, std::move( src ), qty );
                    if( qty > 0 ) {
                        history_fuel = fuel_type;
                        history_charges += qty;
                        used_target_parts.insert( part_index );
                        if( source_index >= 0 ) {
                            used_source_groups.insert( source_index );
                        }
                    }
''',
    '''                    const int qty = src->charges;
                    const int before = vp.ammo_remaining();
                    const bool reloaded = vp.base.reload( you, std::move( src ), qty );
                    const int moved = reloaded ? std::max( 0, vp.ammo_remaining() - before ) : 0;
                    if( moved > 0 ) {
                        history_fuel = fuel_type;
                        history_charges += moved;
                        used_target_parts.insert( part_index );
                        if( source_index >= 0 ) {
                            used_source_groups.insert( source_index );
                        }
                    }
''',
    "count actual solid fuel moved",
)
p.write_text(s)

Path("/tmp/branch_patch_commit_message").write_text(
    "Refine vehicle editor action history accounting\n"
)
