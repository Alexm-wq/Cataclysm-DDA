from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1))


hpp = Path("src/veh_interact.h")
replace_once(
    hpp,
    """        int editor_context_width = 0;\n        int editor_context_height = 0;\n        std::vector<editor_context_button> editor_context_buttons;\n""",
    """        int editor_context_width = 0;\n        int editor_context_height = 0;\n        std::vector<editor_context_button> editor_context_buttons;\n        std::string editor_context_hover_action;\n""",
    "context hover state",
)
replace_once(
    hpp,
    """        bool handle_editor_context_click( map &here, const point &pos );\n        bool run_editor_context_action( map &here, const std::string &action );\n        void display_editor_context_menu();\n""",
    """        bool handle_editor_context_click( map &here, const point &pos );\n        bool run_editor_context_action( map &here, const std::string &action );\n        void update_editor_context_hover( map &here );\n        bool set_editor_repair_requirements( map &here, vehicle_part &part );\n        void display_editor_context_menu();\n""",
    "context hover declarations",
)

cpp = Path("src/veh_interact.cpp")
replace_once(
    cpp,
    """void veh_interact::close_editor_context_menu()\n{\n    editor_context_open = false;\n    editor_context_target = editor_context_surface::none;\n    editor_context_buttons.clear();\n    editor_context_width = 0;\n    editor_context_height = 0;\n}\n""",
    """void veh_interact::close_editor_context_menu()\n{\n    if( !editor_context_hover_action.empty() ) {\n        msg.reset();\n        w_msg_scroll_offset = 0;\n    }\n    editor_context_hover_action.clear();\n    editor_context_open = false;\n    editor_context_target = editor_context_surface::none;\n    editor_context_buttons.clear();\n    editor_context_width = 0;\n    editor_context_height = 0;\n}\n""",
    "clear hover preview on close",
)

# Insert reusable repair requirements formatter immediately before action dispatch.
marker = """bool veh_interact::run_editor_context_action( map &here, const std::string &action )\n{\n"""
text = cpp.read_text()
if text.count(marker) != 1:
    raise SystemExit(f"action dispatch marker count={text.count(marker)}")
helper = r'''bool veh_interact::set_editor_repair_requirements( map &here, vehicle_part &part )
{
    avatar &player_character = get_avatar();
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
    return ok;
}

void veh_interact::update_editor_context_hover( map &here )
{
    if( !editor_context_open ) {
        return;
    }

    const editor_context_button *hovered = nullptr;
    for( const editor_context_button &button : editor_context_buttons ) {
        if( editor_mouse_pos.y == button.pos.y && editor_mouse_pos.x >= button.pos.x &&
            editor_mouse_pos.x < button.pos.x + button.width ) {
            hovered = &button;
            break;
        }
    }

    const std::string new_action = hovered != nullptr ? hovered->action : std::string();
    if( new_action == editor_context_hover_action ) {
        return;
    }

    const bool had_preview = !editor_context_hover_action.empty();
    editor_context_hover_action = new_action;
    w_msg_scroll_offset = 0;

    if( hovered == nullptr || ( hovered->action != "EDITOR_REMOVE" &&
                                hovered->action != "EDITOR_REPAIR" ) ) {
        if( had_preview ) {
            msg.reset();
        }
        return;
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return;
    }

    if( hovered->action == "EDITOR_REPAIR" ) {
        set_editor_repair_requirements( here, part );
        return;
    }

    // can_remove_part already owns the canonical removal requirements display,
    // including tools, skills, time, lifting/jacking and can_unmount reasons.
    // It historically updates command-side pointers, so preserve them while
    // using it as a read-only hover preview.
    const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
    const vpart_info *old_sel_vpart_info = sel_vpart_info;
    can_remove_part( here, selected_part, get_avatar() );
    sel_vehicle_part = old_sel_vehicle_part;
    sel_vpart_info = old_sel_vpart_info;
}

'''
cpp.write_text(text.replace(marker, helper + marker, 1))

# Replace duplicated repair requirement generation inside context click with helper.
old_repair = r'''        const vpart_info &vpi = part.info();
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
'''
new_repair = r'''        const vpart_info &vpi = part.info();
        if( !set_editor_repair_requirements( here, part ) ) {
            return true;
        }
        const bool would_prevent_flying = veh->would_repair_prevent_flyable( part, player_character );
'''
replace_once(cpp, old_repair, new_repair, "reuse repair requirements in action")

# Consume context-menu mouse movement and update preview before generic drag handling.
needle = r'''    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    } else if( editor_context_target == editor_context_surface::parts && parts_pos ) {
        editor_mouse_pos = *parts_pos;
    } else if( viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    }

#if defined(TILES)
'''
replacement = r'''    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    } else if( editor_context_target == editor_context_surface::parts && parts_pos ) {
        editor_mouse_pos = *parts_pos;
    } else if( viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    }

    if( action == "MOUSE_MOVE" && editor_context_open ) {
        update_editor_context_hover( here );
        return true;
    }

#if defined(TILES)
'''
replace_once(cpp, needle, replacement, "consume context hover mouse move")
