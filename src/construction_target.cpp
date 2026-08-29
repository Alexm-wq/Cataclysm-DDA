#include "construction_target.h"

#include <vector>

#include "character.h"
#include "construction.h"
#include "map.h"
#include "translations.h"

static const trait_id trait_DEBUG_HS( "DEBUG_HS" );

construction_target_resolution resolve_construction_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target )
{
    construction_target_resolution result;
    if( group.is_null() ) {
        result.reason = _( "Select a construction first." );
        return result;
    }

    map &here = get_map();
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
        result.reason = _( "Move away from the target tile before building there." );
        return result;
    }

    if( const partial_con *partial = here.partial_con_at( target ) ) {
        result.id = partial->id;
        result.status = construction_target_status::in_progress;
        result.reason = _( "There is already unfinished construction here." );
        return result;
    }

    const std::vector<construction *> candidates = constructions_by_group( group );
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
            result.reason = _( "Ready to build." );
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
    result.reason = _( "The selected construction is not compatible with this tile." );
    return result;
}
