from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


def replace_between(path: str, start: str, end: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    a = text.find(start)
    if a < 0:
        raise RuntimeError(f"{path}: start marker not found: {start!r}")
    b = text.find(end, a)
    if b < 0:
        raise RuntimeError(f"{path}: end marker not found: {end!r}")
    p.write_text(text[:a] + new + text[b:])


# ---------------------------------------------------------------------------
# Semantic model: distinguish results, carried-item placement, contextual work,
# markers, and coarse player-facing catalog sections without changing the
# underlying construction simulation.
# ---------------------------------------------------------------------------
replace_once(
    "src/construction.h",
    '''enum class construction_ui_intent : int {\n    build,\n    repair,\n    modify,\n    upgrade,\n    terrain_work,\n    decorate,\n    marker,\n    remove\n};\n''',
    '''enum class construction_ui_intent : int {\n    build,\n    place,\n    repair,\n    finish,\n    modify,\n    upgrade,\n    terrain_work,\n    decorate,\n    marker,\n    remove\n};\n\n/** Coarse player-facing section used to keep the Build/Place catalogs small. */\nenum class construction_ui_section : int {\n    structures,\n    furniture,\n    workshop,\n    outdoor,\n    infrastructure,\n    appliances,\n    other\n};\n'''
)
replace_once(
    "src/construction.h",
    '''        construction_action action = construction_action::build;\n        construction_ui_intent ui_intent = construction_ui_intent::build;\n        // Optional key used to merge multiple backend definitions into one contextual UI action.\n''',
    '''        construction_action action = construction_action::build;\n        construction_ui_intent ui_intent = construction_ui_intent::build;\n        construction_ui_section ui_section = construction_ui_section::other;\n        // Optional key used to merge multiple backend definitions into one contextual UI action.\n'''
)
replace_once(
    "src/construction.h",
    '''ret_val<void> start_construction_at( Character &who, const construction &con,\n                                     const tripoint_bub_ms &target );\n''',
    '''ret_val<void> start_construction_at( Character &who, const construction &con,\n                                     const tripoint_bub_ms &target, bool carried_source_only = false );\n'''
)

replace_once(
    "src/construction.cpp",
    '''    const std::string ui_intent = jo.get_string( "ui_intent", "" );\n    if( ui_intent.empty() ) {\n        if( con.action != construction_action::build ) {\n            con.ui_intent = construction_ui_intent::remove;\n        } else if( con.category == construction_category_REPAIR ) {\n            con.ui_intent = construction_ui_intent::repair;\n        } else {\n            con.ui_intent = construction_ui_intent::build;\n        }\n    } else if( ui_intent == "build" ) {\n        con.ui_intent = construction_ui_intent::build;\n    } else if( ui_intent == "repair" ) {\n        con.ui_intent = construction_ui_intent::repair;\n    } else if( ui_intent == "modify" ) {\n        con.ui_intent = construction_ui_intent::modify;\n    } else if( ui_intent == "upgrade" ) {\n        con.ui_intent = construction_ui_intent::upgrade;\n    } else if( ui_intent == "terrain_work" ) {\n        con.ui_intent = construction_ui_intent::terrain_work;\n    } else if( ui_intent == "decorate" ) {\n        con.ui_intent = construction_ui_intent::decorate;\n    } else if( ui_intent == "marker" ) {\n        con.ui_intent = construction_ui_intent::marker;\n    } else if( ui_intent == "remove" ) {\n        con.ui_intent = construction_ui_intent::remove;\n    } else {\n        jo.throw_error_at( "ui_intent",\n                           string_format( "Invalid construction ui_intent %s", ui_intent ) );\n    }\n''',
    '''    const std::string ui_intent = jo.get_string( "ui_intent", "" );\n    if( ui_intent.empty() ) {\n        if( con.action != construction_action::build ) {\n            con.ui_intent = construction_ui_intent::remove;\n        } else if( con.category == construction_category_REPAIR ) {\n            con.ui_intent = construction_ui_intent::repair;\n        } else if( con.category.str() == "APPLIANCE" ) {\n            con.ui_intent = construction_ui_intent::place;\n        } else if( con.category.str() == "DECORATE" ) {\n            con.ui_intent = construction_ui_intent::decorate;\n        } else {\n            con.ui_intent = construction_ui_intent::build;\n        }\n    } else if( ui_intent == "build" ) {\n        con.ui_intent = construction_ui_intent::build;\n    } else if( ui_intent == "place" ) {\n        con.ui_intent = construction_ui_intent::place;\n    } else if( ui_intent == "repair" ) {\n        con.ui_intent = construction_ui_intent::repair;\n    } else if( ui_intent == "finish" ) {\n        con.ui_intent = construction_ui_intent::finish;\n    } else if( ui_intent == "modify" ) {\n        con.ui_intent = construction_ui_intent::modify;\n    } else if( ui_intent == "upgrade" ) {\n        con.ui_intent = construction_ui_intent::upgrade;\n    } else if( ui_intent == "terrain_work" ) {\n        con.ui_intent = construction_ui_intent::terrain_work;\n    } else if( ui_intent == "decorate" ) {\n        con.ui_intent = construction_ui_intent::decorate;\n    } else if( ui_intent == "marker" ) {\n        con.ui_intent = construction_ui_intent::marker;\n    } else if( ui_intent == "remove" ) {\n        con.ui_intent = construction_ui_intent::remove;\n    } else {\n        jo.throw_error_at( "ui_intent",\n                           string_format( "Invalid construction ui_intent %s", ui_intent ) );\n    }\n'''
)
replace_once(
    "src/construction.cpp",
    '''    con.ui_action = jo.get_string( "ui_action", "" );\n    jo.read( "ui_name", con.ui_name );\n''',
    '''    const std::string ui_section = jo.get_string( "ui_section", "" );\n    if( ui_section == "structures" ) {\n        con.ui_section = construction_ui_section::structures;\n    } else if( ui_section == "furniture" ) {\n        con.ui_section = construction_ui_section::furniture;\n    } else if( ui_section == "workshop" ) {\n        con.ui_section = construction_ui_section::workshop;\n    } else if( ui_section == "outdoor" ) {\n        con.ui_section = construction_ui_section::outdoor;\n    } else if( ui_section == "infrastructure" ) {\n        con.ui_section = construction_ui_section::infrastructure;\n    } else if( ui_section == "appliances" ) {\n        con.ui_section = construction_ui_section::appliances;\n    } else if( ui_section == "other" ) {\n        con.ui_section = construction_ui_section::other;\n    } else if( ui_section.empty() ) {\n        if( con.category.str() == "APPLIANCE" ) {\n            con.ui_section = construction_ui_section::appliances;\n        } else if( con.category.str() == "FURN" ) {\n            con.ui_section = construction_ui_section::furniture;\n        } else if( con.category.str() == "TOOL" ) {\n            con.ui_section = construction_ui_section::workshop;\n        }\n    } else {\n        jo.throw_error_at( "ui_section",\n                           string_format( "Invalid construction ui_section %s", ui_section ) );\n    }\n\n    con.ui_action = jo.get_string( "ui_action", "" );\n    jo.read( "ui_name", con.ui_name );\n'''
)
replace_once(
    "src/construction.cpp",
    '''ret_val<void> start_construction_at( Character &who, const construction &con,\n                                     const tripoint_bub_ms &target )\n{\n''',
    '''ret_val<void> start_construction_at( Character &who, const construction &con,\n                                     const tripoint_bub_ms &target, const bool carried_source_only )\n{\n'''
)
replace_once(
    "src/construction.cpp",
    '''    if( !player_can_build( who, who.crafting_inventory(), con, true ) ) {\n        return ret_val<void>::make_failure( _( "You no longer meet the construction requirements." ) );\n    }\n''',
    '''    const read_only_visitable &available_inventory = carried_source_only ?\n            static_cast<const read_only_visitable &>( who ) : who.crafting_inventory();\n    if( !free_test_mode && !player_can_build( who, available_inventory, con, true ) ) {\n        return ret_val<void>::make_failure( carried_source_only ?\n                _( "The item to place is no longer in your carried inventory, or its installation requirements are no longer met." ) :\n                _( "You no longer meet the construction requirements." ) );\n    }\n'''
)

# ---------------------------------------------------------------------------
# Resolver: Build, Place and Markers are separate selection domains.  Contextual
# actions never leak back into the result catalogs.
# ---------------------------------------------------------------------------
replace_once(
    "src/construction_target.h",
    '''enum class construction_operation : int {\n    build,\n    remove\n};\n''',
    '''enum class construction_operation : int {\n    build,\n    place,\n    markers,\n    remove\n};\n'''
)
replace_once(
    "src/construction_target.h",
    '''construction_target_resolution resolve_remove_target(\n    Character &who, const read_only_visitable &inventory,\n    const tripoint_bub_ms &target );\n''',
    '''construction_target_resolution resolve_place_target(\n    Character &who, const read_only_visitable &inventory,\n    const construction_group_str_id &group, const tripoint_bub_ms &target );\nconstruction_target_resolution resolve_marker_target(\n    Character &who, const read_only_visitable &inventory,\n    const construction_group_str_id &group, const tripoint_bub_ms &target );\nconstruction_target_resolution resolve_remove_target(\n    Character &who, const read_only_visitable &inventory,\n    const tripoint_bub_ms &target );\n'''
)
replace_once(
    "src/construction_target.h",
    '''bool construction_is_catalog_action( const construction &con );\nbool construction_is_remove_action( const construction &con );\n''',
    '''bool construction_is_catalog_action( const construction &con );\nbool construction_is_place_action( const construction &con );\nbool construction_is_marker_action( const construction &con );\nbool construction_has_place_source( const construction &con, const read_only_visitable &carried );\nbool construction_is_remove_action( const construction &con );\n'''
)
replace_once(
    "src/construction_target.cpp",
    '''bool construction_is_catalog_action( const construction &con )\n{\n    return construction_ui_intent_for( con ) == construction_ui_intent::build;\n}\n''',
    '''bool construction_is_catalog_action( const construction &con )\n{\n    return construction_ui_intent_for( con ) == construction_ui_intent::build;\n}\n\nbool construction_is_place_action( const construction &con )\n{\n    return construction_ui_intent_for( con ) == construction_ui_intent::place;\n}\n\nbool construction_is_marker_action( const construction &con )\n{\n    return construction_ui_intent_for( con ) == construction_ui_intent::marker;\n}\n\nbool construction_has_place_source( const construction &con, const read_only_visitable &carried )\n{\n    bool has_component_group = false;\n    for( const std::vector<item_comp> &alternatives : con.requirements->get_components() ) {\n        has_component_group = true;\n        if( std::none_of( alternatives.begin(), alternatives.end(),\n        [&carried]( const item_comp &component ) {\n            return component.has( carried, is_crafting_component, 1, craft_flags::none );\n        } ) ) {\n            return false;\n        }\n    }\n    return has_component_group;\n}\n'''
)
replace_between(
    "src/construction_target.cpp",
    "construction_target_resolution resolve_construction_target(\n",
    "construction_target_resolution resolve_remove_target(\n",
    '''construction_target_resolution resolve_construction_target(\n    Character &who, const read_only_visitable &inventory,\n    const construction_group_str_id &group, const tripoint_bub_ms &target )\n{\n    construction_target_resolution result;\n    if( group.is_null() ) {\n        result.reason = _( "Select a construction first." );\n        return result;\n    }\n    if( const std::optional<construction_target_resolution> rejected =\n            common_target_rejection( who, target, true ) ) {\n        return *rejected;\n    }\n\n    const std::vector<construction *> grouped = constructions_by_group( group );\n    std::vector<const construction *> candidates;\n    for( const construction *candidate : grouped ) {\n        if( candidate != nullptr && construction_is_catalog_action( *candidate ) ) {\n            candidates.push_back( candidate );\n        }\n    }\n    return resolve_candidates( who, inventory, candidates, target,\n                               _( "Ready to build." ),\n                               _( "The selected construction is not compatible with this tile." ) );\n}\n\nconstruction_target_resolution resolve_place_target(\n    Character &who, const read_only_visitable &inventory,\n    const construction_group_str_id &group, const tripoint_bub_ms &target )\n{\n    construction_target_resolution result;\n    if( group.is_null() ) {\n        result.reason = _( "Select an item to place first." );\n        return result;\n    }\n    if( const std::optional<construction_target_resolution> rejected =\n            common_target_rejection( who, target, true ) ) {\n        return *rejected;\n    }\n\n    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );\n    const std::vector<construction *> grouped = constructions_by_group( group );\n    std::vector<const construction *> candidates;\n    for( const construction *candidate : grouped ) {\n        if( candidate != nullptr && construction_is_place_action( *candidate ) &&\n            ( free_test_mode || construction_has_place_source( *candidate, who ) ) ) {\n            candidates.push_back( candidate );\n        }\n    }\n    return resolve_candidates( who, inventory, candidates, target,\n                               _( "Ready to place." ),\n                               _( "That carried item cannot be placed on this tile." ) );\n}\n\nconstruction_target_resolution resolve_marker_target(\n    Character &who, const read_only_visitable &inventory,\n    const construction_group_str_id &group, const tripoint_bub_ms &target )\n{\n    construction_target_resolution result;\n    if( group.is_null() ) {\n        result.reason = _( "Select a marker first." );\n        return result;\n    }\n    if( const std::optional<construction_target_resolution> rejected =\n            common_target_rejection( who, target, true ) ) {\n        return *rejected;\n    }\n\n    const std::vector<construction *> grouped = constructions_by_group( group );\n    std::vector<const construction *> candidates;\n    for( const construction *candidate : grouped ) {\n        if( candidate != nullptr && construction_is_marker_action( *candidate ) ) {\n            candidates.push_back( candidate );\n        }\n    }\n    return resolve_candidates( who, inventory, candidates, target,\n                               _( "Ready to mark." ),\n                               _( "That marker cannot be used on this tile." ) );\n}\n\n'''
)
replace_once(
    "src/construction_target.cpp",
    '''    const std::array<construction_ui_intent, 6> contextual_intents = {\n        construction_ui_intent::repair,\n        construction_ui_intent::modify,\n        construction_ui_intent::upgrade,\n        construction_ui_intent::terrain_work,\n        construction_ui_intent::decorate,\n        construction_ui_intent::marker\n    };\n''',
    '''    const std::array<construction_ui_intent, 6> contextual_intents = {\n        construction_ui_intent::repair,\n        construction_ui_intent::finish,\n        construction_ui_intent::modify,\n        construction_ui_intent::upgrade,\n        construction_ui_intent::terrain_work,\n        construction_ui_intent::decorate\n    };\n'''
)
replace_once(
    "src/construction_target.cpp",
    '''                case construction_ui_intent::modify:\n                    ready_reason = _( "Ready to modify." );\n                    break;\n''',
    '''                case construction_ui_intent::finish:\n                    ready_reason = _( "Ready to finish." );\n                    break;\n                case construction_ui_intent::modify:\n                    ready_reason = _( "Ready to modify." );\n                    break;\n'''
)
replace_once(
    "src/construction_target.cpp",
    '''                case construction_ui_intent::build:\n                case construction_ui_intent::remove:\n                    break;\n''',
    '''                case construction_ui_intent::build:\n                case construction_ui_intent::place:\n                case construction_ui_intent::marker:\n                case construction_ui_intent::remove:\n                    break;\n'''
)

# ---------------------------------------------------------------------------
# Workspace helpers and state.
# ---------------------------------------------------------------------------
replace_once(
    "src/construction_ui.cpp",
    '''        case construction_ui_intent::repair:\n            return _( "Repair" );\n        case construction_ui_intent::modify:\n''',
    '''        case construction_ui_intent::place:\n            return _( "Place" );\n        case construction_ui_intent::repair:\n            return _( "Repair" );\n        case construction_ui_intent::finish:\n            return _( "Finish" );\n        case construction_ui_intent::modify:\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        case construction_ui_intent::build:\n            return _( "Build" );\n''',
    '''        case construction_ui_intent::build:\n            return _( "Build" );\n'''
)
# Insert section helpers after contextual action id.
replace_once(
    "src/construction_ui.cpp",
    '''static std::string contextual_action_id( const construction_context_action &action )\n{\n    return string_format( "CONTEXT_%d_%s", static_cast<int>( action.intent ), action.key );\n}\n\nclass construction_workspace\n''',
    '''static std::string contextual_action_id( const construction_context_action &action )\n{\n    return string_format( "CONTEXT_%d_%s", static_cast<int>( action.intent ), action.key );\n}\n\nstatic std::string catalog_section_label( const construction_ui_section section )\n{\n    switch( section ) {\n        case construction_ui_section::structures:\n            return _( "Structures" );\n        case construction_ui_section::furniture:\n            return _( "Furniture" );\n        case construction_ui_section::workshop:\n            return _( "Workshop & utilities" );\n        case construction_ui_section::outdoor:\n            return _( "Outdoor" );\n        case construction_ui_section::infrastructure:\n            return _( "Infrastructure" );\n        case construction_ui_section::appliances:\n            return _( "Appliances" );\n        case construction_ui_section::other:\n            return _( "Other" );\n    }\n    return _( "Other" );\n}\n\nstatic std::string catalog_section_id( const construction_ui_section section )\n{\n    return string_format( "SECTION_%d", static_cast<int>( section ) );\n}\n\nstatic std::optional<construction_ui_section> catalog_section_from_id( const std::string &id )\n{\n    for( const construction_ui_section section : {\n             construction_ui_section::structures, construction_ui_section::furniture,\n             construction_ui_section::workshop, construction_ui_section::outdoor,\n             construction_ui_section::infrastructure, construction_ui_section::appliances,\n             construction_ui_section::other\n         } ) {\n        if( catalog_section_id( section ) == id ) {\n            return section;\n        }\n    }\n    return std::nullopt;\n}\n\nclass construction_workspace\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        void open_context_menu( const point &anchor, const tripoint_bub_ms &target );\n        bool execute_context_action( const std::string &id );\n''',
    '''        void open_context_menu( const point &anchor, const tripoint_bub_ms &target );\n        void open_context_intent_menu( const point &anchor, const tripoint_bub_ms &target,\n                                       construction_ui_intent intent );\n        bool execute_context_action( const std::string &id );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        const construction *catalog_preview_construction(\n            const construction_group_str_id &group ) const;\n        std::string category_label() const;\n''',
    '''        const construction *catalog_preview_construction(\n            const construction_group_str_id &group ) const;\n        bool palette_accepts( const construction &con ) const;\n        const read_only_visitable &active_inventory() const;\n        construction_target_resolution resolve_active_target( const tripoint_bub_ms &target ) const;\n        std::string category_label() const;\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        construction_operation operation = construction_operation::build;\n        construction_category_id category = construction_category_ALL;\n        construction_group_str_id selected_group = construction_group_str_id::NULL_ID();\n''',
    '''        construction_operation operation = construction_operation::build;\n        std::optional<construction_ui_section> section_filter;\n        construction_group_str_id selected_group = construction_group_str_id::NULL_ID();\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    search = uistate.construction_filter;\n    if( uistate.construction_tab.is_valid() &&\n        uistate.construction_tab != construction_category_FILTER ) {\n        category = uistate.construction_tab;\n    }\n''',
    '''    search = uistate.construction_filter;\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''struct construction_build_order {\n    construction_id id = construction_id( -1 );\n    tripoint_bub_ms target;\n    bool resume = false;\n};\n''',
    '''struct construction_build_order {\n    construction_id id = construction_id( -1 );\n    tripoint_bub_ms target;\n    bool resume = false;\n    bool carried_source_only = false;\n};\n'''
)

# Replace catalog-preview helpers with operation-aware versions.
replace_between(
    "src/construction_ui.cpp",
    "const construction *construction_workspace::catalog_preview_construction(\n",
    "void construction_workspace::rebuild_palette()\n",
    '''bool construction_workspace::palette_accepts( const construction &con ) const\n{\n    if( !con.on_display ) {\n        return false;\n    }\n    switch( operation ) {\n        case construction_operation::build:\n            return construction_is_catalog_action( con );\n        case construction_operation::place:\n            return construction_is_place_action( con );\n        case construction_operation::markers:\n            return construction_is_marker_action( con );\n        case construction_operation::remove:\n            return false;\n    }\n    return false;\n}\n\nconst read_only_visitable &construction_workspace::active_inventory() const\n{\n    // Place is selected from carried items, but tool/skill readiness can still\n    // use the normal crafting reach.  The resolver separately enforces that a\n    // concrete source item is carried.\n    return you.crafting_inventory();\n}\n\nconstruction_target_resolution construction_workspace::resolve_active_target(\n    const tripoint_bub_ms &target ) const\n{\n    switch( operation ) {\n        case construction_operation::build:\n            return resolve_construction_target( you, active_inventory(), selected_group, target );\n        case construction_operation::place:\n            return resolve_place_target( you, active_inventory(), selected_group, target );\n        case construction_operation::markers:\n            return resolve_marker_target( you, active_inventory(), selected_group, target );\n        case construction_operation::remove:\n            return resolve_remove_target( you, active_inventory(), target );\n    }\n    return construction_target_resolution();\n}\n\nconst construction *construction_workspace::catalog_preview_construction(\n    const construction_group_str_id &group ) const\n{\n    const std::vector<construction *> variants = constructions_by_group( group );\n    const auto first = std::find_if( variants.begin(), variants.end(),\n    [this]( const construction * candidate ) {\n        return candidate != nullptr && palette_accepts( *candidate );\n    } );\n    if( first == variants.end() ) {\n        return nullptr;\n    }\n\n    if( operation != construction_operation::build || ( *first )->post_terrain.empty() ) {\n        return *first;\n    }\n\n    // Follow actual catalog stages to the completed result, but never cross\n    // into contextual or placement definitions that happen to share a group.\n    const construction *result = *first;\n    std::set<construction_id> visited;\n    while( visited.insert( result->id ).second ) {\n        const auto next = std::find_if( variants.begin(), variants.end(),\n        [this, result, &visited]( const construction * candidate ) {\n            return candidate != nullptr && palette_accepts( *candidate ) &&\n                   visited.count( candidate->id ) == 0 &&\n                   candidate->pre_terrain.count( result->post_terrain ) != 0;\n        } );\n        if( next == variants.end() ) {\n            break;\n        }\n        result = *next;\n    }\n    return result;\n}\n\nstd::string construction_workspace::category_label() const\n{\n    return section_filter ? catalog_section_label( *section_filter ) : _( "All" );\n}\n\n'''
)

replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::rebuild_palette()\n",
    "void construction_workspace::refresh_active_target()\n",
    '''void construction_workspace::rebuild_palette()\n{\n    const construction_group_str_id previous = selected_group;\n    visible_groups.clear();\n    if( operation == construction_operation::remove ) {\n        palette.set_entries( {}, false );\n        palette.set_row_accessories( {} );\n        return;\n    }\n\n    if( section_filter ) {\n        const bool section_has_entries = std::any_of( get_constructions().begin(),\n        get_constructions().end(), [this]( const construction &con ) {\n            return palette_accepts( con ) && con.ui_section == *section_filter;\n        } );\n        if( !section_has_entries ) {\n            section_filter.reset();\n        }\n    }\n\n    std::set<construction_group_str_id> seen;\n    std::map<construction_group_str_id, bool> currently_available;\n    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );\n    for( const construction &con : get_constructions() ) {\n        if( !palette_accepts( con ) || !seen.insert( con.group ).second ) {\n            continue;\n        }\n\n        const std::vector<construction *> variants = constructions_by_group( con.group );\n        bool has_carried_source = operation != construction_operation::place || free_test_mode;\n        bool available = free_test_mode;\n        for( const construction *candidate : variants ) {\n            if( candidate == nullptr || !palette_accepts( *candidate ) ) {\n                continue;\n            }\n            if( operation == construction_operation::place &&\n                construction_has_place_source( *candidate, you ) ) {\n                has_carried_source = true;\n            }\n            if( player_can_build( you, active_inventory(), *candidate, true ) ) {\n                available = true;\n            }\n        }\n        if( operation == construction_operation::place && !has_carried_source ) {\n            continue;\n        }\n        currently_available[con.group] = available;\n        if( operation == construction_operation::build && !show_unavailable && !available ) {\n            continue;\n        }\n\n        const construction *representative = catalog_preview_construction( con.group );\n        if( representative == nullptr ) {\n            continue;\n        }\n        const bool section_matches = !section_filter ||\n                                     representative->ui_section == *section_filter;\n        const std::string result_name = representative->post_terrain.empty() ?\n                                        representative->group->name() :\n                                        construction_result_name( *representative );\n        const std::string section_name = catalog_section_label( representative->ui_section );\n        const bool search_matches = search.empty() || lcmatch( con.group->name(), search ) ||\n                                    lcmatch( result_name, search ) || lcmatch( section_name, search );\n        if( section_matches && search_matches ) {\n            visible_groups.push_back( con.group );\n        }\n    }\n\n    std::sort( visible_groups.begin(), visible_groups.end(), [this](\n    const construction_group_str_id &lhs, const construction_group_str_id &rhs ) {\n        const construction *left = catalog_preview_construction( lhs );\n        const construction *right = catalog_preview_construction( rhs );\n        if( left != nullptr && right != nullptr && left->ui_section != right->ui_section ) {\n            return static_cast<int>( left->ui_section ) < static_cast<int>( right->ui_section );\n        }\n        const std::string left_name = left != nullptr && !left->post_terrain.empty() ?\n                                      construction_result_name( *left ) : lhs->name();\n        const std::string right_name = right != nullptr && !right->post_terrain.empty() ?\n                                       construction_result_name( *right ) : rhs->name();\n        return left_name < right_name;\n    } );\n\n    std::vector<ui_action_entry> entries;\n    std::vector<std::vector<ui_row_accessory>> row_accessories;\n    entries.reserve( visible_groups.size() );\n    row_accessories.reserve( visible_groups.size() );\n    for( const construction_group_str_id &group : visible_groups ) {\n        const construction *representative = catalog_preview_construction( group );\n        std::string label = group->name();\n        if( representative != nullptr ) {\n            if( operation == construction_operation::markers && !representative->ui_name.empty() ) {\n                label = representative->ui_name.translated();\n            } else if( !representative->post_terrain.empty() ) {\n                label = construction_result_name( *representative );\n            }\n        }\n        ui_action_entry entry( label, group.str(), true, group == selected_group );\n        if( currently_available[group] ) {\n            entry.tone = ui_action_tone::positive;\n        }\n        entries.push_back( std::move( entry ) );\n        row_accessories.push_back( { ui_row_accessory{\n                ui_action_entry( "    ", "PREVIEW_" + group.str() ),\n                ui_row_accessory_side::leading, false, 4 } } );\n    }\n    palette.set_entries( std::move( entries ), false );\n    palette.set_row_accessories( std::move( row_accessories ) );\n    const auto selected = std::find( visible_groups.begin(), visible_groups.end(), selected_group );\n    if( selected != visible_groups.end() ) {\n        palette.select_only( static_cast<int>( selected - visible_groups.begin() ) );\n    } else {\n        const auto remembered = operation == construction_operation::build ?\n                                std::find( visible_groups.begin(), visible_groups.end(),\n                                           uistate.last_construction ) : visible_groups.end();\n        if( !selection_cleared_by_user && remembered != visible_groups.end() ) {\n            selected_group = *remembered;\n            palette.select_only( static_cast<int>( remembered - visible_groups.begin() ) );\n        } else {\n            selected_group = construction_group_str_id::NULL_ID();\n            palette.clear_selection();\n        }\n    }\n    if( selected_group != previous ) {\n        refresh_active_target();\n    }\n}\n\n'''
)

replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::refresh_active_target()\n",
    "void construction_workspace::clear_selection()\n",
    '''void construction_workspace::refresh_active_target()\n{\n    const std::optional<tripoint_bub_ms> target = displayed_target();\n    context_actions.clear();\n    if( target && operation == construction_operation::build ) {\n        context_actions = resolve_context_construction_actions(\n                              you, you.crafting_inventory(), *target );\n    }\n\n    if( !target || ( operation != construction_operation::remove && selected_group.is_null() ) ) {\n        resolution = construction_target_resolution();\n    } else {\n        resolution = resolve_active_target( *target );\n    }\n\n    adjacent_resolutions.clear();\n    if( operation != construction_operation::remove && !selected_group.is_null() ) {\n        for( int x = -1; x <= 1; ++x ) {\n            for( int y = -1; y <= 1; ++y ) {\n                if( x == 0 && y == 0 ) {\n                    continue;\n                }\n                const tripoint_bub_ms candidate = you.pos_bub() + tripoint_rel_ms( x, y, 0 );\n                adjacent_resolutions.emplace_back( candidate, resolve_active_target( candidate ) );\n            }\n        }\n    }\n    rebuild_inspector();\n}\n\n'''
)

# Layout: every non-destructive catalog mode owns the palette.
replace_once(
    "src/construction_ui.cpp",
    '''    palette_visible = operation == construction_operation::build &&\n                      ( !compact || focus == workspace_focus::palette );\n''',
    '''    palette_visible = operation != construction_operation::remove &&\n                      ( !compact || focus == workspace_focus::palette );\n'''
)

# Header with explicit Place and Markers modes.
replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::draw_header()\n",
    "void construction_workspace::draw_palette()\n",
    '''void construction_workspace::draw_header()\n{\n    werase( header );\n    draw_border( header, c_light_gray );\n    trim_and_print( header, point( 2, 1 ), 14, c_light_green, _( "Construction" ) );\n\n    std::vector<ui_action_strip_item> actions = {\n        { ui_action_entry( _( "Build" ), "MODE_BUILD", true,\n                           operation == construction_operation::build ), 0, ui_action_alignment::left },\n        { ui_action_entry( _( "Place" ), "MODE_PLACE", true,\n                           operation == construction_operation::place ), 0, ui_action_alignment::left },\n        { ui_action_entry( _( "Remove" ), "MODE_REMOVE", true,\n                           operation == construction_operation::remove ), 0, ui_action_alignment::left },\n        { ui_action_entry( _( "Markers" ), "MODE_MARKERS", true,\n                           operation == construction_operation::markers ), 0, ui_action_alignment::left },\n        { ui_action_entry( _( "Plan" ), "MODE_PLAN", false, false,\n                           _( "Persistent construction plans are not implemented in this UI pass." ) ), 0,\n          ui_action_alignment::left },\n        { ui_action_entry( _( "Plans" ), "MODE_PLANS", false, false,\n                           _( "Plan management requires the construction-plan backend." ) ), 0,\n          ui_action_alignment::left }\n    };\n    if( compact && operation != construction_operation::remove ) {\n        actions.push_back( { ui_action_entry( _( "Palette" ), "FOCUS_PALETTE", true,\n                                              focus == workspace_focus::palette ), 1,\n                             ui_action_alignment::left } );\n        actions.push_back( { ui_action_entry( _( "Map" ), "FOCUS_VIEWPORT", true,\n                                              focus == workspace_focus::viewport ), 1,\n                             ui_action_alignment::left } );\n        actions.push_back( { ui_action_entry( _( "Inspector" ), "FOCUS_INSPECTOR", true,\n                                              focus == workspace_focus::inspector ), 1,\n                             ui_action_alignment::left } );\n    }\n    actions.push_back( { ui_action_entry( _( "Back" ), "BACK" ), 2,\n                         ui_action_alignment::right } );\n    header_actions.configure( header, point( 17, 1 ), std::move( actions ),\n                              std::max( 1, getmaxx( header ) - 19 ), 1 );\n    header_actions.draw( header );\n    const int viewport_left = palette_width;\n    const int viewport_width = TERMX - palette_width - inspector_width;\n    if( viewport_width > 12 ) {\n        trim_and_print( header, point( viewport_left + 2, 2 ), viewport_width - 4,\n                        focus == workspace_focus::viewport ? c_light_cyan : c_dark_gray,\n                        _( " World viewport " ) );\n    }\n    wnoutrefresh( header );\n}\n\n'''
)

# Replace palette drawing so Place only presents carried deployables and Build
# uses semantic sections rather than the backend construction categories.
replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::draw_palette()\n",
    "void construction_workspace::draw_inspector()\n",
    '''void construction_workspace::draw_palette()\n{\n    if( !palette_window ) {\n        palette.invalidate_geometry();\n#if defined(TILES)\n        clear_ui_tile_previews();\n#endif\n        return;\n    }\n    werase( palette_window );\n    draw_border( palette_window, focus == workspace_focus::palette ? c_light_cyan : c_light_gray );\n\n    std::string title = _( " Build catalog " );\n    if( operation == construction_operation::place ) {\n        title = _( " Place from inventory " );\n    } else if( operation == construction_operation::markers ) {\n        title = _( " Markers " );\n    } else if( operation == construction_operation::remove ) {\n        title = _( " Remove tool " );\n    }\n    trim_and_print( palette_window, point( 2, 0 ), std::max( 1, palette_width - 4 ),\n                    c_light_green, title );\n\n    if( operation == construction_operation::remove ) {\n        search_field.clear();\n        palette_actions.clear();\n        palette.invalidate_geometry();\n#if defined(TILES)\n        clear_ui_tile_previews();\n#endif\n        trim_and_print( palette_window, point( 2, 2 ), palette_width - 4, c_light_green,\n                        _( "Select a tile on the map." ) );\n        fold_and_print( palette_window, point( 2, 4 ), palette_width - 4, c_light_gray,\n                        _( "Remove resolves the correct dismantle or removal action from the selected terrain or furniture." ) );\n        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {\n            const std::string existing = here.has_furn( *target ) ? here.furn( *target )->name() :\n                                         here.ter( *target )->name();\n            trim_and_print( palette_window, point( 2, 8 ), palette_width - 4, c_light_cyan,\n                            string_format( _( "Target: %s" ), existing ) );\n        }\n        wnoutrefresh( palette_window );\n        return;\n    }\n\n    const std::string hint = operation == construction_operation::place ?\n                             _( "carried item" ) : operation == construction_operation::markers ?\n                             _( "marker" ) : _( "name or result" );\n    search_field.configure( palette_window, point( 2, 2 ), palette_width - 4,\n                            _( "Search: " ), search, hint, true );\n    search_field.draw( palette_window );\n\n    std::vector<ui_action_entry> palette_entries = {\n        ui_action_entry( string_format( _( "Section: %s" ), category_label() ),\n                         "CATEGORY", true, category_menu.is_open(), std::string(), std::nullopt, true )\n    };\n    if( operation == construction_operation::build ) {\n        palette_entries.emplace_back( _( "Show unavailable" ), "SHOW_UNAVAILABLE", true, false,\n                                      std::string(), show_unavailable );\n    }\n    palette_actions.configure( palette_window, point( 2, 4 ), std::move( palette_entries ),\n                               palette_width - 4, 2 );\n    palette_actions.draw( palette_window );\n\n    const int list_y = 7;\n    palette.draw( palette_window, point( 2, list_y ), palette_width - 4,\n                  std::max( 1, getmaxy( palette_window ) - list_y - 2 ),\n                  ui_selection_list_style(), 2 );\n    if( visible_groups.empty() ) {\n        const std::string empty = operation == construction_operation::place &&\n                                  !get_option<bool>( "UI_TEST_MODE" ) ?\n                                  _( "No carried items can be placed." ) : _( "No entries match." );\n        trim_and_print( palette_window, point( 2, list_y ), palette_width - 4, c_dark_gray, empty );\n    }\n\n#if defined(TILES)\n    std::vector<ui_tile_preview> previews;\n#endif\n    for( int index = 0; index < static_cast<int>( visible_groups.size() ); ++index ) {\n        const std::optional<point> row = palette.entry_position( index );\n        if( !row ) {\n            continue;\n        }\n        const construction *representative = catalog_preview_construction( visible_groups[index] );\n        if( representative == nullptr ) {\n            continue;\n        }\n        const bool selected = visible_groups[index] == selected_group;\n        if( representative->post_terrain.empty() ) {\n            mvwputch( palette_window, *row + point( 1, 0 ),\n                      selected ? h_light_cyan : c_light_cyan, '*' );\n        } else {\n#if defined(TILES)\n            const ui_tile_preview_type type = representative->post_is_furniture ?\n                                              ui_tile_preview_type::furniture : ui_tile_preview_type::terrain;\n            if( has_ui_tile_preview( type, representative->post_terrain ) ) {\n                previews.push_back( ui_tile_preview{ *row, point( 4, 2 ), type,\n                                                     representative->post_terrain, std::string(), 0 } );\n            } else {\n                trim_and_print( palette_window, *row, 4, c_light_red, _( "[?]" ) );\n            }\n#else\n            if( representative->post_is_furniture ) {\n                const furn_str_id result( representative->post_terrain );\n                mvwputch( palette_window, *row + point( 1, 0 ),\n                          selected ? hilite( result->color() ) : result->color(), result->symbol() );\n            } else {\n                const ter_str_id result( representative->post_terrain );\n                mvwputch( palette_window, *row + point( 1, 0 ),\n                          selected ? hilite( result->color() ) : result->color(), result->symbol() );\n            }\n#endif\n        }\n\n        std::string detail = catalog_section_label( representative->ui_section );\n        detail += "  •  " + to_string( time_duration::from_moves( representative->adjusted_time() ) );\n        if( !representative->required_skills.empty() ) {\n            const auto skill = std::max_element( representative->required_skills.begin(),\n            representative->required_skills.end(), []( const auto & lhs, const auto & rhs ) {\n                return lhs.second < rhs.second;\n            } );\n            detail += string_format( "  •  %s %d", skill->first->name(), skill->second );\n        }\n        trim_and_print( palette_window, *row + point( 5, 1 ),\n                        std::max( 1, palette_width - row->x - 8 ),\n                        selected ? h_dark_gray : c_dark_gray, detail );\n    }\n#if defined(TILES)\n    set_ui_tile_previews( palette_window, previews );\n#endif\n    wnoutrefresh( palette_window );\n}\n\n'''
)

# Inspector: safe empty states for Place/Markers, operation-specific labels, and
# carried-inventory requirement display for placement.
replace_once(
    "src/construction_ui.cpp",
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();\n    add( colorize( operation == construction_operation::remove ? _( "Remove" ) :\n                   inspect_mode ? _( "Inspect & work" ) : selected_group->name(), c_light_green ) );\n''',
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();\n    const bool selection_missing = operation != construction_operation::remove && selected_group.is_null();\n    std::string heading = _( "Remove" );\n    if( operation == construction_operation::build ) {\n        heading = inspect_mode ? _( "Inspect & work" ) : selected_group->name();\n    } else if( operation == construction_operation::place ) {\n        heading = selection_missing ? _( "Place from inventory" ) : selected_group->name();\n    } else if( operation == construction_operation::markers ) {\n        heading = selection_missing ? _( "Markers" ) : selected_group->name();\n    }\n    add( colorize( heading, c_light_green ) );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        add( operation == construction_operation::remove ?\n             _( "Select a world tile to inspect its removal action." ) :\n             inspect_mode ?\n             _( "Select a tile to inspect contextual work such as repairs, or choose a build result from the catalog." ) :\n             _( "Hover or select a world tile." ) );\n''',
    '''        add( operation == construction_operation::remove ?\n             _( "Select a world tile to inspect its removal action." ) :\n             inspect_mode ?\n             _( "Select a tile to inspect contextual work such as repairs, or choose a build result from the catalog." ) :\n             selection_missing && operation == construction_operation::place ?\n             _( "Choose one of the placeable items currently carried." ) :\n             selection_missing && operation == construction_operation::markers ?\n             _( "Choose a marker, then select a world tile." ) :\n             _( "Hover or select a world tile." ) );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    if( inspect_mode ) {\n        if( context_actions.empty() ) {\n''',
    '''    if( inspect_mode ) {\n        if( context_actions.empty() ) {\n'''
)
# Insert missing-selection return immediately after inspect-mode block.
replace_once(
    "src/construction_ui.cpp",
    '''        inspector.model().scroll_to_start();\n        return;\n    }\n\n    const nc_color status_color = resolution.status == construction_target_status::ready ?\n''',
    '''        inspector.model().scroll_to_start();\n        return;\n    }\n    if( selection_missing ) {\n        blank();\n        add( colorize( operation == construction_operation::place ?\n                       _( "Choose a carried item from the left." ) :\n                       _( "Choose a marker from the left." ), c_dark_gray ) );\n        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );\n        inspector.model().scroll_to_start();\n        return;\n    }\n\n    const nc_color status_color = resolution.status == construction_target_status::ready ?\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    add( colorize( operation == construction_operation::remove ? _( "Action" ) : _( "Result" ),\n                   c_light_gray ) );\n''',
    '''    add( colorize( operation == construction_operation::remove ? _( "Action" ) :\n                   operation == construction_operation::place ? _( "Place" ) :\n                   operation == construction_operation::markers ? _( "Marker" ) : _( "Result" ),\n                   c_light_gray ) );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    con->requirements->can_make_with_inventory( you.crafting_inventory(), is_crafting_component, 1,\n            craft_flags::none, false );\n    blank();\n    const std::vector<std::string> tools = con->requirements->get_folded_tools_list(\n            wrap_width, c_light_gray, you.crafting_inventory() );\n''',
    '''    con->requirements->can_make_with_inventory( active_inventory(), is_crafting_component, 1,\n            craft_flags::none, false );\n    blank();\n    const std::vector<std::string> tools = con->requirements->get_folded_tools_list(\n            wrap_width, c_light_gray, active_inventory() );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    const std::vector<std::string> components = con->requirements->get_folded_components_list(\n            wrap_width, c_light_gray, you.crafting_inventory(), is_crafting_component );\n''',
    '''    const std::vector<std::string> components = con->requirements->get_folded_components_list(\n            wrap_width, c_light_gray, operation == construction_operation::place ?\n            static_cast<const read_only_visitable &>( you ) : active_inventory(), is_crafting_component );\n'''
)

# Inspector buttons: collapse decoration into a chooser and label the primary
# operation accurately.
replace_once(
    "src/construction_ui.cpp",
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();\n    const bool show_context_actions = operation == construction_operation::build &&\n                                      selected_target && !context_actions.empty();\n''',
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();\n    const bool selection_missing = operation != construction_operation::remove && selected_group.is_null();\n    const bool show_context_actions = operation == construction_operation::build &&\n                                      selected_target && !context_actions.empty();\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    ui_action_entry build( _( "Select a target" ), "APPLY", false, false,\n                           operation == construction_operation::remove ?\n                           _( "Select a world tile first." ) :\n                           _( "Select a construction and a world tile first." ) );\n''',
    '''    ui_action_entry build( _( "Select a target" ), "APPLY", false, false,\n                           operation == construction_operation::remove ?\n                           _( "Select a world tile first." ) :\n                           operation == construction_operation::place ?\n                           _( "Select a carried item and a world tile first." ) :\n                           operation == construction_operation::markers ?\n                           _( "Select a marker and a world tile first." ) :\n                           _( "Select a construction and a world tile first." ) );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''                build.label = operation == construction_operation::remove && resolved_construction() ?\n                              string_format( _( "Remove %s" ), resolved_construction()->group->name() ) :\n                              _( "Build here" );\n''',
    '''                if( operation == construction_operation::remove && resolved_construction() ) {\n                    build.label = string_format( _( "Remove %s" ), resolved_construction()->group->name() );\n                } else if( operation == construction_operation::place ) {\n                    build.label = _( "Place here" );\n                } else if( operation == construction_operation::markers ) {\n                    build.label = _( "Mark here" );\n                } else {\n                    build.label = _( "Build here" );\n                }\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        for( const construction_context_action &action : context_actions ) {\n            bool enabled = action.resolution.ready();\n            std::string reason = action.resolution.reason;\n''',
    '''        bool decorate_group_added = false;\n        for( const construction_context_action &action : context_actions ) {\n            if( action.intent == construction_ui_intent::decorate ) {\n                if( !decorate_group_added ) {\n                    ui_action_entry decorate( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE", true, false,\n                                              _( "Choose a surface treatment for this tile." ) );\n                    decorate.tone = ui_action_tone::positive;\n                    entries.push_back( std::move( decorate ) );\n                    decorate_group_added = true;\n                }\n                continue;\n            }\n            bool enabled = action.resolution.ready();\n            std::string reason = action.resolution.reason;\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    if( inspect_mode ) {\n        primary_action.clear();\n    } else {\n        build.tone = operation == construction_operation::build ?\n                     ui_action_tone::positive : ui_action_tone::destructive;\n''',
    '''    if( inspect_mode || selection_missing ) {\n        primary_action.clear();\n    } else {\n        build.tone = operation == construction_operation::remove ?\n                     ui_action_tone::destructive : ui_action_tone::positive;\n'''
)

# Operation switching and semantic section dropdown.
replace_once(
    "src/construction_ui.cpp",
    '''    if( operation == construction_operation::remove && next == workspace_focus::palette ) {\n''',
    '''    if( operation == construction_operation::remove && next == workspace_focus::palette ) {\n'''
)
replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::set_operation( const construction_operation next, ui_adaptor &ui )\n",
    "void construction_workspace::edit_search()\n",
    '''void construction_workspace::set_operation( const construction_operation next, ui_adaptor &ui )\n{\n    if( operation == next ) {\n        return;\n    }\n    operation = next;\n    category_menu.close();\n    context_menu.close();\n    selected_group = construction_group_str_id::NULL_ID();\n    selected_target.reset();\n    hovered_target.reset();\n    context_target.reset();\n    section_filter.reset();\n    selection_cleared_by_user = false;\n    transient_status.clear();\n    if( operation == construction_operation::remove ) {\n        focus = workspace_focus::viewport;\n    } else if( compact ) {\n        focus = workspace_focus::palette;\n    }\n    rebuild_palette();\n    refresh_active_target();\n    if( compact ) {\n        ui.mark_resize();\n    }\n}\n\n'''
)
replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::edit_search()\n",
    "void construction_workspace::open_category_menu()\n",
    '''void construction_workspace::edit_search()\n{\n    if( operation == construction_operation::remove ) {\n        transient_status = _( "Search is not needed in Remove mode." );\n        return;\n    }\n    const std::string title = operation == construction_operation::place ?\n                              _( "Search carried items" ) : operation == construction_operation::markers ?\n                              _( "Search markers" ) : _( "Search constructions" );\n    const std::optional<std::string> edited = ui_query_text_input_dialog(\n            title, _( "Search" ), search, 30, 100 );\n    if( edited ) {\n        search = *edited;\n        uistate.construction_filter = search;\n        rebuild_palette();\n    }\n}\n\n'''
)
replace_between(
    "src/construction_ui.cpp",
    "void construction_workspace::open_category_menu()\n",
    "void construction_workspace::open_context_menu( const point &anchor,\n",
    '''void construction_workspace::open_category_menu()\n{\n    if( !palette_window || operation == construction_operation::remove ) {\n        return;\n    }\n    std::set<construction_ui_section> sections;\n    for( const construction &con : get_constructions() ) {\n        if( palette_accepts( con ) ) {\n            sections.insert( con.ui_section );\n        }\n    }\n    std::vector<ui_dropdown_entry> entries;\n    entries.emplace_back( _( "All sections" ), "SECTION_ALL", true, !section_filter );\n    for( const construction_ui_section candidate : {\n             construction_ui_section::structures, construction_ui_section::furniture,\n             construction_ui_section::workshop, construction_ui_section::outdoor,\n             construction_ui_section::infrastructure, construction_ui_section::appliances,\n             construction_ui_section::other\n         } ) {\n        if( sections.count( candidate ) == 0 ) {\n            continue;\n        }\n        entries.emplace_back( catalog_section_label( candidate ), catalog_section_id( candidate ), true,\n                              section_filter && *section_filter == candidate );\n    }\n    category_menu.configure( palette_window, point( 2, 6 ), std::move( entries ),\n                             std::max( 16, palette_width - 4 ) );\n    category_menu.focus_selected();\n}\n\n'''
)

# Context menu uses the active operation resolver; decoration gets its own popup
# from the inspector so large color/material families do not consume the strip.
replace_once(
    "src/construction_ui.cpp",
    '''    const construction_target_resolution target_resolution =\n        operation == construction_operation::remove ?\n        resolve_remove_target( you, you.crafting_inventory(), target ) :\n        resolve_construction_target( you, you.crafting_inventory(), selected_group, target );\n''',
    '''    const construction_target_resolution target_resolution = resolve_active_target( target );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    std::string build_label = operation == construction_operation::remove ?\n                              _( "Remove here" ) : _( "Build here" );\n''',
    '''    std::string build_label = operation == construction_operation::remove ? _( "Remove here" ) :\n                              operation == construction_operation::place ? _( "Place here" ) :\n                              operation == construction_operation::markers ? _( "Mark here" ) : _( "Build here" );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    if( operation == construction_operation::remove || !selected_group.is_null() ) {\n''',
    '''    if( operation == construction_operation::remove || !selected_group.is_null() ) {\n'''
)
# Add grouped contextual popup before execute_context_action.
replace_once(
    "src/construction_ui.cpp",
    '''bool construction_workspace::execute_context_action( const std::string &id )\n''',
    '''void construction_workspace::open_context_intent_menu( const point &anchor,\n        const tripoint_bub_ms &target, const construction_ui_intent intent )\n{\n    context_target = target;\n    const bool adjacent = target_is_adjacent( target );\n    std::vector<ui_dropdown_entry> entries;\n    for( const construction_context_action &action :\n         resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {\n        if( action.intent != intent ) {\n            continue;\n        }\n        bool enabled = action.resolution.ready() && adjacent;\n        std::string reason = adjacent ? action.resolution.reason :\n                             _( "Move adjacent to use this tile action." );\n        entries.emplace_back( contextual_action_label( action ), contextual_action_id( action ),\n                              enabled, false, reason );\n    }\n    if( entries.empty() ) {\n        entries.emplace_back( _( "No applicable actions" ), "NO_ACTION", false, false,\n                              _( "This tile has no applicable action in that group." ) );\n    }\n    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );\n}\n\nbool construction_workspace::execute_context_action( const std::string &id )\n'''
)

replace_between(
    "src/construction_ui.cpp",
    "bool construction_workspace::request_action( const tripoint_bub_ms &target )\n",
    "bool construction_workspace::request_context_action( const std::string &id,\n",
    '''bool construction_workspace::request_action( const tripoint_bub_ms &target )\n{\n    if( operation != construction_operation::remove && selected_group.is_null() ) {\n        transient_status = operation == construction_operation::build ?\n                           _( "Choose a build result, or use an available tile action." ) :\n                           operation == construction_operation::place ?\n                           _( "Choose a carried item to place." ) : _( "Choose a marker." );\n        return false;\n    }\n    const construction_target_resolution current = resolve_active_target( target );\n    if( !target_is_adjacent( target ) ) {\n        transient_status = operation == construction_operation::remove ?\n                           _( "Distant removal orders are not implemented yet." ) :\n                           operation == construction_operation::place ?\n                           _( "Distant placement orders are not implemented yet." ) :\n                           operation == construction_operation::markers ?\n                           _( "Distant marker orders are not implemented yet." ) :\n                           _( "Distant build orders are not implemented yet." );\n        return false;\n    }\n    if( !current.ready() && current.status != construction_target_status::in_progress ) {\n        transient_status = current.reason;\n        return false;\n    }\n    if( !g->warn_player_maybe_anger_local_faction( true ) ) {\n        transient_status = _( "Construction canceled." );\n        return false;\n    }\n    build_order = construction_build_order{ current.id, target,\n                                            current.status == construction_target_status::in_progress,\n                                            operation == construction_operation::place };\n    exit_requested = true;\n    return true;\n}\n\n'''
)

# Pointer/input routing for new modes and semantic sections.
replace_once(
    "src/construction_ui.cpp",
    '''            category = construction_category_id( result.entry->id );\n            uistate.construction_tab = category;\n            rebuild_palette();\n''',
    '''            if( result.entry->id == "SECTION_ALL" ) {\n                section_filter.reset();\n            } else {\n                section_filter = catalog_section_from_id( result.entry->id );\n            }\n            rebuild_palette();\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        } else if( id == "MODE_BUILD" ) {\n            set_operation( construction_operation::build, ui );\n        } else if( id == "MODE_REMOVE" ) {\n            set_operation( construction_operation::remove, ui );\n''',
    '''        } else if( id == "MODE_BUILD" ) {\n            set_operation( construction_operation::build, ui );\n        } else if( id == "MODE_PLACE" ) {\n            set_operation( construction_operation::place, ui );\n        } else if( id == "MODE_REMOVE" ) {\n            set_operation( construction_operation::remove, ui );\n        } else if( id == "MODE_MARKERS" ) {\n            set_operation( construction_operation::markers, ui );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    if( palette_window && operation == construction_operation::build ) {\n''',
    '''    if( palette_window && operation != construction_operation::remove ) {\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''            } else if( palette_action.entry->id == "SHOW_UNAVAILABLE" ) {\n                show_unavailable = !show_unavailable;\n                rebuild_palette();\n''',
    '''            } else if( palette_action.entry->id == "SHOW_UNAVAILABLE" &&\n                       operation == construction_operation::build ) {\n                show_unavailable = !show_unavailable;\n                rebuild_palette();\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''            uistate.last_construction = selected_group;\n            refresh_active_target();\n''',
    '''            if( operation == construction_operation::build ) {\n                uistate.last_construction = selected_group;\n            }\n            refresh_active_target();\n'''
)
# There is a second keyboard selection path with the same assignment.
replace_once(
    "src/construction_ui.cpp",
    '''            uistate.last_construction = selected_group;\n            refresh_active_target();\n        }\n        return result.consumed();\n''',
    '''            if( operation == construction_operation::build ) {\n                uistate.last_construction = selected_group;\n            }\n            refresh_active_target();\n        }\n        return result.consumed();\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        if( contextual_result.type == ui_action_result_type::activated && contextual_result.entry ) {\n            if( selected_target ) {\n                request_context_action( contextual_result.entry->id, *selected_target );\n            }\n            return true;\n        }\n''',
    '''        if( contextual_result.type == ui_action_result_type::activated && contextual_result.entry ) {\n            if( selected_target ) {\n                if( contextual_result.entry->id == "CONTEXT_GROUP_DECORATE" && screen_pos ) {\n                    open_context_intent_menu( *screen_pos, *selected_target,\n                                              construction_ui_intent::decorate );\n                } else {\n                    request_context_action( contextual_result.entry->id, *selected_target );\n                }\n            }\n            return true;\n        }\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''        if( operation != construction_operation::build ) {\n            transient_status = _( "Unavailable filtering is available in Build mode." );\n            return true;\n        }\n''',
    '''        if( operation != construction_operation::build ) {\n            transient_status = _( "Unavailable filtering is only used by the Build catalog." );\n            return true;\n        }\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    if( focus == workspace_focus::palette && palette_window &&\n        operation == construction_operation::build ) {\n''',
    '''    if( focus == workspace_focus::palette && palette_window &&\n        operation != construction_operation::remove ) {\n'''
)

# World overlay resolves hover according to the active mode.
replace_once(
    "src/construction_ui.cpp",
    '''        const construction_target_resolution hover_state =\n            operation == construction_operation::remove ?\n            resolve_remove_target( you, you.crafting_inventory(), *hovered_target ) :\n            resolve_construction_target( you, you.crafting_inventory(), selected_group, *hovered_target );\n''',
    '''        const construction_target_resolution hover_state = resolve_active_target( *hovered_target );\n'''
)

# Final persistence/execution: raw backend category tab is no longer the UI
# filter, and placement revalidates against carried inventory.
replace_once(
    "src/construction_ui.cpp",
    '''    uistate.construction_filter = search;\n    uistate.construction_tab = category;\n    if( !selected_group.is_null() ) {\n        uistate.last_construction = selected_group;\n    }\n''',
    '''    uistate.construction_filter = search;\n    if( operation == construction_operation::build && !selected_group.is_null() ) {\n        uistate.last_construction = selected_group;\n    }\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''                                      start_construction_at( you, final_order->id.obj(), final_order->target );\n''',
    '''                                      start_construction_at( you, final_order->id.obj(), final_order->target,\n                                                             final_order->carried_source_only );\n'''
)

# Fix the primary-action descriptive labels in distant modes.
replace_once(
    "src/construction_ui.cpp",
    '''                build.label = operation == construction_operation::remove ?\n                              _( "Go there and remove" ) : _( "Go there and build" );\n                build.disabled_reason = operation == construction_operation::remove ?\n                                        _( "Distant removal orders are not implemented yet." ) :\n                                        _( "Distant build orders are planned for the next construction pass." );\n''',
    '''                build.label = operation == construction_operation::remove ? _( "Go there and remove" ) :\n                              operation == construction_operation::place ? _( "Go there and place" ) :\n                              operation == construction_operation::markers ? _( "Go there and mark" ) :\n                              _( "Go there and build" );\n                build.disabled_reason = operation == construction_operation::remove ?\n                                        _( "Distant removal orders are not implemented yet." ) :\n                                        operation == construction_operation::place ?\n                                        _( "Distant placement orders are not implemented yet." ) :\n                                        operation == construction_operation::markers ?\n                                        _( "Distant marker orders are not implemented yet." ) :\n                                        _( "Distant build orders are planned for the next construction pass." );\n'''
)

# Avoid stale selection on operation switches in compact layouts and make the
# palette header/filters redraw immediately.
replace_once(
    "src/construction_ui.cpp",
    '''    if( compact && operation == construction_operation::build ) {\n''',
    '''    if( compact && operation != construction_operation::remove ) {\n'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Separate build, placement and contextual construction catalogs [skip ci]\n"
)
