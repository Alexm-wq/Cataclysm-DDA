#pragma once
#ifndef CATA_SRC_CONSTRUCTION_PLAN_H
#define CATA_SRC_CONSTRUCTION_PLAN_H

#include <optional>
#include <string>
#include <vector>

#include "coordinates.h"
#include "ret_val.h"
#include "type_id.h"

class Character;

enum class construction_plan_status : int {
    ready,
    missing_requirements,
    unreachable,
    invalidated,
    in_progress,
    completed
};

struct construction_plan {
    tripoint_abs_ms position;
    construction_group_str_id group = construction_group_str_id::NULL_ID();
    construction_id desired = construction_id( -1 );
    construction_plan_status status = construction_plan_status::invalidated;
    std::string name;
    std::string reason;
};

enum class construction_plan_change : int {
    created,
    replaced,
    unchanged
};

struct construction_plan_mutation {
    bool success = false;
    construction_plan_change change = construction_plan_change::unchanged;
    construction_id desired = construction_id( -1 );
    std::string message;
};

construction_plan_mutation set_construction_plan(
    Character &who, const construction_group_str_id &group,
    const tripoint_bub_ms &target );

ret_val<void> remove_construction_plan( Character &who,
                                        const tripoint_abs_ms &target );

std::optional<construction_plan> get_construction_plan(
    Character &who, const tripoint_abs_ms &target );

std::vector<construction_plan> get_nearby_construction_plans(
    Character &who, int range );

std::string construction_plan_status_name( construction_plan_status status );

#endif // CATA_SRC_CONSTRUCTION_PLAN_H
