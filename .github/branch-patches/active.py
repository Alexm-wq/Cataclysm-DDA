from pathlib import Path
import re

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")


def replace_once(label: str, old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


def regex_once(label: str, pattern: str, replacement: str) -> None:
    global text
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")


replace_once(
    "helper includes",
    '#include "ui_iteminfo.h"\n#include "ui_manager.h"\n#include "uistate.h"',
    '#include "ui_iteminfo.h"\n#include "ui_manager.h"\n#include "ui_helpers/controls/action_strip.h"\n#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/models/double_click_tracker.h"\n#include "ui_helpers/models/hit_map.h"\n#include "ui_helpers/models/multiselect_filter.h"\n#include "ui_helpers/models/scroll_model.h"\n#include "ui_helpers/primitive/scrollbar.h"\n#include "uistate.h"',
)

replace_once(
    "crafting filter enum",
    'enum class crafting_browser_pane : int {\n    categories = 0,\n    recipes,\n    inspector\n};',
    'enum class crafting_browser_pane : int {\n    categories = 0,\n    recipes,\n    inspector\n};\n\nenum class crafting_filter : int {\n    craftable,\n    memorized,\n    unread\n};',
)

regex_once(
    "remove bespoke button struct",
    r'\nstruct crafting_browser_button \{.*?\n\};\n\nstruct crafting_browser_state \{',
    '\nstruct crafting_browser_state {',
)

replace_once(
    "browser state helpers",
    '''struct crafting_browser_state {
    const recipe *selected_recipe = nullptr;
    std::string selected_category;
    std::string selected_subcategory;
    std::string search_query;
    bool craftable_only = false;
    bool memorized_only = false;
    bool unread_only = false;
    bool unread_first = false;
    int recipe_scroll = 0;
    int category_scroll = 0;
    int inspector_scroll = 0;
    int item_popup_scroll = 0;
    int batch_size = 1;
    crafting_browser_pane focused_pane = crafting_browser_pane::recipes;
    const recipe *hovered_recipe = nullptr;
    const recipe *last_clicked_recipe = nullptr;
    std::optional<std::chrono::steady_clock::time_point> last_click_time;
    bool context_open = false;
    point context_pos;
    int context_width = 0;
    int context_height = 0;
};''',
    '''struct crafting_browser_state {
    crafting_browser_state() : filters( { crafting_filter::craftable, crafting_filter::memorized,
                                          crafting_filter::unread } ) {
        filters.clear();
    }

    const recipe *selected_recipe = nullptr;
    std::string selected_category;
    std::string selected_subcategory;
    std::string search_query;
    ui_multiselect_filter<crafting_filter> filters;
    bool unread_first = false;
    ui_scroll_model recipe_scroll;
    ui_scroll_model category_scroll;
    ui_scroll_model inspector_scroll;
    int item_popup_scroll = 0;
    int batch_size = 1;
    crafting_browser_pane focused_pane = crafting_browser_pane::recipes;
    const recipe *hovered_recipe = nullptr;
    ui_double_click_tracker<const recipe *> recipe_clicks;
    bool context_open = false;
    point context_pos;
};''',
)

replace_once(
    "restore filters and scroll models",
    '''    state.craftable_only = uistate.crafting_browser_craftable_only;
    state.memorized_only = uistate.crafting_browser_memorized_only;
    state.unread_only = highlight_unread_recipes && uistate.crafting_browser_unread_only;
    state.unread_first = highlight_unread_recipes && uistate.crafting_browser_unread_first;
    state.category_scroll = std::max( 0, uistate.crafting_browser_category_scroll );
    state.recipe_scroll = std::max( 0, uistate.crafting_browser_recipe_scroll );
    state.inspector_scroll = std::max( 0, uistate.crafting_browser_inspector_scroll );''',
    '''    state.filters.set( crafting_filter::craftable, uistate.crafting_browser_craftable_only );
    state.filters.set( crafting_filter::memorized, uistate.crafting_browser_memorized_only );
    state.filters.set( crafting_filter::unread,
                       highlight_unread_recipes && uistate.crafting_browser_unread_only );
    state.unread_first = highlight_unread_recipes && uistate.crafting_browser_unread_first;
    state.category_scroll.set_viewport_pos( std::max( 0, uistate.crafting_browser_category_scroll ) );
    state.recipe_scroll.set_viewport_pos( std::max( 0, uistate.crafting_browser_recipe_scroll ) );
    state.inspector_scroll.set_viewport_pos( std::max( 0, uistate.crafting_browser_inspector_scroll ) );''',
)

replace_once(
    "helper control declarations",
    '''    std::vector<crafting_sidebar_entry> sidebar_entries;
    std::vector<std::pair<inclusive_rectangle<point>, int>> sidebar_hits;
    std::vector<std::pair<inclusive_rectangle<point>, int>> recipe_hits;
    std::vector<std::pair<inclusive_rectangle<point>, crafting_browser_pane>> pane_hits;
    std::vector<crafting_browser_button> inspector_buttons;
    std::vector<crafting_browser_button> toolbar_buttons;
    std::vector<crafting_browser_button> context_buttons;
    int hovered_sidebar_entry = -1;
    std::string hovered_inspector_action;
    std::string hovered_toolbar_action;
    int hovered_context_button = -1;''',
    '''    std::vector<crafting_sidebar_entry> sidebar_entries;
    ui_hit_map<int> sidebar_hits;
    ui_hit_map<int> recipe_hits;
    ui_action_strip pane_actions;
    ui_action_strip inspector_actions;
    ui_action_strip toolbar_actions;
    ui_dropdown context_menu;
    scrollbar sidebar_scrollbar;
    scrollbar recipe_scrollbar;
    scrollbar inspector_scrollbar;
    int hovered_sidebar_entry = -1;''',
)

replace_once(
    "selection reset helper state",
    '''            workspace_status.clear();
            state.inspector_scroll = 0;
            state.context_open = false;
            state.last_clicked_recipe = nullptr;
            state.last_click_time.reset();''',
    '''            workspace_status.clear();
            state.inspector_scroll.scroll_to_start();
            state.context_open = false;
            context_menu.close();
            state.recipe_clicks.reset();''',
)

replace_once(
    "persist helper state",
    '''        uistate.crafting_browser_craftable_only = state.craftable_only;
        uistate.crafting_browser_memorized_only = state.memorized_only;
        uistate.crafting_browser_unread_only = state.unread_only;
        uistate.crafting_browser_unread_first = state.unread_first;
        uistate.crafting_browser_category_scroll = state.category_scroll;
        uistate.crafting_browser_recipe_scroll = state.recipe_scroll;
        uistate.crafting_browser_inspector_scroll = state.inspector_scroll;''',
    '''        uistate.crafting_browser_craftable_only = state.filters.contains( crafting_filter::craftable );
        uistate.crafting_browser_memorized_only = state.filters.contains( crafting_filter::memorized );
        uistate.crafting_browser_unread_only = state.filters.contains( crafting_filter::unread );
        uistate.crafting_browser_unread_first = state.unread_first;
        uistate.crafting_browser_category_scroll = state.category_scroll.viewport_pos();
        uistate.crafting_browser_recipe_scroll = state.recipe_scroll.viewport_pos();
        uistate.crafting_browser_inspector_scroll = state.inspector_scroll.viewport_pos();''',
)

replace_once(
    "redraw clear helpers",
    '''        sidebar_hits.clear();
        recipe_hits.clear();
        pane_hits.clear();
        inspector_buttons.clear();
        toolbar_buttons.clear();
        context_buttons.clear();''',
    '''        sidebar_hits.clear();
        recipe_hits.clear();
        if( !compact_layout ) {
            pane_actions.clear();
        }''',
)

regex_once(
    "compact pane action strip",
    r'''        if\( compact_layout \) \{\n            int pane_x = 2;.*?\n        \}\n        wnoutrefresh\( w_header \);''',
    '''        if( compact_layout ) {
            std::vector<ui_action_entry> pane_entries = {
                { _( "Categories" ), "PANE_CATEGORIES", true,
                  state.focused_pane == crafting_browser_pane::categories },
                { _( "Recipes" ), "PANE_RECIPES", true,
                  state.focused_pane == crafting_browser_pane::recipes },
                { _( "Inspector" ), "PANE_INSPECTOR", true,
                  state.focused_pane == crafting_browser_pane::inspector }
            };
            pane_actions.configure( w_header, point( 2, 3 ), std::move( pane_entries ),
                                    std::max( 1, browser_width - 4 ) );
            pane_actions.draw( w_header );
        }
        wnoutrefresh( w_header );''',
)

replace_once(
    "sidebar scroll model setup",
    '''            const int visible = std::max( 1, getmaxy( w_sidebar ) - 2 );
            const int max_scroll = std::max( 0, static_cast<int>( sidebar_entries.size() ) - visible );
            state.category_scroll = std::clamp( state.category_scroll, 0, max_scroll );
            for( int row = 0; row < visible; ++row ) {
                const int index = state.category_scroll + row;''',
    '''            const int visible = std::max( 1, getmaxy( w_sidebar ) - 2 );
            state.category_scroll.set_content_size( static_cast<int>( sidebar_entries.size() ) )
            .set_viewport_size( visible );
            for( int row = 0; row < visible; ++row ) {
                const int index = state.category_scroll.viewport_pos() + row;''',
)

replace_once(
    "sidebar filter rendering",
    '''                    if( entry.category == "FILTER_CRAFTABLE" ) {
                        selected = state.craftable_only;
                    } else if( entry.category == "FILTER_MEMORIZED" ) {
                        selected = state.memorized_only;
                    } else if( entry.category == "FILTER_UNREAD" ) {
                        selected = state.unread_only;
                    }''',
    '''                    if( entry.category == "FILTER_CRAFTABLE" ) {
                        selected = state.filters.contains( crafting_filter::craftable );
                    } else if( entry.category == "FILTER_MEMORIZED" ) {
                        selected = state.filters.contains( crafting_filter::memorized );
                    } else if( entry.category == "FILTER_UNREAD" ) {
                        selected = state.filters.contains( crafting_filter::unread );
                    }''',
)

replace_once(
    "sidebar hit map add",
    '''                    sidebar_hits.emplace_back( inclusive_rectangle<point>( point( 1, y ),
                                               point( sidebar_width - 2, y ) ), index );''',
    '''                    sidebar_hits.add( inclusive_rectangle<point>( point( 1, y ),
                                      point( sidebar_width - 2, y ) ), index );''',
)

replace_once(
    "sidebar persistent scrollbar",
    '''                scrollbar().offset_x( sidebar_width - 1 ).offset_y( 1 )
                .content_size( static_cast<int>( sidebar_entries.size() ) )
                .viewport_pos( state.category_scroll ).viewport_size( visible ).apply( w_sidebar );''',
    '''                sidebar_scrollbar.offset_x( sidebar_width - 1 ).offset_y( 1 )
                .model( state.category_scroll ).apply( w_sidebar );''',
)

replace_once(
    "recipe scroll model setup",
    '''            const int visible = std::max( 1, getmaxy( w_recipes ) - first_row - 1 );
            const int max_scroll = std::max( 0, static_cast<int>( current.size() ) - visible );
            state.recipe_scroll = std::clamp( state.recipe_scroll, 0, max_scroll );''',
    '''            const int visible = std::max( 1, getmaxy( w_recipes ) - first_row - 1 );
            state.recipe_scroll.set_content_size( static_cast<int>( current.size() ) )
            .set_viewport_size( visible );''',
)
text = text.replace('const int index = state.recipe_scroll + row;',
                    'const int index = state.recipe_scroll.viewport_pos() + row;')

replace_once(
    "recipe hit map add",
    '''                recipe_hits.emplace_back( inclusive_rectangle<point>( point( 1, y ),
                                          point( list_width - 2, y ) ), index );''',
    '''                recipe_hits.add( inclusive_rectangle<point>( point( 1, y ),
                                 point( list_width - 2, y ) ), index );''',
)

replace_once(
    "recipe persistent scrollbar",
    '''                scrollbar().offset_x( list_width - 1 ).offset_y( first_row )
                .content_size( static_cast<int>( current.size() ) )
                .viewport_pos( state.recipe_scroll ).viewport_size( visible ).apply( w_recipes );''',
    '''                recipe_scrollbar.offset_x( list_width - 1 ).offset_y( first_row )
                .model( state.recipe_scroll ).apply( w_recipes );''',
)

regex_once(
    "context dropdown",
    r'''            if\( state\.context_open && state\.selected_recipe != nullptr \) \{.*?\n            \}\n            wnoutrefresh\( w_recipes \);''',
    '''            if( state.context_open && state.selected_recipe != nullptr ) {
                availability *avail = selected_availability();
                const std::string reason = avail == nullptr ? _( "Nothing selected." ) :
                                           crafting_unavailable_reason( *state.selected_recipe, *avail,
                                                   *crafter, state.batch_size );
                const bool craft_enabled = avail != nullptr &&
                                           crafting_recipe_can_start( *state.selected_recipe, *avail, *crafter );
                const bool normal_recipe = !state.selected_recipe->is_nested();
                const bool favorite = uistate.favorite_recipes.count( state.selected_recipe->ident() );
                const bool hidden = uistate.hidden_recipes.count( state.selected_recipe->ident() );
                std::vector<ui_dropdown_entry> entries = {
                    { craft_enabled ? _( "Craft" ) : string_format( _( "Craft — %s" ), reason ),
                      "CONFIRM", craft_enabled, false, reason },
                    { _( "Craft batch…" ), "CYCLE_BATCH", normal_recipe, false,
                      _( "Choose a concrete recipe first." ) },
                    { favorite ? _( "Unfavorite" ) : _( "Favorite" ), "TOGGLE_FAVORITE" },
                    { hidden ? _( "Unhide" ) : _( "Hide" ), "HIDE_SHOW_RECIPE" },
                    { _( "Examine" ), "HELP_RECIPE", normal_recipe, false,
                      _( "Choose a concrete recipe first." ) },
                    { _( "Choose crafter…" ), "CHOOSE_CRAFTER" },
                    { _( "Related recipes…" ), "RELATED_RECIPES", normal_recipe, false,
                      _( "Choose a concrete recipe first." ) },
                    { _( "Compare…" ), "COMPARE", normal_recipe, false,
                      _( "Choose a concrete recipe first." ) }
                };
                context_menu.configure( w_recipes, state.context_pos, std::move( entries ) );
                context_menu.draw( w_recipes );
            } else {
                context_menu.close();
            }
            wnoutrefresh( w_recipes );''',
)

regex_once(
    "inspector action strip",
    r'''                int batch_x = 1;\n                mvwprintz\( w_inspector, point\( batch_x, 3 \), c_light_gray, "%s", _\( "Batch: " \) \);.*?\n                wattron\( w_inspector, c_dark_gray \);''',
    '''                int batch_x = 1;
                mvwprintz( w_inspector, point( batch_x, 3 ), c_light_gray, "%s", _( "Batch: " ) );
                batch_x += utf8_width( _( "Batch: " ) );
                const bool batch_enabled = !state.selected_recipe->is_nested();
                std::vector<ui_action_entry> batch_entries = {
                    { "[ - ]", "BATCH_DEC", batch_enabled, false,
                      _( "Choose a concrete recipe first." ) },
                    { string_format( "[ %d ]", state.batch_size ), "BATCH_EDIT", batch_enabled, false,
                      _( "Choose a concrete recipe first." ) },
                    { "[ + ]", "BATCH_INC", batch_enabled, false,
                      _( "Choose a concrete recipe first." ) },
                    { _( "[ Max ]" ), "BATCH_MAX", batch_enabled, false,
                      _( "Choose a concrete recipe first." ) }
                };
                ui_action_strip_style batch_style;
                batch_style.decorate = false;
                batch_style.gap = 1;
                inspector_actions.configure( w_inspector, point( batch_x, 3 ),
                                             std::move( batch_entries ),
                                             std::max( 1, inspector_width - batch_x - 1 ), 1,
                                             batch_style );
                inspector_actions.draw( w_inspector );
                wattron( w_inspector, c_dark_gray );''',
)

replace_once(
    "inspector scroll model setup",
    '''                    const int visible = std::max( 1, inspector_height - first_row - 1 );
                    const int max_scroll = std::max( 0, static_cast<int>( info.size() ) - visible );
                    state.inspector_scroll = std::clamp( state.inspector_scroll, 0, max_scroll );
                    for( int row = 0; row < visible; ++row ) {
                        const int index = state.inspector_scroll + row;''',
    '''                    const int visible = std::max( 1, inspector_height - first_row - 1 );
                    state.inspector_scroll.set_content_size( static_cast<int>( info.size() ) )
                    .set_viewport_size( visible );
                    for( int row = 0; row < visible; ++row ) {
                        const int index = state.inspector_scroll.viewport_pos() + row;''',
)

replace_once(
    "inspector persistent scrollbar",
    '''                        scrollbar().offset_x( inspector_width - 1 ).offset_y( first_row )
                        .content_size( static_cast<int>( info.size() ) )
                        .viewport_pos( state.inspector_scroll ).viewport_size( visible )
                        .apply( w_inspector );''',
    '''                        inspector_scrollbar.offset_x( inspector_width - 1 ).offset_y( first_row )
                        .model( state.inspector_scroll ).apply( w_inspector );''',
)

regex_once(
    "toolbar action strip",
    r'''        toolbar_buttons = \{.*?\n        \};\n        int button_x = 1;.*?\n        const std::string status =''',
    '''        std::vector<ui_action_entry> toolbar_entries = {
            { _( "Craft" ), "CONFIRM", craft_enabled, false, reason },
            { _( "Batch…" ), "CYCLE_BATCH", normal_recipe, false,
              _( "Choose a concrete recipe first." ) },
            { favorite ? _( "Unfavorite" ) : _( "Favorite" ), "TOGGLE_FAVORITE",
              state.selected_recipe != nullptr, false, _( "Select a recipe first." ) },
            { hidden ? _( "Unhide" ) : _( "Hide" ), "HIDE_SHOW_RECIPE",
              state.selected_recipe != nullptr, false, _( "Select a recipe first." ) },
            { _( "Examine" ), "HELP_RECIPE", normal_recipe, false,
              _( "Choose a concrete recipe first." ) },
            { _( "Crafter…" ), "CHOOSE_CRAFTER" },
            { _( "Related" ), "RELATED_RECIPES", normal_recipe, false,
              _( "Choose a concrete recipe first." ) },
            { _( "Compare" ), "COMPARE", normal_recipe, false,
              _( "Choose a concrete recipe first." ) },
            { _( "Back" ), "QUIT" }
        };
        toolbar_actions.configure( w_actions, point( 1, 1 ), std::move( toolbar_entries ),
                                   std::max( 1, browser_width - 2 ), 2 );
        toolbar_actions.draw( w_actions );
        const std::string status =''',
)

replace_once(
    "craftable filter predicate",
    '''            if( state.craftable_only &&
                !( rec_avail.can_craft && rec_avail.crafter_has_primary_skill ) ) {''',
    '''            if( state.filters.contains( crafting_filter::craftable ) &&
                !( rec_avail.can_craft && rec_avail.crafter_has_primary_skill ) ) {''',
)
replace_once(
    "memorized filter predicate",
    '''            if( state.memorized_only && !crafter->knows_recipe( rec ) ) {''',
    '''            if( state.filters.contains( crafting_filter::memorized ) && !crafter->knows_recipe( rec ) ) {''',
)
replace_once(
    "unread filter predicate",
    '''            if( state.unread_only && uistate.read_recipes.count( rec->ident() ) ) {''',
    '''            if( state.filters.contains( crafting_filter::unread ) &&
                uistate.read_recipes.count( rec->ident() ) ) {''',
)

replace_once(
    "rebuild recipe scroll ensure",
    '''        const int index = selected_index();
        const int visible = w_recipes ? std::max( 1, getmaxy( w_recipes ) - 3 ) :
                            std::max( 1, body_height - 3 );
        if( index >= 0 ) {
            if( index < state.recipe_scroll ) {
                state.recipe_scroll = index;
            } else if( index >= state.recipe_scroll + visible ) {
                state.recipe_scroll = index - visible + 1;
            }
        } else {
            state.recipe_scroll = 0;
        }''',
    '''        const int index = selected_index();
        const int visible = w_recipes ? std::max( 1, getmaxy( w_recipes ) - 3 ) :
                            std::max( 1, body_height - 3 );
        state.recipe_scroll.set_content_size( static_cast<int>( current.size() ) )
        .set_viewport_size( visible );
        if( index >= 0 ) {
            state.recipe_scroll.ensure_visible( index );
        } else {
            state.recipe_scroll.scroll_to_start();
        }''',
)

regex_once(
    "context centralized input",
    r'''        if\( state\.context_open \) \{.*?\n        \}\n\n        if\( action == "MOUSE_MOVE" \) \{''',
    '''        if( state.context_open ) {
            const ui_action_result result = context_menu.handle_input( action, recipes_pos );
            if( result.type == ui_action_result_type::activated && result.entry ) {
                state.context_open = false;
                action = result.entry->id;
            } else if( result.type == ui_action_result_type::disabled && result.entry ) {
                workspace_status = result.entry->disabled_reason;
                state.context_open = false;
                context_menu.close();
                continue;
            } else if( result.type == ui_action_result_type::closed ) {
                state.context_open = false;
                continue;
            } else if( result.consumed() ) {
                continue;
            }
        }

        if( action == "MOUSE_MOVE" ) {''',
)

regex_once(
    "mouse hover helper controls",
    r'''        if\( action == "MOUSE_MOVE" \) \{.*?\n            continue;\n        \}\n\n        if\( action == "SELECT" \) \{''',
    '''        if( action == "MOUSE_MOVE" ) {
            hovered_sidebar_entry = -1;
            state.hovered_recipe = nullptr;
            pane_actions.update_hover( compact_layout ? header_pos : std::nullopt );
            inspector_actions.update_hover( ( !compact_layout ||
                                               state.focused_pane == crafting_browser_pane::inspector ) ?
                                              inspector_pos : std::nullopt );
            toolbar_actions.update_hover( actions_pos );
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::categories ) && sidebar_pos ) {
                hovered_sidebar_entry = sidebar_hits.hit( *sidebar_pos ).value_or( -1 );
            }
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );
                if( hit && *hit >= 0 && *hit < static_cast<int>( current.size() ) ) {
                    state.hovered_recipe = current[*hit];
                }
            }
            continue;
        }

        if( action == "SELECT" ) {''',
)

replace_once(
    "pane action input",
    '''            if( compact_layout && header_pos ) {
                for( const auto &hit : pane_hits ) {
                    if( hit.first.contains( *header_pos ) ) {
                        state.focused_pane = hit.second;
                        handled = true;
                        break;
                    }
                }
            }''',
    '''            if( compact_layout && header_pos ) {
                const ui_action_result result = pane_actions.handle_input( action, header_pos );
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    if( result.entry->id == "PANE_CATEGORIES" ) {
                        state.focused_pane = crafting_browser_pane::categories;
                    } else if( result.entry->id == "PANE_RECIPES" ) {
                        state.focused_pane = crafting_browser_pane::recipes;
                    } else if( result.entry->id == "PANE_INSPECTOR" ) {
                        state.focused_pane = crafting_browser_pane::inspector;
                    }
                }
                handled = result.consumed();
            }''',
)

regex_once(
    "sidebar semantic click",
    r'''            if\( !handled && \( !compact_layout \|\|\n                             state\.focused_pane == crafting_browser_pane::categories \) && sidebar_pos \) \{\n                for\( const auto &hit : sidebar_hits \) \{.*?\n                \}\n            \}''',
    '''            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::categories ) && sidebar_pos ) {
                const std::optional<int> hit = sidebar_hits.hit( *sidebar_pos );
                if( hit ) {
                    const crafting_sidebar_entry &entry = sidebar_entries[*hit];
                    if( entry.type == crafting_sidebar_entry_type::filter ) {
                        if( entry.category == "FILTER_CRAFTABLE" ) {
                            state.filters.toggle( crafting_filter::craftable );
                        } else if( entry.category == "FILTER_MEMORIZED" ) {
                            state.filters.toggle( crafting_filter::memorized );
                        } else if( entry.category == "FILTER_UNREAD" && highlight_unread_recipes ) {
                            state.filters.toggle( crafting_filter::unread );
                        }
                    } else {
                        state.selected_category = entry.category;
                        state.selected_subcategory = entry.subcategory;
                        if( compact_layout ) {
                            state.focused_pane = crafting_browser_pane::recipes;
                        }
                    }
                    recalc = true;
                    handled = true;
                }
            }''',
)

regex_once(
    "inspector action input",
    r'''            if\( !handled && \( !compact_layout \|\|\n                             state\.focused_pane == crafting_browser_pane::inspector \) && inspector_pos \) \{.*?\n            \}\n            if\( !handled && actions_pos \) \{.*?\n            \}''',
    '''            if( !handled && ( !compact_layout ||
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
            }''',
)

regex_once(
    "recipe semantic click and double click",
    r'''            if\( !handled && \( !compact_layout \|\|\n                             state\.focused_pane == crafting_browser_pane::recipes \) && recipes_pos \) \{\n                for\( const auto &hit : recipe_hits \) \{.*?\n                \}\n            \}''',
    '''            if( !handled && ( !compact_layout ||
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
            }''',
)

regex_once(
    "recipe semantic right click",
    r'''        \} else if\( action == "SEC_SELECT" \) \{\n            if\( \( !compact_layout \|\|\n                  state\.focused_pane == crafting_browser_pane::recipes \) && recipes_pos \) \{\n                for\( const auto &hit : recipe_hits \) \{.*?\n                \}\n            \}\n            continue;\n        \}''',
    '''        } else if( action == "SEC_SELECT" ) {
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                const std::optional<int> hit = recipe_hits.hit( *recipes_pos );
                if( hit ) {
                    select_index( *hit, false );
                    state.context_open = true;
                    state.context_pos = *recipes_pos;
                }
            }
            continue;
        }''',
)

replace_once(
    "wheel scroll models",
    '''            if( compact_layout ) {
                if( state.focused_pane == crafting_browser_pane::categories ) {
                    state.category_scroll = std::max( 0, state.category_scroll + direction );
                } else if( state.focused_pane == crafting_browser_pane::recipes ) {
                    state.recipe_scroll = std::max( 0, state.recipe_scroll + direction * 3 );
                } else {
                    state.inspector_scroll = std::max( 0, state.inspector_scroll + direction * 3 );
                }
            } else if( sidebar_pos ) {
                state.category_scroll = std::max( 0, state.category_scroll + direction );
            } else if( recipes_pos ) {
                state.recipe_scroll = std::max( 0, state.recipe_scroll + direction * 3 );
            } else if( inspector_pos ) {
                state.inspector_scroll = std::max( 0, state.inspector_scroll + direction * 3 );
            }''',
    '''            if( compact_layout ) {
                if( state.focused_pane == crafting_browser_pane::categories ) {
                    state.category_scroll.scroll_by( direction );
                } else if( state.focused_pane == crafting_browser_pane::recipes ) {
                    state.recipe_scroll.scroll_by( direction * 3 );
                } else {
                    state.inspector_scroll.scroll_by( direction * 3 );
                }
            } else if( sidebar_pos ) {
                state.category_scroll.scroll_by( direction );
            } else if( recipes_pos ) {
                state.recipe_scroll.scroll_by( direction * 3 );
            } else if( inspector_pos ) {
                state.inspector_scroll.scroll_by( direction * 3 );
            }''',
)

replace_once(
    "inspector keyboard scrolling",
    '''        } else if( action == "SCROLL_RECIPE_INFO_UP" || action == "SCROLL_ITEM_INFO_UP" ) {
            state.inspector_scroll = std::max( 0, state.inspector_scroll -
                                              std::max( 1, getmaxy( w_inspector ) - 7 ) );
        } else if( action == "SCROLL_RECIPE_INFO_DOWN" || action == "SCROLL_ITEM_INFO_DOWN" ) {
            state.inspector_scroll += std::max( 1, getmaxy( w_inspector ) - 7 );''',
    '''        } else if( action == "SCROLL_RECIPE_INFO_UP" || action == "SCROLL_ITEM_INFO_UP" ) {
            state.inspector_scroll.page_by( -1 );
        } else if( action == "SCROLL_RECIPE_INFO_DOWN" || action == "SCROLL_ITEM_INFO_DOWN" ) {
            state.inspector_scroll.page_by( 1 );''',
)

text = text.replace('if( state.unread_only ) {',
                    'if( state.filters.contains( crafting_filter::unread ) ) {')

replace_once(
    "final selection ensure visible",
    '''        const int new_index = selected_index();
        if( new_index >= 0 ) {
            if( new_index < state.recipe_scroll ) {
                state.recipe_scroll = new_index;
            } else if( new_index >= state.recipe_scroll + visible_recipes ) {
                state.recipe_scroll = new_index - visible_recipes + 1;
            }
        }''',
    '''        const int new_index = selected_index();
        state.recipe_scroll.set_content_size( static_cast<int>( current.size() ) )
        .set_viewport_size( visible_recipes );
        if( new_index >= 0 ) {
            state.recipe_scroll.ensure_visible( new_index );
        }''',
)

# The project is still compiled as C++17 in the Windows full-feature build.
text = text.replace('qry.starts_with( "c:" )', 'qry.rfind( "c:", 0 ) == 0')

# All raw browser scroll integer operations and bespoke button vectors should be gone.
for forbidden in (
    'crafting_browser_button', 'pane_hits', 'inspector_buttons', 'toolbar_buttons',
    'context_buttons', 'last_clicked_recipe', 'last_click_time',
    'state.craftable_only', 'state.memorized_only', 'state.unread_only',
):
    if forbidden in text:
        raise SystemExit(f"migration incomplete, forbidden token remains: {forbidden}")

path.write_text(text, encoding="utf-8")
Path('/tmp/branch_patch_commit_message').write_text(
    'Migrate crafting browser to reusable UI helpers\n', encoding='utf-8'
)
