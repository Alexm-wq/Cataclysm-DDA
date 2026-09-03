from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/character.h",
    '''        void set_destination( const std::vector<tripoint_bub_ms> &route,\n                              const player_activity &new_destination_activity = player_activity() );\n        void clear_destination();\n        //clear_destination(), also closes overmap UI if still open\n        void abort_automove();''',
    '''        void set_destination( const std::vector<tripoint_bub_ms> &route,\n                              const player_activity &new_destination_activity = player_activity() );\n        // Queue one ordinary gameplay action to run after the current destination is reached.\n        // It shares the destination lifecycle, so canceling/replacing auto-move cancels the action too.\n        void set_destination_action( action_id action );\n        bool has_destination_action() const;\n        action_id start_destination_action();\n        void clear_destination();\n        //clear_destination(), also closes overmap UI if still open\n        void abort_automove();'''
)

replace_once(
    "src/character.h",
    '''        player_activity destination_activity;\n        /// A unique ID number, assigned by the game class. Values should never be reused.''',
    '''        player_activity destination_activity;\n        // Ephemeral mouse/world-order continuation; deliberately not persisted across saves.\n        std::optional<action_id> destination_action; // NOLINT(cata-serialize)\n        /// A unique ID number, assigned by the game class. Values should never be reused.'''
)

replace_once(
    "src/character.cpp",
    '''void Character::set_destination( const std::vector<tripoint_bub_ms> &route,\n                                 const player_activity &new_destination_activity )\n{\n    auto_move_route = route;\n    set_destination_activity( new_destination_activity );\n    destination_point.emplace( get_map().get_abs( route.back() ) );\n}\n\nvoid Character::clear_destination()\n{\n    auto_move_route.clear();\n    clear_destination_activity();\n    destination_point = std::nullopt;\n    next_expected_position = std::nullopt;\n}''',
    '''void Character::set_destination( const std::vector<tripoint_bub_ms> &route,\n                                 const player_activity &new_destination_activity )\n{\n    auto_move_route = route;\n    set_destination_activity( new_destination_activity );\n    destination_action.reset();\n    destination_point.emplace( get_map().get_abs( route.back() ) );\n}\n\nvoid Character::set_destination_action( const action_id action )\n{\n    clear_destination_activity();\n    if( action == ACTION_NULL ) {\n        destination_action.reset();\n    } else {\n        destination_action = action;\n    }\n}\n\nbool Character::has_destination_action() const\n{\n    const bool has_reached_destination = destination_point &&\n                                         ( pos_abs() == *destination_point || auto_move_route.empty() );\n    return destination_action.has_value() && has_reached_destination;\n}\n\naction_id Character::start_destination_action()\n{\n    if( !has_destination_action() ) {\n        debugmsg( "Tried to start invalid destination action" );\n        return ACTION_NULL;\n    }\n\n    const action_id result = *destination_action;\n    clear_destination();\n    return result;\n}\n\nvoid Character::clear_destination()\n{\n    auto_move_route.clear();\n    clear_destination_activity();\n    destination_action.reset();\n    destination_point = std::nullopt;\n    next_expected_position = std::nullopt;\n}'''
)

replace_once(
    "src/handle_action.cpp",
    '''        handle_key_blocking_activity();\n    } else if( player_character.has_destination_activity() ) {\n        // starts destination activity after the player successfully reached his destination\n        player_character.start_destination_activity();\n        return false;\n    } else if( uistate.open_menu ) {''',
    '''        handle_key_blocking_activity();\n    } else if( player_character.has_destination_action() ) {\n        // Run a queued world-context action only after auto-move has reached its exact tile.\n        // The action then follows the normal gameplay handler, including all usual checks.\n        act = player_character.start_destination_action();\n        if( act == ACTION_NULL ) {\n            return false;\n        }\n    } else if( player_character.has_destination_activity() ) {\n        // starts destination activity after the player successfully reached his destination\n        player_character.start_destination_activity();\n        return false;\n    } else if( uistate.open_menu ) {'''
)

replace_once(
    "src/game.cpp",
    '''    // These actions are implemented by the normal action handlers on the player's own square.\n    if( is_self && can_interact_at( ACTION_BUTCHER, here, mouse_target ) ) {\n        add_action( ACTION_BUTCHER );\n    }\n    if( is_self && can_interact_at( ACTION_MOVE_UP, here, mouse_target ) ) {\n        add_action( ACTION_MOVE_UP );\n    }\n    if( is_self && can_interact_at( ACTION_MOVE_DOWN, here, mouse_target ) ) {\n        add_action( ACTION_MOVE_DOWN );\n    }\n\n    // Preflight pathfinding so an unreachable square does not advertise a bogus Move to action.\n    std::optional<std::vector<tripoint_bub_ms>> move_route;\n    if( !is_self && creature == nullptr ) {\n        move_route = safe_route_to( u, mouse_target, 0, []( const std::string & ) {} );\n        if( move_route ) {\n            entries.emplace_back( _( "Move to" ), "CONTEXT_MOVE_TO" );\n        }\n    }''',
    '''    // Preflight pathfinding once.  Distant contextual interactions may reuse this route,\n    // and unreachable squares should not advertise actions that require standing on them.\n    std::optional<std::vector<tripoint_bub_ms>> move_route;\n    if( !is_self && creature == nullptr ) {\n        move_route = safe_route_to( u, mouse_target, 0, []( const std::string & ) {} );\n    }\n\n    if( is_self && can_interact_at( ACTION_BUTCHER, here, mouse_target ) ) {\n        add_action( ACTION_BUTCHER );\n    }\n\n    // Vertical transitions are useful as destination orders: from range, walk onto\n    // the selected stairs/ladder first, then execute the ordinary ascend/descend action.\n    const bool can_reach_vertical_target = is_self || move_route.has_value();\n    if( can_reach_vertical_target && can_interact_at( ACTION_MOVE_UP, here, mouse_target ) ) {\n        entries.emplace_back( action_names.get_action_name( action_ident( ACTION_MOVE_UP ) ),\n                              "CONTEXT_MOVE_UP" );\n    }\n    if( can_reach_vertical_target && can_interact_at( ACTION_MOVE_DOWN, here, mouse_target ) ) {\n        entries.emplace_back( action_names.get_action_name( action_ident( ACTION_MOVE_DOWN ) ),\n                              "CONTEXT_MOVE_DOWN" );\n    }\n\n    if( move_route ) {\n        entries.emplace_back( _( "Move to" ), "CONTEXT_MOVE_TO" );\n    }'''
)

replace_once(
    "src/game.cpp",
    '''        if( result.entry->id == "CONTEXT_MOVE_TO" ) {\n            if( !move_route ) {\n                return false;\n            }\n            u.set_destination( *move_route );\n            act = u.get_next_auto_move_direction();\n            if( act == ACTION_NULL ) {\n                u.clear_destination();\n                return false;\n            }\n            return true;\n        }''',
    '''        if( result.entry->id == "CONTEXT_MOVE_UP" ||\n            result.entry->id == "CONTEXT_MOVE_DOWN" ) {\n            const action_id vertical_action = result.entry->id == "CONTEXT_MOVE_UP" ?\n                                              ACTION_MOVE_UP : ACTION_MOVE_DOWN;\n            if( is_self ) {\n                act = vertical_action;\n                return true;\n            }\n            if( !move_route ) {\n                return false;\n            }\n            u.set_destination( *move_route );\n            u.set_destination_action( vertical_action );\n            act = u.get_next_auto_move_direction();\n            if( act == ACTION_NULL ) {\n                u.clear_destination();\n                return false;\n            }\n            return true;\n        }\n\n        if( result.entry->id == "CONTEXT_MOVE_TO" ) {\n            if( !move_route ) {\n                return false;\n            }\n            u.set_destination( *move_route );\n            act = u.get_next_auto_move_direction();\n            if( act == ACTION_NULL ) {\n                u.clear_destination();\n                return false;\n            }\n            return true;\n        }'''
)

Path("/tmp/branch_patch_commit_message").write_text("Walk to contextual stairs before using them\n")
print("contextual stair auto-travel patched")
