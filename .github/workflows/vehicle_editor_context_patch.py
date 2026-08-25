from pathlib import Path

cpp_path = Path("src/veh_interact.cpp")
hdr_path = Path("src/veh_interact.h")
cpp = cpp_path.read_text()
hdr = hdr_path.read_text()


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_function(text, signature, replacement):
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"function signature not found: {signature}")
    brace = text.find("{", start + len(signature))
    if brace < 0:
        raise RuntimeError(f"opening brace not found: {signature}")
    depth = 0
    i = brace
    in_string = False
    in_char = False
    escape = False
    line_comment = False
    block_comment = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if in_char:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
        elif ch == "'":
            in_char = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                return text[:start] + replacement.rstrip() + text[end:]
        i += 1
    raise RuntimeError(f"unbalanced function: {signature}")


hdr = replace_once(
    hdr,
    """        enum class editor_dropdown {
            none,
            system,
            condition
        };
""",
    """        enum class editor_dropdown {
            none,
            system,
            condition
        };
        enum class editor_context_surface {
            none,
            viewport,
            parts
        };
""",
    "context surface enum",
)
hdr = replace_once(
    hdr,
    """        bool editor_context_open = false;
        point editor_context_anchor = point::zero;
""",
    """        bool editor_context_open = false;
        editor_context_surface editor_context_target = editor_context_surface::none;
        point editor_context_anchor = point::zero;
""",
    "context target state",
)
hdr = replace_once(
    hdr,
    "        void open_editor_context_menu( map &here, const point &pos );\n",
    "        void open_editor_context_menu( map &here, const point &pos, editor_context_surface surface );\n",
    "context menu declaration",
)

cpp = replace_once(
    cpp,
    "    const int ghost_symbol = '#';\n",
    "    const int ghost_symbol = 0x25A1; // U+25A1 WHITE SQUARE: occupied mount hidden by this view.\n",
    "filtered mount glyph",
)

cpp = replace_function(
    cpp,
    "void veh_interact::close_editor_context_menu()",
    r'''void veh_interact::close_editor_context_menu()
{
    editor_context_open = false;
    editor_context_target = editor_context_surface::none;
    editor_context_buttons.clear();
    editor_context_width = 0;
    editor_context_height = 0;
}''',
)

cpp = replace_function(
    cpp,
    "void veh_interact::open_editor_context_menu( map &here, const point &pos )",
    r'''void veh_interact::open_editor_context_menu( map &here, const point &pos,
        const editor_context_surface surface )
{
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    editor_context_target = surface;
    editor_context_anchor = pos;
    editor_mouse_pos = pos;

    const auto add_entry = [&]( const std::string &label, const std::string &action,
                                const bool enabled = true,
                                const std::string &disabled_reason = std::string() ) {
        editor_context_buttons.push_back( { label, point::zero, 0, action, disabled_reason, enabled } );
    };

    if( surface == editor_context_surface::viewport ) {
        const bool has_install_for_layer = std::any_of( can_mount.begin(), can_mount.end(),
        [&]( const vpart_info *info ) {
            return info != nullptr && part_info_matches_layer( *info );
        } );
        add_entry( _( "Install…" ), "EDITOR_INSTALL", has_install_for_layer,
                   _( "No parts for the selected layer can be installed at this mount." ) );
    } else if( surface == editor_context_surface::parts && selected_part >= 0 &&
               selected_part < veh->part_count() ) {
        vehicle_part &part = veh->part( selected_part );
        if( !part.removed && part.mount == selected_mount() ) {
            if( part.health_percent() < 0.999 ) {
                if( part.is_broken() ) {
                    add_entry( _( "Replace" ), "EDITOR_REPAIR" );
                } else {
                    add_entry( _( "Repair" ), "EDITOR_REPAIR", part.is_repairable(),
                               _( "This damaged part has no valid repair operation." ) );
                }
            }

            const vpart_info &vpi = part.info();
            const bool uninstallable = !vpi.has_flag( "NO_UNINSTALL" ) &&
                                       veh->can_unmount( part ).success();
            add_entry( _( "Remove" ), "EDITOR_REMOVE", uninstallable,
                       uninstallable ? std::string() :
                       _( "This part cannot be removed in the current vehicle state." ) );
        }
    }

    if( editor_context_buttons.empty() ) {
        close_editor_context_menu();
        return;
    }
    editor_context_open = true;

    const catacurses::window &target = surface == editor_context_surface::parts ? w_parts : w_disp;
    const int target_width = getmaxx( target );
    const int target_height = getmaxy( target );
    int widest = 0;
    for( const editor_context_button &button : editor_context_buttons ) {
        widest = std::max( widest, utf8_width( button.label ) );
    }
    editor_context_width = std::clamp( widest + 4, 12, std::max( 12, target_width - 2 ) );
    editor_context_height = std::min( static_cast<int>( editor_context_buttons.size() ) + 2,
                                      std::max( 3, target_height ) );
    if( static_cast<int>( editor_context_buttons.size() ) > editor_context_height - 2 ) {
        editor_context_buttons.resize( editor_context_height - 2 );
    }

    int menu_x = pos.x + 2;
    if( menu_x + editor_context_width >= target_width ) {
        menu_x = pos.x - editor_context_width - 1;
    }
    menu_x = std::clamp( menu_x, 0, std::max( 0, target_width - editor_context_width ) );

    const int min_y = surface == editor_context_surface::viewport ? editor_viewport_top() : 0;
    int menu_y = pos.y;
    if( menu_y + editor_context_height > target_height ) {
        menu_y = target_height - editor_context_height;
    }
    menu_y = std::clamp( menu_y, min_y,
                         std::max( min_y, target_height - editor_context_height ) );
    editor_context_pos = point( menu_x, menu_y );
}''',
)

cpp = replace_function(
    cpp,
    "bool veh_interact::run_editor_context_action( map &here, const std::string &action )",
    r'''bool veh_interact::run_editor_context_action( map &here, const std::string &action )
{
    close_editor_context_menu();

    if( action == "EDITOR_INSTALL" ) {
        if( veh->handle_potential_theft( get_player_character() ) ) {
            do_install( here );
        }
        return sel_cmd == ' ';
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return true;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return true;
    }
    if( !veh->handle_potential_theft( get_player_character() ) ) {
        return true;
    }

    avatar &player_character = get_avatar();

    if( action == "EDITOR_REMOVE" ) {
        const task_reason reason = cant_do( here, 'o' );
        switch( reason ) {
            case task_reason::LOW_MORALE:
                msg = _( "Your morale is too low to construct…" );
                return true;
            case task_reason::LOW_LIGHT:
                msg = _( "It's too dark to see what you are doing…" );
                return true;
            case task_reason::MOVING_VEHICLE:
                msg = _( "Better not remove something while driving." );
                return true;
            default:
                break;
        }

        // can_remove_part validates the exact stacked part selected in the inspector;
        // cant_do('o') only knows about the mount's legacy displayed part.
        if( !can_remove_part( here, selected_part, player_character ) ) {
            return true;
        }
        if( veh->would_removal_prevent_flyable( part, player_character ) ) {
            if( query_yn(
                    _( "Removing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
                veh->set_flyable( false );
            } else {
                return true;
            }
        }
        for( const Character *helper : player_character.get_crafting_helpers() ) {
            add_msg( m_info, _( "%s helps with this task…" ), helper->get_name() );
        }
        sel_vehicle_part = &part;
        sel_vpart_info = &part.info();
        sel_cmd = 'o';
        veh->recalculate_enchantment_cache();
        return false;
    }

    if( action == "EDITOR_REPAIR" ) {
        const task_reason reason = cant_do( here, 'r' );
        switch( reason ) {
            case task_reason::LOW_MORALE:
                msg = _( "Your morale is too low to repair…" );
                return true;
            case task_reason::LOW_LIGHT:
                msg = _( "It's too dark to see what you are doing…" );
                return true;
            case task_reason::MOVING_VEHICLE:
                msg = _( "You can't repair stuff while driving." );
                return true;
            case task_reason::INVALID_TARGET:
                msg = _( "This part does not need repair." );
                return true;
            default:
                break;
        }

        const vpart_info &vpi = part.info();
        std::string nmsg;
        bool ok = true;
        if( part.is_broken() ) {
            ok = format_reqs( nmsg, vpi.install_requirements(), vpi.install_skills,
                              vpi.install_time( player_character ) );
            if( vpi.has_flag( "NEEDS_JACKING" ) ) {
                nmsg += _( "<color_white>Additional requirements:</color>\n" );
                const std::pair<bool, std::string> res = calc_lift_requirements( here, vpi );
                ok = ok && res.first;
                nmsg += res.second;
            }
            if( part.has_flag( vp_flag::carried_flag ) ) {
                nmsg += colorize( _( "\nUnracking is required before replacing this part.\n" ), c_red );
                ok = false;
            }
        } else if( !part.is_repairable() ) {
            nmsg += colorize( _( "This part cannot be repaired.\n" ), c_light_red );
            ok = false;
        } else if( veh->has_part( "NO_MODIFY_VEHICLE" ) && !vpi.has_flag( "SIMPLE_PART" ) ) {
            nmsg += colorize( _( "This vehicle cannot be repaired.\n" ), c_light_red );
            ok = false;
        } else {
            const int levels = part.base.repairable_levels();
            ok = format_reqs( nmsg, vpi.repair_requirements() * levels, vpi.repair_skills,
                              vpi.repair_time( player_character ) * levels );
        }

        const bool would_prevent_flying = veh->would_repair_prevent_flyable( part, player_character );
        if( would_prevent_flying &&
            !player_character.has_proficiency( proficiency_prof_aircraft_mechanic ) ) {
            nmsg += string_format(
                        _( "\n<color_yellow>You require the \"%s\" proficiency to repair this part safely!</color>\n\n" ),
                        proficiency_prof_aircraft_mechanic->name() );
        }
        const nc_color desc_color = part.is_broken() ? c_dark_gray : c_light_gray;
        vpi.format_description( nmsg, desc_color, getmaxx( w_msg ) - 4 );
        msg = colorize( nmsg, c_light_gray );
        if( !ok ) {
            return true;
        }

        if( would_prevent_flying ) {
            if( query_yn(
                    _( "Repairing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
                veh->set_flyable( false );
            } else {
                return true;
            }
        }
        sel_vehicle_part = &part;
        sel_vpart_info = &vpi;
        for( const Character *helper : player_character.get_crafting_helpers() ) {
            add_msg( m_info, _( "%s helps with this task…" ), helper->get_name() );
        }
        sel_cmd = 'r';
        return false;
    }

    return true;
}''',
)

cpp = replace_function(
    cpp,
    "void veh_interact::display_editor_context_menu()",
    r'''void veh_interact::display_editor_context_menu()
{
    if( !editor_context_open || editor_context_target == editor_context_surface::none ||
        editor_context_width <= 0 || editor_context_height < 3 ) {
        return;
    }

    catacurses::window &target = editor_context_target == editor_context_surface::parts ? w_parts : w_disp;
    const std::string blank( editor_context_width, ' ' );
    for( int row = 0; row < editor_context_height; ++row ) {
        mvwprintz( target, editor_context_pos + point( 0, row ), c_black, "%s", blank );
    }
    mvwhline( target, editor_context_pos, c_light_gray, LINE_OXOX, editor_context_width );
    mvwhline( target, editor_context_pos + point( 0, editor_context_height - 1 ), c_light_gray,
              LINE_OXOX, editor_context_width );
    mvwvline( target, editor_context_pos, c_light_gray, LINE_XOXO, editor_context_height );
    mvwvline( target, editor_context_pos + point( editor_context_width - 1, 0 ), c_light_gray,
              LINE_XOXO, editor_context_height );
    mvwputch( target, editor_context_pos, c_light_gray, LINE_OXXO );
    mvwputch( target, editor_context_pos + point( editor_context_width - 1, 0 ), c_light_gray, LINE_OOXX );
    mvwputch( target, editor_context_pos + point( 0, editor_context_height - 1 ), c_light_gray, LINE_XXOO );
    mvwputch( target, editor_context_pos + point( editor_context_width - 1,
             editor_context_height - 1 ), c_light_gray, LINE_XOOX );

    for( int row = 0; row < static_cast<int>( editor_context_buttons.size() ); ++row ) {
        editor_context_button &button = editor_context_buttons[row];
        button.pos = editor_context_pos + point( 1, row + 1 );
        button.width = editor_context_width - 2;
        const bool hovered = editor_mouse_pos.y == button.pos.y &&
                             editor_mouse_pos.x >= button.pos.x &&
                             editor_mouse_pos.x < button.pos.x + button.width;
        const nc_color color = !button.enabled ? c_dark_gray : hovered ? h_green : c_light_green;
        trim_and_print( target, button.pos, button.width, color, button.label );
    }
    wnoutrefresh( target );
}''',
)

cpp = replace_function(
    cpp,
    "bool veh_interact::handle_editor_mouse( map &here, const std::string &action )",
    r'''bool veh_interact::handle_editor_mouse( map &here, const std::string &action )
{
    // get_coordinates_text() deliberately returns coordinates outside a window in
    // the tiles build, so pane routing must bounds-check the relative position.
    const auto mouse_pos_in = [&]( const catacurses::window & win ) -> std::optional<point> {
        const std::optional<point> pos = main_context.get_coordinates_text( win );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( win ) ||
            pos->y >= getmaxy( win ) ) {
            return std::nullopt;
        }
        return pos;
    };

    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );
    const std::optional<point> parts_pos = mouse_pos_in( w_parts );
    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_viewport_content = viewport_pos && viewport_pos->y >= editor_viewport_top();

    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    } else if( editor_context_target == editor_context_surface::parts && parts_pos ) {
        editor_mouse_pos = *parts_pos;
    } else if( viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    }

#if defined(TILES)
    const bool middle_mouse_down = is_middle_mouse_button_down();
    const bool mouse_focused = has_sdl_mouse_focus();
    if( viewport_dragging && ( !middle_mouse_down || !mouse_focused ) ) {
        viewport_dragging = false;
        set_sdl_mouse_capture( false );
    }
    if( action == "MOUSE_MOVE" && !viewport_dragging && middle_mouse_down && mouse_focused &&
        over_viewport_content && open_editor_dropdown == editor_dropdown::none && !editor_context_open ) {
        viewport_dragging = true;
        viewport_drag_anchor = *viewport_pos;
        viewport_drag_pan_origin = viewport_pan;
        set_sdl_mouse_capture( true );
        return true;
    }
#endif

    if( action == "CAMERA_PAN_START" ) {
        if( over_viewport_content && open_editor_dropdown == editor_dropdown::none && !editor_context_open ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        return false;
    }
    if( action == "CAMERA_PAN_END" ) {
        if( viewport_dragging ) {
            viewport_dragging = false;
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            return true;
        }
#if defined(TILES)
        set_sdl_mouse_capture( false );
#endif
        return false;
    }
    if( action == "MOUSE_MOVE" && viewport_dragging ) {
        if( viewport_pos ) {
            viewport_pan = viewport_drag_pan_origin + ( *viewport_pos - viewport_drag_anchor );
            clamp_viewport_pan();
        }
        return true;
    }

    if( action == "SEC_SELECT" && !install_info && !remove_info ) {
        close_editor_context_menu();

        if( parts_pos ) {
            if( parts_pos->y >= 3 ) {
                const std::vector<int> parts = inspector_parts();
                const int row = part_scroll + parts_pos->y - 3;
                if( row >= 0 && row < static_cast<int>( parts.size() ) ) {
                    selected_part = parts[row];
                    part_detail_scroll = 0;
                    open_editor_context_menu( here, *parts_pos, editor_context_surface::parts );
                }
            }
            return true;
        }

        if( over_viewport_content ) {
            if( const std::optional<point_rel_ms> mount = viewport_to_mount( *viewport_pos ) ) {
                select_mount( here, *mount );
                // A viewport context action is deliberately limited to a physically empty
                // mount. Occupied mounts are manipulated from the exact part row in the inspector.
                if( veh->parts_at_relative( *mount, true, false ).empty() ) {
                    open_editor_context_menu( here, *viewport_pos, editor_context_surface::viewport );
                }
            }
            return true;
        }
        return false;
    }

    if( action == "SELECT" && !install_info && !remove_info ) {
        if( editor_context_open ) {
            if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
                return handle_editor_context_click( here, *viewport_pos );
            }
            if( editor_context_target == editor_context_surface::parts && parts_pos ) {
                return handle_editor_context_click( here, *parts_pos );
            }
            close_editor_context_menu();
            return true;
        }
        if( viewport_pos && handle_editor_controls_click( *viewport_pos ) ) {
            return true;
        }
        if( open_editor_dropdown != editor_dropdown::none ) {
            open_editor_dropdown = editor_dropdown::none;
            return true;
        }
        if( viewport_pos ) {
            if( const std::optional<point_rel_ms> mount = viewport_to_mount( *viewport_pos ) ) {
                select_mount( here, *mount );
            }
            return true;
        }
        if( parts_pos && parts_pos->y >= 3 ) {
            const std::vector<int> parts = inspector_parts();
            const int row = part_scroll + parts_pos->y - 3;
            if( row >= 0 && row < static_cast<int>( parts.size() ) ) {
                selected_part = parts[row];
                part_detail_scroll = 0;
            }
            return true;
        }
    }

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        if( open_editor_dropdown != editor_dropdown::none || editor_context_open ) {
            return true;
        }
        const int direction = action == "SCROLL_UP" ? -1 : 1;
        if( !install_info && !remove_info && parts_pos ) {
            scroll_part_inspector( direction );
            return true;
        }
        if( !install_info && !remove_info && details_pos ) {
            scroll_part_details( direction );
            return true;
        }
        if( over_viewport_content ) {
            const std::optional<point_rel_ms> anchor = viewport_to_mount( *viewport_pos );
            const int old_zoom = viewport_zoom;
            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 3 );
            if( viewport_zoom != old_zoom && anchor ) {
                const point after = mount_to_viewport( *anchor );
                viewport_pan += *viewport_pos - after;
                clamp_viewport_pan();
            }
            return true;
        }
    }

    return false;
}''',
)

cpp = replace_once(
    cpp,
    "    display_editor_controls();\n    display_editor_context_menu();\n    wnoutrefresh( w_disp );\n",
    "    display_editor_controls();\n    wnoutrefresh( w_disp );\n",
    "move context overlay out of viewport renderer",
)
cpp = replace_once(
    cpp,
    "            display_mode( here );\n",
    "            display_editor_context_menu();\n            display_mode( here );\n",
    "draw context overlay after inspector",
)

cpp_path.write_text(cpp)
hdr_path.write_text(hdr)
