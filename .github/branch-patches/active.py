from pathlib import Path

SRC = Path("src/construction_ui.cpp")
DOC = Path("doc/UI_MODERNIZATION_PLANS/CONSTRUCTION_UI_IMPLEMENTATION_PLAN.md")
text = SRC.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)


def replace_count(old: str, new: str, expected: int, label: str) -> None:
    global text
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} matches, found {count}")
    text = text.replace(old, new)


def replace_between(start: str, end: str, new_block: str, label: str) -> None:
    global text
    begin = text.find(start)
    if begin < 0:
        raise RuntimeError(f"{label}: start marker not found")
    finish = text.find(end, begin)
    if finish < 0:
        raise RuntimeError(f"{label}: end marker not found")
    if text.find(start, begin + 1) >= 0 and text.find(start, begin + 1) < finish:
        raise RuntimeError(f"{label}: ambiguous start marker")
    text = text[:begin] + new_block + text[finish:]


replace_once(
    "        void refresh_active_target();\n        void clear_selection();\n",
    "        void refresh_active_target();\n        void clear_target_selection();\n        void clear_selection();\n",
    "declare target clear helper",
)

replace_between(
    "bool construction_workspace::poll_activity_input()\n{",
    "\nbool construction_workspace::target_is_adjacent",
    r'''bool construction_workspace::poll_activity_input()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return false;
    }

    // Auto-walk / ACT_BUILD owns the turn loop, but the editor remains visible.
    // UI interaction must never implicitly cancel the order.  Only the explicit
    // Pause control stops movement/work and hands control back to the editor.
    audit_camera_state( "activity-input" );
    synchronize_handoff_coordinates();

    const int previous_timeout = inp_mngr.get_timeout();
    inp_mngr.set_timeout( 0 );
    const input_event raw_input = inp_mngr.get_input_event( keyboard_mode::keycode );
    inp_mngr.set_timeout( previous_timeout );

    if( raw_input.type == input_event_t::timeout || raw_input.type == input_event_t::error ) {
        return false;
    }

    const int mouse_input = raw_input.type == input_event_t::mouse ?
                            raw_input.get_first_input() : 0;
    if( raw_input.type != input_event_t::mouse ||
        mouse_input != static_cast<int>( MouseInput::LeftButtonPressed ) ) {
        return false;
    }

    const std::optional<point> inspector_pos = input_event_window_position(
                raw_input, inspector_window );
    if( !inspector_pos ) {
        return false;
    }
    const std::optional<int> hit = primary_action.hit_test( *inspector_pos );
    const ui_action_entry *entry = hit ? primary_action.entry( *hit ) : nullptr;
    if( entry == nullptr || entry->id != "PAUSE" ) {
        return false;
    }

    // Pause is acted on at press time while the activity loop still owns input.
    // Consume its matching release when the editor re-enters so that physical
    // click cannot also activate whatever is beneath the button afterward.
    suppress_next_select_release = true;

    DebugLog( D_INFO, D_GAME )
            << "[CONSTRUCTION_HANDOFF_PAUSE] input_type=" << static_cast<int>( raw_input.type )
            << " input_code=" << raw_input.get_first_input()
            << " mouse_pos=(" << raw_input.mouse_pos.x << "," << raw_input.mouse_pos.y << ")"
            << " target_abs=" << ( handoff_target_abs ?
                                      handoff_target_abs->to_string_writable() : "none" )
            << " player_abs=" << you.pos_abs().to_string_writable()
            << " walking=" << you.has_destination()
            << " activity=" << ( you.activity ? you.activity.id().str() : "none" );

    const bool was_plan_order = plan_multi_activity_handoff;
    const std::optional<tripoint_abs_ms> paused_target = current_handoff_target_abs();
    if( you.has_destination() || you.has_destination_activity() ) {
        you.clear_destination();
    }
    if( you.activity ) {
        you.cancel_activity();
    }

    // If cancellation handed control to some other activity, do not open a modal
    // editor on top of it; the normal activity lifecycle will resolve that case.
    if( you.activity ) {
        return true;
    }

    g->wait_popup_reset();
    resume_activity_handoff();
    const bool unfinished = paused_target &&
                            here.partial_con_at( here.get_bub( *paused_target ) ) != nullptr;
    if( was_plan_order ) {
        transient_status = unfinished ?
                           _( "Plan construction paused.  Its unfinished work remains on the map." ) :
                           _( "Plan order paused.  Select a plan to review its current status." );
    } else {
        transient_status = operation == construction_operation::remove ?
                           unfinished ?
                           _( "Removal paused.  Continue the unfinished work or click another tile." ) :
                           _( "Walking paused before removal started." ) :
                           operation == construction_operation::place ?
                           unfinished ?
                           _( "Placement paused.  Continue the unfinished work or choose another tile." ) :
                           _( "Walking paused before placement started." ) :
                           unfinished ?
                           _( "Construction paused.  Move the ghost to another tile or continue the "
                              "unfinished work." ) :
                           _( "Walking paused before construction started.  No components were used." );
    }
    if( ui ) {
        ui->invalidate_ui();
    }
    return true;
}
''',
    "explicit pause input",
)

replace_once(
    '''void construction_workspace::clear_selection()
{
    selection_cleared_by_user = true;
    selected_group = construction_group_str_id::NULL_ID();
    selected_target.reset();
    selected_plan_abs.reset();
    hovered_target.reset();
    context_target.reset();
    context_anchor.reset();
    context_actions.clear();
    adjacent_resolutions.clear();
    resolution = construction_target_resolution();
    transient_status.clear();
    palette.clear_selection();
    rebuild_inspector();
}
''',
    '''void construction_workspace::clear_target_selection()
{
    selected_target.reset();
    selected_plan_abs.reset();
    hovered_target.reset();
    context_target.reset();
    context_anchor.reset();
    context_actions.clear();
    adjacent_resolutions.clear();
    resolution = construction_target_resolution();
    transient_status.clear();
    if( mode == construction_workspace_mode::plans ) {
        rebuild_plan_palette();
    } else {
        refresh_active_target();
    }
}

void construction_workspace::clear_selection()
{
    selection_cleared_by_user = true;
    selected_group = construction_group_str_id::NULL_ID();
    selected_target.reset();
    selected_plan_abs.reset();
    hovered_target.reset();
    context_target.reset();
    context_anchor.reset();
    context_actions.clear();
    adjacent_resolutions.clear();
    resolution = construction_target_resolution();
    transient_status.clear();
    palette.clear_selection();
    rebuild_inspector();
}
''',
    "target-only clear helper",
)

replace_once(
    '''    adjacent_resolutions.clear();
    if( ( operation == construction_operation::place ||
          operation == construction_operation::markers ) && !selected_group.is_null() ) {
        for( int x = -1; x <= 1; ++x ) {
            for( int y = -1; y <= 1; ++y ) {
                if( x == 0 && y == 0 ) {
                    continue;
                }
                const tripoint_bub_ms candidate = you.pos_bub() + tripoint_rel_ms( x, y, 0 );
                adjacent_resolutions.emplace_back( candidate, resolve_active_target( candidate ) );
            }
        }
    }
''',
    '''    // Validity follows the hovered/pinned tile.  Do not special-case Place
    // and Markers with an eight-tile halo that the other construction tools do
    // not show; the ghost and status marker are the common feedback model.
    adjacent_resolutions.clear();
''',
    "remove operation-specific adjacent halo",
)

replace_once(
    '''    add( operation == construction_operation::remove ? con->group->name() :
         construction_result_name( *con ) );
''',
    '''    const std::string action_name =
        ( operation == construction_operation::place ||
          operation == construction_operation::markers ) && con->post_terrain.empty() ?
        ( !con->ui_name.empty() ? con->ui_name.translated() : con->group->name() ) :
        construction_result_name( *con );
    add( operation == construction_operation::remove ? con->group->name() : action_name );
''',
    "player-facing special action name",
)

replace_once(
    '''        { ui_action_entry( _( "Plan" ), "MODE_PLAN", true,
                           mode == construction_workspace_mode::plan ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Plans" ), "MODE_PLANS", true,
                           mode == construction_workspace_mode::plans ), 0,
          ui_action_alignment::left }
''',
    '''        { ui_action_entry( _( "Add plans" ), "MODE_PLAN", true,
                           mode == construction_workspace_mode::plan ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Manage plans" ), "MODE_PLANS", true,
                           mode == construction_workspace_mode::plans ), 0,
          ui_action_alignment::left }
''',
    "disambiguate plan tabs",
)
replace_once('title = _( " Plans " );', 'title = _( " Manage plans " );', "plans palette title")
replace_once('title = _( " Plan catalog " );', 'title = _( " Add plans " );', "plan palette title")

replace_once(
    '''        if( work_running ) {
            const std::optional<tripoint_abs_ms> work_target = current_handoff_target_abs();
            const construction_plan *active_plan = work_target ? plan_at( *work_target ) : nullptr;
            const construction_plan *chosen = selected_plan();
            const std::string task_name = active_plan != nullptr ? active_plan->name :
                                          plan_multi_build_all ? _( "all plans" ) :
                                          chosen != nullptr ? chosen->name : _( "selected plan" );
            std::string label;
            if( you.has_destination() || you.has_destination_activity() ) {
                label = string_format( _( "Walking: %s" ), task_name );
            } else if( you.activity && you.activity.id() == ACT_BUILD ) {
                label = string_format( _( "Building: %s" ), task_name );
            } else {
                label = string_format( _( "Preparing: %s" ), task_name );
            }
            ui_action_entry current( label,
                                     plan_multi_build_all ? "BUILD_ALL_PLANS" :
                                     "BUILD_SELECTED_PLAN", true, true );
            current.tone = ui_action_tone::positive;
            actions.push_back( std::move( current ) );
            actions.emplace_back( _( "Pause" ), "PAUSE" );
        } else {
''',
    '''        if( work_running ) {
            // The running task is status, not a second executable button.  Pause
            // is the only gameplay action exposed while the handoff is active.
            actions.emplace_back( _( "Pause" ), "PAUSE" );
        } else {
''',
    "plans running action strip",
)

replace_between(
    '''    if( work_running ) {
        const construction *active = handoff_construction_id.is_valid() ?''',
    '''    if( show_context_actions ) {''',
    '''    if( show_context_actions ) {''',
    "remove running pseudo-action button",
)

replace_count(
    '''                const bool can_walk = operation == construction_operation::build ||
                                      operation == construction_operation::place ||
                                      operation == construction_operation::remove;
''',
    '''                const bool can_walk = operation == construction_operation::build ||
                                      operation == construction_operation::place ||
                                      operation == construction_operation::markers ||
                                      operation == construction_operation::remove;
''',
    2,
    "enable distant markers in inspector",
)

replace_once(
    '''                    const bool adjacent = selected_target && target_is_adjacent( *selected_target );
                    const bool enabled = decorate_ready && adjacent;
                    const std::string reason = !adjacent ? _( "Move adjacent to decorate this tile." ) :
                                               decorate_ready ? std::string() :
                                               _( "No decoration option currently meets its requirements." );
                    ui_action_entry decorate( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",
                                              enabled, false, reason );
''',
    '''                    bool enabled = decorate_ready;
                    std::string reason = decorate_ready ? std::string() :
                                         _( "No decoration option currently meets its requirements." );
                    if( selected_target && !target_is_adjacent( *selected_target ) ) {
                        const ret_val<void> reachable = can_reach_construction_target(
                                                            you, *selected_target );
                        enabled = decorate_ready && reachable.success();
                        reason = reachable.success() ? reason : reachable.str();
                    }
                    ui_action_entry decorate( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",
                                              enabled, false, reason );
''',
    "distant decorate inspector action",
)
replace_once(
    '''            if( selected_target && !target_is_adjacent( *selected_target ) ) {
                enabled = false;
                reason = _( "Move adjacent to use this tile action." );
            }
''',
    '''            if( selected_target && !target_is_adjacent( *selected_target ) ) {
                const ret_val<void> reachable = can_reach_construction_target(
                                                    you, *selected_target );
                enabled = action.resolution.ready() && reachable.success();
                reason = reachable.success() ? reason : reachable.str();
            }
''',
    "distant contextual inspector action",
)

replace_once(
    '''    if( ( inspect_mode || selection_missing ) && !resolution.unfinished ) {
        primary_action.clear();
    } else {
        build.tone = operation == construction_operation::remove ?
                     ui_action_tone::destructive : ui_action_tone::positive;
        ui_action_entry pause( _( "Pause" ), "PAUSE", work_running, false,
                               _( "Construction is already paused." ) );
        std::vector<ui_action_entry> actions = { build };
        if( work_running || resolution.unfinished ) {
            actions.push_back( std::move( pause ) );
        }
        primary_action.configure( inspector_window, point( 2, primary_action_y ), std::move( actions ),
                                  inspector_width - 4, 1 );
        primary_action.draw( inspector_window );
    }
''',
    '''    if( work_running ) {
        std::vector<ui_action_entry> actions = {
            ui_action_entry( _( "Pause" ), "PAUSE" )
        };
        primary_action.configure( inspector_window, point( 2, primary_action_y ),
                                  std::move( actions ), inspector_width - 4, 1 );
        primary_action.draw( inspector_window );
    } else if( ( inspect_mode || selection_missing ) && !resolution.unfinished ) {
        primary_action.clear();
    } else {
        build.tone = operation == construction_operation::remove ?
                     ui_action_tone::destructive : ui_action_tone::positive;
        std::vector<ui_action_entry> actions = { build };
        primary_action.configure( inspector_window, point( 2, primary_action_y ),
                                  std::move( actions ), inspector_width - 4, 1 );
        primary_action.draw( inspector_window );
    }
''',
    "explicit pause primary action",
)

replace_count(
    '_( "Walking to the removal site… click or press a key to pause." )',
    '_( "Walking to the removal site… choose Pause to stop." )',
    1,
    "remove walking footer",
)
replace_count(
    '_( "Walking to the placement site… click or press a key to pause." )',
    '_( "Walking to the placement site… choose Pause to stop." )',
    1,
    "place walking footer",
)
replace_count(
    '_( "Walking to the construction site… click or press a key to pause." )',
    '_( "Walking to the construction site… choose Pause to stop." )',
    1,
    "build walking footer",
)
replace_count('_( "Removing… click or press a key to pause." )', '_( "Removing… choose Pause to stop." )', 1, "remove footer")
replace_count('_( "Placing… click or press a key to pause." )', '_( "Placing… choose Pause to stop." )', 1, "place footer")
replace_count('_( "Marking… click or press a key to pause." )', '_( "Marking… choose Pause to stop." )', 1, "marker footer")
replace_count('_( "Building… click or press a key to pause." )', '_( "Building… choose Pause to stop." )', 1, "build footer")
replace_once(
    '''    if( ( operation == construction_operation::remove || !selected_group.is_null() ) &&
        !selected_target ) {
        return placement_prompt();
    }
''',
    '''    if( operation == construction_operation::remove || !selected_group.is_null() ) {
        return placement_prompt();
    }
''',
    "tool-centric footer",
)

replace_between(
    "void construction_workspace::draw_world_overlay() const\n{",
    "\nvoid construction_workspace::draw( ui_adaptor &ui )",
    r'''void construction_workspace::draw_world_overlay() const
{
    if( mode == construction_workspace_mode::plan ||
        mode == construction_workspace_mode::plans ) {
        for( const construction_plan &plan : nearby_plans ) {
            const tripoint_bub_ms position = here.get_bub( plan.position );
            if( !here.inbounds( position ) ) {
                continue;
            }
            if( plan.status != construction_plan_status::completed &&
                plan.desired.is_valid() && !plan.desired.obj().post_terrain.empty() ) {
                const construction &desired = plan.desired.obj();
                if( desired.post_is_furniture ) {
                    viewport.draw_map_plan_furniture_overlay(
                        position, furn_str_id( desired.post_terrain ) );
                } else {
                    viewport.draw_map_plan_terrain_overlay(
                        position, ter_str_id( desired.post_terrain ) );
                }
            }
            if( const partial_con *partial = here.partial_con_at( position ) ) {
                viewport.draw_map_progress_bar(
                    position, std::clamp( partial->counter / 10000000.0f, 0.0f, 1.0f ) );
            }
            const std::pair<std::string, nc_color> marker =
                construction_plan_marker( plan.status );
            viewport.draw_map_marker( position, marker.first, marker.second );
        }
        if( mode == construction_workspace_mode::plans ) {
            const std::optional<tripoint_abs_ms> cursor = activity_handoff ?
                    current_handoff_target_abs() : selected_plan_abs;
            if( cursor ) {
                viewport.draw_map_cursor( here.get_bub( *cursor ) );
            }
            return;
        }
    }

    const auto draw_status = [&]( const tripoint_bub_ms & position,
    const construction_target_resolution & state ) {
        std::string symbol = "×";
        nc_color color = c_light_red;
        if( state.unfinished && state.ready() ) {
            symbol = "▣";
            color = c_light_blue;
        } else if( state.status == construction_target_status::ready ) {
            symbol = "✓";
            color = c_light_green;
        } else if( state.status == construction_target_status::unavailable_requirements ) {
            symbol = "!";
            color = c_yellow;
        }
#if defined(TILES)
        if( operation != construction_operation::remove ) {
            viewport.draw_map_highlight( position );
        }
#else
        here.drawsq( g->w_terrain, position,
                     drawsq_params().highlight( true ).show_items( true )
                     .center( you.pos_bub() + you.view_offset ) );
#endif
        viewport.draw_map_marker( position, symbol, color );
    };

    const bool tool_preview_active = !activity_handoff &&
                                     ( mode == construction_workspace_mode::plan ||
                                       operation == construction_operation::remove ||
                                       !selected_group.is_null() );
    const std::optional<tripoint_bub_ms> target =
        tool_preview_active && hovered_target ? hovered_target : displayed_target();
    if( !target ) {
        return;
    }

    const construction_target_resolution target_state =
        selected_target && *target != *selected_target ? resolve_active_target( *target ) : resolution;

    if( mode == construction_workspace_mode::build && selected_group.is_null() &&
        !target_state.unfinished ) {
        viewport.draw_map_highlight( *target );
        if( !context_actions.empty() ) {
            viewport.draw_map_marker( *target, "•", c_light_cyan );
        }
        if( selected_target ) {
            viewport.draw_map_cursor( *selected_target );
        }
        return;
    }

    const construction *con = target_state.id.is_valid() ? &target_state.id.obj() : nullptr;
    if( operation == construction_operation::remove ) {
        // Removal previews the existing visible object.  Keep its world layers
        // intact and tint the target rather than replacing it with exposed terrain.
        viewport.draw_map_removal_overlay( *target );
    } else if( con ) {
        if( !con->post_terrain.empty() ) {
            if( con->post_is_furniture ) {
                viewport.draw_map_furniture_override( *target, furn_str_id( con->post_terrain ) );
            } else {
                viewport.draw_map_terrain_override( *target, ter_str_id( con->post_terrain ) );
            }
        } else if( operation == construction_operation::place ) {
            const std::optional<construction_item_preview> preview =
                construction_place_preview( *con, you );
            if( preview ) {
                if( preview->appliance ) {
                    viewport.draw_map_vpart_override( *target, preview->appliance );
                } else if( !preview->item.is_null() ) {
                    viewport.draw_map_item_override( *target, preview->item );
                }
            }
        } else if( operation == construction_operation::markers ) {
            // Marker constructions often have no terrain result sprite.  Give
            // them the same cursor-owned ghost semantics as the other tools.
            viewport.draw_map_marker( *target, "◇", c_light_cyan );
        }
    }

    if( const partial_con *partial = here.partial_con_at( *target ) ) {
        viewport.draw_map_progress_bar( *target,
                                        std::clamp( partial->counter / 10000000.0f, 0.0f, 1.0f ) );
    }
    draw_status( *target, target_state );

    // A pinned failed/unfinished target remains visible for diagnosis while the
    // active ghost follows the mouse independently to the next candidate tile.
    if( selected_target && *selected_target != *target ) {
        const construction_target_resolution selected_state =
            resolve_active_target( *selected_target );
        draw_status( *selected_target, selected_state );
        if( const partial_con *partial = here.partial_con_at( *selected_target ) ) {
            viewport.draw_map_progress_bar(
                *selected_target, std::clamp( partial->counter / 10000000.0f, 0.0f, 1.0f ) );
        }
    }
    if( selected_target ) {
        viewport.draw_map_cursor( *selected_target );
    }
}
''',
    "hover-owned ghost preview",
)

replace_once(
    '''    focus = next;
    transient_status.clear();
    if( compact ) {
''',
    '''    focus = next;
    if( compact ) {
''',
    "keep diagnostic status across focus changes",
)

replace_once(
    '''    if( next == construction_workspace_mode::plans ) {
        selected_group = construction_group_str_id::NULL_ID();
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
    } else if( previous_mode == construction_workspace_mode::plans && next_catalog ) {
        selected_group = catalog_group_before_plans;
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
    } else if( !( previous_catalog && next_catalog ) ) {
        selected_group = construction_group_str_id::NULL_ID();
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
        section_filter.reset();
        selection_cleared_by_user = false;
    }
''',
    '''    if( next == construction_workspace_mode::plans ) {
        selected_group = construction_group_str_id::NULL_ID();
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
        context_anchor.reset();
    } else if( previous_mode == construction_workspace_mode::plans && next_catalog ) {
        selected_group = catalog_group_before_plans;
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
        context_anchor.reset();
    } else if( previous_catalog && next_catalog ) {
        // Build and Add plans may share the catalog choice, but a world target
        // must never silently change meaning when the operation changes.
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
        context_anchor.reset();
    } else {
        selected_group = construction_group_str_id::NULL_ID();
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
        context_anchor.reset();
        section_filter.reset();
        selection_cleared_by_user = false;
    }
''',
    "clear targets across mode semantics",
)

replace_between(
    "void construction_workspace::open_context_menu( const point &anchor,\n        const tripoint_bub_ms &target )\n{",
    "\nvoid construction_workspace::open_context_intent_menu",
    r'''void construction_workspace::open_context_menu( const point &anchor,
        const tripoint_bub_ms &target )
{
    context_target = target;
    context_anchor = anchor;
    const tripoint_abs_ms target_abs = here.get_abs( target );
    const construction_plan *existing_plan = plan_at( target_abs );

    if( mode == construction_workspace_mode::plan ) {
        const construction_target_resolution target_resolution = resolve_active_target( target );
        const bool plannable = !selected_group.is_null() &&
                               !target_resolution.unfinished &&
                               target_resolution.has_construction() &&
                               target_resolution.status !=
                               construction_target_status::invalid_location;
        std::vector<ui_dropdown_entry> entries = {
            ui_dropdown_entry( _( "Inspect tile" ), "SELECT_TILE" )
        };
        if( existing_plan != nullptr && !selected_group.is_null() &&
            existing_plan->group != selected_group ) {
            entries.emplace_back( _( "Replace plan" ), "PLAN_HERE", plannable, false,
                                  plannable ? std::string() : target_resolution.reason );
        }
        if( existing_plan != nullptr ) {
            entries.emplace_back( _( "Remove plan" ), "REMOVE_PLAN_HERE" );
        }
        entries.emplace_back( _( "Center view here" ), "CENTER" );
        entries.emplace_back( _( "Clear target" ), "CLEAR_TARGET",
                              selected_target.has_value() || selected_plan_abs.has_value() );
        context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
        return;
    }

    if( mode == construction_workspace_mode::plans ) {
        std::vector<ui_dropdown_entry> entries;
        entries.emplace_back( existing_plan == nullptr ? _( "No plan here" ) : _( "Select plan" ),
                              "SELECT_PLAN", existing_plan != nullptr, false,
                              _( "There is no active construction plan on this tile." ) );
        if( existing_plan != nullptr ) {
            entries.emplace_back( _( "Build this plan" ), "BUILD_SELECTED_PLAN",
                                  construction_plan_can_execute( existing_plan->status ), false,
                                  existing_plan->reason );
            entries.emplace_back( _( "Remove plan" ), "REMOVE_PLAN_HERE" );
        }
        entries.emplace_back( _( "Center view here" ), "CENTER" );
        context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
        return;
    }

    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Inspect tile" ), "SELECT_TILE" )
    };
    if( mode == construction_workspace_mode::build ) {
        std::vector<ui_dropdown_entry> contextual_entries;
        bool has_decorate = false;
        bool decorate_ready = false;
        std::string decorate_reason;
        for( const construction_context_action &action :
             resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {
            if( action.intent == construction_ui_intent::decorate ) {
                has_decorate = true;
                decorate_ready = decorate_ready || action.resolution.ready();
                if( decorate_reason.empty() && !action.resolution.ready() ) {
                    decorate_reason = action.resolution.reason;
                }
                continue;
            }
            bool enabled = action.resolution.ready();
            std::string reason = action.resolution.reason;
            if( !target_is_adjacent( target ) ) {
                const ret_val<void> reachable = can_reach_construction_target( you, target );
                enabled = action.resolution.ready() && reachable.success();
                reason = reachable.success() ? reason : reachable.str();
            }
            contextual_entries.emplace_back( contextual_action_label( action ),
                                               contextual_action_id( action ),
                                               enabled, false, reason );
        }
        if( has_decorate ) {
            bool enabled = decorate_ready;
            std::string reason = decorate_ready ? std::string() : decorate_reason;
            if( !target_is_adjacent( target ) ) {
                const ret_val<void> reachable = can_reach_construction_target( you, target );
                enabled = decorate_ready && reachable.success();
                reason = reachable.success() ? reason : reachable.str();
            }
            contextual_entries.emplace_back( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",
                                               enabled, false, reason );
        }
        entries.insert( entries.end(), contextual_entries.begin(), contextual_entries.end() );
    }
    entries.emplace_back( _( "Center view here" ), "CENTER" );
    entries.emplace_back( _( "Clear target" ), "CLEAR_TARGET", selected_target.has_value() );
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
}
''',
    "non-duplicated context menus",
)

replace_between(
    "void construction_workspace::open_context_intent_menu( const point &anchor,\n        const tripoint_bub_ms &target, const construction_ui_intent intent )\n{",
    "\nbool construction_workspace::execute_context_action",
    r'''void construction_workspace::open_context_intent_menu( const point &anchor,
        const tripoint_bub_ms &target, const construction_ui_intent intent )
{
    context_target = target;
    context_anchor = anchor;
    std::vector<ui_dropdown_entry> entries;
    for( const construction_context_action &action :
         resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {
        if( action.intent != intent ) {
            continue;
        }
        bool enabled = action.resolution.ready();
        std::string reason = action.resolution.reason;
        if( !target_is_adjacent( target ) ) {
            const ret_val<void> reachable = can_reach_construction_target( you, target );
            enabled = action.resolution.ready() && reachable.success();
            reason = reachable.success() ? reason : reachable.str();
        }
        entries.emplace_back( contextual_action_label( action ), contextual_action_id( action ),
                              enabled, false, reason );
    }
    if( entries.empty() ) {
        entries.emplace_back( _( "No applicable actions" ), "NO_ACTION", false, false,
                              _( "This tile has no applicable action in that group." ) );
    }
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
}
''',
    "distant grouped contextual actions",
)

replace_once(
    '''    } else if( id == "CLEAR" ) {
        clear_selection();
''',
    '''    } else if( id == "CLEAR_TARGET" ) {
        clear_target_selection();
''',
    "context clear target only",
)

replace_once(
    '''    const bool can_walk = operation == construction_operation::build ||
                          operation == construction_operation::place ||
                          operation == construction_operation::remove;
    if( !target_is_adjacent( target ) && !can_walk ) {
        transient_status = _( "Distant marker orders are not implemented yet." );
        return false;
    }
''',
    '''    const bool can_walk = operation == construction_operation::build ||
                          operation == construction_operation::place ||
                          operation == construction_operation::markers ||
                          operation == construction_operation::remove;
''',
    "enable distant marker request",
)

replace_once(
    '''    if( !target_is_adjacent( target ) ) {
        transient_status = _( "Move adjacent to use this tile action." );
        return false;
    }
''',
    '''    if( !target_is_adjacent( target ) ) {
        const ret_val<void> reachable = can_reach_construction_target( you, target );
        if( !reachable.success() ) {
            transient_status = reachable.str();
            return false;
        }
    }
''',
    "walk to contextual action",
)

replace_between(
    "bool construction_workspace::handle_viewport_action(\n    const ui_world_viewport_action &action, ui_adaptor &ui )\n{",
    "\nbool construction_workspace::handle_pointer",
    r'''bool construction_workspace::handle_viewport_action(
    const ui_world_viewport_action &action, ui_adaptor &ui )
{
    switch( action.type ) {
        case ui_world_viewport_action_type::hover:
            if( hovered_target == action.world_position ) {
                return false;
            }
            hovered_target = action.world_position;
            if( !selected_target ) {
                refresh_active_target();
            }
            return true;
        case ui_world_viewport_action_type::select:
            if( action.world_position ) {
                if( mode == construction_workspace_mode::plans ) {
                    const tripoint_abs_ms position = here.get_abs( *action.world_position );
                    if( plan_at( position ) != nullptr ) {
                        transient_status.clear();
                        select_plan( position, false );
                    } else {
                        selected_plan_abs.reset();
                        selected_target.reset();
                        hovered_target.reset();
                        transient_status = _( "There is no construction plan on that tile." );
                    }
                    rebuild_plan_palette();
                    set_focus( workspace_focus::viewport, ui );
                    return true;
                }

                transient_status.clear();
                selected_target = action.world_position;
                hovered_target.reset();
                refresh_active_target();
                set_focus( workspace_focus::viewport, ui );
                if( mode == construction_workspace_mode::plan ) {
                    const construction_plan *existing = plan_at(
                                here.get_abs( *action.world_position ) );
                    if( existing == nullptr && !selected_group.is_null() ) {
                        request_plan( *action.world_position );
                    }
                } else if( ( mode == construction_workspace_mode::build &&
                             ( !selected_group.is_null() || resolution.unfinished ) ) ||
                           ( operation == construction_operation::place &&
                             !selected_group.is_null() ) ||
                           ( operation == construction_operation::markers &&
                             !selected_group.is_null() ) ||
                           operation == construction_operation::remove ) {
                    // LMB is the canonical primary action.  If the order cannot
                    // start, keep this tile pinned so the inspector retains the
                    // exact reason instead of collapsing back into hover state.
                    request_action( *action.world_position );
                }
            }
            return true;
        case ui_world_viewport_action_type::context:
            if( action.world_position && action.position ) {
                open_context_menu( *action.position, *action.world_position );
                set_focus( workspace_focus::viewport, ui );
            }
            return true;
        case ui_world_viewport_action_type::pan_start:
        case ui_world_viewport_action_type::pan_move:
        case ui_world_viewport_action_type::pan_end:
        case ui_world_viewport_action_type::zoom_in:
        case ui_world_viewport_action_type::zoom_out:
            audit_camera_state( "pointer-camera", true );
            return true;
        case ui_world_viewport_action_type::handled:
            return true;
        case ui_world_viewport_action_type::ignored:
            return false;
    }
    return false;
}
''',
    "canonical viewport click path",
)

replace_once(
    '''                    select_plan( *found, true );
                    rebuild_plan_palette();
                    inspector.model().scroll_to_start();
                    set_focus( workspace_focus::inspector, ui );
''',
    '''                    select_plan( *found, true );
                    rebuild_plan_palette();
                    inspector.model().scroll_to_start();
                    if( list_result.type == ui_action_result_type::activated ) {
                        set_focus( workspace_focus::inspector, ui );
                    }
''',
    "plans compact mouse focus",
)

replace_once(
    '''            selected_group = construction_group_str_id( list_result.entry->id );
            selection_cleared_by_user = false;
            selected_target.reset();
            context_target.reset();
            context_anchor.reset();
''',
    '''            selected_group = construction_group_str_id( list_result.entry->id );
            selection_cleared_by_user = false;
            selected_target.reset();
            hovered_target.reset();
            context_target.reset();
            context_anchor.reset();
''',
    "mouse catalog clears stale hover",
)
replace_once(
    '''            refresh_active_target();
            inspector.model().scroll_to_start();
            set_focus( workspace_focus::viewport, ui );
            transient_status = placement_prompt();
            return true;
''',
    '''            refresh_active_target();
            inspector.model().scroll_to_start();
            if( list_result.type == ui_action_result_type::activated ) {
                set_focus( workspace_focus::viewport, ui );
            }
            transient_status = placement_prompt();
            return true;
''',
    "catalog compact mouse focus",
)

replace_once(
    '''    if( action != "MOUSE_MOVE" ) {
        if( !transient_status.empty() ) {
            ui.invalidate_ui();
        }
        transient_status.clear();
    }
''',
    '''    // Diagnostic/action status persists until a meaningful state change
    // replaces it.  Scrolling, focus traversal and other harmless input should
    // not erase the explanation the user is trying to inspect.
''',
    "persistent diagnostic status",
)

replace_once(
    '''    if( action == "QUIT" ) {
        if( category_menu.is_open() ) {
            category_menu.close();
        } else if( context_menu.is_open() ) {
            context_menu.close();
        } else if( !selected_group.is_null() || selected_target || hovered_target || context_target ) {
            clear_selection();
        } else {
            exit_requested = true;
        }
        return true;
    }
''',
    '''    if( action == "QUIT" ) {
        if( category_menu.is_open() ) {
            category_menu.close();
        } else if( context_menu.is_open() ) {
            context_menu.close();
        } else if( selected_target || selected_plan_abs || context_target ) {
            clear_target_selection();
        } else if( !selected_group.is_null() ) {
            clear_selection();
        } else {
            // Hover is transient preview state and never consumes an extra Esc.
            hovered_target.reset();
            exit_requested = true;
        }
        return true;
    }
''',
    "hierarchical escape",
)

replace_once(
    '''            selected_group = construction_group_str_id( result.entry->id );
            selection_cleared_by_user = false;
            selected_target.reset();
            context_target.reset();
            context_anchor.reset();
''',
    '''            selected_group = construction_group_str_id( result.entry->id );
            selection_cleared_by_user = false;
            selected_target.reset();
            hovered_target.reset();
            context_target.reset();
            context_anchor.reset();
''',
    "keyboard catalog clears stale hover",
)

replace_once(
    '''        if( direction ) {
            viewport.move_map_camera( you, *direction );
            audit_camera_state( "keyboard-pan", true );
            selected_target = viewport.map_camera_center( you );
            hovered_target.reset();
            refresh_active_target();
            return true;
        }
''',
    '''        if( direction ) {
            viewport.move_map_camera( you, *direction );
            audit_camera_state( "keyboard-pan", true );
            hovered_target = viewport.map_camera_center( you );
            if( !selected_target ) {
                refresh_active_target();
            }
            return true;
        }
''',
    "keyboard pan previews without pinning",
)

SRC.write_text(text, encoding="utf-8")

# Keep the design document aligned with the now-canonical one-click tool model.
doc = DOC.read_text(encoding="utf-8")
old = '''### 13.1 Selecting a target

A normal viewport click:

- selects the target;
- updates the inspector;
- does **not** move the character;
- does **not** consume components;
- does **not** start construction automatically.

Simple inspection must never accidentally issue a travel order.
'''
new = '''### 13.1 Selecting a target

With an active Build result, a normal viewport click is the primary construction command:

- validate the clicked tile;
- start immediately when the character can work there;
- otherwise issue the normal route-to-adjacent order and start automatically after arrival;
- if the order cannot start, keep the tile pinned and show the exact reason in the inspector.

Without an active Build result, a viewport click pins the tile for inspection only.  Right-click
**Inspect tile** provides the same deliberate inspection path without duplicating the primary build
command in the context menu.
'''
if doc.count(old) != 1:
    raise RuntimeError(f"doc build click contract: expected one match, found {doc.count(old)}")
doc = doc.replace(old, new, 1)
old = '''### 30.1 Simple click

Select/inspect target only.

### 30.2 Explicit action

`Build here`, `Go there and build`, or `Execute plans` issues a gameplay order.
'''
new = '''### 30.1 Simple click

With an active Build / Place / Remove / Marker tool, LMB issues that tool's primary action.  Distant
orders route to the work site and start automatically.  If execution fails, the clicked tile stays
pinned so the inspector can explain why.  In neutral Build inspection mode, LMB only pins/inspects.

### 30.2 Inspector action

A deliberately pinned target may expose the same primary action in the inspector.  This is the
inspection/diagnostic path, not a required second confirmation.  RMB is reserved for inspection,
alternate contextual work, plan-local actions, centering, and target clearing.
'''
if doc.count(old) != 1:
    raise RuntimeError(f"doc map interaction contract: expected one match, found {doc.count(old)}")
doc = doc.replace(old, new, 1)
DOC.write_text(doc, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Unify construction workspace interactions\n", encoding="utf-8"
)
