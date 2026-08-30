from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


# Give contextual definitions an optional semantic action key.  By default,
# Repair collapses to one action while other future intents stay distinct per group.
replace_once(
    "src/construction.h",
    '''        construction_action action = construction_action::build;
        construction_ui_intent ui_intent = construction_ui_intent::build;
        // Additional note displayed along with construction requirements.
''',
    '''        construction_action action = construction_action::build;
        construction_ui_intent ui_intent = construction_ui_intent::build;
        // Optional key used to merge multiple backend definitions into one contextual UI action.
        std::string ui_action;
        // Additional note displayed along with construction requirements.
'''
)

replace_once(
    "src/construction.cpp",
    '''    if( con.action == construction_action::build &&
        con.ui_intent == construction_ui_intent::remove ) {
        jo.throw_error_at( "ui_intent",
                           "Build constructions cannot use ui_intent remove" );
    }
    if( jo.has_string( "time" ) ) {
''',
    '''    if( con.action == construction_action::build &&
        con.ui_intent == construction_ui_intent::remove ) {
        jo.throw_error_at( "ui_intent",
                           "Build constructions cannot use ui_intent remove" );
    }
    con.ui_action = jo.get_string( "ui_action", "" );
    if( jo.has_string( "time" ) ) {
'''
)

replace_once(
    "src/construction_target.h",
    '''struct construction_context_action {
    construction_ui_intent intent = construction_ui_intent::build;
    construction_target_resolution resolution;
};
''',
    '''struct construction_context_action {
    construction_ui_intent intent = construction_ui_intent::build;
    std::string key;
    construction_target_resolution resolution;
};
'''
)

replace_once(
    "src/construction_target.cpp",
    '''#include <array>
#include <optional>
''',
    '''#include <array>
#include <map>
#include <optional>
'''
)

replace_once(
    "src/construction_target.cpp",
    '''    const std::array<construction_ui_intent, 6> contextual_intents = {
        construction_ui_intent::repair,
        construction_ui_intent::modify,
        construction_ui_intent::upgrade,
        construction_ui_intent::terrain_work,
        construction_ui_intent::decorate,
        construction_ui_intent::marker
    };
    for( const construction_ui_intent intent : contextual_intents ) {
        std::vector<const construction *> candidates;
        for( const construction &con : get_constructions() ) {
            if( construction_ui_intent_for( con ) == intent ) {
                candidates.push_back( &con );
            }
        }
        if( candidates.empty() ) {
            continue;
        }

        std::string ready_reason = _( "Ready." );
        switch( intent ) {
            case construction_ui_intent::repair:
                ready_reason = _( "Ready to repair." );
                break;
            case construction_ui_intent::modify:
                ready_reason = _( "Ready to modify." );
                break;
            case construction_ui_intent::upgrade:
                ready_reason = _( "Ready to upgrade." );
                break;
            case construction_ui_intent::terrain_work:
                ready_reason = _( "Ready for terrain work." );
                break;
            case construction_ui_intent::decorate:
                ready_reason = _( "Ready to decorate." );
                break;
            case construction_ui_intent::marker:
                ready_reason = _( "Ready to mark." );
                break;
            case construction_ui_intent::build:
            case construction_ui_intent::remove:
                break;
        }

        const construction_target_resolution resolution = resolve_candidates(
                    who, inventory, candidates, target, ready_reason,
                    _( "This tile has no applicable contextual construction action." ) );
        if( resolution.has_construction() ) {
            result.push_back( construction_context_action{ intent, resolution } );
        }
    }
''',
    '''    const std::array<construction_ui_intent, 6> contextual_intents = {
        construction_ui_intent::repair,
        construction_ui_intent::modify,
        construction_ui_intent::upgrade,
        construction_ui_intent::terrain_work,
        construction_ui_intent::decorate,
        construction_ui_intent::marker
    };

    std::map<construction_ui_intent, std::map<std::string, std::vector<const construction *>>> buckets;
    for( const construction &con : get_constructions() ) {
        const construction_ui_intent intent = construction_ui_intent_for( con );
        if( std::find( contextual_intents.begin(), contextual_intents.end(), intent ) ==
            contextual_intents.end() ) {
            continue;
        }
        const std::string key = !con.ui_action.empty() ? con.ui_action :
                                intent == construction_ui_intent::repair ? "repair" : con.group.str();
        buckets[intent][key].push_back( &con );
    }

    for( const construction_ui_intent intent : contextual_intents ) {
        const auto intent_bucket = buckets.find( intent );
        if( intent_bucket == buckets.end() ) {
            continue;
        }
        for( const auto &bucket : intent_bucket->second ) {
            std::string ready_reason = _( "Ready." );
            switch( intent ) {
                case construction_ui_intent::repair:
                    ready_reason = _( "Ready to repair." );
                    break;
                case construction_ui_intent::modify:
                    ready_reason = _( "Ready to modify." );
                    break;
                case construction_ui_intent::upgrade:
                    ready_reason = _( "Ready to upgrade." );
                    break;
                case construction_ui_intent::terrain_work:
                    ready_reason = _( "Ready for terrain work." );
                    break;
                case construction_ui_intent::decorate:
                    ready_reason = _( "Ready to decorate." );
                    break;
                case construction_ui_intent::marker:
                    ready_reason = _( "Ready to mark." );
                    break;
                case construction_ui_intent::build:
                case construction_ui_intent::remove:
                    break;
            }

            const construction_target_resolution resolution = resolve_candidates(
                        who, inventory, bucket.second, target, ready_reason,
                        _( "This tile has no applicable contextual construction action." ) );
            if( resolution.has_construction() ) {
                result.push_back( construction_context_action{ intent, bucket.first, resolution } );
            }
        }
    }
'''
)

# Context action identity is now stable per semantic action key rather than only per intent.
replace_once(
    "src/construction_ui.cpp",
    '''static std::string contextual_action_label( const construction_ui_intent intent )
{
    switch( intent ) {
        case construction_ui_intent::repair:
            return _( "Repair" );
        case construction_ui_intent::modify:
            return _( "Modify" );
        case construction_ui_intent::upgrade:
            return _( "Upgrade" );
        case construction_ui_intent::terrain_work:
            return _( "Terrain work" );
        case construction_ui_intent::decorate:
            return _( "Decorate" );
        case construction_ui_intent::marker:
            return _( "Mark" );
        case construction_ui_intent::remove:
            return _( "Remove" );
        case construction_ui_intent::build:
            return _( "Build" );
    }
    return _( "Work" );
}

static std::string contextual_action_id( const construction_ui_intent intent )
{
    switch( intent ) {
        case construction_ui_intent::repair:
            return "CONTEXT_REPAIR";
        case construction_ui_intent::modify:
            return "CONTEXT_MODIFY";
        case construction_ui_intent::upgrade:
            return "CONTEXT_UPGRADE";
        case construction_ui_intent::terrain_work:
            return "CONTEXT_TERRAIN_WORK";
        case construction_ui_intent::decorate:
            return "CONTEXT_DECORATE";
        case construction_ui_intent::marker:
            return "CONTEXT_MARKER";
        case construction_ui_intent::remove:
            return "CONTEXT_REMOVE";
        case construction_ui_intent::build:
            return "CONTEXT_BUILD";
    }
    return "CONTEXT_WORK";
}
''',
    '''static std::string contextual_intent_label( const construction_ui_intent intent )
{
    switch( intent ) {
        case construction_ui_intent::repair:
            return _( "Repair" );
        case construction_ui_intent::modify:
            return _( "Modify" );
        case construction_ui_intent::upgrade:
            return _( "Upgrade" );
        case construction_ui_intent::terrain_work:
            return _( "Terrain work" );
        case construction_ui_intent::decorate:
            return _( "Decorate" );
        case construction_ui_intent::marker:
            return _( "Mark" );
        case construction_ui_intent::remove:
            return _( "Remove" );
        case construction_ui_intent::build:
            return _( "Build" );
    }
    return _( "Work" );
}

static std::string contextual_action_label( const construction_context_action &action )
{
    if( action.intent == construction_ui_intent::repair ) {
        return contextual_intent_label( action.intent );
    }
    if( action.resolution.id.is_valid() ) {
        return action.resolution.id.obj().group->name();
    }
    return contextual_intent_label( action.intent );
}

static std::string contextual_action_id( const construction_context_action &action )
{
    return string_format( "CONTEXT_%d_%s", static_cast<int>( action.intent ), action.key );
}
'''
)

for old, new in [
    ("contextual_action_label( action.intent )", "contextual_action_label( action )"),
    ("contextual_action_id( action.intent )", "contextual_action_id( action )")
]:
    p = Path("src/construction_ui.cpp")
    text = p.read_text()
    if old not in text:
        raise RuntimeError(f"src/construction_ui.cpp: missing {old}")
    p.write_text(text.replace(old, new))

# Keep an explicit Esc clear sticky within the current workspace.  A filter/category
# rebuild may restore a hidden recipe, but must never undo the user's explicit clear.
replace_once(
    "src/construction_ui.cpp",
    '''        bool show_unavailable = true;
        bool compact = false;
''',
    '''        bool show_unavailable = true;
        bool selection_cleared_by_user = false;
        bool compact = false;
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''        const auto remembered = std::find( visible_groups.begin(), visible_groups.end(),
                                           uistate.last_construction );
        if( remembered != visible_groups.end() ) {
            selected_group = *remembered;
            palette.select_only( static_cast<int>( remembered - visible_groups.begin() ) );
        } else {
''',
    '''        const auto remembered = std::find( visible_groups.begin(), visible_groups.end(),
                                           uistate.last_construction );
        if( !selection_cleared_by_user && remembered != visible_groups.end() ) {
            selected_group = *remembered;
            palette.select_only( static_cast<int>( remembered - visible_groups.begin() ) );
        } else {
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''void construction_workspace::clear_selection()
{
    selected_group = construction_group_str_id::NULL_ID();
''',
    '''void construction_workspace::clear_selection()
{
    selection_cleared_by_user = true;
    selected_group = construction_group_str_id::NULL_ID();
'''
)

# Every deliberate catalog selection re-enables ordinary remembered-selection behavior.
p = Path("src/construction_ui.cpp")
text = p.read_text()
old = '''            selected_group = construction_group_str_id( list_result.entry->id );
            uistate.last_construction = selected_group;
'''
new = '''            selected_group = construction_group_str_id( list_result.entry->id );
            selection_cleared_by_user = false;
            uistate.last_construction = selected_group;
'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"src/construction_ui.cpp: expected one mouse selection block, found {count}")
text = text.replace(old, new, 1)
old = '''            selected_group = construction_group_str_id( result.entry->id );
            uistate.last_construction = selected_group;
'''
new = '''            selected_group = construction_group_str_id( result.entry->id );
            selection_cleared_by_user = false;
            uistate.last_construction = selected_group;
'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"src/construction_ui.cpp: expected one keyboard selection block, found {count}")
text = text.replace(old, new, 1)
p.write_text(text)

# Normalize a remembered category if it no longer contains catalog-visible actions
# (for example REPAIR after becoming contextual), and pick a representative only
# from catalog variants of mixed groups.
replace_once(
    "src/construction_ui.cpp",
    '''    std::set<construction_group_str_id> seen;
    std::map<construction_group_str_id, bool> currently_available;
    for( const construction &con : get_constructions() ) {
''',
    '''    if( category != construction_category_ALL ) {
        const bool category_has_catalog = std::any_of( get_constructions().begin(),
        get_constructions().end(), [this]( const construction &con ) {
            return con.on_display && construction_is_catalog_action( con ) && con.category == category;
        } );
        if( !category_has_catalog ) {
            category = construction_category_ALL;
            uistate.construction_tab = category;
        }
    }
    std::set<construction_group_str_id> seen;
    std::map<construction_group_str_id, bool> currently_available;
    for( const construction &con : get_constructions() ) {
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''        const std::vector<construction *> variants = constructions_by_group( con.group );
        const construction &representative = *variants.front();
        const std::string category_name = representative.category.is_valid() ?
''',
    '''        const std::vector<construction *> variants = constructions_by_group( con.group );
        const auto representative_it = std::find_if( variants.begin(), variants.end(),
        []( const construction *candidate ) {
            return candidate != nullptr && construction_is_catalog_action( *candidate );
        } );
        if( representative_it == variants.end() ) {
            continue;
        }
        const construction &representative = **representative_it;
        const std::string category_name = representative.category.is_valid() ?
'''
)

# Keep inspector scroll/content state coherent in early-return inspect paths.
replace_once(
    "src/construction_ui.cpp",
    '''        add( operation == construction_operation::remove ?
             _( "Select a world tile to inspect its removal action." ) :
             inspect_mode ?
             _( "Select a tile to inspect contextual work such as repairs, or choose a build result from the catalog." ) :
             _( "Hover or select a world tile." ) );
        inspector.model().scroll_to_start();
        return;
''',
    '''        add( operation == construction_operation::remove ?
             _( "Select a world tile to inspect its removal action." ) :
             inspect_mode ?
             _( "Select a tile to inspect contextual work such as repairs, or choose a build result from the catalog." ) :
             _( "Hover or select a world tile." ) );
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    const construction *con = resolved_construction();
    if( con == nullptr ) {
        inspector.model().scroll_to_start();
        return;
    }
''',
    '''    const construction *con = resolved_construction();
    if( con == nullptr ) {
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
    }
'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Give contextual construction actions stable identities [skip ci]\n"
)
