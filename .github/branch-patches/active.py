from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


def annotate_group(path: str, group: str, intent: str, action: str = "") -> None:
    p = Path(path)
    text = p.read_text()
    needle = f'    "group": "{group}",\n'
    count = text.count(needle)
    if count < 1:
        raise RuntimeError(f"{path}: expected at least one {group} definition")
    annotation = needle + f'    "ui_intent": "{intent}",\n'
    if action:
        annotation += f'    "ui_action": "{action}",\n'
    p.write_text(text.replace(needle, annotation))


# When several backend groups deliberately share an action key, present the
# semantic verb rather than whichever implementation happened to rank first.
replace_once(
    "src/construction_ui.cpp",
    '''static std::string contextual_action_label( const construction_context_action &action )
{
    if( action.intent == construction_ui_intent::repair ) {
        return contextual_intent_label( action.intent );
    }
    if( action.resolution.id.is_valid() ) {
        return action.resolution.id.obj().group->name();
    }
    return contextual_intent_label( action.intent );
}
''',
    '''static std::string contextual_action_label( const construction_context_action &action )
{
    if( action.intent == construction_ui_intent::repair ) {
        return contextual_intent_label( action.intent );
    }
    if( action.resolution.id.is_valid() ) {
        const construction &chosen = action.resolution.id.obj();
        if( !chosen.ui_action.empty() && chosen.ui_action != chosen.group.str() ) {
            return contextual_intent_label( action.intent );
        }
        return chosen.group->name();
    }
    return contextual_intent_label( action.intent );
}
'''
)

# Reserve two rows for real world-object actions.  This comfortably fits the
# first migration (repair/board/tape/reinforce) without committing the UI to a
# huge ungrouped decoration list later.
replace_once(
    "src/construction_ui.cpp",
    '''    const bool show_context_actions = operation == construction_operation::build &&
                                      selected_target && !context_actions.empty();
    const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int contextual_action_y = show_context_actions ?
                                    std::max( 2, primary_action_y - 2 ) : primary_action_y;
    const int content_height = std::max( 1, contextual_action_y - 2 );
''',
    '''    const bool show_context_actions = operation == construction_operation::build &&
                                      selected_target && !context_actions.empty();
    const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int contextual_action_y = show_context_actions ?
                                    std::max( 2, primary_action_y - 3 ) : primary_action_y;
    const int content_height = std::max( 1, contextual_action_y - 2 );
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''        contextual_action_strip.configure( inspector_window, point( 2, contextual_action_y ),
                                           std::move( entries ), inspector_width - 4, 1 );
''',
    '''        contextual_action_strip.configure( inspector_window, point( 2, contextual_action_y ),
                                           std::move( entries ), inspector_width - 4, 2 );
'''
)

# First real verb migration.  These groups all operate on an existing world
# object; they are not useful as global catalog nouns.  Backend variants within
# each group remain intact and are resolved from the clicked tile.
annotate_group( "data/json/construction/windows.json", "board_up_window", "modify" )
annotate_group( "data/json/construction/windows.json", "tape_up_window", "modify" )
annotate_group( "data/json/construction/windows.json", "reinforce_boarded_window", "upgrade" )

annotate_group( "data/json/construction/doors.json", "board_up_wood_door", "modify" )
annotate_group( "data/json/construction/doors.json", "reinforce_wood_door", "upgrade" )

# These are two different implementation groups for the same player intent.
# ui_action deliberately merges them so the player sees one Upgrade action and
# the resolver chooses the better applicable requirement path.
annotate_group(
    "data/json/construction/walls.json",
    "reinforce_junk_metal_wall_using_bolts",
    "upgrade",
    "reinforce_junk_wall"
)
annotate_group(
    "data/json/construction/walls.json",
    "reinforce_junk_metal_wall_using_spot_welds",
    "upgrade",
    "reinforce_junk_wall"
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Move structural verbs into contextual construction actions [skip ci]\n"
)
