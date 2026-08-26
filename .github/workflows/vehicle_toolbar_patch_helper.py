from pathlib import Path

CPP = Path("src/veh_interact.cpp")
HDR = Path("src/veh_interact.h")
STATUS = Path("doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md")

cpp = CPP.read_text(encoding="utf-8")
hdr = HDR.read_text(encoding="utf-8")
status = STATUS.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Header: toolbar state and helpers.
# ---------------------------------------------------------------------------
hdr = replace_once(
    hdr,
'''        std::vector<editor_context_button> editor_context_buttons;
        std::string editor_context_hover_action;
        /* starting offset for vehicle parts description display and max offset for scrolling */
''',
'''        std::vector<editor_context_button> editor_context_buttons;
        std::string editor_context_hover_action;

        struct editor_toolbar_button {
            std::string label;
            std::string action;
            point pos = point::zero;
            int width = 0;
            bool enabled = true;
            int group = 0;
        };
        std::vector<editor_toolbar_button> editor_toolbar_buttons;
        int editor_toolbar_hover_button = -1;
        std::string editor_toolbar_hover_action;
        std::string pending_editor_action;
        /* starting offset for vehicle parts description display and max offset for scrolling */
''',
    "toolbar state",
)

hdr = replace_once(
    hdr,
'''        void update_editor_context_hover( map &here );
        bool set_editor_repair_requirements( map &here, vehicle_part &part );
        void display_editor_context_menu();
        bool handle_editor_mouse( map &here, const std::string &action );
        void display_editor_controls();
''',
'''        void update_editor_context_hover( map &here );
        bool set_editor_repair_requirements( map &here, vehicle_part &part );
        void display_editor_context_menu();
        bool editor_toolbar_action_enabled( const map &here, const std::string &action );
        void rebuild_editor_toolbar( const map &here );
        void update_editor_toolbar_hover( map &here, const std::optional<point> &pos );
        bool handle_editor_toolbar_mouse( map &here, const std::string &action,
                                          const std::optional<point> &pos );
        void open_editor_toolbar_menu( const map &here, const std::string &which );
        bool handle_editor_mouse( map &here, const std::string &action );
        void display_editor_controls();
''',
    "toolbar declarations",
)

# ---------------------------------------------------------------------------
# Main loop: toolbar clicks become ordinary VEH_INTERACT action IDs.
# ---------------------------------------------------------------------------
cpp = replace_once(
    cpp,
'''        const std::string action = main_context.handle_input();

        if( handle_editor_mouse( here, action ) ) {
            if( sel_cmd != ' ' ) {
                finish = true;
            }
            continue;
        }

        if( install_info ) {
''',
'''        std::string action = main_context.handle_input();

        const bool mouse_handled = handle_editor_mouse( here, action );
        if( !pending_editor_action.empty() ) {
            action = pending_editor_action;
            pending_editor_action.clear();
        } else if( mouse_handled ) {
            if( sel_cmd != ' ' ) {
                finish = true;
            }
            continue;
        }

        if( install_info ) {
''',
    "main-loop toolbar dispatch",
)

# ---------------------------------------------------------------------------
# Mouse routing: w_mode is a real pane and owns its mouse events.
# ---------------------------------------------------------------------------
cpp = replace_once(
    cpp,
'''    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );
    const std::optional<point> parts_pos = mouse_pos_in( w_parts );
    const std::optional<point> list_pos = mouse_pos_in( w_list );
    const std::optional<point> details_pos = mouse_pos_in( w_msg );
''',
'''    const std::optional<point> mode_pos = mouse_pos_in( w_mode );
    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );
    const std::optional<point> parts_pos = mouse_pos_in( w_parts );
    const std::optional<point> list_pos = mouse_pos_in( w_list );
    const std::optional<point> details_pos = mouse_pos_in( w_msg );
''',
    "toolbar mouse coordinate",
)

cpp = replace_once(
    cpp,
'''    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );

    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
''',
'''    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );

    // The toolbar is a first-class pane.  If a click chooses a command it stores
    // the existing VEH_INTERACT action ID in pending_editor_action; return false
    // immediately so do_main_loop() dispatches that action through the normal
    // keyboard/backend path instead of adding mouse-only vehicle mechanics.
    if( action == "MOUSE_MOVE" || mode_pos || editor_toolbar_hover_button >= 0 ) {
        const bool toolbar_handled = handle_editor_toolbar_mouse( here, action, mode_pos );
        if( !pending_editor_action.empty() ) {
            return false;
        }
        if( toolbar_handled ) {
            return true;
        }
    }

    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
''',
    "toolbar mouse routing",
)

# ---------------------------------------------------------------------------
# Replace the legacy one-line hotkey text renderer with a responsive toolbar.
# ---------------------------------------------------------------------------
start = cpp.find("static std::string veh_act_desc(")
if start < 0:
    raise SystemExit("legacy veh_act_desc block not found")
end_marker = "/**\n * Draws the list of parts that can be mounted in the selected square."
end = cpp.find(end_marker, start)
if end < 0:
    raise SystemExit("display_mode end marker not found")

new_block = r'''bool veh_interact::editor_toolbar_action_enabled( const map &here, const std::string &action )
{
    if( install_info ) {
        // Install is a persistent editor mode.  Do not allow another command to
        // start on top of it; Back still routes through QUIT and closes the mode.
        return action == "INSTALL" || action == "QUIT";
    }

    const auto selected = [&]() -> const vehicle_part * {
        if( selected_part < 0 || selected_part >= veh->part_count() ) {
            return nullptr;
        }
        const vehicle_part &part = veh->part( selected_part );
        return !part.removed && part.mount == selected_mount() ? &part : nullptr;
    };

    if( action == "INSTALL" ) {
        return cant_do( here, 'i' ) == task_reason::CAN_DO;
    }
    if( action == "REPAIR" ) {
        const vehicle_part *part = selected();
        return part != nullptr && part->health_percent() < 0.999 &&
               ( part->is_broken() || part->is_repairable() );
    }
    if( action == "REMOVE" ) {
        const vehicle_part *part = selected();
        return part != nullptr && !part->info().has_flag( "NO_UNINSTALL" ) &&
               veh->can_unmount( *part ).success();
    }
    if( action == "REFILL" ) {
        return cant_do( here, 'f' ) == task_reason::CAN_DO;
    }
    if( action == "MEND" ) {
        return cant_do( here, 'm' ) == task_reason::CAN_DO;
    }
    if( action == "CHANGE_SHAPE" || action == "RELABEL" ) {
        return selected() != nullptr;
    }
    if( action == "ASSIGN_CREW" ) {
        return cant_do( here, 'w' ) == task_reason::CAN_DO;
    }
    if( action == "SIPHON" ) {
        return cant_do( here, 's' ) == task_reason::CAN_DO;
    }
    if( action == "UNLOAD" ) {
        return cant_do( here, 'd' ) == task_reason::CAN_DO;
    }
    return action == "RENAME" || action == "QUIT";
}

void veh_interact::rebuild_editor_toolbar( const map &here )
{
    editor_toolbar_buttons.clear();
    const int width = getmaxx( w_mode );
    if( width <= 2 ) {
        return;
    }

    struct toolbar_candidate {
        std::string label;
        std::string action;
        int group = 0;
    };
    const auto direct = []( const std::string &label, const std::string &action, const int group ) {
        return toolbar_candidate{ label, action, group };
    };
    const auto menu = []( const std::string &label, const std::string &menu_id, const int group ) {
        return toolbar_candidate{ label, menu_id, group };
    };
    const auto is_menu = []( const toolbar_candidate &entry ) {
        return entry.action.starts_with( "TOOLBAR_MENU_" );
    };
    const auto rendered = [&]( const toolbar_candidate &entry ) {
        return is_menu( entry ) ? string_format( "[ %s ▼ ]", entry.label ) :
               string_format( "[ %s ]", entry.label );
    };

    const toolbar_candidate back = direct( _( "Back" ), "QUIT", 4 );
    const int back_width = utf8_width( rendered( back ) );

    const std::vector<toolbar_candidate> wide = {
        direct( _( "Install" ), "INSTALL", 0 ),
        direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ),
        direct( _( "Refuel" ), "REFILL", 0 ),
        menu( _( "Modify" ), "TOOLBAR_MENU_MODIFY", 1 ),
        direct( _( "Crew" ), "ASSIGN_CREW", 2 ),
        direct( _( "Rename" ), "RENAME", 2 ),
        menu( _( "More" ), "TOOLBAR_MENU_MORE", 3 )
    };
    const std::vector<toolbar_candidate> medium = {
        direct( _( "Install" ), "INSTALL", 0 ),
        direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ),
        direct( _( "Refuel" ), "REFILL", 0 ),
        menu( _( "Modify" ), "TOOLBAR_MENU_MODIFY", 1 ),
        menu( _( "More" ), "TOOLBAR_MENU_MORE", 2 )
    };
    const std::vector<toolbar_candidate> narrow = {
        direct( _( "Install" ), "INSTALL", 0 ),
        direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ),
        menu( _( "Actions" ), "TOOLBAR_MENU_ACTIONS", 1 )
    };
    const std::vector<toolbar_candidate> tiny = {
        menu( _( "Actions" ), "TOOLBAR_MENU_ACTIONS", 0 )
    };

    const auto required_width = [&]( const std::vector<toolbar_candidate> &entries ) {
        int total = 1 + back_width + 1;
        int previous_group = -1;
        for( const toolbar_candidate &entry : entries ) {
            if( previous_group >= 0 ) {
                total += entry.group == previous_group ? 1 : 3;
            }
            total += utf8_width( rendered( entry ) );
            previous_group = entry.group;
        }
        return total + 1;
    };

    const std::vector<toolbar_candidate> *chosen = &tiny;
    if( required_width( wide ) <= width ) {
        chosen = &wide;
    } else if( required_width( medium ) <= width ) {
        chosen = &medium;
    } else if( required_width( narrow ) <= width ) {
        chosen = &narrow;
    }

    int x = 1;
    int previous_group = -1;
    for( const toolbar_candidate &entry : *chosen ) {
        if( previous_group >= 0 ) {
            x += entry.group == previous_group ? 1 : 3;
        }
        const int button_width = utf8_width( rendered( entry ) );
        if( x + button_width >= width - back_width - 1 ) {
            break;
        }
        const bool menu_button = is_menu( entry );
        editor_toolbar_buttons.push_back( { entry.label, entry.action, point( x, 0 ), button_width,
                                            menu_button || editor_toolbar_action_enabled( here, entry.action ),
                                            entry.group } );
        x += button_width;
        previous_group = entry.group;
    }

    editor_toolbar_buttons.push_back( { back.label, back.action,
                                        point( std::max( 1, width - back_width - 1 ), 0 ),
                                        back_width, true, back.group } );
}

void veh_interact::update_editor_toolbar_hover( map &here, const std::optional<point> &pos )
{
    int hovered_index = -1;
    if( pos ) {
        for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
            const editor_toolbar_button &button = editor_toolbar_buttons[i];
            if( pos->y == button.pos.y && pos->x >= button.pos.x &&
                pos->x < button.pos.x + button.width ) {
                hovered_index = i;
                break;
            }
        }
    }

    std::string preview_action;
    if( hovered_index >= 0 ) {
        const std::string &action = editor_toolbar_buttons[hovered_index].action;
        if( action == "REPAIR" || action == "REMOVE" ) {
            preview_action = action;
        }
    }

    editor_toolbar_hover_button = hovered_index;
    if( preview_action == editor_toolbar_hover_action ) {
        return;
    }

    const bool had_preview = !editor_toolbar_hover_action.empty();
    editor_toolbar_hover_action = preview_action;
    w_msg_scroll_offset = 0;
    if( preview_action.empty() ) {
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

    if( preview_action == "REPAIR" ) {
        set_editor_repair_requirements( here, part );
        return;
    }

    // Removal already has one canonical formatter.  Preserve the transient
    // command pointers so hovering remains a read-only preview.
    const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
    const vpart_info *old_sel_vpart_info = sel_vpart_info;
    can_remove_part( here, selected_part, get_avatar() );
    sel_vehicle_part = old_sel_vehicle_part;
    sel_vpart_info = old_sel_vpart_info;
}

void veh_interact::open_editor_toolbar_menu( const map &here, const std::string &which )
{
    struct toolbar_menu_entry {
        std::string label;
        std::string action;
    };
    std::vector<toolbar_menu_entry> entries;

    const auto has_direct = [&]( const std::string &action ) {
        return std::any_of( editor_toolbar_buttons.begin(), editor_toolbar_buttons.end(),
        [&]( const editor_toolbar_button &button ) {
            return !button.action.starts_with( "TOOLBAR_MENU_" ) && button.action == action;
        } );
    };
    const auto add = [&]( const std::string &label, const std::string &action ) {
        entries.push_back( { label, action } );
    };

    if( which == "TOOLBAR_MENU_MODIFY" ) {
        add( _( "Mend faults…" ), "MEND" );
        add( _( "Change shape…" ), "CHANGE_SHAPE" );
        add( _( "Relabel…" ), "RELABEL" );
    } else if( which == "TOOLBAR_MENU_MORE" ) {
        if( !has_direct( "ASSIGN_CREW" ) ) {
            add( _( "Crew…" ), "ASSIGN_CREW" );
        }
        if( !has_direct( "RENAME" ) ) {
            add( _( "Rename vehicle…" ), "RENAME" );
        }
        add( _( "Siphon liquid…" ), "SIPHON" );
        add( _( "Unload fuel…" ), "UNLOAD" );
    } else if( which == "TOOLBAR_MENU_ACTIONS" ) {
        if( !has_direct( "INSTALL" ) ) {
            add( _( "Install…" ), "INSTALL" );
        }
        if( !has_direct( "REPAIR" ) ) {
            add( _( "Repair…" ), "REPAIR" );
        }
        if( !has_direct( "REMOVE" ) ) {
            add( _( "Remove…" ), "REMOVE" );
        }
        if( !has_direct( "REFILL" ) ) {
            add( _( "Refuel…" ), "REFILL" );
        }
        add( _( "Mend faults…" ), "MEND" );
        add( _( "Change shape…" ), "CHANGE_SHAPE" );
        add( _( "Relabel…" ), "RELABEL" );
        add( _( "Crew…" ), "ASSIGN_CREW" );
        add( _( "Rename vehicle…" ), "RENAME" );
        add( _( "Siphon liquid…" ), "SIPHON" );
        add( _( "Unload fuel…" ), "UNLOAD" );
    }

    if( entries.empty() ) {
        return;
    }

    uilist menu;
    if( which == "TOOLBAR_MENU_MODIFY" ) {
        menu.text = _( "Modify selected part" );
    } else if( which == "TOOLBAR_MENU_MORE" ) {
        menu.text = _( "More vehicle actions" );
    } else {
        menu.text = _( "Vehicle actions" );
    }

    for( int i = 0; i < static_cast<int>( entries.size() ); ++i ) {
        menu.addentry( i, editor_toolbar_action_enabled( here, entries[i].action ), -1,
                       entries[i].label );
    }
    menu.query();
    if( menu.ret >= 0 && menu.ret < static_cast<int>( entries.size() ) &&
        editor_toolbar_action_enabled( here, entries[menu.ret].action ) ) {
        pending_editor_action = entries[menu.ret].action;
    }
}

bool veh_interact::handle_editor_toolbar_mouse( map &here, const std::string &action,
        const std::optional<point> &pos )
{
    // Legacy modal command choosers temporarily own w_mode for their title.
    // Do not make an invisible toolbar clickable underneath them.
    if( title.has_value() && !install_info ) {
        if( editor_toolbar_hover_button >= 0 || !editor_toolbar_hover_action.empty() ) {
            editor_toolbar_hover_button = -1;
            editor_toolbar_hover_action.clear();
        }
        return false;
    }

    rebuild_editor_toolbar( here );
    if( action == "MOUSE_MOVE" || editor_toolbar_hover_button >= 0 ) {
        update_editor_toolbar_hover( here, pos );
        if( action == "MOUSE_MOVE" && pos ) {
            return true;
        }
    }
    if( !pos ) {
        return false;
    }

    int hit = -1;
    for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[i];
        if( pos->y == button.pos.y && pos->x >= button.pos.x &&
            pos->x < button.pos.x + button.width ) {
            hit = i;
            break;
        }
    }
    if( hit < 0 ) {
        return true;
    }

    if( action == "SELECT" ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[hit];
        if( button.action.starts_with( "TOOLBAR_MENU_" ) ) {
            close_editor_context_menu();
            open_editor_toolbar_menu( here, button.action );
            return pending_editor_action.empty();
        }
        if( !button.enabled ) {
            return true;
        }
        pending_editor_action = button.action;
        return false;
    }

    // The toolbar consumes wheel/secondary clicks over its own row so those
    // inputs never leak into the viewport, inspector, or live-preview camera.
    return action == "SEC_SELECT" || action == "SCROLL_UP" || action == "SCROLL_DOWN";
}

/**
 * Mouse-first action toolbar.  The old keyboard bindings remain registered in
 * VEH_INTERACT; toolbar clicks inject those same action IDs into do_main_loop().
 */
void veh_interact::display_mode( const map &here )
{
    werase( w_mode );

    if( title.has_value() && !install_info ) {
        nc_color title_col = c_light_gray;
        print_colored_text( w_mode, point( 1, 0 ), title_col, title_col, title.value() );
        wnoutrefresh( w_mode );
        return;
    }

    rebuild_editor_toolbar( here );
    for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[i];
        const bool menu_button = button.action.starts_with( "TOOLBAR_MENU_" );
        const std::string text = menu_button ? string_format( "[ %s ▼ ]", button.label ) :
                                 string_format( "[ %s ]", button.label );
        const bool hovered = i == editor_toolbar_hover_button;
        const nc_color color = !button.enabled ? c_dark_gray :
                               hovered ? h_light_cyan : c_light_cyan;
        trim_and_print( w_mode, button.pos, button.width, color, text );
    }
    wnoutrefresh( w_mode );
}

'''
cpp = cpp[:start] + new_block + cpp[end:]

# ---------------------------------------------------------------------------
# Living status document.
# ---------------------------------------------------------------------------
status = replace_once(
    status,
"Status: **active — approximately 90% complete**",
"Status: **active — approximately 92% complete**",
    "status percentage",
)
status = replace_once(
    status,
"Last audited implementation head: `fef22b8181b197d266841d5d96fcb95844fe1e42` (`Fix split live preview zoom anchor`)",
"Last audited implementation head: current `mouse-inventory-0-i-test` toolbar integration; live-preview camera fixes and action-hover requirements are included in this audit.",
    "status audited head",
)
status = replace_once(
    status,
'''The editor now has an independent viewport/camera, mouse-selectable mounts, an inspector, panning/zooming, semantic layer/filter controls, context actions, a live install pane, multiple viewport modes, and a live tiles preview with its own camera controls. Existing vehicle command mechanics still route through `veh_interact` rather than being reimplemented as UI-only rules.
''',
'''The editor now has an independent viewport/camera, mouse-selectable mounts, an inspector, panning/zooming, semantic layer/filter controls, context actions, a live install pane, multiple viewport modes, a live tiles preview with its own camera controls, and a responsive clickable action toolbar. Existing vehicle command mechanics still route through `veh_interact` rather than being reimplemented as UI-only rules.
''',
    "status current-state toolbar",
)
status = replace_once(
    status,
"Current estimate: **~90% complete**.",
"Current estimate: **~92% complete**.",
    "status current estimate",
)

anchor = "## Implemented functionality\n\n"
if anchor not in status:
    raise SystemExit("status implemented-functionality anchor missing")
toolbar_section = '''### Clickable responsive action toolbar\n\n- [x] Legacy top command-hint strip replaced by a mouse-clickable vehicle action toolbar.\n- [x] Primary construction actions are first-class buttons: **Install**, **Repair**, **Remove**, and **Refuel**.\n- [x] **Modify** groups lower-frequency selected-part operations such as Mend, Change Shape, and Relabel.\n- [x] **More** groups vehicle-level/utility actions such as Crew, Rename, Siphon, and Unload when they are not already visible directly.\n- [x] Toolbar collapses by available translated width: wide, medium, narrow, and tiny layouts progressively move actions into **More** or **Actions** instead of truncating labels.\n- [x] **Back** remains a direct far-right action while the existing keyboard `QUIT`/Esc path remains available.\n- [x] Toolbar clicks inject existing `VEH_INTERACT` action IDs back into `do_main_loop()`; ownership checks, command handlers, activities, time costs, and vehicle rules therefore remain shared with keyboard control.\n- [x] Toolbar mouse routing is confined to `w_mode`, preventing clicks/wheel input from leaking into the schematic, inspector, or live-preview camera.\n- [x] Repair/Remove toolbar hover reuses the same canonical requirements preview as the inspector context menu, so components/tools/skills/time and removal blockers are visible before committing.\n- [x] Current **Refuel** toolbar entry intentionally routes to the existing refill backend. The dedicated persistent Refuel pane is the next refueling implementation step rather than a second toolbar action.\n\n'''
status = status.replace(anchor, anchor + toolbar_section, 1)

remaining_anchor = "### High-priority completion work\n\n"
if remaining_anchor not in status:
    raise SystemExit("status high-priority anchor missing")
refuel_remaining = '''- [ ] Replace the legacy refill chooser behind the single **Refuel** toolbar entry with the persistent Refuel pane: vehicle/available-fuel summary, tank → source selection, double-click progression, and **Quick refill all** optimized for the lowest valid turn cost.\n- [ ] In Vehicle Editor Test mode, add a test-only way to place ordinary filled gasoline containers into valid vehicle cargo/trunk storage so manual and quick-refill source selection can be exercised with real items.\n'''
status = status.replace(remaining_anchor, remaining_anchor + refuel_remaining, 1)

# Update the primary code-surface description to mention the toolbar.
status = status.replace(
"Main editor redesign: viewport layout, selection, inspector, pan/zoom, filters/layers, context actions, install pane, mode buttons, live preview state and interaction.",
"Main editor redesign: viewport layout, selection, inspector, pan/zoom, filters/layers, context actions, install pane, responsive action toolbar, mode buttons, live preview state and interaction.",
1,
)

# Add a non-self-referential timeline item; the exact source commit is reported by
# the branch history and final implementation response.
timeline_anchor = "| [`fef22b81`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/fef22b8181b197d266841d5d96fcb95844fe1e42) | Latest audited split live-preview zoom-anchor correction. |\n"
if timeline_anchor in status:
    status = status.replace(
        timeline_anchor,
        timeline_anchor + "| Current toolbar integration | Responsive clickable action toolbar, grouped overflow menus, shared keyboard/backend dispatch, and Repair/Remove hover requirements. |\n",
        1,
    )

CPP.write_text(cpp, encoding="utf-8")
HDR.write_text(hdr, encoding="utf-8")
STATUS.write_text(status, encoding="utf-8")
