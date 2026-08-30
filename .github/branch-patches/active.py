from pathlib import Path

def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))

# construction_target.h: add a presentation semantic layer and contextual action result type.
replace_once(
    "src/construction_target.h",
    """enum class construction_target_status : int {
    none,
    ready,
    unavailable_requirements,
    invalid_location,
    in_progress
};
""",
    """enum class construction_target_status : int {
    none,
    ready,
    unavailable_requirements,
    invalid_location,
    in_progress
};

/**
 * Player-facing intent for a construction definition.  The construction JSON
 * remains the simulation source of truth; this layer only decides how a
 * definition should be exposed by map-centric construction UIs.
 *
 * Only repair is contextualized in the first demo.  The remaining values make
 * the resolver extensible without teaching construction_ui about recipe names.
 */
enum class construction_ui_intent : int {
    build,
    repair,
    modify,
    upgrade,
    terrain_work,
    decorate,
    marker,
    remove
};
"""
)

replace_once(
    "src/construction_target.h",
    """struct construction_target_resolution {
    construction_id id = construction_id( -1 );
    construction_target_status status = construction_target_status::none;
    std::string reason;
    /** Applicable alternatives ordered best-first; id is always the chosen first entry. */
    std::vector<construction_id> alternative_ids;

    bool has_construction() const {
        return id.to_i() >= 0;
    }
    bool ready() const {
        return status == construction_target_status::ready;
    }
};
""",
    """struct construction_target_resolution {
    construction_id id = construction_id( -1 );
    construction_target_status status = construction_target_status::none;
    std::string reason;
    /** Applicable alternatives ordered best-first; id is always the chosen first entry. */
    std::vector<construction_id> alternative_ids;

    bool has_construction() const {
        return id.to_i() >= 0;
    }
    bool ready() const {
        return status == construction_target_status::ready;
    }
};

struct construction_context_action {
    construction_ui_intent intent = construction_ui_intent::build;
    construction_target_resolution resolution;
};
"""
)

replace_once(
    "src/construction_target.h",
    """construction_target_resolution resolve_remove_target(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target );
bool construction_is_remove_action( const construction &con );
""",
    """construction_target_resolution resolve_remove_target(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target );
std::vector<construction_context_action> resolve_context_construction_actions(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target );
construction_ui_intent construction_ui_intent_for( const construction &con );
bool construction_is_catalog_action( const construction &con );
bool construction_is_remove_action( const construction &con );
"""
)

# construction_target.cpp: centralize presentation classification and add a generic
# contextual action resolver.  REPAIR is the first real action wired through it.
replace_once(
    "src/construction_target.cpp",
    """static const trait_id trait_DEBUG_HS( "DEBUG_HS" );
bool construction_is_remove_action( const construction &con )
{
    return con.action != construction_action::build;
}
""",
    """static const trait_id trait_DEBUG_HS( "DEBUG_HS" );
static const construction_category_id construction_category_REPAIR( "REPAIR" );

bool construction_is_remove_action( const construction &con )
{
    return con.action != construction_action::build;
}

construction_ui_intent construction_ui_intent_for( const construction &con )
{
    if( construction_is_remove_action( con ) ) {
        return construction_ui_intent::remove;
    }
    if( con.category == construction_category_REPAIR ) {
        return construction_ui_intent::repair;
    }
    return construction_ui_intent::build;
}

bool construction_is_catalog_action( const construction &con )
{
    return construction_ui_intent_for( con ) == construction_ui_intent::build;
}
"""
)

replace_once(
    "src/construction_target.cpp",
    """    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to remove." ),
                               _( "The selected tile has no removable construction." ) );
}
""",
    """    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to remove." ),
                               _( "The selected tile has no removable construction." ) );
}

std::vector<construction_context_action> resolve_context_construction_actions(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target )
{
    std::vector<construction_context_action> result;
    if( common_target_rejection( who, target, false ) ) {
        return result;
    }

    // Context actions are resolved by player intent, not by construction group.
    // Adding Modify/Upgrade/Terrain Work later only requires another intent
    // bucket here; construction_ui consumes the same generic result structure.
    std::vector<const construction *> repair_candidates;
    for( const construction &con : get_constructions() ) {
        if( construction_ui_intent_for( con ) == construction_ui_intent::repair ) {
            repair_candidates.push_back( &con );
        }
    }

    const construction_target_resolution repair = resolve_candidates(
                who, inventory, repair_candidates, target,
                _( "Ready to repair." ),
                _( "This tile has no applicable repair action." ) );
    if( repair.has_construction() ) {
        result.push_back( construction_context_action{ construction_ui_intent::repair, repair } );
    }
    return result;
}
"""
)

# construction_ui.cpp: consume contextual actions without hardcoding repair recipe IDs/groups.
replace_once(
    "src/construction_ui.cpp",
    """static std::string construction_result_description( const construction &con )
{
    if( con.post_terrain.empty() ) {
        return con.pre_note.empty() ? std::string() : con.pre_note.translated();
    }
    return con.post_is_furniture ? furn_str_id( con.post_terrain )->description.translated() :
           ter_str_id( con.post_terrain )->description.translated();
}
""",
    """static std::string construction_result_description( const construction &con )
{
    if( con.post_terrain.empty() ) {
        return con.pre_note.empty() ? std::string() : con.pre_note.translated();
    }
    return con.post_is_furniture ? furn_str_id( con.post_terrain )->description.translated() :
           ter_str_id( con.post_terrain )->description.translated();
}

static std::string contextual_action_label( const construction_ui_intent intent )
{
    switch( intent ) {
        case construction_ui_intent::repair:
            return _( "Repair" );
        case construction_ui_intent::modify:
            return _( "Modify" );
        case construction_ui_intent::upgrade:
            return _( "Upgrade" );
        case construction_ui_intent::terrain_work:
            return _( "Terrain work" );
        case construction_ui_intent::decorate:
            return _( "Decorate" );
        case construction_ui_intent::marker:
            return _( "Mark" );
        case construction_ui_intent::remove:
            return _( "Remove" );
        case construction_ui_intent::build:
            return _( "Build" );
    }
    return _( "Work" );
}

static std::string contextual_action_id( const construction_ui_intent intent )
{
    switch( intent ) {
        case construction_ui_intent::repair:
            return "CONTEXT_REPAIR";
        case construction_ui_intent::modify:
            return "CONTEXT_MODIFY";
        case construction_ui_intent::upgrade:
            return "CONTEXT_UPGRADE";
        case construction_ui_intent::terrain_work:
            return "CONTEXT_TERRAIN_WORK";
        case construction_ui_intent::decorate:
            return "CONTEXT_DECORATE";
        case construction_ui_intent::marker:
            return "CONTEXT_MARKER";
        case construction_ui_intent::remove:
            return "CONTEXT_REMOVE";
        case construction_ui_intent::build:
            return "CONTEXT_BUILD";
    }
    return "CONTEXT_WORK";
}
"""
)

replace_once(
    "src/construction_ui.cpp",
    """        bool execute_context_action( const std::string &id );
        bool request_action( const tripoint_bub_ms &target );
""",
    """        bool execute_context_action( const std::string &id );
        bool request_action( const tripoint_bub_ms &target );
        bool request_context_action( const std::string &id, const tripoint_bub_ms &target );
"""
)

replace_once(
    "src/construction_ui.cpp",
    """        ui_action_strip palette_actions;
        ui_action_strip primary_action;
""",
    """        ui_action_strip palette_actions;
        ui_action_strip contextual_action_strip;
        ui_action_strip primary_action;
"""
)

replace_once(
    "src/construction_ui.cpp",
    """        std::optional<tripoint_bub_ms> context_target;
        construction_target_resolution resolution;
        std::vector<std::pair<tripoint_bub_ms, construction_target_resolution>> adjacent_resolutions;
""",
    """        std::optional<tripoint_bub_ms> context_target;
        construction_target_resolution resolution;
        std::vector<construction_context_action> context_actions;
        std::vector<std::pair<tripoint_bub_ms, construction_target_resolution>> adjacent_resolutions;
"""
)

replace_once(
    "src/construction_ui.cpp",
    """        if( std::none_of( variants.begin(), variants.end(), []( const construction * candidate ) {
        return candidate != nullptr && !construction_is_remove_action( *candidate );
        } ) ) {
""",
    """        if( std::none_of( variants.begin(), variants.end(), []( const construction * candidate ) {
        return candidate != nullptr && construction_is_catalog_action( *candidate );
        } ) ) {
"""
)

replace_once(
    "src/construction_ui.cpp",
    """        return candidate != nullptr && !candidate->post_terrain.empty() &&
               !construction_is_remove_action( *candidate );
""",
    """        return candidate != nullptr && !candidate->post_terrain.empty() &&
               construction_is_catalog_action( *candidate );
"""
)

replace_once(
    "src/construction_ui.cpp",
    """            return candidate != nullptr && !construction_is_remove_action( *candidate ) &&
                   visited.count( candidate->id ) == 0 &&
""",
    """            return candidate != nullptr && construction_is_catalog_action( *candidate ) &&
                   visited.count( candidate->id ) == 0 &&
"""
)

replace_once(
    "src/construction_ui.cpp",
    """        if( !con.on_display || construction_is_remove_action( con ) ||
            !seen.insert( con.group ).second ) {
""",
    """        if( !con.on_display || !construction_is_catalog_action( con ) ||
            !seen.insert( con.group ).second ) {
"""
)

replace_once(
    "src/construction_ui.cpp",
    """            if( candidate && player_can_build( you, you.crafting_inventory(), *candidate, true ) ) {
""",
    """            if( candidate && construction_is_catalog_action( *candidate ) &&
                player_can_build( you, you.crafting_inventory(), *candidate, true ) ) {
"""
)

replace_once(
    "src/construction_ui.cpp",
    """void construction_workspace::refresh_active_target()
{
    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
""",
    """void construction_workspace::refresh_active_target()
{
    const std::optional<tripoint_bub_ms> target = displayed_target();
    context_actions.clear();
    if( target && operation == construction_operation::build ) {
        context_actions = resolve_context_construction_actions(
                              you, you.crafting_inventory(), *target );
    }
    if( !target ) {
"""
)

replace_once(
    "src/construction_ui.cpp",
    """    add( target_description );

    const nc_color status_color = resolution.status == construction_target_status::ready ?
""",
    """    add( target_description );

    if( operation == construction_operation::build && !context_actions.empty() ) {
        blank();
        add( colorize( _( "Tile actions" ), c_light_gray ) );
        for( const construction_context_action &action : context_actions ) {
            const nc_color action_color = action.resolution.ready() ? c_light_green : c_yellow;
            add( colorize( string_format( _( "%s  •  %s" ),
                                          contextual_action_label( action.intent ),
                                          action.resolution.reason ), action_color ) );
        }
    }

    const nc_color status_color = resolution.status == construction_target_status::ready ?
"""
)

replace_once(
    "src/construction_ui.cpp",
    """    const int action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int content_height = std::max( 1, action_y - 2 );
""",
    """    const bool show_context_actions = operation == construction_operation::build &&
                                      selected_target && !context_actions.empty();
    const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int contextual_action_y = show_context_actions ?
                                    std::max( 2, primary_action_y - 2 ) : primary_action_y;
    const int content_height = std::max( 1, contextual_action_y - 2 );
"""
)

replace_once(
    "src/construction_ui.cpp",
    """    build.tone = operation == construction_operation::build ?
                 ui_action_tone::positive : ui_action_tone::destructive;
    primary_action.configure( inspector_window, point( 2, action_y ), { build },
                              inspector_width - 4, 1 );
""",
    """    if( show_context_actions ) {
        std::vector<ui_action_entry> entries;
        entries.reserve( context_actions.size() );
        for( const construction_context_action &action : context_actions ) {
            bool enabled = action.resolution.ready();
            std::string reason = action.resolution.reason;
            if( selected_target && !target_is_adjacent( *selected_target ) ) {
                enabled = false;
                reason = _( "Move adjacent to use this tile action." );
            }
            ui_action_entry entry( contextual_action_label( action.intent ),
                                   contextual_action_id( action.intent ), enabled, false, reason );
            entry.tone = ui_action_tone::positive;
            entries.push_back( std::move( entry ) );
        }
        contextual_action_strip.configure( inspector_window, point( 2, contextual_action_y ),
                                           std::move( entries ), inspector_width - 4, 1 );
        contextual_action_strip.draw( inspector_window );
    } else {
        contextual_action_strip.clear();
    }

    build.tone = operation == construction_operation::build ?
                 ui_action_tone::positive : ui_action_tone::destructive;
    primary_action.configure( inspector_window, point( 2, primary_action_y ), { build },
                              inspector_width - 4, 1 );
"""
)

replace_once(
    "src/construction_ui.cpp",
    """    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" ),
        ui_dropdown_entry( build_label, "APPLY", buildable, false, build_reason ),
        ui_dropdown_entry( _( "Center view here" ), "CENTER" ),
        ui_dropdown_entry( _( "Clear selection" ), "CLEAR", selected_target.has_value() )
    };
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
""",
    """    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" ),
        ui_dropdown_entry( build_label, "APPLY", buildable, false, build_reason ),
        ui_dropdown_entry( _( "Center view here" ), "CENTER" ),
        ui_dropdown_entry( _( "Clear selection" ), "CLEAR", selected_target.has_value() )
    };
    if( operation == construction_operation::build ) {
        std::vector<ui_dropdown_entry> contextual_entries;
        for( const construction_context_action &action :
             resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {
            bool enabled = action.resolution.ready() && adjacent;
            std::string reason = action.resolution.reason;
            if( !adjacent ) {
                reason = _( "Move adjacent to use this tile action." );
            }
            contextual_entries.emplace_back( contextual_action_label( action.intent ),
                                               contextual_action_id( action.intent ),
                                               enabled, false, reason );
        }
        entries.insert( entries.begin() + 1, contextual_entries.begin(), contextual_entries.end() );
    }
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
"""
)

replace_once(
    "src/construction_ui.cpp",
    """    } else if( id == "APPLY" ) {
        return request_action( *context_target );
""",
    """    } else if( id.rfind( "CONTEXT_", 0 ) == 0 ) {
        return request_context_action( id, *context_target );
    } else if( id == "APPLY" ) {
        return request_action( *context_target );
"""
)

replace_once(
    "src/construction_ui.cpp",
    """bool construction_workspace::handle_viewport_action(
    const ui_world_viewport_action &action, ui_adaptor &ui )
""",
    """bool construction_workspace::request_context_action( const std::string &id,
        const tripoint_bub_ms &target )
{
    const std::vector<construction_context_action> current =
        resolve_context_construction_actions( you, you.crafting_inventory(), target );
    const auto found = std::find_if( current.begin(), current.end(),
    [&id]( const construction_context_action & action ) {
        return contextual_action_id( action.intent ) == id;
    } );
    if( found == current.end() ) {
        transient_status = _( "That tile action is no longer applicable." );
        return false;
    }
    if( !target_is_adjacent( target ) ) {
        transient_status = _( "Move adjacent to use this tile action." );
        return false;
    }
    if( !found->resolution.ready() ) {
        transient_status = found->resolution.reason;
        return false;
    }
    if( !g->warn_player_maybe_anger_local_faction( true ) ) {
        transient_status = _( "Construction canceled." );
        return false;
    }
    build_order = construction_build_order{ found->resolution.id, target, false };
    exit_requested = true;
    return true;
}

bool construction_workspace::handle_viewport_action(
    const ui_world_viewport_action &action, ui_adaptor &ui )
"""
)

replace_once(
    "src/construction_ui.cpp",
    """    if( inspector_window ) {
        const ui_action_result build_result = primary_action.handle_pointer_input( action, inspector_pos );
""",
    """    if( inspector_window ) {
        const ui_action_result contextual_result =
            contextual_action_strip.handle_pointer_input( action, inspector_pos );
        if( contextual_result.type == ui_action_result_type::disabled && contextual_result.entry ) {
            transient_status = contextual_result.entry->disabled_reason;
            return true;
        }
        if( contextual_result.type == ui_action_result_type::activated && contextual_result.entry ) {
            if( selected_target ) {
                request_context_action( contextual_result.entry->id, *selected_target );
            }
            return true;
        }

        const ui_action_result build_result = primary_action.handle_pointer_input( action, inspector_pos );
"""
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Demo contextual construction repair [skip ci]\n"
)
