from pathlib import Path
import re

path = Path('src/veh_interact.cpp')
text = path.read_text()

replacement = r'''shared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor( map &here )
{
    shared_ptr_fast<ui_adaptor> current_ui = ui.lock();
    if( !current_ui ) {
        ui = current_ui = make_shared_fast<ui_adaptor>();
        current_ui->on_screen_resize( [this]( ui_adaptor & current_ui ) {
            if( ui_hidden ) {
                current_ui.position( point::zero, point::zero );
                return;
            }
            allocate_windows();
            current_ui.position_from_window( catacurses::stdscr );
        } );
        current_ui->mark_resize();
        current_ui->on_redraw( [&here, this]( const ui_adaptor & ) {
            if( ui_hidden ) {
                return;
            }
            display_grid();
            display_name();
            display_stats( here );
            display_veh( here );
            if( refuel_info ) {
                // Preserve the regular editor behind the compact modal.
                display_part_inspector();
                display_part_details();
                display_refuel_pane( here );
                display_mode( here );
#if defined(TILES)
                // SDL map previews are outside curses window ordering and can
                // otherwise draw over the modal.
                clear_map_preview_window();
#endif
                return;
            }

            const auto draw_message_window = [&]() {
                werase( w_msg );
                if( !msg.has_value() ) {
                    veh->print_vparts_descs( w_msg, getmaxy( w_msg ), getmaxx( w_msg ), cpart,
                                             start_at, start_limit );
                } else {
                    const int height = catacurses::getmaxy( w_msg );
                    const int width = catacurses::getmaxx( w_msg ) - 2;
                    std::vector<std::string> buffer;
                    std::istringstream msg_stream( msg.value() );
                    while( !msg_stream.eof() ) {
                        std::string line;
                        getline( msg_stream, line );
                        if( utf8_width( line ) <= width ) {
                            buffer.emplace_back( line );
                        } else {
                            std::vector<std::string> folded = foldstring( line, width );
                            std::copy( folded.begin(), folded.end(), std::back_inserter( buffer ) );
                        }
                    }
                    const int page_height = std::max( 1, height - 1 );
                    const int pages = static_cast<int>( buffer.size() / page_height );
                    w_msg_scroll_offset = clamp( w_msg_scroll_offset, 0, pages );
                    for( int line = 0; line < height; ++line ) {
                        const int idx = w_msg_scroll_offset * page_height + line;
                        if( static_cast<size_t>( idx ) >= buffer.size() ) {
                            break;
                        }
                        nc_color dummy = c_unset;
                        print_colored_text( w_msg, point( 1, line ), dummy, c_unset, buffer[idx] );
                    }
                }
                wnoutrefresh( w_msg );
            };

            if( !install_info && !remove_info ) {
                display_part_inspector();
                if( msg.has_value() ) {
                    draw_message_window();
                } else {
                    display_part_details();
                }
            } else {
                werase( w_parts );
                wnoutrefresh( w_parts );
                draw_message_window();

                if( install_info ) {
                    display_list( install_info->pos, install_info->tab_vparts, 2 );
                    display_details( sel_vpart_info );
                } else {
                    display_details( sel_vpart_info );
                    display_overview( here );
                }
            }
            display_editor_context_menu();
            display_mode( here );
            display_live_preview( here );
        } );
    }
    return current_ui;
}

void veh_interact::hide_ui( map &here, const bool hide )
{
    if( hide != ui_hidden ) {
        ui_hidden = hide;
        create_or_get_ui_adaptor( here )->mark_resize();
    }
}

void veh_interact::do_main_loop( map &here )
{
    bool finish = false;
    Character &player_character = get_player_character();
    const bool owned_by_player = veh->handle_potential_theft( player_character, true );
    faction *owner_fac;
    if( veh->has_owner() ) {
        owner_fac = g->faction_manager_ptr->get( veh->get_owner() );
    } else {
        owner_fac = g->faction_manager_ptr->get( faction_no_faction );
    }

    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );

    while( !finish ) {
        calc_overview( here );
        if( install_info ) {
            refresh_install_candidates();
            sync_install_selection( here );
        }
        ui_manager::redraw();
        const int description_scroll_lines = std::max( 1, catacurses::getmaxy( w_msg ) - 4 );
        std::string action = main_context.handle_input();

        const bool mouse_handled = handle_editor_mouse( here, action );
        if( !pending_editor_action.empty() ) {
            action = pending_editor_action;
            pending_editor_action.clear();
        } else if( mouse_handled ) {
            if( sel_cmd != ' ' ) {
                finish = true;
            }
            continue;
        }

        if( refuel_info ) {
            using refuel_stage = refuel_info_t::stage_t;
            if( action == "QUIT" ) {
                if( refuel_info->stage == refuel_stage::tank ) {
                    close_refuel_mode();
                } else {
                    refuel_info->stage = refuel_stage::tank;
                    refuel_info->source_range_anchor = -1;
                    msg.reset();
                    refresh_refuel_sources( here );
                }
                continue;
            }

            if( action == "UP" || action == "DOWN" ||
                action == "PAGE_UP" || action == "PAGE_DOWN" ) {
                const int page = std::max( 1, getmaxy( w_refuel_overlay ) - 8 );
                const int delta = action == "UP" ? -1 : action == "DOWN" ? 1 :
                                  action == "PAGE_UP" ? -page : page;
                if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {
                    refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,
                                            static_cast<int>( refuel_info->tanks.size() ) - 1 );
                } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {
                    refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,
                                              static_cast<int>( refuel_info->sources.size() ) - 1 );
                } else if( refuel_info->stage == refuel_stage::quick_fuel &&
                           !refuel_info->quick_fuels.empty() ) {
                    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,
                                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
                }
                continue;
            }

            if( action == "REFILL" || action == "CONFIRM" ) {
                if( refuel_info->stage == refuel_stage::tank ) {
                    if( !refuel_info->tanks.empty() ) {
                        refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,
                                                static_cast<int>( refuel_info->tanks.size() ) - 1 );
                        const int part_index = refuel_info->tanks[refuel_info->tank_pos];
                        if( part_index >= 0 && part_index < veh->part_count() &&
                            veh->part( part_index ).can_reload() ) {
                            refuel_info->selected_tank_slot = refuel_info->tank_pos;
                            refuel_info->stage = refuel_stage::source;
                            refuel_info->source_pos = 0;
                            refuel_info->source_range_anchor = -1;
                            refresh_refuel_sources( here );
                        } else {
                            msg = _( "That fuel store is already full or cannot currently be refilled." );
                        }
                    }
                } else if( refuel_info->stage == refuel_stage::source ) {
                    const bool any_selected = std::any_of( refuel_info->sources.begin(),
                                              refuel_info->sources.end(),
                    []( const refuel_info_t::source_t &entry ) {
                        return entry.selected;
                    } );
                    if( !any_selected && !refuel_info->sources.empty() ) {
                        refuel_info->sources[refuel_info->source_pos].selected = true;
                    }
                    if( queue_selected_refill_source( here ) ) {
                        finish = true;
                    }
                } else if( queue_quick_refill_all( here ) ) {
                    finish = true;
                }
                continue;
            }

            // Refuel modal consumes unrelated editor/navigation input rather than
            // moving the vehicle mount behind it.
            continue;
        } else if( install_info ) {
            if( action == "QUIT" ) {
                close_install_mode();
                continue;
            }
            if( action == "FILTER" ) {
                string_input_popup()
                .title( _( "Search installable parts" ) )
                .width( 50 )
                .description( _( "Search" ) )
                .max_length( 100 )
                .edit( install_info->filter );
                install_search_cache = install_info->filter;
                install_info->pos = 0;
                install_info->dirty = true;
                refresh_install_candidates();
                sync_install_selection( here );
                continue;
            }
            if( action == "INSTALL" || action == "CONFIRM" ) {
                if( confirm_install( here ) ) {
                    finish = true;
                }
                continue;
            }
            if( action == "UP" || action == "DOWN" || action == "PAGE_UP" || action == "PAGE_DOWN" ) {
                if( !install_info->tab_vparts.empty() ) {
                    const int old_pos = install_info->pos;
                    if( action == "UP" ) {
                        install_info->pos = std::max( 0, install_info->pos - 1 );
                    } else if( action == "DOWN" ) {
                        install_info->pos = std::min(
                                                static_cast<int>( install_info->tab_vparts.size() ) - 1,
                                                install_info->pos + 1 );
                    } else {
                        const int page = std::max( 1, getmaxy( w_list ) - 4 );
                        const int delta = action == "PAGE_UP" ? -page : page;
                        install_info->pos = std::clamp(
                                                install_info->pos + delta, 0,
                                                static_cast<int>( install_info->tab_vparts.size() ) - 1 );
                    }
                    if( install_info->pos != old_pos ) {
                        sync_install_selection( here );
                    }
                }
                continue;
            }
            if( action == "DESC_LIST_DOWN" ) {
                ++w_msg_scroll_offset;
                continue;
            }
            if( action == "DESC_LIST_UP" ) {
                w_msg_scroll_offset = std::max( 0, w_msg_scroll_offset - 1 );
                continue;
            }
        } else {
            msg.reset();
        }

        if( const std::optional<tripoint_rel_ms> vec = main_context.get_direction_rel_ms( action ) ) {
            move_cursor( here, vec->xy() );
        } else if( action == "QUIT" ) {
            finish = true;
        } else if( action == "INSTALL" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_install( here );
            }
        } else if( action == "REPAIR" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_repair( here );
            }
        } else if( action == "MEND" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_mend( here );
            }
        } else if( action == "REFILL" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_refill( here );
            }
        } else if( action == "REMOVE" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_remove( here );
            }
        } else if( action == "RENAME" ) {
            if( owned_by_player ) {
                do_rename();
            } else if( owner_fac ) {
                popup( _( "You cannot rename this vehicle as it is owned by: %s." ), _( owner_fac->name ) );
            }
        } else if( action == "SIPHON" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_siphon( here );
                finish = !player_character.activity.is_null();
                if( !finish ) {
                    cache_tool_availability();
                }
            }
        } else if( action == "UNLOAD" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                finish = do_unload( here );
            }
        } else if( action == "CHANGE_SHAPE" ) {
            sel_cmd = 'p';
        } else if( action == "ASSIGN_CREW" ) {
            if( owned_by_player ) {
                do_assign_crew( here );
            } else if( owner_fac ) {
                popup( _( "You cannot assign crew on this vehicle as it is owned by: %s." ),
                       _( owner_fac->name ) );
            }
        } else if( action == "RELABEL" ) {
            if( owned_by_player ) {
                do_relabel( here );
            } else if( owner_fac ) {
                popup( _( "You cannot relabel this vehicle as it is owned by: %s." ), _( owner_fac->name ) );
            }
        } else if( action == "FUEL_LIST_DOWN" ) {
            move_fuel_cursor( here, 1 );
        } else if( action == "FUEL_LIST_UP" ) {
            move_fuel_cursor( here, -1 );
        } else if( action == "OVERVIEW_DOWN" ) {
            move_overview_line( 1 );
        } else if( action == "OVERVIEW_UP" ) {
            move_overview_line( -1 );
        } else if( action == "DESC_LIST_DOWN" ) {
            if( !remove_info ) {
                scroll_part_details( 1 );
            } else {
                move_cursor( here, point_rel_ms::zero, 1 );
            }
        } else if( action == "DESC_LIST_UP" ) {
            if( !remove_info ) {
                scroll_part_details( -1 );
            } else {
                move_cursor( here, point_rel_ms::zero, -1 );
            }
        } else if( action == "PAGE_DOWN" ) {
            if( !remove_info ) {
                scroll_part_details( description_scroll_lines );
            } else {
                move_cursor( here, point_rel_ms::zero, description_scroll_lines );
            }
        } else if( action == "PAGE_UP" ) {
            if( !remove_info ) {
                scroll_part_details( -description_scroll_lines );
            } else {
                move_cursor( here, point_rel_ms::zero, -description_scroll_lines );
            }
        }
        if( sel_cmd != ' ' ) {
            finish = true;
        }
    }
}

void veh_interact::cache_tool_availability()'''

pattern = re.compile(
    r'shared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor\( map &here \)\n\{.*?\nvoid veh_interact::cache_tool_availability\(\)',
    re.S,
)
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f'expected one damaged UI/main-loop block, found {count}')

# Guard against the exact failure mode that caused the MSVC cascade.
redraw_start = text.index('shared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor')
main_start = text.index('void veh_interact::do_main_loop', redraw_start)
redraw_block = text[redraw_start:main_start]
assert 'continue;' not in redraw_block
assert 'action ==' not in redraw_block
assert 'owner_fac' not in redraw_block
assert 'while( !finish )' in text[main_start:text.index('void veh_interact::cache_tool_availability', main_start)]
assert text.count('void veh_interact::do_main_loop( map &here )') == 1

path.write_text(text)
