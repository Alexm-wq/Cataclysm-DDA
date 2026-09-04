from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


# Expose the existing curtain teardown mechanic so the mouse context menu can
# promote it out of the legacy Examine submenu without duplicating behavior.
h_path = Path("src/iexamine.h")
hdr = h_path.read_text(encoding="utf-8")
hdr = replace_once(
    hdr,
    '''void reload_furniture( Character &you, const tripoint_bub_ms &examp );
void curtains( Character &you, const tripoint_bub_ms &examp );
''',
    '''void reload_furniture( Character &you, const tripoint_bub_ms &examp );
bool can_tear_down_curtains( Character &you, const tripoint_bub_ms &examp );
void tear_down_curtains( Character &you, const tripoint_bub_ms &examp );
void curtains( Character &you, const tripoint_bub_ms &examp );
''',
    "curtain helper declarations",
)
h_path.write_text(hdr, encoding="utf-8")

iexamine_path = Path("src/iexamine.cpp")
iexamine = iexamine_path.read_text(encoding="utf-8")
marker = '''void iexamine::curtains( Character &you, const tripoint_bub_ms &examp )
{
'''
helpers = '''bool iexamine::can_tear_down_curtains( Character &you, const tripoint_bub_ms &examp )
{
    map &here = get_map();
    const ter_id &ter = here.ter( examp );
    if( !ter->has_curtains() ) {
        return false;
    }

    const bool closed_window_with_curtains = here.has_flag(
                ter_furn_flag::TFLAG_BARRICADABLE_WINDOW_CURTAINS, examp );
    return !( here.is_outside( you.pos_bub() ) &&
              ( here.has_flag( ter_furn_flag::TFLAG_WALL, examp ) ||
                closed_window_with_curtains ) );
}

void iexamine::tear_down_curtains( Character &you, const tripoint_bub_ms &examp )
{
    map &here = get_map();
    const ter_id &ter = here.ter( examp );
    if( !ter->has_curtains() ) {
        return;
    }
    if( !can_tear_down_curtains( you, examp ) ) {
        locked_object( you, examp );
        return;
    }

    here.ter_set( examp, ter->curtain_transform );
    here.spawn_item( you.pos_bub(), itype_nail, 1, 4, calendar::turn );
    here.spawn_item( you.pos_bub(), itype_sheet, 2, 0, calendar::turn );
    here.spawn_item( you.pos_bub(), itype_stick, 1, 0, calendar::turn );
    here.spawn_item( you.pos_bub(), itype_string_36, 1, 0, calendar::turn );
    you.mod_moves( -to_moves<int>( 10_seconds ) );
    you.add_msg_if_player( _( "You tear the curtains and curtain rod off the windowframe." ) );
}

void iexamine::curtains( Character &you, const tripoint_bub_ms &examp )
{
'''
iexamine = replace_once(iexamine, marker, helpers, "insert curtain helpers")
old_teardown = '''    } else if( choice == 1 ) {
        // Mr. Gorbachev, tear down those curtains!
        const ter_id &t = here.ter( examp );
        if( t->has_curtains() ) {
            here.ter_set( examp, t->curtain_transform );
        }

        here.spawn_item( you.pos_bub(), itype_nail, 1, 4, calendar::turn );
        here.spawn_item( you.pos_bub(), itype_sheet, 2, 0, calendar::turn );
        here.spawn_item( you.pos_bub(), itype_stick, 1, 0, calendar::turn );
        here.spawn_item( you.pos_bub(), itype_string_36, 1, 0, calendar::turn );
        you.mod_moves( -to_moves<int>( 10_seconds ) );
        you.add_msg_if_player( _( "You tear the curtains and curtain rod off the windowframe." ) );
'''
new_teardown = '''    } else if( choice == 1 ) {
        tear_down_curtains( you, examp );
'''
iexamine = replace_once(iexamine, old_teardown, new_teardown, "reuse curtain teardown helper")
iexamine_path.write_text(iexamine, encoding="utf-8")


game_path = Path("src/game.cpp")
game = game_path.read_text(encoding="utf-8")

old_open_close = '''    // Use the same interaction predicates as the keyboard action menu wherever possible,
    // but describe the actual world object instead of exposing the generic keybinding text.
    if( is_adjacent && can_interact_at( ACTION_OPEN, here, mouse_target ) ) {
        entries.emplace_back( string_format( _( "Open %s" ), structural_name ),
                              action_ident( ACTION_OPEN ) );
    }
    if( is_adjacent && can_interact_at( ACTION_CLOSE, here, mouse_target ) ) {
        entries.emplace_back( string_format( _( "Close %s" ), structural_name ),
                              action_ident( ACTION_CLOSE ) );
    }

'''
new_open_close = '''    // Open/close describe only the layer that can be changed in the current state.
    // Curtained windows are a small state machine: curtains -> closed window -> open window.
    const ter_id &context_terrain = here.ter( mouse_target );
    const furn_t &context_furniture = here.furn( mouse_target ).obj();
    const bool terrain_has_curtains = context_terrain->has_curtains();
    const bool curtains_block_view = terrain_has_curtains &&
                                     !here.has_flag( ter_furn_flag::TFLAG_TRANSPARENT, mouse_target );
    const bool window_is_open = terrain_has_curtains &&
                                here.has_flag( ter_furn_flag::TFLAG_PERMEABLE, mouse_target );
    const bool can_manage_curtains = is_adjacent && terrain_has_curtains &&
                                     iexamine::can_tear_down_curtains( u, mouse_target );

    if( is_adjacent && can_interact_at( ACTION_OPEN, here, mouse_target ) ) {
        const std::string open_label = terrain_has_curtains ?
                                       ( curtains_block_view ? _( "Open curtains" ) : _( "Open window" ) ) :
                                       string_format( _( "Open %s" ), structural_name );
        entries.emplace_back( open_label, action_ident( ACTION_OPEN ) );
    }
    if( is_adjacent && can_interact_at( ACTION_CLOSE, here, mouse_target ) ) {
        const std::string close_label = terrain_has_curtains ?
                                        ( window_is_open ? _( "Close window" ) : _( "Close curtains" ) ) :
                                        string_format( _( "Close %s" ), structural_name );
        entries.emplace_back( close_label, action_ident( ACTION_CLOSE ) );
    }

    if( can_manage_curtains ) {
        const bool can_peek_through_curtains =
            !context_terrain.obj().close &&
            here.has_flag( ter_furn_flag::TFLAG_BARRICADABLE_WINDOW_CURTAINS, mouse_target );
        if( can_peek_through_curtains ) {
            entries.emplace_back( _( "Peek through curtains" ), "CONTEXT_CURTAIN_PEEK" );
        }
        entries.emplace_back( _( "Tear down curtains" ), "CONTEXT_CURTAIN_TEAR_DOWN" );
    }

'''
game = replace_once(game, old_open_close, new_open_close, "state-aware open/close layer")

old_examine = '''    if( is_adjacent && can_interact_at( ACTION_EXAMINE, here, mouse_target ) ) {
        const std::string examine_name = visible_creature ? creature_name : structural_name;
        entries.emplace_back( string_format( _( "Examine %s" ), examine_name ),
                              action_ident( ACTION_EXAMINE ) );
    }
'''
new_examine = '''    // `examine_action` is historically the primary terrain/furniture interaction callback,
    // not an information action.  Keep that implementation, but expose it under a semantic
    // verb (or a neutral Use fallback) and reserve Inspect for information only.
    const map_data_common_t *context_examine_data = nullptr;
    if( here.has_furn( mouse_target ) && context_furniture.can_examine( mouse_target ) ) {
        context_examine_data = &context_furniture;
    } else if( context_terrain->can_examine( mouse_target ) ) {
        context_examine_data = &context_terrain.obj();
    }

    const auto examine_use_label = [&]( const map_data_common_t &data ) -> std::string {
        if( data.has_examine( iexamine::reload_furniture ) ) {
            return string_format( _( "Reload %s" ), structural_name );
        }
        if( data.has_examine( iexamine::rubble ) ) {
            return string_format( _( "Clear %s" ), structural_name );
        }
        if( data.has_examine( iexamine::portable_structure ) ) {
            return string_format( _( "Take down %s" ), structural_name );
        }
        if( data.has_examine( iexamine::door_peephole ) ) {
            return string_format( _( "Look through %s" ), structural_name );
        }
        if( data.has_examine( iexamine::sign ) ) {
            return string_format( _( "Read %s" ), structural_name );
        }
        if( data.has_examine( iexamine::controls_gate ) || data.has_examine( iexamine::fswitch ) ) {
            return string_format( _( "Operate %s" ), structural_name );
        }
        if( data.has_examine( iexamine::workout ) ) {
            return string_format( _( "Exercise using %s" ), structural_name );
        }
        if( data.has_examine( iexamine::clear_overgrown ) ) {
            return string_format( _( "Clear %s" ), structural_name );
        }
        if( data.has_examine( iexamine::harvest_furn ) ||
            data.has_examine( iexamine::harvest_furn_nectar ) ||
            data.has_examine( iexamine::harvest_ter ) ||
            data.has_examine( iexamine::harvest_ter_nectar ) ||
            data.has_examine( iexamine::harvest_plant_ex ) ||
            data.has_examine( iexamine::aggie_plant ) ||
            data.has_examine( iexamine::shrub_wildveggies ) ) {
            return string_format( _( "Harvest %s" ), structural_name );
        }
        return string_format( _( "Use %s" ), structural_name );
    };

    bool has_context_use = false;
    std::string context_use_label;
    if( is_adjacent && !can_manage_curtains ) {
        if( visible_creature && !hostile_creature && guy == nullptr ) {
            context_use_label = string_format( _( "Interact with %s" ), creature_name );
            has_context_use = true;
        } else if( here.veh_at( mouse_target ) ) {
            context_use_label = string_format( _( "Interact with %s" ), structural_name );
            has_context_use = true;
        } else if( here.has_flag( ter_furn_flag::TFLAG_CONSOLE, mouse_target ) ) {
            context_use_label = string_format( _( "Use %s" ), structural_name );
            has_context_use = true;
        } else if( context_examine_data != nullptr ) {
            context_use_label = examine_use_label( *context_examine_data );
            has_context_use = true;
        } else if( here.partial_con_at( mouse_target ) != nullptr ) {
            context_use_label = _( "Work on unfinished construction" );
            has_context_use = true;
        } else if( here.can_see_trap_at( mouse_target, u ) ) {
            context_use_label = _( "Interact with trap" );
            has_context_use = true;
        }
    }
    if( has_context_use ) {
        entries.emplace_back( context_use_label, "CONTEXT_USE_EXAMINE" );
    }

    const bool has_inspectable_world_object = is_adjacent &&
            ( visible_creature || here.has_furn( mouse_target ) || here.veh_at( mouse_target ) ||
              here.has_flag( ter_furn_flag::TFLAG_CONSOLE, mouse_target ) ||
              context_examine_data != nullptr || here.partial_con_at( mouse_target ) != nullptr ||
              here.can_see_trap_at( mouse_target, u ) );
    if( has_inspectable_world_object ) {
        const std::string inspect_name = visible_creature ? creature_name : structural_name;
        entries.emplace_back( string_format( _( "Inspect %s" ), inspect_name ), "CONTEXT_INSPECT" );
    }
'''
game = replace_once(game, old_examine, new_examine, "split examine into use and inspect")

activation_marker = '''        if( result.entry->id == "CONTEXT_TALK" ) {
'''
activation = '''        if( result.entry->id == "CONTEXT_CURTAIN_PEEK" ) {
            context_menu.close();
            if( can_manage_curtains ) {
                peek( mouse_target );
                u.add_msg_if_player( _( "You carefully peek through the curtains." ) );
            }
            return false;
        }
        if( result.entry->id == "CONTEXT_CURTAIN_TEAR_DOWN" ) {
            context_menu.close();
            iexamine::tear_down_curtains( u, mouse_target );
            return false;
        }
        if( result.entry->id == "CONTEXT_USE_EXAMINE" ) {
            context_menu.close();
            examine( mouse_target, false );
            return false;
        }
        if( result.entry->id == "CONTEXT_INSPECT" ) {
            context_menu.close();
            tripoint_bub_ms inspect_target = mouse_target;
            extended_description_window ext_desc( inspect_target );
            ext_desc.show();
            return false;
        }

        if( result.entry->id == "CONTEXT_TALK" ) {
'''
game = replace_once(game, activation_marker, activation, "activate semantic examine actions")

game_path.write_text(game, encoding="utf-8")

# Sanity: the mouse context must no longer emit the old ACTION_EXAMINE entry.
assert 'string_format( _( "Examine %s" ), examine_name )' not in game
assert '"CONTEXT_USE_EXAMINE"' in game
assert '"CONTEXT_INSPECT"' in game
assert '"Tear down curtains"' in game

Path("/tmp/branch_patch_commit_message").write_text(
    "Separate world inspection from interaction\n", encoding="utf-8"
)
