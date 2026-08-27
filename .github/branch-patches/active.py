from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/veh_interact.h",
    '''        scrollbar install_scrollbar;\n        scrollbar reshape_scrollbar;\n''',
    '''        scrollbar install_scrollbar;\n        scrollbar reshape_scrollbar;\n        scrollbar refuel_tank_scrollbar;\n        scrollbar refuel_source_scrollbar;\n        scrollbar refuel_quick_scrollbar;\n''',
    "refuel scrollbar members",
)

replace_once(
    "src/veh_interact.cpp",
    '''    install_scrollbar.debug_name( "vehicle.install" );\n    reshape_scrollbar.debug_name( "vehicle.reshape" );\n''',
    '''    install_scrollbar.debug_name( "vehicle.install" );\n    reshape_scrollbar.debug_name( "vehicle.reshape" );\n    refuel_tank_scrollbar.debug_name( "vehicle.refuel.tanks" );\n    refuel_source_scrollbar.debug_name( "vehicle.refuel.sources" );\n    refuel_quick_scrollbar.debug_name( "vehicle.refuel.quick" );\n''',
    "refuel scrollbar diagnostics",
)

replace_once(
    "src/veh_interact.cpp",
    '''        if( !refuel_info->tanks.empty() ) {\n            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );\n            refuel_info->tank_scroll.ensure_visible( refuel_info->tank_pos );\n        }\n''',
    '''        if( !refuel_info->tanks.empty() ) {\n            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,\n                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );\n        }\n''',
    "tank redraw selection independence",
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( !refuel_info->sources.empty() ) {\n            refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,\n                                      static_cast<int>( refuel_info->sources.size() ) - 1 );\n            refuel_info->source_scroll.ensure_visible( refuel_info->source_pos );\n        }\n''',
    '''        if( !refuel_info->sources.empty() ) {\n            refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,\n                                      static_cast<int>( refuel_info->sources.size() ) - 1 );\n        }\n''',
    "source redraw selection independence",
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( !refuel_info->quick_fuels.empty() ) {\n            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,\n                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n            refuel_info->quick_fuel_scroll.ensure_visible( refuel_info->quick_fuel_pos );\n        }\n''',
    '''        if( !refuel_info->quick_fuels.empty() ) {\n            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,\n                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n        }\n''',
    "quick redraw selection independence",
)

replace_once(
    "src/veh_interact.cpp",
    '''            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );\n        }\n\n        const bool any_selected = std::any_of( refuel_info->tank_selected.begin(),\n''',
    '''            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );\n        }\n        refuel_tank_scrollbar.offset_x( width - 2 ).offset_y( first_row )\n        .model( refuel_info->tank_scroll ).apply( w_refuel_overlay );\n\n        const bool any_selected = std::any_of( refuel_info->tank_selected.begin(),\n''',
    "tank scrollbar draw",
)
replace_once(
    "src/veh_interact.cpp",
    '''            const nc_color color = selected ? hilite( c_white ) : c_light_gray;\n            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );\n        }\n        if( refuel_info->sources.empty() ) {\n''',
    '''            const nc_color color = selected ? hilite( c_white ) : c_light_gray;\n            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );\n        }\n        refuel_source_scrollbar.offset_x( width - 2 ).offset_y( first_row )\n        .model( refuel_info->source_scroll ).apply( w_refuel_overlay );\n        if( refuel_info->sources.empty() ) {\n''',
    "source scrollbar draw",
)
replace_once(
    "src/veh_interact.cpp",
    '''            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4,\n                            index == refuel_info->quick_fuel_pos ? h_light_cyan : c_light_gray,\n                            string_format( "%s  —  %s available", item::nname( fuel ), amount ) );\n        }\n        if( refuel_info->quick_fuels.empty() ) {\n''',
    '''            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4,\n                            index == refuel_info->quick_fuel_pos ? h_light_cyan : c_light_gray,\n                            string_format( "%s  —  %s available", item::nname( fuel ), amount ) );\n        }\n        refuel_quick_scrollbar.offset_x( width - 2 ).offset_y( first_row )\n        .model( refuel_info->quick_fuel_scroll ).apply( w_refuel_overlay );\n        if( refuel_info->quick_fuels.empty() ) {\n''',
    "quick scrollbar draw",
)

replace_once(
    "src/veh_interact.cpp",
    '''    const int height = getmaxy( w_refuel_overlay );\n    using refuel_stage = refuel_info_t::stage_t;\n\n    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n        const int delta = action == "SCROLL_UP" ? -1 : 1;\n        if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {\n            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,\n                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );\n        } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {\n            refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,\n                                      static_cast<int>( refuel_info->sources.size() ) - 1 );\n        } else if( refuel_info->stage == refuel_stage::quick_fuel && !refuel_info->quick_fuels.empty() ) {\n            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,\n                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n        }\n        return true;\n    }\n''',
    '''    const int height = getmaxy( w_refuel_overlay );\n    using refuel_stage = refuel_info_t::stage_t;\n\n    scrollbar *active_scrollbar = nullptr;\n    ui_scroll_model *active_scroll = nullptr;\n    if( refuel_info->stage == refuel_stage::tank ) {\n        active_scrollbar = &refuel_tank_scrollbar;\n        active_scroll = &refuel_info->tank_scroll;\n    } else if( refuel_info->stage == refuel_stage::source ) {\n        active_scrollbar = &refuel_source_scrollbar;\n        active_scroll = &refuel_info->source_scroll;\n    } else {\n        active_scrollbar = &refuel_quick_scrollbar;\n        active_scroll = &refuel_info->quick_fuel_scroll;\n    }\n    if( active_scrollbar != nullptr && active_scroll != nullptr &&\n        active_scrollbar->handle_input( action, main_context, *active_scroll ) ) {\n        return true;\n    }\n\n    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {\n        active_scroll->scroll_by( action == "SCROLL_UP" ? -1 : 1 );\n        return true;\n    }\n''',
    "refuel scrollbar input and free wheel scrolling",
)

replace_once(
    "src/veh_interact.cpp",
    '''        if( pos->y >= first_row && pos->y < first_row + visible ) {\n            const int slot = refuel_info->tank_scroll.viewport_pos() + pos->y - first_row;\n            if( slot < 0 || slot >= static_cast<int>( refuel_info->tanks.size() ) ) {\n                return true;\n            }\n''',
    '''        if( pos->y >= first_row && pos->y < first_row + visible ) {\n            const std::optional<int> slot_at_row =\n                refuel_info->tank_scroll.index_at_viewport_row( pos->y - first_row );\n            if( !slot_at_row ) {\n                return true;\n            }\n            const int slot = *slot_at_row;\n''',
    "tank helper row mapping",
)
replace_once(
    "src/veh_interact.cpp",
    '''        if( pos->y >= first_row && pos->y < first_row + visible ) {\n            const int index = refuel_info->source_scroll.viewport_pos() + pos->y - first_row;\n            if( index < 0 || index >= static_cast<int>( refuel_info->sources.size() ) ) {\n                return true;\n            }\n''',
    '''        if( pos->y >= first_row && pos->y < first_row + visible ) {\n            const std::optional<int> index_at_row =\n                refuel_info->source_scroll.index_at_viewport_row( pos->y - first_row );\n            if( !index_at_row ) {\n                return true;\n            }\n            const int index = *index_at_row;\n''',
    "source helper row mapping",
)
replace_once(
    "src/veh_interact.cpp",
    '''    if( pos->y >= first_row && pos->y < first_row + visible ) {\n        const int index = refuel_info->quick_fuel_scroll.viewport_pos() + pos->y - first_row;\n        if( index >= 0 && index < static_cast<int>( refuel_info->quick_fuels.size() ) ) {\n            refuel_info->quick_fuel_pos = index;\n        }\n        return true;\n    }\n''',
    '''    if( pos->y >= first_row && pos->y < first_row + visible ) {\n        const std::optional<int> index_at_row =\n            refuel_info->quick_fuel_scroll.index_at_viewport_row( pos->y - first_row );\n        if( index_at_row ) {\n            refuel_info->quick_fuel_pos = *index_at_row;\n        }\n        return true;\n    }\n''',
    "quick helper row mapping",
)

replace_once(
    "src/veh_interact.cpp",
    '''                if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {\n                    refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,\n                                            static_cast<int>( refuel_info->tanks.size() ) - 1 );\n                } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {\n                    refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,\n                                              static_cast<int>( refuel_info->sources.size() ) - 1 );\n                } else if( refuel_info->stage == refuel_stage::quick_fuel &&\n                           !refuel_info->quick_fuels.empty() ) {\n                    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,\n                                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n                }\n''',
    '''                if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {\n                    refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,\n                                            static_cast<int>( refuel_info->tanks.size() ) - 1 );\n                    refuel_info->tank_scroll.ensure_visible( refuel_info->tank_pos );\n                } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {\n                    refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,\n                                              static_cast<int>( refuel_info->sources.size() ) - 1 );\n                    refuel_info->source_scroll.ensure_visible( refuel_info->source_pos );\n                } else if( refuel_info->stage == refuel_stage::quick_fuel &&\n                           !refuel_info->quick_fuels.empty() ) {\n                    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,\n                                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );\n                    refuel_info->quick_fuel_scroll.ensure_visible( refuel_info->quick_fuel_pos );\n                }\n''',
    "refuel keyboard ensure visible",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Move vehicle refuel scrolling onto UI helpers\n", encoding="utf-8"
)
