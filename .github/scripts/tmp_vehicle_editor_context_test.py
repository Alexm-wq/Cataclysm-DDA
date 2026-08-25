from pathlib import Path
import re

EXPECTED = "c82e47ead39a2548d521f86e1de608449b1a6242"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)

# ---------------- veh_interact.h ----------------
p = Path("src/veh_interact.h")
s = p.read_text()
s = replace_once(s,
'''        editor_condition_filter active_condition_filter = editor_condition_filter::all;
        editor_dropdown open_editor_dropdown = editor_dropdown::none;
''',
'''        editor_condition_filter active_condition_filter = editor_condition_filter::all;
        editor_dropdown open_editor_dropdown = editor_dropdown::none;

        struct editor_context_button {
            std::string label;
            point pos = point::zero;
            int width = 0;
            std::string action;
            std::string disabled_reason;
            bool enabled = true;
        };
        bool editor_test_mode = false;
        bool editor_context_open = false;
        point editor_context_anchor = point::zero;
        point editor_context_pos = point::zero;
        point editor_mouse_pos = point::zero;
        int editor_context_width = 0;
        int editor_context_height = 0;
        std::vector<editor_context_button> editor_context_buttons;
''', "context state")
s = replace_once(s,
'''        bool part_matches_layer( const vehicle_part &vp ) const;
        editor_system_filter primary_system_for_part( const vehicle_part &vp ) const;
''',
'''        bool part_info_matches_layer( const vpart_info &vpi ) const;
        bool part_matches_layer( const vehicle_part &vp ) const;
        editor_system_filter primary_system_for_part( const vehicle_part &vp ) const;
''', "layer declaration")
s = replace_once(s,
'''        bool handle_editor_controls_click( const point &pos );
        bool handle_editor_mouse( map &here, const std::string &action );
        void display_editor_controls();
''',
'''        bool handle_editor_controls_click( const point &pos );
        void close_editor_context_menu();
        void open_editor_context_menu( map &here, const point &pos );
        bool handle_editor_context_click( map &here, const point &pos );
        bool run_editor_context_action( map &here, const std::string &action );
        void display_editor_context_menu();
        bool handle_editor_mouse( map &here, const std::string &action );
        void display_editor_controls();
''', "context declarations")
p.write_text(s)

# ---------------- veh_utils.h ----------------
p = Path("src/veh_utils.h")
s = p.read_text()
s = replace_once(s,
'''bool repair_part( map &here, vehicle &veh, vehicle_part &pt, Character &who );
''',
'''bool repair_part( map &here, vehicle &veh, vehicle_part &pt, Character &who,
                  bool consume_resources = true );
''', "repair signature")
p.write_text(s)

# ---------------- veh_utils.cpp ----------------
p = Path("src/veh_utils.cpp")
s = p.read_text()
s = replace_once(s,
'''bool repair_part( map &here, vehicle &veh, vehicle_part &pt, Character &who )
{
''',
'''bool repair_part( map &here, vehicle &veh, vehicle_part &pt, Character &who,
                  const bool consume_resources )
{
''', "repair definition")
s = replace_once(s,
'''    if( !reqs.can_make_with_inventory( inv, is_crafting_component ) ) {
        who.add_msg_if_player( m_info, _( "You don't meet the requirements to repair the %s." ),
                               pt.name() );
        return false;
    }

    // consume items extracting any base item (which we will need if replacing broken part)
    item base( vp.base_item );
    for( const auto &e : reqs.get_components() ) {
        for( item &obj : who.consume_items( who.select_item_component( e, 1, map_inv ), 1,
                                            is_crafting_component ) ) {
            if( obj.typeId() == vp.base_item ) {
                base = obj;
            }
        }
    }

    for( const auto &e : reqs.get_tools() ) {
        who.consume_tools( who.select_tool_component( e, 1, map_inv ), 1 );
    }

    who.invalidate_crafting_inventory();

    for( const auto &sk : pt.is_broken() ? vp.install_skills : vp.repair_skills ) {
        who.practice( sk.first, calc_xp_gain( vp, sk.first, who ) );
    }
''',
'''    if( consume_resources && !reqs.can_make_with_inventory( inv, is_crafting_component ) ) {
        who.add_msg_if_player( m_info, _( "You don't meet the requirements to repair the %s." ),
                               pt.name() );
        return false;
    }

    // Test-mode repair/replacement deliberately creates the base part in memory and
    // skips inventory/tool consumption.  The actual repair/replacement mutation below
    // is unchanged, so degradation and broken-part semantics remain authoritative.
    item base( vp.base_item );
    if( consume_resources ) {
        for( const auto &e : reqs.get_components() ) {
            for( item &obj : who.consume_items( who.select_item_component( e, 1, map_inv ), 1,
                                                is_crafting_component ) ) {
                if( obj.typeId() == vp.base_item ) {
                    base = obj;
                }
            }
        }

        for( const auto &e : reqs.get_tools() ) {
            who.consume_tools( who.select_tool_component( e, 1, map_inv ), 1 );
        }

        who.invalidate_crafting_inventory();

        for( const auto &sk : pt.is_broken() ? vp.install_skills : vp.repair_skills ) {
            who.practice( sk.first, calc_xp_gain( vp, sk.first, who ) );
        }
    }
''', "repair resource block")
s = replace_once(s,
'''        here.spawn_items( who.pos_bub( here ), pt.pieces_for_broken_part() );
''',
'''        if( consume_resources ) {
            here.spawn_items( who.pos_bub( here ), pt.pieces_for_broken_part() );
        }
''', "repair broken salvage")
p.write_text(s)

# ---------------- veh_interact.cpp ----------------
p = Path("src/veh_interact.cpp")
s = p.read_text()

# Add the intentionally easy-to-toggle exposure guard beside existing file-scope declarations.
anchor = 'static void act_vehicle_unload_fuel( map &here, vehicle *veh );\n'
s = replace_once(s, anchor, anchor + '''\n// Development-only vehicle editor hammerspace.  The workflow\n// .github/workflows/toggle-vehicle-editor-test-mode.yml flips only this constant.\nstatic constexpr bool vehicle_editor_test_mode_visible = true;\nstatic bool vehicle_editor_test_mode_latched = false;\n''', "test visibility constant")

# Persist Test mode across the normal vehicle activity close/reopen cycle.
s = replace_once(s,
'''    main_context.register_action( "SELECT" );
    main_context.register_action( "MOUSE_MOVE" );
''',
'''    main_context.register_action( "SELECT" );
    main_context.register_action( "SEC_SELECT" );
    main_context.register_action( "MOUSE_MOVE" );
''', "secondary select registration")
s = replace_once(s,
'''    count_durability();
    cache_tool_availability();
''',
'''    editor_test_mode = vehicle_editor_test_mode_visible && vehicle_editor_test_mode_latched;
    if( !vehicle_editor_test_mode_visible ) {
        vehicle_editor_test_mode_latched = false;
    }

    count_durability();
    cache_tool_availability();
''', "test mode constructor")

# Activity marker and fast test duration.
s = replace_once(s,
'''    if( player_character.has_trait( trait_DEBUG_HS ) ) {
        time = 1_seconds;
    }
''',
'''    if( player_character.has_trait( trait_DEBUG_HS ) || editor_test_mode ) {
        time = 1_seconds;
    }
''', "test activity time")
s = replace_once(s,
'''    res.str_values.emplace_back( vp->id.str() );
    res.str_values.emplace_back( "" ); // previously stored the part variant, now obsolete
''',
'''    res.str_values.emplace_back( vp->id.str() );
    res.str_values.emplace_back( editor_test_mode ? "vehicle_editor_test" : "" );
''', "test activity marker")

# Resource checks in UI keep skill/physical legality, while Test ignores only inventory/tool possession.
s = replace_once(s,
'''    bool ok = reqs.can_make_with_inventory( inv, is_crafting_component, 1, craft_flags::none, false );

    msg += _( "<color_white>Time required:</color>\\n" );
''',
'''    const bool resources_available = reqs.can_make_with_inventory( inv, is_crafting_component, 1,
                                     craft_flags::none, false );
    bool ok = editor_test_mode || resources_available;

    if( editor_test_mode ) {
        msg += _( "<color_light_cyan>Test mode: components and tools are ignored.</color>\\n" );
    }
    msg += _( "<color_white>Time required:</color>\\n" );
''', "format requirements test bypass")

# Layer classification works for both installed vehicle_part and prospective vpart_info.
old_layer = '''bool veh_interact::part_matches_layer( const vehicle_part &vp ) const
{
    if( active_editor_layer == editor_layer::composite ) {
        return true;
    }

    const std::string &location = vp.info().location;
    const bool ground = location == "under" || location == "engine_block" ||
                        location == "on_battery_mount" || location == "fuel_source";
    const bool roof = location == "roof" || location == "on_roof";

    switch( active_editor_layer ) {
        case editor_layer::ground:
            return ground;
        case editor_layer::roof:
            return roof;
        case editor_layer::middle:
            // New or modded locations default to the body/interior layer rather than
            // silently disappearing from all non-composite views.
            return !ground && !roof;
        case editor_layer::composite:
        default:
            return true;
    }
}
'''
new_layer = '''bool veh_interact::part_info_matches_layer( const vpart_info &vpi ) const
{
    if( active_editor_layer == editor_layer::composite ) {
        return true;
    }

    const std::string &location = vpi.location;
    const bool ground = location == "under" || location == "engine_block" ||
                        location == "on_battery_mount" || location == "fuel_source";
    const bool roof = location == "roof" || location == "on_roof";

    switch( active_editor_layer ) {
        case editor_layer::ground:
            return ground;
        case editor_layer::roof:
            return roof;
        case editor_layer::middle:
            return !ground && !roof;
        case editor_layer::composite:
        default:
            return true;
    }
}

bool veh_interact::part_matches_layer( const vehicle_part &vp ) const
{
    return part_info_matches_layer( vp.info() );
}
'''
s = replace_once(s, old_layer, new_layer, "layer helper implementation")

# Fix condition semantics: a merely damaged NO_REPAIR part is still Damaged, not replacement-only.
pattern = re.compile(r'''bool veh_interact::part_matches_condition\( const vehicle_part &vp \) const\n\{.*?\n\}\n\nstd::string veh_interact::editor_layer_name''', re.S)
m = pattern.search(s)
if not m:
    raise SystemExit("condition function anchor not found")
new_condition = '''bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
{
    if( active_condition_filter == editor_condition_filter::all ) {
        return true;
    }

    const double health = vp.health_percent();
    const bool healthy = health >= 0.999;
    const bool destroyed = vp.is_broken();
    const bool replacement = destroyed && !vp.is_repairable();
    const bool broken = destroyed && vp.is_repairable();
    const bool damaged = !destroyed && health < 0.999;

    switch( active_condition_filter ) {
        case editor_condition_filter::healthy:
            return healthy;
        case editor_condition_filter::damaged:
            return damaged;
        case editor_condition_filter::broken:
            return broken;
        case editor_condition_filter::replacement:
            return replacement;
        case editor_condition_filter::all:
        default:
            return true;
    }
}

std::string veh_interact::editor_layer_name'''
s = s[:m.start()] + new_condition + s[m.end():]

# Same condition palette correction.
pattern = re.compile(r'''nc_color veh_interact::editor_condition_color\( const vehicle_part &vp \) const\n\{.*?\n\}\n\nstd::optional<std::pair<int, nc_color>> veh_interact::editor_mount_display''', re.S)
m = pattern.search(s)
if not m:
    raise SystemExit("condition color function anchor not found")
new_color = '''nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
{
    if( vp.is_broken() ) {
        return vp.is_repairable() ? c_brown : c_light_red;
    }
    if( vp.health_percent() < 0.999 ) {
        return c_yellow;
    }
    return c_light_green;
}

std::optional<std::pair<int, nc_color>> veh_interact::editor_mount_display'''
s = s[:m.start()] + new_color + s[m.end():]

# Guaranteed ASCII ghost instead of a Unicode shade glyph that disappears in some tiles/font paths.
s = replace_once(s,
'''    const int ghost_symbol = vpart_variant::get_symbol_curses( U'▒' );
''',
'''    const int ghost_symbol = '#';
''', "ghost symbol")

# Layer-aware install list.
s = replace_once(s,
'''        std::copy_if( can_mount.begin(), can_mount.end(), std::back_inserter( tab_vparts ),
                      tab_filters[tab] );
''',
'''        std::copy_if( can_mount.begin(), can_mount.end(), std::back_inserter( tab_vparts ),
        [&]( const vpart_info *part ) {
            return part_info_matches_layer( *part ) && tab_filters[tab]( part );
        } );
''', "install layer filter")

# Test mode makes resource possession irrelevant to install sorting, while keeping engine limits.
s = replace_once(s,
'''    bool can_make = vpart.install_requirements().can_make_with_inventory( *crafting_inv,
                    is_crafting_component, 1, craft_flags::none, false );
    bool hammerspace = get_player_character().has_trait( trait_DEBUG_HS );
''',
'''    bool can_make = editor_test_mode || vpart.install_requirements().can_make_with_inventory( *crafting_inv,
                    is_crafting_component, 1, craft_flags::none, false );
    bool hammerspace = get_player_character().has_trait( trait_DEBUG_HS );
''', "install resource sorting")

# Start repair/remove selectors on the exact inspector-selected part.
s = replace_once(s,
'''    int pos = 0;

    restore_on_out_of_scope prev_hilight_part( highlight_part );
''',
'''    int pos = 0;
    if( selected_part >= 0 ) {
        for( size_t i = 0; i < need_repair.size(); ++i ) {
            if( parts_here[need_repair[i]] == selected_part ) {
                pos = static_cast<int>( i );
                break;
            }
        }
    }

    restore_on_out_of_scope prev_hilight_part( highlight_part );
''', "repair selected part")
s = replace_once(s,
'''    avatar &player_character = get_avatar();
    int pos = 0;
    for( size_t i = 0; i < parts_here.size(); i++ ) {
        if( can_remove_part( here, parts_here[ i ], player_character ) ) {
            pos = i;
            break;
        }
    }
''',
'''    avatar &player_character = get_avatar();
    int pos = 0;
    bool selected_remove_target = false;
    if( selected_part >= 0 ) {
        for( size_t i = 0; i < parts_here.size(); ++i ) {
            if( parts_here[i] == selected_part ) {
                pos = static_cast<int>( i );
                selected_remove_target = true;
                break;
            }
        }
    }
    if( !selected_remove_target ) {
        for( size_t i = 0; i < parts_here.size(); i++ ) {
            if( can_remove_part( here, parts_here[ i ], player_character ) ) {
                pos = i;
                break;
            }
        }
    }
''', "remove selected part")

# Test checkbox click, preserving existing System/Condition dropdown behavior.
s = replace_once(s,
'''    if( pos.y == 2 ) {
        for( const editor_dropdown which : { editor_dropdown::system, editor_dropdown::condition } ) {
            int x = 0;
            int width = 0;
            editor_filter_button_geometry( which, x, width );
            if( pos.x >= x && pos.x < x + width ) {
                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;
                return true;
            }
        }
        return true;
    }
''',
'''    if( pos.y == 2 ) {
        for( const editor_dropdown which : { editor_dropdown::system, editor_dropdown::condition } ) {
            int x = 0;
            int width = 0;
            editor_filter_button_geometry( which, x, width );
            if( pos.x >= x && pos.x < x + width ) {
                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;
                close_editor_context_menu();
                return true;
            }
        }
        if( vehicle_editor_test_mode_visible ) {
            int condition_x = 0;
            int condition_width = 0;
            editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );
            const int test_x = condition_x + condition_width + 2;
            const int test_width = utf8_width( _( "[ ] Test" ) );
            if( pos.x >= test_x && pos.x < test_x + test_width ) {
                editor_test_mode = !editor_test_mode;
                vehicle_editor_test_mode_latched = editor_test_mode;
                open_editor_dropdown = editor_dropdown::none;
                close_editor_context_menu();
                msg = editor_test_mode ?
                      _( "Test mode enabled: components and tools are ignored; vehicle legality still applies." ) :
                      _( "Test mode disabled." );
                return true;
            }
        }
        return true;
    }
''', "test checkbox click")

# Insert context-menu implementation before handle_editor_mouse.
context_anchor = 'bool veh_interact::handle_editor_mouse( map &here, const std::string &action )\n'
if s.count(context_anchor) != 1:
    raise SystemExit("handle_editor_mouse anchor mismatch")
context_impl = r'''void veh_interact::close_editor_context_menu()
{
    editor_context_open = false;
    editor_context_buttons.clear();
    editor_context_width = 0;
    editor_context_height = 0;
}

void veh_interact::open_editor_context_menu( map &here, const point &pos )
{
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    editor_context_anchor = pos;

    const auto add_entry = [&]( const std::string &label, const std::string &action,
                                const bool enabled = true,
                                const std::string &disabled_reason = std::string() ) {
        editor_context_buttons.push_back( { label, point::zero, 0, action, disabled_reason, enabled } );
    };

    const bool has_install_for_layer = std::any_of( can_mount.begin(), can_mount.end(),
    [&]( const vpart_info *info ) {
        return info != nullptr && part_info_matches_layer( *info );
    } );
    add_entry( _( "Install…" ), "EDITOR_INSTALL", has_install_for_layer,
               _( "No parts for the selected layer can be installed at this mount." ) );

    if( selected_part >= 0 && selected_part < veh->part_count() ) {
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
                       uninstallable ? std::string() : _( "This part cannot be removed in the current vehicle state." ) );
            add_entry( _( "Examine" ), "EDITOR_EXAMINE" );
        }
    }

    add_entry( _( "Close" ), "EDITOR_CLOSE" );
    editor_context_open = !editor_context_buttons.empty();

    int widest = 0;
    for( const editor_context_button &button : editor_context_buttons ) {
        widest = std::max( widest, utf8_width( button.label ) );
    }
    editor_context_width = std::clamp( widest + 4, 16, std::max( 16, getmaxx( w_disp ) - 2 ) );
    editor_context_height = std::min( static_cast<int>( editor_context_buttons.size() ) + 2,
                                      std::max( 3, getmaxy( w_disp ) - editor_viewport_top() ) );
    if( static_cast<int>( editor_context_buttons.size() ) > editor_context_height - 2 ) {
        editor_context_buttons.resize( editor_context_height - 2 );
    }

    int menu_x = pos.x + 2;
    if( menu_x + editor_context_width >= getmaxx( w_disp ) ) {
        menu_x = pos.x - editor_context_width - 1;
    }
    menu_x = std::clamp( menu_x, 1, std::max( 1, getmaxx( w_disp ) - editor_context_width - 1 ) );
    int menu_y = pos.y;
    if( menu_y + editor_context_height >= getmaxy( w_disp ) ) {
        menu_y = getmaxy( w_disp ) - editor_context_height - 1;
    }
    menu_y = std::clamp( menu_y, editor_viewport_top(),
                         std::max( editor_viewport_top(), getmaxy( w_disp ) - editor_context_height - 1 ) );
    editor_context_pos = point( menu_x, menu_y );
}

bool veh_interact::run_editor_context_action( map &here, const std::string &action )
{
    close_editor_context_menu();
    if( action == "EDITOR_CLOSE" || action == "EDITOR_EXAMINE" ) {
        return true;
    }
    if( action == "EDITOR_INSTALL" ) {
        if( veh->handle_potential_theft( get_player_character() ) ) {
            do_install( here );
        }
        return sel_cmd == ' ';
    }
    if( action == "EDITOR_REPAIR" ) {
        if( veh->handle_potential_theft( get_player_character() ) ) {
            do_repair( here );
        }
        return sel_cmd == ' ';
    }
    if( action == "EDITOR_REMOVE" ) {
        if( veh->handle_potential_theft( get_player_character() ) ) {
            do_remove( here );
        }
        return sel_cmd == ' ';
    }
    return true;
}

bool veh_interact::handle_editor_context_click( map &here, const point &pos )
{
    if( !editor_context_open ) {
        return false;
    }
    for( const editor_context_button &button : editor_context_buttons ) {
        if( pos.y == button.pos.y && pos.x >= button.pos.x && pos.x < button.pos.x + button.width ) {
            if( !button.enabled ) {
                msg = button.disabled_reason.empty() ? _( "That action is not available." ) : button.disabled_reason;
                return true;
            }
            return run_editor_context_action( here, button.action );
        }
    }
    close_editor_context_menu();
    return true;
}

void veh_interact::display_editor_context_menu()
{
    if( !editor_context_open || editor_context_width <= 0 || editor_context_height < 3 ) {
        return;
    }

    const std::string blank( editor_context_width, ' ' );
    for( int row = 0; row < editor_context_height; ++row ) {
        mvwprintz( w_disp, editor_context_pos + point( 0, row ), c_black, "%s", blank );
    }
    mvwhline( w_disp, editor_context_pos, c_light_gray, LINE_OXOX, editor_context_width );
    mvwhline( w_disp, editor_context_pos + point( 0, editor_context_height - 1 ), c_light_gray,
              LINE_OXOX, editor_context_width );
    mvwvline( w_disp, editor_context_pos, c_light_gray, LINE_XOXO, editor_context_height );
    mvwvline( w_disp, editor_context_pos + point( editor_context_width - 1, 0 ), c_light_gray,
              LINE_XOXO, editor_context_height );
    mvwputch( w_disp, editor_context_pos, c_light_gray, LINE_OXXO );
    mvwputch( w_disp, editor_context_pos + point( editor_context_width - 1, 0 ), c_light_gray, LINE_OOXX );
    mvwputch( w_disp, editor_context_pos + point( 0, editor_context_height - 1 ), c_light_gray, LINE_XXOO );
    mvwputch( w_disp, editor_context_pos + point( editor_context_width - 1, editor_context_height - 1 ),
              c_light_gray, LINE_XOOX );

    for( int row = 0; row < static_cast<int>( editor_context_buttons.size() ); ++row ) {
        editor_context_button &button = editor_context_buttons[row];
        button.pos = editor_context_pos + point( 1, row + 1 );
        button.width = editor_context_width - 2;
        const bool hovered = editor_mouse_pos.y == button.pos.y &&
                             editor_mouse_pos.x >= button.pos.x &&
                             editor_mouse_pos.x < button.pos.x + button.width;
        const nc_color color = !button.enabled ? c_dark_gray : hovered ? h_green : c_light_green;
        trim_and_print( w_disp, button.pos, button.width, color, button.label );
    }
}

'''
s = s.replace(context_anchor, context_impl + context_anchor, 1)

# Track mouse position, right-click opens menu, left-click dispatches it before normal controls/mount selection.
s = replace_once(s,
'''    const bool over_viewport_content = viewport_pos && viewport_pos->y >= editor_viewport_top();
''',
'''    const bool over_viewport_content = viewport_pos && viewport_pos->y >= editor_viewport_top();
    if( viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    }
''', "context mouse tracking")
s = replace_once(s,
'''    if( action == "SELECT" && !install_info && !remove_info ) {
        if( viewport_pos && handle_editor_controls_click( *viewport_pos ) ) {
''',
'''    if( action == "SEC_SELECT" && !install_info && !remove_info ) {
        if( over_viewport_content ) {
            if( const std::optional<point_rel_ms> mount = viewport_to_mount( *viewport_pos ) ) {
                select_mount( here, *mount );
                open_editor_context_menu( here, *viewport_pos );
            }
            return true;
        }
        close_editor_context_menu();
        return false;
    }

    if( action == "SELECT" && !install_info && !remove_info ) {
        if( editor_context_open && viewport_pos ) {
            return handle_editor_context_click( here, *viewport_pos );
        }
        if( viewport_pos && handle_editor_controls_click( *viewport_pos ) ) {
''', "context mouse dispatch")

# Draw Test checkbox and context overlay.
s = replace_once(s,
'''    if( condition_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),
                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,
                        condition_button );
    }

    if( open_editor_dropdown == editor_dropdown::none ) {
''',
'''    if( condition_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),
                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,
                        condition_button );
    }

    if( vehicle_editor_test_mode_visible ) {
        const int test_x = condition_x + condition_width + 2;
        const std::string test_label = editor_test_mode ? _( "[x] Test" ) : _( "[ ] Test" );
        if( test_x < width - 1 ) {
            trim_and_print( w_disp, point( test_x, 2 ), std::max( 1, width - test_x - 1 ),
                            editor_test_mode ? h_light_red : c_light_gray, test_label );
        }
    }

    if( open_editor_dropdown == editor_dropdown::none ) {
''', "test checkbox draw")
s = replace_once(s,
'''    display_editor_controls();
    wnoutrefresh( w_disp );
''',
'''    display_editor_controls();
    display_editor_context_menu();
    wnoutrefresh( w_disp );
''', "context menu draw")

# Test marker at completion.
s = replace_once(s,
'''    const vpart_id part_id( you.activity.str_values[0] );
    const vpart_info &vpinfo = part_id.obj();
''',
'''    const vpart_id part_id( you.activity.str_values[0] );
    const vpart_info &vpinfo = part_id.obj();
    const bool editor_test = you.activity.str_values.size() > 1 &&
                             you.activity.str_values[1] == "vehicle_editor_test";
''', "completion test marker")

# Test install: no requirements/consumption, real install_part mutation.
old_install = '''            const inventory &inv = you.crafting_inventory();
            const requirement_data reqs = vpinfo.install_requirements();
            if( !reqs.can_make_with_inventory( inv, is_crafting_component, 1, craft_flags::none, false ) ) {
                you.add_msg_player_or_npc( m_info,
                                           _( "You don't meet the requirements to install the %s." ),
                                           _( "<npcname> doesn't meet the requirements to install the %s." ),
                                           vpinfo.name() );
                break;
            }

            // consume items extracting a match for the parts base item
            item base;
            std::vector<item> installed_with;
            for( const std::vector<item_comp> &e : reqs.get_components() ) {
                for( item &obj : you.consume_items( e, 1, is_crafting_component, [&vpinfo]( const itype_id & itm ) {
                return itm == vpinfo.base_item;
            } ) ) {
                    if( obj.typeId() == vpinfo.base_item ) {
                        base = obj;
                    } else {
                        installed_with.push_back( obj );
                    }
                }
            }
            if( base.is_null() ) {
                if( !you.has_trait( trait_DEBUG_HS ) ) {
                    add_msg( m_info, _( "Could not find base part in requirements for %s." ), vpinfo.name() );
                    break;
                } else {
                    base = item( vpinfo.base_item );
                }
            }

            for( const auto &e : reqs.get_tools() ) {
                you.consume_tools( e );
            }

            you.invalidate_crafting_inventory();
'''
new_install = '''            const inventory &inv = you.crafting_inventory();
            const requirement_data reqs = vpinfo.install_requirements();
            if( !editor_test &&
                !reqs.can_make_with_inventory( inv, is_crafting_component, 1, craft_flags::none, false ) ) {
                you.add_msg_player_or_npc( m_info,
                                           _( "You don't meet the requirements to install the %s." ),
                                           _( "<npcname> doesn't meet the requirements to install the %s." ),
                                           vpinfo.name() );
                break;
            }

            item base;
            std::vector<item> installed_with;
            if( editor_test ) {
                base = item( vpinfo.base_item );
            } else {
                for( const std::vector<item_comp> &e : reqs.get_components() ) {
                    for( item &obj : you.consume_items( e, 1, is_crafting_component, [&vpinfo]( const itype_id & itm ) {
                    return itm == vpinfo.base_item;
                } ) ) {
                        if( obj.typeId() == vpinfo.base_item ) {
                            base = obj;
                        } else {
                            installed_with.push_back( obj );
                        }
                    }
                }
                if( base.is_null() ) {
                    if( !you.has_trait( trait_DEBUG_HS ) ) {
                        add_msg( m_info, _( "Could not find base part in requirements for %s." ), vpinfo.name() );
                        break;
                    }
                    base = item( vpinfo.base_item );
                }

                for( const auto &e : reqs.get_tools() ) {
                    you.consume_tools( e );
                }
                you.invalidate_crafting_inventory();
            }
'''
s = replace_once(s, old_install, new_install, "completion install test")
s = replace_once(s,
'''            for( const auto &sk : vpinfo.install_skills ) {
                you.practice( sk.first, veh_utils::calc_xp_gain( vpinfo, sk.first, you ) );
            }
''',
'''            if( !editor_test ) {
                for( const auto &sk : vpinfo.install_skills ) {
                    you.practice( sk.first, veh_utils::calc_xp_gain( vpinfo, sk.first, you ) );
                }
            }
''', "test install xp")
s = replace_once(s,
'''            veh_utils::repair_part( here, veh, vp, you );
''',
'''            veh_utils::repair_part( here, veh, vp, you, !editor_test );
''', "test repair completion")

# Test remove: preserve cargo contents, but do not require/consume resources or generate free salvage/parts.
s = replace_once(s,
'''            if( !reqs.can_make_with_inventory( inv, is_crafting_component ) ) {
''',
'''            if( !editor_test && !reqs.can_make_with_inventory( inv, is_crafting_component ) ) {
''', "test remove requirements")
s = replace_once(s,
'''            for( const auto &e : reqs.get_components() ) {
                you.consume_items( e, 1, is_crafting_component );
            }
            for( const auto &e : reqs.get_tools() ) {
                you.consume_tools( e );
            }

            you.invalidate_crafting_inventory();
''',
'''            if( !editor_test ) {
                for( const auto &e : reqs.get_components() ) {
                    you.consume_items( e, 1, is_crafting_component );
                }
                for( const auto &e : reqs.get_tools() ) {
                    you.consume_tools( e );
                }
                you.invalidate_crafting_inventory();
            }
''', "test remove consumption")
# Guard all removal salvage generation, leaving the pre-existing cargo-content extraction untouched.
s = replace_once(s,
'''            if( wall_wire_removal ) {
                veh.part_to_item( here, *vp ); // what's going on here? this line isn't doing anything...
            } else if( vpi.has_flag( "TOW_CABLE" ) ) {
                veh.invalidate_towing( here, true, &you );
            } else if( broken ) {
                item_group::ItemList pieces = vp->pieces_for_broken_part();
                resulting_items.insert( resulting_items.end(), pieces.begin(), pieces.end() );
            } else {
''',
'''            if( wall_wire_removal ) {
                if( !editor_test ) {
                    veh.part_to_item( here, *vp );
                }
            } else if( vpi.has_flag( "TOW_CABLE" ) ) {
                veh.invalidate_towing( here, true, &you );
            } else if( editor_test ) {
                // Test removal intentionally produces no part/salvage items.
            } else if( broken ) {
                item_group::ItemList pieces = vp->pieces_for_broken_part();
                resulting_items.insert( resulting_items.end(), pieces.begin(), pieces.end() );
            } else {
''', "test removal salvage")
s = replace_once(s,
'''                for( const std::pair<const skill_id, int> &sk : vpi.install_skills ) {
                    // removal is half as educational as installation
                    you.practice( sk.first, veh_utils::calc_xp_gain( vpi, sk.first, you ) / 2 );
                }
''',
'''                if( !editor_test ) {
                    for( const std::pair<const skill_id, int> &sk : vpi.install_skills ) {
                        // removal is half as educational as installation
                        you.practice( sk.first, veh_utils::calc_xp_gain( vpi, sk.first, you ) / 2 );
                    }
                }
''', "test removal xp")

p.write_text(s)

# ---------------- permanent toggle workflow ----------------
p = Path(".github/workflows/toggle-vehicle-editor-test-mode.yml")
p.write_text('''name: Toggle vehicle editor Test mode\n\non:\n  workflow_dispatch:\n    inputs:\n      visible:\n        description: "Expose the vehicle editor Test checkbox"\n        required: true\n        type: choice\n        default: "false"\n        options:\n          - "false"\n          - "true"\n\npermissions:\n  contents: write\n\njobs:\n  toggle:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          ref: mouse-inventory-0-i-test\n          fetch-depth: 1\n      - name: Toggle exposure guard\n        env:\n          VISIBLE: ${{ inputs.visible }}\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3 - <<'PY'\n          import os\n          from pathlib import Path\n          p = Path("src/veh_interact.cpp")\n          s = p.read_text()\n          old_true = "static constexpr bool vehicle_editor_test_mode_visible = true;"\n          old_false = "static constexpr bool vehicle_editor_test_mode_visible = false;"\n          desired = os.environ["VISIBLE"].lower() == "true"\n          if s.count(old_true) + s.count(old_false) != 1:\n              raise SystemExit("vehicle editor Test visibility guard is missing or duplicated")\n          s = s.replace(old_true, old_false).replace(\n              old_false, old_true if desired else old_false, 1\n          ) if desired else s.replace(old_true, old_false)\n          p.write_text(s)\n          PY\n          git diff --check\n          if git diff --quiet; then\n            echo "Already in requested state."\n            exit 0\n          fi\n          git config user.name github-actions[bot]\n          git config user.email 41898282+github-actions[bot]@users.noreply.github.com\n          git add src/veh_interact.cpp\n          git commit -m "Toggle vehicle editor Test mode exposure"\n          git push origin HEAD:mouse-inventory-0-i-test\n''')

print("patched vehicle editor context menu, Test mode, layers, condition semantics, and ghost visibility")
