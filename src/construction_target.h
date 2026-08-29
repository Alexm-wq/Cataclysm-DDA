#pragma once
#ifndef CATA_SRC_CONSTRUCTION_TARGET_H
#define CATA_SRC_CONSTRUCTION_TARGET_H

#include <string>

#include "coords_fwd.h"
#include "type_id.h"

class Character;
class read_only_visitable;

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

    bool has_construction() const {
        return id.to_i() >= 0;
    }
    bool ready() const {
        return status == construction_target_status::ready;
    }
};

construction_target_resolution resolve_construction_target(
    Character &who, const read_only_visitable &inventory,
    const construction_group_str_id &group, const tripoint_bub_ms &target );

#endif // CATA_SRC_CONSTRUCTION_TARGET_H
