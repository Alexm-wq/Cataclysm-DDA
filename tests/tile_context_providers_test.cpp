#include <algorithm>
#include <vector>

#include "action.h"
#include "cata_catch.h"
#include "tile_context.h"
#include "tile_context_providers.h"

namespace
{
const tile_context_action *find_action( const std::vector<tile_context_action> &actions,
                                        const tile_context_action_id id )
{
    const auto iter = std::find_if( actions.begin(), actions.end(), [id]( const tile_context_action &action ) {
        return action.id == id;
    } );
    return iter == actions.end() ? nullptr : &*iter;
}

tile_context_snapshot visible_adjacent_snapshot()
{
    tile_context_snapshot snapshot;
    snapshot.target = tripoint_bub_ms( 61, 60, 0 );
    snapshot.player_pos = tripoint_bub_ms( 60, 60, 0 );
    snapshot.in_bounds = true;
    snapshot.distance = 1;
    snapshot.is_adjacent = true;
    snapshot.visible = true;
    snapshot.player_inside = true;
    return snapshot;
}
} // namespace

TEST_CASE( "basic_tile_context_self_actions_are_deliberately_small", "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot = visible_adjacent_snapshot();
    snapshot.target = snapshot.player_pos;
    snapshot.distance = 0;
    snapshot.is_self = true;
    snapshot.is_adjacent = false;

    const std::vector<tile_context_action> actions = collect_basic_tile_context_actions( snapshot );

    const tile_context_action *character = find_action( actions, tile_context_action_id::character_info );
    const tile_context_action *inventory = find_action( actions, tile_context_action_id::inventory );
    const tile_context_action *inspect = find_action( actions, tile_context_action_id::inspect );

    REQUIRE( character != nullptr );
    REQUIRE( inventory != nullptr );
    REQUIRE( inspect != nullptr );
    CHECK( character->section == tile_context_section::self );
    CHECK( inventory->section == tile_context_section::self );
    REQUIRE( character->keyboard_equivalent );
    REQUIRE( inventory->keyboard_equivalent );
    CHECK( *character->keyboard_equivalent == ACTION_PL_INFO );
    CHECK( *inventory->keyboard_equivalent == ACTION_INVENTORY );

    CHECK( find_action( actions, tile_context_action_id::medical ) == nullptr );
    CHECK( find_action( actions, tile_context_action_id::movement ) == nullptr );
}

TEST_CASE( "basic_tile_context_closed_and_open_doors_are_mutually_applicable",
           "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot = visible_adjacent_snapshot();
    snapshot.terrain_capabilities.supports_open = true;

    std::vector<tile_context_action> actions = collect_basic_tile_context_actions( snapshot );
    const tile_context_action *open = find_action( actions, tile_context_action_id::open );
    REQUIRE( open != nullptr );
    CHECK( open->is_available() );
    CHECK( find_action( actions, tile_context_action_id::close ) == nullptr );

    snapshot.terrain_capabilities.supports_open = false;
    snapshot.terrain_capabilities.supports_close = true;
    actions = collect_basic_tile_context_actions( snapshot );

    const tile_context_action *close = find_action( actions, tile_context_action_id::close );
    REQUIRE( close != nullptr );
    CHECK( close->is_available() );
    CHECK( find_action( actions, tile_context_action_id::open ) == nullptr );
}

TEST_CASE( "basic_tile_context_locked_door_keeps_open_visible_but_blocked",
           "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot = visible_adjacent_snapshot();
    snapshot.terrain_capabilities.supports_open = true;
    snapshot.terrain_capabilities.locked = true;

    const std::vector<tile_context_action> actions = collect_basic_tile_context_actions( snapshot );
    const tile_context_action *open = find_action( actions, tile_context_action_id::open );

    REQUIRE( open != nullptr );
    CHECK( open->is_blocked() );
    CHECK( open->denial_reason.translated() == "Locked" );
    REQUIRE( open->keyboard_equivalent );
    CHECK( *open->keyboard_equivalent == ACTION_OPEN );
}

TEST_CASE( "basic_tile_context_distant_door_is_applicable_but_too_far",
           "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot = visible_adjacent_snapshot();
    snapshot.distance = 4;
    snapshot.is_adjacent = false;
    snapshot.terrain_capabilities.supports_open = true;

    const std::vector<tile_context_action> actions = collect_basic_tile_context_actions( snapshot );
    const tile_context_action *open = find_action( actions, tile_context_action_id::open );

    REQUIRE( open != nullptr );
    CHECK( open->is_blocked() );
    CHECK( open->denial_reason.translated() == "Too far" );
}

TEST_CASE( "basic_tile_context_inside_only_door_reports_side_restriction",
           "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot = visible_adjacent_snapshot();
    snapshot.player_inside = false;
    snapshot.terrain_capabilities.supports_open = true;
    snapshot.terrain_capabilities.open_close_inside_only = true;

    const std::vector<tile_context_action> actions = collect_basic_tile_context_actions( snapshot );
    const tile_context_action *open = find_action( actions, tile_context_action_id::open );

    REQUIRE( open != nullptr );
    CHECK( open->is_blocked() );
    CHECK( open->denial_reason.translated() == "Must be opened from inside" );
}

TEST_CASE( "basic_tile_context_hidden_or_out_of_bounds_tile_has_no_tile_actions",
           "[tile_context][nogame]" )
{
    tile_context_snapshot snapshot = visible_adjacent_snapshot();
    snapshot.visible = false;
    snapshot.terrain_capabilities.supports_open = true;

    CHECK( collect_basic_tile_context_actions( snapshot ).empty() );

    snapshot.visible = true;
    snapshot.in_bounds = false;
    CHECK( collect_basic_tile_context_actions( snapshot ).empty() );
}
