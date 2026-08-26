from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text()

def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, got {count}')
    text = text.replace(old, new, 1)

replace_once(
'''            if( action == "QUIT" ) {
                if( refuel_info->stage == refuel_stage::tank ) {
                    close_refuel_mode();
                } else {
                    refuel_info->stage = refuel_stage::tank;
                    refuel_info->source_range_anchor = -1;
                    msg.reset();
                    refresh_refuel_sources( here );
                }
                continue;
            }
''',
'''            if( action == "QUIT" ) {
                // QUIT/Esc is Cancel for the entire transactional refuel workflow.
                // The explicit Back button is what returns to the tank-selection stage.
                close_refuel_mode();
                continue;
            }
''',
'QUIT semantics'
)

replace_once(
'''    vehicle_selector nearby_vehicles( here, player_character.pos_bub(), 1, true );
    for( const vehicle_cursor &cursor : nearby_vehicles ) {
        if( cursor.part < 0 || cursor.part >= cursor.veh.part_count() ) {
            continue;
        }
        vehicle_part &cargo = cursor.veh.part( cursor.part );
        if( !cargo.info().has_flag( VPFLAG_CARGO ) ) {
            continue;
        }
        vehicle_stack stack = cursor.veh.get_items( cargo );
        for( item &it : stack ) {
            add_source( item_location( cursor, &it ) );
        }
    }
''',
'''    vehicle_selector nearby_vehicles( here, player_character.pos_bub(), 1, true );
    for( const vehicle_cursor &cursor : nearby_vehicles ) {
        if( cursor.part < 0 || cursor.part >= cursor.veh.part_count() ) {
            continue;
        }

        // veh_at()/vehicle_selector returns one representative part for a vehicle tile.
        // A trunk tile is usually a stack (frame + cargo + roof/etc.), so that representative
        // part is not guaranteed to be the cargo part. Resolve CARGO at the same mount before
        // reading the stack, and build the item_location with that resolved part as well.
        const int cargo_index = cursor.veh.part_with_feature( static_cast<int>( cursor.part ),
                                VPFLAG_CARGO, true );
        if( cargo_index < 0 ) {
            continue;
        }
        vehicle_part &cargo = cursor.veh.part( cargo_index );
        vehicle_cursor cargo_cursor( cursor.veh, cargo_index );
        vehicle_stack stack = cursor.veh.get_items( cargo );
        for( item &it : stack ) {
            add_source( item_location( cargo_cursor, &it ) );
        }
    }
''',
'vehicle cargo source discovery'
)

replace_once(
'''        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Back ]    [ Cancel ]" ) );
''',
'''        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        back_label );
        const int cancel_x = std::max( 2, width - 2 - utf8_width( cancel_label ) );
        trim_and_print( w_refuel_overlay, point( cancel_x, height - 2 ),
                        width - cancel_x - 1, c_light_gray, cancel_label );
''',
'source Back/Cancel rendering'
)

replace_once(
'''        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Back ]    [ Cancel ]" ) );
''',
'''        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        back_label );
        const int cancel_x = std::max( 2, width - 2 - utf8_width( cancel_label ) );
        trim_and_print( w_refuel_overlay, point( cancel_x, height - 2 ),
                        width - cancel_x - 1, c_light_gray, cancel_label );
''',
'quick Back/Cancel rendering'
)

replace_once(
'''        if( pos->y == height - 2 ) {
            const int cancel_x = getmaxx( w_refuel_overlay ) / 2;
            if( pos->x >= cancel_x ) {
                close_refuel_mode();
            } else {
                refuel_info->stage = refuel_stage::tank;
                refuel_info->source_range_anchor = -1;
                refresh_refuel_sources( here );
            }
            return true;
        }
''',
'''        if( pos->y == height - 2 ) {
            const std::string back_label = _( "[ Back ]" );
            const std::string cancel_label = _( "[ Cancel ]" );
            const int back_x = 2;
            const int cancel_x = std::max( 2, getmaxx( w_refuel_overlay ) - 2 -
                                           utf8_width( cancel_label ) );
            if( pos->x >= cancel_x && pos->x < cancel_x + utf8_width( cancel_label ) ) {
                close_refuel_mode();
            } else if( pos->x >= back_x && pos->x < back_x + utf8_width( back_label ) ) {
                refuel_info->stage = refuel_stage::tank;
                refuel_info->source_range_anchor = -1;
                refresh_refuel_sources( here );
            }
            return true;
        }
''',
'source Back/Cancel hitboxes'
)

replace_once(
'''    if( pos->y == height - 2 ) {
        const int cancel_x = getmaxx( w_refuel_overlay ) / 2;
        if( pos->x >= cancel_x ) {
            close_refuel_mode();
        } else {
            refuel_info->stage = refuel_stage::tank;
            refresh_refuel_sources( here );
        }
        return true;
    }
''',
'''    if( pos->y == height - 2 ) {
        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        const int back_x = 2;
        const int cancel_x = std::max( 2, getmaxx( w_refuel_overlay ) - 2 -
                                       utf8_width( cancel_label ) );
        if( pos->x >= cancel_x && pos->x < cancel_x + utf8_width( cancel_label ) ) {
            close_refuel_mode();
        } else if( pos->x >= back_x && pos->x < back_x + utf8_width( back_label ) ) {
            refuel_info->stage = refuel_stage::tank;
            refresh_refuel_sources( here );
        }
        return true;
    }
''',
'quick Back/Cancel hitboxes'
)

path.write_text(text)
