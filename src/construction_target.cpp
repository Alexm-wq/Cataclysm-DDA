#include "construction_target.h"

#include <algorithm>
#include <optional>
#include <string>
#include <vector>

#include "character.h"
#include "construction.h"
#include "map.h"
#include "translations.h"

static const trait_id trait_DEBUG_HS( "DEBUG_HS" );
static const construction_category_id construction_category_DECONSTRUCT( "DECONSTRUCT" );
static const construction_group_str_id construction_group_deconstruct_furniture(
    "deconstruct_furniture" );
static const construction_group_str_id construction_group_deconstruct_simple_furniture(
    "deconstruct_simple_furniture" );

static bool has_prefix( const std::string &value, const std::string &prefix )
{
    return value.rfind( prefix, 0 ) == 0;
}

bool construction_is_remove_action( const construction &con )
{
    const std::string group = con.group.str();
    return con.category == construction_category_DECONSTRUCT ||
           con.group == construction_group_deconstruct_furniture ||
           con.group == construction_group_deconstruct_simple_furniture ||
           has_prefix( group, "remove_" ) || has_prefix( group, "deconstruct_" );
}

static int removal_priority( const construction &con )
{
    if( con.category == construction_category_DECONSTRUCT ) {
        return 0;
    }
    if( has_prefix( con.group.str(), "remove_" ) ) {
        return 1;
    }
    if( has_prefix( con.group.str(), "deconstruct_" ) &&
        con.group != construction_group_deconstruct_furniture &&
        con.group != construction_group_deconstruct_simple_furniture ) {
        return 1;
    }
    if( con.group == construction_group_deconstruct_simple_furniture ) {
        return 2;
    }
    return 3;
}

static std::optional<construction_target_resolution> common_target_rejection(
    Character &who, const tripoint_bub_ms &target )
{
    map &here = get_map();
    construction_target_resolution result;
    if( target.z() != who.pos_bub().z() ) {
        result.status = construction_target_status::invalid_location;
        result.reason = _( "Construction is limited to the current z-level." );
        return result;
    }
    if( !who.sees( here, target ) ) {
        result.status = construction_target_status::invalid_location;
        result.reason = _( "You cannot inspect construction validity at a tile you cannot see." );
        return result;
    }
    if( target == who.pos_bub() ) {
        result.status = construction_target_status::invalid_location;
        result.reason = _( "Move away from the target tile before working there." );
        return result;
    }
    if( const partial_con *partial = here.partial_con_at( target ) ) {
        result.id = partial->id;
        result.status = construction_target_status::in_progress;
        result.reason = _( "There is already unfinished construction here." );
        return result;
    }
    return std::nullopt;
}

static construction_target_resolution resolve_candidates(
    Character &who, const read_only_visitable &inventory,
    const std::vector<const construction *> &candidates,
    const tripoint_bub_ms &target, const std::string &ready_reason,
    const std::string &invalid_reason )
{
    construction_target_resolution result;
    const construction *fallback = nullptr;
    bool blocked_by_darkness = false;
    for( const construction *candidate : candidates ) {
        if( candidate == nullptr || !can_construct( *candidate, target ) ) {
            continue;
        }
        if( fallback == nullptr ) {
            fallback = candidate;
        }
        if( player_can_build( who, inventory, *candidate, true ) ) {
            if( who.fine_detail_vision_mod() >= 4 && !who.has_trait( trait_DEBUG_HS ) &&
                !candidate->dark_craftable ) {
                blocked_by_darkness = true;
                continue;
            }
            result.id = candidate->id;
            result.status = construction_target_status::ready;
            result.reason = ready_reason;
            return result;
        }
    }

    if( fallback != nullptr ) {
        result.id = fallback->id;
        result.status = construction_target_status::unavailable_requirements;
        result.reason = blocked_by_darkness ? _( "It is too dark to construct right now." ) :
                        _( "This location is valid, but current skill, tool, or component requirements are not met." );
        return result;
    }
    result.status = construction_target_status::invalid_location;
    result.reason = invalid_reason;
    return result;
}

construction_target_resolution resolve_construction_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target )
{
    construction_target_resolution result;
    if( group.is_null() ) {
        result.reason = _( "Select a construction first." );
        return result;
    }
    if( const std::optional<construction_target_resolution> rejected =
            common_target_rejection( who, target ) ) {
        return *rejected;
    }

    const std::vector<construction *> grouped = constructions_by_group( group );
    std::vector<const construction *> candidates( grouped.begin(), grouped.end() );
    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to build." ),
                               _( "The selected construction is not compatible with this tile." ) );
}

construction_target_resolution resolve_remove_target(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target )
{
    if( const std::optional<construction_target_resolution> rejected =
            common_target_rejection( who, target ) ) {
        return *rejected;
    }

    std::vector<const construction *> candidates;
    for( const construction &con : get_constructions() ) {
        if( construction_is_remove_action( con ) && can_construct( con, target ) ) {
            candidates.push_back( &con );
        }
    }
    if( candidates.empty() ) {
        construction_target_resolution result;
        result.status = construction_target_status::invalid_location;
        result.reason = _( "The selected tile has no removable construction." );
        return result;
    }

    const auto best = std::min_element( candidates.begin(), candidates.end(),
    []( const construction * lhs, const construction * rhs ) {
        return removal_priority( *lhs ) < removal_priority( *rhs );
    } );
    const int best_priority = removal_priority( **best );
    candidates.erase( std::remove_if( candidates.begin(), candidates.end(),
    [best_priority]( const construction * candidate ) {
        return removal_priority( *candidate ) != best_priority;
    } ), candidates.end() );

    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to remove." ),
                               _( "The selected tile has no removable construction." ) );
}
