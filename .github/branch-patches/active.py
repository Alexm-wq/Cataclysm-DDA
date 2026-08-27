from pathlib import Path

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
'''    struct browser_list_row {
        const recipe *rec = nullptr;
        const crafting_group *group = nullptr;
        int recipe_index = -1;
        std::string heading;
    };
''',
'''    struct browser_list_row {
        const recipe *rec = nullptr;
        const crafting_group *group = nullptr;
        int recipe_index = -1;
        std::string heading;
        std::vector<int> recipe_indices;
    };
''',
"extend browser recipe row",
)

replace_once(
'''    ui_action_strip pane_actions;
    ui_action_strip inspector_actions;
    ui_action_strip toolbar_actions;
''',
'''    ui_action_strip pane_actions;
    ui_action_strip recipe_method_actions;
    ui_action_strip inspector_actions;
    ui_action_strip toolbar_actions;
''',
"add recipe method action strip",
)

replace_once(
'''    const auto selected_row_index = [&]() -> int {
        if( state.selected_recipe == nullptr ) {
            return -1;
        }
        const auto found = std::find_if( recipe_rows.begin(), recipe_rows.end(),
        [&]( const browser_list_row & row ) {
            return row.rec == state.selected_recipe;
        } );
        return found == recipe_rows.end() ? -1 : static_cast<int>( found - recipe_rows.begin() );
    };
''',
'''    const auto selected_row_index = [&]() -> int {
        const int selected = selected_index();
        if( selected < 0 ) {
            return -1;
        }
        const auto found = std::find_if( recipe_rows.begin(), recipe_rows.end(),
        [&]( const browser_list_row & row ) {
            return row.rec != nullptr &&
                   std::find( row.recipe_indices.begin(), row.recipe_indices.end(), selected ) !=
                   row.recipe_indices.end();
        } );
        return found == recipe_rows.end() ? -1 : static_cast<int>( found - recipe_rows.begin() );
    };
''',
"make row selection alternate-aware",
)

replace_once(
'''    const auto select_row = [&]( int requested, const int direction, const bool mark_read ) {
        if( recipe_rows.empty() ) {
            state.selected_recipe = nullptr;
            return;
        }
        requested = std::clamp( requested, 0, static_cast<int>( recipe_rows.size() ) - 1 );
        while( requested >= 0 && requested < static_cast<int>( recipe_rows.size() ) ) {
            if( recipe_rows[requested].rec != nullptr ) {
                select_index( recipe_rows[requested].recipe_index, mark_read );
                return;
            }
            requested += direction;
        }
    };

    const auto selected_availability = [&]() -> availability * {
''',
'''    const auto select_row = [&]( int requested, const int direction, const bool mark_read ) {
        if( recipe_rows.empty() ) {
            state.selected_recipe = nullptr;
            return;
        }
        requested = std::clamp( requested, 0, static_cast<int>( recipe_rows.size() ) - 1 );
        while( requested >= 0 && requested < static_cast<int>( recipe_rows.size() ) ) {
            if( recipe_rows[requested].rec != nullptr ) {
                select_index( recipe_rows[requested].recipe_index, mark_read );
                return;
            }
            requested += direction;
        }
    };

    const auto cycle_selected_recipe = [&]( const int direction ) {
        const int row_index = selected_row_index();
        if( row_index < 0 || row_index >= static_cast<int>( recipe_rows.size() ) ) {
            return false;
        }
        browser_list_row &row = recipe_rows[row_index];
        if( row.recipe_indices.size() <= 1 ) {
            return false;
        }

        const int selected = selected_index();
        auto found = std::find( row.recipe_indices.begin(), row.recipe_indices.end(), selected );
        int method_index = found == row.recipe_indices.end() ? 0 :
                           static_cast<int>( found - row.recipe_indices.begin() );
        method_index = ( method_index + direction + static_cast<int>( row.recipe_indices.size() ) ) %
                       static_cast<int>( row.recipe_indices.size() );
        const int next_recipe_index = row.recipe_indices[method_index];
        row.recipe_index = next_recipe_index;
        row.rec = current[next_recipe_index];
        select_index( next_recipe_index, false );
        workspace_status = string_format( _( "Recipe %d of %d selected." ), method_index + 1,
                                          static_cast<int>( row.recipe_indices.size() ) );
        return true;
    };

    const auto selected_availability = [&]() -> availability * {
''',
"add alternate recipe cycling",
)

old_rows = '''        for( const crafting_group *group : visible_groups ) {
            recipe_rows.push_back( { nullptr, group, -1, group->name.translated() } );
            for( const int recipe_index : grouped_recipe_indices[group] ) {
                recipe_rows.push_back( { current[recipe_index], group, recipe_index, std::string() } );
            }
        }
        for( const auto &entry : ungrouped_recipe_indices ) {
            const std::string heading = string_format( _( "%s — other recipes" ),
                                        _( get_subcat_unprefixed( entry.first.first, entry.first.second ) ) );
            recipe_rows.push_back( { nullptr, nullptr, -1, heading } );
            for( const int recipe_index : entry.second ) {
                recipe_rows.push_back( { current[recipe_index], nullptr, recipe_index, std::string() } );
            }
        }

        const auto preserved = std::find( current.begin(), current.end(), previous_recipe );
        if( preserved != current.end() ) {
            state.selected_recipe = *preserved;
        } else if( !current.empty() ) {
            const int replacement = std::clamp( previous_index < 0 ? 0 : previous_index, 0,
                                                static_cast<int>( current.size() ) - 1 );
            state.selected_recipe = current[replacement];
            state.inspector_scroll.scroll_to_start();
        } else {
            state.selected_recipe = nullptr;
            state.inspector_scroll.scroll_to_start();
        }
'''
new_rows = '''        const auto append_collapsed_rows = [&]( const std::vector<int> &indices,
        const crafting_group * group ) {
            std::vector<std::vector<int>> collapsed;
            for( const int recipe_index : indices ) {
                const recipe *rec = current[recipe_index];
                auto found = std::find_if( collapsed.begin(), collapsed.end(),
                [&]( const std::vector<int> & bucket ) {
                    const recipe *first = current[bucket.front()];
                    return first->result() == rec->result() && first->variant() == rec->variant();
                } );
                if( found == collapsed.end() ) {
                    collapsed.push_back( { recipe_index } );
                } else {
                    found->push_back( recipe_index );
                }
            }

            for( std::vector<int> &bucket : collapsed ) {
                int active_index = bucket.front();
                if( previous_recipe != nullptr ) {
                    const auto previous = std::find_if( bucket.begin(), bucket.end(),
                    [&]( const int recipe_index ) {
                        return current[recipe_index] == previous_recipe;
                    } );
                    if( previous != bucket.end() ) {
                        active_index = *previous;
                    }
                }
                recipe_rows.push_back( { current[active_index], group, active_index, std::string(),
                                         std::move( bucket ) } );
            }
        };

        for( const crafting_group *group : visible_groups ) {
            recipe_rows.push_back( { nullptr, group, -1, group->name.translated(), {} } );
            append_collapsed_rows( grouped_recipe_indices[group], group );
        }
        for( const auto &entry : ungrouped_recipe_indices ) {
            const std::string heading = string_format( _( "%s — other recipes" ),
                                        _( get_subcat_unprefixed( entry.first.first, entry.first.second ) ) );
            recipe_rows.push_back( { nullptr, nullptr, -1, heading, {} } );
            append_collapsed_rows( entry.second, nullptr );
        }

        const auto preserved = std::find( current.begin(), current.end(), previous_recipe );
        if( preserved != current.end() ) {
            state.selected_recipe = *preserved;
        } else {
            state.selected_recipe = nullptr;
            const crafting_group *previous_group = previous_recipe == nullptr ? nullptr :
                                                   crafting_group_for_recipe( previous_recipe->ident() );
            if( previous_recipe != nullptr ) {
                const auto same_item_row = std::find_if( recipe_rows.begin(), recipe_rows.end(),
                [&]( const browser_list_row & row ) {
                    return row.rec != nullptr && row.group == previous_group &&
                           row.rec->result() == previous_recipe->result() &&
                           row.rec->variant() == previous_recipe->variant();
                } );
                if( same_item_row != recipe_rows.end() ) {
                    state.selected_recipe = same_item_row->rec;
                }
            }
            if( state.selected_recipe == nullptr ) {
                const auto first_recipe_row = std::find_if( recipe_rows.begin(), recipe_rows.end(),
                []( const browser_list_row & row ) {
                    return row.rec != nullptr;
                } );
                if( first_recipe_row != recipe_rows.end() ) {
                    state.selected_recipe = first_recipe_row->rec;
                }
            }
            state.inspector_scroll.scroll_to_start();
        }
'''
replace_once(old_rows, new_rows, "collapse duplicate item rows")

replace_once(
'''            const std::string list_title = string_format( _( "RECIPES (%d)" ),
                                           static_cast<int>( current.size() ) );
''',
'''            const int visible_recipe_count = static_cast<int>( std::count_if(
                                                 recipe_rows.begin(), recipe_rows.end(),
            []( const browser_list_row & row ) {
                return row.rec != nullptr;
            } ) );
            const std::string list_title = string_format( _( "RECIPES (%d)" ), visible_recipe_count );
''',
"count displayed recipe rows",
)

replace_once(
'''                std::string name = prefix + rec->result_name( /*decorated=*/true );
                const std::string metadata = string_format( "D%d", rec->get_difficulty( *crafter ) );
''',
'''                std::string name = prefix + rec->result_name( /*decorated=*/true );
                name += string_format( " (%d)", static_cast<int>( list_row.recipe_indices.size() ) );
                const std::string metadata = string_format( "D%d", rec->get_difficulty( *crafter ) );
''',
"show alternate recipe count",
)

replace_once(
'''            const int inspector_first_row = 5;
''',
'''            const int inspector_first_row = 6;
''',
"make room for recipe cycling row",
)

replace_once(
'''            if( state.selected_recipe == nullptr ) {
                state.inspector_scroll.set_content_size( 0 );
                trim_and_print( w_inspector, point( 2, 1 ), std::max( 1, inspector_width - 4 ),
                                c_dark_gray, _( "Select a recipe to inspect it." ) );
            } else {
''',
'''            if( state.selected_recipe == nullptr ) {
                recipe_method_actions.clear();
                inspector_actions.clear();
                state.inspector_scroll.set_content_size( 0 );
                trim_and_print( w_inspector, point( 2, 1 ), std::max( 1, inspector_width - 4 ),
                                c_dark_gray, _( "Select a recipe to inspect it." ) );
            } else {
''',
"clear inspector controls when empty",
)

old_batch = '''                int batch_x = 1;
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
                wattron( w_inspector, c_dark_gray );
                mvwhline( w_inspector, point( 1, 4 ), LINE_OXOX, std::max( 0, inspector_width - 2 ) );
                wattroff( w_inspector, c_dark_gray );
'''
new_batch = '''                int method_count = 1;
                int method_index = 0;
                const int selected_recipe_row = selected_row_index();
                if( selected_recipe_row >= 0 ) {
                    const browser_list_row &row = recipe_rows[selected_recipe_row];
                    method_count = std::max( 1, static_cast<int>( row.recipe_indices.size() ) );
                    const int selected = selected_index();
                    const auto found = std::find( row.recipe_indices.begin(), row.recipe_indices.end(), selected );
                    if( found != row.recipe_indices.end() ) {
                        method_index = static_cast<int>( found - row.recipe_indices.begin() );
                    }
                }

                int method_x = 1;
                const std::string method_label = string_format( _( "Recipe %d/%d: " ), method_index + 1,
                                                 method_count );
                mvwprintz( w_inspector, point( method_x, 3 ), c_light_gray, "%s", method_label );
                method_x += utf8_width( method_label );
                const bool has_alternates = method_count > 1;
                std::vector<ui_action_entry> method_entries = {
                    { "[ < ]", "RECIPE_PREV", has_alternates, false,
                      _( "Only one recipe is available for this item." ) },
                    { "[ > ]", "RECIPE_NEXT", has_alternates, false,
                      _( "Only one recipe is available for this item." ) }
                };
                ui_action_strip_style method_style;
                method_style.decorate = false;
                method_style.gap = 1;
                recipe_method_actions.configure( w_inspector, point( method_x, 3 ),
                                                 std::move( method_entries ),
                                                 std::max( 1, inspector_width - method_x - 1 ), 1,
                                                 method_style );
                recipe_method_actions.draw( w_inspector );

                int batch_x = 1;
                mvwprintz( w_inspector, point( batch_x, 4 ), c_light_gray, "%s", _( "Batch: " ) );
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
                inspector_actions.configure( w_inspector, point( batch_x, 4 ),
                                             std::move( batch_entries ),
                                             std::max( 1, inspector_width - batch_x - 1 ), 1,
                                             batch_style );
                inspector_actions.draw( w_inspector );
                wattron( w_inspector, c_dark_gray );
                mvwhline( w_inspector, point( 1, 5 ), LINE_OXOX, std::max( 0, inspector_width - 2 ) );
                wattroff( w_inspector, c_dark_gray );
'''
replace_once(old_batch, new_batch, "add recipe cycling controls")

replace_once(
'''            inspector_actions.update_hover( ( !compact_layout ||
                                               state.focused_pane == crafting_browser_pane::inspector ) ?
                                              inspector_pos : std::nullopt );
''',
'''            recipe_method_actions.update_hover( ( !compact_layout ||
                                                    state.focused_pane == crafting_browser_pane::inspector ) ?
                                                   inspector_pos : std::nullopt );
            inspector_actions.update_hover( ( !compact_layout ||
                                               state.focused_pane == crafting_browser_pane::inspector ) ?
                                              inspector_pos : std::nullopt );
''',
"hover recipe method controls",
)

replace_once(
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
''',
'''            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::inspector ) && inspector_pos ) {
                const ui_action_result result = recipe_method_actions.handle_input( action, inspector_pos );
                if( result.type == ui_action_result_type::activated && result.entry ) {
                    action = result.entry->id;
                } else if( result.type == ui_action_result_type::disabled && result.entry ) {
                    workspace_status = result.entry->disabled_reason;
                }
                handled = result.consumed();
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
''',
"handle recipe method control clicks",
)

replace_once(
'''        } else if( action == "BATCH_DEC" ) {
            set_batch_size( state.batch_size - 1 );
''',
'''        } else if( action == "RECIPE_PREV" ) {
            cycle_selected_recipe( -1 );
        } else if( action == "RECIPE_NEXT" ) {
            cycle_selected_recipe( 1 );
        } else if( action == "BATCH_DEC" ) {
            set_batch_size( state.batch_size - 1 );
''',
"dispatch recipe cycling actions",
)

replace_once(
'''                for( const recipe *rec : current ) {
                    uistate.read_recipes.insert( rec->ident() );
                }
''',
'''                for( const browser_list_row &row : recipe_rows ) {
                    for( const int recipe_index : row.recipe_indices ) {
                        uistate.read_recipes.insert( current[recipe_index]->ident() );
                    }
                }
''',
"mark collapsed recipe methods read",
)

replace_once(
'''        state.recipe_scroll.set_content_size( static_cast<int>( current.size() ) )
        .set_viewport_size( visible_recipes );
''',
'''        state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )
        .set_viewport_size( visible_recipes );
''',
"keep scrollbar aligned with collapsed rows",
)

# Guard the intended behavior so later branch drift fails loudly instead of partially applying.
for required in (
    'name += string_format( " (%d)", static_cast<int>( list_row.recipe_indices.size() ) );',
    '"RECIPE_PREV"',
    '"RECIPE_NEXT"',
    'first->result() == rec->result() && first->variant() == rec->variant()',
    'state.recipe_scroll.set_content_size( static_cast<int>( recipe_rows.size() ) )',
):
    if required not in text:
        raise RuntimeError(f"missing expected patched fragment: {required}")

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Collapse alternate crafting recipes by item\n", encoding="utf-8"
)
