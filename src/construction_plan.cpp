#include "construction_plan.h"

#include <algorithm>
#include <set>
#include <unordered_set>
#include <utility>
#include <vector>

#include "character.h"
#include "clzones.h"
#include "construction.h"
#include "construction_group.h"
#include "construction_target.h"
#include "faction.h"
#include "game_constants.h"
#include "map.h"
#include "memory_fast.h"
#include "translations.h"

namespace
{

static const zone_type_id zone_type_CONSTRUCTION_BLUEPRINT( "CONSTRUCTION_BLUEPRINT" );

faction_id plan_faction( Character &who )
{
    const faction *fac = who.get_faction();
    return fac == nullptr ? your_fac : fac->id;
}

construction_id final_plan_construction( const construction_id &start )
{
    if( !start.is_valid() ) {
        return construction_id( -1 );
    }
    blueprint_options resolver;
    std::set<construction_id> visited;
    return resolver.get_final_construction( get_constructions(), start, visited );
}

bool construction_result_exists( map &here, const tripoint_bub_ms &target,
                                 const construction &con )
{
    if( con.post_terrain.empty() ) {
        return false;
    }
    return con.post_is_furniture ?
           here.furn( target ) == furn_str_id( con.post_terrain ) :
           here.ter( target ) == ter_str_id( con.post_terrain );
}

std::vector<const zone_data *> active_plan_zones_at( zone_manager &manager,
        const faction_id &fac, const tripoint_abs_ms &target )
{
    std::vector<const zone_data *> result;
    for( const zone_data *zone : manager.get_zones_at(
             target, zone_type_CONSTRUCTION_BLUEPRINT, fac ) ) {
        if( zone != nullptr && zone->get_enabled() && !zone->get_temporarily_disabled() ) {
            result.push_back( zone );
        }
    }
    return result;
}

const zone_data *active_plan_zone_at( zone_manager &manager, const faction_id &fac,
                                     const tripoint_abs_ms &target )
{
    const std::vector<const zone_data *> zones = active_plan_zones_at( manager, fac, target );
    // The multi-construction executor also uses the first matching blueprint.
    // Report the same intent when legacy zones happen to overlap.
    return zones.empty() ? nullptr : zones.front();
}

std::vector<std::pair<tripoint_abs_ms, tripoint_abs_ms>> split_around_point(
    const tripoint_abs_ms &start, const tripoint_abs_ms &end,
    const tripoint_abs_ms &removed )
{
    const int min_x = std::min( start.x(), end.x() );
    const int max_x = std::max( start.x(), end.x() );
    const int min_y = std::min( start.y(), end.y() );
    const int max_y = std::max( start.y(), end.y() );
    const int min_z = std::min( start.z(), end.z() );
    const int max_z = std::max( start.z(), end.z() );
    std::vector<std::pair<tripoint_abs_ms, tripoint_abs_ms>> result;

    const auto add = [&result]( const int x1, const int y1, const int z1,
    const int x2, const int y2, const int z2 ) {
        if( x1 <= x2 && y1 <= y2 && z1 <= z2 ) {
            result.emplace_back( tripoint_abs_ms( x1, y1, z1 ),
                                 tripoint_abs_ms( x2, y2, z2 ) );
        }
    };

    add( min_x, min_y, min_z, max_x, max_y, removed.z() - 1 );
    add( min_x, min_y, removed.z() + 1, max_x, max_y, max_z );
    add( min_x, min_y, removed.z(), max_x, removed.y() - 1, removed.z() );
    add( min_x, removed.y() + 1, removed.z(), max_x, max_y, removed.z() );
    add( min_x, removed.y(), removed.z(), removed.x() - 1, removed.y(), removed.z() );
    add( removed.x() + 1, removed.y(), removed.z(), max_x, removed.y(), removed.z() );
    return result;
}

bool remove_active_plan_zones_at( Character &who, const tripoint_abs_ms &target )
{
    zone_manager &manager = zone_manager::get_manager();
    const faction_id fac = plan_faction( who );
    bool removed_any = false;

    // Removing one tile from a legacy rectangular blueprint must preserve the
    // rest of that rectangle.  Work one zone at a time because erasing a zone
    // invalidates references into the manager's backing vector.
    while( true ) {
        zone_data *match = nullptr;
        for( zone_manager::ref_zone_data ref : manager.get_zones( fac ) ) {
            zone_data &zone = ref.get();
            if( zone.get_type() == zone_type_CONSTRUCTION_BLUEPRINT &&
                zone.get_enabled() && !zone.get_temporarily_disabled() &&
                zone.has_inside( target ) ) {
                match = &zone;
                break;
            }
        }
        if( match == nullptr ) {
            break;
        }

        const blueprint_options *source_options =
            dynamic_cast<const blueprint_options *>( &match->get_options() );
        if( source_options == nullptr ) {
            break;
        }
        const std::string name = match->get_name();
        const bool invert = match->get_invert();
        const bool enabled = match->get_enabled();
        const tripoint_abs_ms start = match->get_start_point();
        const tripoint_abs_ms end = match->get_end_point();
        const blueprint_options options = *source_options;
        const std::vector<std::pair<tripoint_abs_ms, tripoint_abs_ms>> remnants =
            split_around_point( start, end, target );

        if( !manager.remove( *match ) ) {
            break;
        }
        removed_any = true;
        for( const auto &remnant : remnants ) {
            manager.add( name, zone_type_CONSTRUCTION_BLUEPRINT, fac, invert, enabled,
                         remnant.first, remnant.second,
                         make_shared_fast<blueprint_options>( options ), true );
        }
    }
    if( removed_any ) {
        manager.cache_data();
    }
    return removed_any;
}

construction_plan make_plan( Character &who, const zone_data &zone,
                             const tripoint_abs_ms &position )
{
    construction_plan result;
    result.position = position;
    result.name = zone.get_name();
    const blueprint_options *options =
        dynamic_cast<const blueprint_options *>( &zone.get_options() );
    if( options == nullptr ) {
        result.reason = _( "The stored construction plan has invalid options." );
        return result;
    }
    result.group = options->get_group();
    result.desired = final_plan_construction( options->get_index() );
    if( !result.desired.is_valid() ) {
        result.reason = _( "The construction used by this plan no longer exists." );
        return result;
    }
    const construction &desired = result.desired.obj();
    result.group = desired.group;
    result.name = desired.group->name();

    map &here = get_map();
    const tripoint_bub_ms target = here.get_bub( position );
    if( !here.inbounds( target ) ) {
        result.status = construction_plan_status::unreachable;
        result.reason = _( "This plan is outside the currently loaded map." );
        return result;
    }
    if( construction_result_exists( here, target, desired ) ) {
        result.status = construction_plan_status::completed;
        result.reason = _( "The planned result is already complete." );
        return result;
    }
    if( const partial_con *partial = here.partial_con_at( target ) ) {
        const bool matches_plan = partial->id.is_valid() &&
                                  final_plan_construction( partial->id ) == result.desired;
        result.status = matches_plan ? construction_plan_status::in_progress :
                        construction_plan_status::invalidated;
        result.reason = matches_plan ?
                        _( "Construction is already in progress here." ) :
                        partial->id.is_valid() ?
                        _( "Different unfinished construction is blocking this plan." ) :
                        _( "The unfinished construction data here is invalid." );
        return result;
    }
    if( target.z() != who.pos_bub().z() ) {
        result.status = construction_plan_status::unreachable;
        result.reason = _( "Construction plans can only be executed on the current z-level." );
        return result;
    }
    if( !who.sees( here, target ) ) {
        result.status = construction_plan_status::unreachable;
        result.reason = _( "This planned tile is not currently visible." );
        return result;
    }

    const construction_target_resolution resolution = resolve_construction_target(
                who, who.crafting_inventory(), result.group, target );
    if( resolution.status == construction_target_status::invalid_location ||
        !resolution.has_construction() ) {
        result.status = construction_plan_status::invalidated;
        result.reason = resolution.reason.empty() ?
                        _( "The planned construction is no longer valid on this tile." ) :
                        resolution.reason;
        return result;
    }
    if( resolution.status == construction_target_status::unavailable_requirements ) {
        result.status = construction_plan_status::missing_requirements;
        result.reason = resolution.reason;
        return result;
    }
    const ret_val<void> reachable = can_reach_construction_target( who, target );
    if( !reachable.success() ) {
        result.status = construction_plan_status::unreachable;
        result.reason = reachable.str();
        return result;
    }
    result.status = construction_plan_status::ready;
    result.reason = _( "Ready to execute." );
    return result;
}

} // namespace

construction_plan_mutation set_construction_plan(
    Character &who, const construction_group_str_id &group,
    const tripoint_bub_ms &target )
{
    construction_plan_mutation result;
    if( group.is_null() ) {
        result.message = _( "Select a construction before placing a plan." );
        return result;
    }
    if( get_map().partial_con_at( target ) != nullptr ) {
        result.message = _( "Finish the unfinished construction before planning something here." );
        return result;
    }
    const construction_target_resolution resolution = resolve_construction_target(
                who, who.crafting_inventory(), group, target );
    if( !resolution.has_construction() ||
        resolution.status == construction_target_status::invalid_location ) {
        result.message = resolution.reason.empty() ?
                         _( "That construction cannot be planned on this tile." ) :
                         resolution.reason;
        return result;
    }
    result.desired = final_plan_construction( resolution.id );
    if( !result.desired.is_valid() ) {
        result.message = _( "The selected construction has no valid final stage." );
        return result;
    }

    map &here = get_map();
    const tripoint_abs_ms target_abs = here.get_abs( target );
    zone_manager &manager = zone_manager::get_manager();
    const faction_id fac = plan_faction( who );
    const std::vector<const zone_data *> existing = active_plan_zones_at(
                manager, fac, target_abs );
    const bool all_same = !existing.empty() && std::all_of( existing.begin(), existing.end(),
    [&result]( const zone_data * zone ) {
        const blueprint_options *options =
            dynamic_cast<const blueprint_options *>( &zone->get_options() );
        return options != nullptr &&
               final_plan_construction( options->get_index() ) == result.desired;
    } );
    if( all_same ) {
        result.success = true;
        result.change = construction_plan_change::unchanged;
        result.message = _( "That construction is already planned here." );
        return result;
    }

    const bool replaced = remove_active_plan_zones_at( who, target_abs );
    const construction &desired = result.desired.obj();
    manager.add( desired.group->name(), zone_type_CONSTRUCTION_BLUEPRINT, fac, false, true,
                 target_abs, target_abs,
                 make_shared_fast<blueprint_options>( desired.post_terrain, desired.group,
                         result.desired ), true );
    manager.cache_data();
    result.success = true;
    result.change = replaced ? construction_plan_change::replaced :
                    construction_plan_change::created;
    result.message = replaced ? _( "Construction plan replaced." ) :
                     _( "Construction plan added." );
    return result;
}

ret_val<void> remove_construction_plan( Character &who,
                                        const tripoint_abs_ms &target )
{
    if( !remove_active_plan_zones_at( who, target ) ) {
        return ret_val<void>::make_failure( _( "There is no active construction plan here." ) );
    }
    return ret_val<void>::make_success();
}

std::optional<construction_plan> get_construction_plan(
    Character &who, const tripoint_abs_ms &target )
{
    zone_manager &manager = zone_manager::get_manager();
    const zone_data *zone = active_plan_zone_at( manager, plan_faction( who ), target );
    if( zone == nullptr ) {
        return std::nullopt;
    }
    return make_plan( who, *zone, target );
}

std::vector<construction_plan> get_nearby_construction_plans(
    Character &who, const int range )
{
    zone_manager &manager = zone_manager::get_manager();
    map &here = get_map();
    const tripoint_abs_ms center = here.get_abs( who.pos_bub() );
    const faction_id fac = plan_faction( who );
    std::vector<construction_plan> result;
    const std::unordered_set<tripoint_abs_ms> points = manager.get_near(
                zone_type_CONSTRUCTION_BLUEPRINT, center, range, nullptr, fac );
    result.reserve( points.size() );
    for( const tripoint_abs_ms &point : points ) {
        if( point.z() != center.z() ) {
            continue;
        }
        const zone_data *zone = active_plan_zone_at( manager, fac, point );
        if( zone != nullptr ) {
            result.push_back( make_plan( who, *zone, point ) );
        }
    }
    std::sort( result.begin(), result.end(), [&center]( const construction_plan &lhs,
    const construction_plan &rhs ) {
        if( lhs.status != rhs.status ) {
            return static_cast<int>( lhs.status ) < static_cast<int>( rhs.status );
        }
        if( lhs.name != rhs.name ) {
            return lhs.name < rhs.name;
        }
        const int left_distance = square_dist( lhs.position, center );
        const int right_distance = square_dist( rhs.position, center );
        return left_distance != right_distance ? left_distance < right_distance :
               lhs.position < rhs.position;
    } );
    return result;
}

std::string construction_plan_status_name( const construction_plan_status status )
{
    switch( status ) {
        case construction_plan_status::ready:
            return _( "Ready" );
        case construction_plan_status::missing_requirements:
            return _( "Missing requirements" );
        case construction_plan_status::unreachable:
            return _( "Unreachable" );
        case construction_plan_status::invalidated:
            return _( "Invalidated" );
        case construction_plan_status::in_progress:
            return _( "In progress" );
        case construction_plan_status::completed:
            return _( "Completed" );
    }
    return _( "Unknown" );
}
