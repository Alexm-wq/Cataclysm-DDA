#include "test_monster_spawner.h"

#include <algorithm>
#include <cstdlib>
#include <optional>
#include <string>
#include <vector>

#include "avatar.h"
#include "cursesdef.h"
#include "game.h"
#include "input_context.h"
#include "messages.h"
#include "monster.h"
#include "output.h"
#include "translations.h"
#include "type_id.h"
#include "ui_manager.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/selection_list.h"

namespace
{
static const mtype_id mon_ocular_parasite_human( "mon_ocular_parasite_human" );
static const mtype_id mon_bioluminescent_overgrowth_brute_test(
    "mon_bioluminescent_overgrowth_brute_test" );
static const mtype_id mon_bioluminescent_elongated_host_test(
    "mon_bioluminescent_elongated_host_test" );

bool spawn_test_monster_three_tiles_away( const mtype_id &monster_id )
{
    const tripoint_bub_ms center = get_avatar().pos_bub();
    const auto try_spawn = [&]( const int dx, const int dy ) {
        const tripoint_bub_ms target( center.x() + dx, center.y() + dy, center.z() );
        return g->place_critter_at( monster_id, target ) != nullptr;
    };

    if( try_spawn( 3, 0 ) || try_spawn( -3, 0 ) || try_spawn( 0, 3 ) || try_spawn( 0, -3 ) ) {
        return true;
    }

    for( int dx = -3; dx <= 3; ++dx ) {
        for( int dy = -3; dy <= 3; ++dy ) {
            if( std::max( std::abs( dx ), std::abs( dy ) ) != 3 ) {
                continue;
            }
            if( ( dx == 3 && dy == 0 ) || ( dx == -3 && dy == 0 ) ||
                ( dx == 0 && dy == 3 ) || ( dx == 0 && dy == -3 ) ) {
                continue;
            }
            if( try_spawn( dx, dy ) ) {
                return true;
            }
        }
    }
    return false;
}
} // namespace

void show_test_monster_spawner()
{
    int width = std::min( 58, TERMX - 4 );
    int height = std::min( 14, TERMY - 4 );
    if( width < 34 || height < 12 ) {
        popup( _( "The terminal is too small for the test monster spawner." ) );
        return;
    }

    const std::vector<mtype_id> monster_ids = {
        mon_ocular_parasite_human,
        mon_bioluminescent_overgrowth_brute_test,
        mon_bioluminescent_elongated_host_test
    };
    const std::vector<std::string> monster_names = {
        _( "Ocular parasite host" ),
        _( "Bioluminescent overgrowth brute (test)" ),
        _( "Elongated bioluminescent host (test)" )
    };

    catacurses::window window;
    ui_selection_list monsters;
    monsters.set_entries( {
        ui_action_entry( monster_names[0], "SPAWN_OCULAR" ),
        ui_action_entry( monster_names[1], "SPAWN_OVERGROWTH_BRUTE" ),
        ui_action_entry( monster_names[2], "SPAWN_ELONGATED_HOST" )
    }, false );
    monsters.select_only( 0 );
    ui_selection_list_style list_style;
    ui_action_strip actions;
    std::string status = _( "These are temporary test enemies.  Select one and press Spawn." );
    nc_color status_color = c_light_gray;

    input_context ctxt( "TEST_MONSTER_SPAWNER" );
    for( const std::string &action : { "UP", "DOWN", "CONFIRM", "QUIT", "SELECT",
                                      "MOUSE_MOVE", "SCROLL_UP", "SCROLL_DOWN" } ) {
        ctxt.register_action( action );
    }

    const auto spawn_selected = [&]() {
        const std::vector<int> selected = monsters.selected_indices();
        const int index = selected.empty() ? 0 : selected.front();
        if( index < 0 || index >= static_cast<int>( monster_ids.size() ) ) {
            return;
        }

        if( spawn_test_monster_three_tiles_away( monster_ids[index] ) ) {
            status = _( "Spawned 3 tiles away.  Test enemies currently deal 0 melee damage." );
            status_color = c_light_green;
            add_msg( m_info, _( "Spawned %s three tiles away." ), monster_names[index] );
        } else {
            status = _( "No open tile exactly 3 tiles away is available." );
            status_color = c_light_red;
            add_msg( m_warning,
                     _( "No open tile exactly three tiles away was available for the selected test monster." ) );
        }
    };

    ui_adaptor ui( ui_adaptor::disable_uis_below{} );
    ui.on_screen_resize( [&]( ui_adaptor &adaptor ) {
        width = std::min( 58, TERMX - 4 );
        height = std::min( 14, TERMY - 4 );
        if( width < 34 || height < 12 ) {
            window = catacurses::window();
            adaptor.position( point::zero, point::zero );
            return;
        }
        const point origin( std::max( 0, ( TERMX - width ) / 2 ),
                            std::max( 0, ( TERMY - height ) / 2 ) );
        window = catacurses::newwin( height, width, origin );
        adaptor.position_from_window( window );
    } );
    ui.mark_resize();

    ui.on_redraw( [&]( ui_adaptor &adaptor ) {
        if( !window ) {
            return;
        }
        werase( window );
        draw_border( window, c_light_gray );
        trim_and_print( window, point( 2, 1 ), width - 4, c_light_green,
                        _( "Test monster spawner" ) );
        trim_and_print( window, point( 2, 3 ), width - 4, c_light_gray,
                        _( "Bioluminescent infection test enemies" ) );
        monsters.draw( window, point( 2, 4 ), width - 4, 4, list_style );
        trim_and_print( window, point( 2, 9 ), width - 4, status_color, status );

        const std::vector<ui_action_strip_item> action_items = {
            { ui_action_entry( _( "Spawn" ), "SPAWN" ), 0, ui_action_alignment::left },
            { ui_action_entry( _( "Close" ), "CLOSE" ), 0, ui_action_alignment::right }
        };
        actions.configure( window, point( 2, height - 2 ), action_items, width - 4, 1 );
        actions.draw( window );
        adaptor.disable_cursor();
        wnoutrefresh( window );
    } );

    while( true ) {
        ui_manager::redraw();
        if( !window ) {
            return;
        }

        const std::string action = ctxt.handle_input();
        const std::optional<point> pos = ctxt.get_coordinates_text( window );
        if( action == "QUIT" ) {
            return;
        }

        if( action == "MOUSE_MOVE" || action == "SELECT" ) {
            const ui_action_result button_result = actions.handle_input( action, pos );
            if( button_result.type == ui_action_result_type::activated && button_result.entry ) {
                if( button_result.entry->id == "CLOSE" ) {
                    return;
                }
                if( button_result.entry->id == "SPAWN" ) {
                    spawn_selected();
                    continue;
                }
            }
            if( action == "SELECT" && button_result.consumed() ) {
                continue;
            }
        }

        const ui_action_result list_result = monsters.handle_input( action, ctxt, pos );
        if( list_result.type == ui_action_result_type::activated && list_result.entry ) {
            spawn_selected();
        }
    }
}
