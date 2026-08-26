from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: {label}: expected 1 match, got {count}")
    path.write_text(text.replace(old, new, 1))


cpp = Path("src/veh_interact.cpp")

replace_once(
    cpp,
    '''    item_location last_clicked_source;\n    std::optional<std::chrono::steady_clock::time_point> last_source_click_time;\n''',
    '''    // Double-click is a UI-row gesture, not an item_location equivalence test.\n    // Multiple containers in the same cargo source can otherwise compare as the\n    // same effective location and turn two different row clicks into a double-click.\n    int last_clicked_source_index = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_source_click_time;\n''',
    "strict refuel source double-click identity",
)

replace_once(
    cpp,
    '''    refuel_info->sources.clear();\n\n    Character &player_character = get_player_character();\n''',
    '''    refuel_info->sources.clear();\n    // Rebuilding/sorting the visible source rows invalidates any row-based\n    // double-click candidate.\n    refuel_info->last_clicked_source_index = -1;\n    refuel_info->last_source_click_time.reset();\n\n    Character &player_character = get_player_character();\n''',
    "reset source double-click on rebuild",
)

replace_once(
    cpp,
    '''        std::optional<itype_id> selected_fuel;\n        for( const refuel_info_t::source_t &source : refuel_info->sources ) {\n''',
    '''        std::optional<itype_id> selected_fuel;\n        bool mixed_fuels = false;\n        for( const refuel_info_t::source_t &source : refuel_info->sources ) {\n''',
    "track mixed selected fuels",
)

replace_once(
    cpp,
    '''            if( payload->typeId() != *selected_fuel || simulated_remaining <= 0 ) {\n                continue;\n            }\n''',
    '''            if( payload->typeId() != *selected_fuel ) {\n                mixed_fuels = true;\n                continue;\n            }\n            if( simulated_remaining <= 0 ) {\n                continue;\n            }\n''',
    "detect mixed selected fuels",
)

replace_once(
    cpp,
    '''        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4, c_light_gray,\n                        string_format( _( "Selected: %1$d source(s)   Cost: %2$d refill action(s)" ),\n                                       selected_count, effective_actions ) );\n        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4, c_light_green,\n                        _( "[ Refuel selected ]" ) );\n''',
    '''        const std::string selection_status = mixed_fuels ?\n                _( "Selected containers contain different fuel types and cannot be refueled together." ) :\n                string_format( _( "Selected: %1$d source(s)   Cost: %2$d refill action(s)" ),\n                               selected_count, effective_actions );\n        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4,\n                        mixed_fuels ? c_light_red : c_light_gray, selection_status );\n        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4,\n                        mixed_fuels ? c_dark_gray : c_light_green, _( "[ Refuel selected ]" ) );\n''',
    "mixed-fuel status and disabled fill affordance",
)

replace_once(
    cpp,
    '''            const item_location clicked = refuel_info->sources[index].location;\n            const auto now = std::chrono::steady_clock::now();\n            const bool double_click = !ctrl && !shift && refuel_info->last_clicked_source &&\n                                      refuel_info->last_clicked_source == clicked &&\n                                      refuel_info->last_source_click_time &&\n                                      now - *refuel_info->last_source_click_time <= std::chrono::milliseconds( 500 );\n''',
    '''            const auto now = std::chrono::steady_clock::now();\n            const bool double_click = !ctrl && !shift &&\n                                      refuel_info->last_clicked_source_index == index &&\n                                      refuel_info->last_source_click_time &&\n                                      now - *refuel_info->last_source_click_time <= std::chrono::milliseconds( 500 );\n''',
    "row-specific refuel double-click",
)

replace_once(
    cpp,
    '''            if( double_click ) {\n                refuel_info->last_clicked_source = item_location();\n                refuel_info->last_source_click_time.reset();\n                queue_selected_refill_source( here );\n            } else {\n                refuel_info->last_clicked_source = clicked;\n                refuel_info->last_source_click_time = now;\n            }\n''',
    '''            if( double_click ) {\n                refuel_info->last_clicked_source_index = -1;\n                refuel_info->last_source_click_time.reset();\n                queue_selected_refill_source( here );\n            } else {\n                refuel_info->last_clicked_source_index = index;\n                refuel_info->last_source_click_time = now;\n            }\n''',
    "store row double-click candidate",
)

replace_once(
    cpp,
    '''            msg = _( "Selected sources must contain the same fuel type." );\n''',
    '''            msg = _( "Selected containers contain different fuel types and cannot be refueled together." );\n''',
    "mixed-fuel queue message",
)

replace_once(
    cpp,
    '''        // Escape dismisses transient editor menus before it is allowed to close\n        // a mode or the vehicle editor itself.\n        if( action == "QUIT" && editor_context_open ) {\n''',
    '''        // Refuel is a modal workflow and owns Escape before any transient\n        // editor UI hidden behind it.  Otherwise a stale editor dropdown can\n        // consume Esc and make the fuel window appear impossible to close.\n        if( action == "QUIT" && refuel_info ) {\n            close_refuel_mode();\n            continue;\n        }\n\n        // Escape dismisses transient editor menus before it is allowed to close\n        // a mode or the vehicle editor itself.\n        if( action == "QUIT" && editor_context_open ) {\n''',
    "refuel escape priority",
)

replace_once(
    cpp,
    '''        if( refuel_info ) {\n            using refuel_stage = refuel_info_t::stage_t;\n            if( action == "QUIT" ) {\n                // QUIT/Esc is Cancel for the entire transactional refuel workflow.\n                // The explicit Back button is what returns to the tank-selection stage.\n                close_refuel_mode();\n                continue;\n            }\n\n            if( action == "UP" || action == "DOWN" ||\n''',
    '''        if( refuel_info ) {\n            using refuel_stage = refuel_info_t::stage_t;\n\n            if( action == "UP" || action == "DOWN" ||\n''',
    "remove redundant late refuel escape handling",
)

print("refuel source selection patch applied")
