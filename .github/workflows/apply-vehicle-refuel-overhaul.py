from pathlib import Path
import re

CPP = Path("src/veh_interact.cpp")
HDR = Path("src/veh_interact.h")
STATUS = Path("doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Header state / declarations
# ---------------------------------------------------------------------------
h = HDR.read_text()

h = replace_once(
    h,
    """        // target vehicle tank for refill with liquids\n        item_location refill_target;\n""",
    """        // Legacy single refill target plus the persistent editor's batch payload.\n        item_location refill_target;\n        std::vector<int> refill_part_indices;\n        std::vector<item_location> refill_targets;\n""",
    "header refill state",
)

h = replace_once(
    h,
    """        catacurses::window w_list;\n        catacurses::window w_details;\n        catacurses::window w_name;\n""",
    """        catacurses::window w_list;\n        catacurses::window w_details;\n        catacurses::window w_name;\n        catacurses::window w_refuel_tanks;\n        catacurses::window w_refuel_sources;\n        catacurses::window w_refuel_details;\n""",
    "header refuel windows",
)

h = replace_once(
    h,
    """        struct remove_info_t;\n\n        std::unique_ptr<remove_info_t> remove_info;\n\n        vehicle *veh;\n""",
    """        struct remove_info_t;\n\n        std::unique_ptr<remove_info_t> remove_info;\n\n        struct refuel_info_t;\n\n        std::unique_ptr<refuel_info_t> refuel_info;\n\n        vehicle *veh;\n""",
    "header refuel info",
)

h = replace_once(
    h,
    """        void do_mend( map &here );\n        void do_refill( map &here );\n        void do_remove( map &here );\n""",
    """        void do_mend( map &here );\n        void do_refill( map &here );\n        void refresh_refuel_sources( map &here );\n        bool refill_source_compatible( const vehicle_part &part, const item_location &source ) const;\n        int refill_source_available( const item_location &source ) const;\n        int refill_part_remaining( const vehicle_part &part, const item_location &source ) const;\n        bool queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan );\n        bool queue_selected_refill_source( map &here );\n        bool queue_quick_refill_all( map &here );\n        void close_refuel_mode();\n        bool handle_refuel_mouse( map &here, const std::string &action );\n        void display_refuel_pane( map &here );\n        void do_remove( map &here );\n""",
    "header refuel methods",
)

HDR.write_text(h)

# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------
c = CPP.read_text()

# Batch-aware activity timing and serialization.  game.cpp already burns the
# current action by setting player moves to zero when ACT_VEHICLE is assigned.
# Therefore N refill transfers require only N-1 additional activity turns here.
c = replace_once(
    c,
    """        case 'o':\n            time = vp->removal_time( player_character );\n            break;\n        default:\n            break;\n    }\n    if( player_character.has_trait( trait_DEBUG_HS ) || editor_test_mode ) {\n        time = 1_seconds;\n    }\n""",
    """        case 'o':\n            time = vp->removal_time( player_character );\n            break;\n        case 'f':\n            if( !refill_part_indices.empty() ) {\n                time = time_duration::from_turns(\n                           std::max( 0, static_cast<int>( refill_part_indices.size() ) - 1 ) );\n            }\n            break;\n        default:\n            break;\n    }\n    // Refueling keeps normal turn accounting even in Vehicle Editor Test mode:\n    // the initial action consumes one turn and every additional transfer is one\n    // more ACT_VEHICLE turn.  Other editor test operations retain fast timing.\n    if( sel_cmd != 'f' && ( player_character.has_trait( trait_DEBUG_HS ) || editor_test_mode ) ) {\n        time = 1_seconds;\n    }\n""",
    "serialize refill time",
)

c = replace_once(
    c,
    """    res.values.push_back( veh->index_of_part( vpt ) ); // values[6]\n    res.str_values.emplace_back( vp->id.str() );\n    res.str_values.emplace_back( editor_test_mode ? \"vehicle_editor_test\" : \"\" );\n    res.targets.emplace_back( std::move( refill_target ) );\n\n    return res;\n""",
    """    const int primary_part_index = sel_cmd == 'f' && !refill_part_indices.empty() ?\n                                   refill_part_indices.front() : veh->index_of_part( vpt );\n    res.values.push_back( primary_part_index ); // values[6]\n    if( sel_cmd == 'f' && refill_part_indices.size() > 1 ) {\n        for( size_t i = 1; i < refill_part_indices.size(); ++i ) {\n            res.values.push_back( refill_part_indices[i] );\n        }\n    }\n    res.str_values.emplace_back( vp->id.str() );\n    res.str_values.emplace_back( editor_test_mode ? \"vehicle_editor_test\" : \"\" );\n    res.str_values.emplace_back( sel_cmd == 'f' && !refill_part_indices.empty() ?\n                                 \"vehicle_refill_batch\" : \"\" );\n    if( sel_cmd == 'f' && !refill_targets.empty() ) {\n        for( item_location &target : refill_targets ) {\n            res.targets.emplace_back( std::move( target ) );\n        }\n    } else {\n        res.targets.emplace_back( std::move( refill_target ) );\n    }\n\n    return res;\n""",
    "serialize refill payload",
)

# Dedicated three-column refuel windows reuse the editor body while leaving the
# responsive toolbar and bottom vehicle stats intact.
c = replace_once(
    c,
    """    w_name = catacurses::newwin( name_h, grid_w, point( grid.x, name_y ) );\n\n    // Existing install/remove details continue to occupy the lower-right stats area.\n""",
    """    w_name = catacurses::newwin( name_h, grid_w, point( grid.x, name_y ) );\n\n    const int refuel_tank_w = std::max( 22, grid_w * 30 / 100 );\n    const int refuel_source_w = std::max( 26, grid_w * 38 / 100 );\n    const int refuel_detail_w = std::max( 1, grid_w - refuel_tank_w - refuel_source_w );\n    w_refuel_tanks = catacurses::newwin( page_size, refuel_tank_w,\n                                         point( grid.x, pane_y ) );\n    w_refuel_sources = catacurses::newwin( page_size, refuel_source_w,\n                                           point( grid.x + refuel_tank_w, pane_y ) );\n    w_refuel_details = catacurses::newwin( page_size, refuel_detail_w,\n                                           point( grid.x + refuel_tank_w + refuel_source_w, pane_y ) );\n\n    // Existing install/remove details continue to occupy the lower-right stats area.\n""",
    "allocate refuel windows",
)

c = replace_once(
    c,
    """struct veh_interact::remove_info_t {\n    int pos = 0;\n    size_t tab = 0;\n};\n\nshared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor( map &here )\n""",
    """struct veh_interact::remove_info_t {\n    int pos = 0;\n    size_t tab = 0;\n};\n\nstruct veh_interact::refuel_info_t {\n    struct source_t {\n        item_location location;\n        std::string label;\n    };\n\n    std::vector<int> tanks;\n    std::vector<bool> selected_tanks;\n    std::vector<source_t> sources;\n    int tank_scroll = 0;\n    int source_scroll = 0;\n    int source_pos = 0;\n    int last_clicked_tank = -1;\n    item_location last_clicked_source;\n    std::optional<std::chrono::steady_clock::time_point> last_tank_click_time;\n    std::optional<std::chrono::steady_clock::time_point> last_source_click_time;\n};\n\nshared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor( map &here )\n""",
    "refuel info struct",
)

# Refuel mode owns the body of the editor.  Clear the live tiles preview so its
# auxiliary renderer cannot remain registered under the full-width selector.
c = replace_once(
    c,
    """            display_grid();\n            display_name();\n            display_stats( here );\n            display_veh( here );\n\n            const auto draw_message_window = [&]() {\n""",
    """            display_grid();\n            display_name();\n            display_stats( here );\n            if( refuel_info ) {\n                display_refuel_pane( here );\n                display_mode( here );\n#if defined(TILES)\n                clear_map_preview_window();\n#endif\n                return;\n            }\n            display_veh( here );\n\n            const auto draw_message_window = [&]() {\n""",
    "redraw refuel pane",
)

# Keyboard/refuel-mode routing.  Mouse double-click/Quick actions set sel_cmd;
# the existing main loop then exits and serializes ACT_VEHICLE normally.
c = replace_once(
    c,
    """        if( install_info ) {\n            if( action == \"QUIT\" ) {\n                close_install_mode();\n                continue;\n            }\n""",
    """        if( refuel_info ) {\n            if( action == \"QUIT\" ) {\n                close_refuel_mode();\n                continue;\n            }\n            if( action == \"REFILL\" || action == \"CONFIRM\" ) {\n                if( queue_selected_refill_source( here ) ) {\n                    finish = true;\n                }\n                continue;\n            }\n            if( action == \"UP\" || action == \"DOWN\" ||\n                action == \"PAGE_UP\" || action == \"PAGE_DOWN\" ) {\n                if( !refuel_info->sources.empty() ) {\n                    const int page = std::max( 1, getmaxy( w_refuel_sources ) - 4 );\n                    int delta = action == \"UP\" ? -1 : action == \"DOWN\" ? 1 :\n                                action == \"PAGE_UP\" ? -page : page;\n                    refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,\n                                              static_cast<int>( refuel_info->sources.size() ) - 1 );\n                }\n                continue;\n            }\n            // Persistent refuel mode consumes unrelated editor/navigation input\n            // rather than letting it move the vehicle mount behind the pane.\n            continue;\n        } else if( install_info ) {\n            if( action == \"QUIT\" ) {\n                close_install_mode();\n                continue;\n            }\n""",
    "main loop refuel routing",
)

# Toolbar is locked to Refuel/Back while the persistent selector is open.
c = replace_once(
    c,
    """bool veh_interact::editor_toolbar_action_enabled( const map &here, const std::string &action )\n{\n    if( install_info ) {\n""",
    """bool veh_interact::editor_toolbar_action_enabled( const map &here, const std::string &action )\n{\n    if( refuel_info ) {\n        return action == \"REFILL\" || action == \"QUIT\";\n    }\n    if( install_info ) {\n""",
    "toolbar refuel mode",
)

# Route body mouse events into the dedicated selector after toolbar hit-testing.
c = replace_once(
    c,
    """        if( toolbar_handled ) {\n            return true;\n        }\n    }\n\n    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {\n""",
    """        if( toolbar_handled ) {\n            return true;\n        }\n    }\n\n    if( refuel_info ) {\n        return handle_refuel_mouse( here, action );\n    }\n\n    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {\n""",
    "mouse refuel routing",
)

# Replace the legacy overview + inv_map_splice path with the persistent three-
# panel editor selector and its shared planning helpers.
refuel_impl = r'''void veh_interact::close_refuel_mode()
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
        // Raw map liquid covers fuel sitting on a pump/map tile without treating
        // contained liquid as a second source beside its portable container.
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

    item_location previous;
    if( refuel_info->source_pos >= 0 &&
        refuel_info->source_pos < static_cast<int>( refuel_info->sources.size() ) ) {
        previous = refuel_info->sources[refuel_info->source_pos].location;
    }
    refuel_info->sources.clear();

    Character &player_character = get_player_character();
    const bool any_selected = std::any_of( refuel_info->selected_tanks.begin(),
                                           refuel_info->selected_tanks.end(), []( bool selected ) {
        return selected;
    } );

    const auto add_source = [&]( const item_location &loc ) {
        if( !loc ) {
            return;
        }
        // The portable container is the source shown to the user.  Do not also
        // list its contained liquid as a separate nested entry.
        if( loc->made_of( phase_id::LIQUID ) && loc.has_parent() ) {
            return;
        }
        bool compatible = false;
        for( size_t i = 0; i < refuel_info->tanks.size(); ++i ) {
            if( any_selected && !refuel_info->selected_tanks[i] ) {
                continue;
            }
            const int part_index = refuel_info->tanks[i];
            if( part_index >= 0 && part_index < veh->part_count() &&
                refill_source_compatible( veh->part( part_index ), loc ) &&
                refill_part_remaining( veh->part( part_index ), loc ) > 0 ) {
                compatible = true;
                break;
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
    if( previous ) {
        const auto found = std::find_if( refuel_info->sources.begin(), refuel_info->sources.end(),
        [&]( const refuel_info_t::source_t &entry ) {
            return entry.location == previous;
        } );
        if( found != refuel_info->sources.end() ) {
            refuel_info->source_pos = static_cast<int>( std::distance( refuel_info->sources.begin(), found ) );
        }
    }
    if( refuel_info->sources.empty() ) {
        refuel_info->source_pos = 0;
        refuel_info->source_scroll = 0;
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
    if( !refuel_info || refuel_info->sources.empty() ) {
        msg = _( "No compatible fuel source is available within reach." );
        return false;
    }
    refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                              static_cast<int>( refuel_info->sources.size() ) - 1 );
    const item_location source = refuel_info->sources[refuel_info->source_pos].location;
    int available = refill_source_available( source );
    if( available <= 0 ) {
        msg = _( "That fuel source is empty." );
        refresh_refuel_sources( here );
        return false;
    }

    const item *payload = source.get_item();
    if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
        payload = &source->only_item();
    }
    const bool divisible_liquid = payload != nullptr && payload->made_of( phase_id::LIQUID ) &&
                                  payload->count_by_charges();

    std::vector<std::pair<int, item_location>> plan;
    for( size_t i = 0; i < refuel_info->tanks.size() && available > 0; ++i ) {
        if( !refuel_info->selected_tanks[i] ) {
            continue;
        }
        const int part_index = refuel_info->tanks[i];
        vehicle_part &part = veh->part( part_index );
        if( !refill_source_compatible( part, source ) ) {
            continue;
        }
        const int needed = refill_part_remaining( part, source );
        if( needed <= 0 ) {
            continue;
        }
        plan.emplace_back( part_index, source );
        if( divisible_liquid ) {
            available -= std::min( available, needed );
        } else {
            available = 0;
        }
    }

    if( plan.empty() ) {
        msg = _( "Select at least one compatible tank or fuel store." );
        return false;
    }
    return queue_refill_plan( plan );
}

bool veh_interact::queue_quick_refill_all( map &here )
{
    if( !refuel_info ) {
        return false;
    }
    // Quick refill operates over every refillable store, independent of the
    // manual checkbox selection.  Rebuild against all tanks so sources filtered
    // out by a current manual selection are available to the planner.
    std::vector<bool> saved_selection = refuel_info->selected_tanks;
    std::fill( refuel_info->selected_tanks.begin(), refuel_info->selected_tanks.end(), false );
    refresh_refuel_sources( here );

    std::vector<int> remaining;
    remaining.reserve( refuel_info->sources.size() );
    for( const refuel_info_t::source_t &source : refuel_info->sources ) {
        remaining.push_back( refill_source_available( source.location ) );
    }

    std::vector<size_t> tank_order( refuel_info->tanks.size() );
    std::iota( tank_order.begin(), tank_order.end(), 0 );
    std::stable_sort( tank_order.begin(), tank_order.end(), [&]( size_t lhs, size_t rhs ) {
        int lhs_need = 0;
        int rhs_need = 0;
        for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
            if( refill_source_compatible( veh->part( refuel_info->tanks[lhs] ),
                                          refuel_info->sources[s].location ) ) {
                lhs_need = std::max( lhs_need, refill_part_remaining(
                                         veh->part( refuel_info->tanks[lhs] ), refuel_info->sources[s].location ) );
            }
            if( refill_source_compatible( veh->part( refuel_info->tanks[rhs] ),
                                          refuel_info->sources[s].location ) ) {
                rhs_need = std::max( rhs_need, refill_part_remaining(
                                         veh->part( refuel_info->tanks[rhs] ), refuel_info->sources[s].location ) );
            }
        }
        return lhs_need > rhs_need;
    } );

    std::vector<std::pair<int, item_location>> plan;
    for( size_t tank_slot : tank_order ) {
        const int part_index = refuel_info->tanks[tank_slot];
        vehicle_part &part = veh->part( part_index );
        while( true ) {
            int best_source = -1;
            int best_transfer = 0;
            bool best_finishes = false;
            int best_finishing_surplus = INT_MAX;
            int need_for_best = 0;

            for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
                if( remaining[s] <= 0 ||
                    !refill_source_compatible( part, refuel_info->sources[s].location ) ) {
                    continue;
                }
                const int needed = refill_part_remaining( part, refuel_info->sources[s].location );
                if( needed <= 0 ) {
                    continue;
                }
                const int transfer = std::min( needed, remaining[s] );
                const bool finishes = remaining[s] >= needed;
                const int surplus = finishes ? remaining[s] - needed : INT_MAX;
                if( ( finishes && !best_finishes ) ||
                    ( finishes == best_finishes && finishes && surplus < best_finishing_surplus ) ||
                    ( !finishes && !best_finishes && transfer > best_transfer ) ) {
                    best_source = static_cast<int>( s );
                    best_transfer = transfer;
                    best_finishes = finishes;
                    best_finishing_surplus = surplus;
                    need_for_best = needed;
                }
            }

            if( best_source < 0 || best_transfer <= 0 ) {
                break;
            }

            const item_location source = refuel_info->sources[best_source].location;
            plan.emplace_back( part_index, source );
            const item *payload = source.get_item();
            if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
                payload = &source->only_item();
            }
            if( payload != nullptr && payload->made_of( phase_id::LIQUID ) && payload->count_by_charges() ) {
                remaining[best_source] -= best_transfer;
            } else {
                remaining[best_source] = 0;
            }
            if( best_transfer >= need_for_best ) {
                break;
            }
        }
    }

    if( plan.empty() ) {
        refuel_info->selected_tanks = std::move( saved_selection );
        refresh_refuel_sources( here );
        msg = _( "No valid refuel transfers are available." );
        return false;
    }

    // Each pair is one canonical vehicle refill transfer.  serialize_activity()
    // charges exactly one action-turn per pair, including the current turn.
    return queue_refill_plan( plan );
}

void veh_interact::display_refuel_pane( map & )
{
    if( !refuel_info ) {
        return;
    }

    const auto draw_panel = []( const catacurses::window &win, const std::string &title ) {
        werase( win );
        draw_border( win );
        trim_and_print( win, point( 2, 0 ), std::max( 1, getmaxx( win ) - 4 ), c_light_green, title );
    };
    draw_panel( w_refuel_tanks, _( "Vehicle fuel stores" ) );
    draw_panel( w_refuel_sources, _( "Available fuel sources" ) );
    draw_panel( w_refuel_details, _( "Refuel selection" ) );

    const auto source_payload = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };
    const auto source_amount = [&]( const item_location &source ) {
        const item *payload = source_payload( source );
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

    constexpr int first_row = 2;
    const int tank_visible = std::max( 1, getmaxy( w_refuel_tanks ) - first_row - 1 );
    const int tank_max_scroll = std::max( 0, static_cast<int>( refuel_info->tanks.size() ) - tank_visible );
    refuel_info->tank_scroll = std::clamp( refuel_info->tank_scroll, 0, tank_max_scroll );
    for( int row = 0; row < tank_visible; ++row ) {
        const int slot = refuel_info->tank_scroll + row;
        if( slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
            break;
        }
        const vehicle_part &part = veh->part( refuel_info->tanks[slot] );
        const bool selected = refuel_info->selected_tanks[slot];
        const std::string marker = selected ? "[x] " : "[ ] ";
        const std::string label = string_format( "%s%s  %s", marker, part.name(), tank_amount( part ) );
        trim_and_print( w_refuel_tanks, point( 1, first_row + row ),
                        std::max( 1, getmaxx( w_refuel_tanks ) - 2 ),
                        selected ? c_light_cyan : c_light_gray, label );
    }
    if( static_cast<int>( refuel_info->tanks.size() ) > tank_visible ) {
        scrollbar().offset_x( getmaxx( w_refuel_tanks ) - 1 ).offset_y( first_row )
        .content_size( static_cast<int>( refuel_info->tanks.size() ) )
        .viewport_pos( refuel_info->tank_scroll ).viewport_size( tank_visible ).apply( w_refuel_tanks );
    }

    const int source_visible = std::max( 1, getmaxy( w_refuel_sources ) - first_row - 2 );
    if( !refuel_info->sources.empty() ) {
        refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                  static_cast<int>( refuel_info->sources.size() ) - 1 );
        if( refuel_info->source_pos < refuel_info->source_scroll ) {
            refuel_info->source_scroll = refuel_info->source_pos;
        } else if( refuel_info->source_pos >= refuel_info->source_scroll + source_visible ) {
            refuel_info->source_scroll = refuel_info->source_pos - source_visible + 1;
        }
        const int source_max_scroll = std::max( 0,
                                      static_cast<int>( refuel_info->sources.size() ) - source_visible );
        refuel_info->source_scroll = std::clamp( refuel_info->source_scroll, 0, source_max_scroll );
    }
    for( int row = 0; row < source_visible; ++row ) {
        const int index = refuel_info->source_scroll + row;
        if( index >= static_cast<int>( refuel_info->sources.size() ) ) {
            break;
        }
        const refuel_info_t::source_t &source = refuel_info->sources[index];
        const std::string line = string_format( "%s  %s", source_amount( source.location ), source.label );
        trim_and_print( w_refuel_sources, point( 1, first_row + row ),
                        std::max( 1, getmaxx( w_refuel_sources ) - 2 ),
                        index == refuel_info->source_pos ? h_white : c_light_gray, line );
    }
    if( refuel_info->sources.empty() ) {
        trim_and_print( w_refuel_sources, point( 2, first_row ),
                        std::max( 1, getmaxx( w_refuel_sources ) - 4 ), c_dark_gray,
                        _( "No compatible carried, adjacent, cargo, or map fuel sources." ) );
    } else if( static_cast<int>( refuel_info->sources.size() ) > source_visible ) {
        scrollbar().offset_x( getmaxx( w_refuel_sources ) - 1 ).offset_y( first_row )
        .content_size( static_cast<int>( refuel_info->sources.size() ) )
        .viewport_pos( refuel_info->source_scroll ).viewport_size( source_visible ).apply( w_refuel_sources );
    }
    trim_and_print( w_refuel_sources, point( 1, getmaxy( w_refuel_sources ) - 2 ),
                    std::max( 1, getmaxx( w_refuel_sources ) - 2 ), c_dark_gray,
                    _( "Double-click a source to refuel selected stores." ) );

    int detail_y = 2;
    int selected_count = 0;
    for( size_t slot = 0; slot < refuel_info->tanks.size(); ++slot ) {
        if( !refuel_info->selected_tanks[slot] ) {
            continue;
        }
        ++selected_count;
        const vehicle_part &part = veh->part( refuel_info->tanks[slot] );
        if( detail_y < getmaxy( w_refuel_details ) - 7 ) {
            trim_and_print( w_refuel_details, point( 1, detail_y++ ),
                            std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_cyan,
                            string_format( "%s: %s", part.name(), tank_amount( part ) ) );
            if( part.is_tank() ) {
                units::volume current = 0_ml;
                if( !part.base.empty() && part.base.only_item().made_of( phase_id::LIQUID ) ) {
                    current = part.base.only_item().volume();
                }
                trim_and_print( w_refuel_details, point( 3, detail_y++ ),
                                std::max( 1, getmaxx( w_refuel_details ) - 4 ), c_light_gray,
                                string_format( _( "Remaining: %.1f L" ),
                                               units::to_liter( std::max( 0_ml, part.info().size - current ) ) ) );
            }
        }
    }
    if( selected_count == 0 ) {
        trim_and_print( w_refuel_details, point( 2, detail_y++ ),
                        std::max( 1, getmaxx( w_refuel_details ) - 4 ), c_dark_gray,
                        _( "Select one or more fuel stores on the left." ) );
    }

    if( !refuel_info->sources.empty() && detail_y < getmaxy( w_refuel_details ) - 6 ) {
        const refuel_info_t::source_t &source = refuel_info->sources[refuel_info->source_pos];
        trim_and_print( w_refuel_details, point( 1, detail_y++ ),
                        std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_green,
                        string_format( _( "Source: %s" ), source_amount( source.location ) ) );
    }

    const int button_y = std::max( 2, getmaxy( w_refuel_details ) - 5 );
    trim_and_print( w_refuel_details, point( 1, button_y ),
                    std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_green,
                    _( "[ Refuel selected ]" ) );
    trim_and_print( w_refuel_details, point( 1, button_y + 1 ),
                    std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_cyan,
                    _( "[ Quick refill all ]" ) );
    trim_and_print( w_refuel_details, point( 1, button_y + 2 ),
                    std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_gray,
                    _( "[ Close ]" ) );
    trim_and_print( w_refuel_details, point( 1, button_y + 3 ),
                    std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_dark_gray,
                    _( "Batch refuel costs one normal action turn per transfer." ) );

    wnoutrefresh( w_refuel_tanks );
    wnoutrefresh( w_refuel_sources );
    wnoutrefresh( w_refuel_details );
}

bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )
{
    if( !refuel_info ) {
        return false;
    }
    const auto mouse_pos_in = [&]( const catacurses::window &win ) -> std::optional<point> {
        const std::optional<point> pos = main_context.get_coordinates_text( win );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( win ) || pos->y >= getmaxy( win ) ) {
            return std::nullopt;
        }
        return pos;
    };
    const std::optional<point> tank_pos = mouse_pos_in( w_refuel_tanks );
    const std::optional<point> source_pos = mouse_pos_in( w_refuel_sources );
    const std::optional<point> detail_pos = mouse_pos_in( w_refuel_details );

    constexpr int first_row = 2;
    if( action == "SELECT" ) {
        if( tank_pos && tank_pos->y >= first_row ) {
            const int slot = refuel_info->tank_scroll + tank_pos->y - first_row;
            if( slot >= 0 && slot < static_cast<int>( refuel_info->tanks.size() ) ) {
                const auto now = std::chrono::steady_clock::now();
                const bool double_click = refuel_info->last_clicked_tank == slot &&
                                          refuel_info->last_tank_click_time &&
                                          now - *refuel_info->last_tank_click_time <= std::chrono::milliseconds( 500 );
                if( double_click ) {
                    std::fill( refuel_info->selected_tanks.begin(), refuel_info->selected_tanks.end(), false );
                    refuel_info->selected_tanks[slot] = true;
                    refuel_info->last_clicked_tank = -1;
                    refuel_info->last_tank_click_time.reset();
                } else {
                    refuel_info->selected_tanks[slot] = !refuel_info->selected_tanks[slot];
                    refuel_info->last_clicked_tank = slot;
                    refuel_info->last_tank_click_time = now;
                }
                refresh_refuel_sources( here );
            }
            return true;
        }
        if( source_pos && source_pos->y >= first_row &&
            source_pos->y < getmaxy( w_refuel_sources ) - 2 ) {
            const int index = refuel_info->source_scroll + source_pos->y - first_row;
            if( index >= 0 && index < static_cast<int>( refuel_info->sources.size() ) ) {
                const item_location clicked = refuel_info->sources[index].location;
                const auto now = std::chrono::steady_clock::now();
                const bool double_click = refuel_info->last_clicked_source &&
                                          refuel_info->last_clicked_source == clicked &&
                                          refuel_info->last_source_click_time &&
                                          now - *refuel_info->last_source_click_time <= std::chrono::milliseconds( 500 );
                refuel_info->source_pos = index;
                if( double_click ) {
                    refuel_info->last_clicked_source = item_location();
                    refuel_info->last_source_click_time.reset();
                    queue_selected_refill_source( here );
                } else {
                    refuel_info->last_clicked_source = clicked;
                    refuel_info->last_source_click_time = now;
                }
            }
            return true;
        }
        if( detail_pos ) {
            const int button_y = std::max( 2, getmaxy( w_refuel_details ) - 5 );
            if( detail_pos->y == button_y ) {
                queue_selected_refill_source( here );
                return true;
            }
            if( detail_pos->y == button_y + 1 ) {
                queue_quick_refill_all( here );
                return true;
            }
            if( detail_pos->y == button_y + 2 ) {
                close_refuel_mode();
                return true;
            }
        }
        return true;
    }

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        const int delta = action == "SCROLL_UP" ? -1 : 1;
        if( tank_pos ) {
            refuel_info->tank_scroll = std::max( 0, refuel_info->tank_scroll + delta );
            return true;
        }
        if( source_pos && !refuel_info->sources.empty() ) {
            refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,
                                      static_cast<int>( refuel_info->sources.size() ) - 1 );
            return true;
        }
        return detail_pos.has_value();
    }

    return tank_pos || source_pos || detail_pos || action == "MOUSE_MOVE" || action == "SEC_SELECT";
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
        refuel_info->selected_tanks.push_back( false );
    }

    int default_slot = -1;
    for( size_t i = 0; i < refuel_info->tanks.size(); ++i ) {
        if( refuel_info->tanks[i] == selected_part && veh->part( refuel_info->tanks[i] ).can_reload() ) {
            default_slot = static_cast<int>( i );
            break;
        }
        if( default_slot < 0 && veh->part( refuel_info->tanks[i] ).can_reload() ) {
            default_slot = static_cast<int>( i );
        }
    }
    if( default_slot >= 0 ) {
        refuel_info->selected_tanks[default_slot] = true;
    }
    refresh_refuel_sources( here );
    if( refuel_info->sources.empty() ) {
        msg = _( "No compatible fuel source is available within reach. You can still change the tank selection." );
    } else {
        msg.reset();
    }
}

void veh_interact::calc_overview'''

c, n = re.subn(
    r"void veh_interact::do_refill\( map &here \)\n\{.*?\n\}\n\nvoid veh_interact::calc_overview",
    refuel_impl,
    c,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit(f"refuel implementation: expected one replacement, got {n}")

# Batch-capable completion backend.  Single refuel activities still use one
# target/values[6], while the new marker maps targets[i] to values[6+i].
old_refill_complete = r'''        case 'f': {
            if( you.activity.targets.empty() || !you.activity.targets.front() ) {
                debugmsg( "Activity ACT_VEHICLE: missing refill source" );
                break;
            }

            item_location &src = you.activity.targets.front();
            vehicle_part &vp = veh.part( you.activity.values[6] );
            if( vp.is_tank() && src->is_container() && !src->empty() ) {
                item_location contained( src, &src->only_item() );
                contained->charges -= vp.base.fill_with( *contained, contained->charges );

                contents_change_handler handler;
                handler.unseal_pocket_containing( contained );

                // if code goes here, we can assume "vp" has already refilled with "contained" something.
                int remaining_ammo_capacity = vp.ammo_capacity( contained->ammo_type() ) - vp.ammo_remaining(
                                              );

                if( remaining_ammo_capacity ) {
                    //~ 1$s vehicle name, 2$s tank name
                    you.add_msg_if_player( m_good, _( "You refill the %1$s's %2$s." ), veh.name, vp.name() );
                } else {
                    //~ 1$s vehicle name, 2$s tank name
                    you.add_msg_if_player( m_good, _( "You completely refill the %1$s's %2$s." ), veh.name, vp.name() );
                }

                if( contained->charges == 0 ) {
                    contained.remove_item();
                } else {
                    you.add_msg_if_player( m_good, _( "There's some left over!" ) );
                }

                handler.handle_by( you );
            } else if( vp.is_fuel_store() ) {
                contents_change_handler handler;
                handler.unseal_pocket_containing( src );

                int qty = src->charges;
                vp.base.reload( you, std::move( src ), qty );

                //~ 1$s vehicle name, 2$s reactor name
                you.add_msg_if_player( m_good, _( "You refuel the %1$s's %2$s." ), veh.name, vp.name() );

                handler.handle_by( you );
            } else {
                debugmsg( "vehicle part is not reloadable" );
                break;
            }

            veh.invalidate_mass();
            break;
        }
'''

new_refill_complete = r'''        case 'f': {
            const bool batch = you.activity.str_values.size() > 2 &&
                               you.activity.str_values[2] == "vehicle_refill_batch";
            const size_t transfer_count = batch ? you.activity.targets.size() :
                                          std::min<size_t>( 1, you.activity.targets.size() );
            if( transfer_count == 0 ) {
                debugmsg( "Activity ACT_VEHICLE: missing refill source" );
                break;
            }

            const auto refill_one = [&]( vehicle_part &vp, item_location &src ) {
                if( !src ) {
                    debugmsg( "Activity ACT_VEHICLE: refill source became invalid" );
                    return;
                }

                if( vp.is_tank() ) {
                    item_location liquid;
                    if( src->is_container() && !src->empty() ) {
                        liquid = item_location( src, &src->only_item() );
                    } else if( src->made_of( phase_id::LIQUID ) ) {
                        liquid = src;
                    }
                    if( !liquid || !liquid->made_of( phase_id::LIQUID ) ) {
                        debugmsg( "Activity ACT_VEHICLE: invalid liquid refill source" );
                        return;
                    }

                    const itype_id fuel_type = liquid->typeId();
                    contents_change_handler handler;
                    if( liquid.has_parent() ) {
                        handler.unseal_pocket_containing( liquid );
                    }
                    const int moved = vp.base.fill_with( *liquid, liquid->charges );
                    liquid->charges -= moved;
                    if( moved <= 0 ) {
                        return;
                    }

                    const int remaining_ammo_capacity = std::max( 0,
                            vp.item_capacity( fuel_type ) - vp.ammo_remaining() );
                    if( remaining_ammo_capacity ) {
                        you.add_msg_if_player( m_good, _( "You refill the %1$s's %2$s." ), veh.name, vp.name() );
                    } else {
                        you.add_msg_if_player( m_good, _( "You completely refill the %1$s's %2$s." ),
                                               veh.name, vp.name() );
                    }

                    if( liquid->charges <= 0 ) {
                        liquid.remove_item();
                    } else {
                        liquid.on_contents_changed();
                    }
                    handler.handle_by( you );
                    return;
                }

                if( vp.is_fuel_store() ) {
                    contents_change_handler handler;
                    handler.unseal_pocket_containing( src );
                    const int qty = src->charges;
                    vp.base.reload( you, std::move( src ), qty );
                    you.add_msg_if_player( m_good, _( "You refuel the %1$s's %2$s." ), veh.name, vp.name() );
                    handler.handle_by( you );
                    return;
                }

                debugmsg( "vehicle part is not reloadable" );
            };

            for( size_t i = 0; i < transfer_count; ++i ) {
                if( 6 + i >= you.activity.values.size() ) {
                    debugmsg( "Activity ACT_VEHICLE: missing refill part index" );
                    break;
                }
                const int part_index = you.activity.values[6 + i];
                if( part_index < 0 || part_index >= veh.part_count() ) {
                    debugmsg( "Activity ACT_VEHICLE: invalid refill part index %d", part_index );
                    continue;
                }
                refill_one( veh.part( part_index ), you.activity.targets[i] );
            }

            veh.invalidate_mass();
            break;
        }
'''

c = replace_once(c, old_refill_complete, new_refill_complete, "complete refuel batch")
CPP.write_text(c)

# ---------------------------------------------------------------------------
# Living status document
# ---------------------------------------------------------------------------
s = STATUS.read_text()
s = s.replace("Status: **active — approximately 92% complete**",
              "Status: **active — approximately 96% complete**")
s = s.replace("Current estimate: **~92% complete**.", "Current estimate: **~96% complete**.")
s = s.replace(
    "Last audited implementation head: current `mouse-inventory-0-i-test` toolbar integration; live-preview camera fixes and action-hover requirements are included in this audit.",
    "Last audited implementation head: current `mouse-inventory-0-i-test` persistent refuel integration; live-preview camera fixes, action-hover requirements, and batch turn accounting are included in this audit.")
s = s.replace(
    "- [x] Current **Refuel** toolbar entry intentionally routes to the existing refill backend. The dedicated persistent Refuel pane is the next refueling implementation step rather than a second toolbar action.",
    "- [x] **Refuel** opens the dedicated persistent three-panel selector while still completing through the existing `ACT_VEHICLE` refill backend; there is no second mouse-only fuel rules path.")

anchor = "### First-class editor viewport\n"
refuel_section = """### Persistent refuel pane\n\n- [x] Single **Refuel** toolbar action opens a persistent three-panel workflow: vehicle fuel stores, available sources, and selection/details.\n- [x] Multiple tanks/fuel stores can be selected simultaneously.\n- [x] Compatible sources are discovered from carried items, accessible adjacent map tiles, and nearby vehicle cargo, including raw map/pump-tile liquid.\n- [x] Liquid quantities and fluid-tank capacity/current/remaining values are presented in liters.\n- [x] Double-clicking a fuel source immediately schedules refueling of the selected compatible stores.\n- [x] **Quick refill all** builds a turn-cost-aware plan that prefers a single source able to finish a store, otherwise consuming the largest useful source first to reduce transfer count.\n- [x] Batch refueling does **not** bypass game time: every planned tank/source transfer is one normal refill action. Because `game.cpp` already consumes the initial action turn when assigning `ACT_VEHICLE`, an `N`-transfer batch serializes exactly `N-1` additional turns.\n- [x] Batch and single refills share `veh_interact::complete_vehicle`; portable liquid containers, raw map liquid, and fuel-store reloads are completed through canonical item locations rather than directly mutating vehicle fuel counters from the UI.\n\n"""
if refuel_section not in s:
    s = s.replace(anchor, refuel_section + anchor, 1)

s = s.replace(
    "- [ ] Replace the legacy refill chooser behind the single **Refuel** toolbar entry with the persistent Refuel pane: vehicle/available-fuel summary, tank → source selection, double-click progression, and **Quick refill all** optimized for the lowest valid turn cost.",
    "- [x] Replace the legacy refill chooser behind the single **Refuel** toolbar entry with the persistent Refuel pane: vehicle/available-fuel summary, multi-tank → source selection, double-click progression, and turn-cost-aware **Quick refill all**.")
s = s.replace(
    "- [ ] Confirm install/remove/repair/refill/etc. paths do not accidentally diverge from normal `veh_interact` requirement, tool, activity, or move-cost rules.",
    "- [ ] Confirm install/remove/repair/etc. paths do not accidentally diverge from normal `veh_interact` requirement, tool, activity, or move-cost rules. Refuel is now explicitly routed through `ACT_VEHICLE`, with one normal action turn charged per individual transfer even when batched.")
s = s.replace(
    "`src/veh_interact.cpp` | Main editor redesign: viewport layout, selection, inspector, pan/zoom, filters/layers, context actions, install pane, responsive action toolbar, mode buttons, live preview state and interaction.",
    "`src/veh_interact.cpp` | Main editor redesign: viewport layout, selection, inspector, pan/zoom, filters/layers, context actions, install pane, persistent refuel pane/batch planning, responsive action toolbar, mode buttons, live preview state and interaction.")
STATUS.write_text(s)

# Sanity assertions before the workflow commits anything.
final_h = HDR.read_text()
final_c = CPP.read_text()
assert "std::unique_ptr<refuel_info_t> refuel_info" in final_h
assert "void veh_interact::display_refuel_pane" in final_c
assert "vehicle_refill_batch" in final_c
assert "time_duration::from_turns" in final_c
assert "Quick refill all" in final_c
assert "inv_map_splice" not in re.search(r"void veh_interact::do_refill\( map &here \).*?void veh_interact::calc_overview", final_c, re.S).group(0)
print("vehicle refuel overhaul patch applied")
