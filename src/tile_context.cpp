#include "tile_context.h"

#include <sstream>
#include <utility>

#include "avatar.h"
#include "creature.h"
#include "creature_tracker.h"
#include "line.h"
#include "map.h"
#include "mapdata.h"

namespace
{
using capability_member = bool tile_context_layer_capabilities::*;

bool any_layer_capability( const tile_context_snapshot &snapshot, capability_member member )
{
    return snapshot.terrain_capabilities.*member ||
           snapshot.furniture_capabilities.*member ||
           snapshot.vehicle_capabilities.*member;
}

template<typename MapData>
tile_context_layer_capabilities map_data_capabilities( const MapData &data,
        const tripoint_bub_ms &target )
{
    tile_context_layer_capabilities result;

    result.supports_open = !data.open.is_null();
    result.supports_close = !data.close.is_null();
    result.goes_up = data.has_flag( ter_furn_flag::TFLAG_GOES_UP );
    result.goes_down = data.has_flag( ter_furn_flag::TFLAG_GOES_DOWN );
    result.supports_interact = data.can_examine( target );

    result.supports_bash = data.is_smashable();
    result.supports_pry = static_cast<bool>( data.prying );
    result.supports_lockpick = !data.lockpick_result.is_null() ||
                               data.has_flag( ter_furn_flag::TFLAG_PICKABLE );
    result.supports_boltcut = static_cast<bool>( data.boltcut );
    result.supports_hacksaw = static_cast<bool>( data.hacksaw );
    result.supports_oxytorch = static_cast<bool>( data.oxytorch );
    result.supports_mine = data.has_flag( ter_furn_flag::TFLAG_MINEABLE );
    result.supports_deconstruct = data.deconstruct.has_value();

    // Chopping is intentionally not inferred from TREE/YOUNG alone.  Its
    // canonical applicability rules will be wired when the tool provider is
    // implemented, so we do not create false-positive menu actions.
    result.supports_chop = false;

    result.climbable = data.has_flag( ter_furn_flag::TFLAG_CLIMBABLE ) ||
                       data.has_flag( ter_furn_flag::TFLAG_CLIMB_SIMPLE );
    result.console = data.has_flag( ter_furn_flag::TFLAG_CONSOLE );
    result.locked = data.has_flag( ter_furn_flag::TFLAG_LOCKED );
    result.open_close_inside_only = data.has_flag( ter_furn_flag::TFLAG_OPENCLOSE_INSIDE );

    return result;
}
} // namespace

tile_context_snapshot build_tile_context_snapshot( map &here, const avatar &player_character,
        const tripoint_bub_ms &target )
{
    tile_context_snapshot snapshot;
    snapshot.target = target;
    snapshot.player_pos = player_character.pos_bub( here );
    snapshot.in_bounds = here.inbounds( target );

    if( !snapshot.in_bounds ) {
        return snapshot;
    }

    snapshot.distance = square_dist( target.xy(), snapshot.player_pos.xy() );
    snapshot.is_self = target == snapshot.player_pos;
    snapshot.is_adjacent = target.z() == snapshot.player_pos.z() &&
                           !snapshot.is_self && snapshot.distance <= 1;
    snapshot.visible = player_character.sees( here, target );
    snapshot.player_inside = !here.is_outside( snapshot.player_pos );

    snapshot.terrain = here.ter( target );
    snapshot.furniture = here.furn( target );
    snapshot.terrain_capabilities = map_data_capabilities( snapshot.terrain.obj(), target );
    snapshot.furniture_capabilities = map_data_capabilities( snapshot.furniture.obj(), target );

    // Vehicle presence is a neutral fact here. Vehicle-specific open/close,
    // cargo and control capabilities depend on the concrete part(s) at this
    // mount point and are intentionally decoded by the vehicle provider.
    snapshot.has_vehicle = static_cast<bool>( here.veh_at( target ) );

    const Creature *const creature = get_creature_tracker().creature_at<>( target );
    snapshot.has_creature = snapshot.is_self || creature != nullptr;
    snapshot.creature_is_avatar = snapshot.is_self ||
                                  ( creature != nullptr && creature->is_avatar() );

    snapshot.item_count = here.i_at( target ).size();
    snapshot.has_field = here.has_field_at( target );
    snapshot.has_known_trap = here.can_see_trap_at( target, player_character );

    return snapshot;
}

bool tile_context_action::is_available() const
{
    return availability == tile_context_availability::ready;
}

bool tile_context_action::is_blocked() const
{
    return availability == tile_context_availability::blocked;
}

tile_context_action make_ready_tile_context_action(
    const tile_context_action_id id,
    const tile_context_section section,
    const tile_context_category category,
    const tripoint_bub_ms &target,
    translation label,
    const std::optional<action_id> keyboard_equivalent,
    const bool destructive,
    const bool noisy )
{
    tile_context_action result;
    result.id = id;
    result.section = section;
    result.category = category;
    result.label = std::move( label );
    result.target = target;
    result.availability = tile_context_availability::ready;
    result.destructive = destructive;
    result.noisy = noisy;
    result.keyboard_equivalent = keyboard_equivalent;
    return result;
}

tile_context_action make_blocked_tile_context_action(
    const tile_context_action_id id,
    const tile_context_section section,
    const tile_context_category category,
    const tripoint_bub_ms &target,
    translation label,
    translation denial_reason,
    const std::optional<action_id> keyboard_equivalent,
    const bool destructive,
    const bool noisy )
{
    tile_context_action result;
    result.id = id;
    result.section = section;
    result.category = category;
    result.label = std::move( label );
    result.target = target;
    result.availability = tile_context_availability::blocked;
    result.denial_reason = std::move( denial_reason );
    result.destructive = destructive;
    result.noisy = noisy;
    result.keyboard_equivalent = keyboard_equivalent;
    return result;
}

std::vector<tile_context_action> collect_tile_context_actions(
    const tile_context_snapshot &snapshot,
    const std::vector<tile_context_provider> &providers )
{
    std::vector<tile_context_action> result;
    for( const tile_context_provider provider : providers ) {
        if( provider != nullptr ) {
            provider( snapshot, result );
        }
    }
    return result;
}

bool tile_context_supports_open( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_open );
}

bool tile_context_supports_close( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_close );
}

bool tile_context_supports_go_up( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::goes_up );
}

bool tile_context_supports_go_down( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::goes_down );
}

bool tile_context_supports_interact( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_interact );
}

bool tile_context_supports_bash( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_bash );
}

bool tile_context_supports_pry( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_pry );
}

bool tile_context_supports_lockpick( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_lockpick );
}

bool tile_context_supports_boltcut( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_boltcut );
}

bool tile_context_supports_hacksaw( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_hacksaw );
}

bool tile_context_supports_oxytorch( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_oxytorch );
}

bool tile_context_supports_mine( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_mine );
}

bool tile_context_supports_deconstruct( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_deconstruct );
}

bool tile_context_supports_chop( const tile_context_snapshot &snapshot )
{
    return any_layer_capability( snapshot, &tile_context_layer_capabilities::supports_chop );
}

const char *tile_context_action_id_name( const tile_context_action_id id )
{
    switch( id ) {
        case tile_context_action_id::none:
            return "none";
        case tile_context_action_id::character_info:
            return "character_info";
        case tile_context_action_id::inventory:
            return "inventory";
        case tile_context_action_id::medical:
            return "medical";
        case tile_context_action_id::movement:
            return "movement";
        case tile_context_action_id::inspect:
            return "inspect";
        case tile_context_action_id::interact:
            return "interact";
        case tile_context_action_id::open:
            return "open";
        case tile_context_action_id::close:
            return "close";
        case tile_context_action_id::go_up:
            return "go_up";
        case tile_context_action_id::go_down:
            return "go_down";
        case tile_context_action_id::go_to_and_up:
            return "go_to_and_up";
        case tile_context_action_id::go_to_and_down:
            return "go_to_and_down";
        case tile_context_action_id::move_to:
            return "move_to";
        case tile_context_action_id::pickup:
            return "pickup";
        case tile_context_action_id::drop:
            return "drop";
        case tile_context_action_id::examine_items:
            return "examine_items";
        case tile_context_action_id::throw_item:
            return "throw_item";
        case tile_context_action_id::break_down:
            return "break_down";
        case tile_context_action_id::smash:
            return "smash";
        case tile_context_action_id::pry:
            return "pry";
        case tile_context_action_id::lockpick:
            return "lockpick";
        case tile_context_action_id::boltcut:
            return "boltcut";
        case tile_context_action_id::hacksaw:
            return "hacksaw";
        case tile_context_action_id::oxytorch:
            return "oxytorch";
        case tile_context_action_id::mine:
            return "mine";
        case tile_context_action_id::deconstruct:
            return "deconstruct";
        case tile_context_action_id::chop:
            return "chop";
        case tile_context_action_id::attack:
            return "attack";
        case tile_context_action_id::fire:
            return "fire";
        case tile_context_action_id::talk:
            return "talk";
        case tile_context_action_id::disarm:
            return "disarm";
        case tile_context_action_id::use_controls:
            return "use_controls";
    }
    return "unknown";
}

const char *tile_context_section_name( const tile_context_section section )
{
    switch( section ) {
        case tile_context_section::self:
            return "self";
        case tile_context_section::creature:
            return "creature";
        case tile_context_section::tile:
            return "tile";
        case tile_context_section::vehicle:
            return "vehicle";
        case tile_context_section::items:
            return "items";
        case tile_context_section::field_trap:
            return "field_trap";
        case tile_context_section::destination:
            return "destination";
    }
    return "unknown";
}

std::string tile_context_debug_string( const tile_context_snapshot &snapshot,
                                       const std::vector<tile_context_action> &actions )
{
    std::ostringstream out;
    out << "target=" << snapshot.target.to_string()
        << " player=" << snapshot.player_pos.to_string()
        << " in_bounds=" << snapshot.in_bounds
        << " distance=" << snapshot.distance
        << " self=" << snapshot.is_self
        << " adjacent=" << snapshot.is_adjacent
        << " visible=" << snapshot.visible
        << " vehicle=" << snapshot.has_vehicle
        << " creature=" << snapshot.has_creature
        << " avatar=" << snapshot.creature_is_avatar
        << " items=" << snapshot.item_count
        << " field=" << snapshot.has_field
        << " known_trap=" << snapshot.has_known_trap;

    for( const tile_context_action &action : actions ) {
        out << "\n  action=" << tile_context_action_id_name( action.id )
            << " section=" << tile_context_section_name( action.section )
            << " state=" << ( action.is_available() ? "ready" : "blocked" )
            << " label=\"" << action.label.translated() << '"';
        if( action.is_blocked() && !action.denial_reason.empty() ) {
            out << " reason=\"" << action.denial_reason.translated() << '"';
        }
        if( action.keyboard_equivalent ) {
            out << " key_action=" << action_ident( *action.keyboard_equivalent );
        }
        if( action.destructive ) {
            out << " destructive";
        }
        if( action.noisy ) {
            out << " noisy";
        }
    }

    return out.str();
}
