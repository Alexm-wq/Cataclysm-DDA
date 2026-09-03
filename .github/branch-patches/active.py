from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"guard failed in {path}: expected text not found")
    if text.count(old) != 1:
        raise SystemExit(f"guard failed in {path}: expected one match, found {text.count(old)}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/game.h",
    "        bool try_get_right_click_action( action_id &act, const tripoint_bub_ms &mouse_target );\n",
    "        bool try_get_right_click_action( action_id &act, const tripoint_bub_ms &mouse_target,\n"
    "                                         const point &menu_anchor );\n",
)

replace_once(
    "src/game.cpp",
    "bool game::try_get_right_click_action( action_id &act, const tripoint_bub_ms &mouse_target )\n",
    "bool game::try_get_right_click_action( action_id &act, const tripoint_bub_ms &mouse_target,\n"
    "        const point &menu_anchor )\n",
)

replace_once(
    "src/game.cpp",
    "    if( is_adjacent && !is_self &&\n"
    "        ( here.is_bashable( mouse_target ) || here.veh_at( mouse_target ).obstacle_at_part() ) ) {\n"
    "        add_action( ACTION_SMASH );\n"
    "    }\n",
    "    if( is_adjacent && !is_self &&\n"
    "        ( here.is_bashable( mouse_target ) || here.veh_at( mouse_target ).obstacle_at_part() ) ) {\n"
    "        std::string smash_target = here.name( mouse_target );\n"
    "        if( const std::optional<vpart_reference> obstacle =\n"
    "                here.veh_at( mouse_target ).obstacle_at_part() ) {\n"
    "            smash_target = obstacle->info().name();\n"
    "        }\n"
    "        entries.emplace_back( string_format( _( \"Smash %s\" ), smash_target ),\n"
    "                              action_ident( ACTION_SMASH ) );\n"
    "    }\n",
)

replace_once(
    "src/game.cpp",
    "    // ui_dropdown is the shared mouse-first context-menu helper.  Anchor it to the clicked\n"
    "    // map square in screen coordinates and let the helper handle clamping, hover and input.\n"
    "    const point terrain_anchor = mouse_target.xy().raw() - ter_view_p.xy().raw() + point( POSX, POSY );\n"
    "    const point anchor = terrain_anchor + point( getbegx( w_terrain ), getbegy( w_terrain ) );\n\n",
    "    // ui_dropdown is the shared mouse-first context-menu helper.  The gameplay input\n"
    "    // context already resolved the exact screen-space mouse position, including tile\n"
    "    // zoom/isometric projection, so use it directly instead of reconstructing it from\n"
    "    // world coordinates.\n\n",
)

replace_once(
    "src/game.cpp",
    "        context_menu.configure( catacurses::stdscr, anchor, entries, 0, style );\n",
    "        context_menu.configure( catacurses::stdscr, menu_anchor, entries, 0, style );\n",
)

replace_once(
    "src/handle_action.cpp",
    "static void open()\n"
    "{\n"
    "    map &here = get_map();\n\n"
    "    avatar &player_character = get_avatar();\n"
    "    const std::optional<tripoint_bub_ms> openp_ = choose_adjacent_highlight( here, _( \"Open where?\" ),\n"
    "            pgettext( \"no door, gate, curtain, etc.\", \"There is nothing that can be opened nearby.\" ),\n"
    "            ACTION_OPEN, false );\n\n"
    "    if( !openp_ ) {\n"
    "        return;\n"
    "    }\n"
    "    const tripoint_bub_ms openp = *openp_;\n",
    "static void open( const std::optional<tripoint_bub_ms> &target = std::nullopt )\n"
    "{\n"
    "    map &here = get_map();\n\n"
    "    avatar &player_character = get_avatar();\n"
    "    std::optional<tripoint_bub_ms> openp_ = target;\n"
    "    if( !openp_ ) {\n"
    "        openp_ = choose_adjacent_highlight( here, _( \"Open where?\" ),\n"
    "                 pgettext( \"no door, gate, curtain, etc.\",\n"
    "                           \"There is nothing that can be opened nearby.\" ),\n"
    "                 ACTION_OPEN, false );\n"
    "    }\n\n"
    "    if( !openp_ ) {\n"
    "        return;\n"
    "    }\n"
    "    const tripoint_bub_ms openp = *openp_;\n",
)

replace_once(
    "src/handle_action.cpp",
    "static void smash()\n"
    "{\n"
    "    const bool allow_floor_bash = debug_mode; // Should later become \"true\"\n"
    "    const std::optional<tripoint_bub_ms> smashp_ = choose_adjacent( _( \"Smash where?\" ),\n"
    "            allow_floor_bash );\n"
    "    if( !smashp_ ) {\n"
    "        return;\n"
    "    }\n"
    "    tripoint_bub_ms smashp = *smashp_;\n",
    "static void smash( const std::optional<tripoint_bub_ms> &target = std::nullopt )\n"
    "{\n"
    "    const bool allow_floor_bash = debug_mode; // Should later become \"true\"\n"
    "    std::optional<tripoint_bub_ms> smashp_ = target;\n"
    "    if( !smashp_ ) {\n"
    "        smashp_ = choose_adjacent( _( \"Smash where?\" ), allow_floor_bash );\n"
    "    }\n"
    "    if( !smashp_ ) {\n"
    "        return;\n"
    "    }\n"
    "    tripoint_bub_ms smashp = *smashp_;\n",
)

replace_once(
    "src/handle_action.cpp",
    "        case ACTION_OPEN:\n"
    "            open();\n"
    "            break;\n",
    "        case ACTION_OPEN:\n"
    "            open( mouse_target );\n"
    "            break;\n",
)

replace_once(
    "src/handle_action.cpp",
    "        case ACTION_SMASH:\n"
    "            if( has_vehicle_control( player_character ) ) {\n"
    "                handbrake( here );\n"
    "            } else {\n"
    "                smash();\n"
    "            }\n"
    "            break;\n",
    "        case ACTION_SMASH:\n"
    "            if( has_vehicle_control( player_character ) ) {\n"
    "                handbrake( here );\n"
    "            } else {\n"
    "                smash( mouse_target );\n"
    "            }\n"
    "            break;\n",
)

replace_once(
    "src/handle_action.cpp",
    "            } else if( act == ACTION_SEC_SELECT ) {\n"
    "                if( !try_get_right_click_action( act, *mouse_target ) ) {\n"
    "                    return false;\n"
    "                }\n"
    "            }\n",
    "            } else if( act == ACTION_SEC_SELECT ) {\n"
    "                const std::optional<point> menu_anchor =\n"
    "                    ctxt.get_coordinates_text( catacurses::stdscr );\n"
    "                if( !menu_anchor ||\n"
    "                    !try_get_right_click_action( act, *mouse_target, *menu_anchor ) ) {\n"
    "                    return false;\n"
    "                }\n"
    "            }\n",
)
