from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# veh_interact.h
# -----------------------------------------------------------------------------
p = Path("src/veh_interact.h")
s = p.read_text()

s = replace_once(
    s,
    "        /** Restore the untouched retained editor after a distraction query continues the activity. */\n"
    "        static void restore_persistent_editor_after_query();\n",
    "        /** Restore the untouched retained editor after a distraction query continues the activity. */\n"
    "        static void restore_persistent_editor_after_query();\n"
    "        /** Add a completed, player-meaningful action to the current vehicle workspace history. */\n"
    "        static void record_editor_action( vehicle &veh, const std::string &text );\n"
    "        /** Stage an action whose mutation finishes outside the editor input loop. */\n"
    "        static void stage_editor_action( vehicle &veh, const std::string &text );\n"
    "        /** Commit/clear the currently staged action.  expected_vehicle guards siphon re-entry. */\n"
    "        static void commit_staged_editor_action( vehicle *expected_vehicle = nullptr );\n"
    "        static void clear_staged_editor_action();\n",
    "public action-history API",
)

s = replace_once(
    s,
    "        std::vector<int> refill_part_indices;\n"
    "        std::vector<item_location> refill_targets;\n",
    "        std::vector<int> refill_part_indices;\n"
    "        std::vector<item_location> refill_targets;\n"
    "        bool refill_quick = false;\n",
    "refill quick marker",
)

s = replace_once(
    s,
    "        catacurses::window w_msg;\n"
    "        catacurses::window w_disp;\n",
    "        catacurses::window w_msg;\n"
    "        catacurses::window w_disp;\n"
    "        catacurses::window w_action_history;\n",
    "action-history window member",
)

s = replace_once(
    s,
    "        bool queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan );\n",
    "        bool queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan,\n"
    "                                bool quick = false );\n",
    "queue refill signature",
)

s = replace_once(
    s,
    "        void display_grid();\n"
    "        void display_veh( map &here );\n",
    "        void display_grid();\n"
    "        void display_action_history();\n"
    "        void display_veh( map &here );\n",
    "action-history display declaration",
)

p.write_text(s)


# -----------------------------------------------------------------------------
# veh_interact.cpp
# -----------------------------------------------------------------------------
p = Path("src/veh_interact.cpp")
s = p.read_text()

s = replace_once(
    s,
    "#include <cstdlib>\n#include <functional>\n",
    "#include <cstdlib>\n#include <deque>\n#include <functional>\n",
    "deque include",
)

s = replace_once(
    s,
    "static int vehicle_editor_view_mode_latched = 0;\n\n"
    "veh_interact *veh_interact::persistent_editor = nullptr;\n",
    "static int vehicle_editor_view_mode_latched = 0;\n"
    "static constexpr int vehicle_editor_action_history_height = 5;\n"
    "static vehicle *vehicle_editor_history_vehicle = nullptr;\n"
    "static std::deque<std::string> vehicle_editor_action_history;\n"
    "static vehicle *vehicle_editor_staged_vehicle = nullptr;\n"
    "static std::string vehicle_editor_staged_action;\n\n"
    "veh_interact *veh_interact::persistent_editor = nullptr;\n\n"
    "void veh_interact::record_editor_action( vehicle &history_veh, const std::string &text )\n"
    "{\n"
    "    if( text.empty() ) {\n"
    "        return;\n"
    "    }\n"
    "    if( vehicle_editor_history_vehicle != &history_veh ) {\n"
    "        vehicle_editor_history_vehicle = &history_veh;\n"
    "        vehicle_editor_action_history.clear();\n"
    "    }\n"
    "    vehicle_editor_action_history.push_back( text );\n"
    "    while( vehicle_editor_action_history.size() > 3 ) {\n"
    "        vehicle_editor_action_history.pop_front();\n"
    "    }\n"
    "}\n\n"
    "void veh_interact::stage_editor_action( vehicle &history_veh, const std::string &text )\n"
    "{\n"
    "    vehicle_editor_staged_vehicle = &history_veh;\n"
    "    vehicle_editor_staged_action = text;\n"
    "}\n\n"
    "void veh_interact::commit_staged_editor_action( vehicle *expected_vehicle )\n"
    "{\n"
    "    if( vehicle_editor_staged_vehicle == nullptr || vehicle_editor_staged_action.empty() ) {\n"
    "        clear_staged_editor_action();\n"
    "        return;\n"
    "    }\n"
    "    if( expected_vehicle != nullptr && expected_vehicle != vehicle_editor_staged_vehicle ) {\n"
    "        clear_staged_editor_action();\n"
    "        return;\n"
    "    }\n"
    "    if( vehicle_editor_history_vehicle != vehicle_editor_staged_vehicle ) {\n"
    "        vehicle_editor_history_vehicle = vehicle_editor_staged_vehicle;\n"
    "        vehicle_editor_action_history.clear();\n"
    "    }\n"
    "    vehicle_editor_action_history.push_back( vehicle_editor_staged_action );\n"
    "    while( vehicle_editor_action_history.size() > 3 ) {\n"
    "        vehicle_editor_action_history.pop_front();\n"
    "    }\n"
    "    clear_staged_editor_action();\n"
    "}\n\n"
    "void veh_interact::clear_staged_editor_action()\n"
    "{\n"
    "    vehicle_editor_staged_vehicle = nullptr;\n"
    "    vehicle_editor_staged_action.clear();\n"
    "}\n",
    "action-history state and API",
)

s = replace_once(
    s,
    "    res.str_values.emplace_back( sel_cmd == 'f' && !refill_part_indices.empty() ?\n"
    "                                 \"vehicle_refill_batch\" : \"\" );\n",
    "    res.str_values.emplace_back( sel_cmd == 'f' && !refill_part_indices.empty() ?\n"
    "                                 \"vehicle_refill_batch\" : \"\" );\n"
    "    res.str_values.emplace_back( \"vehicle_editor_history\" );\n"
    "    res.str_values.emplace_back( sel_cmd == 'f' && refill_quick ?\n"
    "                                 \"vehicle_refill_quick\" : \"\" );\n",
    "serialize editor history marker",
)

s = replace_once(
    s,
    "    active_editor_view_mode = static_cast<editor_view_mode>(\n"
    "                                  std::clamp( vehicle_editor_view_mode_latched, 0, 2 ) );\n\n"
    "    count_durability();\n",
    "    active_editor_view_mode = static_cast<editor_view_mode>(\n"
    "                                  std::clamp( vehicle_editor_view_mode_latched, 0, 2 ) );\n\n"
    "    if( vehicle_editor_history_vehicle != &veh ) {\n"
    "        vehicle_editor_history_vehicle = &veh;\n"
    "        vehicle_editor_action_history.clear();\n"
    "        clear_staged_editor_action();\n"
    "    }\n\n"
    "    count_durability();\n",
    "constructor history ownership",
)

s = replace_once(
    s,
    "    page_size = grid_h - ( mode_h + stats_h + name_h ) - 2;\n"
    "    const int pane_y = grid.y + mode_h + 1;\n",
    "    page_size = grid_h - ( mode_h + stats_h + name_h ) - 2;\n"
    "    const int pane_y = grid.y + mode_h + 1;\n"
    "    const int action_history_h = std::min( vehicle_editor_action_history_height,\n"
    "                                      std::max( 1, page_size - 4 ) );\n"
    "    const int editor_page_h = std::max( 1, page_size - action_history_h );\n",
    "history geometry",
)

s = replace_once(
    s,
    "    w_disp = catacurses::newwin( page_size, disp_w, point( grid.x, pane_y ) );\n",
    "    w_disp = catacurses::newwin( editor_page_h, disp_w, point( grid.x, pane_y ) );\n"
    "    w_action_history = catacurses::newwin( action_history_h, disp_w,\n"
    "                       point( grid.x, pane_y + editor_page_h ) );\n",
    "history window allocation",
)

s = replace_once(
    s,
    "    const int preview_h = std::max( 1, page_size - content_top );\n",
    "    const int preview_h = std::max( 1, editor_page_h - content_top );\n",
    "live-preview height",
)

s = replace_once(
    s,
    "            display_stats( here );\n"
    "            display_veh( here );\n",
    "            display_stats( here );\n"
    "            display_veh( here );\n"
    "            display_action_history();\n",
    "history redraw hook",
)

history_display = '''void veh_interact::display_action_history()\n{\n    if( !w_action_history ) {\n        return;\n    }\n    werase( w_action_history );\n    const int width = getmaxx( w_action_history );\n    const int height = getmaxy( w_action_history );\n    if( width <= 0 || height <= 0 ) {\n        return;\n    }\n\n    draw_border( w_action_history, c_dark_gray );\n    trim_and_print( w_action_history, point( 2, 0 ), std::max( 1, width - 4 ), c_light_gray,\n                    _( "Workspace — recent actions" ) );\n\n    const int rows = std::min( 3, std::max( 0, height - 2 ) );\n    if( vehicle_editor_history_vehicle != veh || vehicle_editor_action_history.empty() ) {\n        if( rows > 0 ) {\n            trim_and_print( w_action_history, point( 2, 1 ), std::max( 1, width - 4 ), c_dark_gray,\n                            _( "No completed actions yet." ) );\n        }\n    } else {\n        const int first = std::max( 0, static_cast<int>( vehicle_editor_action_history.size() ) - rows );\n        for( int row = 0; row < rows && first + row < static_cast<int>( vehicle_editor_action_history.size() ); ++row ) {\n            trim_and_print( w_action_history, point( 2, row + 1 ), std::max( 1, width - 4 ),\n                            c_light_gray, vehicle_editor_action_history[first + row] );\n        }\n    }\n    wnoutrefresh( w_action_history );\n}\n\n'''

s = replace_once(
    s,
    "void veh_interact::display_grid()\n{\n",
    history_display + "void veh_interact::display_grid()\n{\n",
    "history display function",
)

# Mend only commits after ACT_MEND_ITEM reports success.
s = replace_once(
    s,
    "    player_character.assign_activity( ACT_MEND_ITEM, to_moves<int>( option.time_to_fix ) );\n"
    "    player_character.activity.name = option.fault.str();\n"
    "    player_character.activity.str_values.emplace_back( option.fix.str() );\n",
    "    stage_editor_action( *veh, string_format( _( \"Mended %1$s: %2$s\" ),\n"
    "                         editor_part_display_name( part ), option.fix->name.translated() ) );\n"
    "    player_character.assign_activity( ACT_MEND_ITEM, to_moves<int>( option.time_to_fix ) );\n"
    "    player_character.activity.name = option.fault.str();\n"
    "    player_character.activity.str_values.emplace_back( option.fix.str() );\n"
    "    player_character.activity.str_values.emplace_back( \"vehicle_editor_history\" );\n",
    "mend staged history",
)

# Reshape logs only committed changes, not previews/clicks.
s = replace_once(
    s,
    "    reshape_info->committed_variant = part.variant;\n"
    "    reshape_info->double_click.reset();\n"
    "    msg.reset();\n"
    "    return true;\n"
    "}\n\n"
    "bool veh_interact::handle_reshape_mouse",
    "    const std::string previous_variant = reshape_info->committed_variant;\n"
    "    reshape_info->committed_variant = part.variant;\n"
    "    if( previous_variant != part.variant ) {\n"
    "        record_editor_action( *veh, string_format( _( \"Reshaped %s\" ),\n"
    "                              editor_part_display_name( part ) ) );\n"
    "    }\n"
    "    reshape_info->double_click.reset();\n"
    "    msg.reset();\n"
    "    return true;\n"
    "}\n\n"
    "bool veh_interact::handle_reshape_mouse",
    "reshape committed history",
)

# Relabel logs only actual label mutations.
s = replace_once(
    s,
    "        vpart_position( *veh, info.part_indices.front() ).set_label( info.draft );\n"
    "        info.status = info.draft.empty() ? _( \"Position label removed.\" ) :\n"
    "                      _( \"Position label applied.\" );\n",
    "        vpart_position position( *veh, info.part_indices.front() );\n"
    "        const std::string previous = position.get_label().value_or( \"\" );\n"
    "        position.set_label( info.draft );\n"
    "        info.status = info.draft.empty() ? _( \"Position label removed.\" ) :\n"
    "                      _( \"Position label applied.\" );\n"
    "        if( previous != info.draft ) {\n"
    "            record_editor_action( *veh, info.draft.empty() ?\n"
    "                                  string_format( _( \"Removed label from position (%+d,%+d)\" ),\n"
    "                                                 info.mount.x(), info.mount.y() ) :\n"
    "                                  string_format( _( \"Labeled position (%+d,%+d): %s\" ),\n"
    "                                                 info.mount.x(), info.mount.y(), info.draft ) );\n"
    "        }\n",
    "position relabel history",
)

s = replace_once(
    s,
    "        veh->part( info.target_part ).set_label( info.draft );\n"
    "        info.status = info.draft.empty() ? _( \"Part label removed.\" ) : _( \"Part label applied.\" );\n",
    "        vehicle_part &part = veh->part( info.target_part );\n"
    "        const std::string previous = part.get_label().value_or( \"\" );\n"
    "        const std::string part_name = part.name( false );\n"
    "        part.set_label( info.draft );\n"
    "        info.status = info.draft.empty() ? _( \"Part label removed.\" ) : _( \"Part label applied.\" );\n"
    "        if( previous != info.draft ) {\n"
    "            record_editor_action( *veh, info.draft.empty() ?\n"
    "                                  string_format( _( \"Removed label from %s\" ), part_name ) :\n"
    "                                  string_format( _( \"Labeled %1$s: %2$s\" ), part_name, info.draft ) );\n"
    "        }\n",
    "part relabel history",
)

# Refuel remembers quick-vs-manual through the activity handoff.
s = replace_once(
    s,
    "bool veh_interact::queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan )\n"
    "{\n"
    "    if( plan.empty() ) {\n",
    "bool veh_interact::queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan,\n"
    "        const bool quick )\n"
    "{\n"
    "    if( plan.empty() ) {\n",
    "queue refill definition",
)

s = replace_once(
    s,
    "    sel_vehicle_part = &veh->part( refill_part_indices.front() );\n"
    "    sel_vpart_info = &sel_vehicle_part->info();\n"
    "    sel_cmd = 'f';\n",
    "    refill_quick = quick;\n"
    "    sel_vehicle_part = &veh->part( refill_part_indices.front() );\n"
    "    sel_vpart_info = &sel_vehicle_part->info();\n"
    "    sel_cmd = 'f';\n",
    "queue refill quick state",
)

s = replace_once(
    s,
    "    // queue_refill_plan preserves the canonical one-action-turn-per-transfer cost.\n"
    "    return queue_refill_plan( plan );\n",
    "    // queue_refill_plan preserves the canonical one-action-turn-per-transfer cost.\n"
    "    return queue_refill_plan( plan, true );\n",
    "quick refill call",
)

s = replace_once(
    s,
    "    refuel_info = std::make_unique<refuel_info_t>();\n"
    "    refuel_overlay.show();\n",
    "    refuel_info = std::make_unique<refuel_info_t>();\n"
    "    refill_quick = false;\n"
    "    refuel_overlay.show();\n",
    "refuel reset quick state",
)

# Solid-fuel unload is immediate, so log the mutation here.
s = replace_once(
    s,
    "        for( const int index : info.panel.list.selected_indices() ) {\n"
    "            if( const std::optional<item> fuel = veh->unload_fuel( here, info.fuels[index] ) ) {\n"
    "                who.i_add( *fuel );\n"
    "            }\n"
    "        }\n"
    "        cache_tool_availability();\n",
    "        std::vector<std::string> unloaded;\n"
    "        for( const int index : info.panel.list.selected_indices() ) {\n"
    "            if( const std::optional<item> fuel = veh->unload_fuel( here, info.fuels[index] ) ) {\n"
    "                unloaded.push_back( fuel->display_name() );\n"
    "                who.i_add( *fuel );\n"
    "            }\n"
    "        }\n"
    "        if( unloaded.size() == 1 ) {\n"
    "            record_editor_action( *veh, string_format( _( \"Unloaded %s\" ), unloaded.front() ) );\n"
    "        } else if( !unloaded.empty() ) {\n"
    "            record_editor_action( *veh, string_format( _( \"Unloaded %d fuel stacks\" ),\n"
    "                                                   static_cast<int>( unloaded.size() ) ) );\n"
    "        }\n"
    "        cache_tool_availability();\n",
    "unload history",
)

# Siphon plan: summarize only sources/destinations that actually receive a planned transfer.
s = replace_once(
    s,
    "    std::vector<player_activity> transfers;\n"
    "    int64_t remaining_total = 0;\n",
    "    std::vector<player_activity> transfers;\n"
    "    std::vector<int> used_sources;\n"
    "    std::set<size_t> used_destinations;\n"
    "    int total_transfer_charges = 0;\n"
    "    int64_t remaining_total = 0;\n",
    "siphon history tracking",
)

s = replace_once(
    s,
    "        int remaining = veh->part( source ).ammo_remaining();\n"
    "        for( size_t i = 0; i < destinations.size() && remaining > 0; ++i ) {\n",
    "        int remaining = veh->part( source ).ammo_remaining();\n"
    "        bool source_used = false;\n"
    "        for( size_t i = 0; i < destinations.size() && remaining > 0; ++i ) {\n",
    "siphon source usage flag",
)

s = replace_once(
    s,
    "                transfers.push_back( liquid_handler::siphon_transfer( *veh, source, destinations[i], amount ) );\n"
    "                capacity[i] -= amount;\n"
    "                remaining -= amount;\n",
    "                transfers.push_back( liquid_handler::siphon_transfer( *veh, source, destinations[i], amount ) );\n"
    "                source_used = true;\n"
    "                used_destinations.insert( i );\n"
    "                total_transfer_charges += amount;\n"
    "                capacity[i] -= amount;\n"
    "                remaining -= amount;\n",
    "siphon successful planned transfer tracking",
)

s = replace_once(
    s,
    "        remaining_total += remaining;\n"
    "    }\n"
    "    if( transfers.empty() ) {\n",
    "        if( source_used ) {\n"
    "            used_sources.push_back( source );\n"
    "        }\n"
    "        remaining_total += remaining;\n"
    "    }\n"
    "    if( transfers.empty() ) {\n",
    "siphon source collection",
)

siphon_summary = '''    std::string source_summary;\n    if( used_sources.size() == 1 ) {\n        source_summary = editor_part_display_name( veh->part( used_sources.front() ) );\n    } else {\n        source_summary = string_format( _( "%d tanks" ), static_cast<int>( used_sources.size() ) );\n    }\n\n    std::string destination_summary;\n    if( used_destinations.size() == 1 ) {\n        const liquid_handler::siphon_destination &destination = destinations[*used_destinations.begin()];\n        if( destination.container ) {\n            destination_summary = destination.container->display_name();\n        } else if( destination.tank ) {\n            destination_summary = string_format( _( "%1$s on %2$s" ),\n                                                 editor_part_display_name( destination.tank->part() ),\n                                                 destination.tank->vehicle().name );\n        }\n    } else {\n        int containers = 0;\n        int tanks = 0;\n        for( const size_t index : used_destinations ) {\n            if( destinations[index].container ) {\n                ++containers;\n            } else if( destinations[index].tank ) {\n                ++tanks;\n            }\n        }\n        if( tanks == 0 ) {\n            destination_summary = string_format( _( "%d containers" ), containers );\n        } else if( containers == 0 ) {\n            destination_summary = string_format( _( "%d tanks" ), tanks );\n        } else {\n            destination_summary = string_format( _( "%d destinations" ),\n                                                 static_cast<int>( used_destinations.size() ) );\n        }\n    }\n\n    item transferred_liquid( *info.liquid );\n    transferred_liquid.charges = total_transfer_charges;\n    stage_editor_action( *veh, string_format(\n                             _( "Siphoned %1$.1f L of %2$s from %3$s to %4$s" ),\n                             units::to_liter( transferred_liquid.volume() ),\n                             item::nname( info.liquid->typeId() ), source_summary, destination_summary ) );\n'''

s = replace_once(
    s,
    "    resource_transfer_activity = player_activity( vehicle_siphon_activity_actor(\n"
    "                                     std::move( transfers ), veh->abs_part_pos( 0 ), dd ) );\n",
    siphon_summary
    + "    resource_transfer_activity = player_activity( vehicle_siphon_activity_actor(\n"
    "                                     std::move( transfers ), veh->abs_part_pos( 0 ), dd ) );\n",
    "siphon staged summary",
)

# Crew assignment / clearing is immediate.
s = replace_once(
    s,
    "        menu.query();\n"
    "        if( menu.ret == 0 ) {\n"
    "            pt.unset_crew();\n"
    "        } else if( menu.ret > 0 ) {\n"
    "            const npc &who = *g->critter_by_id<npc>( character_id( menu.ret ) );\n"
    "            veh->assign_seat( pt, who );\n"
    "        }\n",
    "        menu.query();\n"
    "        if( menu.ret == 0 && pt.crew() ) {\n"
    "            const std::string crew_name = pt.crew()->get_name();\n"
    "            const std::string seat_name = editor_part_display_name( pt );\n"
    "            pt.unset_crew();\n"
    "            record_editor_action( *veh, string_format( _( \"Unassigned %1$s from %2$s\" ),\n"
    "                                                       crew_name, seat_name ) );\n"
    "        } else if( menu.ret > 0 ) {\n"
    "            const npc &who = *g->critter_by_id<npc>( character_id( menu.ret ) );\n"
    "            const bool changed = pt.crew() == nullptr || pt.crew()->getID() != who.getID();\n"
    "            veh->assign_seat( pt, who );\n"
    "            if( changed ) {\n"
    "                record_editor_action( *veh, string_format( _( \"Assigned %1$s to %2$s\" ),\n"
    "                                                           who.get_name(), editor_part_display_name( pt ) ) );\n"
    "            }\n"
    "        }\n",
    "crew history",
)

# Rename only records a real name change.
s = replace_once(
    s,
    "void veh_interact::do_rename()\n"
    "{\n"
    "    const std::optional<std::string> name = ui_query_text_input_dialog(\n"
    "                _( \"Rename vehicle\" ), _( \"Name\" ), veh->name, 20 );\n"
    "    if( name && !name->empty() ) {\n"
    "        veh->name = *name;\n",
    "void veh_interact::do_rename()\n"
    "{\n"
    "    const std::string old_name = veh->name;\n"
    "    const std::optional<std::string> name = ui_query_text_input_dialog(\n"
    "                _( \"Rename vehicle\" ), _( \"Name\" ), veh->name, 20 );\n"
    "    if( name && !name->empty() ) {\n"
    "        veh->name = *name;\n",
    "rename old name",
)

s = replace_once(
    s,
    "            overmap_buffer.add_vehicle( veh );\n"
    "        }\n"
    "    }\n"
    "}\n\n"
    "void veh_interact::do_relabel",
    "            overmap_buffer.add_vehicle( veh );\n"
    "        }\n"
    "        if( old_name != *name ) {\n"
    "            record_editor_action( *veh, string_format( _( \"Renamed vehicle: %1$s → %2$s\" ),\n"
    "                                                       old_name, *name ) );\n"
    "        }\n"
    "    }\n"
    "}\n\n"
    "void veh_interact::do_relabel",
    "rename history",
)

# ACT_VEHICLE completion logging: only editor-originated activities carry the marker.
s = replace_once(
    s,
    "    const bool editor_test = you.activity.str_values.size() > 1 &&\n"
    "                             you.activity.str_values[1] == \"vehicle_editor_test\";\n",
    "    const bool editor_test = you.activity.str_values.size() > 1 &&\n"
    "                             you.activity.str_values[1] == \"vehicle_editor_test\";\n"
    "    const bool editor_history = you.activity.str_values.size() > 3 &&\n"
    "                                you.activity.str_values[3] == \"vehicle_editor_history\";\n",
    "complete vehicle history marker",
)

s = replace_once(
    s,
    "            you.add_msg_if_player( m_good, _( \"You install a %1$s into the %2$s.\" ), vp_new.name(), veh.name );\n\n"
    "            if( !editor_test ) {\n",
    "            you.add_msg_if_player( m_good, _( \"You install a %1$s into the %2$s.\" ), vp_new.name(), veh.name );\n"
    "            if( editor_history ) {\n"
    "                record_editor_action( veh, string_format( _( \"Installed %s\" ),\n"
    "                                                           editor_part_display_name( vp_new ) ) );\n"
    "            }\n\n"
    "            if( !editor_test ) {\n",
    "install completion history",
)

s = replace_once(
    s,
    "        case 'r': {\n"
    "            vehicle_part &vp = veh.part( you.activity.values[6] );\n"
    "            veh_utils::repair_part( here, veh, vp, you, !editor_test );\n"
    "            break;\n"
    "        }\n",
    "        case 'r': {\n"
    "            vehicle_part &vp = veh.part( you.activity.values[6] );\n"
    "            const bool replacing = vp.is_broken();\n"
    "            const std::string part_name = editor_part_display_name( vp );\n"
    "            if( veh_utils::repair_part( here, veh, vp, you, !editor_test ) && editor_history ) {\n"
    "                record_editor_action( veh, replacing ?\n"
    "                                      string_format( _( \"Replaced %s\" ), part_name ) :\n"
    "                                      string_format( _( \"Repaired %s\" ), part_name ) );\n"
    "            }\n"
    "            break;\n"
    "        }\n",
    "repair completion history",
)

# Refuel aggregate is based on successful moves, not the requested plan.
s = replace_once(
    s,
    "            const auto refill_one = [&]( vehicle_part &vp, item_location &src ) {\n",
    "            std::vector<int> source_group( transfer_count, -1 );\n"
    "            std::vector<item_location> unique_sources;\n"
    "            std::vector<std::string> source_labels;\n"
    "            for( size_t i = 0; i < transfer_count; ++i ) {\n"
    "                if( !you.activity.targets[i] ) {\n"
    "                    continue;\n"
    "                }\n"
    "                const auto found = std::find( unique_sources.begin(), unique_sources.end(),\n"
    "                                              you.activity.targets[i] );\n"
    "                if( found != unique_sources.end() ) {\n"
    "                    source_group[i] = static_cast<int>( std::distance( unique_sources.begin(), found ) );\n"
    "                } else {\n"
    "                    source_group[i] = static_cast<int>( unique_sources.size() );\n"
    "                    source_labels.push_back( you.activity.targets[i]->display_name() );\n"
    "                    unique_sources.push_back( you.activity.targets[i] );\n"
    "                }\n"
    "            }\n"
    "            std::set<int> used_source_groups;\n"
    "            std::set<int> used_target_parts;\n"
    "            itype_id history_fuel = itype_id::NULL_ID();\n"
    "            units::volume history_liquid_volume = 0_ml;\n"
    "            int history_charges = 0;\n"
    "            bool history_liquid = false;\n\n"
    "            const auto refill_one = [&]( vehicle_part &vp, item_location &src,\n"
    "                                         const int part_index, const int source_index ) {\n",
    "refuel aggregate setup",
)

s = replace_once(
    s,
    "                    if( moved <= 0 ) {\n"
    "                        return;\n"
    "                    }\n\n"
    "                    const int remaining_ammo_capacity",
    "                    if( moved <= 0 ) {\n"
    "                        return;\n"
    "                    }\n"
    "                    item moved_liquid( *liquid );\n"
    "                    moved_liquid.charges = moved;\n"
    "                    history_fuel = fuel_type;\n"
    "                    history_liquid = true;\n"
    "                    history_liquid_volume += moved_liquid.volume();\n"
    "                    used_target_parts.insert( part_index );\n"
    "                    if( source_index >= 0 ) {\n"
    "                        used_source_groups.insert( source_index );\n"
    "                    }\n\n"
    "                    const int remaining_ammo_capacity",
    "liquid refuel aggregate",
)

s = replace_once(
    s,
    "                if( vp.is_fuel_store() ) {\n"
    "                    contents_change_handler handler;\n"
    "                    handler.unseal_pocket_containing( src );\n"
    "                    const int qty = src->charges;\n"
    "                    vp.base.reload( you, std::move( src ), qty );\n",
    "                if( vp.is_fuel_store() ) {\n"
    "                    const itype_id fuel_type = src->typeId();\n"
    "                    contents_change_handler handler;\n"
    "                    handler.unseal_pocket_containing( src );\n"
    "                    const int qty = src->charges;\n"
    "                    vp.base.reload( you, std::move( src ), qty );\n"
    "                    if( qty > 0 ) {\n"
    "                        history_fuel = fuel_type;\n"
    "                        history_charges += qty;\n"
    "                        used_target_parts.insert( part_index );\n"
    "                        if( source_index >= 0 ) {\n"
    "                            used_source_groups.insert( source_index );\n"
    "                        }\n"
    "                    }\n",
    "solid refuel aggregate",
)

s = replace_once(
    s,
    "                refill_one( veh.part( part_index ), you.activity.targets[i] );\n"
    "            }\n\n"
    "            veh.invalidate_mass();\n",
    "                refill_one( veh.part( part_index ), you.activity.targets[i], part_index, source_group[i] );\n"
    "            }\n\n"
    "            if( editor_history && !history_fuel.is_null() &&\n"
    "                ( history_liquid_volume > 0_ml || history_charges > 0 ) ) {\n"
    "                const bool quick = you.activity.str_values.size() > 4 &&\n"
    "                                   you.activity.str_values[4] == \"vehicle_refill_quick\";\n"
    "                const std::string amount = history_liquid ?\n"
    "                                           string_format( \"%.1f L\", units::to_liter( history_liquid_volume ) ) :\n"
    "                                           string_format( _( \"%d charges\" ), history_charges );\n"
    "                if( quick ) {\n"
    "                    record_editor_action( veh, string_format( _( \"Quick refueled %1$s of %2$s\" ),\n"
    "                                                              amount, item::nname( history_fuel ) ) );\n"
    "                } else {\n"
    "                    std::string target_summary;\n"
    "                    if( used_target_parts.size() == 1 ) {\n"
    "                        target_summary = editor_part_display_name( veh.part( *used_target_parts.begin() ) );\n"
    "                    } else {\n"
    "                        target_summary = string_format( _( \"%d fuel stores\" ),\n"
    "                                                        static_cast<int>( used_target_parts.size() ) );\n"
    "                    }\n"
    "                    std::string source_summary;\n"
    "                    if( used_source_groups.size() == 1 ) {\n"
    "                        const int group = *used_source_groups.begin();\n"
    "                        if( group >= 0 && group < static_cast<int>( source_labels.size() ) ) {\n"
    "                            source_summary = source_labels[group];\n"
    "                        }\n"
    "                    } else {\n"
    "                        source_summary = string_format( _( \"%d sources\" ),\n"
    "                                                        static_cast<int>( used_source_groups.size() ) );\n"
    "                    }\n"
    "                    record_editor_action( veh, string_format(\n"
    "                                              _( \"Refueled %1$s of %2$s into %3$s from %4$s\" ),\n"
    "                                              amount, item::nname( history_fuel ),\n"
    "                                              target_summary, source_summary ) );\n"
    "                }\n"
    "            }\n\n"
    "            veh.invalidate_mass();\n",
    "refuel completion summary",
)

# Removal stores the name before references can be invalidated and logs after the mutation is committed.
s = replace_once(
    s,
    "            vehicle_part *vp = &veh.part( vp_index );\n"
    "            const vpart_info &vpi = vp->info();\n",
    "            vehicle_part *vp = &veh.part( vp_index );\n"
    "            const std::string removed_part_name = editor_part_display_name( *vp );\n"
    "            const vpart_info &vpi = vp->info();\n",
    "removed part history name",
)

s = replace_once(
    s,
    "            if( veh.part_count_real() <= 1 ) {\n"
    "                you.add_msg_if_player( _( \"You completely dismantle the %s.\" ), veh.name );\n",
    "            if( editor_history ) {\n"
    "                record_editor_action( veh, string_format( _( \"Removed %s\" ), removed_part_name ) );\n"
    "            }\n"
    "            if( veh.part_count_real() <= 1 ) {\n"
    "                you.add_msg_if_player( _( \"You completely dismantle the %s.\" ), veh.name );\n",
    "remove completion history",
)

p.write_text(s)


# -----------------------------------------------------------------------------
# activity_handlers.cpp -- mend history commits only after a successful fix.
# -----------------------------------------------------------------------------
p = Path("src/activity_handlers.cpp")
s = p.read_text()

s = replace_once(
    s,
    "    add_msg( m_good, fix.success_msg.translated(), target.tname( 1, false ),\n"
    "             start_durability, target.durability_indicator( true ) );\n",
    "    add_msg( m_good, fix.success_msg.translated(), target.tname( 1, false ),\n"
    "             start_durability, target.durability_indicator( true ) );\n"
    "    if( act->str_values.size() > 1 && act->str_values[1] == \"vehicle_editor_history\" ) {\n"
    "        veh_interact::commit_staged_editor_action();\n"
    "    }\n",
    "mend completion commit",
)

p.write_text(s)


# -----------------------------------------------------------------------------
# activity_actor.cpp -- siphon commits only after the entire transfer actor ends.
# -----------------------------------------------------------------------------
p = Path("src/activity_actor.cpp")
s = p.read_text()

s = replace_once(
    s,
    "        who.add_msg_if_player( m_info, _( \"You can no longer siphon from this vehicle.\" ) );\n"
    "        veh_interact::discard_persistent_editor();\n",
    "        who.add_msg_if_player( m_info, _( \"You can no longer siphon from this vehicle.\" ) );\n"
    "        veh_interact::clear_staged_editor_action();\n"
    "        veh_interact::discard_persistent_editor();\n",
    "siphon invalidation clears staged history",
)

s = replace_once(
    s,
    "    if( source && who.is_avatar() ) {\n"
    "        here.invalidate_map_cache( here.get_abs_sub().z() );\n",
    "    if( source && who.is_avatar() ) {\n"
    "        veh_interact::commit_staged_editor_action( &source->vehicle() );\n"
    "        here.invalidate_map_cache( here.get_abs_sub().z() );\n",
    "siphon completion commit",
)

s = replace_once(
    s,
    "void vehicle_siphon_activity_actor::canceled( player_activity &, Character & )\n"
    "{\n"
    "    veh_interact::discard_persistent_editor();\n"
    "}\n",
    "void vehicle_siphon_activity_actor::canceled( player_activity &, Character & )\n"
    "{\n"
    "    veh_interact::clear_staged_editor_action();\n"
    "    veh_interact::discard_persistent_editor();\n"
    "}\n",
    "siphon cancellation clears staged history",
)

p.write_text(s)

Path("/tmp/branch_patch_commit_message").write_text(
    "Add vehicle editor action workspace history\n"
)
