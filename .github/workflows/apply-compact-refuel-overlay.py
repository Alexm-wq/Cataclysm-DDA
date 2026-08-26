from pathlib import Path
import re

CPP = Path('src/veh_interact.cpp')
HDR = Path('src/veh_interact.h')
STATUS = Path('doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, got {count}')
    return text.replace(old, new, 1)


def sub_once(text, pattern, repl, label):
    out, count = re.subn(pattern, repl, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f'{label}: expected one regex match, got {count}')
    return out

# Header ---------------------------------------------------------------------
h = HDR.read_text()
h = replace_once(
    h,
    '''        catacurses::window w_refuel_tanks;\n        catacurses::window w_refuel_sources;\n        catacurses::window w_refuel_details;\n''',
    '''        catacurses::window w_refuel_overlay;\n''',
    'refuel window declaration'
)
h = replace_once(
    h,
    '''        void refresh_refuel_sources( map &here );\n        bool refill_source_compatible( const vehicle_part &part, const item_location &source ) const;\n        int refill_source_available( const item_location &source ) const;\n        int refill_part_remaining( const vehicle_part &part, const item_location &source ) const;\n        bool queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan );\n        bool queue_selected_refill_source( map &here );\n        bool queue_quick_refill_all( map &here );\n        void close_refuel_mode();\n        bool handle_refuel_mouse( map &here, const std::string &action );\n        void display_refuel_pane( map &here );\n''',
    '''        void refresh_refuel_sources( map &here );\n        void refresh_quick_refuel_fuels( map &here );\n        bool refill_source_compatible( const vehicle_part &part, const item_location &source ) const;\n        int refill_source_available( const item_location &source ) const;\n        int refill_part_remaining( const vehicle_part &part, const item_location &source ) const;\n        bool queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan );\n        bool queue_selected_refill_source( map &here );\n        bool queue_quick_refill_all( map &here );\n        bool add_test_refuel_containers( map &here );\n        void close_refuel_mode();\n        bool handle_refuel_mouse( map &here, const std::string &action );\n        void display_refuel_pane( map &here );\n''',
    'refuel method declarations'
)
HDR.write_text(h)

# Core -----------------------------------------------------------------------
c = CPP.read_text()

c = replace_once(
    c,
    '''    const int refuel_tank_w = std::max( 22, grid_w * 30 / 100 );\n    const int refuel_source_w = std::max( 26, grid_w * 38 / 100 );\n    const int refuel_detail_w = std::max( 1, grid_w - refuel_tank_w - refuel_source_w );\n    w_refuel_tanks = catacurses::newwin( page_size, refuel_tank_w,\n                                         point( grid.x, pane_y ) );\n    w_refuel_sources = catacurses::newwin( page_size, refuel_source_w,\n                                           point( grid.x + refuel_tank_w, pane_y ) );\n    w_refuel_details = catacurses::newwin( page_size, refuel_detail_w,\n                                           point( grid.x + refuel_tank_w + refuel_source_w, pane_y ) );\n''',
    '''    // Refueling is a short transactional workflow, not a replacement editor.\n    // Keep it as a compact centered modal over the normal vehicle editor.\n    const int refuel_overlay_w = std::min( grid_w, std::clamp( grid_w * 55 / 100, 36, 64 ) );\n    const int refuel_overlay_h = std::min( page_size, std::clamp( page_size - 2, 12, 20 ) );\n    w_refuel_overlay = catacurses::newwin( refuel_overlay_h, refuel_overlay_w,\n                       point( grid.x + std::max( 0, ( grid_w - refuel_overlay_w ) / 2 ),\n                              pane_y + std::max( 0, ( page_size - refuel_overlay_h ) / 2 ) ) );\n''',
    'allocate compact refuel overlay'
)

c = sub_once(
    c,
    r'''struct veh_interact::refuel_info_t \{.*?\n\};\n\nshared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor''',
    '''struct veh_interact::refuel_info_t {\n    enum class stage_t {\n        tank,\n        source,\n        quick_fuel\n    };\n\n    struct source_t {\n        item_location location;\n        std::string label;\n        bool selected = false;\n    };\n\n    stage_t stage = stage_t::tank;\n    std::vector<int> tanks;\n    int tank_pos = 0;\n    int tank_scroll = 0;\n    int selected_tank_slot = -1;\n\n    std::vector<source_t> sources;\n    int source_pos = 0;\n    int source_scroll = 0;\n    int source_range_anchor = -1;\n    item_location last_clicked_source;\n    std::optional<std::chrono::steady_clock::time_point> last_source_click_time;\n\n    std::vector<itype_id> quick_fuels;\n    int quick_fuel_pos = 0;\n    int quick_fuel_scroll = 0;\n};\n\nshared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor''',
    'refuel state structure'
)

c = replace_once(
    c,
    '''            display_grid();\n            display_name();\n            display_stats( here );\n            if( refuel_info ) {\n                display_refuel_pane( here );\n                display_mode( here );\n#if defined(TILES)\n                clear_map_preview_window();\n#endif\n                return;\n            }\n            display_veh( here );\n''',
    '''            display_grid();\n            display_name();\n            display_stats( here );\n            display_veh( here );\n            if( refuel_info ) {\n                // Preserve the normal editor as visual context behind the compact modal.\n                display_part_inspector();\n                display_part_details();\n                display_refuel_pane( here );\n                display_mode( here );\n#if defined(TILES)\n                // SDL map previews draw outside curses ordering; suppress them while\n                // the modal is open so they cannot cover the overlay.\n                clear_map_preview_window();\n#endif\n                return;\n            }\n''',
    'refuel redraw layering'
)

c = sub_once(
    c,
    r'''        if\( refuel_info \) \{.*?            // Persistent refuel mode consumes unrelated editor/navigation input\n            // rather than letting it move the vehicle mount behind the pane\.\n            continue;\n        \} else if\( install_info \) \{''',
    '''        if( refuel_info ) {\n            using refuel_stage = refuel_info_t::stage_t;\n            if( action == "QUIT" ) {\n                if( refuel_info->stage == refuel_stage::tank ) {\n                    close_refuel_mode();\n                } else {\n                    refuel_info->stage = refuel_stage::tank;\n                    refuel_info->source_range_anchor = -1;\n                    msg.reset();\n                    refresh_refuel_sources( here );\n                }\n                continue;\n            }\n\n            if( action == "UP" || action == "DOWN" ||\n                action == "PAGE_UP" || action == "PAGE_DOWN" ) {\n                const int page = std::max( 1, getmaxy( w_refuel_overlay ) - 8 );\n                const int delta = action == "UP" ? -1 : action == "DOWN" ? 1 :\n                                  action == "PAGE_UP" ? -page : page;\n                if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {\n                    refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,\n                                            static_cast<int>( refuel_info->tanks.size() ) - 1 );\n                } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {\n                    refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,\n                                              static_cast<int>( refuel_info->sources.size() ) - 1 );\n                } else if( refuel_info->stage == refuel_stage::quick_fuel &&\n                           !refuel_info->quick_fuels.empty() ) {\n                    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,\n                                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n                }\n                continue;\n            }\n\n            if( action == "REFILL" || action == "CONFIRM" ) {\n                if( refuel_info->stage == refuel_stage::tank ) {\n                    if( !refuel_info->tanks.empty() ) {\n                        refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                                static_cast<int>( refuel_info->tanks.size() ) - 1 );\n                        const int part_index = refuel_info->tanks[refuel_info->tank_pos];\n                        if( part_index >= 0 && part_index < veh->part_count() &&\n                            veh->part( part_index ).can_reload() ) {\n                            refuel_info->selected_tank_slot = refuel_info->tank_pos;\n                            refuel_info->stage = refuel_stage::source;\n                            refuel_info->source_pos = 0;\n                            refuel_info->source_range_anchor = -1;\n                            refresh_refuel_sources( here );\n                        } else {\n                            msg = _( "That fuel store is already full or cannot currently be refilled." );\n                        }\n                    }\n                } else if( refuel_info->stage == refuel_stage::source ) {\n                    bool any_selected = std::any_of( refuel_info->sources.begin(), refuel_info->sources.end(),\n                    []( const refuel_info_t::source_t &entry ) {\n                        return entry.selected;\n                    } );\n                    if( !any_selected && !refuel_info->sources.empty() ) {\n                        refuel_info->sources[refuel_info->source_pos].selected = true;\n                    }\n                    if( queue_selected_refill_source( here ) ) {\n                        finish = true;\n                    }\n                } else if( queue_quick_refill_all( here ) ) {\n                    finish = true;\n                }\n                continue;\n            }\n\n            // Refuel modal consumes unrelated editor/navigation input rather than\n            // moving the vehicle mount behind it.\n            continue;\n        } else if( install_info ) {''',
    'refuel main-loop state machine'
)

REFUEL_BLOCK = r'''void veh_interact::close_refuel_mode\(\).*?\nvoid veh_interact::calc_overview'''
NEW_REFUEL = r'''void veh_interact::close_refuel_mode()
{
    refuel_info.reset();
    msg.reset();
}

bool veh_interact::refill_source_compatible( const vehicle_part &part,
        const item_location &source ) const
{
    if( !source ) {
        return false;
    }

    const item &obj = *source;
    if( part.is_tank() ) {
        if( obj.is_watertight_container() && obj.num_item_stacks() == 1 && !obj.empty() ) {
            return part.can_reload( obj.only_item() );
        }
        if( obj.made_of( phase_id::LIQUID ) && !source.has_parent() ) {
            return part.can_reload( obj );
        }
        return false;
    }

    if( part.is_fuel_store() ) {
        return part.can_reload( obj ) || part.get_base().can_reload_with( obj, true );
    }
    return false;
}

int veh_interact::refill_source_available( const item_location &source ) const
{
    if( !source ) {
        return 0;
    }
    const item *payload = source.get_item();
    if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
        payload = &source->only_item();
    }
    if( payload == nullptr ) {
        return 0;
    }
    return payload->count_by_charges() ? std::max( 0, payload->charges ) : 1;
}

int veh_interact::refill_part_remaining( const vehicle_part &part,
        const item_location &source ) const
{
    if( !source ) {
        return 0;
    }
    const item *payload = source.get_item();
    if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
        payload = &source->only_item();
    }
    if( payload == nullptr ) {
        return 0;
    }

    const int capacity = part.item_capacity( payload->typeId() );
    if( capacity <= 0 ) {
        return 0;
    }
    const int current = part.ammo_current() == payload->typeId() ? part.ammo_remaining() : 0;
    return std::max( 0, capacity - current );
}

void veh_interact::refresh_refuel_sources( map &here )
{
    if( !refuel_info ) {
        return;
    }

    std::vector<item_location> previously_selected;
    item_location previous_cursor;
    for( size_t i = 0; i < refuel_info->sources.size(); ++i ) {
        if( refuel_info->sources[i].selected ) {
            previously_selected.push_back( refuel_info->sources[i].location );
        }
        if( static_cast<int>( i ) == refuel_info->source_pos ) {
            previous_cursor = refuel_info->sources[i].location;
        }
    }
    refuel_info->sources.clear();

    Character &player_character = get_player_character();
    const bool target_one_tank = refuel_info->stage == refuel_info_t::stage_t::source &&
                                 refuel_info->selected_tank_slot >= 0 &&
                                 refuel_info->selected_tank_slot < static_cast<int>( refuel_info->tanks.size() );

    const auto add_source = [&]( const item_location &loc ) {
        if( !loc ) {
            return;
        }
        if( loc->made_of( phase_id::LIQUID ) && loc.has_parent() ) {
            return;
        }

        bool compatible = false;
        if( target_one_tank ) {
            const int part_index = refuel_info->tanks[refuel_info->selected_tank_slot];
            compatible = part_index >= 0 && part_index < veh->part_count() &&
                         refill_source_compatible( veh->part( part_index ), loc ) &&
                         refill_part_remaining( veh->part( part_index ), loc ) > 0;
        } else {
            for( const int part_index : refuel_info->tanks ) {
                if( part_index >= 0 && part_index < veh->part_count() &&
                    refill_source_compatible( veh->part( part_index ), loc ) &&
                    refill_part_remaining( veh->part( part_index ), loc ) > 0 ) {
                    compatible = true;
                    break;
                }
            }
        }
        if( !compatible ) {
            return;
        }
        if( std::any_of( refuel_info->sources.begin(), refuel_info->sources.end(),
        [&]( const refuel_info_t::source_t &entry ) {
            return entry.location == loc;
        } ) ) {
            return;
        }
        refuel_info_t::source_t entry;
        entry.location = loc;
        entry.label = string_format( "%s — %s", loc->display_name(), loc.describe( &player_character ) );
        entry.selected = std::any_of( previously_selected.begin(), previously_selected.end(),
        [&]( const item_location &old ) {
            return old == loc;
        } );
        refuel_info->sources.emplace_back( std::move( entry ) );
    };

    for( const item_location &loc : player_character.all_items_loc() ) {
        add_source( loc );
    }

    map_selector nearby_map( player_character.pos_bub(), 1, true );
    for( const map_cursor &cursor : nearby_map ) {
        for( item &it : here.i_at( cursor.pos_bub( here ) ) ) {
            add_source( item_location( cursor, &it ) );
        }
    }

    vehicle_selector nearby_vehicles( here, player_character.pos_bub(), 1, true );
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

    std::stable_sort( refuel_info->sources.begin(), refuel_info->sources.end(),
    []( const refuel_info_t::source_t &lhs, const refuel_info_t::source_t &rhs ) {
        return localized_compare( lhs.label, rhs.label );
    } );

    refuel_info->source_pos = 0;
    if( previous_cursor ) {
        const auto found = std::find_if( refuel_info->sources.begin(), refuel_info->sources.end(),
        [&]( const refuel_info_t::source_t &entry ) {
            return entry.location == previous_cursor;
        } );
        if( found != refuel_info->sources.end() ) {
            refuel_info->source_pos = static_cast<int>( std::distance( refuel_info->sources.begin(), found ) );
        }
    }
    if( refuel_info->sources.empty() ) {
        refuel_info->source_pos = 0;
        refuel_info->source_scroll = 0;
        refuel_info->source_range_anchor = -1;
    } else {
        refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                  static_cast<int>( refuel_info->sources.size() ) - 1 );
        refuel_info->source_range_anchor = std::clamp( refuel_info->source_range_anchor, -1,
                                           static_cast<int>( refuel_info->sources.size() ) - 1 );
    }
}

void veh_interact::refresh_quick_refuel_fuels( map &here )
{
    if( !refuel_info ) {
        return;
    }
    refresh_refuel_sources( here );

    std::set<itype_id> propulsion_fuels;
    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        const vehicle_part &part = vpr.part();
        if( !part.is_engine() || !part.is_available() || !part.info().engine_info ) {
            continue;
        }
        for( const itype_id &fuel : part.info().engine_info->fuel_opts ) {
            if( !fuel.is_null() ) {
                propulsion_fuels.insert( fuel );
            }
        }
        if( !part.fuel_current().is_null() ) {
            propulsion_fuels.insert( part.fuel_current() );
        }
    }

    refuel_info->quick_fuels.clear();
    for( const refuel_info_t::source_t &source : refuel_info->sources ) {
        if( !source.location ) {
            continue;
        }
        const item *payload = source.location.get_item();
        if( source.location->is_watertight_container() &&
            source.location->num_item_stacks() == 1 && !source.location->empty() ) {
            payload = &source.location->only_item();
        }
        if( payload == nullptr || propulsion_fuels.count( payload->typeId() ) == 0 ||
            refill_source_available( source.location ) <= 0 ) {
            continue;
        }

        bool has_target_store = false;
        for( const int part_index : refuel_info->tanks ) {
            if( part_index >= 0 && part_index < veh->part_count() &&
                refill_source_compatible( veh->part( part_index ), source.location ) &&
                refill_part_remaining( veh->part( part_index ), source.location ) > 0 ) {
                has_target_store = true;
                break;
            }
        }
        if( !has_target_store ) {
            continue;
        }
        if( std::find( refuel_info->quick_fuels.begin(), refuel_info->quick_fuels.end(),
                      payload->typeId() ) == refuel_info->quick_fuels.end() ) {
            refuel_info->quick_fuels.push_back( payload->typeId() );
        }
    }

    std::stable_sort( refuel_info->quick_fuels.begin(), refuel_info->quick_fuels.end(),
    []( const itype_id &lhs, const itype_id &rhs ) {
        return localized_compare( item::nname( lhs ), item::nname( rhs ) );
    } );
    if( refuel_info->quick_fuels.empty() ) {
        refuel_info->quick_fuel_pos = 0;
        refuel_info->quick_fuel_scroll = 0;
    } else {
        refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,
                                      static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
    }
}

bool veh_interact::queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan )
{
    if( plan.empty() ) {
        return false;
    }

    refill_part_indices.clear();
    refill_targets.clear();
    for( const std::pair<int, item_location> &transfer : plan ) {
        if( transfer.first < 0 || transfer.first >= veh->part_count() || !transfer.second ) {
            continue;
        }
        refill_part_indices.push_back( transfer.first );
        refill_targets.push_back( transfer.second );
    }
    if( refill_part_indices.empty() ) {
        return false;
    }

    sel_vehicle_part = &veh->part( refill_part_indices.front() );
    sel_vpart_info = &sel_vehicle_part->info();
    sel_cmd = 'f';
    close_refuel_mode();
    return true;
}

bool veh_interact::queue_selected_refill_source( map &here )
{
    if( !refuel_info || refuel_info->stage != refuel_info_t::stage_t::source ||
        refuel_info->selected_tank_slot < 0 ||
        refuel_info->selected_tank_slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
        return false;
    }
    if( refuel_info->sources.empty() ) {
        msg = _( "No compatible fuel source is available within reach." );
        return false;
    }

    const int part_index = refuel_info->tanks[refuel_info->selected_tank_slot];
    vehicle_part &part = veh->part( part_index );
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
    int remaining = -1;
    std::vector<std::pair<int, item_location>> plan;
    for( const int source_index : selected_sources ) {
        const item_location source = refuel_info->sources[source_index].location;
        const item *payload = payload_of( source );
        if( payload == nullptr || !refill_source_compatible( part, source ) ) {
            continue;
        }
        if( fuel_type && payload->typeId() != *fuel_type ) {
            msg = _( "Selected sources must contain the same fuel type." );
            return false;
        }
        if( !fuel_type ) {
            fuel_type = payload->typeId();
            remaining = refill_part_remaining( part, source );
        }
        if( remaining <= 0 ) {
            break;
        }
        const int available = refill_source_available( source );
        if( available <= 0 ) {
            continue;
        }
        plan.emplace_back( part_index, source );
        remaining -= std::min( remaining, available );
    }

    if( plan.empty() ) {
        msg = _( "The selected sources cannot refill this fuel store." );
        refresh_refuel_sources( here );
        return false;
    }
    return queue_refill_plan( plan );
}

bool veh_interact::queue_quick_refill_all( map &here )
{
    if( !refuel_info || refuel_info->stage != refuel_info_t::stage_t::quick_fuel ) {
        return false;
    }
    refresh_quick_refuel_fuels( here );
    if( refuel_info->quick_fuels.empty() ) {
        msg = _( "No available fuel can currently power an installed, working engine." );
        return false;
    }
    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,
                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
    const itype_id selected_fuel = refuel_info->quick_fuels[refuel_info->quick_fuel_pos];

    const auto payload_of = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };

    struct source_state_t {
        int remaining = 0;
        bool divisible = false;
    };
    std::vector<source_state_t> source_state( refuel_info->sources.size() );
    for( size_t i = 0; i < refuel_info->sources.size(); ++i ) {
        const item *payload = payload_of( refuel_info->sources[i].location );
        if( payload != nullptr && payload->typeId() == selected_fuel ) {
            source_state[i].remaining = refill_source_available( refuel_info->sources[i].location );
            source_state[i].divisible = payload->count_by_charges();
        }
    }

    struct target_t {
        int part_index = -1;
        int need = 0;
    };
    std::vector<target_t> targets;
    for( const int part_index : refuel_info->tanks ) {
        if( part_index < 0 || part_index >= veh->part_count() ) {
            continue;
        }
        int best_need = 0;
        for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
            if( source_state[s].remaining <= 0 ) {
                continue;
            }
            const item_location &source = refuel_info->sources[s].location;
            if( refill_source_compatible( veh->part( part_index ), source ) ) {
                best_need = std::max( best_need, refill_part_remaining( veh->part( part_index ), source ) );
            }
        }
        if( best_need > 0 ) {
            targets.push_back( { part_index, best_need } );
        }
    }
    std::stable_sort( targets.begin(), targets.end(), []( const target_t &lhs, const target_t &rhs ) {
        return lhs.need > rhs.need;
    } );

    std::vector<std::pair<int, item_location>> plan;
    for( const target_t &target : targets ) {
        int tank_remaining = target.need;
        while( tank_remaining > 0 ) {
            int best_source = -1;
            int best_transfer = 0;
            bool best_finishes = false;
            int best_surplus = INT_MAX;

            for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
                if( source_state[s].remaining <= 0 ) {
                    continue;
                }
                const item_location &source = refuel_info->sources[s].location;
                const item *payload = payload_of( source );
                if( payload == nullptr || payload->typeId() != selected_fuel ||
                    !refill_source_compatible( veh->part( target.part_index ), source ) ) {
                    continue;
                }
                const int transfer = std::min( tank_remaining, source_state[s].remaining );
                const bool finishes = transfer >= tank_remaining;
                const int surplus = finishes ? source_state[s].remaining - tank_remaining : INT_MAX;
                if( best_source < 0 || ( finishes && !best_finishes ) ||
                    ( finishes == best_finishes && finishes && surplus < best_surplus ) ||
                    ( !finishes && !best_finishes && transfer > best_transfer ) ) {
                    best_source = static_cast<int>( s );
                    best_transfer = transfer;
                    best_finishes = finishes;
                    best_surplus = surplus;
                }
            }

            if( best_source < 0 || best_transfer <= 0 ) {
                break;
            }
            plan.emplace_back( target.part_index, refuel_info->sources[best_source].location );
            tank_remaining -= best_transfer;
            source_state[best_source].remaining -= best_transfer;
            if( !source_state[best_source].divisible ) {
                source_state[best_source].remaining = 0;
            }
        }
    }

    if( plan.empty() ) {
        msg = string_format( _( "No connected vehicle fuel stores can be filled with %s." ),
                             item::nname( selected_fuel ) );
        return false;
    }
    // queue_refill_plan preserves the canonical one-action-turn-per-transfer cost.
    return queue_refill_plan( plan );
}

bool veh_interact::add_test_refuel_containers( map &here )
{
    if( !editor_test_mode ) {
        return false;
    }

    std::vector<int> cargo_parts;
    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        const vehicle_part &part = vpr.part();
        if( part.is_available() && part.info().has_flag( VPFLAG_CARGO ) ) {
            cargo_parts.push_back( veh->index_of_part( &part ) );
        }
    }
    if( cargo_parts.empty() ) {
        msg = _( "Test fuel requires at least one valid cargo/trunk part on this vehicle." );
        return false;
    }

    std::set<itype_id> propulsion_liquids;
    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        const vehicle_part &part = vpr.part();
        if( !part.is_engine() || !part.is_available() || !part.info().engine_info ) {
            continue;
        }
        for( const itype_id &fuel : part.info().engine_info->fuel_opts ) {
            if( !fuel.is_null() && item::find_type( fuel )->phase == phase_id::LIQUID ) {
                propulsion_liquids.insert( fuel );
            }
        }
    }

    const itype_id gasoline( "gasoline" );
    itype_id fuel = gasoline;
    if( propulsion_liquids.count( gasoline ) == 0 && !propulsion_liquids.empty() ) {
        fuel = *propulsion_liquids.begin();
    }

    const std::array<itype_id, 4> container_types = { {
            itype_id( "bottle_plastic" ), itype_id( "bottle_glass" ),
            itype_id( "canteen" ), itype_id( "jerrycan" )
        } };

    int added = 0;
    for( const itype_id &container_type : container_types ) {
        item container( container_type, calendar::turn );
        item liquid( fuel, calendar::turn );
        const int capacity = container.get_remaining_capacity_for_liquid( liquid );
        if( capacity <= 0 ) {
            continue;
        }
        liquid.charges = capacity;
        if( container.fill_with( liquid, capacity, true, true, true ) <= 0 ) {
            continue;
        }

        for( const int cargo_index : cargo_parts ) {
            if( veh->add_item( here, veh->part( cargo_index ), container ) ) {
                ++added;
                break;
            }
        }
    }

    if( added <= 0 ) {
        msg = _( "No test fuel containers fit in this vehicle's cargo storage." );
        return false;
    }

    veh->invalidate_mass();
    refresh_refuel_sources( here );
    refresh_quick_refuel_fuels( here );
    msg = string_format( _( "Added %1$d filled %2$s test containers directly to vehicle cargo." ),
                         added, item::nname( fuel ) );
    return true;
}

void veh_interact::display_refuel_pane( map &here )
{
    if( !refuel_info || !w_refuel_overlay ) {
        return;
    }

    werase( w_refuel_overlay );
    draw_border( w_refuel_overlay, c_light_gray );
    const int width = getmaxx( w_refuel_overlay );
    const int height = getmaxy( w_refuel_overlay );
    if( width < 4 || height < 4 ) {
        wnoutrefresh( w_refuel_overlay );
        return;
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
    const auto source_amount = [&]( const item_location &source ) {
        const item *payload = payload_of( source );
        if( payload == nullptr ) {
            return std::string();
        }
        if( payload->made_of( phase_id::LIQUID ) ) {
            return string_format( "%.1f L", units::to_liter( payload->volume() ) );
        }
        return string_format( _( "%d charges" ), refill_source_available( source ) );
    };
    const auto tank_amount = []( const vehicle_part &part ) {
        if( part.is_tank() ) {
            units::volume current = 0_ml;
            if( !part.base.empty() && part.base.only_item().made_of( phase_id::LIQUID ) ) {
                current = part.base.only_item().volume();
            }
            return string_format( "%.1f / %.1f L", units::to_liter( current ),
                                  units::to_liter( part.info().size ) );
        }
        if( !part.ammo_current().is_null() ) {
            return string_format( "%d / %d", part.ammo_remaining(),
                                  part.item_capacity( part.ammo_current() ) );
        }
        return std::string( "0" );
    };

    using refuel_stage = refuel_info_t::stage_t;
    if( refuel_info->stage == refuel_stage::tank ) {
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        _( "Refuel vehicle" ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        _( "Select a fuel store. Quick fill chooses propulsion fuel separately." ) );

        const int first_row = 3;
        const int button_rows = editor_test_mode ? 4 : 3;
        const int visible = std::max( 1, height - first_row - button_rows );
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
            std::string fuel = part.ammo_current().is_null() ? _( "empty" ) : item::nname( part.ammo_current() );
            const std::string line = string_format( "%s  %s  [%s]", part.name(), tank_amount( part ), fuel );
            nc_color color = usable ? c_light_gray : c_dark_gray;
            if( slot == refuel_info->tank_pos ) {
                color = hilite( color );
            }
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );
        }

        const int quick_y = height - ( editor_test_mode ? 4 : 3 );
        trim_and_print( w_refuel_overlay, point( 2, quick_y ), width - 4, c_light_cyan,
                        _( "[ Quick fill… ]" ) );
        if( editor_test_mode ) {
            trim_and_print( w_refuel_overlay, point( 2, quick_y + 1 ), width - 4, c_light_red,
                            _( "[ Test: add filled fuel containers to cargo ]" ) );
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Close ]" ) );
    } else if( refuel_info->stage == refuel_stage::source ) {
        if( refuel_info->selected_tank_slot < 0 ||
            refuel_info->selected_tank_slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
            refuel_info->stage = refuel_stage::tank;
            wnoutrefresh( w_refuel_overlay );
            return;
        }
        const vehicle_part &tank = veh->part( refuel_info->tanks[refuel_info->selected_tank_slot] );
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        string_format( _( "Refuel: %s" ), tank.name() ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        string_format( _( "Current: %s" ), tank_amount( tank ) ) );
        trim_and_print( w_refuel_overlay, point( 2, 2 ), width - 4, c_dark_gray,
                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range" ) );

        constexpr int first_row = 4;
        const int visible = std::max( 1, height - first_row - 5 );
        if( !refuel_info->sources.empty() ) {
            refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                      static_cast<int>( refuel_info->sources.size() ) - 1 );
            if( refuel_info->source_pos < refuel_info->source_scroll ) {
                refuel_info->source_scroll = refuel_info->source_pos;
            } else if( refuel_info->source_pos >= refuel_info->source_scroll + visible ) {
                refuel_info->source_scroll = refuel_info->source_pos - visible + 1;
            }
            refuel_info->source_scroll = std::clamp( refuel_info->source_scroll, 0,
                                         std::max( 0, static_cast<int>( refuel_info->sources.size() ) - visible ) );
        }
        for( int row = 0; row < visible; ++row ) {
            const int index = refuel_info->source_scroll + row;
            if( index >= static_cast<int>( refuel_info->sources.size() ) ) {
                break;
            }
            const refuel_info_t::source_t &source = refuel_info->sources[index];
            const std::string marker = source.selected ? "[x]" : "[ ]";
            const std::string line = string_format( "%s %s  %s", marker,
                                     source_amount( source.location ), source.label );
            nc_color color = source.selected ? c_light_cyan : c_light_gray;
            if( index == refuel_info->source_pos ) {
                color = hilite( color );
            }
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );
        }
        if( refuel_info->sources.empty() ) {
            trim_and_print( w_refuel_overlay, point( 2, first_row ), width - 4, c_dark_gray,
                            _( "No compatible carried, adjacent, cargo, or map fuel source is in reach." ) );
        }

        int selected_count = 0;
        int effective_actions = 0;
        int simulated_remaining = -1;
        std::optional<itype_id> selected_fuel;
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
                simulated_remaining = refill_part_remaining( tank, source.location );
            }
            if( payload->typeId() != *selected_fuel || simulated_remaining <= 0 ) {
                continue;
            }
            const int available = refill_source_available( source.location );
            if( available > 0 ) {
                ++effective_actions;
                simulated_remaining -= std::min( simulated_remaining, available );
            }
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4, c_light_gray,
                        string_format( _( "Selected: %1$d source(s)   Cost: %2$d refill action(s)" ),
                                       selected_count, effective_actions ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4, c_light_green,
                        _( "[ Refuel selected ]" ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Back ]    [ Cancel ]" ) );
    } else {
        refresh_quick_refuel_fuels( here );
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        _( "Quick fill — propulsion fuel" ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        _( "Only fuel usable by an installed working engine and available now is listed." ) );

        constexpr int first_row = 3;
        const int visible = std::max( 1, height - first_row - 4 );
        if( !refuel_info->quick_fuels.empty() ) {
            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,
                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
            if( refuel_info->quick_fuel_pos < refuel_info->quick_fuel_scroll ) {
                refuel_info->quick_fuel_scroll = refuel_info->quick_fuel_pos;
            } else if( refuel_info->quick_fuel_pos >= refuel_info->quick_fuel_scroll + visible ) {
                refuel_info->quick_fuel_scroll = refuel_info->quick_fuel_pos - visible + 1;
            }
        }
        for( int row = 0; row < visible; ++row ) {
            const int index = refuel_info->quick_fuel_scroll + row;
            if( index >= static_cast<int>( refuel_info->quick_fuels.size() ) ) {
                break;
            }
            const itype_id fuel = refuel_info->quick_fuels[index];
            double liters = 0.0;
            int charges = 0;
            bool liquid = item::find_type( fuel )->phase == phase_id::LIQUID;
            for( const refuel_info_t::source_t &source : refuel_info->sources ) {
                const item *payload = payload_of( source.location );
                if( payload == nullptr || payload->typeId() != fuel ) {
                    continue;
                }
                if( liquid ) {
                    liters += units::to_liter( payload->volume() );
                } else {
                    charges += refill_source_available( source.location );
                }
            }
            const std::string amount = liquid ? string_format( "%.1f L", liters ) :
                                       string_format( _( "%d charges" ), charges );
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4,
                            index == refuel_info->quick_fuel_pos ? h_light_cyan : c_light_gray,
                            string_format( "%s  —  %s available", item::nname( fuel ), amount ) );
        }
        if( refuel_info->quick_fuels.empty() ) {
            trim_and_print( w_refuel_overlay, point( 2, first_row ), width - 4, c_dark_gray,
                            _( "No currently available source matches a working propulsion engine." ) );
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4,
                        refuel_info->quick_fuels.empty() ? c_dark_gray : c_light_green,
                        _( "[ Quick fill selected fuel ]" ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Back ]    [ Cancel ]" ) );
    }

    if( msg && height > 5 ) {
        trim_and_print( w_refuel_overlay, point( 2, height - 5 ), width - 4, c_light_red, *msg );
    }
    wnoutrefresh( w_refuel_overlay );
}

bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )
{
    if( !refuel_info ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_refuel_overlay );
    const bool inside = pos && pos->x >= 0 && pos->y >= 0 &&
                        pos->x < getmaxx( w_refuel_overlay ) && pos->y < getmaxy( w_refuel_overlay );
    if( !inside ) {
        // The modal owns mouse input while open; clicks outside do not alter the editor behind it.
        return action == "SELECT" || action == "SEC_SELECT" || action == "SCROLL_UP" ||
               action == "SCROLL_DOWN" || action == "MOUSE_MOVE";
    }

    const int height = getmaxy( w_refuel_overlay );
    using refuel_stage = refuel_info_t::stage_t;

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        const int delta = action == "SCROLL_UP" ? -1 : 1;
        if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {
            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,
                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );
        } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {
            refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,
                                      static_cast<int>( refuel_info->sources.size() ) - 1 );
        } else if( refuel_info->stage == refuel_stage::quick_fuel && !refuel_info->quick_fuels.empty() ) {
            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,
                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
        }
        return true;
    }

    if( action != "SELECT" ) {
        return true;
    }

    msg.reset();
    if( refuel_info->stage == refuel_stage::tank ) {
        constexpr int first_row = 3;
        const int button_rows = editor_test_mode ? 4 : 3;
        const int visible = std::max( 1, height - first_row - button_rows );
        if( pos->y >= first_row && pos->y < first_row + visible ) {
            const int slot = refuel_info->tank_scroll + pos->y - first_row;
            if( slot >= 0 && slot < static_cast<int>( refuel_info->tanks.size() ) ) {
                refuel_info->tank_pos = slot;
                const int part_index = refuel_info->tanks[slot];
                if( veh->part( part_index ).can_reload() ) {
                    refuel_info->selected_tank_slot = slot;
                    refuel_info->stage = refuel_stage::source;
                    refuel_info->source_pos = 0;
                    refuel_info->source_range_anchor = -1;
                    refresh_refuel_sources( here );
                } else {
                    msg = _( "That fuel store is already full or cannot currently be refilled." );
                }
            }
            return true;
        }
        const int quick_y = height - ( editor_test_mode ? 4 : 3 );
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

    if( refuel_info->stage == refuel_stage::source ) {
        constexpr int first_row = 4;
        const int visible = std::max( 1, height - first_row - 5 );
        if( pos->y >= first_row && pos->y < first_row + visible ) {
            const int index = refuel_info->source_scroll + pos->y - first_row;
            if( index < 0 || index >= static_cast<int>( refuel_info->sources.size() ) ) {
                return true;
            }

            const input_event raw = main_context.get_raw_input();
            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;
            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;
            const item_location clicked = refuel_info->sources[index].location;
            const auto now = std::chrono::steady_clock::now();
            const bool double_click = !ctrl && !shift && refuel_info->last_clicked_source &&
                                      refuel_info->last_clicked_source == clicked &&
                                      refuel_info->last_source_click_time &&
                                      now - *refuel_info->last_source_click_time <= std::chrono::milliseconds( 500 );

            refuel_info->source_pos = index;
            if( shift && refuel_info->source_range_anchor >= 0 ) {
                if( !ctrl ) {
                    for( refuel_info_t::source_t &source : refuel_info->sources ) {
                        source.selected = false;
                    }
                }
                const int first = std::min( refuel_info->source_range_anchor, index );
                const int last = std::max( refuel_info->source_range_anchor, index );
                for( int i = first; i <= last; ++i ) {
                    refuel_info->sources[i].selected = true;
                }
            } else if( ctrl ) {
                refuel_info->sources[index].selected = !refuel_info->sources[index].selected;
                refuel_info->source_range_anchor = index;
            } else {
                for( refuel_info_t::source_t &source : refuel_info->sources ) {
                    source.selected = false;
                }
                refuel_info->sources[index].selected = true;
                refuel_info->source_range_anchor = index;
            }

            if( double_click ) {
                refuel_info->last_clicked_source = item_location();
                refuel_info->last_source_click_time.reset();
                queue_selected_refill_source( here );
            } else {
                refuel_info->last_clicked_source = clicked;
                refuel_info->last_source_click_time = now;
            }
            return true;
        }
        if( pos->y == height - 3 ) {
            queue_selected_refill_source( here );
            return true;
        }
        if( pos->y == height - 2 ) {
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
        return true;
    }

    const int first_row = 3;
    const int visible = std::max( 1, height - first_row - 4 );
    if( pos->y >= first_row && pos->y < first_row + visible ) {
        const int index = refuel_info->quick_fuel_scroll + pos->y - first_row;
        if( index >= 0 && index < static_cast<int>( refuel_info->quick_fuels.size() ) ) {
            refuel_info->quick_fuel_pos = index;
        }
        return true;
    }
    if( pos->y == height - 3 ) {
        queue_quick_refill_all( here );
        return true;
    }
    if( pos->y == height - 2 ) {
        const int cancel_x = getmaxx( w_refuel_overlay ) / 2;
        if( pos->x >= cancel_x ) {
            close_refuel_mode();
        } else {
            refuel_info->stage = refuel_stage::tank;
            refresh_refuel_sources( here );
        }
        return true;
    }
    return true;
}

void veh_interact::do_refill( map &here )
{
    if( refuel_info ) {
        refresh_refuel_sources( here );
        return;
    }

    switch( cant_do( here, 'f' ) ) {
        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't refill a moving vehicle." );
            return;
        case task_reason::INVALID_TARGET:
            msg = _( "No parts can currently be refilled." );
            return;
        default:
            break;
    }

    refuel_info = std::make_unique<refuel_info_t>();
    for( const vpart_reference &ref : veh->get_all_parts() ) {
        const vehicle_part &part = ref.part();
        if( part.removed || !( part.is_tank() || part.is_fuel_store() ) ) {
            continue;
        }
        refuel_info->tanks.push_back( veh->index_of_part( &part ) );
    }

    for( size_t i = 0; i < refuel_info->tanks.size(); ++i ) {
        if( refuel_info->tanks[i] == selected_part && veh->part( refuel_info->tanks[i] ).can_reload() ) {
            refuel_info->tank_pos = static_cast<int>( i );
            break;
        }
        if( !veh->part( refuel_info->tanks[refuel_info->tank_pos] ).can_reload() &&
            veh->part( refuel_info->tanks[i] ).can_reload() ) {
            refuel_info->tank_pos = static_cast<int>( i );
        }
    }
    refresh_refuel_sources( here );
    msg.reset();
}

void veh_interact::calc_overview'''

c = sub_once(c, REFUEL_BLOCK, NEW_REFUEL, 'replace complete refuel UI/state block')
CPP.write_text(c)

# Status document ------------------------------------------------------------
s = STATUS.read_text()
s = s.replace('approximately 96% complete', 'approximately 97% complete', 1)
s = s.replace('Current estimate: **~96% complete**.', 'Current estimate: **~97% complete**.', 1)
s = s.replace('The remaining ~4% is primarily stabilization and UX completion.',
              'The remaining ~3% is primarily stabilization and UX completion.', 1)
s = s.replace('**Refuel** opens the dedicated persistent three-panel selector while still completing through the existing `ACT_VEHICLE` refill backend; there is no second mouse-only fuel rules path.',
              '**Refuel** opens a compact staged overlay over the editor while still completing through the existing `ACT_VEHICLE` refill backend; there is no second mouse-only fuel rules path.', 1)

s = sub_once(
    s,
    r'''### Persistent refuel pane\n.*?\n### First-class editor viewport''',
    '''### Compact staged refuel overlay\n\n- [x] Single **Refuel** toolbar action opens a compact centered overlay while the vehicle editor remains visible behind it.\n- [x] Stage 1 is fuel-store selection with current fuel/capacity information plus **Quick fill…**. Selecting a store advances immediately to source selection.\n- [x] Stage 2 is source selection for exactly that store. Plain click selects one source, Ctrl+click toggles sources, Shift+click selects a contiguous range, and Ctrl+Shift extends a range, matching the inventory overhaul's desktop multi-select model.\n- [x] Double-clicking a source performs the selected-source refill immediately. Multi-source confirmation remains a batch convenience only: every actual source→store transfer still costs one normal refill action turn.\n- [x] **Quick fill…** now has its own propulsion-fuel stage. The player chooses an actually available fuel type; container/source selection is then automatic.\n- [x] Quick-fill fuel choices are the intersection of fuel accepted by installed working propulsion engines, fuel actually available from reachable sources, and compatible onboard stores that still have capacity. Unrelated utility/reactor/liquid fuel types are not offered merely because the vehicle can store them.\n- [x] Quick fill then fills only onboard stores compatible with the chosen propulsion fuel and keeps the existing minimum-transfer-oriented source planner.\n- [x] Refuel source discovery still covers carried items, accessible adjacent map tiles, nearby vehicle cargo, and raw map/pump-tile liquid.\n- [x] Liquid quantities and fluid-tank capacity/current/remaining values are presented in liters.\n- [x] Vehicle Editor **Test** mode exposes a small **add filled fuel containers to cargo** button. It ignores player distance, inserts ordinary filled containers directly into valid cargo/trunk parts on the edited vehicle, and creates several different fluid-capable container types so normal source-selection/container handling can be exercised.\n- [x] The test helper prefers a liquid fuel actually accepted by an installed propulsion engine (gasoline when applicable) and remains completely unavailable when Test mode is off.\n- [x] Batch and single refills share `veh_interact::complete_vehicle`; portable liquid containers, raw map liquid, and fuel-store reloads are completed through canonical item locations rather than directly mutating vehicle fuel counters from the UI.\n\n### First-class editor viewport''',
    'status staged refuel section'
)
s = s.replace('- [ ] In Vehicle Editor Test mode, add a test-only way to place ordinary filled gasoline containers into valid vehicle cargo/trunk storage so manual and quick-refill source selection can be exercised with real items.',
              '- [x] Vehicle Editor Test mode can now place several ordinary filled fluid-capable containers directly into valid vehicle cargo/trunk storage, ignoring player distance for development testing only.', 1)
STATUS.write_text(s)
