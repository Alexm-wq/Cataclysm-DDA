from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/game.cpp",
    '''    const npc *const guy = dynamic_cast<const npc *>( creature );\n    const bool visible_creature = creature != nullptr && !creature->is_avatar() && u.sees( here, *creature );\n\n    const auto world_object_name = [&]() -> std::string {''',
    '''    const npc *const guy = dynamic_cast<const npc *>( creature );\n    const bool visible_creature = creature != nullptr && !creature->is_avatar() && u.sees( here, *creature );\n    const bool hostile_creature = visible_creature &&\n                                  u.attitude_to( *creature ) == Creature::Attitude::HOSTILE;\n\n    const auto world_object_name = [&]() -> std::string {'''
)

replace_once(
    "src/game.cpp",
    '''    // Creature actions come first because they describe the most specific thing under the pointer.\n    if( visible_creature && is_adjacent ) {\n        entries.emplace_back( string_format( _( "Attack %s" ), creature_name ),\n                              "CONTEXT_ATTACK" );\n    }\n    if( mon != nullptr && u.sees( here, *mon ) && u.get_wielded_item() &&\n        u.get_wielded_item()->is_gun() ) {\n        entries.emplace_back( string_format( _( "Fire at %s" ), mon->name() ),\n                              action_ident( ACTION_FIRE ) );\n    }''',
    '''    // Creature actions come first because they describe the most specific thing under the pointer.\n    if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {\n        entries.emplace_back( string_format( _( "Talk to %s" ), guy->get_name() ),\n                              "CONTEXT_TALK" );\n    }\n    if( hostile_creature && is_adjacent ) {\n        entries.emplace_back( string_format( _( "Attack %s" ), creature_name ),\n                              "CONTEXT_ATTACK" );\n    }\n    if( hostile_creature && u.get_wielded_item() && u.get_wielded_item()->is_gun() ) {\n        // ACTION_FIRE opens the normal targeting UI, so do not imply that the\n        // clicked creature is hard-locked as the shot target.\n        add_action( ACTION_FIRE );\n    }'''
)

replace_once(
    "src/game.cpp",
    '''        entries.emplace_back( string_format( _( "Smash %s" ), smash_target ),\n                              action_ident( ACTION_SMASH ) );\n    }\n\n    // Preflight pathfinding once.  Distant contextual interactions may reuse this route,''',
    '''        entries.emplace_back( string_format( _( "Smash %s" ), smash_target ),\n                              action_ident( ACTION_SMASH ) );\n    }\n\n    const bool grabbable_furniture = is_adjacent && !is_self && here.has_furn( mouse_target ) &&\n                                     here.furn( mouse_target ).obj().is_movable();\n    const bool grabbable_vehicle = is_adjacent && !is_self &&\n                                   static_cast<bool>( here.veh_at( mouse_target ) );\n    if( u.get_grab_type() == object_type::NONE &&\n        ( grabbable_furniture || grabbable_vehicle ) ) {\n        entries.emplace_back( string_format( _( "Grab %s" ), structural_name ),\n                              action_ident( ACTION_GRAB ) );\n    }\n    if( is_adjacent && !is_self ) {\n        add_action( ACTION_PEEK );\n    }\n\n    // Preflight pathfinding once.  Distant contextual interactions may reuse this route,'''
)

replace_once(
    "src/game.cpp",
    '''        if( result.entry->id == "CONTEXT_MOVE_UP" ||\n            result.entry->id == "CONTEXT_MOVE_DOWN" ) {''',
    '''        if( result.entry->id == "CONTEXT_TALK" ) {\n            context_menu.close();\n            if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {\n                u.talk_to( get_talker_for( *guy ) );\n            }\n            return false;\n        }\n\n        if( result.entry->id == "CONTEXT_MOVE_UP" ||\n            result.entry->id == "CONTEXT_MOVE_DOWN" ) {'''
)

replace_once(
    "src/handle_action.cpp",
    '''static void grab()\n{''',
    '''static void grab( const std::optional<tripoint_bub_ms> &p = std::nullopt )\n{'''
)

replace_once(
    "src/handle_action.cpp",
    '''    const std::optional<tripoint_bub_ms> grabp_ = choose_adjacent( _( "Grab where?" ) );\n    if( !grabp_ ) {''',
    '''    std::optional<tripoint_bub_ms> grabp_ = p;\n    if( !grabp_ ) {\n        grabp_ = choose_adjacent( _( "Grab where?" ) );\n    }\n    if( !grabp_ ) {'''
)

replace_once(
    "src/handle_action.cpp",
    '''        case ACTION_GRAB:\n            grab();\n            break;''',
    '''        case ACTION_GRAB:\n            grab( mouse_target );\n            break;'''
)

replace_once(
    "src/handle_action.cpp",
    '''        case ACTION_PEEK:\n            peek();\n            break;''',
    '''        case ACTION_PEEK:\n            if( mouse_target ) {\n                peek( *mouse_target );\n            } else {\n                peek();\n            }\n            break;'''
)

replace_once(
    "src/handle_action.cpp",
    '''            const std::string reason =\n                _( "Walking to the construction site stopped because the route could not "\n                   "continue." );\n            add_msg( m_info, _( "Auto-move canceled" ) );''',
    '''            const std::string reason =\n                _( "Auto-move stopped because the route could not continue." );\n            add_msg( m_info, _( "Auto-move canceled" ) );'''
)

replace_once(
    "src/handle_action.cpp",
    '''                    construction_ui::set_persistent_editor_activity_failure(\n                        _( "Walking to the construction site stopped because the next step "\n                           "was blocked." ) );''',
    '''                    construction_ui::set_persistent_editor_activity_failure(\n                        _( "Auto-move stopped because the next step was blocked." ) );'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Polish contextual world actions\n"
)
print("contextual world action cleanup patched")
