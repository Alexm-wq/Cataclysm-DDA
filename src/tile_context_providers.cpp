#include "tile_context_providers.h"

#include <array>

#include "action.h"
#include "translation.h"

namespace
{
struct structural_action_state {
    bool applicable = false;
    bool has_ready_source = false;
    bool locked = false;
    bool inside_only = false;
};

struct layer_capability_ref {
    const tile_context_layer_capabilities *capabilities;
};

structural_action_state open_state( const tile_context_snapshot &snapshot )
{
    structural_action_state result;
    const std::array<layer_capability_ref, 3> layers = {{
            { &snapshot.terrain_capabilities },
            { &snapshot.furniture_capabilities },
            { &snapshot.vehicle_capabilities },
        }};

    for( const layer_capability_ref &layer : layers ) {
        const tile_context_layer_capabilities &cap = *layer.capabilities;
        if( !cap.supports_open ) {
            continue;
        }
        result.applicable = true;
        result.locked = result.locked || cap.locked;
        result.inside_only = result.inside_only || cap.open_close_inside_only;
        if( !cap.locked && ( !cap.open_close_inside_only || snapshot.player_inside ) ) {
            result.has_ready_source = true;
        }
    }
    return result;
}

structural_action_state close_state( const tile_context_snapshot &snapshot )
{
    structural_action_state result;
    const std::array<layer_capability_ref, 3> layers = {{
            { &snapshot.terrain_capabilities },
            { &snapshot.furniture_capabilities },
            { &snapshot.vehicle_capabilities },
        }};

    for( const layer_capability_ref &layer : layers ) {
        const tile_context_layer_capabilities &cap = *layer.capabilities;
        if( !cap.supports_close ) {
            continue;
        }
        result.applicable = true;
        result.inside_only = result.inside_only || cap.open_close_inside_only;
        if( !cap.open_close_inside_only || snapshot.player_inside ) {
            result.has_ready_source = true;
        }
    }
    return result;
}

void add_open_action( const tile_context_snapshot &snapshot,
                      std::vector<tile_context_action> &actions )
{
    const structural_action_state state = open_state( snapshot );
    if( !state.applicable ) {
        return;
    }

    if( !snapshot.is_adjacent ) {
        actions.push_back( make_blocked_tile_context_action(
                               tile_context_action_id::open,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Open" ),
                               translation::to_translation( "Too far" ),
                               ACTION_OPEN ) );
    } else if( state.has_ready_source ) {
        actions.push_back( make_ready_tile_context_action(
                               tile_context_action_id::open,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Open" ),
                               ACTION_OPEN ) );
    } else if( state.locked ) {
        actions.push_back( make_blocked_tile_context_action(
                               tile_context_action_id::open,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Open" ),
                               translation::to_translation( "Locked" ),
                               ACTION_OPEN ) );
    } else if( state.inside_only ) {
        actions.push_back( make_blocked_tile_context_action(
                               tile_context_action_id::open,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Open" ),
                               translation::to_translation( "Must be opened from inside" ),
                               ACTION_OPEN ) );
    }
}

void add_close_action( const tile_context_snapshot &snapshot,
                       std::vector<tile_context_action> &actions )
{
    const structural_action_state state = close_state( snapshot );
    if( !state.applicable ) {
        return;
    }

    if( !snapshot.is_adjacent ) {
        actions.push_back( make_blocked_tile_context_action(
                               tile_context_action_id::close,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Close" ),
                               translation::to_translation( "Too far" ),
                               ACTION_CLOSE ) );
    } else if( state.has_ready_source ) {
        actions.push_back( make_ready_tile_context_action(
                               tile_context_action_id::close,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Close" ),
                               ACTION_CLOSE ) );
    } else if( state.inside_only ) {
        actions.push_back( make_blocked_tile_context_action(
                               tile_context_action_id::close,
                               tile_context_section::tile,
                               tile_context_category::immediate,
                               snapshot.target,
                               translation::to_translation( "Close" ),
                               translation::to_translation( "Must be closed from inside" ),
                               ACTION_CLOSE ) );
    }
}
} // namespace

void add_self_tile_context_actions( const tile_context_snapshot &snapshot,
                                    std::vector<tile_context_action> &actions )
{
    if( !snapshot.in_bounds || !snapshot.is_self ) {
        return;
    }

    actions.push_back( make_ready_tile_context_action(
                           tile_context_action_id::character_info,
                           tile_context_section::self,
                           tile_context_category::information,
                           snapshot.target,
                           translation::to_translation( "Character..." ),
                           ACTION_PL_INFO ) );
    actions.push_back( make_ready_tile_context_action(
                           tile_context_action_id::inventory,
                           tile_context_section::self,
                           tile_context_category::items,
                           snapshot.target,
                           translation::to_translation( "Inventory..." ),
                           ACTION_INVENTORY ) );
}

void add_basic_tile_context_actions( const tile_context_snapshot &snapshot,
                                     std::vector<tile_context_action> &actions )
{
    if( !snapshot.in_bounds || !snapshot.visible ) {
        return;
    }

    add_open_action( snapshot, actions );
    add_close_action( snapshot, actions );

    actions.push_back( make_ready_tile_context_action(
                           tile_context_action_id::inspect,
                           tile_context_section::tile,
                           tile_context_category::information,
                           snapshot.target,
                           translation::to_translation( "Inspect" ),
                           ACTION_EXAMINE ) );
}

std::vector<tile_context_action> collect_basic_tile_context_actions(
    const tile_context_snapshot &snapshot )
{
    return collect_tile_context_actions( snapshot, {
        &add_self_tile_context_actions,
        &add_basic_tile_context_actions,
    } );
}
