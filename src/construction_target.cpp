#include "construction_target.h"

#include <algorithm>
#include <array>
#include <map>
#include <optional>
#include <string>
#include <tuple>
#include <vector>

#include "character.h"
#include "construction.h"
#include "map.h"
#include "options.h"
#include "translations.h"

static const trait_id trait_DEBUG_HS( "DEBUG_HS" );

bool construction_is_remove_action( const construction &con )
{
    return con.action != construction_action::build;
}

construction_ui_intent construction_ui_intent_for( const construction &con )
{
    return con.ui_intent;
}

bool construction_is_catalog_action( const construction &con )
{
    return construction_ui_intent_for( con ) == construction_ui_intent::build;
}

bool construction_is_place_action( const construction &con )
{
    return construction_ui_intent_for( con ) == construction_ui_intent::place;
}

bool construction_is_marker_action( const construction &con )
{
    return construction_ui_intent_for( con ) == construction_ui_intent::marker;
}

bool construction_has_place_source( const construction &con, const read_only_visitable &carried )
{
    bool has_component_group = false;
    for( const std::vector<item_comp> &alternatives : con.requirements->get_components() ) {
        has_component_group = true;
        if( std::none_of( alternatives.begin(), alternatives.end(),
        [&carried]( const item_comp &component ) {
            return component.has( carried, is_crafting_component, 1, craft_flags::none );
        } ) ) {
            return false;
        }
    }
    return has_component_group;
}

static int removal_priority( const construction &con )
{
    return con.action == construction_action::remove_generic ? 1 : 0;
}

static std::optional<construction_target_resolution> common_target_rejection(
    Character &who, const tripoint_bub_ms &target, const bool detect_partial )
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
    if( detect_partial ) {
        const partial_con *partial = here.partial_con_at( target );
        if( partial == nullptr ) {
            return std::nullopt;
        }
        result.id = partial->id;
        result.status = construction_target_status::in_progress;
        result.reason = _( "There is already unfinished construction here." );
        return result;
    }
    return std::nullopt;
}

struct candidate_rank {
    const construction *candidate = nullptr;
    bool ready = false;
    bool blocked_by_darkness = false;
    bool meets_skills = false;
    bool has_requirements = false;
    float skill_deficit = 0.0f;
};

static candidate_rank rank_candidate( Character &who, const read_only_visitable &inventory,
                                      const construction &candidate )
{
    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );
    candidate_rank rank;
    rank.candidate = &candidate;
    rank.meets_skills = free_test_mode || who.meets_skill_requirements( candidate );
    if( !free_test_mode ) {
        for( const std::pair<const skill_id, int> &required : candidate.required_skills ) {
            rank.skill_deficit += std::max( 0.0f,
                                            required.second - who.get_skill_level( required.first ) );
        }
    }
    rank.has_requirements = free_test_mode || candidate.requirements->can_make_with_inventory(
                                inventory, is_crafting_component, 1, craft_flags::none, false );
    const bool eligible = free_test_mode || player_can_build( who, inventory, candidate, true );
    rank.blocked_by_darkness = !free_test_mode && eligible && who.fine_detail_vision_mod() >= 4 &&
                               !who.has_trait( trait_DEBUG_HS ) && !candidate.dark_craftable;
    rank.ready = eligible && !rank.blocked_by_darkness;
    return rank;
}

static auto candidate_sort_key( const candidate_rank &rank )
{
    const int availability = rank.ready ? 0 : rank.blocked_by_darkness ? 1 : 2;
    const int missing_dimensions = ( rank.meets_skills ? 0 : 1 ) +
                                   ( rank.has_requirements ? 0 : 1 );
    return std::make_tuple( availability, missing_dimensions, rank.skill_deficit,
                            rank.candidate->adjusted_time(), rank.candidate->str_id.str() );
}

static construction_target_resolution resolve_candidates(
    Character &who, const read_only_visitable &inventory,
    const std::vector<const construction *> &candidates,
    const tripoint_bub_ms &target, const std::string &ready_reason,
    const std::string &invalid_reason )
{
    std::vector<candidate_rank> applicable;
    for( const construction *candidate : candidates ) {
        if( candidate == nullptr || !can_construct( *candidate, target ) ) {
            continue;
        }
        applicable.push_back( rank_candidate( who, inventory, *candidate ) );
    }

    construction_target_resolution result;
    if( applicable.empty() ) {
        result.status = construction_target_status::invalid_location;
        result.reason = invalid_reason;
        return result;
    }

    std::sort( applicable.begin(), applicable.end(), []( const candidate_rank & lhs,
    const candidate_rank & rhs ) {
        return candidate_sort_key( lhs ) < candidate_sort_key( rhs );
    } );
    for( const candidate_rank &rank : applicable ) {
        result.alternative_ids.push_back( rank.candidate->id );
    }
    const candidate_rank &chosen = applicable.front();
    result.id = chosen.candidate->id;
    result.status = chosen.ready ? construction_target_status::ready :
                    construction_target_status::unavailable_requirements;
    result.reason = chosen.ready ? ready_reason : chosen.blocked_by_darkness ?
                    _( "It is too dark to construct right now." ) :
                    _( "This location is valid, but current skill, tool, or component requirements are not met." );
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
            common_target_rejection( who, target, true ) ) {
        return *rejected;
    }

    const std::vector<construction *> grouped = constructions_by_group( group );
    std::vector<const construction *> candidates;
    for( const construction *candidate : grouped ) {
        if( candidate != nullptr && construction_is_catalog_action( *candidate ) ) {
            candidates.push_back( candidate );
        }
    }
    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to build." ),
                               _( "The selected construction is not compatible with this tile." ) );
}

construction_target_resolution resolve_place_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target )
{
    construction_target_resolution result;
    if( group.is_null() ) {
        result.reason = _( "Select an item to place first." );
        return result;
    }
    if( const std::optional<construction_target_resolution> rejected =
            common_target_rejection( who, target, true ) ) {
        return *rejected;
    }

    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );
    const std::vector<construction *> grouped = constructions_by_group( group );
    std::vector<const construction *> candidates;
    for( const construction *candidate : grouped ) {
        if( candidate != nullptr && construction_is_place_action( *candidate ) &&
            ( free_test_mode || construction_has_place_source( *candidate, who ) ) ) {
            candidates.push_back( candidate );
        }
    }
    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to place." ),
                               _( "That carried item cannot be placed on this tile." ) );
}

construction_target_resolution resolve_marker_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target )
{
    construction_target_resolution result;
    if( group.is_null() ) {
        result.reason = _( "Select a marker first." );
        return result;
    }
    if( const std::optional<construction_target_resolution> rejected =
            common_target_rejection( who, target, true ) ) {
        return *rejected;
    }

    const std::vector<construction *> grouped = constructions_by_group( group );
    std::vector<const construction *> candidates;
    for( const construction *candidate : grouped ) {
        if( candidate != nullptr && construction_is_marker_action( *candidate ) ) {
            candidates.push_back( candidate );
        }
    }
    return resolve_candidates( who, inventory, candidates, target,
                               _( "Ready to mark." ),
                               _( "That marker cannot be used on this tile." ) );
}

construction_target_resolution resolve_remove_target(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target )
{
    if( const std::optional<construction_target_resolution> rejected =
            common_target_rejection( who, target, false ) ) {
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

std::vector<construction_context_action> resolve_context_construction_actions(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target )
{
    std::vector<construction_context_action> result;
    if( common_target_rejection( who, target, false ) ) {
        return result;
    }

    const std::array<construction_ui_intent, 6> contextual_intents = {
        construction_ui_intent::repair,
        construction_ui_intent::finish,
        construction_ui_intent::modify,
        construction_ui_intent::upgrade,
        construction_ui_intent::terrain_work,
        construction_ui_intent::decorate
    };

    std::map<construction_ui_intent, std::map<std::string, std::vector<const construction *>>> buckets;
    for( const construction &con : get_constructions() ) {
        const construction_ui_intent intent = construction_ui_intent_for( con );
        if( std::find( contextual_intents.begin(), contextual_intents.end(), intent ) ==
            contextual_intents.end() ) {
            continue;
        }
        const std::string key = !con.ui_action.empty() ? con.ui_action :
                                intent == construction_ui_intent::repair ? "repair" : con.group.str();
        buckets[intent][key].push_back( &con );
    }

    for( const construction_ui_intent intent : contextual_intents ) {
        const auto intent_bucket = buckets.find( intent );
        if( intent_bucket == buckets.end() ) {
            continue;
        }
        for( const auto &bucket : intent_bucket->second ) {
            std::string ready_reason = _( "Ready." );
            switch( intent ) {
                case construction_ui_intent::repair:
                    ready_reason = _( "Ready to repair." );
                    break;
                case construction_ui_intent::finish:
                    ready_reason = _( "Ready to finish." );
                    break;
                case construction_ui_intent::modify:
                    ready_reason = _( "Ready to modify." );
                    break;
                case construction_ui_intent::upgrade:
                    ready_reason = _( "Ready to upgrade." );
                    break;
                case construction_ui_intent::terrain_work:
                    ready_reason = _( "Ready for terrain work." );
                    break;
                case construction_ui_intent::decorate:
                    ready_reason = _( "Ready to decorate." );
                    break;
                case construction_ui_intent::marker:
                    ready_reason = _( "Ready to mark." );
                    break;
                case construction_ui_intent::build:
                case construction_ui_intent::place:
                case construction_ui_intent::marker:
                case construction_ui_intent::remove:
                    break;
            }

            const construction_target_resolution resolution = resolve_candidates(
                        who, inventory, bucket.second, target, ready_reason,
                        _( "This tile has no applicable contextual construction action." ) );
            if( resolution.has_construction() ) {
                result.push_back( construction_context_action{ intent, bucket.first, resolution } );
            }
        }
    }
    return result;
}
