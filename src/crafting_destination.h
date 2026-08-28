#pragma once
#ifndef CATA_SRC_CRAFTING_DESTINATION_H
#define CATA_SRC_CRAFTING_DESTINATION_H

#include <memory>
#include <string>
#include <vector>

#include "coordinates.h"
#include "item_location.h"

class Character;
class JsonObject;
class JsonOut;
class item;
template<typename T> class ret_val;
struct crafting_destination_target;

enum class crafting_destination_kind {
    automatic,
    ground,
    container,
    vehicle_cargo,
    vehicle_tank,
    keg
};

/** Finished-output destination, independent of the in-progress craft's workbench.
 * Absolute coordinates survive reality-bubble shifts; item locations track the
 * actual container or installed vehicle part instead of whichever replaces it.
 */
struct crafting_destination {
    crafting_destination_kind kind = crafting_destination_kind::automatic;
    tripoint_abs_ms position = tripoint_abs_ms::zero;

    crafting_destination() = default;
    crafting_destination( crafting_destination_kind kind, const tripoint_abs_ms &position,
                          const item_location &target );
    item_location target() const;

    bool operator==( const crafting_destination &other ) const;
    void serialize( JsonOut &jsout ) const;
    void deserialize( const JsonObject &obj );

    private:
        std::shared_ptr<crafting_destination_target> target_;
};

/** Resolve saved item handles after the world is loaded, before items can move.
 * In-progress crafts can be loaded before their destination's map or inventory.
 */
void resolve_crafting_destinations();

struct crafting_destination_option {
    crafting_destination destination;
    std::string name;
    bool has_items = false;
    bool enabled = false;
    std::string reason;
    // Depth-first hierarchy. Bare ground is a separate leaf, never a parent.
    int parent = -1;
    // An inventory is an expandable group, not an implicit output destination.
    bool inventory_root = false;
};

struct crafting_destination_tile {
    tripoint_abs_ms position = tripoint_abs_ms::zero;
    bool blocked = true;
    bool dangerous = false;
    bool has_items = false;
    bool has_vehicle_storage = false;
    std::vector<crafting_destination_option> options;
};

/** Discover storage on one adjacent tile, including accessible nested containers.
 * Results are previews only: eligibility is checked again for every actual item.
 */
crafting_destination_tile crafting_destinations_at( Character &crafter,
        const tripoint_bub_ms &position, const std::vector<item> &results );

/** Whether at least one unit can be placed there now, using normal storage rules. */
ret_val<void> crafting_destination_can_accept( const Character &crafter,
        const crafting_destination &destination, const item &result );

int crafting_destination_liquid_capacity( const Character &crafter,
        const crafting_destination &destination, const item &liquid );

/** Place as much as fits. Returns true if all was placed; otherwise leaves the
 * unplaced item/charges in result for the caller's normal fallback handling.
 */
bool place_crafting_result( Character &crafter, item &result,
                           const crafting_destination &destination );

#endif // CATA_SRC_CRAFTING_DESTINATION_H
