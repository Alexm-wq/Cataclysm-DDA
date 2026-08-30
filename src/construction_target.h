#pragma once
#ifndef CATA_SRC_CONSTRUCTION_TARGET_H
#define CATA_SRC_CONSTRUCTION_TARGET_H

#include <string>
#include <vector>

#include "construction.h"
#include "coords_fwd.h"
#include "type_id.h"

class Character;
class read_only_visitable;

enum class construction_operation : int {
    build,
    place,
    markers,
    remove
};

enum class construction_target_status : int {
    none,
    ready,
    unavailable_requirements,
    invalid_location,
    in_progress
};

struct construction_target_resolution {
    construction_id id = construction_id( -1 );
    construction_target_status status = construction_target_status::none;
    std::string reason;
    /** Applicable alternatives ordered best-first; id is always the chosen first entry. */
    std::vector<construction_id> alternative_ids;

    bool has_construction() const {
        return id.to_i() >= 0;
    }
    bool ready() const {
        return status == construction_target_status::ready;
    }
};

struct construction_context_action {
    construction_ui_intent intent = construction_ui_intent::build;
    std::string key;
    construction_target_resolution resolution;
};

construction_target_resolution resolve_construction_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target );
construction_target_resolution resolve_place_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target );
construction_target_resolution resolve_marker_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target );
construction_target_resolution resolve_remove_target(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target );
std::vector<construction_context_action> resolve_context_construction_actions(
    Character &who, const read_only_visitable &inventory,
    const tripoint_bub_ms &target );
construction_ui_intent construction_ui_intent_for( const construction &con );
bool construction_is_catalog_action( const construction &con );
bool construction_is_place_action( const construction &con );
bool construction_is_marker_action( const construction &con );
bool construction_has_place_source( const construction &con, const read_only_visitable &carried );
bool construction_is_remove_action( const construction &con );

#endif // CATA_SRC_CONSTRUCTION_TARGET_H
