from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    text = text.replace(old, new, 1)


# Refuel target state: make the tank stage a real multi-select instead of an
# immediate one-tank transition into source selection.
replace_once(
'''    std::vector<int> tanks;\n    int tank_pos = 0;\n    int tank_scroll = 0;\n    int selected_tank_slot = -1;\n''',
'''    std::vector<int> tanks;\n    std::vector<bool> tank_selected;\n    int tank_pos = 0;\n    int tank_scroll = 0;\n    int tank_range_anchor = -1;\n    int last_clicked_tank_index = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_tank_click_time;\n''',
"tank selection state",
)

# Keyboard confirm on the target stage advances using the current multi-selection.
replace_once(
'''                if( refuel_info->stage == refuel_stage::tank ) {\n                    if( !refuel_info->tanks.empty() ) {\n                        refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                                static_cast<int>( refuel_info->tanks.size() ) - 1 );\n                        const int part_index = refuel_info->tanks[refuel_info->tank_pos];\n                        if( part_index >= 0 && part_index < veh->part_count() &&\n                            veh->part( part_index ).can_reload() ) {\n                            refuel_info->selected_tank_slot = refuel_info->tank_pos;\n                            refuel_info->stage = refuel_stage::source;\n                            refuel_info->source_pos = 0;\n                            refuel_info->source_range_anchor = -1;\n                            refresh_refuel_sources( here );\n                        } else {\n                            msg = _( "That fuel store is already full or cannot currently be refilled." );\n                        }\n                    }\n''',
'''                if( refuel_info->stage == refuel_stage::tank ) {\n                    if( !refuel_info->tanks.empty() ) {\n                        refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                                static_cast<int>( refuel_info->tanks.size() ) - 1 );\n                        if( refuel_info->tank_selected.size() != refuel_info->tanks.size() ) {\n                            refuel_info->tank_selected.assign( refuel_info->tanks.size(), false );\n                        }\n                        bool any_selected = std::any_of( refuel_info->tank_selected.begin(),\n                                            refuel_info->tank_selected.end(), []( const bool selected ) {\n                            return selected;\n                        } );\n                        if( !any_selected ) {\n                            const int part_index = refuel_info->tanks[refuel_info->tank_pos];\n                            if( part_index >= 0 && part_index < veh->part_count() &&\n                                veh->part( part_index ).can_reload() ) {\n                                refuel_info->tank_selected[refuel_info->tank_pos] = true;\n                                any_selected = true;\n                            }\n                        }\n                        if( any_selected ) {\n                            refuel_info->stage = refuel_stage::source;\n                            refuel_info->source_pos = 0;\n                            refuel_info->source_range_anchor = -1;\n                            refuel_info->last_clicked_source_index = -1;\n                            refuel_info->last_source_click_time.reset();\n                            refresh_refuel_sources( here );\n                        } else {\n                            msg = _( "Select at least one fuel store that can be refilled." );\n                        }\n                    }\n''',
"keyboard target confirm",
)

# During source selection, show sources usable by at least one selected target.
# Partial compatibility is intentional: the confirmation preview warns before
# executing if some selected targets cannot be fully filled.
replace_once(
'''    Character &player_character = get_player_character();\n    const bool target_one_tank = refuel_info->stage == refuel_info_t::stage_t::source &&\n                                 refuel_info->selected_tank_slot >= 0 &&\n                                 refuel_info->selected_tank_slot < static_cast<int>( refuel_info->tanks.size() );\n\n    const auto add_source = [&]( const item_location &loc ) {\n''',
'''    Character &player_character = get_player_character();\n    const bool target_selected_tanks = refuel_info->stage == refuel_info_t::stage_t::source &&\n                                       refuel_info->tank_selected.size() == refuel_info->tanks.size() &&\n                                       std::any_of( refuel_info->tank_selected.begin(),\n        refuel_info->tank_selected.end(), []( const bool selected ) {\n        return selected;\n    } );\n\n    const auto add_source = [&]( const item_location &loc ) {\n''',
"selected target source header",
)
replace_once(
'''        bool compatible = false;\n        if( target_one_tank ) {\n            const int part_index = refuel_info->tanks[refuel_info->selected_tank_slot];\n            compatible = part_index >= 0 && part_index < veh->part_count() &&\n                         refill_source_compatible( veh->part( part_index ), loc ) &&\n                         refill_part_remaining( veh->part( part_index ), loc ) > 0;\n        } else {\n            for( const int part_index : refuel_info->tanks ) {\n                if( part_index >= 0 && part_index < veh->part_count() &&\n                    refill_source_compatible( veh->part( part_index ), loc ) &&\n                    refill_part_remaining( veh->part( part_index ), loc ) > 0 ) {\n                    compatible = true;\n                    break;\n                }\n            }\n        }\n''',
'''        bool compatible = false;\n        if( target_selected_tanks ) {\n            for( size_t slot = 0; slot < refuel_info->tanks.size(); ++slot ) {\n                if( !refuel_info->tank_selected[slot] ) {\n                    continue;\n                }\n                const int part_index = refuel_info->tanks[slot];\n                if( part_index >= 0 && part_index < veh->part_count() &&\n                    refill_source_compatible( veh->part( part_index ), loc ) &&\n                    refill_part_remaining( veh->part( part_index ), loc ) > 0 ) {\n                    compatible = true;\n                    break;\n                }\n            }\n        } else {\n            for( const int part_index : refuel_info->tanks ) {\n                if( part_index >= 0 && part_index < veh->part_count() &&\n                    refill_source_compatible( veh->part( part_index ), loc ) &&\n                    refill_part_remaining( veh->part( part_index ), loc ) > 0 ) {\n                    compatible = true;\n                    break;\n                }\n            }\n        }\n''',
"selected target source compatibility",
)

# Replace the one-target queue builder with a multi-target sequential planner.
queue_start = text.find("bool veh_interact::queue_selected_refill_source( map &here )")
queue_end = text.find("bool veh_interact::queue_quick_refill_all( map &here )", queue_start)
if queue_start < 0 or queue_end < 0:
    raise SystemExit("queue_selected_refill_source markers not found")
new_queue = r'''bool veh_interact::queue_selected_refill_source( map &here )
{
    if( !refuel_info || refuel_info->stage != refuel_info_t::stage_t::source ||
        refuel_info->tank_selected.size() != refuel_info->tanks.size() ) {
        return false;
    }
    if( refuel_info->sources.empty() ) {
        msg = _( "No compatible fuel source is available within reach." );
        return false;
    }

    std::vector<int> selected_tank_slots;
    for( size_t slot = 0; slot < refuel_info->tanks.size(); ++slot ) {
        if( refuel_info->tank_selected[slot] ) {
            selected_tank_slots.push_back( static_cast<int>( slot ) );
        }
    }
    if( selected_tank_slots.empty() ) {
        msg = _( "Select at least one fuel store to refill." );
        return false;
    }

    std::vector<int> selected_sources;
    for( size_t i = 0; i < refuel_info->sources.size(); ++i ) {
        if( refuel_info->sources[i].selected ) {
            selected_sources.push_back( static_cast<int>( i ) );
        }
    }
    if( selected_sources.empty() ) {
        refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                  static_cast<int>( refuel_info->sources.size() ) - 1 );
        selected_sources.push_back( refuel_info->source_pos );
    }

    const auto payload_of = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };

    std::optional<itype_id> fuel_type;
    const item *fuel_payload = nullptr;
    for( const int source_index : selected_sources ) {
        const item_location &source = refuel_info->sources[source_index].location;
        const item *payload = payload_of( source );
        if( payload == nullptr ) {
            continue;
        }
        if( fuel_type && payload->typeId() != *fuel_type ) {
            msg = _( "Selected containers contain different fuel types and cannot be refueled together." );
            return false;
        }
        if( !fuel_type ) {
            fuel_type = payload->typeId();
            fuel_payload = payload;
        }
    }
    if( !fuel_type || fuel_payload == nullptr ) {
        msg = _( "The selected sources do not contain usable fuel." );
        return false;
    }

    struct source_state_t {
        int remaining = 0;
        bool divisible = false;
    };
    std::vector<source_state_t> source_state( refuel_info->sources.size() );
    for( const int source_index : selected_sources ) {
        const item *payload = payload_of( refuel_info->sources[source_index].location );
        if( payload != nullptr && payload->typeId() == *fuel_type ) {
            source_state[source_index].remaining = refill_source_available(
                    refuel_info->sources[source_index].location );
            source_state[source_index].divisible = payload->count_by_charges();
        }
    }

    struct target_preview_t {
        int part_index = -1;
        int current = 0;
        int capacity = 0;
        int need = 0;
        int planned = 0;
        bool compatible = false;
    };
    std::vector<target_preview_t> previews;
    std::vector<std::pair<int, item_location>> plan;

    // Fill selected vehicle stores in their visible target-list order.  Finish
    // one target before moving to the next and consume selected source containers
    // in source-list order.  This makes the resulting partial fill deterministic.
    for( const int slot : selected_tank_slots ) {
        const int part_index = refuel_info->tanks[slot];
        target_preview_t preview;
        preview.part_index = part_index;
        if( part_index < 0 || part_index >= veh->part_count() ) {
            previews.push_back( preview );
            continue;
        }

        vehicle_part &part = veh->part( part_index );
        preview.compatible = refill_source_compatible( part,
                             refuel_info->sources[selected_sources.front()].location );
        preview.capacity = preview.compatible ? part.item_capacity( *fuel_type ) : 0;
        preview.current = part.ammo_current() == *fuel_type ? part.ammo_remaining() : 0;
        preview.need = preview.compatible ? std::max( 0, preview.capacity - preview.current ) : 0;

        int remaining = preview.need;
        for( const int source_index : selected_sources ) {
            if( remaining <= 0 ) {
                break;
            }
            if( source_state[source_index].remaining <= 0 ) {
                continue;
            }
            const item_location &source = refuel_info->sources[source_index].location;
            if( !refill_source_compatible( part, source ) ) {
                continue;
            }
            const int transfer = std::min( remaining, source_state[source_index].remaining );
            if( transfer <= 0 ) {
                continue;
            }
            plan.emplace_back( part_index, source );
            preview.planned += transfer;
            remaining -= transfer;
            if( source_state[source_index].divisible ) {
                source_state[source_index].remaining -= transfer;
            } else {
                source_state[source_index].remaining = 0;
            }
        }
        previews.push_back( preview );
    }

    if( plan.empty() ) {
        msg = _( "The selected sources cannot refill any selected fuel store." );
        return false;
    }

    const bool partial = std::any_of( previews.begin(), previews.end(), []( const target_preview_t &preview ) {
        return !preview.compatible || preview.planned < preview.need;
    } );
    if( partial ) {
        std::string warning = _( "The selected fuel is not enough to completely fill every selected fuel store.\n\nProjected result:\n" );
        const bool liquid = fuel_payload->made_of( phase_id::LIQUID );
        const auto charge_volume = [&]( const int charges ) {
            item amount( *fuel_payload );
            amount.charges = std::max( 0, charges );
            return amount.volume();
        };

        for( const target_preview_t &preview : previews ) {
            if( preview.part_index < 0 || preview.part_index >= veh->part_count() ) {
                continue;
            }
            const vehicle_part &part = veh->part( preview.part_index );
            if( liquid && part.is_tank() ) {
                units::volume current_volume = 0_ml;
                if( !part.base.empty() && part.base.only_item().made_of( phase_id::LIQUID ) ) {
                    current_volume = part.base.only_item().volume();
                }
                const units::volume added_volume = charge_volume( preview.planned );
                const units::volume projected_volume = current_volume + added_volume;
                warning += string_format( _( "%1$s: %2$.1f -> %3$.1f / %4$.1f L (+%5$.1f L)%6$s\n" ),
                                          part.name(), units::to_liter( current_volume ),
                                          units::to_liter( projected_volume ),
                                          units::to_liter( part.info().size ),
                                          units::to_liter( added_volume ),
                                          preview.compatible ? "" : _( " — incompatible" ) );
            } else {
                const int projected = preview.current + preview.planned;
                warning += string_format( _( "%1$s: %2$d -> %3$d / %4$d (+%5$d)%6$s\n" ),
                                          part.name(), preview.current, projected, preview.capacity,
                                          preview.planned,
                                          preview.compatible ? "" : _( " — incompatible" ) );
            }
        }
        warning += _( "\nContinue with this partial refuel?" );
        if( !query_yn( warning ) ) {
            msg = _( "Partial refuel canceled." );
            return false;
        }
    }

    return queue_refill_plan( plan );
}

'''
text = text[:queue_start] + new_queue + text[queue_end:]

# Target-stage renderer: checkbox selection plus explicit advance button.
display_fn = text.find("void veh_interact::display_refuel_pane( map &here )")
tank_start = text.find("    if( refuel_info->stage == refuel_stage::tank ) {", display_fn)
source_marker = "    } else if( refuel_info->stage == refuel_stage::source ) {"
source_start = text.find(source_marker, tank_start)
if tank_start < 0 or source_start < 0:
    raise SystemExit("target display markers not found")
new_tank_display = r'''    if( refuel_info->stage == refuel_stage::tank ) {
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        _( "Refuel vehicle — select fuel stores" ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range   Double-click = continue" ) );

        if( refuel_info->tank_selected.size() != refuel_info->tanks.size() ) {
            refuel_info->tank_selected.assign( refuel_info->tanks.size(), false );
        }
        const int first_row = 3;
        const int footer_rows = editor_test_mode ? 5 : 4;
        const int visible = std::max( 1, height - first_row - footer_rows );
        if( !refuel_info->tanks.empty() ) {
            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,
                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );
            if( refuel_info->tank_pos < refuel_info->tank_scroll ) {
                refuel_info->tank_scroll = refuel_info->tank_pos;
            } else if( refuel_info->tank_pos >= refuel_info->tank_scroll + visible ) {
                refuel_info->tank_scroll = refuel_info->tank_pos - visible + 1;
            }
            refuel_info->tank_scroll = std::clamp( refuel_info->tank_scroll, 0,
                                       std::max( 0, static_cast<int>( refuel_info->tanks.size() ) - visible ) );
        }
        for( int row = 0; row < visible; ++row ) {
            const int slot = refuel_info->tank_scroll + row;
            if( slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
                break;
            }
            const vehicle_part &part = veh->part( refuel_info->tanks[slot] );
            const bool usable = part.can_reload();
            const bool selected = slot < static_cast<int>( refuel_info->tank_selected.size() ) &&
                                  refuel_info->tank_selected[slot];
            const std::string marker = selected ? "[x]" : "[ ]";
            const std::string fuel = part.ammo_current().is_null() ? _( "empty" ) : item::nname( part.ammo_current() );
            const std::string line = string_format( "%s %s  %s  [%s]", marker, part.name(),
                                     tank_amount( part ), fuel );
            nc_color color = usable ? c_light_gray : c_dark_gray;
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
        const int quick_y = choose_y + 1;
        trim_and_print( w_refuel_overlay, point( 2, quick_y ), width - 4, c_light_cyan,
                        _( "[ Quick fill… ]" ) );
        if( editor_test_mode ) {
            trim_and_print( w_refuel_overlay, point( 2, quick_y + 1 ), width - 4, c_light_red,
                            _( "[ Test: add filled fuel containers to cargo ]" ) );
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Close ]" ) );
'''
text = text[:tank_start] + new_tank_display + text[source_start:]

# Source-stage header no longer assumes exactly one target tank.
source_start = text.find(source_marker, display_fn)
first_row_marker = "        constexpr int first_row = 4;"
first_row_pos = text.find(first_row_marker, source_start)
if source_start < 0 or first_row_pos < 0:
    raise SystemExit("source display header markers not found")
new_source_header = r'''    } else if( refuel_info->stage == refuel_stage::source ) {
        std::vector<int> selected_tank_slots;
        if( refuel_info->tank_selected.size() == refuel_info->tanks.size() ) {
            for( size_t slot = 0; slot < refuel_info->tanks.size(); ++slot ) {
                if( refuel_info->tank_selected[slot] ) {
                    selected_tank_slots.push_back( static_cast<int>( slot ) );
                }
            }
        }
        if( selected_tank_slots.empty() ) {
            refuel_info->stage = refuel_stage::tank;
            wnoutrefresh( w_refuel_overlay );
            return;
        }
        if( selected_tank_slots.size() == 1 ) {
            const vehicle_part &tank = veh->part( refuel_info->tanks[selected_tank_slots.front()] );
            trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                            string_format( _( "Refuel: %s" ), tank.name() ) );
            trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                            string_format( _( "Current: %s" ), tank_amount( tank ) ) );
        } else {
            trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                            string_format( _( "Refuel %d selected fuel stores" ),
                                           static_cast<int>( selected_tank_slots.size() ) ) );
            trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                            _( "Fuel is applied to the selected stores in list order." ) );
        }
        trim_and_print( w_refuel_overlay, point( 2, 2 ), width - 4, c_dark_gray,
                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range" ) );

'''
text = text[:source_start] + new_source_header + text[first_row_pos:]

# Source-stage status: mixed-fuel validation plus selected target count, no singular tank simulation.
status_start = text.find("        int selected_count = 0;", source_start)
status_end_marker = '        const std::string back_label = _( "[ Back ]" );'
status_end = text.find(status_end_marker, status_start)
if status_start < 0 or status_end < 0:
    raise SystemExit("source status markers not found")
new_status = r'''        int selected_count = 0;
        std::optional<itype_id> selected_fuel;
        bool mixed_fuels = false;
        for( const refuel_info_t::source_t &source : refuel_info->sources ) {
            if( !source.selected ) {
                continue;
            }
            ++selected_count;
            const item *payload = payload_of( source.location );
            if( payload == nullptr ) {
                continue;
            }
            if( !selected_fuel ) {
                selected_fuel = payload->typeId();
            } else if( payload->typeId() != *selected_fuel ) {
                mixed_fuels = true;
            }
        }
        const std::string selection_status = mixed_fuels ?
                _( "Selected containers contain different fuel types and cannot be refueled together." ) :
                string_format( _( "Selected: %1$d source(s)   Targets: %2$d fuel store(s)" ),
                               selected_count, static_cast<int>( selected_tank_slots.size() ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4,
                        mixed_fuels ? c_light_red : c_light_gray, selection_status );
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4,
                        mixed_fuels ? c_dark_gray : c_light_green, _( "[ Refuel selected ]" ) );
'''
text = text[:status_start] + new_status + text[status_end:]

# Target-stage mouse behavior: selection first, explicit/double-click advance second.
mouse_fn = text.find("bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )")
tank_mouse_start = text.find("    if( refuel_info->stage == refuel_stage::tank ) {", mouse_fn)
source_mouse_marker = "    if( refuel_info->stage == refuel_stage::source ) {"
tank_mouse_end = text.find(source_mouse_marker, tank_mouse_start)
if tank_mouse_start < 0 or tank_mouse_end < 0:
    raise SystemExit("target mouse markers not found")
new_tank_mouse = r'''    if( refuel_info->stage == refuel_stage::tank ) {
        if( refuel_info->tank_selected.size() != refuel_info->tanks.size() ) {
            refuel_info->tank_selected.assign( refuel_info->tanks.size(), false );
        }
        constexpr int first_row = 3;
        const int footer_rows = editor_test_mode ? 5 : 4;
        const int visible = std::max( 1, height - first_row - footer_rows );
        if( pos->y >= first_row && pos->y < first_row + visible ) {
            const int slot = refuel_info->tank_scroll + pos->y - first_row;
            if( slot < 0 || slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
                return true;
            }
            refuel_info->tank_pos = slot;
            const int part_index = refuel_info->tanks[slot];
            if( part_index < 0 || part_index >= veh->part_count() || !veh->part( part_index ).can_reload() ) {
                msg = _( "That fuel store is already full or cannot currently be refilled." );
                refuel_info->last_clicked_tank_index = -1;
                refuel_info->last_tank_click_time.reset();
                return true;
            }

            const input_event raw = main_context.get_raw_input();
            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;
            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;
            const auto now = std::chrono::steady_clock::now();
            const bool double_click = !ctrl && !shift &&
                                      refuel_info->last_clicked_tank_index == slot &&
                                      refuel_info->last_tank_click_time &&
                                      now - *refuel_info->last_tank_click_time <= std::chrono::milliseconds( 500 );

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

            if( double_click ) {
                refuel_info->last_clicked_tank_index = -1;
                refuel_info->last_tank_click_time.reset();
                refuel_info->stage = refuel_stage::source;
                refuel_info->source_pos = 0;
                refuel_info->source_range_anchor = -1;
                refresh_refuel_sources( here );
            } else if( !ctrl && !shift ) {
                refuel_info->last_clicked_tank_index = slot;
                refuel_info->last_tank_click_time = now;
            } else {
                refuel_info->last_clicked_tank_index = -1;
                refuel_info->last_tank_click_time.reset();
            }
            return true;
        }

        const int choose_y = height - ( editor_test_mode ? 5 : 4 );
        if( pos->y == choose_y ) {
            const bool any_selected = std::any_of( refuel_info->tank_selected.begin(),
                                      refuel_info->tank_selected.end(), []( const bool selected ) {
                return selected;
            } );
            if( any_selected ) {
                refuel_info->stage = refuel_stage::source;
                refuel_info->source_pos = 0;
                refuel_info->source_range_anchor = -1;
                refresh_refuel_sources( here );
            } else {
                msg = _( "Select at least one fuel store that can be refilled." );
            }
            return true;
        }
        const int quick_y = choose_y + 1;
        if( pos->y == quick_y ) {
            refuel_info->stage = refuel_stage::quick_fuel;
            refuel_info->quick_fuel_pos = 0;
            refresh_quick_refuel_fuels( here );
            return true;
        }
        if( editor_test_mode && pos->y == quick_y + 1 ) {
            add_test_refuel_containers( here );
            return true;
        }
        if( pos->y == height - 2 ) {
            close_refuel_mode();
            return true;
        }
        return true;
    }

'''
text = text[:tank_mouse_start] + new_tank_mouse + text[tank_mouse_end:]

# Initialize checkbox selection on the current/default target when the modal opens.
replace_once(
'''    refresh_refuel_sources( here );\n    msg.reset();\n}\n\nvoid veh_interact::calc_overview( map &here )\n''',
'''    refuel_info->tank_selected.assign( refuel_info->tanks.size(), false );\n    if( refuel_info->tank_pos >= 0 && refuel_info->tank_pos < static_cast<int>( refuel_info->tanks.size() ) &&\n        veh->part( refuel_info->tanks[refuel_info->tank_pos] ).can_reload() ) {\n        refuel_info->tank_selected[refuel_info->tank_pos] = true;\n        refuel_info->tank_range_anchor = refuel_info->tank_pos;\n    }\n    refresh_refuel_sources( here );\n    msg.reset();\n}\n\nvoid veh_interact::calc_overview( map &here )\n''',
"initialize target selection",
)

# Back from source selection returns to the selected-target screen without losing targets.
# Reset only source gesture state so the next source selection starts cleanly.
replace_once(
'''                refuel_info->stage = refuel_stage::tank;\n                refuel_info->source_range_anchor = -1;\n                refresh_refuel_sources( here );\n''',
'''                refuel_info->stage = refuel_stage::tank;\n                refuel_info->source_range_anchor = -1;\n                refuel_info->last_clicked_source_index = -1;\n                refuel_info->last_source_click_time.reset();\n                refresh_refuel_sources( here );\n''',
"source Back state",
)

path.write_text(text)
print("refuel target multi-select patch applied")
