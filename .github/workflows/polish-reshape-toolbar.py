from pathlib import Path

paths = {
    'veh_h': Path('src/veh_interact.h'),
    'veh_cpp': Path('src/veh_interact.cpp'),
    'sdl_h': Path('src/sdltiles.h'),
    'sdl_cpp': Path('src/sdltiles.cpp'),
    'tiles_h': Path('src/cata_tiles.h'),
    'tiles_cpp': Path('src/cata_tiles.cpp'),
}
text = {k: p.read_text() for k, p in paths.items()}


def rep(key, old, new, label, count=1):
    found = text[key].count(old)
    if found != count:
        raise SystemExit(f'{label}: expected {count} match(es), got {found}')
    text[key] = text[key].replace(old, new, count)


def replace_function(key, signature, replacement, label):
    src = text[key]
    start = src.find(signature)
    if start < 0:
        raise SystemExit(f'{label}: signature not found')
    brace = src.find('{', start)
    if brace < 0:
        raise SystemExit(f'{label}: opening brace not found')
    depth = 0
    in_string = False
    in_char = False
    escape = False
    i = brace
    while i < len(src):
        ch = src[i]
        if escape:
            escape = False
        elif ch == '\\' and (in_string or in_char):
            escape = True
        elif ch == '"' and not in_char:
            in_string = not in_string
        elif ch == "'" and not in_string:
            in_char = not in_char
        elif not in_string and not in_char:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    text[key] = src[:start] + replacement.rstrip() + src[i + 1:]
                    return
        i += 1
    raise SystemExit(f'{label}: unterminated function')


# ---------------------------------------------------------------------------
# Tileset visual-equivalence bridge.  Reshape already asks the active tileset
# whether a variant exists; expose whether two resolved variant definitions are
# actually the same complete visual so cosmetic aliases can collapse in the UI.
# ---------------------------------------------------------------------------
rep('sdl_h',
'''bool has_vehicle_part_preview_tile( const std::string &part_id, const std::string &variant );\n''',
'''bool has_vehicle_part_preview_tile( const std::string &part_id, const std::string &variant );\nbool same_vehicle_part_preview_tile( const std::string &part_id, const std::string &lhs_variant,\n                                     const std::string &rhs_variant );\n''',
'sdl visual-equivalence declaration')

rep('tiles_h',
'''        bool has_vehicle_part_preview_tile( const std::string &part_id,\n                                            const std::string &variant ) const;\n        bool draw_vehicle_part_preview( const point &dest, const point &size,\n''',
'''        bool has_vehicle_part_preview_tile( const std::string &part_id,\n                                            const std::string &variant ) const;\n        bool same_vehicle_part_preview_tile( const std::string &part_id,\n                                             const std::string &lhs_variant,\n                                             const std::string &rhs_variant ) const;\n        bool draw_vehicle_part_preview( const point &dest, const point &size,\n''',
'tiles visual-equivalence declaration')

has_tile_impl = r'''bool cata_tiles::has_vehicle_part_preview_tile( const std::string &part_id,
        const std::string &variant ) const
{
    if( !tileset_ptr || part_id.empty() ) {
        return false;
    }
    return find_tile_looks_like( "vp_" + part_id, TILE_CATEGORY::VEHICLE_PART, variant ).has_value();
}

bool cata_tiles::same_vehicle_part_preview_tile( const std::string &part_id,
        const std::string &lhs_variant, const std::string &rhs_variant ) const
{
    if( !tileset_ptr || part_id.empty() ) {
        return false;
    }
    std::optional<tile_lookup_res> lhs =
        find_tile_looks_like( "vp_" + part_id, TILE_CATEGORY::VEHICLE_PART, lhs_variant );
    std::optional<tile_lookup_res> rhs =
        find_tile_looks_like( "vp_" + part_id, TILE_CATEGORY::VEHICLE_PART, rhs_variant );
    if( !lhs || !rhs ) {
        return false;
    }

    const auto same_definition = []( const tile_type &a, const tile_type &b ) {
        return a.fg == b.fg && a.bg == b.bg && a.multitile == b.multitile &&
               a.rotates == b.rotates && a.animated == b.animated &&
               a.height_3d == b.height_3d && a.offset == b.offset &&
               a.offset_retracted == b.offset_retracted && a.pixelscale == b.pixelscale &&
               a.available_subtiles == b.available_subtiles;
    };

    if( !same_definition( lhs->tile(), rhs->tile() ) ) {
        return false;
    }

    // Doors and other multitiles can share a closed sprite while differing when
    // opened/broken.  Compare their authored subtiles too before collapsing them.
    for( const std::string &subtile : lhs->tile().available_subtiles ) {
        const tile_type *lhs_sub = tileset_ptr->find_tile_type( lhs->id() + "_" + subtile );
        const tile_type *rhs_sub = tileset_ptr->find_tile_type( rhs->id() + "_" + subtile );
        if( ( lhs_sub == nullptr ) != ( rhs_sub == nullptr ) ) {
            return false;
        }
        if( lhs_sub != nullptr && !same_definition( *lhs_sub, *rhs_sub ) ) {
            return false;
        }
    }
    return true;
}'''
replace_function('tiles_cpp',
                 'bool cata_tiles::has_vehicle_part_preview_tile( const std::string &part_id,',
                 has_tile_impl, 'tiles visual-equivalence implementation')

sdl_has_impl = r'''bool has_vehicle_part_preview_tile( const std::string &part_id, const std::string &variant )
{
    if( !use_tiles ) {
        return false;
    }
    const std::shared_ptr<cata_tiles> draw_tiles = closetilecontext ? closetilecontext : tilecontext;
    return draw_tiles && draw_tiles->has_vehicle_part_preview_tile( part_id, variant );
}

bool same_vehicle_part_preview_tile( const std::string &part_id, const std::string &lhs_variant,
                                     const std::string &rhs_variant )
{
    if( !use_tiles ) {
        return false;
    }
    const std::shared_ptr<cata_tiles> draw_tiles = closetilecontext ? closetilecontext : tilecontext;
    return draw_tiles && draw_tiles->same_vehicle_part_preview_tile( part_id, lhs_variant, rhs_variant );
}'''
replace_function('sdl_cpp', 'bool has_vehicle_part_preview_tile( const std::string &part_id,',
                 sdl_has_impl, 'sdl visual-equivalence implementation')


# ---------------------------------------------------------------------------
# Toolbar inline dropdown state.
# ---------------------------------------------------------------------------
rep('veh_h',
'''        std::string editor_toolbar_hover_action;\n        std::string pending_editor_action;\n''',
'''        std::string editor_toolbar_hover_action;\n        std::string pending_editor_action;\n        std::string open_editor_toolbar_dropdown;\n        point editor_toolbar_dropdown_pos = point::zero;\n        int editor_toolbar_dropdown_width = 0;\n        int editor_toolbar_dropdown_height = 0;\n        std::vector<editor_context_button> editor_toolbar_dropdown_buttons;\n''',
'toolbar dropdown state')

rep('veh_h',
'''        void open_editor_toolbar_menu( const map &here, const std::string &which );\n        bool handle_editor_mouse( map &here, const std::string &action );\n''',
'''        void open_editor_toolbar_menu( const map &here, const std::string &which );\n        void close_editor_toolbar_dropdown();\n        bool handle_editor_toolbar_dropdown_mouse( const std::string &action );\n        void display_editor_toolbar_dropdown();\n        bool handle_editor_mouse( map &here, const std::string &action );\n''',
'toolbar dropdown methods')


# ---------------------------------------------------------------------------
# Reshape visual dedupe.
# ---------------------------------------------------------------------------
reshape_helper = r'''static bool reshape_part_has_visible_variants( const vpart_info &vpi )
{
    if( vpi.variants.size() <= 1 ) {
        return false;
    }
#if defined(TILES)
    // JSON may contain visual aliases (doors are a common example) as well as
    // variants the active tileset does not author.  A part is meaningfully
    // reshapeable only when at least two distinct rendered definitions exist.
    std::vector<std::string> distinct;
    for( const auto &[variant_id, variant] : vpi.variants ) {
        ( void )variant;
        if( !has_vehicle_part_preview_tile( vpi.id.str(), variant_id ) ) {
            continue;
        }
        const bool duplicate = std::any_of( distinct.begin(), distinct.end(),
        [&]( const std::string &existing ) {
            return same_vehicle_part_preview_tile( vpi.id.str(), existing, variant_id );
        } );
        if( !duplicate ) {
            distinct.push_back( variant_id );
            if( distinct.size() > 1 ) {
                return true;
            }
        }
    }
    return false;
#else
    return true;
#endif
}'''
replace_function('veh_cpp', 'static bool reshape_part_has_visible_variants( const vpart_info &vpi )',
                 reshape_helper, 'reshape distinct-visual predicate')

rep('veh_cpp',
'''    for( const auto &[variant_id, variant] : vpi.variants ) {\n        ( void )variant;\n#if defined(TILES)\n        if( !has_vehicle_part_preview_tile( vpi.id.str(), variant_id ) ) {\n            continue;\n        }\n#endif\n        reshape_info->variants.push_back( variant_id );\n    }\n''',
'''    for( const auto &[variant_id, variant] : vpi.variants ) {\n        ( void )variant;\n#if defined(TILES)\n        if( !has_vehicle_part_preview_tile( vpi.id.str(), variant_id ) ) {\n            continue;\n        }\n        auto duplicate = std::find_if( reshape_info->variants.begin(), reshape_info->variants.end(),\n        [&]( const std::string &existing ) {\n            return same_vehicle_part_preview_tile( vpi.id.str(), existing, variant_id );\n        } );\n        if( duplicate != reshape_info->variants.end() ) {\n            // Preserve the exact committed alias as the visible representative so\n            // Current/selection state remains lossless even though its twins hide.\n            if( variant_id == reshape_info->committed_variant ) {\n                *duplicate = variant_id;\n            }\n            continue;\n        }\n#endif\n        reshape_info->variants.push_back( variant_id );\n    }\n''',
'reshape variant visual dedupe')

rep('veh_cpp',
'''            if( vpi.variants.size() > 1 ) {\n                add_entry( _( "Reshape…" ), "EDITOR_RESHAPE" );\n            }\n''',
'''            if( reshape_part_has_visible_variants( vpi ) ) {\n                add_entry( _( "Reshape…" ), "EDITOR_RESHAPE" );\n            }\n''',
'right-click reshape distinct-visual eligibility')


# ---------------------------------------------------------------------------
# Two-stage Escape in reshape: cancel a temporary preview first, then close.
# ---------------------------------------------------------------------------
rep('veh_cpp',
'''        if( action == "QUIT" && reshape_info ) {\n            close_reshape_mode();\n            continue;\n        }\n''',
'''        if( action == "QUIT" && reshape_info ) {\n            bool canceled_preview = false;\n            const int target = reshape_info->target_part;\n            if( target >= 0 && target < veh->part_count() ) {\n                vehicle_part &part = veh->part( target );\n                if( !part.removed && part.variant != reshape_info->committed_variant ) {\n                    part.variant = reshape_info->committed_variant;\n                    const auto committed = std::find( reshape_info->variants.begin(),\n                                                       reshape_info->variants.end(),\n                                                       reshape_info->committed_variant );\n                    if( committed != reshape_info->variants.end() ) {\n                        reshape_info->variant_pos = static_cast<int>( std::distance(\n                                                        reshape_info->variants.begin(), committed ) );\n                    }\n                    reshape_info->last_clicked_variant = -1;\n                    reshape_info->last_click_time.reset();\n                    msg.reset();\n                    canceled_preview = true;\n                }\n            }\n            if( !canceled_preview ) {\n                close_reshape_mode();\n            }\n            continue;\n        }\n''',
'two-stage reshape escape')

# Entering reshape and activity re-entry cannot retain a transient toolbar dropdown.
rep('veh_cpp',
'''    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n    viewport_dragging = false;\n''',
'''    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n    close_editor_toolbar_dropdown();\n    viewport_dragging = false;\n''',
'close toolbar dropdown on reshape entry')

rep('veh_cpp',
'''    pending_editor_action.clear();\n    msg.reset();\n''',
'''    pending_editor_action.clear();\n    close_editor_toolbar_dropdown();\n    msg.reset();\n''',
'clear toolbar dropdown on activity reentry')


# ---------------------------------------------------------------------------
# Inline Modify / More dropdowns.  Narrow-screen Actions deliberately keeps its
# old modal fallback for now; the requested first-class toolbar menus no longer
# create a uilist.
# ---------------------------------------------------------------------------
toolbar_menu_impl = r'''void veh_interact::open_editor_toolbar_menu( const map &here, const std::string &which )
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
    } else {
        return;
    }

    if( entries.empty() ) {
        return;
    }

    // Keep the tiny/narrow fallback behavior until that toolbar is redesigned;
    // Modify and More are the normal desktop toolbar dropdowns requested here.
    if( which == "TOOLBAR_MENU_ACTIONS" ) {
        uilist menu;
        menu.text = _( "Vehicle actions" );
        for( int i = 0; i < static_cast<int>( entries.size() ); ++i ) {
            menu.addentry( i, editor_toolbar_action_enabled( here, entries[i].action ), -1,
                           entries[i].label );
        }
        menu.query();
        if( menu.ret >= 0 && menu.ret < static_cast<int>( entries.size() ) &&
            editor_toolbar_action_enabled( here, entries[menu.ret].action ) ) {
            pending_editor_action = entries[menu.ret].action;
        }
        return;
    }

    if( open_editor_toolbar_dropdown == which ) {
        close_editor_toolbar_dropdown();
        return;
    }

    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    open_editor_toolbar_dropdown = which;
    editor_toolbar_dropdown_buttons.clear();

    int widest = 0;
    for( const toolbar_menu_entry &entry : entries ) {
        widest = std::max( widest, utf8_width( entry.label ) );
        editor_toolbar_dropdown_buttons.push_back( {
            entry.label, point::zero, 0, entry.action, std::string(),
            editor_toolbar_action_enabled( here, entry.action )
        } );
    }
    editor_toolbar_dropdown_width = std::clamp( widest + 4, 14,
                                    std::max( 14, getmaxx( w_border ) - 2 ) );
    editor_toolbar_dropdown_height = static_cast<int>( editor_toolbar_dropdown_buttons.size() ) + 2;

    int anchor_x = 1;
    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {
        if( button.action == which ) {
            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );
            break;
        }
    }
    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );
    const int x = std::clamp( anchor_x, 1, max_x );
    const int desired_y = getbegy( w_disp ) - getbegy( w_border );
    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );
    const int y = std::clamp( desired_y, 1, max_y );
    editor_toolbar_dropdown_pos = point( x, y );

    for( int i = 0; i < static_cast<int>( editor_toolbar_dropdown_buttons.size() ); ++i ) {
        editor_toolbar_dropdown_buttons[i].pos = point( x + 1, y + 1 + i );
        editor_toolbar_dropdown_buttons[i].width = std::max( 1, editor_toolbar_dropdown_width - 2 );
    }
}

void veh_interact::close_editor_toolbar_dropdown()
{
    open_editor_toolbar_dropdown.clear();
    editor_toolbar_dropdown_buttons.clear();
    editor_toolbar_dropdown_width = 0;
    editor_toolbar_dropdown_height = 0;
    editor_toolbar_dropdown_pos = point::zero;
}

bool veh_interact::handle_editor_toolbar_dropdown_mouse( const std::string &action )
{
    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_width <= 0 ||
        editor_toolbar_dropdown_height < 3 ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_border );
    if( !pos ) {
        return false;
    }

    const bool inside = pos->x >= editor_toolbar_dropdown_pos.x &&
                        pos->x < editor_toolbar_dropdown_pos.x + editor_toolbar_dropdown_width &&
                        pos->y >= editor_toolbar_dropdown_pos.y &&
                        pos->y < editor_toolbar_dropdown_pos.y + editor_toolbar_dropdown_height;

    if( action == "MOUSE_MOVE" ) {
        return inside;
    }
    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        // An open dropdown owns wheel input so the camera/list underneath cannot move.
        return true;
    }
    if( action == "SEC_SELECT" ) {
        close_editor_toolbar_dropdown();
        return false;
    }
    if( action != "SELECT" ) {
        return false;
    }

    if( inside ) {
        for( const editor_context_button &button : editor_toolbar_dropdown_buttons ) {
            if( pos->y == button.pos.y && pos->x >= button.pos.x &&
                pos->x < button.pos.x + button.width ) {
                if( !button.enabled ) {
                    msg = _( "That action is not available for the current selection." );
                    return true;
                }
                pending_editor_action = button.action;
                close_editor_toolbar_dropdown();
                return false;
            }
        }
        return true;
    }

    // Same click-through behavior as the editor filter dropdowns: clicking the
    // vehicle/inspector closes this transient UI and still applies the click.
    close_editor_toolbar_dropdown();
    return false;
}

void veh_interact::display_editor_toolbar_dropdown()
{
    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_buttons.empty() ) {
        return;
    }

    // Re-anchor after resize/responsive toolbar changes while keeping the menu
    // attached to the button that opened it.
    int anchor_x = editor_toolbar_dropdown_pos.x;
    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {
        if( button.action == open_editor_toolbar_dropdown ) {
            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );
            break;
        }
    }
    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );
    editor_toolbar_dropdown_pos.x = std::clamp( anchor_x, 1, max_x );
    const int desired_y = getbegy( w_disp ) - getbegy( w_border );
    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );
    editor_toolbar_dropdown_pos.y = std::clamp( desired_y, 1, max_y );

    for( int i = 0; i < static_cast<int>( editor_toolbar_dropdown_buttons.size() ); ++i ) {
        editor_toolbar_dropdown_buttons[i].pos = editor_toolbar_dropdown_pos + point( 1, 1 + i );
        editor_toolbar_dropdown_buttons[i].width = std::max( 1, editor_toolbar_dropdown_width - 2 );
    }

    const std::string blank( editor_toolbar_dropdown_width, ' ' );
    for( int row = 0; row < editor_toolbar_dropdown_height; ++row ) {
        mvwprintz( w_border, editor_toolbar_dropdown_pos + point( 0, row ), c_black, "%s", blank );
    }
    mvwhline( w_border, editor_toolbar_dropdown_pos, c_light_cyan, LINE_OXOX,
              editor_toolbar_dropdown_width );
    mvwhline( w_border, editor_toolbar_dropdown_pos + point( 0, editor_toolbar_dropdown_height - 1 ),
              c_light_cyan, LINE_OXOX, editor_toolbar_dropdown_width );
    mvwvline( w_border, editor_toolbar_dropdown_pos, c_light_cyan, LINE_XOXO,
              editor_toolbar_dropdown_height );
    mvwvline( w_border, editor_toolbar_dropdown_pos + point( editor_toolbar_dropdown_width - 1, 0 ),
              c_light_cyan, LINE_XOXO, editor_toolbar_dropdown_height );
    mvwputch( w_border, editor_toolbar_dropdown_pos, c_light_cyan, LINE_OXXO );
    mvwputch( w_border, editor_toolbar_dropdown_pos + point( editor_toolbar_dropdown_width - 1, 0 ),
              c_light_cyan, LINE_OOXX );
    mvwputch( w_border, editor_toolbar_dropdown_pos + point( 0, editor_toolbar_dropdown_height - 1 ),
              c_light_cyan, LINE_XXOO );
    mvwputch( w_border, editor_toolbar_dropdown_pos +
              point( editor_toolbar_dropdown_width - 1, editor_toolbar_dropdown_height - 1 ),
              c_light_cyan, LINE_XOOX );

    for( const editor_context_button &button : editor_toolbar_dropdown_buttons ) {
        trim_and_print( w_border, button.pos, button.width,
                        button.enabled ? c_light_gray : c_dark_gray, button.label );
    }
    wnoutrefresh( w_border );
}'''
replace_function('veh_cpp', 'void veh_interact::open_editor_toolbar_menu( const map &here,',
                 toolbar_menu_impl, 'inline toolbar dropdown implementation')

# Toolbar button opens inline state and mutually excludes filter/context dropdowns.
rep('veh_cpp',
'''        if( button.action.starts_with( "TOOLBAR_MENU_" ) ) {\n            close_editor_context_menu();\n            open_editor_toolbar_menu( here, button.action );\n            return pending_editor_action.empty();\n        }\n''',
'''        if( button.action.starts_with( "TOOLBAR_MENU_" ) ) {\n            close_editor_context_menu();\n            open_editor_dropdown = editor_dropdown::none;\n            open_editor_toolbar_menu( here, button.action );\n            return pending_editor_action.empty();\n        }\n''',
'toolbar menu button opens inline dropdown')

rep('veh_cpp',
'''            close_editor_context_menu();\n            open_editor_dropdown = editor_dropdown::none;\n        }\n        pending_editor_action = button.action;\n''',
'''            close_editor_context_menu();\n            open_editor_dropdown = editor_dropdown::none;\n            close_editor_toolbar_dropdown();\n        }\n        pending_editor_action = button.action;\n''',
'back closes toolbar dropdown')

# Draw the toolbar button as active while its inline dropdown is open.
display_mode_impl = r'''void veh_interact::display_mode( const map &here )
{
    werase( w_mode );

    if( title.has_value() && !install_info ) {
        close_editor_toolbar_dropdown();
        nc_color title_col = c_light_gray;
        print_colored_text( w_mode, point( 1, 0 ), title_col, title_col, title.value() );
        wnoutrefresh( w_mode );
        return;
    }

    rebuild_editor_toolbar( here );
    for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[i];
        const bool menu_button = button.action.starts_with( "TOOLBAR_MENU_" );
        const std::string shown = menu_button ? string_format( "[ %s ▼ ]", button.label ) :
                                  string_format( "[ %s ]", button.label );
        const bool hovered = i == editor_toolbar_hover_button;
        const bool open = menu_button && open_editor_toolbar_dropdown == button.action;
        const nc_color color = !button.enabled ? c_dark_gray :
                               ( hovered || open ) ? h_light_cyan : c_light_cyan;
        trim_and_print( w_mode, button.pos, button.width, color, shown );
    }
    wnoutrefresh( w_mode );
    display_editor_toolbar_dropdown();
}'''
replace_function('veh_cpp', 'void veh_interact::display_mode( const map &here )',
                 display_mode_impl, 'display inline toolbar dropdown')

# Route the dropdown before modal workflows/viewports; selected dropdown actions
# use the existing pending-action dispatch just like toolbar buttons.
rep('veh_cpp',
'''    if( refuel_info ) {\n        return handle_refuel_mouse( here, action );\n    }\n''',
'''    if( !open_editor_toolbar_dropdown.empty() ) {\n        const bool dropdown_handled = handle_editor_toolbar_dropdown_mouse( action );\n        if( !pending_editor_action.empty() ) {\n            return false;\n        }\n        if( dropdown_handled ) {\n            return true;\n        }\n    }\n\n    if( refuel_info ) {\n        return handle_refuel_mouse( here, action );\n    }\n''',
'route toolbar dropdown mouse')

# Open inline toolbar dropdowns block camera dragging/zoom input underneath them.
rep('veh_cpp',
'''        middle_mouse_down && mouse_focused && open_editor_dropdown == editor_dropdown::none &&\n        !editor_context_open ) {\n''',
'''        middle_mouse_down && mouse_focused && open_editor_dropdown == editor_dropdown::none &&\n        open_editor_toolbar_dropdown.empty() && !editor_context_open ) {\n''',
'block drag under toolbar dropdown')

rep('veh_cpp',
'''        if( open_editor_dropdown != editor_dropdown::none || editor_context_open || !viewport_pos ) {\n''',
'''        if( open_editor_dropdown != editor_dropdown::none ||\n            !open_editor_toolbar_dropdown.empty() || editor_context_open || !viewport_pos ) {\n''',
'block pan start under toolbar dropdown')

rep('veh_cpp',
'''        if( open_editor_dropdown != editor_dropdown::none || editor_context_open ) {\n            return true;\n        }\n''',
'''        if( open_editor_dropdown != editor_dropdown::none ||\n            !open_editor_toolbar_dropdown.empty() || editor_context_open ) {\n            return true;\n        }\n''',
'block wheel under toolbar dropdown')

# Context menus are mutually exclusive with the new toolbar dropdown.
rep('veh_cpp',
'''    const bool had_transient_menu = editor_context_open ||\n                                    open_editor_dropdown != editor_dropdown::none;\n    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n''',
'''    const bool had_transient_menu = editor_context_open ||\n                                    open_editor_dropdown != editor_dropdown::none ||\n                                    !open_editor_toolbar_dropdown.empty();\n    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n    close_editor_toolbar_dropdown();\n''',
'context menu closes toolbar dropdown')

# Keyboard Esc closes the toolbar dropdown before leaving the normal editor.
rep('veh_cpp',
'''        // Escape dismisses transient editor menus before it is allowed to close\n        // a mode or the vehicle editor itself.\n        if( action == "QUIT" && editor_context_open ) {\n''',
'''        // Escape dismisses transient editor menus before it is allowed to close\n        // a mode or the vehicle editor itself.\n        if( action == "QUIT" && !open_editor_toolbar_dropdown.empty() ) {\n            close_editor_toolbar_dropdown();\n            continue;\n        }\n        if( action == "QUIT" && editor_context_open ) {\n''',
'toolbar dropdown escape priority')

# SDL map preview is outside curses ordering, so suppress it while the inline
# toolbar dropdown overlays the editor body (same reason refuel does this).
rep('veh_cpp',
'''void veh_interact::display_live_preview( map &here )\n{\n#if defined(TILES)\n    if( active_editor_view_mode == editor_view_mode::editor ) {\n''',
'''void veh_interact::display_live_preview( map &here )\n{\n#if defined(TILES)\n    if( !open_editor_toolbar_dropdown.empty() ) {\n        live_preview_last_draw_mode.reset();\n        clear_map_preview_window();\n        return;\n    }\n    if( active_editor_view_mode == editor_view_mode::editor ) {\n''',
preserve toolbar dropdown over live preview')


# Structural assertions.
assert 'same_vehicle_part_preview_tile' in text['veh_cpp']
assert 'same_vehicle_part_preview_tile' in text['sdl_cpp']
assert 'same_vehicle_part_preview_tile' in text['tiles_cpp']
assert 'part.variant != reshape_info->committed_variant' in text['veh_cpp']
assert 'if( !canceled_preview )' in text['veh_cpp']
assert 'open_editor_toolbar_dropdown' in text['veh_h']
assert 'display_editor_toolbar_dropdown();' in text['veh_cpp']
assert 'if( which == "TOOLBAR_MENU_ACTIONS" ) {' in text['veh_cpp']
assert 'if( reshape_part_has_visible_variants( vpi ) ) {' in text['veh_cpp']
assert 'if( vpi.variants.size() > 1 ) {\n                add_entry( _( "Reshape…" )' not in text['veh_cpp']

for key, path in paths.items():
    path.write_text(text[key])
print('reshape visual dedupe + two-stage Esc + inline toolbar dropdown patch applied')
