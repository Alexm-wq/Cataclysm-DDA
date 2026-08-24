#include "advanced_inv.h"

#include <algorithm>
#include <climits>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <initializer_list>
#include <iterator>
#include <list>
#include <memory>
#include <optional>
#include <string>
#include <tuple>
#include <type_traits>
#include <unordered_set>
#include <utility>
#include <vector>

#include "activity_actor_definitions.h"
#include "advanced_inv_area.h"
#include "advanced_inv_listitem.h"
#include "advanced_inv_pagination.h"
#include "auto_pickup.h"
#include "avatar.h"
#include "avatar_action.h"
#include "cached_options.h"
#include "calendar.h"
#include "cata_assert.h"
#include "cata_scope_helpers.h"
#include "catacharset.h"
#include "character.h"
#include "color.h"
#include "coordinates.h"
#include "creature.h"
#include "creature_tracker.h"
#include "debug.h"
#include "enums.h"
#include "game.h"
#include "game_constants.h"
#include "input.h"
#include "input_context.h"
#include "inventory.h"
#include "inventory_ui.h"
#include "item.h"
#include "item_category.h"
#include "item_contents.h"
#include "item_location.h"
#include "itype.h"
#include "localized_comparator.h"
#include "map.h"
#include "messages.h"
#include "options.h"
#include "output.h"
#include "panels.h"
#include "pimpl.h"
#include "player_activity.h"
#include "point.h"
#include "ret_val.h"
#include "sdltiles.h"
#include "string_formatter.h"
#include "string_input_popup.h"
#include "translations.h"
#include "type_id.h"
#include "ui_iteminfo.h"
#include "ui_manager.h"
#include "uistate.h"
#include "units.h"
#include "units_utility.h"
#include "vehicle.h"

#if defined(__ANDROID__)
#   include <SDL_keyboard.h>
#endif

static const flag_id json_flag_NO_RELOAD( "NO_RELOAD" );
static const flag_id json_flag_NO_UNLOAD( "NO_UNLOAD" );
static const efftype_id effect_incorporeal( "incorporeal" );
static const trait_id trait_SHELL2( "SHELL2" );
static const trait_id trait_SHELL3( "SHELL3" );

using move_all_entry = std::pair<std::pair<int, int>, drop_or_stash_item_info>;

namespace io
{

template<>
std::string enum_to_string<aim_exit>( const aim_exit v )
{
    switch( v ) {
        // *INDENT-OFF*
        case aim_exit::none: return "none";
        case aim_exit::okay: return "okay";
        case aim_exit::re_entry: return "re_entry";
        // *INDENT-ON*
        case aim_exit::last:
            break;
    }
    cata_fatal( "Invalid aim_exit" );
}

template<>
std::string enum_to_string<aim_entry>( const aim_entry v )
{
    switch( v ) {
        // *INDENT-OFF*
        case aim_entry::START: return "START";
        case aim_entry::VEHICLE: return "VEHICLE";
        case aim_entry::MAP: return "MAP";
        case aim_entry::RESET: return "RESET";
        // *INDENT-ON*
        case aim_entry::last:
            break;
    }
    cata_fatal( "Invalid aim_entry" );
}

} // namespace io

namespace
{
std::unique_ptr<advanced_inventory> advinv;

const char *workspace_preset_name( const inventory_workspace_preset preset )
{
    switch( preset ) {
        case inventory_workspace_preset::manage:
            return "manage";
        case inventory_workspace_preset::pickup:
            return "pickup";
        case inventory_workspace_preset::pickup_all:
            return "pickup_all";
        case inventory_workspace_preset::drop:
            return "drop";
        case inventory_workspace_preset::wear:
            return "wear";
        case inventory_workspace_preset::take_off:
            return "take_off";
        case inventory_workspace_preset::wield:
            return "wield";
        case inventory_workspace_preset::reload:
            return "reload";
    }
    return "unknown";
}
} // namespace

void create_advanced_inv()
{
    if( !advinv ) {
        advinv = std::make_unique<advanced_inventory>( inventory_workspace_entry() );
    }
    advinv->display();
    // keep the UI and its ui_adaptor running if we're returning
    if( uistate.transfer_save.exit_code != aim_exit::re_entry || get_avatar().activity.is_null() ) {
        advinv.reset();
        cancel_aim_processing();
    }
}

void create_advanced_inv( const inventory_workspace_entry &entry )
{
    if( !advinv ) {
        advinv = std::make_unique<advanced_inventory>( entry );
    }
    advinv->display();
    if( uistate.transfer_save.exit_code != aim_exit::re_entry || get_avatar().activity.is_null() ) {
        advinv.reset();
        cancel_aim_processing();
    }
}

void temp_hide_advanced_inv()
{
    if( advinv ) {
        advinv->temp_hide();
    }
}

// *INDENT-OFF*
advanced_inventory::advanced_inventory( const inventory_workspace_entry &entry )
    : recalc( true )
    , entry( entry )
    , src( left )
    , dest( right )
      // panes don't need initialization, they are recalculated immediately
    , squares( {
    {
        //               pos in window
        { AIM_INVENTORY, point( 25, 2 ), tripoint::zero,       _( "Inventory" ),          _( "IN" ),  "I", "ITEMS_INVENTORY", AIM_INVENTORY},
        { AIM_SOUTHWEST, point( 29, 3 ), tripoint::south_west, _( "South West" ),         _( "SW" ),  _( "SW" ), "ITEMS_SW", AIM_WEST},
        { AIM_SOUTH,     point( 34, 3 ), tripoint::south,      _( "South" ),              _( "S" ),   _( "S" ),  "ITEMS_S",  AIM_SOUTHWEST},
        { AIM_SOUTHEAST, point( 39, 3 ), tripoint::south_east, _( "South East" ),         _( "SE" ),  _( "SE" ), "ITEMS_SE", AIM_SOUTH},
        { AIM_WEST,      point( 29, 2 ), tripoint::west,       _( "West" ),               _( "W" ),   _( "W" ),  "ITEMS_W",  AIM_NORTHWEST},
        { AIM_CENTER,    point( 34, 2 ), tripoint::zero,       _( "Directly below you" ), _( "DN" ),  _( "You" ), "ITEMS_CE", AIM_CENTER},
        { AIM_EAST,      point( 40, 2 ), tripoint::east,       _( "East" ),               _( "E" ),   _( "E" ),  "ITEMS_E",  AIM_SOUTHEAST},
        { AIM_NORTHWEST, point( 29, 1 ), tripoint::north_west, _( "North West" ),         _( "NW" ),  _( "NW" ), "ITEMS_NW", AIM_NORTH},
        { AIM_NORTH,     point( 34, 1 ), tripoint::north,      _( "North" ),              _( "N" ),   _( "N" ),  "ITEMS_N",  AIM_NORTHEAST},
        { AIM_NORTHEAST, point( 39, 1 ), tripoint::north_east, _( "North East" ),         _( "NE" ),  _( "NE" ), "ITEMS_NE", AIM_EAST},
        { AIM_DRAGGED,   point( 22, 3 ), tripoint::zero,       _( "Grabbed Vehicle" ),    _( "GR" ),  "D", "ITEMS_DRAGGED_CONTAINER", AIM_DRAGGED},
        { AIM_ALL,       point( 25, 3 ), tripoint::zero,       _( "Surrounding area" ),   _( "AL" ),  "A", "ITEMS_AROUND",    AIM_ALL},
        { AIM_CONTAINER, point( 25, 1 ), tripoint::zero,       _( "Container" ),          _( "CN" ),  "C", "ITEMS_CONTAINER", AIM_CONTAINER},
        { AIM_PARENT,    point( 22, 1 ), tripoint::zero,       "",                        "",         "X", "ITEMS_PARENT",    AIM_PARENT},
        { AIM_WORN,      point( 22, 2 ), tripoint::zero,       _( "Worn Items" ),         _( "WR" ),  "W", "ITEMS_WORN",      AIM_WORN}
    }
} )
{
    save_state = &uistate.transfer_save;
}
// *INDENT-ON*

advanced_inventory::~advanced_inventory()
{
    save_settings( false );
    if( save_state->exit_code != aim_exit::re_entry ) {
        save_state->exit_code = aim_exit::okay;
    }
    // Only refresh if we exited manually, otherwise we're going to be right back
    if( exit ) {
        get_player_character().check_item_encumbrance_flag();
    }
}

void advanced_inventory::save_settings( bool only_panes )
{
    if( !only_panes ) {
        save_state->active_left = ( src == left );
    }
    for( int i = 0; i < NUM_PANES; ++i ) {
        panes[i].save_settings();
    }
}

void advanced_inventory::load_settings()
{
    aim_exit aim_code = static_cast<aim_exit>( save_state->exit_code );
    panes[left].load_settings( save_state->saved_area, squares, aim_code == aim_exit::re_entry );
    panes[right].load_settings( save_state->saved_area_right, squares, aim_code == aim_exit::re_entry );
    // In-vehicle flags are set dynamically inside advanced_inventory_pane::load_settings,
    // which means the flags may end up the same even if the areas are also the same. To
    // avoid this, we use the saved in-vehicle flags instead.
    if( panes[left].get_area() == panes[right].get_area() ) {
        panes[left].set_area( squares[panes[left].get_area()], save_state->pane.in_vehicle );
        // Use the negated in-vehicle flag of the left pane to ensure different
        // in-vehicle flags.
        panes[right].set_area( squares[panes[right].get_area()], !save_state->pane.in_vehicle );
    }
    save_state->exit_code = aim_exit::none;
}

std::string advanced_inventory::get_sortname( advanced_inv_sortby sortby )
{
    switch( sortby ) {
        case SORTBY_NONE:
            return _( "none" );
        case SORTBY_NAME:
            return _( "name" );
        case SORTBY_WEIGHT:
            return _( "weight" );
        case SORTBY_VOLUME:
            return _( "volume" );
        case SORTBY_DENSITY:
            return _( "density" );
        case SORTBY_CHARGES:
            return _( "charges" );
        case SORTBY_CATEGORY:
            return _( "category" );
        case SORTBY_DAMAGE:
            return _( "offensive power" );
        case SORTBY_AMMO:
            return _( "ammo/charge type" );
        case SORTBY_SPOILAGE:
            return _( "spoilage" );
        case SORTBY_PRICE:
            return _( "barter value" );
        case SORTBY_PRICEPERVOLUME:
            return _( "barter value / volume" );
        case SORTBY_PRICEPERWEIGHT:
            return _( "barter value / weight" );
        case SORTBY_STACKS:
            return _( "amount" );
    }
    return "!BUG!";
}

bool advanced_inventory::get_square( const std::string &action, aim_location &ret )
{
    for( advanced_inv_area &s : squares ) {
        if( s.actionname == action ) {
            ret = screen_relative_location( s.id );
            return true;
        }
    }
    return false;
}

aim_location advanced_inventory::screen_relative_location( aim_location area )
{
    if( g->is_tileset_isometric() ) {
        return squares[area].relative_location;
    } else {
        return area;
    }
}

inline std::string advanced_inventory::get_location_key( aim_location area )
{
    return squares[area].minimapname;
}

bool advanced_inventory::location_has_items( const aim_location location ) const
{
    const advanced_inv_area &square = squares[location];
    if( location < AIM_SOUTHWEST || location > AIM_NORTHEAST ) {
        return square.get_item_count() > 0;
    }
    if( !get_map().i_at( square.pos ).empty() ) {
        return true;
    }
    return square.can_store_in_vehicle() && !square.get_vehicle_stack().empty();
}

bool advanced_inventory::location_is_dangerous( const aim_location location ) const
{
    if( location < AIM_SOUTHWEST || location > AIM_NORTHEAST ) {
        return false;
    }

    const advanced_inv_area &square = squares[location];
    if( g->is_dangerous_tile( square.pos ) ) {
        return true;
    }

    const avatar &u = get_avatar();
    const map &here = get_map();
    const Creature *critter = get_creature_tracker().creature_at( square.pos );
    return critter != nullptr && critter != &u &&
           critter->attitude_to( u ) == Creature::Attitude::HOSTILE && u.sees( here, *critter );
}

bool advanced_inventory::location_is_fully_blocked( const aim_location location ) const
{
    return location >= AIM_SOUTHWEST && location <= AIM_NORTHEAST &&
           !squares[location].canputitemsloc && !location_has_items( location );
}

void advanced_inventory::init()
{
    const bool is_re_entry = save_state->exit_code == aim_exit::re_entry;
    for( advanced_inv_area &square : squares ) {
        square.init();
    }

    panes[left].save_state = &save_state->pane;
    panes[right].save_state = &save_state->pane_right;

    load_settings();

    src = ( save_state->active_left ) ? left : right;
    dest = ( save_state->active_left ) ? right : left;

    if( !is_re_entry ) {
        apply_entry_preset();
    }

    //sanity check, badly initialized values may cause problem in move_all_items( see cata_assert() )
    if( panes[src].get_area() == AIM_ALL && panes[dest].get_area() == AIM_ALL ) {
        panes[dest].set_area( AIM_INVENTORY );
    }

    log_workspace_event( string_format( "opened preset=%s left=%d right=%d active=%s",
                                        workspace_preset_name( entry.preset ),
                                        static_cast<int>( panes[left].get_area() ),
                                        static_cast<int>( panes[right].get_area() ),
                                        src == left ? "left" : "right" ) );
}

void advanced_inventory::log_workspace_event( const std::string &event ) const
{
    if( get_option<bool>( "INVENTORY_WORKSPACE_DEBUG_LOG" ) ) {
        DebugLog( D_INFO, DC_ALL ) << "[inventory_workspace] " << event;
    }
}

void advanced_inventory::set_workspace_status( const std::string &message, const bool log_event )
{
    workspace_status = message;
    if( log_event ) {
        log_workspace_event( message );
    }
    if( ui ) {
        ui->invalidate_ui();
    }
}

void advanced_inventory::apply_entry_preset()
{
    if( entry.preset == inventory_workspace_preset::manage ) {
        workspace_status = _( "Drag between panes, right-click an item for actions." );
        return;
    }

    const auto target_area = [this]() {
        if( entry.target ) {
            for( int i = AIM_SOUTHWEST; i <= AIM_NORTHEAST; ++i ) {
                if( squares[i].pos == *entry.target ) {
                    return static_cast<aim_location>( i );
                }
            }
        }
        return AIM_CENTER;
    };
    const auto set_pane = [this]( const side pane_side, const aim_location location ) {
        advanced_inventory_pane &pane = panes[pane_side];
        pane.container = item_location::nowhere;
        pane.container_base_loc = NUM_AIM_LOCATIONS;
        bool show_vehicle = false;
        if( squares[location].can_store_in_vehicle() ) {
            const bool has_vehicle_items = !squares[location].get_vehicle_stack().empty();
            const bool has_ground_items = !get_map().i_at( squares[location].pos ).empty();
            show_vehicle = has_vehicle_items && !has_ground_items;
        }
        pane.set_area( squares[location], show_vehicle );
        pane.index = 0;
        pane.recalc = true;
    };

    switch( entry.preset ) {
        case inventory_workspace_preset::pickup:
            set_pane( left, target_area() );
            set_pane( right, AIM_INVENTORY );
            src = left;
            workspace_status = _( "Pickup: move items from the left pane into Inventory or Worn." );
            break;
        case inventory_workspace_preset::pickup_all:
            set_pane( left, AIM_ALL );
            set_pane( right, AIM_INVENTORY );
            src = left;
            workspace_status = _( "Nearby pickup: choose any adjacent tile on either pane." );
            break;
        case inventory_workspace_preset::drop:
            set_pane( left, AIM_INVENTORY );
            set_pane( right, target_area() );
            src = left;
            workspace_status = _( "Drop: select a destination tile on the right, then drag or move items." );
            break;
        case inventory_workspace_preset::wear:
            set_pane( left, AIM_INVENTORY );
            set_pane( right, AIM_WORN );
            src = left;
            workspace_status = _( "Wear: moving an item to Worn applies the game's normal wear rules." );
            break;
        case inventory_workspace_preset::take_off:
            set_pane( left, AIM_WORN );
            set_pane( right, AIM_INVENTORY );
            src = left;
            workspace_status = _( "Equipment: move worn items to Inventory or an adjacent tile." );
            break;
        case inventory_workspace_preset::wield:
            set_pane( left, AIM_INVENTORY );
            set_pane( right, AIM_WORN );
            src = left;
            workspace_status = _( "Wield: right-click an item and choose Wield." );
            break;
        case inventory_workspace_preset::reload:
            set_pane( left, AIM_WORN );
            set_pane( right, AIM_INVENTORY );
            src = left;
            workspace_status = _( "Reload: select a gun or magazine and click Reload." );
            break;
        case inventory_workspace_preset::manage:
            break;
    }
    dest = src == left ? right : left;
}

void advanced_inventory::print_items( side p, bool active )
{
    map &here = get_map();
    advanced_inventory_pane &pane = panes[p];
    const auto &items = pane.items;
    const catacurses::window &window = pane.window;
    const int index = pane.index;
    bool compact = TERMX <= 100;
    pane.other_cont = -1;
    std::unordered_set<const item *> other_pane_conts;
    if( panes[-p + 1].container ) {
        item_location parent_recursive = panes[-p + 1].container;
        other_pane_conts.insert( parent_recursive.get_item() );
        while( parent_recursive.has_parent() ) {
            parent_recursive = parent_recursive.parent_item();
            other_pane_conts.insert( parent_recursive.get_item() );
        }
    }

    int columns = getmaxx( window );
    std::string spaces( columns - 4, ' ' );

    nc_color norm = active ? c_white : c_dark_gray;

    Character &player_character = get_player_character();
    //print inventory's current and total weight + volume
    if( pane.get_area() == AIM_INVENTORY || pane.get_area() == AIM_WORN ||
        ( pane.get_area() == AIM_CONTAINER && pane.container ) ) {

        double weight_carried;
        double weight_capacity;
        units::volume volume_carried;
        units::volume volume_capacity;
        if( pane.get_area() == AIM_CONTAINER ) {
            weight_carried = convert_weight( pane.container->get_total_contained_weight() );
            weight_capacity = convert_weight( pane.container->get_total_weight_capacity() );
            volume_carried = pane.container->get_total_contained_volume();
            volume_capacity = pane.container->get_total_capacity();
        } else {
            weight_carried = convert_weight( player_character.weight_carried() );
            weight_capacity = convert_weight( player_character.weight_capacity() );
            volume_carried = player_character.volume_carried();
            volume_capacity = player_character.volume_capacity();
        }
        // align right, so calculate formatted head length
        const std::string formatted_head = string_format( "%.1f/%.1f %s  %s/%s %s",
                                           weight_carried, weight_capacity, weight_units(),
                                           format_volume( volume_carried ),
                                           format_volume( volume_capacity ),
                                           volume_units_abbr() );
        const int hrightcol = columns - 1 - utf8_width( formatted_head );
        nc_color color = weight_carried > weight_capacity ? c_red : c_light_green;
        mvwprintz( window, point( hrightcol, 4 ), color, "%.1f", weight_carried );
        wprintz( window, c_light_gray, "/%.1f %s  ", weight_capacity, weight_units() );
        color = volume_carried.value() > volume_capacity.value() ?
                c_red : c_light_green;
        wprintz( window, color, format_volume( volume_carried ) );
        wprintz( window, c_light_gray, "/%s %s", format_volume( volume_capacity ), volume_units_abbr() );
    } else {
        //print square's current and total weight + volume
        std::string formatted_head;
        if( pane.get_area() == AIM_ALL ) {
            formatted_head = string_format( "%3.1f %s  %s %s",
                                            convert_weight( squares[pane.get_area()].weight ),
                                            weight_units(),
                                            format_volume( squares[pane.get_area()].volume ),
                                            volume_units_abbr() );
        } else {
            units::volume maxvolume = 0_ml;
            advanced_inv_area &s = squares[pane.get_area()];
            if( pane.get_area() == AIM_CONTAINER && pane.container ) {
                maxvolume = pane.container->get_total_capacity();
            } else if( pane.in_vehicle() ) {
                maxvolume = s.get_vehicle_stack().max_volume();
            } else {
                maxvolume = here.max_volume( s.pos );
            }
            formatted_head = string_format( "%3.1f %s  %s/%s %s",
                                            convert_weight( pane.in_vehicle() ? s.weight_veh : s.weight ),
                                            weight_units(),
                                            format_volume( pane.in_vehicle() ? s.volume_veh : s.volume ),
                                            format_volume( maxvolume ),
                                            volume_units_abbr() );
        }
        mvwprintz( window, point( columns - 1 - utf8_width( formatted_head ), 4 ), norm, formatted_head );
    }

    //print header row and determine max item name length
    // Last printable column
    const int lastcol = columns - 2;
    const size_t name_startpos = compact ? 1 : 4;
    const size_t src_startpos = lastcol - 18;
    const size_t amt_startpos = lastcol - 15;
    const size_t weight_startpos = lastcol - 10;
    const size_t vol_startpos = lastcol - 4;
    // Default name length
    int max_name_length = amt_startpos - name_startpos - 1;

    //~ Items list header (length type 1). Table fields length without spaces: amt - 4, weight - 5, vol - 4.
    const int table_hdr_len1 = utf8_width( _( "amt weight vol" ) );
    //~ Items list header (length type 2). Table fields length without spaces: src - 2, amt - 4, weight - 5, vol - 4.
    const int table_hdr_len2 = utf8_width( _( "src amt weight vol" ) );

    mvwprintz( window, point( compact ? 1 : 4, 5 ), c_light_gray, _( "Name (charges)" ) );
    if( pane.get_area() == AIM_ALL && !compact ) {
        mvwprintz( window, point( lastcol - table_hdr_len2 + 1, 5 ), c_light_gray,
                   _( "src amt weight vol" ) );
        // 1 for space
        max_name_length = src_startpos - name_startpos - 1;
    } else {
        mvwprintz( window, point( lastcol - table_hdr_len1 + 1, 5 ), c_light_gray, _( "amt weight vol" ) );
    }

    int pageStart = 0; // index of first item on current page

    advanced_inventory_pagination pagination( linesPerPage, pane );
    if( !items.empty() ) {
        // paginate up to the current item (to count pages)
        for( int i = 0; i <= index; i++ ) {
            const bool pagebreak = pagination.step( i );
            if( pagebreak ) {
                pageStart = i;
            }
        }
    }

    pagination.reset_page();
    for( size_t i = pageStart; i < items.size(); i++ ) {
        const advanced_inv_listitem &sitem = items[i];
        const int line = pagination.line;
        int item_line = line;
        if( pane.sortby == SORTBY_CATEGORY && pagination.new_category( sitem.cat ) ) {
            // don't put category header at bottom of page
            if( line == linesPerPage - 1 ) {
                break;
            }
            // insert category header
            mvwprintz( window, point( ( columns - utf8_width( sitem.cat->name_header() ) - 6 ) / 2, 6 + line ),
                       c_cyan, "[%s]", sitem.cat->name_header() );
            item_line = line + 1;
        }

        const item &it = *sitem.items.front();
        const bool selected = active && index == static_cast<int>( i );

        nc_color thiscolor;
        if( !active ) {
            thiscolor = norm;
        } else if( it.is_food_container() && !it.is_craft() && it.num_item_stacks() == 1 ) {
            thiscolor = it.all_items_top().front()->color_in_inventory();
        } else {
            thiscolor = it.color_in_inventory();
        }
        nc_color thiscolordark = c_dark_gray;
        nc_color print_color;

        if( selected ) {
            if( !other_pane_conts.empty() && other_pane_conts.count( &it ) == 1 ) {
                pane.other_cont = item_line;
                thiscolor = c_white_yellow;
            } else {
                thiscolor = inCategoryMode && pane.sortby == SORTBY_CATEGORY ? c_white_red : hilite( c_white );
            }
            thiscolordark = hilite( thiscolordark );
            if( compact ) {
                mvwprintz( window, point( 1, 6 + item_line ), thiscolor, "  %s", spaces );
            } else {
                mvwprintz( window, point( 1, 6 + item_line ), thiscolor, ">>%s", spaces );
            }
        } else if( !other_pane_conts.empty() && other_pane_conts.count( &it ) == 1 ) {
            pane.other_cont = item_line;
            thiscolor = i_brown;
            mvwprintz( window, point( 1, 6 + item_line ), thiscolor, spaces );
        }

        std::string item_name;
        std::string stolen_string;
        bool stolen = false;
        if( !it.is_owned_by( player_character, true ) ) {
            stolen_string = "<color_light_red>!</color>";
            stolen = true;
        }
        if( it.is_money() ) {
            //Count charges
            // TODO: transition to the item_location system used for the normal inventory
            unsigned int charges_total = 0;
            for( const item_location &item : sitem.items ) {
                charges_total += item->ammo_remaining( );
            }
            if( stolen ) {
                item_name = string_format( "%s %s", stolen_string, it.display_money( sitem.items.size(),
                                           charges_total ) );
            } else {
                item_name = it.display_money( sitem.items.size(), charges_total );
            }
        } else {
            if( stolen ) {
                item_name = string_format( "%s %s", stolen_string, it.display_name() );
            } else {
                item_name = it.display_name();
            }
        }
        if( get_option<bool>( "ITEM_SYMBOLS" ) ) {
            item_name = string_format( "%s %s", it.symbol(), item_name );
        }

        //print item name
        trim_and_print( window, point( compact ? 1 : 4, 6 + item_line ), max_name_length, thiscolor,
                        item_name );

        // Leave an obvious mouse target for entering a container.  The two
        // characters to the left are still reserved for the selection marker.
        if( !compact && it.is_container() ) {
            mvwprintz( window, point( 3, 6 + item_line ), thiscolor, "▸" );
        }

        //print src column
        // TODO: specify this is coming from a vehicle!
        if( pane.get_area() == AIM_ALL && !compact ) {
            mvwprintz( window, point( src_startpos, 6 + item_line ), thiscolor, squares[sitem.area].shortname );
        }

        //print "amount" column
        int it_amt = sitem.stacks;
        if( it_amt > 1 ) {
            print_color = thiscolor;
            if( it_amt > 9999 ) {
                it_amt = 9999;
                print_color = selected ? hilite( c_red ) : c_red;
            }
            mvwprintz( window, point( amt_startpos, 6 + item_line ), print_color, "%4d", it_amt );
        }

        //print weight column
        double it_weight = convert_weight( sitem.weight );
        size_t w_precision;
        print_color = it_weight > 0 ? thiscolor : thiscolordark;

        if( it_weight >= 1000.0 ) {
            if( it_weight >= 10000.0 ) {
                print_color = selected ? hilite( c_red ) : c_red;
                it_weight = 9999.0;
            }
            w_precision = 0;
        } else if( it_weight >= 100.0 ) {
            w_precision = 1;
        } else {
            w_precision = 2;
        }
        mvwprintz( window, point( weight_startpos, 6 + item_line ), print_color, "%5.*f", w_precision,
                   it_weight );

        //print volume column
        bool it_vol_truncated = false;
        double it_vol_value = 0.0;
        std::string it_vol = format_volume( sitem.volume, 5, &it_vol_truncated, &it_vol_value );
        if( it_vol_truncated && it_vol_value > 0.0 ) {
            print_color = selected ? hilite( c_red ) : c_red;
        } else {
            print_color = sitem.volume.value() > 0 ? thiscolor : thiscolordark;
        }
        mvwprintz( window, point( vol_startpos, 6 + item_line ), print_color, it_vol );

        if( active && sitem.autopickup ) {
            mvwprintz( window, point( 1, 6 + item_line ), magenta_background( it.color_in_inventory() ),
                       compact ? it.tname().substr( 0, 1 ) : ">" );
        }

        if( pagination.step( i ) ) { // page end
            break;
        }
    }
}

struct advanced_inv_sorter {
    advanced_inv_sortby sortby;
    explicit advanced_inv_sorter( advanced_inv_sortby sort ) {
        sortby = sort;
    }
    bool operator()( const advanced_inv_listitem &d1, const advanced_inv_listitem &d2 ) const {
        // Note: the item pointer can only be null on sort by category, otherwise it is always valid.
        switch( sortby ) {
            case SORTBY_NONE:
                if( d1.idx != d2.idx ) {
                    return d1.idx < d2.idx;
                }
                break;
            case SORTBY_NAME:
                // Fall through to code below the switch
                break;
            case SORTBY_WEIGHT:
                if( d1.weight != d2.weight ) {
                    return d1.weight > d2.weight;
                }
                break;
            case SORTBY_VOLUME:
                if( d1.volume != d2.volume ) {
                    return d1.volume > d2.volume;
                }
                break;
            case SORTBY_DENSITY: {
                const double density1 = static_cast<double>( d1.weight.value() ) /
                                        static_cast<double>( std::max( 1, d1.volume.value() ) );
                const double density2 = static_cast<double>( d2.weight.value() ) /
                                        static_cast<double>( std::max( 1, d2.volume.value() ) );
                if( density1 != density2 ) {
                    return density1 > density2;
                }
                break;
            }
            case SORTBY_CHARGES:
                if( d1.items.front()->charges != d2.items.front()->charges ) {
                    return d1.items.front()->charges > d2.items.front()->charges;
                }
                break;
            case SORTBY_CATEGORY:
                if( d1.cat != d2.cat ) {
                    return d1.cat < d2.cat;
                }
                break;
            case SORTBY_DAMAGE: {
                const double dam1 = d1.items.front()->average_dps( get_player_character() );
                const double dam2 = d2.items.front()->average_dps( get_player_character() );
                if( dam1 != dam2 ) {
                    return dam1 > dam2;
                }
                break;
            }
            case SORTBY_AMMO: {
                const std::string a1 = d1.items.front()->ammo_sort_name();
                const std::string a2 = d2.items.front()->ammo_sort_name();
                // There are many items with "false" ammo types (e.g.
                // scrap metal has "components") that actually is not
                // used as ammo, so we consider them as non-ammo.
                const bool ammoish1 = !a1.empty() && a1 != "components" && a1 != "none" && a1 != "NULL";
                const bool ammoish2 = !a2.empty() && a2 != "components" && a2 != "none" && a2 != "NULL";
                if( ammoish1 != ammoish2 ) {
                    return ammoish1;
                } else if( ammoish1 && ammoish2 ) {
                    if( a1 == a2 ) {
                        // For items with the same ammo type, we sort:
                        // guns > tools > magazines > ammunition
                        if( d1.items.front()->is_gun() && !d2.items.front()->is_gun() ) {
                            return true;
                        }
                        if( !d1.items.front()->is_gun() && d2.items.front()->is_gun() ) {
                            return false;
                        }
                        if( d1.items.front()->is_tool() && !d2.items.front()->is_tool() ) {
                            return true;
                        }
                        if( !d1.items.front()->is_tool() && d2.items.front()->is_tool() ) {
                            return false;
                        }
                        if( d1.items.front()->is_magazine() && d2.items.front()->is_ammo() ) {
                            return true;
                        }
                        if( d2.items.front()->is_magazine() && d1.items.front()->is_ammo() ) {
                            return false;
                        }
                    }
                    return localized_compare( a1, a2 );
                }
            }
            break;
            case SORTBY_SPOILAGE:
                if( d1.items.front()->spoilage_sort_order() != d2.items.front()->spoilage_sort_order() ) {
                    return d1.items.front()->spoilage_sort_order() < d2.items.front()->spoilage_sort_order();
                }
                break;
            case SORTBY_PRICE:
                if( d1.items.front()->price( true ) != d2.items.front()->price( true ) ) {
                    return d1.items.front()->price( true ) > d2.items.front()->price( true );
                }
                break;
            case SORTBY_PRICEPERVOLUME: {
                const double price_density1 = static_cast<double>( d1.items.front()->price( true ) ) /
                                              static_cast<double>( std::max( 1, d1.items.front()->volume().value() ) );
                const double price_density2 = static_cast<double>( d2.items.front()->price( true ) ) /
                                              static_cast<double>( std::max( 1, d2.items.front()->volume().value() ) );
                if( price_density1 != price_density2 ) {
                    return price_density1 > price_density2;
                }
                break;
            }
            case SORTBY_PRICEPERWEIGHT: {
                const double price_density1 = static_cast<double>( d1.items.front()->price( true ) ) /
                                              static_cast<double>( std::max<std::int64_t>( 1, d1.items.front()->weight().value() ) );
                const double price_density2 = static_cast<double>( d2.items.front()->price( true ) ) /
                                              static_cast<double>( std::max<std::int64_t>( 1, d2.items.front()->weight().value() ) );
                if( price_density1 != price_density2 ) {
                    return price_density1 > price_density2;
                }
                break;
            }
            case SORTBY_STACKS:
                if( d1.stacks != d2.stacks ) {
                    return d1.stacks > d2.stacks;
                }
                break;
        }
        // secondary sort by name and link length
        auto const sort_key = []( advanced_inv_listitem const & d ) {
            return std::make_tuple( d.name_without_prefix, d.contents_count, d.name,
                                    d.items.front()->link_sort_key() );
        };
        return localized_compare( sort_key( d1 ), sort_key( d2 ) );
    }
};

int advanced_inventory::print_header( advanced_inventory_pane &pane, aim_location sel )
{
    const catacurses::window &window = pane.window;
    int area = pane.get_area();
    int wwidth = getmaxx( window );
    int ofs = wwidth - 44;
    int min_x = wwidth;
    for( int i = 0; i < NUM_AIM_LOCATIONS; ++i ) {
        int data_location = screen_relative_location( static_cast<aim_location>( i ) );
        bool can_put_items = squares[data_location].canputitems( pane.get_cur_item_ptr() != nullptr ?
                             pane.get_cur_item_ptr()->items.front() : item_location::nowhere );
        const char *bracket = pane.container_base_loc == data_location ||
                              data_location == AIM_CONTAINER ? "><" :
                              squares[data_location].can_store_in_vehicle() ||
                              data_location == AIM_PARENT ? "<>" : "[]";
        bool in_vehicle = pane.in_vehicle() && data_location == area && sel == area &&
                          area != AIM_ALL;
        bool all_brackets = area == AIM_ALL && ( data_location >= AIM_SOUTHWEST &&
                            data_location <= AIM_NORTHEAST );
        const aim_location location = static_cast<aim_location>( data_location );
        const bool adjacent_tile = location >= AIM_SOUTHWEST && location <= AIM_NORTHEAST;
        const bool blocked = location_is_fully_blocked( location );
        const bool dangerous = adjacent_tile && !blocked && location_is_dangerous( location );
        const bool has_items = adjacent_tile && !blocked && location_has_items( location );
        nc_color bcolor = c_red;
        nc_color kcolor = c_red;
        // Highlight location [#] if it can recieve items,
        // or highlight container [C] if container mode is active.
        if( can_put_items ) {
            bcolor = in_vehicle ? c_light_blue :
                     pane.container_base_loc == data_location ? c_brown :
                     data_location == AIM_CONTAINER ? c_dark_gray :
                     area == data_location || all_brackets ? c_light_gray : c_dark_gray;
            kcolor = data_location == AIM_CONTAINER ? c_dark_gray :
                     area == data_location ? c_white :
                     sel == data_location || pane.container_base_loc == data_location ? c_light_gray : c_dark_gray;
        } else if( data_location == AIM_PARENT && pane.container ) {
            bcolor = c_light_gray;
            kcolor = c_white;
        }
        const std::string key = get_location_key( static_cast<aim_location>( i ) );
        const point p( squares[i].hscreen + point( ofs, 0 ) );
        min_x = std::min( min_x, p.x );
        if( blocked ) {
            std::string block;
            for( int cell = 0; cell < utf8_width( key ) + 2; ++cell ) {
                block += "█";
            }
            mvwprintz( window, p, c_dark_gray, "%s", block );
            continue;
        }
        if( dangerous ) {
            // CDDA's terminal palette has no separate orange slot.  The yellow
            // warning foreground is its high-visibility orange equivalent.
            bcolor = c_brown;
            kcolor = area == data_location || sel == data_location ? h_yellow : c_yellow;
        } else if( has_items ) {
            bcolor = c_green;
            kcolor = area == data_location || sel == data_location ? h_green : c_light_green;
        }
        mvwprintz( window, p, bcolor, "%c", bracket[0] );
        wprintz( window, kcolor, "%s", in_vehicle && sel != AIM_DRAGGED ? "V" : key );
        wprintz( window, bcolor, "%c", bracket[1] );
    }

    return min_x;
}

void advanced_inventory::recalc_pane( side p )
{
    advanced_inventory_pane &pane = panes[p];
    pane.recalc = false;
    pane.items.clear();
    advanced_inventory_pane &there = panes[-p + 1];
    advanced_inv_area &other = squares[there.get_area()];
    avatar &player_character = get_avatar();
    if( pane.container &&
        pane.container_base_loc >= AIM_SOUTHWEST && pane.container_base_loc <= AIM_ALL ) {

        const tripoint_rel_ms offset = player_character.pos_abs() - pane.container.pos_abs();

        // If container is no longer adjacent or on the player's z-level, nullify it.
        if( std::abs( offset.x() ) > 1 || std::abs( offset.y() ) > 1 ||
            player_character.posz() != pane.container.pos_abs().z() ) {

            pane.container = item_location::nowhere;
            pane.container_base_loc = NUM_AIM_LOCATIONS;
        } else if( pane.container_base_loc <= AIM_NORTHEAST ) {
            pane.container_base_loc = static_cast<aim_location>( ( offset.y() + 1 ) * 3 - offset.x() + 2 );
        }
    }
    // Add items from the source location or in case of all 9 surrounding squares,
    // add items from several locations.
    if( pane.get_area() == AIM_ALL ) {
        advanced_inv_area &alls = squares[AIM_ALL];
        alls.volume = 0_ml;
        alls.weight = 0_gram;
        for( advanced_inv_area &s : squares ) {
            // All the surrounding squares, nothing else
            if( s.id < AIM_SOUTHWEST || s.id > AIM_NORTHEAST ) {
                continue;
            }

            // To allow the user to transfer all items from all surrounding squares to
            // a specific square, filter out items that are already on that square.
            // e.g. left pane AIM_ALL, right pane AIM_NORTH. The user holds the
            // enter key down in the left square and moves all items to the other side.
            const bool same = other.is_same( s );

            // Deal with squares with ground + vehicle storage
            // Also handle the case when the other tile covers vehicle
            // or the ground below the vehicle.
            if( s.can_store_in_vehicle() && !( same && there.in_vehicle() ) ) {
                bool do_vehicle = there.get_area() == s.id ? !there.in_vehicle() : true;
                pane.add_items_from_area( s, do_vehicle );
                alls.volume += s.volume_veh;
                alls.weight += s.weight_veh;
            }

            // Add map items
            if( !same || there.in_vehicle() ) {
                pane.add_items_from_area( s );
                alls.volume += s.volume;
                alls.weight += s.weight;
            }
        }
    } else {
        pane.add_items_from_area( squares[pane.get_area()] );
    }

    // Sort all items
    std::stable_sort( pane.items.begin(), pane.items.end(), advanced_inv_sorter( pane.sortby ) );

    // Attempt to move to the target item if there is one.
    if( pane.target_item_after_recalc ) {
        for( size_t i = 0; i < pane.items.size(); i++ ) {
            if( pane.items[i].items.front() == pane.target_item_after_recalc ) {
                pane.index = i;
                pane.target_item_after_recalc = item_location::nowhere;
                break;
            }
        }
    }
}

void advanced_inventory::redraw_pane( side p )
{
    input_context ctxt( "ADVANCED_INVENTORY" );

    advanced_inventory_pane &pane = panes[p];
    if( recalc || pane.recalc ) {
        recalc_pane( p );
    }
    pane.fix_index();

    const bool active = p == src;
    const advanced_inv_area &square = squares[pane.get_area()];
    catacurses::window w = pane.window;

    werase( w );
    print_items( p, active );

    advanced_inv_listitem *itm = pane.get_cur_item_ptr();
    int width = print_header( pane, itm != nullptr ? itm->area : pane.get_area() );
    // only cardinals
    // not where you stand, and pane is in vehicle
    // make sure the offsets are the same as the grab point
    bool same_as_dragged = ( square.id >= AIM_SOUTHWEST && square.id <= AIM_NORTHEAST ) &&
                           square.id != AIM_CENTER && panes[p].in_vehicle() &&
                           square.off == squares[AIM_DRAGGED].off;
    const advanced_inv_area &sq = same_as_dragged ? squares[AIM_DRAGGED] : square;
    bool car = square.can_store_in_vehicle() && panes[p].in_vehicle() && sq.id != AIM_DRAGGED;
    std::string name = utf8_truncate( car ? sq.veh->name : sq.name, width );
    std::string desc = pane.container ? pane.container->tname( 1, false ) : sq.desc[car];
    // starts at offset 2, plus space between the header and the text
    width -= 2 + 1;
    trim_and_print( w, point( 2, 1 ), width, active ? c_green  : c_light_gray, name );
    trim_and_print( w, point( 2, 2 ), width, active ? c_light_blue : c_dark_gray, desc );
    if( active ) {
        mvwprintz( w, point( 2, 3 ), c_light_green, _( "< Reload >" ) );
        if( getmaxx( w ) >= 48 ) {
            mvwprintz( w, point( 13, 3 ), c_light_blue, _( "< Ammo sort >" ) );
        }
        if( pane.container && getmaxx( w ) >= 58 ) {
            mvwprintz( w, point( 27, 3 ), c_yellow, _( "< Back >" ) );
        }
    } else {
        trim_and_print( w, point( 2, 3 ), width, c_dark_gray, square.flags );
    }

    if( active ) {
        advanced_inventory_pagination pagination( linesPerPage, pane );
        int cur_page = 0;
        for( int i = 0; i < static_cast<int>( pane.items.size() ); i++ ) {
            pagination.step( i );
            if( i == pane.index ) {
                cur_page = pagination.page;
            }
        }
        const int max_page = pagination.page;
        mvwprintz( w, point( 2, 4 ), c_light_blue, _( "[<] page %1$d of %2$d [>]" ), cur_page + 1,
                   max_page + 1 );
    }

    if( active ) {
        wattron( w, c_cyan );
    }
    // draw a darker border around the inactive pane
    draw_border( w, active ? BORDER_COLOR : c_dark_gray );
    mvwprintw( w, point( 3, 0 ), _( "< [%s] Sort: %s >" ), ctxt.get_desc( "SORT" ),
               get_sortname( pane.sortby ) );
    int max = square.max_size;
    if( max > 0 ) {
        int itemcount = square.get_item_count();
        int fmtw = 7 + ( itemcount > 99 ? 3 : itemcount > 9 ? 2 : 1 ) +
                   ( max > 99 ? 3 : max > 9 ? 2 : 1 );
        mvwprintw( w, point( w_width / 2 - fmtw, 0 ), "< %d/%d >", itemcount, max );
    }

    std::string fprefix = string_format( _( "[%s] Filter" ), ctxt.get_desc( "FILTER" ) );
    const std::string &filter = pane.get_filter();
    if( !filter_edit ) {
        if( !filter.empty() ) {
            mvwprintw( w, point( 2, getmaxy( w ) - 1 ), "< %s: %s >", fprefix, filter );
        } else {
            mvwprintw( w, point( 2, getmaxy( w ) - 1 ), "< %s >", fprefix );
        }
    }
    if( active ) {
        wattroff( w, c_white );
    }
    if( !filter_edit && !filter.empty() ) {
        std::string fsuffix = string_format( _( "[%s] Reset" ), ctxt.get_desc( "RESET_FILTER" ) );
        mvwprintz( w, point( 6 + utf8_width( fprefix ), getmaxy( w ) - 1 ), c_white, filter );
        mvwprintz( w, point( getmaxx( w ) - utf8_width( fsuffix ) - 2, getmaxy( w ) - 1 ), c_white, "%s",
                   fsuffix );
    }
}

bool advanced_inventory::fill_lists_with_pane_items( Character &player_character,
        advanced_inv_sortby sort_priority,
        advanced_inventory_pane &spane, advanced_inventory_pane &dpane,
        std::vector<drop_or_stash_item_info> &item_list,
        std::vector<drop_or_stash_item_info> &fav_list, bool forbid_buckets )
{
    std::vector<move_all_entry> unsorted_item_list;
    std::vector<move_all_entry> unsorted_fav_list;
    item_location wielded = player_character.get_wielded_item();
    bool try_unwield = false;
    item_location stashed_bucket;
    for( const advanced_inv_listitem &listit : spane.items ) {
        if( listit.items.front() == dpane.container ) {
            continue;
        }
        for( const item_location &it : listit.items ) {

            // do not move liquids or gases
            if( ( it->made_of_from_type( phase_id::LIQUID ) && !it->is_frozen_liquid() ) ||
                it->made_of_from_type( phase_id::GAS ) ) {
                continue;
            }
            if( dpane.get_area() == AIM_INVENTORY ) {

                if( !player_character.can_stash_partial( *it ) ) {
                    continue;
                }
            } else if( dpane.container &&
                       !dpane.container->can_contain_directly( *it ).success() ) {
                continue;
            }
            if( it->is_corpse() && !it->empty_container() ) {
                // Only allow moving corpses if they're empty.
                continue;
            }
            if( forbid_buckets && it->is_bucket_nonempty() ) {
                // Don't allow putting nonempty buckets into pockets.
                stashed_bucket = it;
                continue;
            } else if( it == wielded ) {
                // Only allow moving wielded item if it's the only valid item left.
                try_unwield = true;
                continue;
            }

            if( sort_priority == advanced_inv_sortby::SORTBY_NONE ) {
                if( it->is_favorite ) {
                    fav_list.emplace_back( it, it->count() );
                } else {
                    item_list.emplace_back( it, it->count() );
                }
            } else {
                int weight_int = it->weight().value() > INT_MAX ? INT_MAX :
                                 static_cast<int>( it->weight().value() );

                std::pair<int, int> sort_values = sort_priority == advanced_inv_sortby::SORTBY_VOLUME ?
                                                  std::make_pair( it->volume().value(), weight_int ) :
                                                  std::make_pair( weight_int, it->volume().value() );
                if( it->is_favorite ) {
                    unsorted_fav_list.emplace_back( sort_values, drop_or_stash_item_info( it, it->count() ) );
                } else {
                    unsorted_item_list.emplace_back( sort_values, drop_or_stash_item_info( it, it->count() ) );
                }
            }
        }
    }

    if( item_list.empty() && fav_list.empty() &&
        unsorted_item_list.empty() && unsorted_fav_list.empty() ) {

        if( stashed_bucket ) {
            if( !query_yn( _( "The %s would spill if stored there.  Store its contents first?" ),
                           stashed_bucket->tname() ) ) {
                return false;
            }
            for( item *it : stashed_bucket->get_contents().all_items_top() ) {
                item_list.emplace_back( item_location( stashed_bucket, it ), it->count() );
            }
            if( stashed_bucket->is_favorite ) {
                fav_list.emplace_back( stashed_bucket, stashed_bucket->count() );
            } else {
                item_list.emplace_back( stashed_bucket, stashed_bucket->count() );
            }
            return true;

        } else if( try_unwield ) {
            if( !query_yn( _( "Unwield the %s?" ), wielded->tname() ) ) {
                return false;
            }
            if( wielded->is_favorite ) {
                fav_list.emplace_back( wielded, wielded->count() );
            } else {
                item_list.emplace_back( wielded, wielded->count() );
            }
            return true;
        }
        set_workspace_status( _( "None of the items can be moved to that destination." ) );
        return false;
    }

    if( sort_priority == advanced_inv_sortby::SORTBY_NONE ) {
        return true;
    }

    auto sort = [&dpane]( const move_all_entry & lhs, const move_all_entry & rhs ) {
        // pickup_activity_actor processes from the back, so reverse the order if moving to inventory.
        if( lhs.first.first == rhs.first.first ) {
            return dpane.get_area() == AIM_INVENTORY ?
                   lhs.first.second > rhs.first.second : lhs.first.second < rhs.first.second;
        }
        return dpane.get_area() == AIM_INVENTORY ?
               lhs.first.first > rhs.first.first : lhs.first.first < rhs.first.first;
    };
    std::sort( std::begin( unsorted_item_list ), std::end( unsorted_item_list ), sort );
    std::sort( std::begin( unsorted_fav_list ), std::end( unsorted_fav_list ), sort );

    for( const move_all_entry &entry : unsorted_item_list ) {
        item_list.push_back( entry.second );
    }
    for( const move_all_entry &entry : unsorted_fav_list ) {
        fav_list.push_back( entry.second );
    }
    return true;
}

bool advanced_inventory::move_all_items()
{
    advanced_inventory_pane &spane = panes[src];
    advanced_inventory_pane &dpane = panes[dest];

    Character &player_character = get_player_character();
    const auto is_world_area = []( const aim_location area ) {
        return ( area >= AIM_SOUTHWEST && area <= AIM_NORTHEAST ) || area == AIM_DRAGGED ||
               area == AIM_ALL;
    };
    const bool world_transfer = is_world_area( spane.get_area() ) ||
                                is_world_area( dpane.get_area() ) ||
                                ( spane.container && !spane.container.held_by( player_character ) ) ||
                                ( dpane.container && !dpane.container.held_by( player_character ) );
    if( world_transfer && ( player_character.has_active_mutation( trait_SHELL2 ) ||
                            player_character.has_active_mutation( trait_SHELL3 ) ) ) {
        set_workspace_status( _( "You cannot move items to or from the world while inside your shell." ) );
        return false;
    }
    if( world_transfer && player_character.is_mounted() ) {
        set_workspace_status( _( "You cannot move items to or from the world while mounted." ) );
        return false;
    }
    if( world_transfer && player_character.has_effect( effect_incorporeal ) ) {
        set_workspace_status( _( "You lack the substance to move items to or from the world." ) );
        return false;
    }

    // Check some preconditions to quickly leave the function.
    if( spane.get_area() == AIM_CONTAINER && dpane.get_area() == AIM_INVENTORY ) {
        if( spane.container.held_by( player_character ) ) {
            // TODO: Implement this, distributing the contents to other inventory pockets.
            set_workspace_status( _( "Everything in that carried container is already in your inventory." ) );
            return false;
        }
    }
    if( spane.get_area() == AIM_CONTAINER &&
        spane.container.get_item() == nullptr ) {
        set_workspace_status( _( "The source container is no longer valid." ) );
        return false;
    }
    if( spane.get_area() == AIM_CONTAINER &&
        spane.container.get_item()->has_flag( json_flag_NO_UNLOAD ) ) {
        set_workspace_status( _( "The source container cannot be unloaded." ) );
        return false;
    }
    if( dpane.get_area() == AIM_CONTAINER &&
        dpane.container.get_item()->has_flag( json_flag_NO_RELOAD ) ) {
        set_workspace_status( _( "The destination container cannot accept inserted items." ) );
        return false;
    }
    size_t liquid_items = 0;
    for( const advanced_inv_listitem &elem : spane.items ) {
        for( const item_location &elemit : elem.items ) {
            if( ( elemit->made_of_from_type( phase_id::LIQUID ) && !elemit->is_frozen_liquid() ) ||
                elemit->made_of_from_type( phase_id::GAS ) ) {
                liquid_items++;
            }
        }
    }

    if( spane.items.empty() || liquid_items == spane.items.size() ) {
        if( !is_processing() ) {
            set_workspace_status( _( "No eligible items can be moved from this source." ) );
        } else if( spane.get_area() != AIM_ALL ) {
            // ensure we don't get stuck if the recursive calls in the switch above were interrupted
            // by a save-load cycle before the shadowed pane was restored
            spane.set_area( AIM_ALL );
        }
        return false;
    }
    std::unique_ptr<on_out_of_scope> restore_area;
    if( dpane.get_area() == AIM_ALL ) {
        aim_location loc = dpane.get_area();
        // ask where we want to store the item via the menu
        if( !query_destination( loc ) ) {
            return false;
        }
        restore_area = std::make_unique<on_out_of_scope>( [&]() {
            dpane.restore_area();
        } );
    }
    if( !squares[dpane.get_area()].canputitems( dpane.container ) ) {
        set_workspace_status( _( "That destination cannot accept items." ) );
        return false;
    }
    advanced_inv_area &sarea = squares[spane.get_area()];
    advanced_inv_area &darea = squares[dpane.get_area()];

    // Make sure source and destination are different, otherwise items will disappear
    // Need to check actual position to account for dragged vehicles
    if( dpane.get_area() == AIM_DRAGGED && sarea.pos == darea.pos &&
        spane.in_vehicle() == dpane.in_vehicle() ) {
        return false;
    }

    if( spane.get_area() == dpane.get_area() && spane.in_vehicle() == dpane.in_vehicle() &&
        spane.container == dpane.container ) {
        return false;
    }

    if( spane.get_area() == AIM_INVENTORY || spane.get_area() == AIM_WORN ) {
        if( dpane.get_area() == AIM_INVENTORY ) {
            set_workspace_status( _( "Inventory items need a specific destination container, not Inventory itself." ) );
            return false;
        } else if( dpane.get_area() == AIM_WORN ) {
            // TODO: implement move_all to worn from inventory.
            set_workspace_status(
                _( "Wear items one by one so every equipment rule and move cost is applied correctly." ) );
            return false;
        }
    }

    if( dpane.get_area() == AIM_WORN ) {
        // TODO: implement move_all to worn from everywhere other than inventory.
        set_workspace_status(
            _( "Wear items one by one so every equipment rule and move cost is applied correctly." ) );
        return false;
    }

    // Check first if the destination area still has enough room for moving all.
    advanced_inv_sortby sort_priority = advanced_inv_sortby::SORTBY_NONE;
    std::string limitation;
    if( !is_processing() ) {
        units::volume over_volume = 0_ml;
        units::mass over_weight = 0_gram;

        const units::volume &src_volume = spane.in_vehicle() ? sarea.volume_veh : sarea.volume;
        const units::volume dest_volume_free = dpane.free_volume( darea );
        over_volume = src_volume - dest_volume_free;

        if( dpane.get_area() == AIM_INVENTORY || dpane.get_area() == AIM_CONTAINER ) {
            const units::mass &src_weight = spane.in_vehicle() ? sarea.weight_veh : sarea.weight;
            const units::mass dest_weight_free = dpane.free_weight_capacity();
            over_weight = src_weight - dest_weight_free;
        }

        if( over_volume > 0_ml && over_weight > 0_gram ) {
            limitation = _( "room or weight capacity" );
            // Prioritize whichever one is closest to the limit
            sort_priority = units::to_milliliter<int>( over_volume ) < units::to_gram<int>( over_weight ) ?
                            SORTBY_VOLUME : SORTBY_WEIGHT;
        } else if( over_volume > 0_ml ) {
            limitation = pgettext( "As in \"not enough room in the backpack\"", "room" );
            sort_priority = SORTBY_VOLUME;
        } else if( over_weight > 0_gram ) {
            limitation = _( "weight capacity" );
            sort_priority = SORTBY_WEIGHT;
        }
    }

    std::vector<drop_or_stash_item_info> pane_items;
    // Keep a list of favorites separated, only drop non-fav first if they exist.
    std::vector<drop_or_stash_item_info> pane_favs;
    bool forbid_buckets = dpane.get_area() == AIM_INVENTORY || dpane.get_area() == AIM_WORN ||
                          dpane.get_area() == AIM_CONTAINER || dpane.in_vehicle();

    if( !fill_lists_with_pane_items( player_character, sort_priority, spane, dpane,
                                     pane_items, pane_favs, forbid_buckets ) ) {
        return false;
    }

    // Move all the favorite items only if there are no other items
    if( pane_items.empty() ) {
        // Check if the list is still empty for when all that's in the aim_worn list is a wielded weapon.
        if( pane_favs.empty() ) {
            set_workspace_status( _( "None of the items can be moved to that destination." ) );
            return false;
        }
        // Ask to move favorites if the player is holding them
        if( spane.get_area() == AIM_INVENTORY || spane.get_area() == AIM_WORN ) {
            if( !query_yn( _( "Really drop all your favorite items?" ) ) ) {
                return false;
            }
        }
        pane_items = pane_favs;
    }

    if( !limitation.empty() &&
        !query_yn( _( "There isn't enough %s.  Attempt to move as much as you can?" ),
                   limitation ) ) {
        return false;
    }

    if( dpane.get_area() == AIM_CONTAINER ) {
        if( dpane.container ) {
            drop_locations items_to_insert;

            for( const drop_or_stash_item_info &drop : pane_items ) {
                items_to_insert.emplace_back( drop.loc(), drop.count() );
            }
            do_return_entry();

            const insert_item_activity_actor act( dpane.container, items_to_insert );
            player_character.assign_activity( act );
        }
    } else if( spane.get_area() == AIM_INVENTORY || spane.get_area() == AIM_WORN ) {
        const tripoint_rel_ms placement = darea.off;
        // in case there is vehicle cargo space at dest but the player wants to drop to ground
        const bool force_ground = !dpane.in_vehicle();

        do_return_entry();

        const drop_activity_actor act( pane_items, placement, force_ground );
        player_character.assign_activity( act );
    } else if( dpane.get_area() == AIM_INVENTORY ) {
        std::vector<item_location> target_items;
        std::vector<int> quantities;
        target_items.reserve( pane_items.size() );
        quantities.reserve( pane_items.size() );
        for( const drop_or_stash_item_info &drop : pane_items ) {
            target_items.emplace_back( drop.loc() );
            // quantity of 0 means move all
            quantities.emplace_back( 0 );
        }

        do_return_entry();

        const pickup_activity_actor act( target_items, quantities, player_character.pos_bub(), false );
        player_character.assign_activity( act );
    } else {
        // Vehicle and map destinations are handled the same.

        // Stash the destination
        const tripoint_rel_ms relative_destination = darea.off;

        std::vector<item_location> target_items;
        std::vector<int> quantities;
        target_items.reserve( pane_items.size() );
        quantities.reserve( pane_items.size() );
        for( const drop_or_stash_item_info &drop : pane_items ) {
            target_items.emplace_back( drop.loc() );
            // quantity of 0 means move all
            quantities.emplace_back( 0 );
        }

        do_return_entry();

        const move_items_activity_actor act( target_items, quantities, dpane.in_vehicle(),
                                             relative_destination );
        player_character.assign_activity( act );
    }

    return true;
}

void advanced_inventory::cycle_sort_mode( advanced_inventory_pane &pane )
{
    const int next = ( static_cast<int>( pane.sortby ) + 1 ) %
                     ( static_cast<int>( SORTBY_STACKS ) + 1 );
    pane.sortby = static_cast<advanced_inv_sortby>( next );
    set_workspace_status( string_format( _( "Sorted by %s. Click Sort again for the next mode." ),
                                         get_sortname( pane.sortby ) ) );
}

input_context advanced_inventory::register_ctxt() const
{
    input_context ctxt( "ADVANCED_INVENTORY" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "UP" );
    ctxt.register_action( "DOWN" );
    ctxt.register_action( "LEFT" );
    ctxt.register_action( "RIGHT" );
    ctxt.register_action( "PAGE_DOWN" );
    ctxt.register_action( "PAGE_UP" );
    ctxt.register_action( "HOME" );
    ctxt.register_action( "END" );
    ctxt.register_action( "TOGGLE_TAB" );
    ctxt.register_action( "TOGGLE_VEH" );
    ctxt.register_action( "FILTER" );
    ctxt.register_action( "RESET_FILTER" );
    ctxt.register_action( "EXAMINE" );
    ctxt.register_action( "EXAMINE_CONTENTS" );
    ctxt.register_action( "UNLOAD_CONTAINER" );
    // Reuse the existing global reload binding so this workspace does not
    // require a modified core keybindings file.  The inline mouse buttons
    // continue to dispatch the workspace-specific action names directly.
    ctxt.register_action( "reload_item", to_translation( "Reload selected gun or magazine" ) );
    ctxt.register_action( "SORT_AMMO", to_translation( "Sort ammunition, magazines, and guns" ) );
    ctxt.register_action( "SORT" );
    ctxt.register_action( "TOGGLE_AUTO_PICKUP" );
    ctxt.register_action( "TOGGLE_FAVORITE" );
    ctxt.register_action( "MOVE_SINGLE_ITEM" );
    ctxt.register_action( "MOVE_VARIABLE_ITEM" );
    ctxt.register_action( "MOVE_ITEM_STACK" );
    ctxt.register_action( "MOVE_ALL_ITEMS" );
    ctxt.register_action( "CATEGORY_SELECTION" );
    ctxt.register_action( "ITEMS_NW" );
    ctxt.register_action( "ITEMS_N" );
    ctxt.register_action( "ITEMS_NE" );
    ctxt.register_action( "ITEMS_W" );
    ctxt.register_action( "ITEMS_CE" );
    ctxt.register_action( "ITEMS_E" );
    ctxt.register_action( "ITEMS_SW" );
    ctxt.register_action( "ITEMS_S" );
    ctxt.register_action( "ITEMS_SE" );
    ctxt.register_action( "ITEMS_INVENTORY" );
    ctxt.register_action( "ITEMS_WORN" );
    ctxt.register_action( "ITEMS_AROUND" );
    ctxt.register_action( "ITEMS_DRAGGED_CONTAINER" );
    ctxt.register_action( "ITEMS_CONTAINER" );
    ctxt.register_action( "ITEMS_PARENT" );

    // These actions have global mouse bindings.  Registering them here keeps
    // keyboard behavior unchanged while making the native AIM fully operable
    // in SDL/Tiles builds.
    ctxt.register_action( "COORDINATE" );
    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "CLICK_AND_DRAG" );
    ctxt.register_action( "SELECT" );
    ctxt.register_action( "SEC_SELECT" );
    ctxt.register_action( "SCROLL_UP" );
    ctxt.register_action( "SCROLL_DOWN" );

    ctxt.register_action( "ITEMS_DEFAULT" );
    ctxt.register_action( "SAVE_DEFAULT" );

    return ctxt;
}

int advanced_inventory::item_index_at_row( const advanced_inventory_pane &pane, int row ) const
{
    constexpr int first_item_row = 6;
    if( row < first_item_row || row >= first_item_row + linesPerPage || pane.items.empty() ) {
        return -1;
    }

    advanced_inventory_pagination current_page( linesPerPage, pane );
    int selected_page = 0;
    for( int i = 0; i <= pane.index && i < static_cast<int>( pane.items.size() ); ++i ) {
        current_page.step( i );
        if( i == pane.index ) {
            selected_page = current_page.page;
        }
    }

    advanced_inventory_pagination pagination( linesPerPage, pane );
    for( int i = 0; i < static_cast<int>( pane.items.size() ); ++i ) {
        pagination.step( i );
        const int item_row = first_item_row + pagination.line - 1;
        if( pagination.page == selected_page && item_row == row ) {
            return i;
        }
        if( pagination.page > selected_page ) {
            break;
        }
    }
    return -1;
}

int advanced_inventory::item_row_for_index( const advanced_inventory_pane &pane, const int index ) const
{
    if( index < 0 || index >= static_cast<int>( pane.items.size() ) ) {
        return -1;
    }

    advanced_inventory_pagination selected_pagination( linesPerPage, pane );
    int selected_page = 0;
    for( int i = 0; i <= pane.index && i < static_cast<int>( pane.items.size() ); ++i ) {
        selected_pagination.step( i );
        if( i == pane.index ) {
            selected_page = selected_pagination.page;
        }
    }

    advanced_inventory_pagination pagination( linesPerPage, pane );
    for( int i = 0; i <= index; ++i ) {
        pagination.step( i );
    }
    return pagination.page == selected_page ? 5 + pagination.line : -1;
}

bool advanced_inventory::handle_location_click( side pane_side, const point &p )
{
    advanced_inventory_pane &pane = panes[pane_side];
    const int pane_width = getmaxx( pane.window );
    const int offset = pane_width - 44;

    for( int i = 0; i < NUM_AIM_LOCATIONS; ++i ) {
        const point button = squares[i].hscreen + point( offset, 0 );
        const int button_width = utf8_width( get_location_key( static_cast<aim_location>( i ) ) ) + 2;
        if( p.y == button.y && p.x >= button.x && p.x < button.x + button_width ) {
            src = pane_side;
            dest = src == left ? right : left;
            const aim_location location = screen_relative_location( static_cast<aim_location>( i ) );
            if( location_is_fully_blocked( location ) ) {
                set_workspace_status( _( "That tile is fully blocked and has no accessible items or storage." ) );
                log_workspace_event( string_format( "blocked location click pane=%s location=%d",
                                                    pane_side == left ? "left" : "right",
                                                    static_cast<int>( location ) ) );
                return true;
            }
            log_workspace_event( string_format( "location click pane=%s location=%d vehicle=%d",
                                                pane_side == left ? "left" : "right",
                                                static_cast<int>( location ),
                                                static_cast<int>( pane.in_vehicle() ) ) );
            process_action( squares[location].actionname );
            return true;
        }
    }
    return false;
}

bool advanced_inventory::handle_mouse( const input_context &ctxt, const std::string &action )
{
    const bool mouse_action = action == "COORDINATE" || action == "MOUSE_MOVE" ||
                              action == "CLICK_AND_DRAG" || action == "SELECT" ||
                              action == "SEC_SELECT" || action == "SCROLL_UP" ||
                              action == "SCROLL_DOWN";
    if( !mouse_action ) {
        mouse_drag_item = item_location::nowhere;
        mouse_drag_side.reset();
        mouse_pressed_item = item_location::nowhere;
        mouse_pressed_side.reset();
        mouse_hover_side.reset();
        if( context_actions_open ) {
            close_context_menu();
            // Escape closes the dropdown before it closes the whole workspace.
            if( action == "QUIT" ) {
                return true;
            }
        }
        return false;
    }

    // The 3x3 map is a direct selector for adjacent storage.  In isometric
    // tilesets screen_relative_location() rotates it back into map space.
    if( action == "SELECT" ) {
        const std::optional<point> minimap_point = ctxt.get_coordinates_text( minimap );
        if( minimap_point && window_contains_point_relative( minimap, *minimap_point ) ) {
            const int screen_location = ( 2 - minimap_point->y ) * 3 + minimap_point->x + AIM_SOUTHWEST;
            const aim_location location = screen_relative_location(
                                              static_cast<aim_location>( screen_location ) );
            if( location_is_fully_blocked( location ) ) {
                set_workspace_status(
                    _( "That tile is fully blocked and has no accessible items or storage." ) );
                log_workspace_event( string_format( "blocked minimap click location=%d",
                                                    static_cast<int>( location ) ) );
                mouse_drag_item = item_location::nowhere;
                mouse_drag_side.reset();
                mouse_pressed_item = item_location::nowhere;
                mouse_pressed_side.reset();
                return true;
            }
            process_action( squares[location].actionname );
            mouse_drag_item = item_location::nowhere;
            mouse_drag_side.reset();
            mouse_pressed_item = item_location::nowhere;
            mouse_pressed_side.reset();
            return true;
        }
    }

    std::optional<side> hovered_side;
    point pane_point = point::zero;
    for( side candidate : { left, right } ) {
        const std::optional<point> candidate_point = ctxt.get_coordinates_text( panes[candidate].window );
        if( candidate_point && window_contains_point_relative( panes[candidate].window,
                *candidate_point ) ) {
            hovered_side = candidate;
            pane_point = *candidate_point;
            break;
        }
    }

    if( !hovered_side ) {
        mouse_hover_side.reset();
        if( action == "SELECT" || action == "SEC_SELECT" ) {
            mouse_drag_item = item_location::nowhere;
            mouse_drag_side.reset();
            mouse_pressed_item = item_location::nowhere;
            mouse_pressed_side.reset();
        }
        return action != "MOUSE_MOVE" && action != "COORDINATE";
    }

    const side hovered = *hovered_side;
    advanced_inventory_pane &pane = panes[hovered];
    const int item_index = item_index_at_row( pane, pane_point.y );
    mouse_hover_side = hovered;
    mouse_hover_point = pane_point;

    if( context_actions_open && context_menu_side ) {
        const bool same_pane = hovered == *context_menu_side;
        const bool inside_menu = same_pane &&
                                 pane_point.x >= context_menu_pos.x &&
                                 pane_point.x < context_menu_pos.x + context_menu_width &&
                                 pane_point.y >= context_menu_pos.y &&
                                 pane_point.y < context_menu_pos.y + context_menu_height;
        if( inside_menu ) {
            if( action == "SELECT" ) {
                if( handle_action_click( pane_point ) ) {
                    mouse_pressed_item = item_location::nowhere;
                    mouse_pressed_side.reset();
                }
                return true;
            }
            if( action == "CLICK_AND_DRAG" || action == "SEC_SELECT" ) {
                return true;
            }
        } else if( action == "CLICK_AND_DRAG" || action == "SELECT" || action == "SEC_SELECT" ) {
            close_context_menu();
        }
    }

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        src = hovered;
        dest = src == left ? right : left;
        process_action( action == "SCROLL_UP" ? "UP" : "DOWN" );
        return true;
    }

    if( action == "CLICK_AND_DRAG" ) {
        if( item_index >= 0 ) {
            src = hovered;
            dest = src == left ? right : left;
            pane.index = item_index;
            mouse_pressed_item = pane.items[item_index].items.front();
            mouse_pressed_side = hovered;
            mouse_pressed_index = item_index;
            mouse_pressed_point = pane_point;
            mouse_drag_item = item_location::nowhere;
            mouse_drag_side.reset();
            close_context_menu();
            log_workspace_event( string_format( "mouse press item=%s pane=%s index=%d",
                                                mouse_pressed_item->typeId().str(),
                                                hovered == left ? "left" : "right", item_index ) );
        } else {
            mouse_pressed_item = item_location::nowhere;
            mouse_pressed_side.reset();
        }
        return true;
    }

    if( action == "MOUSE_MOVE" && mouse_pressed_side && !mouse_drag_side &&
        ( hovered != *mouse_pressed_side || pane_point != mouse_pressed_point ) ) {
        mouse_drag_item = mouse_pressed_item;
        mouse_drag_side = mouse_pressed_side;
        mouse_drag_index = mouse_pressed_index;
        mouse_pressed_item = item_location::nowhere;
        mouse_pressed_side.reset();
        if( mouse_drag_item ) {
            const advanced_inventory_pane &source_pane = panes[*mouse_drag_side];
            set_workspace_status( string_format( _( "Moving %s — release it over the other pane." ),
                                                 mouse_drag_item->tname() ) );
            log_workspace_event( string_format( "drag begin item=%s source=%s area=%d",
                                                mouse_drag_item->typeId().str(),
                                                *mouse_drag_side == left ? "left" : "right",
                                                static_cast<int>( source_pane.get_area() ) ) );
        }
    }

    if( action == "MOUSE_MOVE" || action == "COORDINATE" ) {
        return true;
    }

    if( action == "SELECT" && mouse_pressed_side && !mouse_drag_side ) {
        const side pressed_side = *mouse_pressed_side;
        const item_location pressed_item = mouse_pressed_item;
        mouse_pressed_item = item_location::nowhere;
        mouse_pressed_side.reset();
        const bool same_item = hovered == pressed_side && item_index >= 0 && pressed_item &&
                               pane.items[item_index].items.front() == pressed_item;
        if( !same_item ) {
            log_workspace_event( "mouse click canceled after release away from its item" );
            return true;
        }
        // Continue into the regular SELECT path.  A press/release without
        // held movement selects (or opens the container chevron) and never
        // starts a transfer.
    }

    // Releasing a dragged item over the other pane transfers it through the
    // existing variable-move path.  That path supplies the numeric stack input
    // and schedules the normal pickup/drop activity, preserving all move costs.
    if( action == "SELECT" && mouse_drag_side ) {
        const side dragged_from = *mouse_drag_side;
        const item_location dragged_item = mouse_drag_item;
        mouse_drag_item = item_location::nowhere;
        mouse_drag_side.reset();
        mouse_pressed_item = item_location::nowhere;
        mouse_pressed_side.reset();

        if( hovered != dragged_from && dragged_item ) {
            // Dropping directly on a container enters that container first, so
            // bags, holsters, magazines, and nested storage are natural targets.
            if( item_index >= 0 && pane.get_area() != AIM_WORN ) {
                pane.index = item_index;
                const item_location &drop_target = pane.items[item_index].items.front();
                if( squares[AIM_CONTAINER].canputitems( drop_target ) ) {
                    src = hovered;
                    dest = src == left ? right : left;
                    process_action( "ITEMS_CONTAINER" );
                }
            }

            src = dragged_from;
            dest = src == left ? right : left;
            set_workspace_status( string_format( _( "Moving %1$s to %2$s…" ), dragged_item->tname(),
                                                 squares[panes[dest].get_area()].name ) );
            log_workspace_event( string_format( "drag release item=%s destination=%d",
                                                dragged_item->typeId().str(),
                                                static_cast<int>( panes[dest].get_area() ) ) );
            panes[src].index = mouse_drag_index;
            if( panes[src].get_cur_item_ptr() != nullptr &&
                panes[src].get_cur_item_ptr()->items.front() == dragged_item ) {
                process_action( "MOVE_VARIABLE_ITEM" );
            } else {
                // A destination-container recalculation may have shifted the
                // source index; locate the original item again before moving.
                for( int i = 0; i < static_cast<int>( panes[src].items.size() ); ++i ) {
                    if( panes[src].items[i].items.front() == dragged_item ) {
                        panes[src].index = i;
                        process_action( "MOVE_VARIABLE_ITEM" );
                        break;
                    }
                }
            }
            return true;
        }

        // A regular click selects.  Clicking the chevron at the left of a
        // container opens it without requiring the keyboard container command.
        src = hovered;
        dest = src == left ? right : left;
        if( item_index >= 0 ) {
            pane.index = item_index;
            close_context_menu();
            if( pane_point.x <= 3 && squares[AIM_CONTAINER].canputitems(
                    pane.items[item_index].items.front() ) ) {
                process_action( "ITEMS_CONTAINER" );
            }
        }
        return true;
    }

    src = hovered;
    dest = src == left ? right : left;

    if( action == "SELECT" ) {
        if( handle_location_click( hovered, pane_point ) ) {
            return true;
        }
        if( pane_point.y == 3 && pane_point.x >= 2 && pane_point.x < 12 ) {
            process_action( "RELOAD_SELECTED" );
        } else if( pane_point.y == 3 && pane_point.x >= 13 && pane_point.x < 27 &&
                   getmaxx( pane.window ) >= 48 ) {
            process_action( "SORT_AMMO" );
        } else if( pane_point.y == 3 && pane_point.x >= 27 && pane_point.x < 37 && pane.container &&
                   getmaxx( pane.window ) >= 58 ) {
            process_action( "ITEMS_PARENT" );
        } else if( pane_point.y == 0 ) {
            process_action( "SORT" );
        } else if( pane_point.y == 4 ) {
            process_action( pane_point.x < getmaxx( pane.window ) / 4 ? "PAGE_UP" : "PAGE_DOWN" );
        } else if( pane_point.y == getmaxy( pane.window ) - 1 ) {
            process_action( "FILTER" );
        } else if( item_index >= 0 ) {
            pane.index = item_index;
            close_context_menu();
            log_workspace_event( string_format( "select item=%s pane=%s index=%d area=%d",
                                                pane.items[item_index].items.front()->typeId().str(),
                                                hovered == left ? "left" : "right", item_index,
                                                static_cast<int>( pane.get_area() ) ) );
        }
        return true;
    }

    if( action == "SEC_SELECT" ) {
        if( item_index >= 0 ) {
            pane.index = item_index;
            context_menu_side = hovered;
            context_menu_anchor = pane_point;
            context_use_methods_open = false;
            log_workspace_event( string_format( "right click item=%s pane=%s index=%d area=%d",
                                                pane.items[item_index].items.front()->typeId().str(),
                                                hovered == left ? "left" : "right", item_index,
                                                static_cast<int>( pane.get_area() ) ) );
            process_action( "CONTEXT_MENU" );
        } else if( pane.container ) {
            process_action( "ITEMS_PARENT" );
        }
        return true;
    }

    return true;
}

void advanced_inventory::redraw_action_strip()
{
    action_buttons.clear();
    const int right_edge = getmaxx( head ) - 2;
    advanced_inv_listitem *sitem = panes[src].get_cur_item_ptr();
    avatar &u = get_avatar();
    if( sitem != nullptr ) {
        trim_and_print( head, point( 2, 1 ), right_edge - 2, c_white,
                        string_format( _( "%1$s  →  %2$s" ), sitem->items.front()->tname(),
                                       squares[panes[dest].get_area()].name ) );
    } else {
        trim_and_print( head, point( 2, 1 ), right_edge - 2, c_dark_gray,
                        _( "Select an item in either pane." ) );
    }
    std::string status = workspace_status;
    nc_color status_color = c_light_blue;
    if( sitem != nullptr && panes[dest].get_area() == AIM_WORN &&
        panes[src].get_area() != AIM_WORN ) {
        const ret_val<void> can_wear = u.can_wear( *sitem->items.front() );
        if( can_wear.success() ) {
            status = string_format( _( "Allowed: dropping %s on Worn will equip it using normal move costs." ),
                                    sitem->items.front()->tname() );
            status_color = c_light_green;
        } else {
            status = string_format( _( "Cannot wear %1$s: %2$s" ),
                                    sitem->items.front()->tname(), can_wear.str() );
            status_color = c_light_red;
        }
    } else if( sitem != nullptr && panes[dest].get_area() == AIM_CONTAINER &&
               panes[dest].container ) {
        item item_copy = *sitem->items.front();
        ret_val<void> can_contain = panes[dest].container->can_contain( item_copy );
        if( can_contain.success() ) {
            can_contain = panes[dest].container.parents_can_contain_recursive( &item_copy );
        }
        if( can_contain.success() ) {
            status = string_format( _( "Allowed: %1$s fits in %2$s." ), item_copy.tname(),
                                    panes[dest].container->tname() );
            status_color = c_light_green;
        } else {
            status = string_format( _( "Cannot put %1$s in %2$s: %3$s" ), item_copy.tname(),
                                    panes[dest].container->tname(), can_contain.str() );
            status_color = c_light_red;
        }
    }
    trim_and_print( head, point( 2, 2 ), right_edge - 2, status_color, status );
    trim_and_print( head, point( 2, 3 ), right_edge - 2, c_dark_gray,
                    _( "Left-click selects · hold and move to drag · right-click opens actions" ) );
}

void advanced_inventory::close_context_menu()
{
    context_actions_open = false;
    context_use_methods_open = false;
    context_menu_side.reset();
    context_menu_width = 0;
    context_menu_height = 0;
    action_buttons.clear();
}

void advanced_inventory::draw_context_menu()
{
    action_buttons.clear();
    if( !context_actions_open || !context_menu_side ) {
        return;
    }

    const side menu_side = *context_menu_side;
    if( src != menu_side ) {
        close_context_menu();
        return;
    }
    advanced_inv_listitem *sitem = panes[src].get_cur_item_ptr();
    if( sitem == nullptr ) {
        close_context_menu();
        return;
    }

    avatar &u = get_avatar();
    const item_location loc = sitem->items.front();
    const auto add_entry = [&]( const std::string &label, const std::string &action,
                                const bool enabled = true,
                                const std::string &disabled_reason = std::string() ) {
        action_buttons.push_back( { label, point::zero, 0, action, disabled_reason, enabled } );
    };

    if( context_use_methods_open ) {
        for( const auto &method : loc->type->use_methods ) {
            const ret_val<void> can_call = method.second.can_call( u, *loc, loc.pos_bub( get_map() ) );
            add_entry( method.second.get_name(), "USE_METHOD:" + method.first,
                       can_call.success(), can_call.str() );
        }
        if( loc->has_relic_activation() ) {
            add_entry( _( "Activate relic" ), "USE_RELIC", loc.held_by( u ),
                       _( "Pick up this relic before activating it." ) );
        }
        add_entry( _( "Back" ), "BACK_TO_ACTIONS" );
        add_entry( _( "Close" ), "CLOSE_ACTIONS" );
    } else {
        const bool is_worn = u.is_worn( *loc );
        const bool is_wielded = u.is_wielding( *loc );
        const ret_val<void> wear_result = u.can_wear( *loc );
        const ret_val<void> takeoff_result = u.can_takeoff( *loc );
        const ret_val<void> wield_result = u.can_wield( *loc );
        const ret_val<void> stow_result = u.can_unwield( *loc );
        const bool can_activate = loc->type->has_use() || loc->has_relic_activation();
        const bool can_unload = !loc->has_flag( json_flag_NO_UNLOAD ) &&
                                ( !loc->empty() || loc->ammo_remaining() > 0 );

        if( loc->is_container() ) {
            add_entry( _( "Open" ), "OPEN_SELECTED" );
        }
        add_entry( _( "Move amount…" ), "MOVE_SELECTED_AMOUNT" );
        if( is_worn ) {
            add_entry( _( "Take off" ), "TAKE_OFF_SELECTED", takeoff_result.success(),
                       takeoff_result.str() );
        } else {
            add_entry( _( "Wear" ), "WEAR_SELECTED", wear_result.success(), wear_result.str() );
        }
        if( is_wielded ) {
            add_entry( _( "Stow" ), "STOW_SELECTED", stow_result.success(), stow_result.str() );
        } else {
            add_entry( _( "Wield" ), "WIELD_SELECTED", wield_result.success(), wield_result.str() );
        }
        if( can_activate ) {
            add_entry( _( "Activate / use" ), "USE_SELECTED" );
        }
        if( loc->is_book() ) {
            add_entry( _( "Read" ), "READ_SELECTED" );
        }
        if( loc->is_comestible() || loc->is_medical_tool() ) {
            add_entry( _( "Consume" ), "CONSUME_SELECTED" );
        }
        if( loc->is_gun() || loc->is_magazine() ) {
            add_entry( _( "Reload" ), "RELOAD_SELECTED" );
        }
        if( can_unload ) {
            add_entry( _( "Unload" ), "UNLOAD_SELECTED" );
        }
        add_entry( _( "Examine" ), "EXAMINE_SELECTED" );
        add_entry( loc->is_favorite ? _( "Unfavorite" ) : _( "Favorite" ),
                   "FAVORITE_SELECTED" );
        if( loc.held_by( u ) ) {
            add_entry( _( "Assign inventory key" ), "ASSIGN_KEY_SELECTED" );
        }
        add_entry( _( "Close" ), "CLOSE_ACTIONS" );
    }

    if( action_buttons.empty() ) {
        close_context_menu();
        return;
    }

    catacurses::window &window = panes[menu_side].window;
    const int pane_width = getmaxx( window );
    const int pane_height = getmaxy( window );
    int widest_label = 0;
    for( const action_button &button : action_buttons ) {
        widest_label = std::max( widest_label, utf8_width( button.label ) );
    }
    context_menu_width = std::clamp( widest_label + 4, 16, std::max( 16, pane_width - 2 ) );
    context_menu_height = std::min( static_cast<int>( action_buttons.size() ) + 2,
                                    std::max( 3, pane_height - 2 ) );
    const int max_entries = context_menu_height - 2;
    if( static_cast<int>( action_buttons.size() ) > max_entries ) {
        action_buttons.resize( max_entries );
    }

    int menu_x = context_menu_anchor.x + 2;
    if( menu_x + context_menu_width >= pane_width ) {
        menu_x = context_menu_anchor.x - context_menu_width - 1;
    }
    menu_x = std::clamp( menu_x, 1, std::max( 1, pane_width - context_menu_width - 1 ) );
    int menu_y = context_menu_anchor.y;
    if( menu_y + context_menu_height >= pane_height ) {
        menu_y = pane_height - context_menu_height - 1;
    }
    menu_y = std::clamp( menu_y, 1, std::max( 1, pane_height - context_menu_height - 1 ) );
    context_menu_pos = point( menu_x, menu_y );

    const std::string blank( context_menu_width, ' ' );
    for( int row = 0; row < context_menu_height; ++row ) {
        mvwprintz( window, context_menu_pos + point( 0, row ), c_black, "%s", blank );
    }
    mvwhline( window, context_menu_pos, c_light_gray, LINE_OXOX, context_menu_width );
    mvwhline( window, context_menu_pos + point( 0, context_menu_height - 1 ), c_light_gray,
              LINE_OXOX, context_menu_width );
    mvwvline( window, context_menu_pos, c_light_gray, LINE_XOXO, context_menu_height );
    mvwvline( window, context_menu_pos + point( context_menu_width - 1, 0 ), c_light_gray,
              LINE_XOXO, context_menu_height );
    mvwputch( window, context_menu_pos, c_light_gray, LINE_OXXO );
    mvwputch( window, context_menu_pos + point( context_menu_width - 1, 0 ), c_light_gray,
              LINE_OOXX );
    mvwputch( window, context_menu_pos + point( 0, context_menu_height - 1 ), c_light_gray,
              LINE_XXOO );
    mvwputch( window, context_menu_pos + point( context_menu_width - 1, context_menu_height - 1 ),
              c_light_gray, LINE_XOOX );

    for( int row = 0; row < static_cast<int>( action_buttons.size() ); ++row ) {
        action_button &button = action_buttons[row];
        button.pos = context_menu_pos + point( 1, row + 1 );
        button.width = context_menu_width - 2;
        const bool hovered = mouse_hover_side && *mouse_hover_side == menu_side &&
                             mouse_hover_point.y == button.pos.y &&
                             mouse_hover_point.x >= button.pos.x &&
                             mouse_hover_point.x < button.pos.x + button.width;
        const nc_color color = !button.enabled ? c_dark_gray : hovered ? h_green : c_light_green;
        trim_and_print( window, button.pos, button.width, color, button.label );
    }
    wnoutrefresh( window );
}

bool advanced_inventory::handle_action_click( const point &p )
{
    for( const action_button &button : action_buttons ) {
        if( p.y == button.pos.y && p.x >= button.pos.x &&
            p.x < button.pos.x + button.width ) {
            if( !button.enabled ) {
                set_workspace_status( button.disabled_reason.empty() ?
                                      _( "That action is not available." ) : button.disabled_reason );
                log_workspace_event( string_format( "disabled context action=%s reason=%s",
                                                    button.action, button.disabled_reason ) );
                return true;
            }
            log_workspace_event( string_format( "clicked context action=%s", button.action ) );
            exit = run_context_action( button.action );
            return true;
        }
    }
    return false;
}

void advanced_inventory::draw_drag_ghost()
{
    if( !mouse_drag_item || !mouse_drag_side || !mouse_hover_side ) {
        return;
    }
    const catacurses::window &window = panes[*mouse_hover_side].window;
    const int ghost_x = std::clamp( mouse_hover_point.x + 1, 1, getmaxx( window ) - 2 );
    const int max_width = std::max( 1, getmaxx( window ) - ghost_x - 1 );
    const point ghost_pos( ghost_x,
                           std::clamp( mouse_hover_point.y, 1, getmaxy( window ) - 2 ) );
    trim_and_print( window, ghost_pos, max_width, h_yellow,
                    string_format( "[%s]", mouse_drag_item->tname() ) );
    wnoutrefresh( window );
}

void advanced_inventory::redraw_sidebar()
{
    input_context ctxt( "ADVANCED_INVENTORY" );
    ctxt.register_action( "HELP_KEYBINDINGS" );

    werase( head );
    werase( minimap );
    werase( mm_border );
    draw_border( head );
    mvwprintz( head, point( 2, 0 ), c_light_cyan, _( "< Inventory workspace >" ) );
    redraw_action_strip();
    draw_minimap();
    right_print( head, 0, +3, c_white, string_format(
                     _( "< [<color_yellow>%s</color>] keybindings >" ),
                     ctxt.get_desc( "HELP_KEYBINDINGS" ) ) );
    if( get_player_character().has_watch() ) {
        const std::string time = to_string_time_of_day( calendar::turn );
        mvwprintz( head, point( 2, 0 ), c_white, time );
    }
    wnoutrefresh( head );
    refresh_minimap();
}

void advanced_inventory::change_square( const aim_location changeSquare,
                                        advanced_inventory_pane &dpane, advanced_inventory_pane &spane )
{
    // Determine behavior if current pane is used.  AIM_CONTAINER should never swap to allow for multi-containers
    if( ( panes[left].get_area() == changeSquare || panes[right].get_area() == changeSquare ) &&
        changeSquare != AIM_CONTAINER && changeSquare != AIM_PARENT ) {
        if( squares[changeSquare].can_store_in_vehicle() && changeSquare != AIM_DRAGGED ) {
            // only deal with spane, as you can't _directly_ change dpane
            if( spane.get_area() == AIM_CONTAINER ) {
                spane.container = item_location::nowhere;
                spane.container_base_loc = NUM_AIM_LOCATIONS;
                // Update dpane to show items removed from the spane.
                dpane.recalc = true;
            }
            if( spane.get_area() == dpane.get_area() ) {
                // swap the `in_vehicle` element of each pane if "one in, one out"
                spane.set_area( squares[spane.get_area()], !spane.in_vehicle() );
                dpane.set_area( squares[dpane.get_area()], !dpane.in_vehicle() );
                recalc = true;
            } else if( dpane.get_area() == changeSquare ) {
                spane.set_area( squares[changeSquare], !dpane.in_vehicle() );
                spane.recalc = true;
            } else {
                spane.set_area( squares[spane.get_area()], !spane.in_vehicle() );
                spane.recalc = true;
            }
        } else {
            swap_panes();
        }
    } else if( changeSquare == AIM_PARENT && spane.container ) {
        spane.target_item_after_recalc = spane.container;
        if( spane.container.has_parent() ) {
            if( spane.container_base_loc == AIM_INVENTORY && !spane.container.parent_item().has_parent() ) {
                // If we're here from the inventory, skip past individual worn items straight to the full inventory view.
                change_square( AIM_INVENTORY, dpane, spane );
            } else {
                if( spane.container.parent_item() == dpane.container ) {
                    swap_panes();
                    return;
                }
                spane.container = spane.container.parent_item();
                spane.set_area( squares[AIM_CONTAINER], false );
            }
        } else {
            change_square( spane.container_base_loc, dpane, spane );
        }
        spane.recalc = true;
        spane.index = 0;
        dpane.recalc = true;
    } else if( squares[changeSquare].canputitems(
                   changeSquare == AIM_CONTAINER && spane.get_cur_item_ptr() != nullptr ?
                   spane.get_cur_item_ptr()->items.front() : item_location::nowhere ) ) {
        if( changeSquare == AIM_CONTAINER ) {
            item_location &target_container = spane.get_cur_item_ptr()->items.front();
            if( target_container == dpane.container ) {
                swap_panes();
                return;
            }
            // Set the pane's container to the selected item.
            spane.container = target_container;
            if( spane.get_area() != AIM_CONTAINER ) {
                spane.container_base_loc = spane.get_area();
            }
            // Update dpane to hide items added to the spane.
            dpane.recalc = true;
        } else {
            // Reset the pane's container whenever we're switching to something else.
            spane.container = item_location::nowhere;
            if( spane.get_area() == AIM_CONTAINER ) {
                spane.container_base_loc = NUM_AIM_LOCATIONS;
                // Update dpane to show items removed from the spane.
                dpane.recalc = true;
            }
        }
        // Check the original area if we can place items in vehicle storage.
        bool in_vehicle_cargo = false;
        if( squares[changeSquare].can_store_in_vehicle() && spane.get_area() != changeSquare ) {
            // auto select vehicle if items exist at said square, or both are empty
            if( changeSquare == AIM_DRAGGED ) {
                in_vehicle_cargo = true;
            } else {
                // check item stacks in vehicle and map at said square
                advanced_inv_area sq = squares[changeSquare];
                map_stack map_stack = get_map().i_at( sq.pos );
                vehicle_stack veh_stack = sq.get_vehicle_stack();
                // auto switch to vehicle storage if vehicle items are there, or neither are there
                if( !veh_stack.empty() || map_stack.empty() ) {
                    in_vehicle_cargo = true;
                }
            }
        }
        spane.set_area( squares[changeSquare], in_vehicle_cargo );
        spane.index = 0;
        spane.recalc = true;
        if( dpane.get_area() == AIM_ALL ) {
            dpane.recalc = true;
        }
    } else {
        switch( changeSquare ) {
            case AIM_DRAGGED:
                set_workspace_status( _( "You aren't dragging a vehicle." ) );
                break;
            case AIM_CONTAINER:
                set_workspace_status( _( "Select a container item before opening it." ) );
                break;
            case AIM_PARENT:
                set_workspace_status( _( "This pane is already at its top level." ) );
                break;
            default:
                set_workspace_status( _( "That tile cannot accept items." ) );
                break;
        }
    }
}

bool advanced_inventory::start_activity(
    const aim_location destarea,
    const aim_location /*srcarea*/,
    advanced_inv_listitem *sitem, int &amount_to_move,
    const bool from_vehicle, const bool to_vehicle )
{

    const bool by_charges = sitem->items.front()->count_by_charges();

    log_workspace_event( string_format(
                             "activity request item=%s source=%d destination=%d amount=%d "
                             "from_vehicle=%d to_vehicle=%d",
                             sitem->items.front()->typeId().str(), static_cast<int>( sitem->area ),
                             static_cast<int>( destarea ), amount_to_move,
                             static_cast<int>( from_vehicle ), static_cast<int>( to_vehicle ) ) );

    Character &player_character = get_player_character();

    if( destarea != AIM_CONTAINER ) {
        // Find target items and quantities thereof for the new activity
        std::vector<item_location> target_items;
        std::vector<int> quantities;
        if( by_charges ) {
            target_items.emplace_back( sitem->items.front() );
            quantities.push_back( amount_to_move );
        } else {
            for( std::vector<item_location>::iterator it = sitem->items.begin(); amount_to_move > 0 &&
                 it != sitem->items.end(); ++it ) {
                target_items.emplace_back( *it );
                quantities.push_back( 0 );
                --amount_to_move;
            }
            if( to_vehicle && sitem->items.front()->is_bucket_nonempty() ) {
                // Copy the pointers so they won't break if the list gets reordered as buckets are partly emptied.
                std::vector<item_location> target_buckets = sitem->items;
                if( target_buckets.front()->contains_no_solids() ) {
                    target_buckets.front()->handle_liquid_or_spill( player_character, &*target_buckets.front() );
                    if( !target_buckets.front()->empty_container() ) {
                        return false;
                    }
                } else {
                    if( !query_yn( _( "The %s would spill if stored there.  Store its contents separately first?" ),
                                   target_buckets.front()->tname() ) ) {
                        return false;
                    }
                    for( item *it : target_buckets.front()->get_contents().all_items_top() ) {
                        target_items.emplace_back( target_buckets.front(), it );
                        quantities.emplace_back( it->count() );
                    }
                }
            }
        }

        do_return_entry();
        if( destarea == AIM_WORN ) {
            const wear_activity_actor act( target_items, quantities );
            player_character.assign_activity( act );
        } else if( destarea == AIM_WIELD ) {
            player_character.assign_activity(
                wield_activity_actor( target_items.front(), quantities.front() ) );
        } else if( destarea == AIM_INVENTORY ) {
            const std::optional<tripoint_bub_ms> starting_pos = from_vehicle
                    ? std::nullopt
                    : std::optional<tripoint_bub_ms>( player_character.pos_bub() );
            const pickup_activity_actor act( target_items, quantities, starting_pos, false );
            player_character.assign_activity( act );
        } else {
            // Stash the destination
            const tripoint_rel_ms relative_destination = squares[destarea].off;

            const move_items_activity_actor act( target_items, quantities, to_vehicle, relative_destination );
            player_character.assign_activity( act );
        }
        return true;
    } else {
        if( !panes[dest].container.get_item() ) {
            debugmsg( "Active container is null, failed to insert!" );
            return false;
        }
        if( sitem->items.front() == panes[dest].container ||
            sitem->items.front().eventually_contains( panes[dest].container ) ) {
            set_workspace_status( string_format( _( "You cannot put %s inside itself." ),
                                                 sitem->items.front()->type_name() ) );
            return false;
        }
        if( panes[dest].container->will_spill_if_unsealed()
            && panes[dest].container.where() != item_location::type::map
            && !player_character.is_wielding( *panes[dest].container ) ) {

            set_workspace_status( string_format(
                                      _( "%s would spill; it must be on the ground or wielded." ),
                                      panes[dest].container->type_name() ) );
            return false;
        }

        // Create drop locations out of target items and quantities
        drop_locations target_inserts;
        if( by_charges ) {
            target_inserts.emplace_back( std::make_pair( sitem->items.front(), amount_to_move ) );
        } else {
            for( std::vector<item_location>::iterator it = sitem->items.begin(); amount_to_move > 0 &&
                 it != sitem->items.end(); ++it ) {
                target_inserts.emplace_back( std::make_pair( *it, 0 ) );
                --amount_to_move;
            }
            if( sitem->items.front()->is_bucket_nonempty() ) {
                // Copy the pointers so they won't break if the list gets reordered as buckets are partly emptied.
                std::vector<item_location> target_buckets = sitem->items;
                if( target_buckets.front()->contains_no_solids() ) {
                    target_buckets.front()->handle_liquid_or_spill( player_character, &*target_buckets.front() );
                    if( !target_buckets.front()->empty_container() ) {
                        return false;
                    }
                } else {
                    if( !query_yn( _( "The %s would spill if stored there.  Store its contents separately first?" ),
                                   target_buckets.front()->tname() ) ) {
                        return false;
                    }
                    // Emplace contents in front of the container because insert_item_activity_actor processes from the front.
                    for( item *it : target_buckets.front()->get_contents().all_items_top() ) {
                        target_inserts.emplace_front( item_location( target_buckets.front(), it ), it->count() );
                    }
                }
            }
        }

        do_return_entry();
        const insert_item_activity_actor act( panes[dest].container, target_inserts, false, false );
        player_character.assign_activity( act );
        return true;
    }
}

bool advanced_inventory::action_move_item( advanced_inv_listitem *sitem,
        advanced_inventory_pane &dpane, const advanced_inventory_pane &spane,
        const std::string &action )
{
    bool exit = false;
    if( sitem == nullptr ) {
        return false;
    }
    avatar &player_character = get_avatar();
    aim_location destarea = dpane.get_area();
    aim_location srcarea = sitem->area;
    bool restore_area = destarea == AIM_ALL;

    const auto is_world_area = []( const aim_location area ) {
        return ( area >= AIM_SOUTHWEST && area <= AIM_NORTHEAST ) || area == AIM_DRAGGED ||
               area == AIM_ALL;
    };
    const bool world_transfer = is_world_area( srcarea ) || is_world_area( destarea ) ||
                                ( spane.container && !spane.container.held_by( player_character ) ) ||
                                ( dpane.container && !dpane.container.held_by( player_character ) );
    if( world_transfer && ( player_character.has_active_mutation( trait_SHELL2 ) ||
                            player_character.has_active_mutation( trait_SHELL3 ) ) ) {
        set_workspace_status( _( "You cannot move items to or from the world while inside your shell." ) );
        return false;
    }
    if( world_transfer && player_character.is_mounted() ) {
        set_workspace_status( _( "You cannot move items to or from the world while mounted." ) );
        return false;
    }
    if( world_transfer && player_character.has_effect( effect_incorporeal ) ) {
        set_workspace_status( _( "You lack the substance to move items to or from the world." ) );
        return false;
    }
    if( !query_destination( destarea ) ) {
        return false;
    }
    // Not necessarily equivalent to spane.in_vehicle() if using AIM_ALL
    bool from_vehicle = sitem->from_vehicle;
    bool to_vehicle = dpane.in_vehicle();

    // Same location check for AIM_CONTAINER and AIM_ALL.
    // AIM_ALL should disable same area check and handle it with proper filtering instead.
    // This is a workaround around the lack of vehicle location info in
    // either aim_location or advanced_inv_listitem.
    if( spane.container ) {
        if( spane.container == dpane.container ) {
            set_workspace_status( string_format( _( "The %1$s is already in the %2$s." ),
                                                 sitem->items.front()->type_name(),
                                                 dpane.container->type_name() ) );
            return false;
        }
    } else if( squares[srcarea].is_same( squares[destarea] ) &&
               spane.get_area() != AIM_ALL && spane.in_vehicle() == dpane.in_vehicle() ) {
        set_workspace_status( string_format( _( "The %1$s is already there." ),
                                             sitem->items.front()->type_name() ) );
        return false;
    }
    cata_assert( !sitem->items.empty() );
    if( destarea == AIM_WORN ) {
        const item &itm = *sitem->items.front().get_item();
        const ret_val<void> can_wear = player_character.can_wear( itm );
        if( !can_wear.success() ) {
            set_workspace_status( string_format( _( "Cannot wear %1$s: %2$s" ), itm.tname(),
                                                 can_wear.str() ) );
            return false;
        }
        log_workspace_event( string_format( "wear validation success item=%s source=%d",
                                            itm.typeId().str(), static_cast<int>( srcarea ) ) );
    }
    if( srcarea == AIM_WORN && sitem->items.front() == player_character.get_wielded_item() ) {
        const ret_val<void> can_unwield = player_character.can_unwield( *sitem->items.front() );
        if( !can_unwield.success() ) {
            set_workspace_status( string_format( _( "Cannot stow %1$s: %2$s" ),
                                                 sitem->items.front()->tname(), can_unwield.str() ) );
            return false;
        }
    } else if( srcarea == AIM_WORN ) {
        const ret_val<void> can_takeoff = player_character.can_takeoff( *sitem->items.front() );
        if( !can_takeoff.success() ) {
            set_workspace_status( string_format( _( "Cannot take off %1$s: %2$s" ),
                                                 sitem->items.front()->tname(), can_takeoff.str() ) );
            return false;
        }
    }
    int amount_to_move = 0;
    if( !query_charges( destarea, *sitem, action, amount_to_move ) ) {
        return false;
    }
    item it_copy = *sitem->items.front();
    if( it_copy.count_by_charges() ) {
        it_copy.charges = std::min( amount_to_move, sitem->items.front()->charges );
    }
    if( spane.get_area() == AIM_CONTAINER &&
        spane.container.get_item()->has_flag( json_flag_NO_UNLOAD ) ) {
        set_workspace_status( _( "This source container cannot be unloaded." ) );
        return false;
    }
    if( destarea == AIM_CONTAINER ) {
        if( dpane.container.get_item()->has_flag( json_flag_NO_RELOAD ) ) {
            set_workspace_status( _( "This destination container cannot accept inserted items." ) );
            return false;
        }
        ret_val<void> can_contain = dpane.container->can_contain( it_copy );
        if( can_contain.success() ) {
            can_contain = dpane.container.parents_can_contain_recursive( &it_copy );
        }
        if( !can_contain.success() ) {
            set_workspace_status( can_contain.str().empty() ?
                                  //~ %1$s: item we failed to put in the container, %2$s: container to put item in
                                  string_format( _( "Could not put %1$s into %2$s." ),
                                                 sitem->items.front()->tname(), dpane.container->tname() ) :
                                  //~ %1$s: item we failed to put in the container, %2$s: container to put item in,
                                  //~ %3$s: reason it failed
                                  string_format( _( "Could not put %1$s into %2$s: %3$s" ),
                                                 sitem->items.front()->tname(), dpane.container->tname(),
                                                 can_contain.str() ) );
            return false;
        }
    }
    // This makes sure that all item references in the advanced_inventory_pane::items vector
    // are recalculated, even when they might not have changed, but they could (e.g. items
    // taken from inventory, but unable to put into the cargo trunk go back into the inventory,
    // but are potentially at a different place).
    recalc = true;
    cata_assert( amount_to_move > 0 );

    if( srcarea == AIM_CONTAINER && destarea == AIM_INVENTORY &&
        spane.container.held_by( player_character ) ) {
        set_workspace_status( string_format(
                                  _( "%s is already carried. Choose a specific container on the other pane to reorganize it." ),
                                  sitem->items.front()->tname() ) );

    } else if( srcarea == AIM_INVENTORY && destarea == AIM_WORN ) {

        // make sure advanced inventory is reopened after activity completion.
        do_return_entry();

        const wear_activity_actor act( { sitem->items.front() }, { amount_to_move } );
        player_character.assign_activity( act );
        // exit so that the activity can be carried out
        exit = true;

    } else if( srcarea == AIM_INVENTORY && destarea == AIM_WIELD ) {
        do_return_entry();
        const wield_activity_actor act( sitem->items.front(), amount_to_move );
        player_character.assign_activity( act );
        exit = true;
    } else if( srcarea == AIM_WORN &&
               sitem->items.front() == player_character.get_wielded_item() &&
               destarea == AIM_INVENTORY ) {
        if( player_character.unwield() ) {
            recalc = true;
        }

    } else if( srcarea == AIM_WORN &&
               sitem->items.front() == player_character.get_wielded_item() ) {
        if( destarea == AIM_CONTAINER ) {
            exit = start_activity( destarea, srcarea, sitem, amount_to_move, from_vehicle, to_vehicle );
        } else {
            const tripoint_rel_ms placement = squares[destarea].off;
            const bool force_ground = !to_vehicle;
            do_return_entry();
            const drop_activity_actor act( { drop_or_stash_item_info( sitem->items.front(),
                                              amount_to_move ) }, placement, force_ground );
            player_character.assign_activity( act );
            exit = true;
        }

    } else if( srcarea == AIM_INVENTORY ||
               ( srcarea == AIM_WORN && sitem->items.front() != player_character.get_wielded_item() ) ) {
        cata_assert( destarea != AIM_WIELD );

        if( srcarea == AIM_WORN && destarea == AIM_INVENTORY ) {
            // if worn, we need to fix with the worn index number (starts at -2, as -1 is weapon)
            // this is ok because worn items are never stacked (can't move more than 1)
            if( player_character.takeoff( Character::worn_position_to_index( sitem->idx ) + 1 ) ) {
                recalc = true;
            }
        } else {
            const ret_val<void> can_drop = player_character.can_drop( it_copy );
            if( !can_drop.success() ) {
                set_workspace_status( string_format( _( "Cannot move %1$s: %2$s" ), it_copy.tname(),
                                                     can_drop.str() ) );
                return false;
            }
            if( destarea == AIM_CONTAINER ) {
                exit = start_activity( destarea, srcarea, sitem, amount_to_move, from_vehicle,
                                       to_vehicle );
            } else {
                const tripoint_rel_ms placement = squares[destarea].off;
                // incase there is vehicle cargo space at dest but the player wants to drop to ground
                const bool force_ground = !to_vehicle;
                std::vector<drop_or_stash_item_info> to_drop;

                int remaining_amount = amount_to_move;
                for( const item_location &itm : sitem->items ) {
                    if( remaining_amount <= 0 ) {
                        break;
                    }
                    const int move_amount = itm->count_by_charges() ?
                                            std::min( remaining_amount, itm->charges ) : 1;
                    to_drop.emplace_back( itm, move_amount );
                    remaining_amount -= move_amount;
                }

                do_return_entry();
                const drop_activity_actor act( to_drop, placement, force_ground );
                player_character.assign_activity( act );
                exit = true;
            }
        }
    } else {
        if( destarea == AIM_INVENTORY ) {
            bool can_stash = player_character.can_stash( it_copy );
            if( !can_stash ) {
                set_workspace_status( string_format( _( "Pickup blocked: no carried pocket accepts %s." ),
                                                     sitem->items.front()->tname() ) );
                return false;
            }
        }
        // from map/vehicle: start ACT_PICKUP or ACT_MOVE_ITEMS as necessary
        // Make sure advanced inventory is reopened after activity completion.
        exit = start_activity( destarea, srcarea, sitem, amount_to_move, from_vehicle, to_vehicle );
    }

    // if dest was AIM_ALL then we used query_destination and should undo that
    if( restore_area ) {
        dpane.restore_area();
    }
    return exit;
}

void advanced_inventory::action_examine( advanced_inv_listitem *sitem,
        advanced_inventory_pane &/*spane*/ )
{
    const auto info_width = [this]() -> int {
        return w_width / 2;
    };
    const auto info_startx = [this]() -> int {
        return colstart + ( src == advanced_inventory::side::left ? w_width / 2 : 0 );
    };
    const item_location &loc = sitem->items.front();
    item &it = *loc;
    std::vector<iteminfo> item_info;
    std::vector<iteminfo> dummy_info;
    // item::info supplies the complete vanilla information model, including
    // armor coverage/protection and its body coverage preview.
    it.info( true, item_info );
    item_info.insert( item_info.begin(),
    { {}, string_format( _( "Location: %s" ), loc.describe( &get_avatar() ) ) } );

    item_info_data data( it.tname(), it.type_name(), item_info, dummy_info );
    data.handle_scrolling = true;
    data.arrow_scrolling = true;

    // Examine is deliberately information-only.  State-changing operations
    // stay in the item-anchored, mouse-operable context menu.
    iteminfo_window info_window( data, point( info_startx(), 0 ), info_width(), TERMY );
    info_window.execute();
    recalc = true;
}

bool advanced_inventory::action_unload( advanced_inv_listitem *sitem,
                                        advanced_inventory_pane &spane, advanced_inventory_pane &dpane )
{
    avatar &u = get_avatar();
    item_location src = spane.container;
    item_location dest = dpane.container;

    if( !src && sitem ) {
        src = sitem->items.front();
    } else {
        add_msg( m_info, _( "Nothing to unload." ) );
        return false;
    }

    const bool started = u.unload( src, false, dest );
    if( started && u.activity ) {
        do_return_entry();
        return true;
    }
    return false;
}

bool advanced_inventory::action_reload( advanced_inv_listitem *sitem )
{
    if( sitem == nullptr ) {
        set_workspace_status( _( "Select a gun or magazine to reload." ) );
        return false;
    }

    avatar &u = get_avatar();
    item_location target = sitem->items.front();
    if( !target->is_gun() && !target->is_magazine() ) {
        set_workspace_status( string_format( _( "%s is not a gun or magazine." ), target->tname() ) );
        return false;
    }

    log_workspace_event( string_format( "reload requested item=%s location=%d",
                                        target->typeId().str(), static_cast<int>( target.where() ) ) );
    g->reload_item( target, false );
    if( u.activity ) {
        do_return_entry();
        return true;
    }
    set_workspace_status( string_format( _( "No valid ammunition source is available for %s." ),
                                         target->tname() ) );
    return false;
}

bool advanced_inventory::action_context_menu( advanced_inv_listitem *sitem,
        advanced_inventory_pane &spane, advanced_inventory_pane &/*dpane*/ )
{
    if( sitem == nullptr ) {
        set_workspace_status( _( "Select an item first." ) );
        return false;
    }
    if( !context_menu_side ) {
        context_menu_side = src;
        const int selected_row = item_row_for_index( spane, spane.index );
        context_menu_anchor = point( 3, selected_row >= 0 ? selected_row : 6 );
    }
    context_actions_open = true;
    context_use_methods_open = false;
    log_workspace_event( string_format( "opened context menu item=%s pane=%s anchor=%d,%d",
                                        sitem->items.front()->typeId().str(),
                                        src == left ? "left" : "right", context_menu_anchor.x,
                                        context_menu_anchor.y ) );
    set_workspace_status( string_format( _( "Actions for %s" ), sitem->items.front()->tname() ) );
    return false;
}

bool advanced_inventory::run_context_action( const std::string &action )
{
    advanced_inventory_pane &spane = panes[src];
    advanced_inventory_pane &dpane = panes[dest];
    advanced_inv_listitem *sitem = spane.get_cur_item_ptr();
    if( action == "CLOSE_ACTIONS" ) {
        close_context_menu();
        return false;
    }
    if( action == "BACK_TO_ACTIONS" ) {
        context_use_methods_open = false;
        context_actions_open = true;
        return false;
    }
    if( sitem == nullptr ) {
        set_workspace_status( _( "The selected item is no longer available." ) );
        close_context_menu();
        return false;
    }

    avatar &u = get_avatar();
    item_location loc = sitem->items.front();
    log_workspace_event( string_format( "context action=%s item=%s source=%d destination=%d",
                                        action, loc->typeId().str(), static_cast<int>( sitem->area ),
                                        static_cast<int>( dpane.get_area() ) ) );

    const auto run_use_action = [&]( const std::string &method = std::string() ) {
        const activity_id previous_activity = u.activity.id();
        const std::string item_id = loc->typeId().str();
        always_recalc = true;
        avatar_action::use_item( u, loc, method );
        always_recalc = false;
        recalc = true;
        const bool started_activity = previous_activity != u.activity.id() || !ui;
        log_workspace_event( string_format( "use result item=%s method=%s activity=%d",
                                            item_id, method.empty() ? "default" : method,
                                            static_cast<int>( started_activity ) ) );
        if( started_activity ) {
            do_return_entry();
        }
        return started_activity;
    };

    if( action == "USE_SELECTED" ) {
        const int choices = static_cast<int>( loc->type->use_methods.size() ) +
                            static_cast<int>( loc->has_relic_activation() );
        if( choices > 1 ) {
            context_use_methods_open = true;
            context_actions_open = true;
            set_workspace_status( string_format( _( "Choose how to use %s." ), loc->tname() ) );
            return false;
        }
        close_context_menu();
        if( !loc->type->use_methods.empty() ) {
            return run_use_action( loc->type->use_methods.begin()->first );
        }
        return run_use_action();
    }
    const std::string use_method_prefix = "USE_METHOD:";
    if( action.compare( 0, use_method_prefix.size(), use_method_prefix ) == 0 ) {
        const std::string method = action.substr( use_method_prefix.size() );
        close_context_menu();
        return run_use_action( method );
    }
    if( action == "USE_RELIC" ) {
        close_context_menu();
        if( !loc.held_by( u ) ) {
            set_workspace_status( _( "Pick up this relic before activating it." ) );
            return false;
        }
        const activity_id previous_activity = u.activity.id();
        loc->use_relic( u, loc.pos_bub( get_map() ) );
        recalc = true;
        const bool started_activity = previous_activity != u.activity.id() || !ui;
        log_workspace_event( string_format( "relic use result item=%s activity=%d",
                                            loc->typeId().str(),
                                            static_cast<int>( started_activity ) ) );
        if( started_activity ) {
            do_return_entry();
        }
        return started_activity;
    }
    close_context_menu();

    const bool takes_world_item = !loc.held_by( u ) &&
                                  ( action == "WEAR_SELECTED" || action == "WIELD_SELECTED" );
    if( takes_world_item && ( u.has_active_mutation( trait_SHELL2 ) ||
                              u.has_active_mutation( trait_SHELL3 ) ) ) {
        set_workspace_status( _( "You cannot equip items from the world while inside your shell." ) );
        return false;
    }
    if( takes_world_item && u.is_mounted() ) {
        set_workspace_status( _( "You cannot equip items from the world while mounted." ) );
        return false;
    }
    if( takes_world_item && u.has_effect( effect_incorporeal ) ) {
        set_workspace_status( _( "You lack the substance to equip that item." ) );
        return false;
    }

    if( action == "OPEN_SELECTED" ) {
        change_square( AIM_CONTAINER, dpane, spane );
    } else if( action == "MOVE_SELECTED_AMOUNT" ) {
        return action_move_item( sitem, dpane, spane, "MOVE_VARIABLE_ITEM" );
    } else if( action == "WEAR_SELECTED" ) {
        const ret_val<void> can_wear = u.can_wear( *loc );
        if( !can_wear.success() ) {
            set_workspace_status( string_format( _( "Cannot wear %1$s: %2$s" ), loc->tname(),
                                                 can_wear.str() ) );
            return false;
        }
        do_return_entry();
        u.assign_activity( wear_activity_actor( { loc }, { 0 } ) );
        return true;
    } else if( action == "TAKE_OFF_SELECTED" ) {
        const ret_val<void> can_takeoff = u.can_takeoff( *loc );
        if( !can_takeoff.success() ) {
            set_workspace_status( string_format( _( "Cannot take off %1$s: %2$s" ), loc->tname(),
                                                 can_takeoff.str() ) );
            return false;
        }
        if( u.takeoff( loc ) ) {
            recalc = true;
        }
    } else if( action == "WIELD_SELECTED" ) {
        const ret_val<void> can_wield = u.can_wield( *loc );
        if( !can_wield.success() ) {
            set_workspace_status( string_format( _( "Cannot wield %1$s: %2$s" ), loc->tname(),
                                                 can_wield.str() ) );
            return false;
        }
        do_return_entry();
        u.assign_activity( wield_activity_actor( loc, 0 ) );
        return true;
    } else if( action == "STOW_SELECTED" ) {
        const ret_val<void> can_unwield = u.can_unwield( *loc );
        if( !can_unwield.success() ) {
            set_workspace_status( string_format( _( "Cannot stow %1$s: %2$s" ), loc->tname(),
                                                 can_unwield.str() ) );
            return false;
        }
        if( u.unwield() ) {
            recalc = true;
        }
    } else if( action == "RELOAD_SELECTED" ) {
        return action_reload( sitem );
    } else if( action == "UNLOAD_SELECTED" ) {
        return action_unload( sitem, spane, dpane );
    } else if( action == "READ_SELECTED" || action == "CONSUME_SELECTED" ) {
        return run_use_action();
    } else if( action == "EXAMINE_SELECTED" ) {
        action_examine( sitem, spane );
        return exit;
    } else if( action == "FAVORITE_SELECTED" ) {
        for( item_location &stack_item : sitem->items ) {
            stack_item->set_favorite( !stack_item->is_favorite );
        }
        recalc = true;
    } else if( action == "ASSIGN_KEY_SELECTED" ) {
        set_workspace_status(
            _( "Type one inventory letter and press Enter. Submit an empty field to clear it." ) );
        if( ui ) {
            ui_manager::redraw();
        }
        string_input_popup key_input;
        key_input.max_length( 1 ).window( panes[src].window, point( 2, 3 ),
                                         std::max( 3, getmaxx( panes[src].window ) - 3 ) );
        const std::string key = key_input.query_string();
        if( !key_input.canceled() ) {
            if( key.empty() ) {
                u.reassign_item( *loc, 0 );
                set_workspace_status( string_format( _( "Cleared the inventory key for %s." ),
                                                     loc->tname() ) );
            } else if( inv_chars.valid( key.front() ) ) {
                u.reassign_item( *loc, key.front() );
                set_workspace_status( string_format( _( "Assigned [%1$c] to %2$s." ), key.front(),
                                                     loc->tname() ) );
            } else {
                set_workspace_status( _( "That character is not a valid inventory key." ) );
            }
        }
    }
    return false;
}

void advanced_inventory::process_action( const std::string &input_action )
{
    recalc = false;
    // source and destination pane
    advanced_inventory_pane &spane = panes[src];
    advanced_inventory_pane &dpane = panes[dest];
    // current item in source pane, might be null
    advanced_inv_listitem *sitem = spane.get_cur_item_ptr();

    log_workspace_event( string_format( "action=%s active=%s source=%d destination=%d item=%s",
                                        input_action, src == left ? "left" : "right",
                                        static_cast<int>( spane.get_area() ),
                                        static_cast<int>( dpane.get_area() ),
                                        sitem == nullptr ? "none" :
                                        sitem->items.front()->typeId().str() ) );

    aim_location changeSquare = NUM_AIM_LOCATIONS;
    avatar &u = get_avatar();

    const std::string &action = is_processing() ? "MOVE_ALL_ITEMS" : input_action;
    if( action == "CATEGORY_SELECTION" ) {
        inCategoryMode = !inCategoryMode;
    } else if( action == "ITEMS_DEFAULT" ) {
        for( side cside : {
                 left, right
             } ) {
            advanced_inventory_pane &pane = panes[cside];
            int i_location = cside == left ? save_state->saved_area : save_state->saved_area_right;
            aim_location location = static_cast<aim_location>( i_location );
            if( pane.get_area() != location || location == AIM_ALL ) {
                pane.recalc = true;
            }
            pane.set_area( squares[location] );
        }
    } else if( action == "SAVE_DEFAULT" ) {
        save_state->saved_area = panes[left].get_area();
        save_state->saved_area_right = panes[right].get_area();
        set_workspace_status( _( "Default inventory workspace layout saved." ) );
    } else if( get_square( action, changeSquare ) ) {
        change_square( changeSquare, dpane, spane );
    } else if( action == "TOGGLE_FAVORITE" ) {
        if( sitem == nullptr ) {
            return;
        }
        for( item_location &item : sitem->items ) {
            item->set_favorite( !item->is_favorite );
        }
        // In case we've merged faved and unfaved items
        recalc = true;
    } else if( action == "MOVE_SINGLE_ITEM" ||
               action == "MOVE_VARIABLE_ITEM" ||
               action == "MOVE_ITEM_STACK" ) {
        exit = action_move_item( sitem, dpane, spane, action );
    } else if( action == "MOVE_ALL_ITEMS" ) {
        exit = move_all_items();
        recalc = true;
        if( exit ) {
            if( get_option<bool>( "CLOSE_ADV_INV" ) ) {
                move_all_items_and_waiting_to_quit = true;
            }
        }
    } else if( action == "SORT" ) {
        cycle_sort_mode( spane );
        recalc = true;
    } else if( action == "SORT_AMMO" ) {
        spane.sortby = SORTBY_AMMO;
        spane.recalc = true;
    } else if( action == "RELOAD_SELECTED" || action == "reload_item" ) {
        exit = action_reload( sitem );
    } else if( action == "CONTEXT_MENU" ) {
        exit = action_context_menu( sitem, spane, dpane );
    } else if( action == "FILTER" ) {
        const std::string &filter = spane.get_filter();
        filter_edit = true;
        if( ui ) {
            spopup = std::make_unique<string_input_popup>();
            spopup->max_length( 256 ).text( filter );
            spopup->identifier( "item_filter" ).hist_use_uilist( false );
            ui->mark_resize();
        }

        do {
            if( ui ) {
                ui_manager::redraw();
            }
            std::string new_filter = spopup->query_string( false );
            if( spopup->canceled() ) {
                // restore original filter
                spane.set_filter( filter );
            } else {
                spane.set_filter( new_filter );
            }
        } while( !spopup->canceled() && !spopup->confirmed() );
        filter_edit = false;
        spopup = nullptr;
    } else if( action == "RESET_FILTER" ) {
        spane.set_filter( "" );
    } else if( action == "TOGGLE_AUTO_PICKUP" ) {
        if( sitem == nullptr ) {
            return;
        }
        if( sitem->autopickup ) {
            get_auto_pickup().remove_rule( &*sitem->items.front() );
            sitem->autopickup = false;
        } else {
            get_auto_pickup().add_rule( &*sitem->items.front(), true );
            sitem->autopickup = true;
        }
        recalc = true;
    } else if( action == "EXAMINE" ) {
        if( sitem == nullptr ) {
            return;
        }
        action_examine( sitem, spane );
    } else if( action == "EXAMINE_CONTENTS" ) {
        if( sitem == nullptr ) {
            return;
        }
        item_location sitem_location = sitem->items.front();
        inventory_examiner examine_contents( u, sitem_location );
        examine_contents.add_contained_items( sitem_location );
        int examine_result = examine_contents.execute();
        if( examine_result == NO_CONTENTS_TO_EXAMINE ) {
            action_examine( sitem, spane );
        }
    } else if( action == "UNLOAD_CONTAINER" ) {
        exit = action_unload( sitem, spane, dpane );
    } else if( action == "QUIT" ) {
        exit = true;
    } else if( action == "PAGE_DOWN" ) {
        spane.scroll_page( linesPerPage, +1 );
    } else if( action == "PAGE_UP" ) {
        spane.scroll_page( linesPerPage, -1 );
    } else if( action == "HOME" ) {
        spane.scroll_to_start();
    } else if( action == "END" ) {
        spane.scroll_to_end();
    } else if( action == "DOWN" ) {
        if( inCategoryMode ) {
            spane.scroll_category( +1 );
        } else {
            spane.scroll_by( +1 );
        }
    } else if( action == "UP" ) {
        if( inCategoryMode ) {
            spane.scroll_category( -1 );
        } else {
            spane.scroll_by( -1 );
        }
    } else if( action == "LEFT" ) {
        src = left;
    } else if( action == "RIGHT" ) {
        src = right;
    } else if( action == "TOGGLE_TAB" ) {
        src = dest;
    } else if( action == "TOGGLE_VEH" ) {
        if( squares[spane.get_area()].can_store_in_vehicle() ) {
            // swap the panes if going vehicle will show the same tile
            if( spane.get_area() == dpane.get_area() && spane.in_vehicle() != dpane.in_vehicle() ) {
                swap_panes();
                // disallow for dragged vehicles
            } else if( spane.get_area() != AIM_DRAGGED ) {
                // Toggle between vehicle and ground
                spane.set_area( squares[spane.get_area()], !spane.in_vehicle() );
                spane.index = 0;
                spane.recalc = true;
                if( dpane.get_area() == AIM_ALL ) {
                    dpane.recalc = true;
                }
            }
        } else {
            set_workspace_status( _( "There is no vehicle cargo space at that tile." ) );
        }
    }
    dest = src == advanced_inventory::side::left ? advanced_inventory::side::right :
           advanced_inventory::side::left;
}

void advanced_inventory::display()
{
    avatar &player_character = get_avatar();
    input_context ctxt{ register_ctxt() };

    exit = false;
    if( !is_processing() ) {

        player_character.inv->restack( player_character );

        recalc = true;
        g->wait_popup_reset();
    }

    if( !ui ) {
        init();
        ui = std::make_unique<ui_adaptor>();
        ui->on_screen_resize( [&]( ui_adaptor & ui ) {
            constexpr int min_w_height = 10;
            const int min_w_width = FULL_SCREEN_WIDTH;
            const int max_w_width = get_option<bool>( "AIM_WIDTH" ) ? TERMX : std::max( 120,
                                    TERMX - 2 * ( panel_manager::get_manager().get_width_right() +
                                                  panel_manager::get_manager().get_width_left() ) );

            w_height = TERMY < min_w_height + head_height ? min_w_height : TERMY - head_height;
            w_width = TERMX < min_w_width ? min_w_width : TERMX > max_w_width ? max_w_width :
                      static_cast<int>( TERMX );

            //(TERMY>w_height)?(TERMY-w_height)/2:0;
            headstart = 0;
            colstart = TERMX > w_width ? ( TERMX - w_width ) / 2 : 0;

            head = catacurses::newwin( head_height, w_width - minimap_width, point( colstart, headstart ) );
            mm_border = catacurses::newwin( minimap_height + 2, minimap_width + 2,
                                            point( colstart + ( w_width - ( minimap_width + 2 ) ), headstart ) );
            minimap = catacurses::newwin( minimap_height, minimap_width,
                                          point( colstart + ( w_width - ( minimap_width + 1 ) ), headstart + 1 ) );
            panes[left].window = catacurses::newwin( w_height, w_width / 2, point( colstart,
                                 headstart + head_height ) );
            panes[right].window = catacurses::newwin( w_height, w_width / 2, point( colstart + w_width / 2,
                                  headstart + head_height ) );

            // 2 for the borders, 5 for the header stuff
            linesPerPage = w_height - 2 - 5;

            if( filter_edit && spopup ) {
                spopup->window( panes[src].window, point( 4, w_height - 1 ), w_width / 2 - 4 );
            }

            ui.position( point( colstart, headstart ), point( w_width, head_height + w_height ) );
        } );
        ui->mark_resize();

        ui->on_redraw( [&]( const ui_adaptor & ) {
            if( always_recalc ) {
                recalc = true;
            }

            redraw_pane( advanced_inventory::side::left );
            redraw_pane( advanced_inventory::side::right );
            if( panes[0].other_cont > -1 && panes[0].other_cont < linesPerPage ) {
                mvwprintz( panes[0].window, point( w_width / 2 - 1, panes[0].other_cont + 6 ), i_brown, " " );
                mvwprintz( panes[1].window, point( 0, panes[0].other_cont + 6 ), c_brown, "▶" );
            } else if( panes[1].other_cont > -1 && panes[1].other_cont < linesPerPage ) {
                mvwprintz( panes[0].window, point( w_width / 2 - 1, panes[1].other_cont + 6 ), c_brown, "◀" );
                mvwprintz( panes[1].window, point( 0, panes[1].other_cont + 6 ), i_brown, " " );
            }
            wnoutrefresh( panes[src].window );
            wnoutrefresh( panes[dest].window );
            redraw_sidebar();
            draw_context_menu();
            draw_drag_ghost();

            if( filter_edit && spopup ) {
                draw_item_filter_rules( panes[dest].window, 1, w_height - 2, item_filter_type::FILTER );
                mvwprintz( panes[src].window, point( 2, getmaxy( panes[src].window ) - 1 ), c_cyan, "< " );
                mvwprintz( panes[src].window, point( w_width / 2 - 4, getmaxy( panes[src].window ) - 1 ), c_cyan,
                           " >" );
                spopup->query_string( /*loop=*/false, /*draw_only=*/true );
            }
        } );
    }

    while( !exit ) {
        if( player_character.get_moves() < 0 ) {
            do_return_entry();
            return;
        }

        if( ui ) {
            ui->invalidate_ui();
            if( recalc ) {
                g->invalidate_main_ui_adaptor();
            }
            ui_manager::redraw_invalidated();
        }

        if( !is_processing() && move_all_items_and_waiting_to_quit ) {
            break;
        }

        const std::string action = ctxt.handle_input();
        if( !handle_mouse( ctxt, action ) ) {
            process_action( action );
        }
    }
}

bool advanced_inventory::query_destination( aim_location &def )
{
    if( def != AIM_ALL ) {
        if( squares[def].canputitems( panes[dest].container ) ) {
            return true;
        }
        set_workspace_status( _( "You can't put items there. Choose another destination on that pane." ) );
        return false;
    }
    set_workspace_status(
        _( "Choose a specific NW/N/NE/W/You/E/SW/S/SE destination on that pane before moving." ) );
    return false;
}

bool advanced_inventory::query_charges( aim_location destarea, const advanced_inv_listitem &sitem,
                                        const std::string &action, int &amount )
{
    // should be a specific location instead
    cata_assert( destarea != AIM_ALL );
    // valid item is obviously required
    cata_assert( !sitem.items.empty() );
    const item &it = *sitem.items.front();
    const bool by_charges = it.count_by_charges();
    // default to move all, unless if being equipped
    const int input_amount = by_charges ? it.charges : action == "MOVE_SINGLE_ITEM" ? 1 : sitem.stacks;
    // there has to be something to begin with
    cata_assert( input_amount > 0 );
    amount = input_amount;

    // Includes moving from/to inventory and around on the map.
    if( it.made_of_from_type( phase_id::LIQUID ) && !it.is_frozen_liquid() ) {
        set_workspace_status( _( "Spilt liquids cannot be picked back up. Try mopping them up instead." ) );
        return false;
    }
    if( it.made_of_from_type( phase_id::GAS ) ) {
        set_workspace_status( _( "Spilt gases cannot be picked up. They will disappear over time." ) );
        return false;
    }
    Character &player_character = get_player_character();
    // Check how many items you can stash. extra check because free_volume() doesn't account for pockets the item would not fit .
    if( destarea == AIM_INVENTORY ) {
        int copies_remaining = amount;
        player_character.can_stash_partial( it, copies_remaining, /*ignore_pkt_settings=*/false );
        amount -= copies_remaining;
        if( amount <= 0 ) {
            set_workspace_status( string_format( _( "Pickup blocked: no carried pocket can contain %s." ),
                                                 it.tname() ) );
            return false;
        }
    }
    // Check volume, this should work the same map and vehicles, but not for worn
    else if( destarea != AIM_WIELD && destarea != AIM_WORN ) {
        const units::volume free_volume = panes[dest].free_volume( squares[destarea] );
        const units::mass free_mass = panes[dest].free_weight_capacity();
        const int room_for = std::min( it.charges_per_volume( free_volume ),
                                       it.charges_per_weight( free_mass ) );
        if( room_for <= 0 ) {
            set_workspace_status( _( "Destination area is full. Remove some items first." ) );
            return false;
        }
        amount = std::min( room_for, amount );
    }
    // Map and vehicles have a maximal item count, check that. Inventory does not have this.
    if( destarea != AIM_INVENTORY &&
        destarea != AIM_WORN &&
        destarea != AIM_WIELD &&
        destarea != AIM_CONTAINER
      ) {
        advanced_inv_area &p = squares[destarea];
        const int cntmax = p.max_size - p.get_item_count();
        // For items counted by charges, adding it adds 0 items if something there stacks with it.
        const bool adds0 = by_charges && std::any_of( panes[dest].items.begin(), panes[dest].items.end(),
        [&it]( const advanced_inv_listitem & li ) {
            return li.items.front()->stacks_with( it );
        } );
        if( cntmax <= 0 && !adds0 ) {
            set_workspace_status( _( "Destination area has too many items. Remove some first." ) );
            return false;
        }
        // Items by charge count as a single item, regardless of the charges. As long as the
        // destination can hold another item, one can move all charges.
        if( !by_charges ) {
            amount = std::min( cntmax, amount );
        }
    }

    // Inventory has a weight capacity, map and vehicle don't have that
    if( ( destarea == AIM_INVENTORY || destarea == AIM_WORN || destarea == AIM_WIELD ) &&
        !sitem.items.front().held_by( player_character ) ) {
        const units::mass unitweight = it.weight() / ( by_charges ? it.charges : 1 );
        const units::mass max_weight = player_character.max_pickup_capacity() -
                                       player_character.weight_carried();
        if( unitweight > 0_gram && unitweight * amount > max_weight ) {
            const int weightmax = max_weight / unitweight;
            if( weightmax <= 0 ) {
                set_workspace_status( _( "This item is too heavy." ) );
                return false;
            }
            amount = std::min( weightmax, amount );
        }
    }
    // handle how many of armor type we can equip (max of 2 per type)
    if( destarea == AIM_WORN ) {
        const itype_id &id = sitem.items.front()->typeId();
        // how many slots are available for the item?
        const int slots_available = id->max_worn - player_character.amount_worn( id );
        // base the amount to equip on amount of slots available
        amount = std::min( slots_available, input_amount );
    }
    // Now we have the final amount. Query if requested or limited room left.
    if( ( action == "MOVE_VARIABLE_ITEM" && input_amount > 1 ) || amount < input_amount ) {
        const int count = by_charges ? it.charges : sitem.stacks;
        const char *msg = nullptr;
        std::string popupmsg;
        if( amount >= input_amount ) {
            msg = _( "How many do you want to move?  [Have %d] (0 to cancel)" );
            popupmsg = string_format( msg, count );
        } else {
            msg = _( "Destination can only hold %d!  Move how many?  [Have %d] (0 to cancel)" );
            popupmsg = string_format( msg, amount, count );
        }
        // At this point amount contains the maximal amount that the destination can hold.
        const int possible_max = std::min( input_amount, amount );
        if( amount <= 0 ) {
            set_workspace_status( _( "The destination is already full." ) );
        } else if( test_mode ) {
            amount = possible_max;
        } else {
            set_workspace_status( popupmsg );
            if( ui ) {
                ui_manager::redraw();
            }
            string_input_popup amount_input;
            amount_input.text( std::to_string( possible_max ) ).only_digits( true ).max_length( 9 );
            amount_input.window( panes[src].window, point( 2, 3 ),
                                 std::max( 3, getmaxx( panes[src].window ) - 3 ) );
            const std::optional<int> requested = amount_input.query_int();
            amount = requested.value_or( 0 );
            log_workspace_event( string_format( "quantity requested=%d maximum=%d item=%s", amount,
                                                possible_max, it.typeId().str() ) );
        }
        if( amount <= 0 ) {
            return false;
        }
        if( amount > possible_max ) {
            amount = possible_max;
        }
    }
    return true;
}

void advanced_inventory::refresh_minimap()
{
    // don't update ui if processing demands
    if( is_processing() ) {
        return;
    }
    // redraw border around minimap
    draw_border( mm_border );
    // minor addition to border for AIM_ALL, sorta hacky
    if( panes[src].get_area() == AIM_ALL || panes[dest].get_area() == AIM_ALL ) {
        // NOLINTNEXTLINE(cata-use-named-point-constants)
        mvwprintz( mm_border, point( 1, 0 ), c_light_gray, utf8_truncate( _( "All" ), minimap_width ) );
    }
    // refresh border, then minimap
    wnoutrefresh( mm_border );
    wnoutrefresh( minimap );
}

void advanced_inventory::draw_minimap()
{
    // if player is in one of the below, invert the player cell
    static const std::array<aim_location, 3> player_locations = {
        {AIM_CENTER, AIM_INVENTORY, AIM_WORN}
    };
    static const std::array<side, NUM_PANES> sides = {{left, right}};
    // get the center of the window
    tripoint pc = {getmaxx( minimap ) / 2, getmaxy( minimap ) / 2, 0};
    Character &player_character = get_player_character();
    // draw the 3x3 tiles centered around player
    get_map().draw( minimap, player_character.pos_bub() );
    for( const side s : sides ) {
        char sym = get_minimap_sym( s );
        if( sym == '\0' ) {
            continue;
        }
        advanced_inv_area sq = squares[panes[s].get_area()];
        tripoint pt = pc + sq.off.raw();
        // invert the color if pointing to the player's position
        nc_color cl = sq.id == AIM_INVENTORY || sq.id == AIM_WORN ?
                      invert_color( c_light_cyan ) : c_light_cyan.blink();
        mvwputch( minimap, pt.xy(), cl, sym );
    }

    // Invert player's tile color if exactly one pane points to player's tile
    bool invert_left = false;
    bool invert_right = false;
    const auto is_selected = [ this ]( const aim_location & where, size_t side ) {
        return where == this->panes[ side ].get_area();
    };
    for( const aim_location &loc : player_locations ) {
        invert_left |= is_selected( loc, 0 );
        invert_right |= is_selected( loc, 1 );
    }

    if( !invert_left || !invert_right ) {
        player_character.draw( minimap, player_character.pos_bub(), invert_left || invert_right );
    }
}

char advanced_inventory::get_minimap_sym( side p ) const
{
    static const std::array<char, NUM_PANES> c_side = {{'L', 'R'}};
    static const std::array<char, NUM_PANES> d_side = {{'^', 'v'}};
    static const std::array<char, NUM_AIM_LOCATIONS> g_nome = {{
            '@', '#', '#', '#', '#', '@', '#',
            '#', '#', '#', 'D', '^', 'C', '@'
        }
    };
    char ch = g_nome[panes[p].get_area()];
    switch( ch ) {
        case '@':
            // '^' or 'v'
            ch = d_side[panes[-p + 1].get_area() == AIM_CENTER];
            break;
        case '#':
            // 'L' or 'R'
            ch = panes[p].in_vehicle() ? 'V' : c_side[p];
            break;
        case '^':
            // do not show anything
            ch ^= ch;
            break;
    }
    return ch;
}

void advanced_inventory::swap_panes()
{
    // Switch left and right pane.
    std::swap( panes[left], panes[right] );
    // Switch save states
    std::swap( panes[left].save_state, panes[right].save_state );
    // Switch currently selected item
    std::swap( panes[left].target_item_after_recalc, panes[right].target_item_after_recalc );
    // Window pointer must be unchanged!
    std::swap( panes[left].window, panes[right].window );
    // Recalculation required for weight & volume
    recalc = true;
}

void advanced_inventory::do_return_entry()
{
    // only save pane settings
    save_settings( true );
    uistate.open_menu = []() {
        create_advanced_inv();
    };
    save_state->exit_code = aim_exit::re_entry;
}

void advanced_inventory::temp_hide()
{
    ui.reset();
    do_return_entry();
    cancel_aim_processing();
}

bool advanced_inventory::is_processing() const
{
    return save_state->re_enter_move_all != aim_entry::START;
}

void cancel_aim_processing()
{
    uistate.transfer_save.re_enter_move_all = aim_entry::START;
    uistate.transfer_save.aim_all_location = AIM_AROUND_BEGIN;
    uistate.transfer_save.exit_code = aim_exit::none;
}
