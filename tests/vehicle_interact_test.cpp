#include <algorithm>
#include <functional>
#include <sstream>
#include <optional>
#include <string>
#include <vector>

#include "activity_actor_definitions.h"
#include "activity_handlers.h"
#include "calendar.h"
#include "cata_catch.h"
#include "character.h"
#include "coordinates.h"
#include "enums.h"
#include "game_constants.h"
#include "handle_liquid.h"
#include "inventory.h"
#include "item.h"
#include "item_location.h"
#include "json.h"
#include "json_loader.h"
#include "map.h"
#include "map_helpers.h"
#include "player_helpers.h"
#include "pocket_type.h"
#include "point.h"
#include "requirements.h"
#include "ret_val.h"
#include "type_id.h"
#include "units.h"
#include "veh_appliance.h"
#include "veh_interact.h"
#include "veh_type.h"
#include "vehicle.h"

static const itype_id itype_UPS_ON( "UPS_ON" );
static const itype_id itype_battery_ups( "battery_ups" );
static const itype_id itype_debug_backpack( "debug_backpack" );
static const itype_id itype_goggles_welding( "goggles_welding" );
static const itype_id itype_hammer( "hammer" );
static const itype_id itype_lc_steel_chunk( "lc_steel_chunk" );
static const itype_id itype_test_storage_battery( "test_storage_battery" );
static const itype_id itype_welder( "welder" );
static const itype_id itype_welding_wire_steel( "welding_wire_steel" );

static const skill_id skill_mechanics( "mechanics" );

static const vpart_id vpart_ap_test_storage_battery( "ap_test_storage_battery" );

static const vproto_id vehicle_prototype_car( "car" );

static void test_repair( const std::vector<item> &tools, bool plug_in_tools, bool expect_craftable )
{
    map &here = get_map();
    clear_avatar();
    clear_map();

    const tripoint_bub_ms test_origin( 60, 60, 0 );
    Character &player_character = get_player_character();
    player_character.setpos( here, test_origin );
    const item debug_backpack( itype_debug_backpack );
    player_character.wear_item( debug_backpack );

    const tripoint_bub_ms battery_pos = test_origin + tripoint::north_west;
    std::optional<item> battery_item( itype_test_storage_battery );
    place_appliance( here, battery_pos, vpart_ap_test_storage_battery, player_character, battery_item );

    for( const item &gear : tools ) {
        item_location added_tool = player_character.i_add( gear );
        if( plug_in_tools && added_tool->can_link_up() ) {
            added_tool->link_to( here.veh_at( player_character.pos_bub() + tripoint::north_west ),
                                 link_state::automatic );
            REQUIRE( added_tool->link().t_veh );
        }
    }
    player_character.set_skill_level( skill_mechanics, 10 );

    const tripoint_bub_ms vehicle_origin = test_origin + tripoint::south_east;
    vehicle *veh_ptr = here.add_vehicle( vehicle_prototype_car, vehicle_origin, -90_degrees, 0,
                                         0 );

    REQUIRE( veh_ptr != nullptr );
    // Find the frame at the origin.
    vehicle_part *origin_frame = nullptr;
    for( vehicle_part *part : veh_ptr->get_parts_at( &here, vehicle_origin, "",
            part_status_flag::any ) ) {
        if( part->info().location == "structure" ) {
            origin_frame = part;
            break;
        }
    }
    REQUIRE( origin_frame != nullptr );
    REQUIRE( origin_frame->hp() == origin_frame->info().durability );
    veh_ptr->mod_hp( *origin_frame, -50 );
    REQUIRE( origin_frame->hp() < origin_frame->info().durability );
    // for a steel frame, one quadrant of damage takes 1000 kJ, 5 chunks of steel and 50 welding wires/rods to fix. (it has 400 max hp)

    const vpart_info &vp = origin_frame->info();
    // Assertions about frame part?

    requirement_data reqs = vp.repair_requirements();
    // Bust cache on crafting_inventory()
    player_character.mod_moves( 1 );
    inventory crafting_inv = player_character.crafting_inventory();
    bool can_repair = vp.repair_requirements().can_make_with_inventory(
                          player_character.crafting_inventory(),
                          is_crafting_component );
    CHECK( can_repair == expect_craftable );
}

TEST_CASE( "repair_vehicle_part", "[vehicle]" )
{
    SECTION( "welder" ) {
        std::vector<item> tools;

        item welder( itype_welder );
        tools.push_back( welder );

        tools.emplace_back( itype_goggles_welding );
        tools.emplace_back( itype_hammer );
        tools.insert( tools.end(), 20, item( itype_lc_steel_chunk ) );
        tools.insert( tools.end(), 200, item( itype_welding_wire_steel ) );
        test_repair( tools, true, true );
    }
    SECTION( "UPS_modded_welder" ) {
        std::vector<item> tools;
        item welder( itype_welder, calendar::turn_zero, 0 );
        welder.put_in( item( itype_battery_ups ), pocket_type::MOD );
        tools.push_back( welder );

        item ups( itype_UPS_ON );
        item ups_mag( ups.magazine_default() );
        ups_mag.ammo_set( ups_mag.ammo_default(), 1000 );
        ups.put_in( ups_mag, pocket_type::MAGAZINE_WELL );
        tools.push_back( ups );

        tools.emplace_back( itype_goggles_welding );
        tools.emplace_back( itype_hammer );
        tools.insert( tools.end(), 5, item( itype_lc_steel_chunk ) );
        tools.insert( tools.end(), 50, item( itype_welding_wire_steel ) );
        test_repair( tools, false, false );
    }
    SECTION( "welder_missing_goggles" ) {
        std::vector<item> tools;

        item welder( itype_welder );
        tools.push_back( welder );

        tools.emplace_back( itype_hammer );
        tools.insert( tools.end(), 5, item( itype_lc_steel_chunk ) );
        tools.insert( tools.end(), 50, item( itype_welding_wire_steel ) );
        test_repair( tools, true, false );
    }
    SECTION( "welder_missing_charge" ) {
        std::vector<item> tools;

        item welder( itype_welder );
        tools.push_back( welder );

        tools.emplace_back( itype_goggles_welding );
        tools.emplace_back( itype_hammer );
        tools.insert( tools.end(), 5, item( itype_lc_steel_chunk ) );
        tools.insert( tools.end(), 50, item( itype_welding_wire_steel ) );
        test_repair( tools, false, false );
    }
    SECTION( "UPS_modded_welder_missing_charges" ) {
        std::vector<item> tools;
        item welder( itype_welder, calendar::turn_zero, 0 );
        welder.put_in( item( itype_battery_ups ), pocket_type::MOD );
        tools.push_back( welder );

        item ups( itype_UPS_ON );
        item ups_mag( ups.magazine_default() );
        ups_mag.ammo_set( ups_mag.ammo_default(), 500 );
        ups.put_in( ups_mag, pocket_type::MAGAZINE_WELL );
        tools.push_back( ups );

        tools.emplace_back( itype_goggles_welding );
        tools.insert( tools.end(), 5, item( itype_lc_steel_chunk ) );
        tools.insert( tools.end(), 50, item( itype_welding_wire_steel ) );
        test_repair( tools, false, false );
    }
    SECTION( "welder_missing_consumables" ) {
        std::vector<item> tools;

        item welder( itype_welder );
        tools.push_back( welder );

        tools.emplace_back( itype_goggles_welding );
        test_repair( tools, true, false );
    }
}


struct veh_interact_test_access {
    static void check_refuel_navigation( map &here, vehicle &veh, bool quick ) {
        veh_interact editor( here, veh );
        editor.do_refill( here );
        REQUIRE( editor.refuel_info );
        editor.handle_refuel_action( here, "REFUEL_ALL" );
        editor.handle_refuel_action( here, quick ? "REFUEL_QUICK_FILL" : "REFUEL_APPLY" );
        REQUIRE( editor.refuel_info );

        // Source and Quick fill stages both return to fuel stores first, even
        // when no compatible sources/propulsion fuels can be listed.
        editor.handle_refuel( here, "QUIT" );
        REQUIRE( editor.refuel_info );
        editor.handle_refuel( here, "QUIT" );
        CHECK_FALSE( editor.refuel_info );
        CHECK( editor.refill_part_indices.empty() );
        CHECK( editor.sel_cmd == ' ' );
    }

    static void check_resource_browser( map &here, vehicle &veh, bool unload,
                                        task_reason expected_reason ) {
        veh_interact editor( here, veh );
        editor.select_mount( here, point_rel_ms( 5, 5 ) );
        REQUIRE( editor.selected_part == -1 );
        REQUIRE( editor.editor_toolbar_action_enabled( here, unload ? "UNLOAD" : "SIPHON" ) );
        REQUIRE( editor.cant_do( here, unload ? 'd' : 's' ) == expected_reason );

        editor.open_resource_transfer( unload );
        REQUIRE( editor.resource_transfer_info );
        const std::string reason = editor.resource_transfer_disabled_reason( here );
        CHECK( reason.empty() == ( expected_reason == task_reason::CAN_DO ) );

        // Opening a browser never transfers anything. A blocked transfer remains
        // blocked when attempted directly, including keyboard/double-click paths.
        editor.apply_resource_transfer( here );
        CHECK( editor.resource_transfer_activity.is_null() );
        if( expected_reason != task_reason::CAN_DO ) {
            CHECK( editor.msg == reason );
        }
        editor.close_resource_transfer();
        CHECK_FALSE( editor.resource_transfer_info );
    }
};

TEST_CASE( "vehicle_refuel_back_unwinds_source_and_quick_fill_stages", "[vehicle][fuel_transfer][ui]" )
{
    clear_avatar();
    clear_map();
    map &here = get_map();
    vehicle *veh = here.add_vehicle( vproto_id( "none" ), tripoint_bub_ms( 60, 60, 0 ),
                                    0_degrees, 0, 0 );
    REQUIRE( veh != nullptr );
    for( int x = 0; x < 2; ++x ) {
        REQUIRE( veh->install_part( here, point_rel_ms( x, 0 ), vpart_id( "frame" ) ) >= 0 );
        REQUIRE( veh->install_part( here, point_rel_ms( x, 0 ), vpart_id( "tank" ) ) >= 0 );
    }
    here.add_vehicle_to_cache( veh );
    for( const bool quick : { false, true } ) {
        CAPTURE( quick );
        veh_interact_test_access::check_refuel_navigation( here, *veh, quick );
    }
    CHECK( get_player_character().activity.is_null() );
}

TEST_CASE( "vehicle_resource_browsers_open_before_transfer_requirements_are_met",
           "[vehicle][fuel_transfer][ui]" )
{
    clear_avatar();
    clear_map();
    map &here = get_map();
    Character &who = get_player_character();
    who.setpos( here, tripoint_bub_ms( 60, 61, 0 ) );
    vehicle *veh = here.add_vehicle( vproto_id( "none" ), tripoint_bub_ms( 60, 60, 0 ),
                                    0_degrees, 0, 0 );
    REQUIRE( veh != nullptr );
    REQUIRE( veh->install_part( here, point_rel_ms::zero, vpart_id( "frame" ) ) >= 0 );
    REQUIRE( veh->install_part( here, point_rel_ms( 1, 0 ), vpart_id( "frame" ) ) >= 0 );
    const int tank = veh->install_part( here, point_rel_ms::zero, vpart_id( "tank" ) );
    const int bunker = veh->install_part( here, point_rel_ms( 1, 0 ), vpart_id( "fuel_bunker" ) );
    REQUIRE( tank >= 0 );
    REQUIRE( bunker >= 0 );
    here.add_vehicle_to_cache( veh );
    task_reason siphon_reason = task_reason::INVALID_TARGET;
    task_reason unload_reason = task_reason::INVALID_TARGET;

    SECTION( "empty_vehicle" ) {
        // No liquid, solid fuel or hose; both browsers must still open.
    }
    SECTION( "liquid_without_a_hose" ) {
        REQUIRE( veh->part( tank ).ammo_set( itype_id( "water_clean" ), 20 ) == 20 );
        siphon_reason = task_reason::LACK_TOOLS;
    }
    SECTION( "moving_vehicle_with_fuel" ) {
        REQUIRE( veh->part( tank ).ammo_set( itype_id( "water_clean" ), 20 ) == 20 );
        REQUIRE( veh->part( bunker ).ammo_set( itype_id( "charcoal" ), 100 ) == 100 );
        veh->velocity = 100;
        siphon_reason = task_reason::MOVING_VEHICLE;
        unload_reason = task_reason::MOVING_VEHICLE;
    }
    SECTION( "controlling_a_stationary_vehicle" ) {
        who.controlling_vehicle = true;
        siphon_reason = task_reason::MOVING_VEHICLE;
        unload_reason = task_reason::MOVING_VEHICLE;
    }
    SECTION( "ready_to_transfer_without_a_selected_vehicle_part" ) {
        who.wear_item( item( itype_debug_backpack ) );
        who.i_add( item( itype_id( "hose" ) ) );
        REQUIRE( veh->part( tank ).ammo_set( itype_id( "water_clean" ), 20 ) == 20 );
        REQUIRE( veh->part( bunker ).ammo_set( itype_id( "charcoal" ), 100 ) == 100 );
        siphon_reason = task_reason::CAN_DO;
        unload_reason = task_reason::CAN_DO;
    }
    const int liquid_before = veh->part( tank ).ammo_remaining();
    const int fuel_before = veh->part( bunker ).ammo_remaining();
    veh_interact_test_access::check_resource_browser( here, *veh, false, siphon_reason );
    veh_interact_test_access::check_resource_browser( here, *veh, true, unload_reason );
    CHECK( veh->part( tank ).ammo_remaining() == liquid_before );
    CHECK( veh->part( bunker ).ammo_remaining() == fuel_before );
    CHECK( who.activity.is_null() );
    who.controlling_vehicle = false;
}

TEST_CASE( "vehicle_unload_solid_fuels_retains_partial_cells", "[vehicle][fuel_transfer]" )
{
    clear_avatar();
    clear_map();
    map &here = get_map();
    vehicle *veh = here.add_vehicle( vproto_id( "none" ), tripoint_bub_ms( 60, 60, 0 ),
                                    0_degrees, 0, 0 );
    REQUIRE( veh != nullptr );
    const auto install = [&]( int x, const vpart_id &type ) {
        const point_rel_ms mount( x, 0 );
        REQUIRE( veh->install_part( here, mount, vpart_id( "frame" ) ) >= 0 );
        const int index = veh->install_part( here, mount, type );
        REQUIRE( index >= 0 );
        return index;
    };
    const int cells = install( 0, vpart_id( "test_solid_fuel_store" ) );
    const int coal = install( 1, vpart_id( "fuel_bunker" ) );
    const int tank = install( 2, vpart_id( "tank" ) );
    const int battery = install( 3, vpart_id( "small_storage_battery" ) );
    const itype_id plut( "plut_cell" );
    const itype_id charcoal( "charcoal" );
    REQUIRE( veh->part( cells ).ammo_set( plut, 2 * PLUTONIUM_CHARGES + 5 ) == 2 * PLUTONIUM_CHARGES + 5 );
    REQUIRE( veh->part( coal ).ammo_set( charcoal, 100 ) == 100 );
    veh->part( tank ).ammo_set( itype_id( "water_clean" ), 20 );
    veh->part( battery ).ammo_set( itype_id( "battery" ), 100 );
    CHECK( veh->unloadable_fuels().size() == 2 );
    CHECK( veh->unloadable_fuels().at( plut ) == 2 );
    CHECK_FALSE( veh->unload_fuel( here, itype_id( "battery" ) ) );
    CHECK_FALSE( veh->unload_fuel( here, itype_id( "water_clean" ) ) );
    const std::optional<item> unloaded_cells = veh->unload_fuel( here, plut );
    REQUIRE( unloaded_cells );
    CHECK( unloaded_cells->charges == 2 );
    CHECK( veh->part( cells ).ammo_remaining() == 5 );
    CHECK( veh->unloadable_fuels().count( plut ) == 0 );
    CHECK( veh->unloadable_fuels().at( charcoal ) == 100 );
    veh->velocity = 100;
    CHECK_FALSE( veh->unload_fuel( here, charcoal ) );
    CHECK( veh->part( coal ).ammo_remaining() == 100 );
    veh->velocity = 0;
    const std::optional<item> unloaded_coal = veh->unload_fuel( here, charcoal );
    REQUIRE( unloaded_coal );
    CHECK( unloaded_coal->charges == 100 );
    CHECK( veh->unloadable_fuels().empty() );
    CHECK( veh->part( tank ).ammo_remaining() == 20 );
    CHECK( veh->part( battery ).ammo_remaining() == 100 );
}

TEST_CASE( "vehicle_siphon_uses_exact_containers_and_saves_remaining_batch", "[vehicle][fuel_transfer]" )
{
    clear_avatar();
    clear_map();
    map &here = get_map();
    Character &who = get_player_character();
    who.setpos( here, tripoint_bub_ms( 60, 61, 0 ) );
    who.wear_item( item( itype_debug_backpack ) );
    who.i_add( item( itype_id( "hose" ) ) );
    vehicle *veh = here.add_vehicle( vproto_id( "none" ), tripoint_bub_ms( 60, 60, 0 ),
                                    0_degrees, 0, 0 );
    REQUIRE( veh != nullptr );
    REQUIRE( veh->install_part( here, point_rel_ms::zero, vpart_id( "frame" ) ) >= 0 );
    const int tank = veh->install_part( here, point_rel_ms::zero, vpart_id( "tank" ) );
    REQUIRE( tank >= 0 );
    here.add_vehicle_to_cache( veh );
    const itype_id water( "water_clean" );
    const item liquid( water );
    std::vector<liquid_handler::siphon_destination> containers;
    for( int i = 0; i < 3; ++i ) {
        item_location bottle = who.i_add( item( itype_id( "bottle_plastic" ) ) );
        REQUIRE( bottle );
        containers.push_back( { bottle, std::nullopt } );
    }
    REQUIRE( containers[0].container != containers[1].container );
    const int capacity = liquid_handler::siphon_destination_capacity( containers[0], liquid, who );
    REQUIRE( capacity > 0 );
    const int initial = capacity * 4;
    REQUIRE( veh->part( tank ).ammo_set( water, initial ) == initial );
    CHECK( veh->siphon_sources() == std::vector<int>{ tank } );

    SECTION( "two_containers_from_a_stack_leave_the_third_untouched_after_save_load" ) {
        std::vector<player_activity> transfers;
        for( int i = 0; i < 2; ++i ) {
            transfers.push_back( liquid_handler::siphon_transfer( *veh, tank, containers[i], capacity ) );
        }
        vehicle_siphon_activity_actor actor( transfers, veh->abs_part_pos( 0 ), point_rel_ms::zero );
        player_activity activity( actor );
        actor.start( activity, who );
        actor.do_turn( activity, who );
        const int after_first_turn = veh->part( tank ).ammo_remaining();
        CHECK( after_first_turn < initial );
        std::ostringstream saved;
        JsonOut out( saved );
        actor.serialize( out );
        JsonValue json = json_loader::from_string( saved.str() );
        std::unique_ptr<activity_actor> restored = vehicle_siphon_activity_actor::deserialize( json );
        int turns = 0;
        while( activity.moves_left > 0 && turns++ < 1000 ) {
            restored->do_turn( activity, who );
        }
        REQUIRE( turns < 1000 );
        CHECK( veh->part( tank ).ammo_remaining() == initial - 2 * capacity );
        CHECK( containers[0].container->only_item().charges == capacity );
        CHECK( containers[1].container->only_item().charges == capacity );
        CHECK( containers[2].container->empty() );
    }
    SECTION( "stale_source_snapshot_does_not_duplicate_lost_liquid" ) {
        player_activity transfer = liquid_handler::siphon_transfer( *veh, tank, containers[0], capacity );
        veh->drain( here, tank, initial - 1 );
        activity_handlers::fill_liquid_do_turn( &transfer, &who );
        CHECK( containers[0].container->only_item().charges == 1 );
        CHECK( veh->part( tank ).ammo_remaining() == 0 );
        CHECK( transfer.is_null() );
    }
    SECTION( "invalid_destination_does_not_drain_source" ) {
        player_activity transfer = liquid_handler::siphon_transfer( *veh, tank, containers[0], capacity );
        containers[0].container.remove_item();
        activity_handlers::fill_liquid_do_turn( &transfer, &who );
        CHECK( transfer.is_null() );
        CHECK( veh->part( tank ).ammo_remaining() == initial );
    }
    SECTION( "replaced_liquid_is_not_poured_as_the_old_type" ) {
        player_activity transfer = liquid_handler::siphon_transfer( *veh, tank, containers[0], capacity );
        veh->part( tank ).ammo_set( itype_id( "water" ), initial );
        activity_handlers::fill_liquid_do_turn( &transfer, &who );
        CHECK( transfer.is_null() );
        CHECK( containers[0].container->empty() );
        CHECK( veh->part( tank ).ammo_remaining() == initial );
    }
    SECTION( "canceling_a_batch_does_not_start_another_transfer" ) {
        vehicle_siphon_activity_actor actor(
        { liquid_handler::siphon_transfer( *veh, tank, containers[0], capacity ),
          liquid_handler::siphon_transfer( *veh, tank, containers[1], capacity ) },
        veh->abs_part_pos( 0 ), point_rel_ms::zero );
        who.assign_activity( actor );
        who.cancel_activity();
        CHECK( who.activity.is_null() );
        CHECK( containers[0].container->empty() );
        CHECK( containers[1].container->empty() );
        CHECK( veh->part( tank ).ammo_remaining() == initial );
    }
}
