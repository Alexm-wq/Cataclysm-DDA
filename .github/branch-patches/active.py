from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


# Keep the legacy NPC interaction implementation, but let the mouse context menu
# promote immediate spatial actions while opening a filtered Interact submenu for
# the slower character-management operations.
h_path = Path("src/game.h")
hdr = h_path.read_text(encoding="utf-8")
hdr = replace_once(
    hdr,
    '''        /** Returns true if the menu handled stuff and player shouldn't do anything else */
        bool npc_menu( npc &who );
''',
    '''        enum class npc_menu_mode : int {
            full,
            context_interact,
            swap,
            push
        };
        /** Returns true if the menu handled stuff and player shouldn't do anything else */
        bool npc_menu( npc &who, npc_menu_mode mode = npc_menu_mode::full );
''',
    "npc menu mode declaration",
)
h_path.write_text(hdr, encoding="utf-8")


game_path = Path("src/game.cpp")
game = game_path.read_text(encoding="utf-8")

game = replace_once(
    game,
    '''bool game::npc_menu( npc &who )
{
''',
    '''bool game::npc_menu( npc &who, const npc_menu_mode mode )
{
''',
    "npc menu signature",
)

game = replace_once(
    game,
    '''    uilist amenu;
    amenu.text = string_format( _( "What to do with %s?" ), who.disp_name() );
    amenu.addentry( talk, true, 't', _( "Talk" ) );
    amenu.addentry( swap_pos, obeys && !who.is_mounted() &&
                    !u.is_mounted(), 's', _( "Swap positions" ) );
    amenu.addentry( push, ( debug_mode || ( !who.is_enemy() && !who.in_sleep_state() ) ) &&
                    !who.is_mounted(), 'p', _( "Push away" ) );
    amenu.addentry( examine_wounds, true, 'w', _( "Examine wounds" ) );
    amenu.addentry( examine_status, true, 'e', _( "Examine status" ) );
    amenu.addentry( use_item, true, 'i', _( "Use item on" ) );
    amenu.addentry( sort_armor, true, 'r', _( "Sort armor" ) );
    amenu.addentry( attack, true, 'a', _( "Attack" ) );
''',
    '''    uilist amenu;
    amenu.text = mode == npc_menu_mode::context_interact ?
                 string_format( _( "Interact with %s" ), who.disp_name() ) :
                 string_format( _( "What to do with %s?" ), who.disp_name() );
    if( mode == npc_menu_mode::full ) {
        amenu.addentry( talk, true, 't', _( "Talk" ) );
        amenu.addentry( swap_pos, obeys && !who.is_mounted() &&
                        !u.is_mounted(), 's', _( "Swap positions" ) );
        amenu.addentry( push, ( debug_mode || ( !who.is_enemy() && !who.in_sleep_state() ) ) &&
                        !who.is_mounted(), 'p', _( "Push away" ) );
    }
    amenu.addentry( examine_wounds, true, 'w', _( "Examine wounds" ) );
    amenu.addentry( examine_status, true, 'e', _( "Examine status" ) );
    amenu.addentry( use_item, true, 'i', mode == npc_menu_mode::context_interact ?
                    _( "Treat wounds…" ) : _( "Use item on" ) );
    amenu.addentry( sort_armor, true, 'r', _( "Sort armor" ) );
    if( mode == npc_menu_mode::full ) {
        amenu.addentry( attack, true, 'a', _( "Attack" ) );
    }
''',
    "filter npc submenu quick actions",
)

game = replace_once(
    game,
    '''    amenu.query();

    const int choice = amenu.ret;
''',
    '''    int choice = -1;
    if( mode == npc_menu_mode::swap ) {
        choice = swap_pos;
    } else if( mode == npc_menu_mode::push ) {
        choice = push;
    } else {
        amenu.query();
        choice = amenu.ret;
    }
''',
    "direct npc menu actions",
)

old_context_creature = '''    // Creature actions come first because they describe the most specific thing under the pointer.
    if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
        entries.emplace_back( string_format( _( "Talk to %s" ), guy->get_name() ),
                              "CONTEXT_TALK" );
    }
'''
new_context_creature = '''    // Creature actions come first because they describe the most specific thing under the pointer.
    // Keep immediate spatial actions at the first level; slower character-management
    // operations live under the filtered Interact submenu.
    if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
        entries.emplace_back( string_format( _( "Talk to %s" ), guy->get_name() ),
                              "CONTEXT_TALK" );
        const bool npc_can_swap = ( debug_mode || ( guy->is_friendly( u ) && !guy->in_sleep_state() ) ) &&
                                  !guy->is_mounted() && !u.is_mounted();
        const bool npc_can_push = ( debug_mode || ( !guy->is_enemy() && !guy->in_sleep_state() ) ) &&
                                  !guy->is_mounted();
        if( npc_can_swap ) {
            entries.emplace_back( _( "Swap positions" ), "CONTEXT_NPC_SWAP" );
        }
        if( npc_can_push ) {
            entries.emplace_back( _( "Push away" ), "CONTEXT_NPC_PUSH" );
        }
        entries.emplace_back( string_format( _( "Interact with %s…" ), guy->get_name() ),
                              "CONTEXT_NPC_INTERACT" );
    }
'''
game = replace_once(game, old_context_creature, new_context_creature,
                    "npc context hierarchy")

old_talk_activation = '''        if( result.entry->id == "CONTEXT_TALK" ) {
            context_menu.close();
            if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
                u.talk_to( get_talker_for( *guy ) );
            }
            return false;
        }

'''
new_talk_activation = '''        if( result.entry->id == "CONTEXT_TALK" ) {
            context_menu.close();
            if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
                u.talk_to( get_talker_for( *guy ) );
            }
            return false;
        }
        if( result.entry->id == "CONTEXT_NPC_SWAP" ) {
            context_menu.close();
            if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
                npc_menu( *guy, npc_menu_mode::swap );
            }
            return false;
        }
        if( result.entry->id == "CONTEXT_NPC_PUSH" ) {
            context_menu.close();
            if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
                npc_menu( *guy, npc_menu_mode::push );
            }
            return false;
        }
        if( result.entry->id == "CONTEXT_NPC_INTERACT" ) {
            context_menu.close();
            if( guy != nullptr && visible_creature && is_adjacent && !hostile_creature ) {
                npc_menu( *guy, npc_menu_mode::context_interact );
            }
            return false;
        }

'''
game = replace_once(game, old_talk_activation, new_talk_activation,
                    "npc context activation")

game_path.write_text(game, encoding="utf-8")

assert 'CONTEXT_NPC_INTERACT' in game
assert 'CONTEXT_NPC_SWAP' in game
assert 'CONTEXT_NPC_PUSH' in game
assert 'Treat wounds…' in game
assert 'bool game::npc_menu( npc &who, const npc_menu_mode mode )' in game

Path("/tmp/branch_patch_commit_message").write_text(
    "Group NPC context interactions\n", encoding="utf-8"
)
