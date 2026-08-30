from pathlib import Path
import json


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


def top_object_spans(text: str):
    spans = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                spans.append((start, i + 1))
                start = None
    return spans


def set_field_for_id(path: str, ident: str, field: str, value: str) -> None:
    p = Path(path)
    text = p.read_text()
    matches = []
    for start, end in top_object_spans(text):
        block = text[start:end]
        obj = json.loads(block)
        if obj.get("type") == "construction" and obj.get("id") == ident:
            matches.append((start, end, block))
    if len(matches) != 1:
        raise RuntimeError(f"{path}: expected one construction {ident}, found {len(matches)}")
    start, end, block = matches[0]
    lines = block.splitlines(keepends=True)
    prefix = f'    "{field}":'
    replacement = f'    "{field}": {json.dumps(value)},\n'
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = replacement
            break
    else:
        raise RuntimeError(f"{path}: {ident} has no {field}")
    p.write_text(text[:start] + "".join(lines) + text[end:])


# Window-bar installation is an upgrade of a selected window, not a standalone
# Build catalog result.  The ordinary no-curtains stage, however, is the bridge
# between an empty frame and the finished domestic window and must remain in
# the hidden Build chain.
for ident in (
    "constr_window_bars",
    "constr_window_bars_alarm",
    "constr_window_bars_frame",
):
    set_field_for_id("data/json/construction/windows.json", ident, "ui_intent", "upgrade")
set_field_for_id("data/json/construction/windows.json", "constr_window_no_curtains",
                 "ui_intent", "build")

# A manhole cover is a finished carried object installed onto an existing
# opening, so it belongs with other inventory-driven placement actions.
set_field_for_id("data/json/construction/zlvels_transition.json", "constr_manhole_cover",
                 "ui_intent", "place")

# Place availability should require the physical source item to be carried,
# while allowing ordinary installation tools/qualities to come from normal
# crafting reach.  The old carried_source_only precheck incorrectly restricted
# *all* requirements to the character inventory.
replace_once(
    "src/construction.cpp",
    '''    const read_only_visitable &available_inventory = carried_source_only ?\n            static_cast<const read_only_visitable &>( who ) : who.crafting_inventory();\n    if( !free_test_mode && !player_can_build( who, available_inventory, con, true ) ) {\n        return ret_val<void>::make_failure( carried_source_only ?\n                _( "The item to place is no longer in your carried inventory, or its installation requirements are no longer met." ) :\n                _( "You no longer meet the construction requirements." ) );\n    }\n''',
    '''    if( !free_test_mode && carried_source_only ) {\n        for( const std::vector<item_comp> &alternatives : con.requirements->get_components() ) {\n            const bool carried = std::any_of( alternatives.begin(), alternatives.end(),\n            [&who]( const item_comp & component ) {\n                return component.has( who, is_crafting_component, 1, craft_flags::none );\n            } );\n            if( !carried ) {\n                return ret_val<void>::make_failure(\n                           _( "The item to place is no longer in your carried inventory." ) );\n            }\n        }\n    }\n    if( !free_test_mode && !player_can_build( who, who.crafting_inventory(), con, true ) ) {\n        return ret_val<void>::make_failure( carried_source_only ?\n                _( "The installation requirements are no longer met." ) :\n                _( "You no longer meet the construction requirements." ) );\n    }\n'''
)

# Normal construction can consume reachable components.  Place deliberately
# selects each source component against an empty map inventory, forcing the
# selected component to come from the character while leaving tool consumption
# on the normal construction path.
replace_once(
    "src/construction.cpp",
    '''    } else {\n        for( const std::vector<item_comp> &alternatives : con.requirements->get_components() ) {\n            std::list<item> consumed = who.consume_items( alternatives, 1, is_crafting_component,\n                                       return_false<itype_id>, true );\n            if( consumed.empty() ) {\n                return ret_val<void>::make_failure( _( "The required components are no longer available." ) );\n            }\n            used.splice( used.end(), consumed );\n        }\n    }\n''',
    '''    } else {\n        inventory no_map_components;\n        for( const std::vector<item_comp> &alternatives : con.requirements->get_components() ) {\n            std::list<item> consumed;\n            if( carried_source_only ) {\n                const auto selected = who.select_item_component( alternatives, 1, no_map_components, false,\n                                      is_crafting_component, true );\n                consumed = who.consume_items( selected, 1, is_crafting_component );\n            } else {\n                consumed = who.consume_items( alternatives, 1, is_crafting_component,\n                                              return_false<itype_id>, true );\n            }\n            if( consumed.empty() ) {\n                return ret_val<void>::make_failure( carried_source_only ?\n                        _( "The item to place is no longer in your carried inventory." ) :\n                        _( "The required components are no longer available." ) );\n            }\n            used.splice( used.end(), consumed );\n        }\n    }\n'''
)

# Keep the context-menu anchor while replacing the top-level menu with an
# intent submenu.  This makes right-click decoration use the same collapsed
# presentation as the inspector instead of dumping every paint/carpet variant.
replace_once(
    "src/construction_ui.cpp",
    '''        std::optional<tripoint_bub_ms> context_target;\n        construction_target_resolution resolution;\n''',
    '''        std::optional<tripoint_bub_ms> context_target;\n        std::optional<point> context_anchor;\n        construction_target_resolution resolution;\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    context_target.reset();\n    context_actions.clear();\n''',
    '''    context_target.reset();\n    context_anchor.reset();\n    context_actions.clear();\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    context_target = target;\n    const construction_target_resolution target_resolution = resolve_active_target( target );\n''',
    '''    context_target = target;\n    context_anchor = anchor;\n    const construction_target_resolution target_resolution = resolve_active_target( target );\n'''
)
replace_once(
    "src/construction_ui.cpp",
    '''    context_target = target;\n    const bool adjacent = target_is_adjacent( target );\n    std::vector<ui_dropdown_entry> entries;\n''',
    '''    context_target = target;\n    context_anchor = anchor;\n    const bool adjacent = target_is_adjacent( target );\n    std::vector<ui_dropdown_entry> entries;\n'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    if( operation == construction_operation::build ) {\n        std::vector<ui_dropdown_entry> contextual_entries;\n        for( const construction_context_action &action :\n             resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {\n            bool enabled = action.resolution.ready() && adjacent;\n            std::string reason = action.resolution.reason;\n            if( !adjacent ) {\n                reason = _( "Move adjacent to use this tile action." );\n            }\n            contextual_entries.emplace_back( contextual_action_label( action ),\n                                               contextual_action_id( action ),\n                                               enabled, false, reason );\n        }\n        entries.insert( entries.begin() + 1, contextual_entries.begin(), contextual_entries.end() );\n    }\n''',
    '''    if( operation == construction_operation::build ) {\n        std::vector<ui_dropdown_entry> contextual_entries;\n        bool has_decorate = false;\n        bool decorate_ready = false;\n        std::string decorate_reason;\n        for( const construction_context_action &action :\n             resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {\n            if( action.intent == construction_ui_intent::decorate ) {\n                has_decorate = true;\n                decorate_ready = decorate_ready || action.resolution.ready();\n                if( decorate_reason.empty() && !action.resolution.ready() ) {\n                    decorate_reason = action.resolution.reason;\n                }\n                continue;\n            }\n            bool enabled = action.resolution.ready() && adjacent;\n            std::string reason = action.resolution.reason;\n            if( !adjacent ) {\n                reason = _( "Move adjacent to use this tile action." );\n            }\n            contextual_entries.emplace_back( contextual_action_label( action ),\n                                               contextual_action_id( action ),\n                                               enabled, false, reason );\n        }\n        if( has_decorate ) {\n            const bool enabled = decorate_ready && adjacent;\n            const std::string reason = !adjacent ? _( "Move adjacent to decorate this tile." ) :\n                                       decorate_ready ? std::string() : decorate_reason;\n            contextual_entries.emplace_back( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",\n                                               enabled, false, reason );\n        }\n        entries.insert( entries.begin() + 1, contextual_entries.begin(), contextual_entries.end() );\n    }\n'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    } else if( id.rfind( "CONTEXT_", 0 ) == 0 ) {\n        return request_context_action( id, *context_target );\n''',
    '''    } else if( id == "CONTEXT_GROUP_DECORATE" ) {\n        if( context_anchor ) {\n            open_context_intent_menu( *context_anchor, *context_target,\n                                      construction_ui_intent::decorate );\n        }\n    } else if( id.rfind( "CONTEXT_", 0 ) == 0 ) {\n        return request_context_action( id, *context_target );\n'''
)

# The inspector already collapses decoration; make the group button accurately
# reflect adjacency and whether at least one decoration method is currently ready.
replace_once(
    "src/construction_ui.cpp",
    '''        std::vector<ui_action_entry> entries;\n        entries.reserve( context_actions.size() );\n        bool decorate_group_added = false;\n        for( const construction_context_action &action : context_actions ) {\n            if( action.intent == construction_ui_intent::decorate ) {\n                if( !decorate_group_added ) {\n                    ui_action_entry decorate( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE", true, false,\n                                              _( "Choose a surface treatment for this tile." ) );\n                    decorate.tone = ui_action_tone::positive;\n                    entries.push_back( std::move( decorate ) );\n                    decorate_group_added = true;\n                }\n                continue;\n            }\n''',
    '''        std::vector<ui_action_entry> entries;\n        entries.reserve( context_actions.size() );\n        const bool decorate_ready = std::any_of( context_actions.begin(), context_actions.end(),\n        []( const construction_context_action & action ) {\n            return action.intent == construction_ui_intent::decorate && action.resolution.ready();\n        } );\n        bool decorate_group_added = false;\n        for( const construction_context_action &action : context_actions ) {\n            if( action.intent == construction_ui_intent::decorate ) {\n                if( !decorate_group_added ) {\n                    const bool adjacent = selected_target && target_is_adjacent( *selected_target );\n                    const bool enabled = decorate_ready && adjacent;\n                    const std::string reason = !adjacent ? _( "Move adjacent to decorate this tile." ) :\n                                               decorate_ready ? std::string() :\n                                               _( "No decoration option currently meets its requirements." );\n                    ui_action_entry decorate( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",\n                                              enabled, false, reason );\n                    decorate.tone = ui_action_tone::positive;\n                    entries.push_back( std::move( decorate ) );\n                    decorate_group_added = true;\n                }\n                continue;\n            }\n'''
)

# Validate all edited construction JSON and semantic invariants touched here.
for path in sorted(Path("data/json/construction").glob("*.json")):
    data = json.loads(path.read_text())
    for obj in data:
        if isinstance(obj, dict) and obj.get("type") == "construction":
            if "ui_intent" not in obj or "ui_section" not in obj:
                raise RuntimeError(f"{path}: {obj.get('id')} lacks explicit UI semantics")

Path("/tmp/branch_patch_commit_message").write_text(
    "Finish construction semantic cleanup [skip ci]\n"
)
