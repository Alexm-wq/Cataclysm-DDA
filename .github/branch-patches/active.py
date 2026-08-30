from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


def annotate_group(path: str, group: str, intent: str) -> None:
    p = Path(path)
    text = p.read_text()
    needle = f'    "group": "{group}",\n'
    count = text.count(needle)
    if count < 1:
        raise RuntimeError(f"{path}: expected at least one {group} definition")
    replacement = needle + f'    "ui_intent": "{intent}",\n'
    p.write_text(text.replace(needle, replacement))


# Allow contextual definitions to carry a translated player-facing verb/name.
# This is especially useful when ui_action deliberately merges different backend groups.
replace_once(
    "src/construction.h",
    '''        // Optional key used to merge multiple backend definitions into one contextual UI action.
        std::string ui_action;
        // Additional note displayed along with construction requirements.
''',
    '''        // Optional key used to merge multiple backend definitions into one contextual UI action.
        std::string ui_action;
        // Optional translated player-facing name for the contextual action.
        translation ui_name;
        // Additional note displayed along with construction requirements.
'''
)

replace_once(
    "src/construction.cpp",
    '''    con.ui_action = jo.get_string( "ui_action", "" );
    if( jo.has_string( "time" ) ) {
''',
    '''    con.ui_action = jo.get_string( "ui_action", "" );
    jo.read( "ui_name", con.ui_name );
    if( jo.has_string( "time" ) ) {
'''
)

replace_once(
    "src/construction_ui.cpp",
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
''',
    '''static std::string contextual_action_label( const construction_context_action &action )
{
    if( action.resolution.id.is_valid() ) {
        const construction &chosen = action.resolution.id.obj();
        if( !chosen.ui_name.empty() ) {
            return chosen.ui_name.translated();
        }
        if( action.intent == construction_ui_intent::repair ) {
            return contextual_intent_label( action.intent );
        }
        if( !chosen.ui_action.empty() && chosen.ui_action != chosen.group.str() ) {
            return contextual_intent_label( action.intent );
        }
        return chosen.group->name();
    }
    return contextual_intent_label( action.intent );
}
'''
)

# Give the cross-group junk-wall upgrade a real player-facing name on both
# implementation variants.  The resolver still decides bolts vs spot welding.
p = Path("data/json/construction/walls.json")
text = p.read_text()
needle = '    "ui_action": "reinforce_junk_wall",\n'
count = text.count(needle)
if count != 2:
    raise RuntimeError(f"walls.json: expected two reinforce_junk_wall variants, found {count}")
text = text.replace(needle, needle + '    "ui_name": "Reinforce junk wall",\n')
p.write_text(text)

# Safe world-work migration: these are verbs whose correct backend recipe is
# determined by the clicked terrain.  They no longer need global catalog rows.
annotate_group( "data/json/construction/flora.json", "cut_grass", "terrain_work" )
annotate_group( "data/json/construction/terrain.json", "constr_excavate_forestfloor", "terrain_work" )
annotate_group( "data/json/construction/terrain.json", "fill_pit_with_dirt", "terrain_work" )
annotate_group( "data/json/construction/terrain.json", "fill_recess_with_dirt", "terrain_work" )
annotate_group( "data/json/construction/terrain.json", "fill_shallow_water_with_dirt", "terrain_work" )
annotate_group( "data/json/construction/terrain.json", "fill_salt_water_with_dirt", "terrain_work" )

Path("/tmp/branch_patch_commit_message").write_text(
    "Move obvious world work out of the build catalog [skip ci]\n"
)
