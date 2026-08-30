from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


# Put player-facing presentation intent on the construction definition itself.
# This keeps construction_target as a resolver rather than a catalog-name/category oracle.
replace_once(
    "src/construction.h",
    '''enum class construction_action : int {
    build,
    remove,
    remove_generic
};
''',
    '''enum class construction_action : int {
    build,
    remove,
    remove_generic
};

/**
 * Player-facing presentation intent for a construction definition.
 *
 * This does not change simulation behavior.  It tells map-centric construction
 * UIs whether a definition is a catalog result or a contextual world action.
 * Optional JSON \"ui_intent\" values use these semantics; legacy data is inferred
 * during loading so mods do not need an immediate migration.
 */
enum class construction_ui_intent : int {
    build,
    repair,
    modify,
    upgrade,
    terrain_work,
    decorate,
    marker,
    remove
};
'''
)

replace_once(
    "src/construction.h",
    '''        construction_group_str_id group;
        construction_action action = construction_action::build;
        // Additional note displayed along with construction requirements.
''',
    '''        construction_group_str_id group;
        construction_action action = construction_action::build;
        construction_ui_intent ui_intent = construction_ui_intent::build;
        // Additional note displayed along with construction requirements.
'''
)

# construction_target consumes the definition-level semantic instead of defining its own copy.
replace_once(
    "src/construction_target.h",
    '''#include "coords_fwd.h"
#include "type_id.h"

class Character;
class read_only_visitable;
struct construction;
''',
    '''#include "construction.h"
#include "coords_fwd.h"
#include "type_id.h"

class Character;
class read_only_visitable;
'''
)

replace_once(
    "src/construction_target.h",
    '''/**
 * Player-facing intent for a construction definition.  The construction JSON
 * remains the simulation source of truth; this layer only decides how a
 * definition should be exposed by map-centric construction UIs.
 *
 * Only repair is contextualized in the first demo.  The remaining values make
 * the resolver extensible without teaching construction_ui about recipe names.
 */
enum class construction_ui_intent : int {
    build,
    repair,
    modify,
    upgrade,
    terrain_work,
    decorate,
    marker,
    remove
};

''',
    ''''''
)

# Load optional data-driven presentation semantics.  Legacy repair/remove behavior is inferred.
replace_once(
    "src/construction.cpp",
    '''    if( operation == "build" ) {
        con.action = construction_action::build;
    } else if( operation == "remove" ) {
        con.action = construction_action::remove;
    } else if( operation == "remove_generic" ) {
        con.action = construction_action::remove_generic;
    } else {
        jo.throw_error_at( "operation",
                           string_format( "Invalid construction operation %s", operation ) );
    }
    if( jo.has_string( "time" ) ) {
''',
    '''    if( operation == "build" ) {
        con.action = construction_action::build;
    } else if( operation == "remove" ) {
        con.action = construction_action::remove;
    } else if( operation == "remove_generic" ) {
        con.action = construction_action::remove_generic;
    } else {
        jo.throw_error_at( "operation",
                           string_format( "Invalid construction operation %s", operation ) );
    }

    const std::string ui_intent = jo.get_string( "ui_intent", "" );
    if( ui_intent.empty() ) {
        if( con.action != construction_action::build ) {
            con.ui_intent = construction_ui_intent::remove;
        } else if( con.category == construction_category_REPAIR ) {
            con.ui_intent = construction_ui_intent::repair;
        } else {
            con.ui_intent = construction_ui_intent::build;
        }
    } else if( ui_intent == "build" ) {
        con.ui_intent = construction_ui_intent::build;
    } else if( ui_intent == "repair" ) {
        con.ui_intent = construction_ui_intent::repair;
    } else if( ui_intent == "modify" ) {
        con.ui_intent = construction_ui_intent::modify;
    } else if( ui_intent == "upgrade" ) {
        con.ui_intent = construction_ui_intent::upgrade;
    } else if( ui_intent == "terrain_work" ) {
        con.ui_intent = construction_ui_intent::terrain_work;
    } else if( ui_intent == "decorate" ) {
        con.ui_intent = construction_ui_intent::decorate;
    } else if( ui_intent == "marker" ) {
        con.ui_intent = construction_ui_intent::marker;
    } else if( ui_intent == "remove" ) {
        con.ui_intent = construction_ui_intent::remove;
    } else {
        jo.throw_error_at( "ui_intent",
                           string_format( "Invalid construction ui_intent %s", ui_intent ) );
    }
    if( con.action != construction_action::build &&
        con.ui_intent != construction_ui_intent::remove ) {
        jo.throw_error_at( "ui_intent",
                           "Removal constructions must use ui_intent remove" );
    }
    if( con.action == construction_action::build &&
        con.ui_intent == construction_ui_intent::remove ) {
        jo.throw_error_at( "ui_intent",
                           "Build constructions cannot use ui_intent remove" );
    }
    if( jo.has_string( "time" ) ) {
'''
)

# Generalize contextual resolution so future data can opt into more intents without UI changes.
replace_once(
    "src/construction_target.cpp",
    '''#include <algorithm>
#include <optional>
''',
    '''#include <algorithm>
#include <array>
#include <optional>
'''
)

replace_once(
    "src/construction_target.cpp",
    '''static const trait_id trait_DEBUG_HS( "DEBUG_HS" );
static const construction_category_id construction_category_REPAIR( "REPAIR" );

bool construction_is_remove_action( const construction &con )
''',
    '''static const trait_id trait_DEBUG_HS( "DEBUG_HS" );

bool construction_is_remove_action( const construction &con )
'''
)

replace_once(
    "src/construction_target.cpp",
    '''construction_ui_intent construction_ui_intent_for( const construction &con )
{
    if( construction_is_remove_action( con ) ) {
        return construction_ui_intent::remove;
    }
    if( con.category == construction_category_REPAIR ) {
        return construction_ui_intent::repair;
    }
    return construction_ui_intent::build;
}
''',
    '''construction_ui_intent construction_ui_intent_for( const construction &con )
{
    return con.ui_intent;
}
'''
)

replace_once(
    "src/construction_target.cpp",
    '''std::vector<construction_context_action> resolve_context_construction_actions(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target )
{
    std::vector<construction_context_action> result;
    if( common_target_rejection( who, target, false ) ) {
        return result;
    }

    // Context actions are resolved by player intent, not by construction group.
    // Adding Modify/Upgrade/Terrain Work later only requires another intent
    // bucket here; construction_ui consumes the same generic result structure.
    std::vector<const construction *> repair_candidates;
    for( const construction &con : get_constructions() ) {
        if( construction_ui_intent_for( con ) == construction_ui_intent::repair ) {
            repair_candidates.push_back( &con );
        }
    }

    const construction_target_resolution repair = resolve_candidates(
                who, inventory, repair_candidates, target,
                _( "Ready to repair." ),
                _( "This tile has no applicable repair action." ) );
    if( repair.has_construction() ) {
        result.push_back( construction_context_action{ construction_ui_intent::repair, repair } );
    }
    return result;
}
''',
    '''std::vector<construction_context_action> resolve_context_construction_actions(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target )
{
    std::vector<construction_context_action> result;
    if( common_target_rejection( who, target, false ) ) {
        return result;
    }

    const std::array<construction_ui_intent, 6> contextual_intents = {
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
    return result;
}
'''
)

# Unarmed Build mode is now a real inspect/work state rather than an error state.
replace_once(
    "src/construction_ui.cpp",
    '''    if( !target ) {
        resolution = construction_target_resolution();
    } else if( operation == construction_operation::remove ) {
        resolution = resolve_remove_target( you, you.crafting_inventory(), *target );
    } else {
        resolution = resolve_construction_target( you, you.crafting_inventory(), selected_group,
            *target );
    }
''',
    '''    if( !target || ( operation == construction_operation::build && selected_group.is_null() ) ) {
        resolution = construction_target_resolution();
    } else if( operation == construction_operation::remove ) {
        resolution = resolve_remove_target( you, you.crafting_inventory(), *target );
    } else {
        resolution = resolve_construction_target( you, you.crafting_inventory(), selected_group,
            *target );
    }
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    if( operation == construction_operation::build && selected_group.is_null() ) {
        add( colorize( _( "Select a construction" ), c_light_green ) );
        blank();
        add( _( "Choose the desired result from the palette, then inspect a tile in the world viewport." ) );
        inspector.model().scroll_to_start();
        return;
    }

    add( colorize( operation == construction_operation::remove ? _( "Remove" ) :
                   selected_group->name(), c_light_green ) );
    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        blank();
        add( colorize( _( "Target" ), c_light_gray ) );
        add( operation == construction_operation::remove ?
             _( "Select a world tile to inspect its removal action." ) :
             _( "Hover or select a world tile." ) );
        inspector.model().scroll_to_start();
        return;
    }
''',
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();
    add( colorize( operation == construction_operation::remove ? _( "Remove" ) :
                   inspect_mode ? _( "Inspect & work" ) : selected_group->name(), c_light_green ) );
    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        blank();
        add( colorize( _( "Target" ), c_light_gray ) );
        add( operation == construction_operation::remove ?
             _( "Select a world tile to inspect its removal action." ) :
             inspect_mode ?
             _( "Select a tile to inspect contextual work such as repairs, or choose a build result from the catalog." ) :
             _( "Hover or select a world tile." ) );
        inspector.model().scroll_to_start();
        return;
    }
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    if( operation == construction_operation::build && !context_actions.empty() ) {
        blank();
        add( colorize( _( "Tile actions" ), c_light_gray ) );
        for( const construction_context_action &action : context_actions ) {
            const nc_color action_color = action.resolution.ready() ? c_light_green : c_yellow;
            add( colorize( string_format( _( "%s  •  %s" ),
                                          contextual_action_label( action.intent ),
                                          action.resolution.reason ), action_color ) );
        }
    }

    const nc_color status_color = resolution.status == construction_target_status::ready ?
''',
    '''    if( operation == construction_operation::build && !context_actions.empty() ) {
        blank();
        add( colorize( _( "Tile actions" ), c_light_gray ) );
        for( const construction_context_action &action : context_actions ) {
            const nc_color action_color = action.resolution.ready() ? c_light_green : c_yellow;
            add( colorize( string_format( _( "%s  •  %s" ),
                                          contextual_action_label( action.intent ),
                                          action.resolution.reason ), action_color ) );
        }
    }
    if( inspect_mode ) {
        if( context_actions.empty() ) {
            blank();
            add( colorize( _( "No construction work is available for this tile." ), c_dark_gray ) );
        }
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
    }

    const nc_color status_color = resolution.status == construction_target_status::ready ?
'''
)

# The bottom action no longer pretends an unarmed inspection target can be built.
replace_once(
    "src/construction_ui.cpp",
    '''    ui_action_entry build( _( "Select a target" ), "APPLY", false, false,
                           operation == construction_operation::remove ?
                           _( "Select a world tile first." ) :
                           _( "Select a construction and a world tile first." ) );
    if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
        if( !selected_target ) {
''',
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();
    ui_action_entry build( inspect_mode ? _( "Choose a build result" ) : _( "Select a target" ),
                           "APPLY", false, false,
                           operation == construction_operation::remove ?
                           _( "Select a world tile first." ) :
                           inspect_mode ? _( "Choose a result from the catalog to place new construction." ) :
                           _( "Select a construction and a world tile first." ) );
    if( !inspect_mode ) {
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            if( !selected_target ) {
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''            build.enabled = resolution.ready();
            build.disabled_reason = resolution.reason;
        }
    }
    if( show_context_actions ) {
''',
    '''                build.enabled = resolution.ready();
                build.disabled_reason = resolution.reason;
            }
        }
    }
    if( show_context_actions ) {
'''
)

# In inspect mode, map selection is neutral rather than a red invalid-build marker.
replace_once(
    "src/construction_ui.cpp",
    '''    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        return;
    }
    const construction *con = resolved_construction();
''',
    '''    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        return;
    }
    if( operation == construction_operation::build && selected_group.is_null() ) {
        viewport.draw_map_highlight( *target );
        if( !context_actions.empty() ) {
            viewport.draw_map_marker( *target, "•", c_light_cyan );
        }
        if( selected_target ) {
            viewport.draw_map_cursor( *selected_target );
        }
        return;
    }
    const construction *con = resolved_construction();
'''
)

# Context menus omit the meaningless disabled Build-here row when no result is armed.
replace_once(
    "src/construction_ui.cpp",
    '''    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" ),
        ui_dropdown_entry( build_label, "APPLY", buildable, false, build_reason ),
        ui_dropdown_entry( _( "Center view here" ), "CENTER" ),
        ui_dropdown_entry( _( "Clear selection" ), "CLEAR", selected_target.has_value() )
    };
    if( operation == construction_operation::build ) {
''',
    '''    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" )
    };
    if( operation == construction_operation::remove || !selected_group.is_null() ) {
        entries.emplace_back( build_label, "APPLY", buildable, false, build_reason );
    }
    if( operation == construction_operation::build ) {
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''        entries.insert( entries.begin() + 1, contextual_entries.begin(), contextual_entries.end() );
    }
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
''',
    '''        entries.insert( entries.begin() + 1, contextual_entries.begin(), contextual_entries.end() );
    }
    entries.emplace_back( _( "Center view here" ), "CENTER" );
    entries.emplace_back( _( "Clear selection" ), "CLEAR", selected_target.has_value() ||
                          !selected_group.is_null() );
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
'''
)

# Keyboard activation gets an explicit unarmed-state message instead of resolving NULL group.
replace_once(
    "src/construction_ui.cpp",
    '''bool construction_workspace::request_action( const tripoint_bub_ms &target )
{
    const construction_target_resolution current = operation == construction_operation::remove ?
''',
    '''bool construction_workspace::request_action( const tripoint_bub_ms &target )
{
    if( operation == construction_operation::build && selected_group.is_null() ) {
        transient_status = _( "Choose a build result from the catalog, or use an available tile action." );
        return false;
    }
    const construction_target_resolution current = operation == construction_operation::remove ?
'''
)

# Do not show now-empty contextual-only categories in the Build category dropdown.
replace_once(
    "src/construction_ui.cpp",
    '''    std::vector<ui_dropdown_entry> entries;
    entries.emplace_back( _( "All categories" ), construction_category_ALL.str(), true,
                          category == construction_category_ALL );
    for( const construction_category &candidate : construction_categories::get_all() ) {
        if( candidate.id == construction_category_ALL || candidate.id == construction_category_FILTER ) {
            continue;
        }
        entries.emplace_back( candidate.name(), candidate.id.str(), true, candidate.id == category );
    }
''',
    '''    std::set<construction_category_id> catalog_categories;
    for( const construction &con : get_constructions() ) {
        if( con.on_display && construction_is_catalog_action( con ) ) {
            catalog_categories.insert( con.category );
        }
    }
    std::vector<ui_dropdown_entry> entries;
    entries.emplace_back( _( "All categories" ), construction_category_ALL.str(), true,
                          category == construction_category_ALL );
    for( const construction_category &candidate : construction_categories::get_all() ) {
        if( candidate.id == construction_category_ALL || candidate.id == construction_category_FILTER ||
            catalog_categories.count( candidate.id ) == 0 ) {
            continue;
        }
        entries.emplace_back( candidate.name(), candidate.id.str(), true, candidate.id == category );
    }
'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Make contextual construction a first-class inspect mode [skip ci]\n"
)
