from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


root = Path('.')
options_path = root / 'src/options.cpp'
bionics_path = root / 'src/bionics_ui.cpp'
options = options_path.read_text()
bionics = bionics_path.read_text()

options = replace_once(
    options,
    '''void options_manager::add_options_debug()\n{\n    const auto add_empty_line = [&]() {\n        this->add_empty_line( "debug" );\n    };\n\n    add( "DEBUG_DIFFICULTIES", "debug", to_translation( "Show values for character creation" ),''',
    '''void options_manager::add_options_debug()\n{\n    const auto add_empty_line = [&]() {\n        this->add_empty_line( "debug" );\n    };\n\n    add( "UI_TEST_MODE", "debug", to_translation( "UI testing mode" ),\n         to_translation( "Expose development-only Test controls in modernized UI screens.  Each screen owns its own safe test fixtures behind this single setting, so future UI reworks can add their testing cases here without permanent debug-only buttons." ),\n         false\n       );\n\n    add_empty_line();\n\n    add( "DEBUG_DIFFICULTIES", "debug", to_translation( "Show values for character creation" ),''',
    'debug UI test option'
)

bionics = replace_once(
    bionics,
    '''static const itype_id itype_battery( "battery" );\nstatic const json_character_flag json_flag_BIONIC_GUN( "BIONIC_GUN" );''',
    '''static const itype_id itype_battery( "battery" );\nstatic const json_character_flag json_flag_BIONIC_FAULTY( "BIONIC_FAULTY" );\nstatic const json_character_flag json_flag_BIONIC_GUN( "BIONIC_GUN" );\nstatic const std::string bionic_ui_test_tag = "UI_TEST_FIXTURE";''',
    'bionics test constants'
)

bionics = replace_once(
    bionics,
    '''        void open_dropdown( const std::string &kind );\n        void dispatch( const std::string &action, std::optional<bio_uid> uid = std::nullopt );\n        void handoff( bio_uid uid, bool weapon_management );''',
    '''        void open_dropdown( const std::string &kind );\n        void apply_test_fixture( const std::string &fixture );\n        void dispatch( const std::string &action, std::optional<bio_uid> uid = std::nullopt );\n        void handoff( bio_uid uid, bool weapon_management );''',
    'bionics test method declaration'
)

old_toolbar = '''void bionics_window::configure_toolbar()\n{\n    std::vector<ui_action_strip_item> actions = {\n        {\n            ui_action_entry( string_format( _( "Activatable (%d)" ), tabs[0].rows.size() ),\n                             "ACTIVE_TAB", true, tab == 0 )\n        },\n        {\n            ui_action_entry( string_format( _( "Passive (%d)" ), tabs[1].rows.size() ),\n                             "PASSIVE_TAB", true, tab == 1 )\n        },\n        {\n            ui_action_entry( string_format( _( "Sort: %s" ), sort_label( uistate.bionic_sort_mode ) ),\n                             "SORT", true, false, std::string(), std::nullopt, true ), 1\n        },\n        {\n            ui_action_entry( single_pane && details_focus ? _( "Back to list" ) : _( "Back" ),\n                             "BACK" ), 2, ui_action_alignment::right\n        }\n    };\n    toolbar.configure( window, point( 1, 1 ), std::move( actions ),\n                       getmaxx( window ) - 2, std::min( 4, std::max( 1, getmaxy( window ) - 6 ) ) );\n}\n'''
new_toolbar = '''void bionics_window::configure_toolbar()\n{\n    std::vector<ui_action_strip_item> actions = {\n        {\n            ui_action_entry( string_format( _( "Activatable (%d)" ), tabs[0].rows.size() ),\n                             "ACTIVE_TAB", true, tab == 0 )\n        },\n        {\n            ui_action_entry( string_format( _( "Passive (%d)" ), tabs[1].rows.size() ),\n                             "PASSIVE_TAB", true, tab == 1 )\n        },\n        {\n            ui_action_entry( string_format( _( "Sort: %s" ), sort_label( uistate.bionic_sort_mode ) ),\n                             "SORT", true, false, std::string(), std::nullopt, true ), 1\n        }\n    };\n    if( get_option<bool>( "UI_TEST_MODE" ) ) {\n        actions.push_back( { ui_action_entry( _( "Test" ), "TEST", true, false,\n                                              std::string(), std::nullopt, true ), 1 } );\n    }\n    actions.push_back( {\n        ui_action_entry( single_pane && details_focus ? _( "Back to list" ) : _( "Back" ),\n                         "BACK" ), 2, ui_action_alignment::right\n    } );\n    toolbar.configure( window, point( 1, 1 ), std::move( actions ),\n                       getmaxx( window ) - 2, std::min( 4, std::max( 1, getmaxy( window ) - 6 ) ) );\n}\n'''
bionics = replace_once(bionics, old_toolbar, new_toolbar, 'bionics toolbar Test button')

bionics = replace_once(
    bionics,
    '''        dropdown_trigger = toolbar.bounds_for_id( "SORT" );\n    } else if( bionic *bio = selected(); bio && bio->supports_safe_fuel() ) {''',
    '''        dropdown_trigger = toolbar.bounds_for_id( "SORT" );\n    } else if( kind == "TEST" && get_option<bool>( "UI_TEST_MODE" ) ) {\n        choices.emplace_back( _( "Grant bionics test suite" ), "GRANT_SUITE" );\n        choices.emplace_back( _( "Add 500 battery charges" ), "ADD_BATTERY" );\n        choices.emplace_back( _( "Set full power" ), "POWER_FULL" );\n        choices.emplace_back( _( "Set low power (10%)" ), "POWER_LOW" );\n        choices.emplace_back( _( "Set empty power" ), "POWER_EMPTY" );\n        choices.emplace_back( _( "Apply mixed active / sprite / fuel states" ), "MIXED_STATES" );\n        choices.emplace_back( _( "Incapacitate selected bionic" ), "INCAPACITATE_SELECTED" );\n        choices.emplace_back( _( "Clear selected incapacitation" ), "CLEAR_INCAPACITATION" );\n        choices.emplace_back( _( "Clear test bionics" ), "CLEAR_SUITE" );\n        dropdown_trigger = toolbar.bounds_for_id( "TEST" );\n    } else if( bionic *bio = selected(); bio && bio->supports_safe_fuel() ) {''',
    'bionics Test dropdown'
)

marker = '''void bionics_window::handoff( bio_uid uid, bool weapon_management )\n{'''
fixture_impl = r'''void bionics_window::apply_test_fixture( const std::string &fixture )
{
    if( !get_option<bool>( "UI_TEST_MODE" ) ) {
        return;
    }

    const auto test_bionics = [&]() {
        std::vector<bionic *> result;
        for( bionic &bio : *p.my_bionics ) {
            if( bio.has_flag( bionic_ui_test_tag ) ) {
                result.push_back( &bio );
            }
        }
        return result;
    };

    if( fixture == "GRANT_SUITE" ) {
        std::set<bio_uid> existing;
        for( const bionic &bio : *p.my_bionics ) {
            existing.insert( bio.get_uid() );
        }

        std::vector<bionic_id> chosen;
        const auto eligible = [&]( const bionic_data & data ) {
            return !data.included && !data.activated_on_install && !data.cant_remove_reason &&
                   !data.has_flag( json_flag_BIONIC_FAULTY ) && !p.has_bionic( data.id ) &&
                   std::find( chosen.begin(), chosen.end(), data.id ) == chosen.end();
        };
        const auto add_matching = [&]( auto predicate, int limit ) {
            int added = 0;
            for( const bionic_data &data : bionic_data::get_all() ) {
                if( added >= limit ) {
                    break;
                }
                if( eligible( data ) && predicate( data ) ) {
                    chosen.push_back( data.id );
                    ++added;
                }
            }
        };

        // Cover the important UI shapes first, then fill out the list so scrolling,
        // sorting and clipping can be tested without depending on a specific character.
        add_matching( []( const bionic_data & d ) { return d.activated; }, 6 );
        add_matching( []( const bionic_data & d ) { return !d.activated; }, 6 );
        add_matching( []( const bionic_data & d ) {
            return !d.fuel_opts.empty() || d.is_remote_fueled;
        }, 4 );
        add_matching( []( const bionic_data & d ) {
            return d.has_flag( json_flag_BIONIC_GUN ) || !d.fake_weapon.is_empty() ||
                   !d.installable_weapon_flags.empty();
        }, 4 );
        add_matching( []( const bionic_data & d ) {
            return d.power_over_time > 0_J || d.power_trigger > 0_J || d.power_deactivate > 0_J;
        }, 4 );
        add_matching( []( const bionic_data & ) { return true; },
                      std::max( 0, 30 - static_cast<int>( chosen.size() ) ) );

        for( const bionic_id &id : chosen ) {
            p.add_bionic( id, 0, true );
        }

        int added = 0;
        for( bionic &bio : *p.my_bionics ) {
            if( existing.count( bio.get_uid() ) == 0 ) {
                bio.set_flag( bionic_ui_test_tag );
                ++added;
            }
        }

        p.update_bionic_power_capacity();
        if( p.get_max_power_level() < 1000_kJ ) {
            p.set_max_power_level( 1000_kJ );
        }
        p.set_power_level( p.get_max_power_level() );

        int active_index = 0;
        int sprite_index = 0;
        int fuel_index = 0;
        bool incapacitated = false;
        for( bionic *bio : test_bionics() ) {
            bio->show_sprite = ( sprite_index++ % 3 ) != 1;
            if( bio->info().activated ) {
                bio->powered = ( active_index++ % 3 ) == 1;
                bio->incapacitated_time = 0_turns;
                if( !incapacitated && !bio->powered ) {
                    bio->incapacitated_time = 10_minutes;
                    incapacitated = true;
                }
            }
            if( bio->supports_safe_fuel() ) {
                bio->set_safe_fuel_thresh(
                    bionics_ui::fuel_thresholds[fuel_index++ % bionics_ui::fuel_thresholds.size()] );
            }
        }
        status = string_format( _( "Added %d UI-test bionics and prepared mixed states." ), added );
    } else if( fixture == "ADD_BATTERY" ) {
        item battery( itype_battery, calendar::turn, 500 );
        p.i_add_or_drop( battery );
        status = _( "Added 500 battery charges." );
    } else if( fixture == "POWER_FULL" ) {
        if( p.get_max_power_level() <= 0_J ) {
            p.set_max_power_level( 1000_kJ );
        }
        p.set_power_level( p.get_max_power_level() );
        status = _( "Bionic power set to full." );
    } else if( fixture == "POWER_LOW" ) {
        if( p.get_max_power_level() <= 0_J ) {
            p.set_max_power_level( 1000_kJ );
        }
        p.set_power_level( p.get_max_power_level() / 10 );
        status = _( "Bionic power set to 10%." );
    } else if( fixture == "POWER_EMPTY" ) {
        p.set_power_level( 0_J );
        status = _( "Bionic power emptied." );
    } else if( fixture == "MIXED_STATES" ) {
        int active_index = 0;
        int sprite_index = 0;
        int fuel_index = 0;
        bool incapacitated = false;
        for( bionic *bio : test_bionics() ) {
            bio->show_sprite = ( sprite_index++ % 3 ) != 1;
            bio->incapacitated_time = 0_turns;
            if( bio->info().activated ) {
                bio->powered = ( active_index++ % 3 ) == 1;
                if( !incapacitated && !bio->powered ) {
                    bio->incapacitated_time = 10_minutes;
                    incapacitated = true;
                }
            }
            if( bio->supports_safe_fuel() ) {
                bio->set_safe_fuel_thresh(
                    bionics_ui::fuel_thresholds[fuel_index++ % bionics_ui::fuel_thresholds.size()] );
            }
        }
        status = _( "Applied mixed states to UI-test bionics." );
    } else if( fixture == "INCAPACITATE_SELECTED" ) {
        if( bionic *bio = selected() ) {
            bio->incapacitated_time = 10_minutes;
            status = _( "Selected bionic incapacitated for 10 minutes." );
        } else {
            status = _( "Select a bionic first." );
        }
    } else if( fixture == "CLEAR_INCAPACITATION" ) {
        if( bionic *bio = selected() ) {
            bio->incapacitated_time = 0_turns;
            status = _( "Selected bionic incapacitation cleared." );
        } else {
            status = _( "Select a bionic first." );
        }
    } else if( fixture == "CLEAR_SUITE" ) {
        std::vector<bio_uid> remove;
        for( const bionic &bio : *p.my_bionics ) {
            if( bio.has_flag( bionic_ui_test_tag ) ) {
                remove.push_back( bio.get_uid() );
            }
        }
        int removed = 0;
        for( const bio_uid uid : remove ) {
            if( const std::optional<bionic *> current = p.find_bionic_by_uid( uid ) ) {
                ( *current )->powered = false;
                p.remove_bionic( **current );
                ++removed;
            }
        }
        p.update_bionic_power_capacity();
        if( p.get_power_level() > p.get_max_power_level() ) {
            p.set_power_level( p.get_max_power_level() );
        }
        status = string_format( _( "Removed %d UI-test bionics." ), removed );
    }

    p.invalidate_pseudo_items();
    p.recalculate_enchantment_cache();
    rebuild();
    ui.mark_resize();
    g->invalidate_main_ui_adaptor();
}

'''
bionics = replace_once(bionics, marker, fixture_impl + marker, 'bionics fixture implementation')

bionics = replace_once(
    bionics,
    '''    if( action == "SORT" ) {\n        open_dropdown( "SORT" );\n        return;\n    }\n    if( action == "LIST" || action == "DETAILS" ) {''',
    '''    if( action == "SORT" ) {\n        open_dropdown( "SORT" );\n        return;\n    }\n    if( action == "TEST" ) {\n        open_dropdown( "TEST" );\n        return;\n    }\n    if( action == "LIST" || action == "DETAILS" ) {''',
    'bionics Test dispatch'
)

bionics = replace_once(
    bionics,
    '''                if( kind == "SORT" ) {\n                    const std::string &id = result.entry->id;\n                    uistate.bionic_sort_mode = id == "power" ? bionic_ui_sort_mode::POWER :\n                                               id == "name" ? bionic_ui_sort_mode::NAME : id == "invlet" ?\n                                               bionic_ui_sort_mode::INVLET : bionic_ui_sort_mode::NONE;\n                    rebuild();\n                    for( tab_state &state : tabs ) {\n                        state.list.scroll_model().ensure_visible( state.list.cursor() );\n                    }\n                    // Translated sort labels can change the toolbar's wrap.\n                    ui.mark_resize();\n                } else if( owner ) {''',
    '''                if( kind == "SORT" ) {\n                    const std::string &id = result.entry->id;\n                    uistate.bionic_sort_mode = id == "power" ? bionic_ui_sort_mode::POWER :\n                                               id == "name" ? bionic_ui_sort_mode::NAME : id == "invlet" ?\n                                               bionic_ui_sort_mode::INVLET : bionic_ui_sort_mode::NONE;\n                    rebuild();\n                    for( tab_state &state : tabs ) {\n                        state.list.scroll_model().ensure_visible( state.list.cursor() );\n                    }\n                    // Translated sort labels can change the toolbar's wrap.\n                    ui.mark_resize();\n                } else if( kind == "TEST" ) {\n                    apply_test_fixture( result.entry->id );\n                } else if( owner ) {''',
    'bionics Test dropdown activation'
)

options_path.write_text(options)
bionics_path.write_text(bionics)
Path('/tmp/branch_patch_commit_message').write_text('Add reusable UI test mode and bionics fixtures\n')
