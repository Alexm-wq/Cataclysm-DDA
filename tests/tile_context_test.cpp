#include <vector>

#include "action.h"
#include "avatar.h"
#include "cata_catch.h"
#include "map.h"
#include "map_helpers.h"
#include "tile_context.h"
#include "translation.h"
#include "type_id.h"

namespace
{
void add_nothing( const tile_context_snapshot &, std::vector<tile_context_action> & )
{
}

void add_ready_open( const tile_context_snapshot &snapshot,
                     std::vector<tile_context_action> &actions )
{
    actions.push_back( make_ready_tile_context_action(
                           tile_context_action_id::open,
                           tile_context_section::tile,
                           tile_context_category::immediate,
                           snapshot.target,
                           translation::no_translation( "Open" ),
                           ACTION_OPEN ) );
}

void add_blocked_pry( const tile_context_snapshot &snapshot,
                      std::vector<tile_context_action> &actions )
{
    actions.push_back( make_blocked_tile_context_action(
                           tile_context_action_id::pry,
                           tile_context_section::tile,
                           tile_context_category::destructive,
                           snapshot.target,
                           translation::no_translation( "Pry" ),
                           translation::no_translation( "Requires PRY 2" ),
                           std::nullopt,
                           true,
                           true ) );
}
} // namespace

TEST_CASE( "tile_context_applicability_is_presence_based", "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot;
    snapshot.target = tripoint_bub_ms( 10, 20, 0 );

    const std::vector<tile_context_provider> providers = {
        &add_nothing,
        &add_ready_open,
        &add_blocked_pry,
    };

    const std::vector<tile_context_action> actions = collect_tile_context_actions( snapshot, providers );

    // The provider which found an action not applicable emitted no placeholder.
    REQUIRE( actions.size() == 2 );

    CHECK( actions[0].id == tile_context_action_id::open );
    CHECK( actions[0].is_available() );
    CHECK_FALSE( actions[0].is_blocked() );
    REQUIRE( actions[0].keyboard_equivalent.has_value() );
    CHECK( *actions[0].keyboard_equivalent == ACTION_OPEN );
    CHECK( actions[0].denial_reason.empty() );

    CHECK( actions[1].id == tile_context_action_id::pry );
    CHECK_FALSE( actions[1].is_available() );
    CHECK( actions[1].is_blocked() );
    CHECK( actions[1].denial_reason.translated() == "Requires PRY 2" );
    CHECK( actions[1].destructive );
    CHECK( actions[1].noisy );
}

TEST_CASE( "tile_context_capabilities_are_structural_facts", "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot;

    CHECK_FALSE( tile_context_supports_open( snapshot ) );
    CHECK_FALSE( tile_context_supports_close( snapshot ) );
    CHECK_FALSE( tile_context_supports_go_up( snapshot ) );
    CHECK_FALSE( tile_context_supports_go_down( snapshot ) );
    CHECK_FALSE( tile_context_supports_pry( snapshot ) );

    snapshot.terrain_capabilities.supports_open = true;
    snapshot.furniture_capabilities.goes_down = true;
    snapshot.vehicle_capabilities.supports_close = true;
    snapshot.terrain_capabilities.supports_pry = true;

    CHECK( tile_context_supports_open( snapshot ) );
    CHECK( tile_context_supports_close( snapshot ) );
    CHECK_FALSE( tile_context_supports_go_up( snapshot ) );
    CHECK( tile_context_supports_go_down( snapshot ) );
    CHECK( tile_context_supports_pry( snapshot ) );
}

TEST_CASE( "tile_context_sections_allow_multiple_targets_on_one_coordinate",
           "[tile_context][nogame]" )
{
    const tripoint_bub_ms target( 1, 2, 0 );

    const tile_context_action character = make_ready_tile_context_action(
            tile_context_action_id::character_info,
            tile_context_section::self,
            tile_context_category::information,
            target,
            translation::no_translation( "Character" ),
            ACTION_PL_INFO );

    const tile_context_action inspect = make_ready_tile_context_action(
                                            tile_context_action_id::inspect,
                                            tile_context_section::tile,
                                            tile_context_category::information,
                                            target,
                                            translation::no_translation( "Inspect" ),
                                            ACTION_EXAMINE );

    CHECK( character.section == tile_context_section::self );
    CHECK( inspect.section == tile_context_section::tile );
    CHECK( character.target == inspect.target );
}

TEST_CASE( "tile_context_snapshot_reads_live_map_facts", "[tile_context]" )
{
    clear_map();
    map &here = get_map();
    avatar &player_character = get_avatar();

    const tripoint_bub_ms player_pos( 60, 60, 0 );
    const tripoint_bub_ms target( 61, 60, 0 );
    player_character.setpos( here, player_pos );

    here.ter_set( target, ter_str_id( "t_door_c" ).id() );
    tile_context_snapshot snapshot = build_tile_context_snapshot( here, player_character, target );

    CHECK( snapshot.in_bounds );
    CHECK_FALSE( snapshot.is_self );
    CHECK( snapshot.is_adjacent );
    CHECK( snapshot.distance == 1 );
    CHECK( snapshot.terrain == ter_str_id( "t_door_c" ).id() );
    CHECK( snapshot.terrain_capabilities.supports_open );
    CHECK_FALSE( snapshot.terrain_capabilities.supports_close );
    CHECK_FALSE( snapshot.has_vehicle );
    CHECK_FALSE( snapshot.has_creature );

    here.ter_set( target, ter_str_id( "t_door_o" ).id() );
    snapshot = build_tile_context_snapshot( here, player_character, target );
    CHECK_FALSE( snapshot.terrain_capabilities.supports_open );
    CHECK( snapshot.terrain_capabilities.supports_close );
}

TEST_CASE( "tile_context_snapshot_uses_actual_transition_capabilities", "[tile_context]" )
{
    clear_map();
    map &here = get_map();
    avatar &player_character = get_avatar();

    const tripoint_bub_ms player_pos( 60, 60, 0 );
    const tripoint_bub_ms target( 61, 60, 0 );
    player_character.setpos( here, player_pos );

    here.ter_set( target, ter_str_id( "t_wood_stairs_down" ).id() );
    tile_context_snapshot snapshot = build_tile_context_snapshot( here, player_character, target );
    CHECK( snapshot.terrain_capabilities.goes_down );

    here.ter_set( target, ter_str_id( "t_manhole_cover" ).id() );
    snapshot = build_tile_context_snapshot( here, player_character, target );
    CHECK_FALSE( snapshot.terrain_capabilities.goes_down );
    CHECK( snapshot.terrain_capabilities.supports_pry );

    here.ter_set( target, ter_str_id( "t_manhole" ).id() );
    snapshot = build_tile_context_snapshot( here, player_character, target );
    CHECK( snapshot.terrain_capabilities.goes_down );
}

TEST_CASE( "tile_context_snapshot_treats_avatar_as_one_layer_of_self_tile", "[tile_context]" )
{
    clear_map();
    map &here = get_map();
    avatar &player_character = get_avatar();

    const tripoint_bub_ms player_pos( 60, 60, 0 );
    player_character.setpos( here, player_pos );

    const tile_context_snapshot snapshot = build_tile_context_snapshot( here, player_character,
                                           player_pos );

    CHECK( snapshot.in_bounds );
    CHECK( snapshot.is_self );
    CHECK_FALSE( snapshot.is_adjacent );
    CHECK( snapshot.has_creature );
    CHECK( snapshot.creature_is_avatar );
}
