from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text()

def replace_exact(old: str, new: str, label: str, expected: int = 1) -> None:
    global text
    count = text.count(old)
    if count != expected:
        raise SystemExit(f'{label}: expected {expected} match(es), got {count}')
    text = text.replace(old, new, expected)

replace_exact(
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

replace_exact(
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

        // vehicle_selector returns one representative part for each occupied tile.  Vehicle
        // tiles are part stacks, so a trunk tile can resolve to its frame/roof instead of CARGO.
        // Resolve the cargo part at that same mount and use it for both stack access and the
        // item_location, otherwise perfectly reachable trunk fuel can disappear from this list.
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

render_old = '''        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Back ]    [ Cancel ]" ) );
'''
render_new = '''        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        back_label );
        const int cancel_x = std::max( 2, width - 2 - utf8_width( cancel_label ) );
        trim_and_print( w_refuel_overlay, point( cancel_x, height - 2 ),
                        width - cancel_x - 1, c_light_gray, cancel_label );
'''
replace_exact( render_old, render_new, 'Back/Cancel rendering', expected=2 )

replace_exact(
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

replace_exact(
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
