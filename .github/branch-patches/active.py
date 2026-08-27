from pathlib import Path
import re


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_span(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{label}: start marker missing")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"{label}: end marker missing")
    return text[:start] + replacement + text[end:]


# Persist multi-category selection, View and Sort as normal UI state.
uistate_path = "src/uistate.h"
uistate = read(uistate_path)
uistate = replace_once(
    uistate,
    '''        std::string crafting_browser_category;
        std::string crafting_browser_subcategory;
        recipe_id crafting_browser_recipe = recipe_id::NULL_ID();
''',
    '''        std::string crafting_browser_category;
        std::string crafting_browser_subcategory;
        std::vector<std::string> crafting_browser_category_filters;
        int crafting_browser_scope = 0;
        int crafting_browser_sort = 0;
        recipe_id crafting_browser_recipe = recipe_id::NULL_ID();
''',
    "uistate crafting browser fields",
)
write(uistate_path, uistate)

inv_path = "src/inventory_ui.cpp"
inv = read(inv_path)
inv = replace_once(
    inv,
    '''    json.member( "crafting_browser_category", crafting_browser_category );
    json.member( "crafting_browser_subcategory", crafting_browser_subcategory );
    json.member( "crafting_browser_recipe", crafting_browser_recipe );
''',
    '''    json.member( "crafting_browser_category", crafting_browser_category );
    json.member( "crafting_browser_subcategory", crafting_browser_subcategory );
    json.member( "crafting_browser_category_filters", crafting_browser_category_filters );
    json.member( "crafting_browser_scope", crafting_browser_scope );
    json.member( "crafting_browser_sort", crafting_browser_sort );
    json.member( "crafting_browser_recipe", crafting_browser_recipe );
''',
    "serialize crafting browser tree state",
)
inv = replace_once(
    inv,
    '''    jo.read( "crafting_browser_category", crafting_browser_category );
    jo.read( "crafting_browser_subcategory", crafting_browser_subcategory );
    jo.read( "crafting_browser_recipe", crafting_browser_recipe );
''',
    '''    jo.read( "crafting_browser_category", crafting_browser_category );
    jo.read( "crafting_browser_subcategory", crafting_browser_subcategory );
    jo.read( "crafting_browser_category_filters", crafting_browser_category_filters );
    jo.read( "crafting_browser_scope", crafting_browser_scope );
    jo.read( "crafting_browser_sort", crafting_browser_sort );
    jo.read( "crafting_browser_recipe", crafting_browser_recipe );
''',
    "deserialize crafting browser tree state",
)
write(inv_path, inv)

craft_path = "src/crafting_gui.cpp"
craft = read(craft_path)
craft = replace_once(
    craft,
    '#include "ui_helpers/controls/dropdown.h"\n',
    '#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/controls/tree_dropdown.h"\n',
    "tree dropdown include",
)

# Browser state is declared immediately above the function, not inside it.
craft = replace_span(
    craft,
    "enum class crafting_browser_pane : int {",
    "static bool crafting_recipe_can_start",
    '''enum class crafting_browser_pane : int {
    recipes = 0,
    inspector
};

enum class crafting_filter : int {
    craftable,
    memorized,
    unread
};

enum class crafting_scope : int {
    all = 0,
    favorites,
    recent,
    hidden,
    nested
};

enum class crafting_sort : int {
    recommended = 0,
    name,
    difficulty,
    time,
    craftability,
    unread
};

struct crafting_browser_state {
    crafting_browser_state() : filters( { crafting_filter::craftable, crafting_filter::memorized,
                                          crafting_filter::unread } ) {
        filters.clear();
    }

    const recipe *selected_recipe = nullptr;
    std::string search_query;
    ui_multiselect_filter<std::string> category_selection;
    ui_multiselect_filter<crafting_filter> filters;
    crafting_scope scope = crafting_scope::all;
    crafting_sort sort = crafting_sort::recommended;
    ui_scroll_model recipe_scroll;
    ui_scroll_model inspector_scroll;
    int item_popup_scroll = 0;
    int batch_size = 1;
    crafting_browser_pane focused_pane = crafting_browser_pane::recipes;
    const recipe *hovered_recipe = nullptr;
    ui_double_click_tracker<const recipe *> recipe_clicks;
    bool context_open = false;
    point context_pos;
    std::string open_header_menu;
};

''',
    "crafting browser state",
)

fn_start = craft.find("static std::pair<Character *, const recipe *> select_crafter_and_crafting_recipe_browser(")
fn_end = craft.find("\nstd::pair<Character *, const recipe *> select_crafter_and_crafting_recipe(", fn_start)
if fn_start < 0 or fn_end < 0:
    raise SystemExit("crafting browser function bounds not found")
browser = craft[fn_start:fn_end]

browser = replace_span(
    browser,
    "    crafting_browser_state state;",
    "    const recipe_subset &available_recipes =",
    '''    crafting_browser_state state;
    state.search_query = filterstring.empty() ? uistate.crafting_browser_search : filterstring;
    state.filters.set( crafting_filter::craftable, uistate.crafting_browser_craftable_only );
    state.filters.set( crafting_filter::memorized, uistate.crafting_browser_memorized_only );
    state.filters.set( crafting_filter::unread,
                       highlight_unread_recipes && uistate.crafting_browser_unread_only );
    state.scope = static_cast<crafting_scope>( std::clamp( uistate.crafting_browser_scope, 0,
                  static_cast<int>( crafting_scope::nested ) ) );
    state.sort = static_cast<crafting_sort>( std::clamp( uistate.crafting_browser_sort, 0,
                 static_cast<int>( crafting_sort::unread ) ) );
    if( uistate.crafting_browser_unread_first &&
        uistate.crafting_browser_sort == static_cast<int>( crafting_sort::recommended ) ) {
        state.sort = crafting_sort::unread;
    }
    state.recipe_scroll.set_viewport_pos( std::max( 0, uistate.crafting_browser_recipe_scroll ) );
    state.inspector_scroll.set_viewport_pos( std::max( 0, uistate.crafting_browser_inspector_scroll ) );
    state.batch_size = std::clamp( uistate.crafting_browser_batch_size, 1, 50 );
    state.focused_pane = uistate.crafting_browser_focused_pane == 2 ?
                         crafting_browser_pane::inspector : crafting_browser_pane::recipes;

    std::vector<std::string> crafting_categories;
    std::vector<std::string> category_leaf_options;
    std::map<std::string, std::vector<std::string>> category_leaf_keys;
    std::map<std::string, std::pair<std::string, std::string>> leaf_identity;
    const auto leaf_key = []( const std::string & category, const std::string & subcategory ) {
        return category + "|" + subcategory;
    };

    for( const crafting_category &cat : craft_cat_list.get_all() ) {
        if( cat.is_hidden || cat.is_wildcard ) {
            continue;
        }
        const std::string category = cat.id.str();
        crafting_categories.push_back( category );
        for( const std::string &subcategory : cat.subcategories ) {
            if( subcategory == "CSC_ALL" ) {
                continue;
            }
            const std::string key = leaf_key( category, subcategory );
            category_leaf_options.push_back( key );
            category_leaf_keys[category].push_back( key );
            leaf_identity.emplace( key, std::make_pair( category, subcategory ) );
        }
    }
    if( crafting_categories.empty() || category_leaf_options.empty() ) {
        return { crafter, nullptr };
    }

    state.category_selection.set_options( category_leaf_options, false, false );
    bool restored_multi = false;
    for( const std::string &key : uistate.crafting_browser_category_filters ) {
        if( state.category_selection.supports( key ) ) {
            state.category_selection.set( key, true );
            restored_multi = true;
        }
    }
    if( !restored_multi ) {
        const std::string &old_category = uistate.crafting_browser_category;
        const std::string &old_subcategory = uistate.crafting_browser_subcategory;
        const auto old_category_found = category_leaf_keys.find( old_category );
        if( old_category_found != category_leaf_keys.end() ) {
            if( old_subcategory == "CSC_ALL" ) {
                for( const std::string &key : old_category_found->second ) {
                    state.category_selection.set( key, true );
                }
            } else {
                state.category_selection.set( leaf_key( old_category, old_subcategory ), true );
            }
        } else {
            state.category_selection.select_all();
            if( old_subcategory == "CSC_*_FAVORITE" ) {
                state.scope = crafting_scope::favorites;
            } else if( old_subcategory == "CSC_*_RECENT" ) {
                state.scope = crafting_scope::recent;
            } else if( old_subcategory == "CSC_*_HIDDEN" ) {
                state.scope = crafting_scope::hidden;
            } else if( old_subcategory == "CSC_*_NESTED" ) {
                state.scope = crafting_scope::nested;
            }
        }
    }
    if( state.category_selection.none_selected() && uistate.crafting_browser_category_filters.empty() ) {
        state.category_selection.select_all();
    }

''',
    "crafting startup/category leaves",
)

browser = replace_span(
    browser,
    "    if( uistate.crafting_browser_recipe.is_valid() ) {",
    "    const std::vector<Character *> crafting_group",
    '''    if( uistate.crafting_browser_recipe.is_valid() ) {
        const recipe *saved_recipe = &uistate.crafting_browser_recipe.obj();
        if( available_recipes.contains( saved_recipe ) ) {
            state.selected_recipe = saved_recipe;
        }
    }
    if( goto_recipe.is_valid() && available_recipes.contains( &goto_recipe.obj() ) ) {
        state.selected_recipe = &goto_recipe.obj();
        state.scope = uistate.hidden_recipes.count( goto_recipe ) ? crafting_scope::hidden :
                      crafting_scope::all;
        state.category_selection.clear();
        const auto found = category_leaf_keys.find( goto_recipe->category.str() );
        if( found != category_leaf_keys.end() ) {
            for( const std::string &key : found->second ) {
                state.category_selection.set( key, true );
            }
        }
    }

''',
    "selected recipe/goto restore",
)

browser = replace_span(
    browser,
    "    std::map<std::string, bool> is_cat_unread;",
    "    catacurses::window w_header;",
    '''    std::map<std::string, bool> is_cat_unread;
    std::map<std::string, std::map<std::string, bool>> is_subcat_unread;
    ui_hit_map<int> recipe_hits;
    ui_action_strip header_actions;
    ui_action_strip pane_actions;
    ui_action_strip inspector_actions;
    ui_action_strip toolbar_actions;
    ui_tree_dropdown category_menu;
    ui_dropdown header_menu;
    ui_dropdown context_menu;
    scrollbar recipe_scrollbar;
    scrollbar inspector_scrollbar;

''',
    "crafting controls",
)
browser = replace_once(
    browser,
    '''    catacurses::window w_header;
    catacurses::window w_sidebar;
    catacurses::window w_recipes;
''',
    '''    catacurses::window w_header;
    catacurses::window w_recipes;
''',
    "remove sidebar window",
)
browser = replace_once(browser, "    int header_height = 3;\n", "    int header_height = 5;\n",
                       "header height default")

browser = replace_span(
    browser,
    "    const auto persist_state = [&]() {",
    "    ui_adaptor ui( ui_adaptor::disable_uis_below{} );",
    r'''    const auto category_state = [&]( const std::string & category ) {
        const auto found = category_leaf_keys.find( category );
        if( found == category_leaf_keys.end() || found->second.empty() ) {
            return ui_tree_check_state::unchecked;
        }
        int selected = 0;
        for( const std::string &key : found->second ) {
            selected += state.category_selection.contains( key ) ? 1 : 0;
        }
        if( selected == 0 ) {
            return ui_tree_check_state::unchecked;
        }
        if( selected == static_cast<int>( found->second.size() ) ) {
            return ui_tree_check_state::checked;
        }
        return ui_tree_check_state::partial;
    };

    const auto all_category_state = [&]() {
        if( state.category_selection.none_selected() ) {
            return ui_tree_check_state::unchecked;
        }
        return state.category_selection.all_selected() ? ui_tree_check_state::checked :
               ui_tree_check_state::partial;
    };

    const auto set_category_selected = [&]( const std::string & category, const bool selected ) {
        const auto found = category_leaf_keys.find( category );
        if( found == category_leaf_keys.end() ) {
            return;
        }
        for( const std::string &key : found->second ) {
            state.category_selection.set( key, selected );
        }
    };

    const auto recipe_matches_categories = [&]( const recipe * rec ) {
        return rec != nullptr && state.category_selection.contains(
                   leaf_key( rec->category.str(), rec->subcategory ) );
    };

    const auto category_summary = [&]() {
        if( state.category_selection.all_selected() ) {
            return _( "Categories: All" );
        }
        if( state.category_selection.none_selected() ) {
            return _( "Categories: None" );
        }
        std::vector<std::string> active;
        for( const std::string &category : crafting_categories ) {
            if( category_state( category ) != ui_tree_check_state::unchecked ) {
                active.push_back( category );
            }
        }
        if( active.size() == 1 ) {
            std::string label = _( get_cat_unprefixed( active.front() ) );
            if( category_state( active.front() ) == ui_tree_check_state::partial ) {
                label += _( " (partial)" );
            }
            return string_format( _( "Category: %s" ), label );
        }
        return string_format( _( "Categories: %d" ), static_cast<int>( active.size() ) );
    };

    const auto filter_summary = [&]() {
        if( state.filters.none_selected() ) {
            return _( "Filter: All" );
        }
        if( state.filters.selected_count() == 1 ) {
            const crafting_filter selected = *state.filters.first_selected();
            if( selected == crafting_filter::craftable ) {
                return _( "Filter: Craftable" );
            }
            if( selected == crafting_filter::memorized ) {
                return _( "Filter: Memorized" );
            }
            return _( "Filter: Unread" );
        }
        return string_format( _( "Filters: %d" ), static_cast<int>( state.filters.selected_count() ) );
    };

    const auto sort_summary = [&]() {
        switch( state.sort ) {
            case crafting_sort::name:
                return _( "Sort: Name" );
            case crafting_sort::difficulty:
                return _( "Sort: Difficulty" );
            case crafting_sort::time:
                return _( "Sort: Time" );
            case crafting_sort::craftability:
                return _( "Sort: Craftability" );
            case crafting_sort::unread:
                return _( "Sort: Unread first" );
            case crafting_sort::recommended:
            default:
                return _( "Sort: Recommended" );
        }
    };

    const auto scope_summary = [&]() {
        switch( state.scope ) {
            case crafting_scope::favorites:
                return _( "View: Favorites" );
            case crafting_scope::recent:
                return _( "View: Recent" );
            case crafting_scope::hidden:
                return _( "View: Hidden" );
            case crafting_scope::nested:
                return _( "View: Nested" );
            case crafting_scope::all:
            default:
                return _( "View: All" );
        }
    };

    const auto build_category_menu_entries = [&]() {
        std::vector<ui_tree_dropdown_entry> entries;
        entries.push_back( { ui_action_entry( _( "All categories" ), "CAT_ALL" ), 0, "", false,
                             all_category_state() } );
        for( const std::string &category : crafting_categories ) {
            const std::string parent_id = "CAT|" + category;
            std::string label = _( get_cat_unprefixed( category ) );
            if( highlight_unread_recipes && is_cat_unread[category] ) {
                label += " +";
            }
            const auto found = category_leaf_keys.find( category );
            const bool expandable = found != category_leaf_keys.end() && !found->second.empty();
            entries.push_back( { ui_action_entry( label, parent_id ), 0, "", expandable,
                                 category_state( category ) } );
            if( found == category_leaf_keys.end() ) {
                continue;
            }
            for( const std::string &key : found->second ) {
                const auto identity = leaf_identity.find( key );
                if( identity == leaf_identity.end() ) {
                    continue;
                }
                const std::string &subcategory = identity->second.second;
                std::string child_label = _( get_subcat_unprefixed( category, subcategory ) );
                if( highlight_unread_recipes && is_subcat_unread[category][subcategory] ) {
                    child_label += " +";
                }
                entries.push_back( { ui_action_entry( child_label, "SUB|" + key ), 1, parent_id, false,
                                     state.category_selection.contains( key ) ? ui_tree_check_state::checked :
                                     ui_tree_check_state::unchecked } );
            }
        }
        return entries;
    };

    const auto persist_state = [&]() {
        uistate.crafting_browser_category_filters.clear();
        for( const std::string &key : state.category_selection.options() ) {
            if( state.category_selection.contains( key ) ) {
                uistate.crafting_browser_category_filters.push_back( key );
            }
        }
        uistate.crafting_browser_scope = static_cast<int>( state.scope );
        uistate.crafting_browser_sort = static_cast<int>( state.sort );

        uistate.crafting_browser_category.clear();
        uistate.crafting_browser_subcategory.clear();
        for( const std::string &category : crafting_categories ) {
            const ui_tree_check_state cat_state = category_state( category );
            if( cat_state == ui_tree_check_state::checked ) {
                uistate.crafting_browser_category = category;
                uistate.crafting_browser_subcategory = "CSC_ALL";
                break;
            }
            if( cat_state == ui_tree_check_state::partial ) {
                for( const std::string &key : category_leaf_keys[category] ) {
                    if( state.category_selection.contains( key ) ) {
                        uistate.crafting_browser_category = category;
                        uistate.crafting_browser_subcategory = leaf_identity[key].second;
                        break;
                    }
                }
                if( !uistate.crafting_browser_category.empty() ) {
                    break;
                }
            }
        }
        if( state.scope != crafting_scope::all ) {
            uistate.crafting_browser_category = "CC_*";
            uistate.crafting_browser_subcategory = state.scope == crafting_scope::favorites ? "CSC_*_FAVORITE" :
                                                   state.scope == crafting_scope::recent ? "CSC_*_RECENT" :
                                                   state.scope == crafting_scope::hidden ? "CSC_*_HIDDEN" :
                                                   "CSC_*_NESTED";
        }

        uistate.crafting_browser_recipe = state.selected_recipe != nullptr ?
                                          state.selected_recipe->ident() : recipe_id::NULL_ID();
        uistate.crafting_browser_search = state.search_query;
        uistate.crafting_browser_craftable_only = state.filters.contains( crafting_filter::craftable );
        uistate.crafting_browser_memorized_only = state.filters.contains( crafting_filter::memorized );
        uistate.crafting_browser_unread_only = state.filters.contains( crafting_filter::unread );
        uistate.crafting_browser_unread_first = state.sort == crafting_sort::unread;
        uistate.crafting_browser_category_scroll = 0;
        uistate.crafting_browser_recipe_scroll = state.recipe_scroll.viewport_pos();
        uistate.crafting_browser_inspector_scroll = state.inspector_scroll.viewport_pos();
        uistate.crafting_browser_batch_size = state.batch_size;
        uistate.crafting_browser_focused_pane = state.focused_pane == crafting_browser_pane::inspector ? 2 : 1;
    };

''',
    "crafting semantic helpers/persistence",
)

# Two-pane responsive shell.
resize_start = browser.find("    ui.on_screen_resize( [&]( ui_adaptor & ui ) {")
resize_end = browser.find("    ui.mark_resize();", resize_start)
if resize_start < 0 or resize_end < 0:
    raise SystemExit("resize block missing")
resize_end += len("    ui.mark_resize();")
browser = browser[:resize_start] + r'''    ui.on_screen_resize( [&]( ui_adaptor & ui ) {
        browser_width = TERMX;
        browser_start = 0;
        compact_layout = browser_width < 100;
        header_height = compact_layout ? 6 : 5;
        body_height = std::max( 8, TERMY - header_height - action_height );

        w_header = catacurses::newwin( header_height, browser_width, point( browser_start, 0 ) );
        w_actions = catacurses::newwin( action_height, browser_width,
                                        point( browser_start, header_height + body_height ) );
        if( compact_layout ) {
            const point body_pos( browser_start, header_height );
            w_recipes = catacurses::newwin( body_height, browser_width, body_pos );
            w_inspector = catacurses::newwin( body_height, browser_width, body_pos );
        } else {
            const int recipe_width = std::clamp( browser_width * 66 / 100, 44, browser_width - 28 );
            const int inspector_width = browser_width - recipe_width;
            w_recipes = catacurses::newwin( body_height, recipe_width,
                                            point( browser_start, header_height ) );
            w_inspector = catacurses::newwin( body_height, inspector_width,
                                              point( browser_start + recipe_width, header_height ) );
        }
        ui.position( point( browser_start, 0 ), point( browser_width, TERMY ) );
    } );
    ui.mark_resize();''' + browser[resize_end:]

redraw_start = browser.find("    ui.on_redraw( [&]( ui_adaptor & ui ) {")
recipes_marker = "        if( draw_recipes ) {"
recipes_at = browser.find(recipes_marker, redraw_start)
if redraw_start < 0 or recipes_at < 0:
    raise SystemExit("redraw/sidebar bounds missing")
browser = browser[:redraw_start] + r'''    ui.on_redraw( [&]( ui_adaptor & ui ) {
        recipe_hits.clear();

        werase( w_header );
        const std::string title = camp_crafting ? _( "CAMP CRAFTING" ) : _( "CRAFTING" );
        draw_border( w_header, BORDER_COLOR, title, c_light_green );

        std::vector<ui_action_entry> header_entries = {
            { category_summary(), "HEADER_CATEGORIES", true, state.open_header_menu == "CATEGORIES" },
            { filter_summary(), "HEADER_FILTER", true, state.open_header_menu == "FILTER" },
            { sort_summary(), "HEADER_SORT", true, state.open_header_menu == "SORT" },
            { scope_summary(), "HEADER_VIEW", true, state.open_header_menu == "VIEW" }
        };
        header_actions.configure( w_header, point( 2, 1 ), std::move( header_entries ),
                                  std::max( 1, browser_width - 4 ), 2 );
        header_actions.draw( w_header );

        const int search_y = 3;
        const int search_x = 2;
        const int search_width = std::max( 16, browser_width - 4 );
        const std::string search_label = _( "Search: " );
        mvwprintz( w_header, point( search_x, search_y ), c_light_gray, "%s", search_label );
        const int field_x = search_x + utf8_width( search_label );
        const int field_width = std::max( 8, search_width - utf8_width( search_label ) );
        mvwputch( w_header, point( field_x, search_y ), c_light_cyan, '[' );
        mvwputch( w_header, point( field_x + field_width - 1, search_y ), c_light_cyan, ']' );
        const bool has_search = !state.search_query.empty();
        const std::string shown_search = has_search ? state.search_query : _( "Search recipes…" );
        trim_and_print( w_header, point( field_x + 1, search_y ), std::max( 1, field_width - 5 ),
                        has_search ? c_white : c_dark_gray, shown_search );
        trim_and_print( w_header, point( field_x + field_width - 4, search_y ), 3,
                        has_search ? c_light_red : c_dark_gray, "[x]" );
        search_hit = inclusive_rectangle<point>( point( field_x, search_y ),
                     point( field_x + field_width - 5, search_y ) );
        search_clear_hit = inclusive_rectangle<point>( point( field_x + field_width - 4, search_y ),
                           point( field_x + field_width - 2, search_y ) );
        search_edit_start = point( field_x + 1, search_y );
        search_edit_end = field_x + field_width - 5;

        if( compact_layout ) {
            std::vector<ui_action_entry> pane_entries = {
                { _( "Recipes" ), "PANE_RECIPES", true,
                  state.focused_pane == crafting_browser_pane::recipes },
                { _( "Inspector" ), "PANE_INSPECTOR", true,
                  state.focused_pane == crafting_browser_pane::inspector }
            };
            pane_actions.configure( w_header, point( 2, 4 ), std::move( pane_entries ),
                                    std::max( 1, browser_width - 4 ) );
            pane_actions.draw( w_header );
        } else {
            pane_actions.clear();
        }
        wnoutrefresh( w_header );

        const bool draw_recipes = !compact_layout ||
                                  state.focused_pane == crafting_browser_pane::recipes;
        const bool draw_inspector = !compact_layout ||
                                    state.focused_pane == crafting_browser_pane::inspector;

        if( draw_recipes ) {''' + browser[recipes_at + len(recipes_marker):]

scope_re = re.compile(r'''            std::string scope = state\.search_query\.empty\(\) \?.*?            trim_and_print\( w_recipes, point\( 1, 1 \),''', re.S)
m = scope_re.search(browser)
if not m:
    raise SystemExit("old recipe scope display missing")
browser = browser[:m.start()] + r'''            std::string scope = scope_summary() + " | " + category_summary();
            if( !state.search_query.empty() ) {
                scope += string_format( _( " | Search: %s" ), state.search_query );
            }
            if( num_hidden > 0 && state.scope != crafting_scope::hidden ) {
                scope += string_format( _( " | %d hidden" ), static_cast<int>( num_hidden ) );
            }
            trim_and_print( w_recipes, point( 1, 1 ),''' + browser[m.end():]

browser = replace_once(
    browser,
    '''        wnoutrefresh( w_actions );
    } );''',
    r'''        wnoutrefresh( w_actions );

        const auto header_menu_pos = [&]( const std::string & id ) {
            int x = 1;
            if( const auto bounds = header_actions.bounds_for_id( id ) ) {
                x = getbegx( w_header ) + bounds->p_min.x;
            }
            return point( std::clamp( x, 0, std::max( 0, TERMX - 3 ) ), header_height );
        };

        if( state.open_header_menu == "CATEGORIES" ) {
            header_menu.close();
            category_menu.configure( catacurses::stdscr, header_menu_pos( "HEADER_CATEGORIES" ),
                                     build_category_menu_entries(), std::min( 46, TERMX ) );
            category_menu.draw( catacurses::stdscr );
        } else {
            category_menu.close();
            if( state.open_header_menu == "FILTER" ) {
                std::vector<ui_dropdown_entry> entries = {
                    { _( "Craftable now" ), "FILTER_CRAFTABLE", true, false, "",
                      state.filters.contains( crafting_filter::craftable ) },
                    { _( "Memorized" ), "FILTER_MEMORIZED", true, false, "",
                      state.filters.contains( crafting_filter::memorized ) },
                    { _( "Unread" ), "FILTER_UNREAD", highlight_unread_recipes, false,
                      _( "Unread highlighting is disabled in options." ),
                      state.filters.contains( crafting_filter::unread ) }
                };
                header_menu.configure( catacurses::stdscr, header_menu_pos( "HEADER_FILTER" ),
                                       std::move( entries ), 28 );
                header_menu.draw( catacurses::stdscr );
            } else if( state.open_header_menu == "SORT" ) {
                std::vector<ui_dropdown_entry> entries = {
                    { _( "Recommended" ), "SORT_0", true, state.sort == crafting_sort::recommended },
                    { _( "Name" ), "SORT_1", true, state.sort == crafting_sort::name },
                    { _( "Difficulty" ), "SORT_2", true, state.sort == crafting_sort::difficulty },
                    { _( "Crafting time" ), "SORT_3", true, state.sort == crafting_sort::time },
                    { _( "Craftability" ), "SORT_4", true, state.sort == crafting_sort::craftability },
                    { _( "Unread first" ), "SORT_5", highlight_unread_recipes,
                      state.sort == crafting_sort::unread,
                      _( "Unread highlighting is disabled in options." ) }
                };
                header_menu.configure( catacurses::stdscr, header_menu_pos( "HEADER_SORT" ),
                                       std::move( entries ), 28 );
                header_menu.draw( catacurses::stdscr );
            } else if( state.open_header_menu == "VIEW" ) {
                std::vector<ui_dropdown_entry> entries = {
                    { _( "All recipes" ), "SCOPE_0", true, state.scope == crafting_scope::all },
                    { _( "Favorites" ), "SCOPE_1", true, state.scope == crafting_scope::favorites },
                    { _( "Recent" ), "SCOPE_2", true, state.scope == crafting_scope::recent },
                    { _( "Hidden" ), "SCOPE_3", true, state.scope == crafting_scope::hidden },
                    { _( "Nested groups" ), "SCOPE_4", true, state.scope == crafting_scope::nested }
                };
                header_menu.configure( catacurses::stdscr, header_menu_pos( "HEADER_VIEW" ),
                                       std::move( entries ), 28 );
                header_menu.draw( catacurses::stdscr );
            } else {
                header_menu.close();
            }
        }
    } );''',
    "draw header dropdowns last",
)

candidate_start = browser.find("        std::vector<const recipe *> candidates;")
sort_start = browser.find('        if( state.selected_subcategory != "CSC_*_RECENT"', candidate_start)
if candidate_start < 0 or sort_start < 0:
    raise SystemExit("candidate/sort markers missing")
browser = browser[:candidate_start] + r'''        std::vector<const recipe *> candidates;
        if( !state.search_query.empty() ) {
            const recipe_subset filtered = filter_recipes( available_recipes,
                                           trim( state.search_query ), *crafter, progress_callback );
            candidates.insert( candidates.end(), filtered.begin(), filtered.end() );
        } else {
            candidates.insert( candidates.end(), available_recipes.begin(), available_recipes.end() );
        }

        show_hidden = state.scope == crafting_scope::hidden;
        num_hidden = 0;
        candidates.erase( std::remove_if( candidates.begin(), candidates.end(),
        [&]( const recipe * rec ) {
            if( rec == nullptr || !recipe_matches_categories( rec ) ) {
                return true;
            }
            const bool hidden = uistate.hidden_recipes.count( rec->ident() ) > 0;
            if( state.scope == crafting_scope::hidden ) {
                return !hidden;
            }
            if( hidden ) {
                ++num_hidden;
                return true;
            }
            switch( state.scope ) {
                case crafting_scope::favorites:
                    return uistate.favorite_recipes.count( rec->ident() ) == 0;
                case crafting_scope::recent:
                    return std::find( uistate.recent_recipes.begin(), uistate.recent_recipes.end(),
                                      rec->ident() ) == uistate.recent_recipes.end();
                case crafting_scope::nested:
                    return !rec->is_nested();
                case crafting_scope::all:
                case crafting_scope::hidden:
                default:
                    return false;
            }
        } ), candidates.end() );

        for( const recipe *rec : candidates ) {
            if( !availability_cache->count( rec ) ) {
                availability_cache->emplace( rec, availability( *crafter, rec, 1,
                                               camp_crafting, inventory_override ) );
            }
        }

''' + browser[sort_start:]

sort_start = browser.find('        if( state.selected_subcategory != "CSC_*_RECENT"')
sort_end = browser.find("        indent.assign( candidates.size(), 0 );", sort_start)
if sort_start < 0 or sort_end < 0:
    raise SystemExit("old sort block missing")
browser = browser[:sort_start] + r'''        if( !( state.scope == crafting_scope::recent && state.sort == crafting_sort::recommended &&
               state.search_query.empty() ) ) {
            std::stable_sort( candidates.begin(), candidates.end(),
            [&]( const recipe * a, const recipe * b ) {
                const availability &a_avail = availability_cache->at( a );
                const availability &b_avail = availability_cache->at( b );
                const auto name_less = [&]() {
                    if( a->result_name() != b->result_name() ) {
                        return localized_compare( a->result_name(), b->result_name() );
                    }
                    return a->ident().str() < b->ident().str();
                };
                switch( state.sort ) {
                    case crafting_sort::name:
                        return name_less();
                    case crafting_sort::difficulty:
                        if( a->difficulty != b->difficulty ) {
                            return a->difficulty < b->difficulty;
                        }
                        return name_less();
                    case crafting_sort::time:
                        if( a->time_to_craft( *crafter ) != b->time_to_craft( *crafter ) ) {
                            return a->time_to_craft( *crafter ) < b->time_to_craft( *crafter );
                        }
                        return name_less();
                    case crafting_sort::craftability:
                        if( a_avail.can_craft != b_avail.can_craft ) {
                            return a_avail.can_craft;
                        }
                        return name_less();
                    case crafting_sort::unread:
                        if( highlight_unread_recipes ) {
                            const bool a_read = uistate.read_recipes.count( a->ident() );
                            const bool b_read = uistate.read_recipes.count( b->ident() );
                            if( a_read != b_read ) {
                                return !a_read;
                            }
                        }
                        // fall through
                    case crafting_sort::recommended:
                    default:
                        if( a_avail.can_craft != b_avail.can_craft ) {
                            return a_avail.can_craft;
                        }
                        if( a->difficulty != b->difficulty ) {
                            return a->difficulty < b->difficulty;
                        }
                        if( a->result_name() != b->result_name() ) {
                            return localized_compare( a->result_name(), b->result_name() );
                        }
                        if( a->time_to_craft( *crafter ) != b->time_to_craft( *crafter ) ) {
                            return a->time_to_craft( *crafter ) < b->time_to_craft( *crafter );
                        }
                        return a->ident().str() < b->ident().str();
                }
            } );
        }

''' + browser[sort_end:]

browser = replace_once(
    browser,
    '''            const availability &rec_avail = availability_cache->at( rec );
            if( state.filters.contains( crafting_filter::craftable ) &&
''',
    '''            const availability &rec_avail = availability_cache->at( rec );
            if( !recipe_matches_categories( rec ) ) {
                continue;
            }
            if( state.filters.contains( crafting_filter::craftable ) &&
''',
    "expanded recipe category filtering",
)
browser = replace_once(
    browser,
    '''        expand_recipes( candidates, indent, *availability_cache, *crafter, state.unread_first,
                        highlight_unread_recipes, available_recipes, uistate.hidden_recipes,
''',
    '''        expand_recipes( candidates, indent, *availability_cache, *crafter,
                        state.sort == crafting_sort::unread,
                        highlight_unread_recipes, available_recipes, uistate.hidden_recipes,
''',
    "nested unread sort state",
)

browser = replace_once(
    browser,
    '''        const std::optional<point> header_pos = local_mouse( w_header );
        const std::optional<point> sidebar_pos = local_mouse( w_sidebar );
        const std::optional<point> recipes_pos = local_mouse( w_recipes );
''',
    '''        const std::optional<point> header_pos = local_mouse( w_header );
        const std::optional<point> screen_pos = local_mouse( catacurses::stdscr );
        const std::optional<point> recipes_pos = local_mouse( w_recipes );
''',
    "input coordinates",
)

context_at = browser.find("        if( state.context_open ) {")
if context_at < 0:
    raise SystemExit("context input marker missing")
browser = browser[:context_at] + r'''        if( state.open_header_menu == "CATEGORIES" ) {
            const ui_action_result result = category_menu.handle_input( action, screen_pos, false );
            if( result.type == ui_action_result_type::activated && result.entry ) {
                const std::string &id = result.entry->id;
                if( id == "CAT_ALL" ) {
                    state.category_selection.toggle_all();
                } else if( id.rfind( "CAT|", 0 ) == 0 ) {
                    const std::string category = id.substr( 4 );
                    set_category_selected( category, category_state( category ) != ui_tree_check_state::checked );
                } else if( id.rfind( "SUB|", 0 ) == 0 ) {
                    state.category_selection.toggle( id.substr( 4 ) );
                }
                recalc = true;
                continue;
            }
            if( result.type == ui_action_result_type::closed ) {
                state.open_header_menu.clear();
                continue;
            }
            if( result.consumed() ) {
                continue;
            }
        } else if( !state.open_header_menu.empty() ) {
            const bool keep_open = state.open_header_menu == "FILTER";
            const ui_action_result result = header_menu.handle_input( action, screen_pos, !keep_open );
            if( result.type == ui_action_result_type::activated && result.entry ) {
                const std::string id = result.entry->id;
                if( id == "FILTER_CRAFTABLE" ) {
                    state.filters.toggle( crafting_filter::craftable );
                } else if( id == "FILTER_MEMORIZED" ) {
                    state.filters.toggle( crafting_filter::memorized );
                } else if( id == "FILTER_UNREAD" && highlight_unread_recipes ) {
                    state.filters.toggle( crafting_filter::unread );
                } else if( id.rfind( "SORT_", 0 ) == 0 ) {
                    state.sort = static_cast<crafting_sort>( std::clamp( std::stoi( id.substr( 5 ) ), 0,
                                 static_cast<int>( crafting_sort::unread ) ) );
                    state.open_header_menu.clear();
                } else if( id.rfind( "SCOPE_", 0 ) == 0 ) {
                    state.scope = static_cast<crafting_scope>( std::clamp( std::stoi( id.substr( 6 ) ), 0,
                                  static_cast<int>( crafting_scope::nested ) ) );
                    state.open_header_menu.clear();
                }
                recalc = true;
                continue;
            }
            if( result.type == ui_action_result_type::disabled && result.entry ) {
                workspace_status = result.entry->disabled_reason;
                continue;
            }
            if( result.type == ui_action_result_type::closed ) {
                state.open_header_menu.clear();
                continue;
            }
            if( result.consumed() ) {
                continue;
            }
        }

''' + browser[context_at:]

mouse_start = browser.find('        if( action == "MOUSE_MOVE" ) {')
select_start = browser.find('        if( action == "SELECT" ) {', mouse_start)
if mouse_start < 0 or select_start < 0:
    raise SystemExit("mouse/select bounds missing")
browser = browser[:mouse_start] + r'''        if( action == "MOUSE_MOVE" ) {
            state.hovered_recipe = nullptr;
            header_actions.update_hover( header_pos );
            pane_actions.update_hover( compact_layout ? header_pos : std::nullopt );
            inspector_actions.update_hover( ( !compact_layout ||
                                               state.focused_pane == crafting_browser_pane::inspector ) ?
                                              inspector_pos : std::nullopt );
            toolbar_actions.update_hover( actions_pos );
            if( ( !compact_layout || state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );
                if( hit && *hit >= 0 && *hit < static_cast<int>( current.size() ) ) {
                    state.hovered_recipe = current[*hit];
                }
            }
            continue;
        }

''' + browser[select_start:]

select_start = browser.find('        if( action == "SELECT" ) {')
sec_start = browser.find('        } else if( action == "SEC_SELECT" ) {', select_start)
if select_start < 0 or sec_start < 0:
    raise SystemExit("select/sec-select bounds missing")
browser = browser[:select_start] + r'''        if( action == "SELECT" ) {
            bool handled = false;
            if( header_pos ) {
                const ui_action_result result = header_actions.handle_input( action, header_pos );
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    const std::string id = result.entry->id;
                    const std::string requested = id == "HEADER_CATEGORIES" ? "CATEGORIES" :
                                                  id == "HEADER_FILTER" ? "FILTER" :
                                                  id == "HEADER_SORT" ? "SORT" :
                                                  id == "HEADER_VIEW" ? "VIEW" : "";
                    if( !requested.empty() ) {
                        state.open_header_menu = state.open_header_menu == requested ? std::string() : requested;
                        category_menu.close();
                        header_menu.close();
                        state.context_open = false;
                        context_menu.close();
                    }
                }
                handled = result.consumed();
            }
            if( !handled && compact_layout && header_pos ) {
                const ui_action_result result = pane_actions.handle_input( action, header_pos );
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    if( result.entry->id == "PANE_RECIPES" ) {
                        state.focused_pane = crafting_browser_pane::recipes;
                    } else if( result.entry->id == "PANE_INSPECTOR" ) {
                        state.focused_pane = crafting_browser_pane::inspector;
                    }
                }
                handled = result.consumed();
            }
            if( !handled && header_pos && search_clear_hit.contains( *header_pos ) ) {
                action = "RESET_FILTER";
                handled = true;
            } else if( !handled && header_pos && search_hit.contains( *header_pos ) ) {
                action = "FILTER";
                handled = true;
            }
            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::inspector ) && inspector_pos ) {
                const ui_action_result result = inspector_actions.handle_input( action, inspector_pos );
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    action = result.entry->id;
                } else if( result.type == ui_action_result_type::disabled && result.entry ) {
                    workspace_status = result.entry->disabled_reason;
                }
                handled = result.consumed();
            }
            if( !handled && actions_pos ) {
                const ui_action_result result = toolbar_actions.handle_input( action, actions_pos );
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    action = result.entry->id;
                } else if( result.type == ui_action_result_type::disabled && result.entry ) {
                    workspace_status = result.entry->disabled_reason;
                }
                handled = result.consumed();
            }
            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );
                if( hit ) {
                    const recipe *clicked = current[*hit];
                    const bool double_click = state.recipe_clicks.click( clicked );
                    select_index( *hit, true );
                    if( double_click ) {
                        action = "CONFIRM";
                    }
                    handled = true;
                }
            }
            if( handled && action == "SELECT" ) {
                continue;
            }
''' + browser[sec_start:]

scroll_start = browser.find('        if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {')
index_at = browser.find('        const int index = selected_index();', scroll_start)
if scroll_start < 0 or index_at < 0:
    raise SystemExit("scroll block missing")
browser = browser[:scroll_start] + r'''        if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
            const int direction = action == "SCROLL_UP" ? -1 : 1;
            if( compact_layout ) {
                if( state.focused_pane == crafting_browser_pane::recipes ) {
                    state.recipe_scroll.scroll_by( direction * 3 );
                } else {
                    state.inspector_scroll.scroll_by( direction * 3 );
                }
            } else if( recipes_pos ) {
                state.recipe_scroll.scroll_by( direction * 3 );
            } else if( inspector_pos ) {
                state.inspector_scroll.scroll_by( direction * 3 );
            }
            continue;
        }

''' + browser[index_at:]

nav_start = browser.find('        } else if( action == "PREV_TAB" || action == "NEXT_TAB" ) {')
filter_at = browser.find('        } else if( action == "FILTER" ) {', nav_start)
if nav_start < 0 or filter_at < 0:
    raise SystemExit("keyboard category navigation missing")
browser = browser[:nav_start] + r'''        } else if( action == "PREV_TAB" || action == "NEXT_TAB" ) {
            int category_index = 0;
            for( int i = 0; i < static_cast<int>( crafting_categories.size() ); ++i ) {
                if( category_state( crafting_categories[i] ) != ui_tree_check_state::unchecked ) {
                    category_index = i;
                    break;
                }
            }
            const int direction = action == "PREV_TAB" ? -1 : 1;
            category_index = ( category_index + direction + static_cast<int>( crafting_categories.size() ) ) %
                             static_cast<int>( crafting_categories.size() );
            state.category_selection.clear();
            set_category_selected( crafting_categories[category_index], true );
            state.scope = crafting_scope::all;
            recalc = true;
        } else if( action == "LEFT" || action == "RIGHT" ) {
            std::string category;
            for( const std::string &candidate : crafting_categories ) {
                if( category_state( candidate ) != ui_tree_check_state::unchecked ) {
                    category = candidate;
                    break;
                }
            }
            const auto found = category_leaf_keys.find( category );
            if( found != category_leaf_keys.end() && !found->second.empty() ) {
                int subcategory_index = 0;
                for( int i = 0; i < static_cast<int>( found->second.size() ); ++i ) {
                    if( state.category_selection.contains( found->second[i] ) ) {
                        subcategory_index = i;
                        break;
                    }
                }
                const int direction = action == "LEFT" ? -1 : 1;
                subcategory_index = ( subcategory_index + direction + static_cast<int>( found->second.size() ) ) %
                                    static_cast<int>( found->second.size() );
                state.category_selection.clear();
                state.category_selection.set( found->second[subcategory_index], true );
                state.scope = crafting_scope::all;
                recalc = true;
            }
''' + browser[filter_at:]

browser = replace_once(
    browser,
    '''            if( state.selected_subcategory == "CSC_*_FAVORITE" && state.search_query.empty() ) {
                recalc = true;
            }
''',
    '''            if( state.scope == crafting_scope::favorites ) {
                recalc = true;
            }
''',
    "favorite scope recalc",
)
browser = replace_once(
    browser,
    '''        } else if( action == "TOGGLE_UNREAD_RECIPES_FIRST" &&
                   highlight_unread_recipes ) {
            state.unread_first = !state.unread_first;
            recalc = true;
''',
    '''        } else if( action == "TOGGLE_UNREAD_RECIPES_FIRST" &&
                   highlight_unread_recipes ) {
            state.sort = state.sort == crafting_sort::unread ? crafting_sort::recommended :
                         crafting_sort::unread;
            recalc = true;
''',
    "unread-first sort compatibility",
)

for forbidden in [
    "state.selected_category",
    "state.selected_subcategory",
    "state.category_scroll",
    "sidebar_hits",
    "sidebar_entries",
    "sidebar_scrollbar",
    "hovered_sidebar_entry",
    "w_sidebar",
    "crafting_browser_pane::categories",
    "state.unread_first",
]:
    if forbidden in browser:
        raise SystemExit(f"migration incomplete; forbidden token remains: {forbidden}")

craft = craft[:fn_start] + browser + craft[fn_end:]
write(craft_path, craft)

Path("/tmp/branch_patch_commit_message").write_text(
    "Redesign crafting browser with helper-driven filters\n", encoding="utf-8"
)
