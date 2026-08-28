#include "crafting_destination.h"

#include <algorithm>
#include <functional>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "character.h"
#include "creature.h"
#include "creature_tracker.h"
#include "enums.h"
#include "flag.h"
#include "game.h"
#include "iexamine.h"
#include "item.h"
#include "item_pocket.h"
#include "json.h"
#include "json_loader.h"
#include "line.h"
#include "map.h"
#include "map_selector.h"
#include "mapdata.h"
#include "pocket_type.h"
#include "ret_val.h"
#include "string_formatter.h"
#include "translations.h"
#include "veh_type.h"
#include "vehicle.h"
#include "vehicle_selector.h"
#include "vpart_position.h"
#include "vpart_range.h"

static const flag_id json_flag_NO_DROP( "NO_DROP" );
static const flag_id json_flag_NO_RELOAD( "NO_RELOAD" );

struct crafting_destination_target {
    item_location location;
    std::string saved_location;
    tripoint_abs_ms position;

    void resolve() {
        if( !saved_location.empty() ) {
            location.deserialize( json_loader::from_string( saved_location ).get_object() );
            // Bind the saved index to a safe reference before storage can change.
            static_cast<void>( location.get_item() );
            saved_location.clear();
        }
    }
};

static std::vector<std::weak_ptr<crafting_destination_target>> pending_destinations;

void resolve_crafting_destinations()
{
    pending_destinations.erase( std::remove_if( pending_destinations.begin(),
    pending_destinations.end(),
    []( const std::weak_ptr<crafting_destination_target> &pending ) {
        const std::shared_ptr<crafting_destination_target> target = pending.lock();
        if( !target || target->saved_location.empty() ) {
            return true;
        }
        if( !get_map().inbounds( target->position ) ) {
            return false;
        }
        target->resolve();
        return true;
    } ), pending_destinations.end() );
}

crafting_destination::crafting_destination( const crafting_destination_kind kind,
        const tripoint_abs_ms &position, const item_location &target ) :
    kind( kind ), position( position )
{
    if( target ) {
        target_ = std::make_shared<crafting_destination_target>();
        target_->location = target;
        target_->position = target.pos_abs();
    }
}

item_location crafting_destination::target() const
{
    if( !target_ ) {
        return item_location();
    }
    target_->resolve();
    return target_->location;
}

bool crafting_destination::operator==( const crafting_destination &other ) const
{
    return kind == other.kind && position == other.position && target() == other.target();
}

void crafting_destination::serialize( JsonOut &jsout ) const
{
    jsout.start_object();
    const char *name = "automatic";
    switch( kind ) {
        case crafting_destination_kind::automatic:
            break;
        case crafting_destination_kind::ground:
            name = "ground";
            break;
        case crafting_destination_kind::container:
            name = "container";
            break;
        case crafting_destination_kind::vehicle_cargo:
            name = "vehicle_cargo";
            break;
        case crafting_destination_kind::vehicle_tank:
            name = "vehicle_tank";
            break;
        case crafting_destination_kind::keg:
            name = "keg";
            break;
    }
    jsout.member( "kind", name );
    jsout.member( "position", target_ && target_->saved_location.empty() && target_->location ?
                  target_->location.pos_abs() : position );
    if( target_ ) {
        if( !target_->saved_location.empty() ) {
            jsout.member( "target", target_->saved_location );
        } else {
            std::ostringstream buffer;
            JsonOut target_json( buffer );
            target_->location.serialize( target_json );
            jsout.member( "target", buffer.str() );
        }
    }
    jsout.end_object();
}

void crafting_destination::deserialize( const JsonObject &obj )
{
    const std::string name = obj.get_string( "kind", "automatic" );
    kind = name == "ground" ? crafting_destination_kind::ground :
           name == "container" ? crafting_destination_kind::container :
           name == "vehicle_cargo" ? crafting_destination_kind::vehicle_cargo :
           name == "vehicle_tank" ? crafting_destination_kind::vehicle_tank :
           name == "keg" ? crafting_destination_kind::keg : crafting_destination_kind::automatic;
    obj.read( "position", position );
    target_.reset();
    if( obj.has_string( "target" ) ) {
        target_ = std::make_shared<crafting_destination_target>();
        target_->saved_location = obj.get_string( "target" );
        target_->position = position;
        pending_destinations.push_back( target_ );
    }
}

static bool reachable_destination( const Character &crafter, const tripoint_bub_ms &pos )
{
    const map &here = get_map();
    return here.inbounds( pos ) && pos.z() == crafter.pos_bub().z() &&
           square_dist( pos, crafter.pos_bub() ) <= 1 &&
           here.clear_path( crafter.pos_bub(), pos, 1, 1, 100 );
}

static bool usable_ground( const tripoint_bub_ms &pos )
{
    const map &here = get_map();
    return here.can_put_items_ter_furn( pos ) &&
           !here.has_flag( ter_furn_flag::TFLAG_DESTROY_ITEM, pos ) &&
           !here.has_flag( ter_furn_flag::TFLAG_NO_FLOOR, pos );
}

static std::optional<vpart_reference> destination_part( const crafting_destination &destination )
{
    const item_location target = destination.target();
    if( !target ) {
        return std::nullopt;
    }
    const vehicle_cursor *cursor = target.veh_cursor();
    if( !cursor || cursor->part < 0 || cursor->part >= cursor->veh.part_count() ) {
        return std::nullopt;
    }
    vehicle_part &part = cursor->veh.part( cursor->part );
    if( part.removed || part.is_broken() || &part.get_base() != target.get_item() ) {
        return std::nullopt;
    }
    return vpart_reference( cursor->veh, cursor->part );
}

/** Use the pocket's native failure codes, never translated-message matching. */
static bool storage_size_failure( const item &container, const item &result )
{
    for( const item_pocket *pocket : container.get_all_contained_pockets() ) {
        if( pocket->is_forbidden() ) {
            continue;
        }
        const ret_val<item_pocket::contain_code> fit = pocket->can_contain( result );
        if( !fit.success() && ( fit.value() == item_pocket::contain_code::ERR_TOO_BIG ||
                               fit.value() == item_pocket::contain_code::ERR_TOO_HEAVY ||
                               fit.value() == item_pocket::contain_code::ERR_NO_SPACE ||
                               fit.value() == item_pocket::contain_code::ERR_CANNOT_SUPPORT ) ) {
            return true;
        }
    }
    return false;
}

static ret_val<void> check_crafting_destination( const Character &crafter,
        const crafting_destination &destination, const item &result, bool *too_small = nullptr )
{
    const auto size_failure = [&]() {
        if( too_small ) {
            *too_small = true;
        }
    };
    if( too_small ) {
        *too_small = false;
    }
    map &here = get_map();
    if( destination.kind == crafting_destination_kind::automatic ) {
        return ret_val<void>::make_success();
    }
    const bool tracked = destination.kind == crafting_destination_kind::container ||
                         destination.kind == crafting_destination_kind::vehicle_cargo ||
                         destination.kind == crafting_destination_kind::vehicle_tank;
    const item_location target = destination.target();
    if( tracked && !target ) {
        return ret_val<void>::make_failure( _( "This destination is no longer available." ) );
    }
    if( ( destination.kind == crafting_destination_kind::vehicle_cargo ||
          destination.kind == crafting_destination_kind::vehicle_tank ) &&
        !destination_part( destination ) ) {
        return ret_val<void>::make_failure( _( "This vehicle storage is no longer available." ) );
    }
    const tripoint_bub_ms pos = tracked ? target.pos_bub( here ) :
                                 here.get_bub( destination.position );
    if( !reachable_destination( crafter, pos ) ) {
        return ret_val<void>::make_failure( _( "This destination is out of reach." ) );
    }

    item unit = result;
    if( unit.count_by_charges() ) {
        unit.charges = 1;
    }
    switch( destination.kind ) {
        case crafting_destination_kind::ground:
            if( !usable_ground( pos ) || result.has_flag( json_flag_NO_DROP ) ) {
                return ret_val<void>::make_failure( _( "You cannot place items on this tile." ) );
            }
            if( result.made_of( phase_id::LIQUID ) ) {
                return ret_val<void>::make_failure( _( "Liquids need a suitable container." ) );
            }
            if( here.i_at( pos ).amount_can_fit( unit ) <= 0 ) {
                size_failure();
                return ret_val<void>::make_failure( _( "There is no room here." ) );
            }
            break;
        case crafting_destination_kind::container: {
            item_location container = target;
            if( !container->has_pocket_type( pocket_type::CONTAINER ) ||
                container->has_flag( json_flag_NO_RELOAD ) ) {
                return ret_val<void>::make_failure( _( "This item cannot be used as a container." ) );
            }
            if( container.where_recursive() == item_location::type::map &&
                !here.accessible_items( pos ) ) {
                return ret_val<void>::make_failure( _( "This container is inaccessible." ) );
            }
            for( item_location parent = container; parent.has_parent();
                 parent = parent.parent_item() ) {
                if( !parent.parent_item() || !parent.parent_pocket() ||
                    parent.parent_pocket()->sealed() ) {
                    return ret_val<void>::make_failure( _( "This container is inside a sealed pocket." ) );
                }
            }
            if( result.is_bucket_nonempty() ) {
                return ret_val<void>::make_failure( _( "The contents would spill." ) );
            }
            if( result.made_of( phase_id::LIQUID ) ) {
                const bool allow_bucket = !container.has_parent() &&
                                          ( container.where() != item_location::type::character ||
                                            container == crafter.get_wielded_item() );
                std::string reason;
                if( container->get_remaining_capacity_for_liquid( unit, allow_bucket,
                        &reason ) <= 0 ) {
                    if( too_small ) {
                        *too_small = storage_size_failure( *container, unit );
                    }
                    return ret_val<void>::make_failure( reason );
                }
            }
            // Only the explicitly selected container's storage pockets, not a
            // magazine well or a different, nested container chosen implicitly.
            const ret_val<void> fit = container->can_contain( unit, false, false, true, true,
                                      item_location(), 10000000_ml, false );
            if( !fit.success() ) {
                if( too_small ) {
                    *too_small = storage_size_failure( *container, unit );
                }
                return fit;
            }
            const ret_val<void> parent_fit = container.parents_can_contain_recursive( &unit );
            if( !parent_fit.success() ) {
                size_failure();
            }
            return parent_fit;
        }
        case crafting_destination_kind::vehicle_cargo:
        case crafting_destination_kind::vehicle_tank: {
            const std::optional<vpart_reference> part = destination_part( destination );
            if( !part ) {
                return ret_val<void>::make_failure( _( "This vehicle storage is no longer available." ) );
            }
            if( destination.kind == crafting_destination_kind::vehicle_tank ) {
                if( !part->part().is_tank() || !result.made_of( phase_id::LIQUID ) ||
                    !part->part().can_reload( unit ) ) {
                    return ret_val<void>::make_failure( _( "This tank cannot hold this liquid, or is full." ) );
                }
            } else {
                if( !part->info().has_flag( VPFLAG_CARGO ) ||
                    result.has_flag( json_flag_NO_DROP ) || result.made_of( phase_id::LIQUID ) ) {
                    return ret_val<void>::make_failure( _( "This item does not fit in the vehicle storage." ) );
                }
                if( part->items().amount_can_fit( unit ) <= 0 ) {
                    size_failure();
                    return ret_val<void>::make_failure( _( "This item does not fit in the vehicle storage." ) );
                }
            }
            break;
        }
        case crafting_destination_kind::keg: {
            if( !iexamine::has_keg( pos ) || !result.made_of( phase_id::LIQUID ) ) {
                return ret_val<void>::make_failure( _( "This destination needs a liquid." ) );
            }
            map_stack stack = here.i_at( pos );
            if( !stack.empty() && ( stack.size() != 1 ||
                                   stack.only_item().typeId() != result.typeId() ) ) {
                return ret_val<void>::make_failure( _( "This container holds something else." ) );
            }
            if( here.stored_volume( pos ) + unit.volume() > here.furn( pos )->keg_capacity ) {
                size_failure();
                return ret_val<void>::make_failure( _( "This container is full." ) );
            }
            break;
        }
        case crafting_destination_kind::automatic:
            break;
    }
    return ret_val<void>::make_success();
}

ret_val<void> crafting_destination_can_accept( const Character &crafter,
        const crafting_destination &destination, const item &result )
{
    return check_crafting_destination( crafter, destination, result );
}

int crafting_destination_liquid_capacity( const Character &crafter,
        const crafting_destination &destination, const item &liquid )
{
    if( !liquid.made_of( phase_id::LIQUID ) ||
        !crafting_destination_can_accept( crafter, destination, liquid ).success() ) {
        return 0;
    }
    switch( destination.kind ) {
        case crafting_destination_kind::container: {
            const item_location target = destination.target();
            const ret_val<int> limit = target.max_charges_by_parent_recursive( liquid );
            return limit.success() ? std::min( limit.value(),
                                              target->get_remaining_capacity_for_liquid( liquid, crafter ) ) :
                   0;
        }
        case crafting_destination_kind::vehicle_tank:
            return destination_part( destination )->part().get_base()
                   .get_remaining_capacity_for_liquid( liquid );
        case crafting_destination_kind::keg: {
            map &here = get_map();
            const tripoint_bub_ms pos = here.get_bub( destination.position );
            return liquid.charges_per_volume( here.furn( pos )->keg_capacity -
                                              here.stored_volume( pos ) );
        }
        default:
            return 0;
    }
}

crafting_destination_tile crafting_destinations_at( Character &crafter,
        const tripoint_bub_ms &position, const std::vector<item> &results )
{
    map &here = get_map();
    crafting_destination_tile tile;
    tile.position = here.get_abs( position );
    if( !reachable_destination( crafter, position ) ) {
        return tile;
    }
    tile.dangerous = g->is_dangerous_tile( position );
    const Creature *creature = get_creature_tracker().creature_at( position );
    tile.dangerous = tile.dangerous || ( creature && creature != &crafter &&
                                       creature->attitude_to( crafter ) == Creature::Attitude::HOSTILE &&
                                       crafter.sees( here, *creature ) );
    tile.has_items = here.accessible_items( position ) && !here.i_at( position ).empty();

    const auto add_option = [&]( const crafting_destination_kind kind,
                                const item_location &target,
                                std::string name, const bool occupied, const int parent = -1 ) {
        crafting_destination_option option;
        option.destination = { kind, tile.position, target };
        option.name = std::move( name );
        option.has_items = occupied;
        option.parent = parent;
        for( const item &result : results ) {
            bool too_small = false;
            const ret_val<void> fit = check_crafting_destination( crafter, option.destination,
                                      result, &too_small );
            if( fit.success() ) {
                option.enabled = true;
                option.too_small = false;
                option.reason.clear();
                break;
            }
            if( option.reason.empty() ) {
                option.reason = fit.str();
                option.too_small = too_small;
            }
        }
        if( results.empty() ) {
            option.reason = _( "Select a recipe that produces an item." );
        }
        tile.options.push_back( std::move( option ) );
        return static_cast<int>( tile.options.size() ) - 1;
    };

    std::function<void( item_location, int )> add_containers;
    add_containers = [&]( item_location container, const int parent ) {
        if( !container || !container->has_pocket_type( pocket_type::CONTAINER ) ) {
            return;
        }
        const int index = add_option( crafting_destination_kind::container, container,
                                      container->display_name(), !container->empty_container(), parent );
        for( item *child : container->all_items_top( pocket_type::CONTAINER ) ) {
            const item_pocket *pocket = container->contained_where( *child );
            if( pocket && !pocket->sealed() ) {
                add_containers( item_location( container, child ), index );
            }
        }
    };

    int surface = -1;
    if( iexamine::has_keg( position ) ) {
        add_option( crafting_destination_kind::keg, item_location(), here.name( position ),
                    tile.has_items );
    } else if( usable_ground( position ) ) {
        // Furniture and the ground beneath it share one map stack, not two
        // independently addressable inventories.
        const int index = add_option( crafting_destination_kind::ground, item_location(),
                                      here.has_furn( position ) ? here.furnname( position ) : _( "Ground" ),
                                      tile.has_items );
        if( here.has_furn( position ) ) {
            surface = index;
        }
    }
    if( here.accessible_items( position ) ) {
        for( item &it : here.i_at( position ) ) {
            add_containers( item_location( map_cursor( position ), &it ), surface );
        }
    }
    if( const optional_vpart_position vp = here.veh_at( position ) ) {
        vehicle &veh = vp->vehicle();
        for( const vpart_reference &part : veh.get_all_parts() ) {
            if( part.pos_bub( here ) != position || part.part().removed ||
                part.part().is_broken() ) {
                continue;
            }
            item_location target = veh.part_base( part.part_index() );
            if( part.info().has_flag( VPFLAG_CARGO ) ) {
                tile.has_vehicle_storage = true;
                tile.has_items = tile.has_items || !part.items().empty();
                const int index = add_option( crafting_destination_kind::vehicle_cargo, target,
                                              string_format( "%s — %s", part.part().name(), veh.name ),
                                              !part.items().empty() );
                for( item &it : part.items() ) {
                    add_containers( item_location( vehicle_cursor( veh, part.part_index() ), &it ),
                                    index );
                }
            } else if( part.part().is_tank() ) {
                tile.has_vehicle_storage = true;
                tile.has_items = tile.has_items || part.part().ammo_remaining() > 0;
                add_option( crafting_destination_kind::vehicle_tank, target,
                            string_format( "%s — %s", part.part().name(), veh.name ),
                            part.part().ammo_remaining() > 0 );
            }
        }
    }
    const auto add_inventory = [&]( Character &owner, const std::string &name ) {
        if( position != owner.pos_bub() ) {
            return;
        }
        // Top-level worn and wielded items count as occupancy too, even when
        // none of them is a usable container for this particular recipe.
        std::vector<item_location> carried = owner.top_items_loc();
        if( const item_location wielded = owner.get_wielded_item() ) {
            carried.push_back( wielded );
        }
        crafting_destination_option inventory;
        inventory.name = name;
        inventory.has_items = !carried.empty();
        inventory.inventory_root = true;
        tile.has_items = tile.has_items || inventory.has_items;
        const int index = static_cast<int>( tile.options.size() );
        tile.options.push_back( std::move( inventory ) );
        for( const item_location &container : carried ) {
            add_containers( container, index );
        }
    };
    Character &player = get_player_character();
    add_inventory( player, _( "You" ) );
    if( &crafter != &player ) {
        add_inventory( crafter, crafter.get_name() );
    }
    tile.blocked = tile.options.empty();
    return tile;
}

bool place_crafting_result( Character &crafter, item &result,
                           const crafting_destination &destination )
{
    if( destination.kind == crafting_destination_kind::automatic ||
        !crafting_destination_can_accept( crafter, destination, result ).success() ) {
        return false;
    }
    map &here = get_map();
    int placed = 0;
    switch( destination.kind ) {
        case crafting_destination_kind::ground: {
            const tripoint_bub_ms pos = here.get_bub( destination.position );
            item portion = result;
            if( portion.count_by_charges() ) {
                portion.charges = std::min( portion.charges,
                                           here.i_at( pos ).amount_can_fit( portion ) );
            }
            if( !here.add_item_or_charges( pos, portion, false ).is_null() ) {
                placed = portion.count();
            }
            break;
        }
        case crafting_destination_kind::container: {
            item_location container = destination.target();
            if( result.count_by_charges() ) {
                const ret_val<int> parent_limit = container.max_charges_by_parent_recursive(
                                                     result );
                if( parent_limit.success() && parent_limit.value() > 0 ) {
                    placed = container->fill_with( result,
                                                  std::min( result.charges, parent_limit.value() ),
                                                  true, true, true, false, false,
                                                  container.carrier() );
                }
            } else if( container->put_in( result, pocket_type::CONTAINER, true,
                                         container.carrier() ).success() ) {
                placed = 1;
            }
            if( placed > 0 ) {
                container.on_contents_changed();
                container.make_active();
            }
            break;
        }
        case crafting_destination_kind::vehicle_cargo: {
            const vpart_reference part = *destination_part( destination );
            placed = result.count_by_charges() ?
                     part.vehicle().add_charges( here, part.part(), result ) :
                     part.vehicle().add_item( here, part.part(), result ).has_value() ? 1 : 0;
            break;
        }
        case crafting_destination_kind::vehicle_tank: {
            const int before = result.charges;
            crafter.pour_into( *destination_part( destination ), result );
            return result.charges == 0 && before > 0;
        }
        case crafting_destination_kind::keg:
            iexamine::pour_into_keg( here.get_bub( destination.position ), result, true );
            return result.charges == 0;
        case crafting_destination_kind::automatic:
            return false;
    }
    if( result.count_by_charges() ) {
        result.charges -= placed;
        return result.charges == 0;
    }
    return placed > 0;
}
