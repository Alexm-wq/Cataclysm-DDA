#pragma once
#ifndef CATA_SRC_TILE_CONTEXT_H
#define CATA_SRC_TILE_CONTEXT_H

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "action.h"
#include "coordinates.h"
#include "translation.h"
#include "type_id.h"

class avatar;
class map;

/** Stable identifiers for actions exposed by the map tile context system. */
enum class tile_context_action_id {
    none,

    // Avatar/self context.
    character_info,
    inventory,
    medical,
    movement,

    // Generic target interaction.
    inspect,
    interact,

    // Terrain/furniture/vehicle interaction.
    open,
    close,
    go_up,
    go_down,
    go_to_and_up,
    go_to_and_down,
    move_to,

    // Item interaction.
    pickup,
    drop,
    examine_items,
    throw_item,

    // Destructive/tool-gated interaction.
    break_down,
    smash,
    pry,
    lockpick,
    boltcut,
    hacksaw,
    oxytorch,
    mine,
    deconstruct,
    chop,

    // Creature/ranged interaction.
    attack,
    fire,
    talk,

    // Other targeted interaction.
    disarm,
    use_controls
};

/**
 * Section in the single context menu for a clicked coordinate.
 * Multiple providers may contribute to the same section; for example terrain
 * and furniture both contribute to the tile section.
 */
enum class tile_context_section {
    self,
    creature,
    tile,
    vehicle,
    items,
    field_trap,
    destination
};

/** Broad ordering/grouping within a section. */
enum class tile_context_category {
    immediate,
    movement,
    items,
    destructive,
    ranged,
    information
};

/**
 * NOT_APPLICABLE is deliberately not represented here.  A provider expresses
 * that state by not returning an action descriptor at all.
 */
enum class tile_context_availability {
    ready,
    blocked
};

/**
 * Side-effect-free structural capabilities of one layer at the clicked tile.
 * These are facts about the target, not decisions about whether the avatar can
 * perform the action right now.
 */
struct tile_context_layer_capabilities {
    bool supports_open = false;
    bool supports_close = false;
    bool goes_up = false;
    bool goes_down = false;
    bool supports_interact = false;

    bool supports_bash = false;
    bool supports_pry = false;
    bool supports_lockpick = false;
    bool supports_boltcut = false;
    bool supports_hacksaw = false;
    bool supports_oxytorch = false;
    bool supports_mine = false;
    bool supports_deconstruct = false;
    bool supports_chop = false;

    bool climbable = false;
    bool console = false;
    bool locked = false;
    bool open_close_inside_only = false;
};

/**
 * Read-only facts describing one clicked map coordinate.  No item_location,
 * Creature pointer, vehicle pointer, or execution callback is retained here;
 * mutable targets will be resolved and revalidated at execution time.
 */
struct tile_context_snapshot {
    tripoint_bub_ms target;
    tripoint_bub_ms player_pos;

    bool in_bounds = false;
    int distance = 0;
    bool is_self = false;
    bool is_adjacent = false;
    bool visible = false;
    bool player_inside = false;

    ter_id terrain;
    furn_id furniture;

    tile_context_layer_capabilities terrain_capabilities;
    tile_context_layer_capabilities furniture_capabilities;
    tile_context_layer_capabilities vehicle_capabilities;

    bool has_vehicle = false;
    bool has_creature = false;
    bool creature_is_avatar = false;
    // Ground/map-stack items only. Vehicle cargo is resolved by the vehicle provider.
    std::size_t item_count = 0;
    bool has_field = false;
    bool has_known_trap = false;
};

/**
 * Build the neutral, side-effect-free facts for one clicked map coordinate.
 * This deliberately does not generate actions or retain mutable world pointers.
 */
tile_context_snapshot build_tile_context_snapshot( map &here, const avatar &player_character,
        const tripoint_bub_ms &target );

/**
 * One applicable context action.  If availability is blocked, denial_reason
 * should contain the concise reason shown by the future menu.
 *
 * keyboard_equivalent is descriptive only: it lets the UI display the user's
 * configured binding for an equivalent canonical action.  It is never used to
 * simulate keyboard input.
 */
struct tile_context_action {
    tile_context_action_id id = tile_context_action_id::none;
    tile_context_section section = tile_context_section::tile;
    tile_context_category category = tile_context_category::immediate;

    translation label;
    tripoint_bub_ms target;

    tile_context_availability availability = tile_context_availability::ready;
    translation denial_reason;

    bool destructive = false;
    bool noisy = false;
    std::optional<action_id> keyboard_equivalent;

    bool is_available() const;
    bool is_blocked() const;
};

/** Helper constructors which keep READY and BLOCKED descriptors explicit. */
tile_context_action make_ready_tile_context_action(
    tile_context_action_id id,
    tile_context_section section,
    tile_context_category category,
    const tripoint_bub_ms &target,
    translation label,
    std::optional<action_id> keyboard_equivalent = std::nullopt,
    bool destructive = false,
    bool noisy = false );

tile_context_action make_blocked_tile_context_action(
    tile_context_action_id id,
    tile_context_section section,
    tile_context_category category,
    const tripoint_bub_ms &target,
    translation label,
    translation denial_reason,
    std::optional<action_id> keyboard_equivalent = std::nullopt,
    bool destructive = false,
    bool noisy = false );

/**
 * Providers are side-effect-free candidate producers.  NOT_APPLICABLE means
 * simply not appending an entry to the output vector.
 */
using tile_context_provider = void ( * )( const tile_context_snapshot &,
        std::vector<tile_context_action> & );

std::vector<tile_context_action> collect_tile_context_actions(
    const tile_context_snapshot &snapshot,
    const std::vector<tile_context_provider> &providers );

/** Combined structural capability queries across terrain/furniture/vehicle layers. */
bool tile_context_supports_open( const tile_context_snapshot &snapshot );
bool tile_context_supports_close( const tile_context_snapshot &snapshot );
bool tile_context_supports_go_up( const tile_context_snapshot &snapshot );
bool tile_context_supports_go_down( const tile_context_snapshot &snapshot );
bool tile_context_supports_interact( const tile_context_snapshot &snapshot );
bool tile_context_supports_bash( const tile_context_snapshot &snapshot );
bool tile_context_supports_pry( const tile_context_snapshot &snapshot );
bool tile_context_supports_lockpick( const tile_context_snapshot &snapshot );
bool tile_context_supports_boltcut( const tile_context_snapshot &snapshot );
bool tile_context_supports_hacksaw( const tile_context_snapshot &snapshot );
bool tile_context_supports_oxytorch( const tile_context_snapshot &snapshot );
bool tile_context_supports_mine( const tile_context_snapshot &snapshot );
bool tile_context_supports_deconstruct( const tile_context_snapshot &snapshot );
bool tile_context_supports_chop( const tile_context_snapshot &snapshot );

/** Debug helpers for the future mouse-UI diagnostics path. */
const char *tile_context_action_id_name( tile_context_action_id id );
const char *tile_context_section_name( tile_context_section section );
std::string tile_context_debug_string( const tile_context_snapshot &snapshot,
                                       const std::vector<tile_context_action> &actions );

#endif // CATA_SRC_TILE_CONTEXT_H
