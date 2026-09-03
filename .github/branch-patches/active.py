from pathlib import Path

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
start = text.index("bool game::try_get_right_click_action( action_id &act, const tripoint_bub_ms &mouse_target )")
end = text.index("\nbool game::is_game_over()", start)
old = text[start:end]
if "WORLD_CONTEXT_MENU" in old:
    raise SystemExit("world context menu is already installed")

new = r'''bool game::try_get_right_click_action( action_id &act, const tripoint_bub_ms &mouse_target )
{
    map &here = get_map();

    const bool cleared_destination = !destination_preview.empty();
    u.clear_destination();
    destination_preview.clear();

    if( cleared_destination ) {
        // Preserve the existing right-click cancel behavior for a pending mouse route.
        return false;
    }

    const tripoint_bub_ms player_pos = u.pos_bub( here );
    const int distance = square_dist( mouse_target.xy(), player_pos.xy() );
    const bool is_adjacent = distance <= 1;
    const bool is_self = distance == 0;
    const Creature *const creature = get_creature_tracker().creature_at( mouse_target );
    const monster *const mon = dynamic_cast<const monster *>( creature );
    const bool visible_creature = creature != nullptr && !creature->is_avatar() && u.sees( here, *creature );

    std::vector<ui_dropdown_entry> entries;
    const input_context action_names = get_default_mode_input_context();
    const auto add_action = [&]( const action_id action ) {
        entries.emplace_back( action_names.get_action_name( action_ident( action ) ),
                              action_ident( action ) );
    };

    // Creature actions come first because they describe the most specific thing under the pointer.
    if( visible_creature && is_adjacent ) {
        entries.emplace_back( _( "Attack" ), "CONTEXT_ATTACK" );
    }
    if( mon != nullptr && u.sees( here, *mon ) && u.get_wielded_item() &&
        u.get_wielded_item()->is_gun() ) {
        add_action( ACTION_FIRE );
    }

    // Use the same interaction predicates as the keyboard action menu wherever possible.
    if( is_adjacent && can_interact_at( ACTION_OPEN, here, mouse_target ) ) {
        add_action( ACTION_OPEN );
    }
    if( is_adjacent && can_interact_at( ACTION_CLOSE, here, mouse_target ) ) {
        add_action( ACTION_CLOSE );
    }
    if( is_adjacent && can_interact_at( ACTION_EXAMINE, here, mouse_target ) ) {
        add_action( ACTION_EXAMINE );
    }
    if( is_adjacent && can_interact_at( ACTION_PICKUP, here, mouse_target ) ) {
        add_action( ACTION_PICKUP );
    }
    if( is_adjacent && !is_self &&
        ( here.is_bashable( mouse_target ) || here.veh_at( mouse_target ).obstacle_at_part() ) ) {
        add_action( ACTION_SMASH );
    }

    // These actions are implemented by the normal action handlers on the player's own square.
    if( is_self && can_interact_at( ACTION_BUTCHER, here, mouse_target ) ) {
        add_action( ACTION_BUTCHER );
    }
    if( is_self && can_interact_at( ACTION_MOVE_UP, here, mouse_target ) ) {
        add_action( ACTION_MOVE_UP );
    }
    if( is_self && can_interact_at( ACTION_MOVE_DOWN, here, mouse_target ) ) {
        add_action( ACTION_MOVE_DOWN );
    }

    // Preflight pathfinding so an unreachable square does not advertise a bogus Move to action.
    std::optional<std::vector<tripoint_bub_ms>> move_route;
    if( !is_self && creature == nullptr ) {
        move_route = safe_route_to( u, mouse_target, 0, []( const std::string & ) {} );
        if( move_route ) {
            entries.emplace_back( _( "Move to" ), "CONTEXT_MOVE_TO" );
        }
    }

    if( entries.empty() ) {
        add_msg( _( "Nothing relevant here." ) );
        return false;
    }

    // ui_dropdown is the shared mouse-first context-menu helper.  Anchor it to the clicked
    // map square in screen coordinates and let the helper handle clamping, hover and input.
    const point terrain_anchor = mouse_target.xy().raw() - ter_view_p.xy().raw() + point( POSX, POSY );
    const point anchor = terrain_anchor + point( getbegx( w_terrain ), getbegy( w_terrain ) );

    ui_dropdown context_menu;
    ui_dropdown_style style;
    style.border = c_light_gray;
    style.text = c_light_gray;
    style.highlight = h_light_gray;
    style.selected = c_white;

    input_context ctxt( "WORLD_CONTEXT_MENU" );
    for( const std::string &menu_action : { "UP", "DOWN", "PAGE_UP", "PAGE_DOWN", "HOME", "END",
                                           "CONFIRM", "QUIT", "SELECT", "SEC_SELECT", "MOUSE_MOVE",
                                           "SCROLL_UP", "SCROLL_DOWN" } ) {
        ctxt.register_action( menu_action );
    }

    ui_adaptor ui( ui_adaptor::disable_uis_below{} );
    ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
        adaptor.position_from_window( catacurses::stdscr );
        context_menu.configure( catacurses::stdscr, anchor, entries, 0, style );
    } );
    ui.mark_resize();
    ui.on_redraw( [&]( ui_adaptor & adaptor ) {
        context_menu.draw( catacurses::stdscr );
        adaptor.disable_cursor();
    } );

    while( true ) {
        ui_manager::redraw();
        if( !context_menu.is_open() ) {
            return false;
        }

        const std::string menu_action = ctxt.handle_input();
        const std::optional<point> pos = ctxt.get_coordinates_text( catacurses::stdscr );
        const ui_action_result result = context_menu.handle_input( menu_action, pos, true,
                                        ui_outside_click_policy::consume, std::nullopt, &ctxt );
        if( result.type == ui_action_result_type::closed ) {
            return false;
        }
        if( result.type != ui_action_result_type::activated || !result.entry ) {
            continue;
        }

        if( result.entry->id == "CONTEXT_MOVE_TO" ) {
            if( !move_route ) {
                return false;
            }
            u.set_destination( *move_route );
            act = u.get_next_auto_move_direction();
            if( act == ACTION_NULL ) {
                u.clear_destination();
                return false;
            }
            return true;
        }

        if( result.entry->id == "CONTEXT_ATTACK" ) {
            const tripoint_rel_ms delta = mouse_target - player_pos;
            act = get_movement_action_from_delta( delta, iso_rotate::yes );
            return act != ACTION_NULL;
        }

        act = look_up_action( result.entry->id );
        return act != ACTION_NULL;
    }
}
'''

path.write_text(text[:start] + new + text[end:], encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Add contextual world right-click menu\n", encoding="utf-8"
)
