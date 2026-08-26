from pathlib import Path

p = Path('src/veh_interact.cpp')
s = p.read_text()


def rep(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    s = s.replace(old, new, 1)


# Centralize the meaning of a tank's currently constrained fuel type so sorting,
# target compatibility, UI affordances and backend validation all agree.
rep(
'''static auto can_refill = []( const map &, const vehicle_part &pt )
{
    return pt.can_reload( );
};

static void act_vehicle_unload_fuel( map &here, vehicle *veh );
''',
'''static auto can_refill = []( const map &, const vehicle_part &pt )
{
    return pt.can_reload( );
};

static itype_id refuel_storage_type( const vehicle_part &part )
{
    if( !part.ammo_current().is_null() ) {
        return part.ammo_current();
    }
    if( !part.info().fuel_type.is_null() ) {
        return part.info().fuel_type;
    }
    return itype_id::NULL_ID();
}

static bool refuel_targets_share_storage( const vehicle &veh, const std::vector<int> &tanks,
        const std::vector<bool> &selected )
{
    if( tanks.size() != selected.size() ) {
        return false;
    }
    std::optional<itype_id> shared_type;
    for( size_t slot = 0; slot < tanks.size(); ++slot ) {
        if( !selected[slot] || tanks[slot] < 0 || tanks[slot] >= veh.part_count() ) {
            continue;
        }
        const itype_id type = refuel_storage_type( veh.part( tanks[slot] ) );
        // An empty generic liquid tank does not constrain the common fuel yet.
        if( type.is_null() ) {
            continue;
        }
        if( shared_type && *shared_type != type ) {
            return false;
        }
        shared_type = type;
    }
    return true;
}

static void act_vehicle_unload_fuel( map &here, vehicle *veh );
''',
'refuel target compatibility helpers')

# Restore row-specific double-click tracking for the tank stage.
rep(
'''    int tank_pos = 0;
    int tank_scroll = 0;
    int tank_range_anchor = -1;

    std::vector<source_t> sources;
''',
'''    int tank_pos = 0;
    int tank_scroll = 0;
    int tank_range_anchor = -1;
    int last_clicked_tank_index = -1;
    std::optional<std::chrono::steady_clock::time_point> last_tank_click_time;

    std::vector<source_t> sources;
''',
'restore tank double-click state')

# Reject heterogeneous target stores in the backend as well as the UI. They can
# remain selected and can enter source selection, but one refill batch cannot mix
# gasoline/battery/etc. target storage.
rep(
'''    if( selected_tank_slots.empty() ) {
        msg = _( "Select at least one fuel store to refill." );
        return false;
    }

    std::vector<int> selected_sources;
''',
'''    if( selected_tank_slots.empty() ) {
        msg = _( "Select at least one fuel store to refill." );
        return false;
    }
    if( !refuel_targets_share_storage( *veh, refuel_info->tanks, refuel_info->tank_selected ) ) {
        msg = _( "Selected fuel stores use different fuel types and cannot be refueled together." );
        return false;
    }

    std::vector<int> selected_sources;
''',
'backend heterogeneous target guard')

# Make the tank stage explain double click again.
rep(
'''                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range" ) );
''',
'''                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range   Double-click = continue" ) );
''',
'tank stage double-click hint')

# Only actual target selections get the inventory-blue overlay. The keyboard/
# wheel cursor remains visible via foreground emphasis without masquerading as a
# second selected row. Also surface heterogeneous target selection immediately.
rep(
'''            nc_color color = usable ? c_light_gray : c_dark_gray;
            if( selected ) {
                color = hilite( c_white );
            } else if( slot == refuel_info->tank_pos ) {
                color = hilite( color );
            }
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );
        }

        const bool any_selected = std::any_of( refuel_info->tank_selected.begin(),
                                  refuel_info->tank_selected.end(), []( const bool selected ) {
            return selected;
        } );
        const int choose_y = height - ( editor_test_mode ? 5 : 4 );
        trim_and_print( w_refuel_overlay, point( 2, choose_y ), width - 4,
                        any_selected ? c_light_green : c_dark_gray, _( "[ Choose fuel sources ]" ) );
''',
'''            nc_color color = usable ? c_light_gray : c_dark_gray;
            if( selected ) {
                color = hilite( c_white );
            } else if( slot == refuel_info->tank_pos && usable ) {
                color = c_white;
            }
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );
        }

        const bool any_selected = std::any_of( refuel_info->tank_selected.begin(),
                                  refuel_info->tank_selected.end(), []( const bool selected ) {
            return selected;
        } );
        const bool compatible_targets = !any_selected ||
                                        refuel_targets_share_storage( *veh, refuel_info->tanks,
                                                refuel_info->tank_selected );
        if( any_selected && !compatible_targets ) {
            trim_and_print( w_refuel_overlay, point( 2, 2 ), width - 4, c_light_red,
                            _( "Selected fuel stores use different fuel types and cannot be refueled together." ) );
        }
        const int choose_y = height - ( editor_test_mode ? 5 : 4 );
        trim_and_print( w_refuel_overlay, point( 2, choose_y ), width - 4,
                        any_selected ? c_light_green : c_dark_gray, _( "[ Choose fuel sources ]" ) );
''',
'distinguish tank cursor and selected targets')

# Disable the actual Refuel-selected affordance when the chosen target stores use
# different storage types, while leaving the target set intact and visible.
rep(
'''        const std::string selection_status = mixed_fuels ?
                _( "Selected containers contain different fuel types and cannot be refueled together." ) :
                string_format( _( "Selected: %1$d source(s)   Targets: %2$d fuel store(s)" ),
                               selected_count, static_cast<int>( selected_tank_slots.size() ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4,
                        mixed_fuels ? c_light_red : c_light_gray, selection_status );
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4,
                        mixed_fuels ? c_dark_gray : c_light_green, _( "[ Refuel selected ]" ) );
''',
'''        const bool compatible_targets = refuel_targets_share_storage( *veh, refuel_info->tanks,
                                        refuel_info->tank_selected );
        const bool refuel_disabled = mixed_fuels || !compatible_targets;
        const std::string selection_status = !compatible_targets ?
                _( "Selected fuel stores use different fuel types and cannot be refueled together." ) :
                mixed_fuels ?
                _( "Selected containers contain different fuel types and cannot be refueled together." ) :
                string_format( _( "Selected: %1$d source(s)   Targets: %2$d fuel store(s)" ),
                               selected_count, static_cast<int>( selected_tank_slots.size() ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4,
                        refuel_disabled ? c_light_red : c_light_gray, selection_status );
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4,
                        refuel_disabled ? c_dark_gray : c_light_green, _( "[ Refuel selected ]" ) );
''',
'disable heterogeneous target refuel action')

# Restore double-click advancement without sacrificing a Ctrl-created multi-select.
# If the first unmodified click lands on a row already in a multi-selection, keep
# the selection intact long enough for the second click to advance it.
rep(
'''            const input_event raw = main_context.get_raw_input();
            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;
            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;

            if( shift && refuel_info->tank_range_anchor >= 0 ) {
                if( !ctrl ) {
                    std::fill( refuel_info->tank_selected.begin(), refuel_info->tank_selected.end(), false );
                }
                const int first = std::min( refuel_info->tank_range_anchor, slot );
                const int last = std::max( refuel_info->tank_range_anchor, slot );
                for( int i = first; i <= last; ++i ) {
                    const int range_part = refuel_info->tanks[i];
                    if( range_part >= 0 && range_part < veh->part_count() && veh->part( range_part ).can_reload() ) {
                        refuel_info->tank_selected[i] = true;
                    }
                }
            } else if( ctrl ) {
                refuel_info->tank_selected[slot] = !refuel_info->tank_selected[slot];
                refuel_info->tank_range_anchor = slot;
            } else {
                std::fill( refuel_info->tank_selected.begin(), refuel_info->tank_selected.end(), false );
                refuel_info->tank_selected[slot] = true;
                refuel_info->tank_range_anchor = slot;
            }

            // Tank-row clicks only modify target selection.  Advancing to fuel
            // sources is explicit via the button or keyboard confirm, so a rapid
            // second click can never consume or collapse a multi-selection.
            return true;
''',
'''            const input_event raw = main_context.get_raw_input();
            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;
            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;
            const auto now = std::chrono::steady_clock::now();
            const bool double_click = !ctrl && !shift &&
                                      refuel_info->last_clicked_tank_index == slot &&
                                      refuel_info->last_tank_click_time &&
                                      now - *refuel_info->last_tank_click_time <= std::chrono::milliseconds( 500 );
            const int selected_before = static_cast<int>( std::count( refuel_info->tank_selected.begin(),
                                        refuel_info->tank_selected.end(), true ) );

            if( shift && refuel_info->tank_range_anchor >= 0 ) {
                if( !ctrl ) {
                    std::fill( refuel_info->tank_selected.begin(), refuel_info->tank_selected.end(), false );
                }
                const int first = std::min( refuel_info->tank_range_anchor, slot );
                const int last = std::max( refuel_info->tank_range_anchor, slot );
                for( int i = first; i <= last; ++i ) {
                    const int range_part = refuel_info->tanks[i];
                    if( range_part >= 0 && range_part < veh->part_count() && veh->part( range_part ).can_reload() ) {
                        refuel_info->tank_selected[i] = true;
                    }
                }
            } else if( ctrl ) {
                refuel_info->tank_selected[slot] = !refuel_info->tank_selected[slot];
                refuel_info->tank_range_anchor = slot;
            } else if( !double_click ) {
                // Clicking a different row behaves like ordinary single selection.
                // Clicking an already-selected row in a multi-selection preserves
                // the set so a second click can advance all selected targets.
                if( !refuel_info->tank_selected[slot] || selected_before <= 1 ) {
                    std::fill( refuel_info->tank_selected.begin(), refuel_info->tank_selected.end(), false );
                    refuel_info->tank_selected[slot] = true;
                    refuel_info->tank_range_anchor = slot;
                }
            }

            if( ctrl || shift ) {
                refuel_info->last_clicked_tank_index = -1;
                refuel_info->last_tank_click_time.reset();
            } else if( double_click ) {
                if( !refuel_info->tank_selected[slot] ) {
                    std::fill( refuel_info->tank_selected.begin(), refuel_info->tank_selected.end(), false );
                    refuel_info->tank_selected[slot] = true;
                    refuel_info->tank_range_anchor = slot;
                }
                refuel_info->last_clicked_tank_index = -1;
                refuel_info->last_tank_click_time.reset();
                refuel_info->stage = refuel_stage::source;
                refuel_info->source_pos = 0;
                refuel_info->source_range_anchor = -1;
                refresh_refuel_sources( here );
            } else {
                refuel_info->last_clicked_tank_index = slot;
                refuel_info->last_tank_click_time = now;
            }
            return true;
''',
'restore robust tank double-click advancement')

# Sort target stores by their current/fixed fuel type before applying selection,
# preserving name ordering inside each fuel group. Unknown empty generic tanks go last.
rep(
'''    for( const vpart_reference &ref : veh->get_all_parts() ) {
        const vehicle_part &part = ref.part();
        if( part.removed || !( part.is_tank() || part.is_fuel_store() ) ) {
            continue;
        }
        refuel_info->tanks.push_back( veh->index_of_part( &part ) );
    }

    for( size_t i = 0; i < refuel_info->tanks.size(); ++i ) {
''',
'''    for( const vpart_reference &ref : veh->get_all_parts() ) {
        const vehicle_part &part = ref.part();
        if( part.removed || !( part.is_tank() || part.is_fuel_store() ) ) {
            continue;
        }
        refuel_info->tanks.push_back( veh->index_of_part( &part ) );
    }
    std::stable_sort( refuel_info->tanks.begin(), refuel_info->tanks.end(), [&]( const int lhs,
    const int rhs ) {
        const vehicle_part &left = veh->part( lhs );
        const vehicle_part &right = veh->part( rhs );
        const itype_id left_type = refuel_storage_type( left );
        const itype_id right_type = refuel_storage_type( right );
        if( left_type.is_null() != right_type.is_null() ) {
            return !left_type.is_null();
        }
        if( left_type != right_type ) {
            const std::string left_name = left_type.is_null() ? std::string() : item::nname( left_type );
            const std::string right_name = right_type.is_null() ? std::string() : item::nname( right_type );
            return localized_compare( left_name, right_name );
        }
        return localized_compare( left.name(), right.name() );
    } );

    for( size_t i = 0; i < refuel_info->tanks.size(); ++i ) {
''',
'sort refuel targets by fuel type')

p.write_text(s)
print('refuel target interaction patch applied')
