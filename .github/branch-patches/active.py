from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

# Resolve category/subcategory through the new curated group metadata.  This is
# essential for concrete recipes whose legacy JSON category is CC_*/NESTED.
text = replace_once(
    text,
    '''    const auto leaf_key = []( const std::string & category, const std::string & subcategory ) {\n        return category + "|" + subcategory;\n    };\n\n''',
    '''    const auto leaf_key = []( const std::string & category, const std::string & subcategory ) {\n        return category + "|" + subcategory;\n    };\n    const auto recipe_category_identity = []( const recipe *rec ) {\n        if( rec == nullptr ) {\n            return std::make_pair( std::string(), std::string() );\n        }\n        if( const crafting_group *group = crafting_group_for_recipe( rec->ident() ) ) {\n            return std::make_pair( group->category.str(), group->subcategory );\n        }\n        return std::make_pair( rec->category.str(), rec->subcategory );\n    };\n\n''',
    "recipe category identity",
)

text = replace_once(
    text,
    '''    state.scope = static_cast<crafting_scope>( std::clamp( uistate.crafting_browser_scope, 0,\n                  static_cast<int>( crafting_scope::nested ) ) );\n    state.sort = static_cast<crafting_sort>( std::clamp( uistate.crafting_browser_sort, 0,\n''',
    '''    state.scope = static_cast<crafting_scope>( std::clamp( uistate.crafting_browser_scope, 0,\n                  static_cast<int>( crafting_scope::nested ) ) );\n    // Nested-category pseudo-recipes are a legacy presentation mechanism.\n    // The modern browser renders crafting_group metadata as section headings instead.\n    if( state.scope == crafting_scope::nested ) {\n        state.scope = crafting_scope::all;\n    }\n    state.sort = static_cast<crafting_sort>( std::clamp( uistate.crafting_browser_sort, 0,\n''',
    "legacy nested scope migration",
)

text = replace_once(
    text,
    '''            } else if( old_subcategory == "CSC_*_NESTED" ) {\n                state.scope = crafting_scope::nested;\n            }\n''',
    '''            } else if( old_subcategory == "CSC_*_NESTED" ) {\n                state.scope = crafting_scope::all;\n            }\n''',
    "legacy nested persisted state",
)

# Use group metadata for goto-category restoration as well, otherwise recipes
# authored under CC_* cannot select their visible modern category.
text = replace_once(
    text,
    '''        state.category_selection.clear();\n        const auto found = category_leaf_keys.find( goto_recipe->category.str() );\n        if( found != category_leaf_keys.end() ) {\n            for( const std::string &key : found->second ) {\n                state.category_selection.set( key, true );\n            }\n        }\n''',
    '''        state.category_selection.clear();\n        const auto identity = recipe_category_identity( &goto_recipe.obj() );\n        const std::string exact_key = leaf_key( identity.first, identity.second );\n        if( state.category_selection.supports( exact_key ) ) {\n            state.category_selection.set( exact_key, true );\n        } else {\n            const auto found = category_leaf_keys.find( identity.first );\n            if( found != category_leaf_keys.end() ) {\n                for( const std::string &key : found->second ) {\n                    state.category_selection.set( key, true );\n                }\n            }\n        }\n''',
    "goto recipe category restore",
)

text = replace_once(
    text,
    '''    std::vector<const recipe *> current;\n    std::vector<int> indent;\n''',
    '''    struct browser_list_row {\n        const recipe *rec = nullptr;\n        const crafting_group *group = nullptr;\n        int recipe_index = -1;\n        std::string heading;\n    };\n\n    std::vector<const recipe *> current;\n    std::vector<browser_list_row> recipe_rows;\n    std::vector<int> indent;\n''',
    "browser section row model",
)

text = replace_once(
    text,
    '''    const auto selected_index = [&]() -> int {\n        if( state.selected_recipe == nullptr ) {\n            return -1;\n        }\n        const auto found = std::find( current.begin(), current.end(), state.selected_recipe );\n        return found == current.end() ? -1 : static_cast<int>( found - current.begin() );\n    };\n\n''',
    '''    const auto selected_index = [&]() -> int {\n        if( state.selected_recipe == nullptr ) {\n            return -1;\n        }\n        const auto found = std::find( current.begin(), current.end(), state.selected_recipe );\n        return found == current.end() ? -1 : static_cast<int>( found - current.begin() );\n    };\n\n    const auto selected_row_index = [&]() -> int {\n        if( state.selected_recipe == nullptr ) {\n            return -1;\n        }\n        const auto found = std::find_if( recipe_rows.begin(), recipe_rows.end(),\n        [&]( const browser_list_row & row ) {\n            return row.rec == state.selected_recipe;\n        } );\n        return found == recipe_rows.end() ? -1 : static_cast<int>( found - recipe_rows.begin() );\n    };\n\n''',
    "selected visual row lookup",
)

# Keep the shared scroll model in visual-row space, not recipe-vector space.
text = replace_once(
    text,
    '''        if( mark_read && highlight_unread_recipes ) {\n            if( previous != nullptr ) {\n                uistate.read_recipes.insert( previous->ident() );\n            }\n            uistate.read_recipes.insert( state.selected_recipe->ident() );\n            recalc_unread = true;\n        }\n    };\n\n    const auto selected_availability = [&]() -> availability * {\n''',
    '''        if( mark_read && highlight_unread_recipes ) {\n            if( previous != nullptr ) {\n                uistate.read_recipes.insert( previous->ident() );\n            }\n            uistate.read_recipes.insert( state.selected_recipe->ident() );\n            recalc_unread = true;\n        }\n        const int row = selected_row_index();\n        if( row >= 0 ) {\n            state.recipe_scroll.ensure_visible( row );\n        }\n    };\n\n    const auto select_row = [&]( int requested, const int direction, const bool mark_read ) {\n        if( recipe_rows.empty() ) {\n            state.selected_recipe = nullptr;\n            return;\n        }\n        requested = std::clamp( requested, 0, static_cast<int>( recipe_rows.size() ) - 1 );\n        while( requested >= 0 && requested < static_cast<int>( recipe_rows.size() ) ) {\n            if( recipe_rows[requested].rec != nullptr ) {\n                select_index( recipe_rows[requested].recipe_index, mark_read );\n                return;\n            }\n            requested += direction;\n        }\n    };\n\n    const auto selected_availability = [&]() -> availability * {\n''',
    "visual row selection",
)

text = replace_once(
    text,
    '''    const auto recipe_matches_categories = [&]( const recipe * rec ) {\n        return rec != nullptr && state.category_selection.contains(\n                   leaf_key( rec->category.str(), rec->subcategory ) );\n    };\n''',
    '''    const auto recipe_matches_categories = [&]( const recipe * rec ) {\n        if( rec == nullptr ) {\n            return false;\n        }\n        const auto identity = recipe_category_identity( rec );\n        return state.category_selection.contains( leaf_key( identity.first, identity.second ) );\n    };\n''',
    "group-backed category matching",
)

text = replace_once(
    text,
    '''            case crafting_scope::nested:\n                return _( "View: Nested" );\n            case crafting_scope::all:\n''',
    '''            case crafting_scope::nested:\n            case crafting_scope::all:\n''',
    "scope summary nested removal",
)

text = replace_once(
    text,
    '''                    { _( "Hidden" ), "SCOPE_3", true, state.scope == crafting_scope::hidden },\n                    { _( "Nested groups" ), "SCOPE_4", true, state.scope == crafting_scope::nested }\n''',
    '''                    { _( "Hidden" ), "SCOPE_3", true, state.scope == crafting_scope::hidden }\n''',
    "view dropdown nested removal",
)

text = replace_once(
    text,
    '''        current.clear();\n        available.clear();\n        indent.clear();\n''',
    '''        current.clear();\n        recipe_rows.clear();\n        available.clear();\n        indent.clear();\n''',
    "clear section rows",
)

text = replace_once(
    text,
    '''            if( rec == nullptr || !recipe_matches_categories( rec ) ) {\n                return true;\n            }\n''',
    '''            if( rec == nullptr || rec->is_nested() || !recipe_matches_categories( rec ) ) {\n                return true;\n            }\n''',
    "remove legacy nested pseudo recipes",
)

text = replace_once(
    text,
    '''                case crafting_scope::nested:\n                    return !rec->is_nested();\n                case crafting_scope::all:\n''',
    '''                case crafting_scope::nested:\n                case crafting_scope::all:\n''',
    "nested scope candidate behavior",
)

text = replace_once(
    text,
    '''        indent.assign( candidates.size(), 0 );\n        expand_recipes( candidates, indent, *availability_cache, *crafter,\n                        state.sort == crafting_sort::unread,\n                        highlight_unread_recipes, available_recipes, uistate.hidden_recipes,\n                        camp_crafting, inventory_override );\n        const std::vector<int> candidate_indent = indent;\n''',
    '''        // The modern list displays concrete recipes directly beneath metadata-backed\n        // section headings; legacy nested recipe expansion is intentionally bypassed.\n        indent.assign( candidates.size(), 0 );\n        const std::vector<int> candidate_indent = indent;\n''',
    "disable nested expansion in modern browser",
)

# Build visual rows after filtering.  Existing sort order is preserved within a
# group; group order is metadata-controlled.  Mod recipes without metadata get
# a deterministic per-subcategory fallback heading rather than disappearing.
text = replace_once(
    text,
    '''        available.reserve( current.size() );\n        for( const recipe *rec : current ) {\n            available.push_back( availability_cache->at( rec ) );\n        }\n\n        const auto preserved = std::find( current.begin(), current.end(), previous_recipe );\n''',
    '''        available.reserve( current.size() );\n        for( const recipe *rec : current ) {\n            available.push_back( availability_cache->at( rec ) );\n        }\n\n        std::map<const crafting_group *, std::vector<int>> grouped_recipe_indices;\n        std::map<std::pair<std::string, std::string>, std::vector<int>> ungrouped_recipe_indices;\n        for( int i = 0; i < static_cast<int>( current.size() ); ++i ) {\n            if( const crafting_group *group = crafting_group_for_recipe( current[i]->ident() ) ) {\n                grouped_recipe_indices[group].push_back( i );\n            } else {\n                ungrouped_recipe_indices[recipe_category_identity( current[i] )].push_back( i );\n            }\n        }\n\n        std::vector<const crafting_group *> visible_groups;\n        for( const crafting_group &group : all_crafting_groups() ) {\n            if( grouped_recipe_indices.count( &group ) > 0 ) {\n                visible_groups.push_back( &group );\n            }\n        }\n        const auto category_rank = [&]( const crafting_group *group ) {\n            const auto found = std::find( crafting_categories.begin(), crafting_categories.end(),\n                                          group->category.str() );\n            return found == crafting_categories.end() ? static_cast<int>( crafting_categories.size() ) :\n                   static_cast<int>( found - crafting_categories.begin() );\n        };\n        std::stable_sort( visible_groups.begin(), visible_groups.end(),\n        [&]( const crafting_group * a, const crafting_group * b ) {\n            const int a_category = category_rank( a );\n            const int b_category = category_rank( b );\n            if( a_category != b_category ) {\n                return a_category < b_category;\n            }\n            if( a->order != b->order ) {\n                return a->order < b->order;\n            }\n            return localized_compare( a->name.translated(), b->name.translated() );\n        } );\n\n        for( const crafting_group *group : visible_groups ) {\n            recipe_rows.push_back( { nullptr, group, -1, group->name.translated() } );\n            for( const int recipe_index : grouped_recipe_indices[group] ) {\n                recipe_rows.push_back( { current[recipe_index], group, recipe_index, std::string() } );\n            }\n        }\n        for( const auto &entry : ungrouped_recipe_indices ) {\n            const std::string heading = string_format( _( "%s — other recipes" ),\n                                        _( get_subcat_unprefixed( entry.first.first, entry.first.second ) ) );\n            recipe_rows.push_back( { nullptr, nullptr, -1, heading } );\n            for( const int recipe_index : entry.second ) {\n                recipe_rows.push_back( { current[recipe_index], nullptr, recipe_index, std::string() } );\n            }\n        }\n\n        const auto preserved = std::find( current.begin(), current.end(), previous_recipe );\n''',
    "build metadata section rows",
)

text = replace_once(
    text,
    '''        const int index = selected_index();\n        const int visible = w_recipes ? std::max( 1, getmaxy( w_recipes ) - 3 ) :\n                            std::max( 1, body_height - 3 );\n        state.recipe_scroll.set_content_size( static_cast<int>( current.size() ) )\n        .set_viewport_size( visible );\n        if( index >= 0 ) {\n            state.recipe_scroll.ensure_visible( index );\n''',
    '''        const int row_index = selected_row_index();\n        const int visible = w_recipes ? std::max( 1, getmaxy( w_recipes ) - 3 ) :\n                            std::max( 1, body_height - 3 );\n        state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )\n        .set_viewport_size( visible );\n        if( row_index >= 0 ) {\n            state.recipe_scroll.ensure_visible( row_index );\n''',
    "rebuild visual scroll extent",
)

# Unread category badges must also resolve wildcard recipes through group metadata.
old_unread = '''    const auto update_unread_maps = [&]() {\n        if( !highlight_unread_recipes ) {\n            return;\n        }\n        for( const std::string &category : crafting_categories ) {\n            is_cat_unread[category] = false;\n            for( const std::string &subcategory :\n                 crafting_category_id( category )->subcategories ) {\n                is_subcat_unread[category][subcategory] = false;\n                const auto result = recipes_from_cat( available_recipes,\n                                    crafting_category_id( category ), subcategory );\n                for( const recipe *rec : result.first ) {\n                    if( !result.second && uistate.hidden_recipes.count( rec->ident() ) ) {\n                        continue;\n                    }\n                    if( !uistate.read_recipes.count( rec->ident() ) ) {\n                        is_cat_unread[category] = true;\n                        is_subcat_unread[category][subcategory] = true;\n                        break;\n                    }\n                }\n            }\n        }\n    };\n'''
new_unread = '''    const auto update_unread_maps = [&]() {\n        if( !highlight_unread_recipes ) {\n            return;\n        }\n        for( const std::string &category : crafting_categories ) {\n            is_cat_unread[category] = false;\n            for( const std::string &subcategory : crafting_category_id( category )->subcategories ) {\n                is_subcat_unread[category][subcategory] = false;\n            }\n        }\n        for( const recipe *rec : available_recipes ) {\n            if( rec == nullptr || rec->is_nested() || uistate.hidden_recipes.count( rec->ident() ) ||\n                uistate.read_recipes.count( rec->ident() ) ) {\n                continue;\n            }\n            const auto identity = recipe_category_identity( rec );\n            if( is_cat_unread.count( identity.first ) > 0 ) {\n                is_cat_unread[identity.first] = true;\n                is_subcat_unread[identity.first][identity.second] = true;\n            }\n        }\n    };\n'''
text = replace_once(text, old_unread, new_unread, "group-backed unread badges")

# Draw section headers as inert rows and concrete recipes as the only hit targets.
text = replace_once(
    text,
    '''            state.recipe_scroll.set_content_size( static_cast<int>( current.size() ) )\n            .set_viewport_size( visible );\n''',
    '''            state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )\n            .set_viewport_size( visible );\n''',
    "redraw visual scroll extent",
)

text = replace_once(
    text,
    '''                if( index >= static_cast<int>( current.size() ) ) {\n                    break;\n                }\n                const recipe *rec = current[index];\n                const bool selected = rec == state.selected_recipe;\n                const bool hovered = rec == state.hovered_recipe;\n                nc_color color = available[index].color();\n                if( selected ) {\n                    color = available[index].selected_color();\n''',
    '''                if( index >= static_cast<int>( recipe_rows.size() ) ) {\n                    break;\n                }\n                const browser_list_row &list_row = recipe_rows[index];\n                if( list_row.rec == nullptr ) {\n                    const int y = first_row + row;\n                    trim_and_print( w_recipes, point( 1, y ), std::max( 1, list_width - 2 ),\n                                    c_light_cyan, list_row.heading );\n                    const int rule_x = std::min( list_width - 1, 2 + utf8_width( list_row.heading ) );\n                    for( int x = rule_x; x < list_width - 1; ++x ) {\n                        mvwputch( w_recipes, point( x, y ), c_dark_gray, LINE_OXOX );\n                    }\n                    continue;\n                }\n                const int recipe_index = list_row.recipe_index;\n                const recipe *rec = list_row.rec;\n                const bool selected = rec == state.selected_recipe;\n                const bool hovered = rec == state.hovered_recipe;\n                nc_color color = available[recipe_index].color();\n                if( selected ) {\n                    color = available[recipe_index].selected_color();\n''',
    "draw section header rows",
)

text = replace_once(
    text,
    '''                if( rec->is_nested() ) {\n                    prefix += uistate.expanded_recipes.count( rec->ident() ) ? "[-] " : "[+] ";\n                }\n                std::string name = prefix + std::string( index < static_cast<int>( indent.size() ) ?\n                                   indent[index] : 0, ' ' ) + rec->result_name( /*decorated=*/true );\n''',
    '''                std::string name = prefix + rec->result_name( /*decorated=*/true );\n''',
    "remove nested list affordance",
)

text = replace_once(
    text,
    '''                                 point( list_width - 2, y ) ), index );\n''',
    '''                                 point( list_width - 2, y ) ), recipe_index );\n''',
    "recipe hit maps to recipe index",
)

text = replace_once(
    text,
    '''            if( static_cast<int>( current.size() ) > visible ) {\n''',
    '''            if( static_cast<int>( recipe_rows.size() ) > visible ) {\n''',
    "section-aware scrollbar visibility",
)

# Headers are intentionally non-hoverable; clear stale hover when pointer is over one.
text = replace_once(
    text,
    '''            if( ( !compact_layout || state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {\n                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit && *hit >= 0 && *hit < static_cast<int>( current.size() ) ) {\n                    state.hovered_recipe = current[*hit];\n                }\n            }\n''',
    '''            if( ( !compact_layout || state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {\n                state.hovered_recipe = nullptr;\n                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );\n                if( hit && *hit >= 0 && *hit < static_cast<int>( current.size() ) ) {\n                    state.hovered_recipe = current[*hit];\n                }\n            }\n''',
    "clear hover on section headings",
)

# Keyboard navigation follows visual rows and skips inert section headings.
old_nav = '''        const int index = selected_index();\n        const int visible_recipes = std::max( 1, getmaxy( w_recipes ) - 3 );\n        if( action == "DOWN" && !current.empty() ) {\n            select_index( ( index < 0 ? 0 : index + 1 ) % current.size(), true );\n        } else if( action == "UP" && !current.empty() ) {\n            select_index( index <= 0 ? static_cast<int>( current.size() ) - 1 : index - 1, true );\n        } else if( action == "PAGE_DOWN" && !current.empty() ) {\n            select_index( std::min( static_cast<int>( current.size() ) - 1,\n                                    std::max( 0, index ) + visible_recipes ), true );\n        } else if( action == "PAGE_UP" && !current.empty() ) {\n            select_index( std::max( 0, std::max( 0, index ) - visible_recipes ), true );\n        } else if( action == "HOME" && !current.empty() ) {\n            select_index( 0, true );\n        } else if( action == "END" && !current.empty() ) {\n            select_index( static_cast<int>( current.size() ) - 1, true );\n'''
new_nav = '''        const int index = selected_index();\n        const int row_index = selected_row_index();\n        const int visible_recipes = std::max( 1, getmaxy( w_recipes ) - 3 );\n        if( action == "DOWN" && !current.empty() ) {\n            if( row_index < 0 || row_index >= static_cast<int>( recipe_rows.size() ) - 1 ) {\n                select_row( 0, 1, true );\n            } else {\n                select_row( row_index + 1, 1, true );\n            }\n        } else if( action == "UP" && !current.empty() ) {\n            if( row_index <= 0 ) {\n                select_row( static_cast<int>( recipe_rows.size() ) - 1, -1, true );\n            } else {\n                select_row( row_index - 1, -1, true );\n            }\n        } else if( action == "PAGE_DOWN" && !current.empty() ) {\n            select_row( std::min( static_cast<int>( recipe_rows.size() ) - 1,\n                                  std::max( 0, row_index ) + visible_recipes ), 1, true );\n        } else if( action == "PAGE_UP" && !current.empty() ) {\n            select_row( std::max( 0, std::max( 0, row_index ) - visible_recipes ), -1, true );\n        } else if( action == "HOME" && !current.empty() ) {\n            select_row( 0, 1, true );\n        } else if( action == "END" && !current.empty() ) {\n            select_row( static_cast<int>( recipe_rows.size() ) - 1, -1, true );\n'''
text = replace_once(text, old_nav, new_nav, "section-aware keyboard navigation")

# `index` is still used by category-tab navigation below this block, so keep it
# deliberately even though recipe movement now uses row_index.

path.write_text(text, encoding="utf-8")

# Lightweight metadata audit: the browser must never depend on duplicate group
# ownership, empty headings, or empty recipe lists.
import json
seen_groups: set[str] = set()
seen_recipes: dict[str, str] = {}
for group_file in sorted(Path("data/json/recipes/crafting_groups").glob("*.json")):
    groups = json.loads(group_file.read_text(encoding="utf-8"))
    for group in groups:
        gid = group["id"]
        if gid in seen_groups:
            raise SystemExit(f"duplicate crafting group id: {gid}")
        seen_groups.add(gid)
        if not group.get("name") or not group.get("recipes"):
            raise SystemExit(f"empty crafting group metadata: {gid}")
        for recipe_id in group["recipes"]:
            if recipe_id in seen_recipes:
                raise SystemExit(
                    f"recipe {recipe_id} belongs to both {seen_recipes[recipe_id]} and {gid}"
                )
            seen_recipes[recipe_id] = gid
print(f"crafting browser group audit: {len(seen_groups)} groups / {len(seen_recipes)} unique recipes")

Path("/tmp/branch_patch_commit_message").write_text(
    "Render crafting groups as recipe section headings\n", encoding="utf-8"
)
