#include "veh_interact.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <climits>
#include <cstdlib>
#include <functional>
#include <initializer_list>
#include <iterator>
#include <list>
#include <memory>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <unordered_set>
#include <utility>

#include "activity_handlers.h"
#include "avatar.h"
#include "calendar.h"
#include "cata_scope_helpers.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "character.h"
#include "character_id.h"
#include "contents_change_handler.h"
#include "crafting.h"
#include "creature_tracker.h"
#include "debug.h"
#include "enums.h"
#include "faction.h"
#include "fault.h"
#include "flag.h"
#include "game.h"
#include "game_constants.h"
#include "handle_liquid.h"
#include "inventory.h"
#include "item.h"
#include "item_group.h"
#include "itype.h"
#include "line.h"
#include "localized_comparator.h"
#include "map.h"
#include "map_selector.h"
#include "mapdata.h"
#include "memory_fast.h"
#include "messages.h"
#include "monster.h"
#include "npc.h"
#include "output.h"
#include "overmapbuffer.h"
#include "pimpl.h"
#include "point.h"
#include "proficiency.h"
#include "requirements.h"
#include "ret_val.h"
#include "rng.h"
#include "skill.h"
#if defined(TILES)
#include "sdl_utils.h"
#include "sdltiles.h"
#endif
#include "string_formatter.h"
#include "string_input_popup.h"
#include "tileray.h"
#include "translation.h"
#include "translations.h"
#include "uilist.h"
#include "ui_manager.h"
#include "units.h"
#include "units_utility.h"
#include "value_ptr.h"
#include "veh_shape.h"
#include "veh_type.h"
#include "veh_utils.h"
#include "vehicle.h"
#include "vehicle_selector.h"
#include "vpart_position.h"
#include "vpart_range.h"

static const activity_id ACT_VEHICLE( "ACT_VEHICLE" );

static const ammotype ammo_battery( "battery" );

static const faction_id faction_no_faction( "no_faction" );

static const itype_id fuel_type_battery( "battery" );
static const itype_id itype_battery( "battery" );
static const itype_id itype_plut_cell( "plut_cell" );

static const proficiency_id proficiency_prof_aircraft_mechanic( "prof_aircraft_mechanic" );

static const quality_id qual_HOSE( "HOSE" );
static const quality_id qual_JACK( "JACK" );
static const quality_id qual_LIFT( "LIFT" );
static const quality_id qual_SELF_JACK( "SELF_JACK" );

static const skill_id skill_mechanics( "mechanics" );

static const trait_id trait_BADBACK( "BADBACK" );
static const trait_id trait_DEBUG_HS( "DEBUG_HS" );
static const trait_id trait_STRONGBACK( "STRONGBACK" );

static const vpart_id vpart_ap_wall_wiring( "ap_wall_wiring" );

static std::string status_color( bool status )
{
    return status ? "<color_green>" : "<color_red>";
}
static std::string health_color( bool status )
{
    return status ? "<color_light_green>" : "<color_light_red>";
}

// Cap JACK requirements to support arbitrarily large vehicles.
static constexpr units::mass JACK_LIMIT = 8500_kilogram; // 8500kg ( 8.5 metric tonnes )

// cap JACK requirements to support arbitrarily large vehicles
static double jack_quality( map &here, const vehicle &veh )
{
    const units::quantity<double, units::mass::unit_type> mass = std::min( veh.total_mass( here ),
            JACK_LIMIT );
    return std::ceil( mass / lifting_quality_to_mass( 1 ) );
}

/** Can part currently be reloaded with anything? */
static auto can_refill = []( const map &, const vehicle_part &pt )
{
    return pt.can_reload( );
};

static void act_vehicle_unload_fuel( map &here, vehicle *veh );

// Development-only vehicle editor hammerspace.  The workflow
// .github/workflows/toggle-vehicle-editor-test-mode.yml flips only this constant.
static constexpr bool vehicle_editor_test_mode_visible = true;
static bool vehicle_editor_test_mode_latched = false;
// Keep the selected viewport through ACT_VEHICLE handoffs/re-entry during this
// game session, just like the editor test-mode latch.
static int vehicle_editor_view_mode_latched = 0;

player_activity veh_interact::serialize_activity( map &here )
{
    const vehicle_part *pt = sel_vehicle_part;
    const vpart_info *vp = sel_vpart_info;

    if( sel_cmd == 'p' ) {
        if( !parts_here.empty() ) {
            const vpart_reference part_here( *veh, parts_here[0] );
            const vpart_reference displayed_part( *veh, veh->part_displayed_at( part_here.mount_pos() ) );
            return veh_shape( here, *veh ).start( displayed_part.pos_bub( here ) );
        }
        return player_activity();
    }

    if( sel_cmd == 'q' || sel_cmd == ' ' || !vp ) {
        return player_activity();
    }

    avatar &player_character = get_avatar();
    time_duration time = 0_seconds;
    switch( sel_cmd ) {
        case 'i':
            time = vp->install_time( player_character );
            break;
        case 'r':
            if( pt != nullptr ) {
                if( pt->is_broken() ) {
                    time = vp->install_time( player_character );
                } else if( pt->is_repairable() ) {
                    time = vp->repair_time( player_character ) * pt->base.repairable_levels();
                }
            }
            break;
        case 'o':
            time = vp->removal_time( player_character );
            break;
        case 'f':
            if( !refill_part_indices.empty() ) {
                time = time_duration::from_turns(
                           std::max( 0, static_cast<int>( refill_part_indices.size() ) - 1 ) );
            }
            break;
        default:
            break;
    }
    // Refueling keeps normal turn accounting even in Vehicle Editor Test mode:
    // the initial action consumes one turn and every additional transfer is one
    // more ACT_VEHICLE turn.  Other editor test operations retain fast timing.
    if( sel_cmd != 'f' && ( player_character.has_trait( trait_DEBUG_HS ) || editor_test_mode ) ) {
        time = 1_seconds;
    }
    player_activity res( ACT_VEHICLE, to_moves<int>( time ), static_cast<int>( sel_cmd ) );

    // if we're working on an existing part, use that part as the reference point
    // otherwise (e.g. installing a new frame), just use part 0
    const point_rel_ms q = veh->coord_translate( pt ? pt->mount : veh->part( 0 ).mount );
    const vehicle_part *vpt = pt ? pt : &veh->part( 0 );
    for( const tripoint_abs_ms &p : veh->get_points( true ) ) {
        res.coord_set.insert( p );
    }
    res.values.push_back( veh->pos_abs().x() + q.x() );   // values[0]
    res.values.push_back( veh->pos_abs().y() + q.y() );   // values[1]
    res.values.push_back( dd.x() );   // values[2]
    res.values.push_back( dd.y() );   // values[3]
    res.values.push_back( -dd.x() );   // values[4]
    res.values.push_back( -dd.y() );   // values[5]
    const int primary_part_index = sel_cmd == 'f' && !refill_part_indices.empty() ?
                                   refill_part_indices.front() : veh->index_of_part( vpt );
    res.values.push_back( primary_part_index ); // values[6]
    if( sel_cmd == 'f' && refill_part_indices.size() > 1 ) {
        for( size_t i = 1; i < refill_part_indices.size(); ++i ) {
            res.values.push_back( refill_part_indices[i] );
        }
    }
    res.str_values.emplace_back( vp->id.str() );
    res.str_values.emplace_back( editor_test_mode ? "vehicle_editor_test" : "" );
    res.str_values.emplace_back( sel_cmd == 'f' && !refill_part_indices.empty() ?
                                 "vehicle_refill_batch" : "" );
    if( sel_cmd == 'f' && !refill_targets.empty() ) {
        for( item_location &target : refill_targets ) {
            res.targets.emplace_back( std::move( target ) );
        }
    } else {
        res.targets.emplace_back( std::move( refill_target ) );
    }

    return res;
}

void orient_part( map &here, vehicle *veh, const vpart_info &vpinfo, int partnum,
                  const std::optional<point_rel_ms> &part_placement )
{
    avatar &player_character = get_avatar();
    // Stash offset and set it to the location of the part so look_around will
    // start there.
    const tripoint_rel_ms old_view_offset = player_character.view_offset;
    tripoint_bub_ms offset = veh->pos_bub( here );
    // Appliances are one tile so the part placement there is always point::zero
    if( part_placement ) {
        point_rel_ms copied_placement = *part_placement;
        offset = offset + copied_placement;
    }
    player_character.view_offset = offset - player_character.pos_bub( here );

    point_rel_ms delta;
    do {
        popup( _( "Press space, choose a facing direction for the new %s and "
                  "confirm with enter." ),
               vpinfo.name() );

        const std::optional<tripoint_bub_ms> chosen = g->look_around();
        if( !chosen ) {
            continue;
        }
        delta = ( *chosen - offset ).xy();
        // atan2 only gives reasonable values when delta is not all zero
    } while( delta == point_rel_ms::zero );

    // Restore previous view offsets.
    player_character.view_offset = old_view_offset;

    units::angle dir = normalize( atan2( delta.raw() ) - veh->face.dir() );

    veh->part( partnum ).direction = dir;
}

player_activity veh_interact::run( map &here, vehicle &veh, const point_rel_ms &p )
{
    veh_interact vehint( here, veh, p );
    vehint.do_main_loop( here );
    return vehint.serialize_activity( here );
}

std::optional<vpart_reference> veh_interact::select_part( map &here, const vehicle &veh,
        const part_selector &sel, const std::string &title )
{
    std::optional<vpart_reference> res = std::nullopt;
    const auto act = [&]( const map &, const vehicle_part & pt ) {
        res = vpart_reference( const_cast<vehicle &>( veh ), veh.index_of_part( &pt ) );
    };
    std::function<bool( const vpart_reference & )> sel_wrapper = [sel,
    &here]( const vpart_reference & vpr ) {
        return sel( here, vpr.part() );
    };

    const vehicle_part_range vpr = veh.get_all_parts();
    int opts = std::count_if( vpr.begin(), vpr.end(), sel_wrapper );

    if( opts == 1 ) {
        act( here, std::find_if( vpr.begin(), vpr.end(), sel_wrapper )->part() );

    } else if( opts != 0 ) {
        veh_interact vehint( here, const_cast<vehicle &>( veh ) );
        vehint.title = title.empty() ? _( "Select part" ) : title;
        vehint.overview( here, sel, act );
    }

    return res;
}

/**
 * Creates a blank veh_interact window.
 */
veh_interact::veh_interact( map &here, vehicle &veh, const point_rel_ms &p )
    : dd( p ), veh( &veh ), main_context( "VEH_INTERACT", keyboard_mode::keycode )
{
    main_context.register_directions();
    main_context.register_action( "QUIT" );
    main_context.register_action( "INSTALL" );
    main_context.register_action( "REPAIR" );
    main_context.register_action( "MEND" );
    main_context.register_action( "REFILL" );
    main_context.register_action( "REMOVE" );
    main_context.register_action( "RENAME" );
    main_context.register_action( "SIPHON" );
    main_context.register_action( "UNLOAD" );
    main_context.register_action( "CHANGE_SHAPE" );
    main_context.register_action( "ASSIGN_CREW" );
    main_context.register_action( "RELABEL" );
    main_context.register_action( "PREV_TAB" );
    main_context.register_action( "NEXT_TAB" );
    main_context.register_action( "OVERVIEW_DOWN" );
    main_context.register_action( "OVERVIEW_UP" );
    main_context.register_action( "FUEL_LIST_DOWN" );
    main_context.register_action( "FUEL_LIST_UP" );
    main_context.register_action( "DESC_LIST_DOWN" );
    main_context.register_action( "DESC_LIST_UP" );
    main_context.register_action( "PAGE_DOWN" );
    main_context.register_action( "PAGE_UP" );
    main_context.register_action( "CONFIRM" );
    main_context.register_action( "HELP_KEYBINDINGS" );
    main_context.register_action( "FILTER" );
    main_context.register_action( "SELECT" );
    main_context.register_action( "SEC_SELECT" );
    main_context.register_action( "MOUSE_MOVE" );
    main_context.register_action( "SCROLL_UP" );
    main_context.register_action( "SCROLL_DOWN" );
    main_context.register_action( "CAMERA_PAN_START" );
    main_context.register_action( "CAMERA_PAN_END" );
    main_context.register_action( "ANY_INPUT" );

    editor_test_mode = vehicle_editor_test_mode_visible && vehicle_editor_test_mode_latched;
    if( !vehicle_editor_test_mode_visible ) {
        vehicle_editor_test_mode_latched = false;
    }
    active_editor_view_mode = static_cast<editor_view_mode>(
                                  std::clamp( vehicle_editor_view_mode_latched, 0, 2 ) );

    count_durability();
    cache_tool_availability();
    // Initialize command-side info and the independent editor selection.
    move_cursor( here, point_rel_ms::zero );
    center_viewport_on_vehicle();
    reset_part_selection();
}

veh_interact::~veh_interact()
{
#if defined(TILES)
    clear_map_preview_window();
    set_sdl_mouse_capture( false );
#endif
}

void veh_interact::allocate_windows()
{
#if defined(TILES)
    // Window objects are replaced below; never leave the SDL preview registry
    // pointing at an old curses window across a resize.
    clear_map_preview_window();
#endif
    const point grid( point::south_east );
    const int grid_w = TERMX - 2;
    const int grid_h = TERMY - 2;

    const int mode_h = 1;
    const int name_h = 1;

    page_size = grid_h - ( mode_h + stats_h + name_h ) - 2;
    const int pane_y = grid.y + mode_h + 1;

    // The vehicle grid is the primary surface.  Keep roughly 70% for it on normal
    // desktop widths while retaining a usable inspector on smaller terminals.
    pane_w = std::clamp( grid_w * 28 / 100, 24, std::max( 24, grid_w / 2 ) );
    disp_w = grid_w - pane_w - 1;

    const int inspector_top_h = std::clamp( page_size * 45 / 100, 5,
                                           std::max( 5, page_size - 5 ) );
    const int inspector_split_y = pane_y + inspector_top_h;
    const int inspector_bottom_y = inspector_split_y + 1;
    const int inspector_bottom_h = std::max( 1, page_size - inspector_top_h - 1 );
    const int inspector_x = grid.x + disp_w + 1;

    const int name_y = pane_y + page_size + 1;
    const int stats_y = name_y + name_h;

    const int left_stats_w = std::max( 10, disp_w / 2 );
    const int right_stats_w = std::max( 1, disp_w - left_stats_w - 1 );

    w_border = catacurses::newwin( TERMY, TERMX, point::zero );
    w_mode = catacurses::newwin( mode_h, grid_w, grid );
    w_disp = catacurses::newwin( page_size, disp_w, point( grid.x, pane_y ) );
#if defined(TILES)
    const int content_top = editor_viewport_top();
    const int preview_h = std::max( 1, page_size - content_top );
    const int split_left_w = std::max( 1, ( disp_w - 1 ) / 2 );
    const int split_preview_x = split_left_w + 1;
    const int split_preview_w = std::max( 1, disp_w - split_preview_x );
    w_live_preview_full = catacurses::newwin( preview_h, disp_w,
                          point( grid.x, pane_y + content_top ) );
    w_live_preview_split = catacurses::newwin( preview_h, split_preview_w,
                           point( grid.x + split_preview_x, pane_y + content_top ) );
#endif

    // Base editor inspector.  Command modes reuse the same two right-side regions.
    w_parts = catacurses::newwin( inspector_top_h, pane_w, point( inspector_x, pane_y ) );
    w_list = catacurses::newwin( inspector_top_h, pane_w, point( inspector_x, pane_y ) );
    w_msg = catacurses::newwin( inspector_bottom_h, pane_w,
                                point( inspector_x, inspector_bottom_y ) );

    w_name = catacurses::newwin( name_h, grid_w, point( grid.x, name_y ) );

    // Refueling is a short transactional workflow, not a replacement editor.
    // Keep it as a compact centered modal over the normal vehicle editor.
    const int refuel_overlay_w = std::min( grid_w, std::clamp( grid_w * 55 / 100, 36, 64 ) );
    const int refuel_overlay_h = std::min( page_size, std::clamp( page_size - 2, 12, 20 ) );
    w_refuel_overlay = catacurses::newwin( refuel_overlay_h, refuel_overlay_w,
                       point( grid.x + std::max( 0, ( grid_w - refuel_overlay_w ) / 2 ),
                              pane_y + std::max( 0, ( page_size - refuel_overlay_h ) / 2 ) ) );

    // Existing install/remove details continue to occupy the lower-right stats area.
    w_details = catacurses::newwin( stats_h, pane_w, point( inspector_x, stats_y ) );
    w_stats_1 = catacurses::newwin( stats_h, left_stats_w,
                                    point( grid.x + 1, stats_y ) );
    w_stats_2 = catacurses::newwin( stats_h, right_stats_w,
                                    point( grid.x + left_stats_w + 2, stats_y ) );
    w_stats_3 = catacurses::newwin( stats_h, std::max( 1, pane_w - 2 ),
                                    point( inspector_x + 1, stats_y ) );
}

bool veh_interact::format_reqs( std::string &msg, const requirement_data &reqs,
                                const std::map<skill_id, int> &skills, time_duration time ) const
{
    Character &player_character = get_player_character();
    const inventory &inv = player_character.crafting_inventory();
    const bool resources_available = reqs.can_make_with_inventory( inv, is_crafting_component, 1,
                                     craft_flags::none, false );
    bool ok = editor_test_mode || resources_available;

    if( editor_test_mode ) {
        msg += _( "<color_light_cyan>Test mode: components, tools, and skill requirements are ignored.</color>\n" );
    }
    msg += _( "<color_white>Time required:</color>\n" );
    msg += "> " + to_string_approx( time ) + "\n";

    msg += _( "<color_white>Skills required:</color>\n" );
    for( const auto &e : skills ) {
        const bool has_skill = player_character.get_knowledge_level( e.first ) >= e.second;
        const bool requirement_met = editor_test_mode || has_skill;
        if( !requirement_met ) {
            ok = false;
        }
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
        msg += string_format( _( "> %1$s%2$s %3$i</color>\n" ), status_color( requirement_met ),
                              e.first.obj().name(), e.second );
    }
    if( skills.empty() ) {
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is the word "NONE"
        msg += string_format( "> %1$s%2$s</color>", status_color( true ), _( "NONE" ) ) + "\n";
    }

    auto comps = reqs.get_folded_components_list( getmaxx( w_msg ) - 2, c_white, inv,
                 is_crafting_component );
    for( const std::string &line : comps ) {
        msg += line + "\n";
    }
    auto tools = reqs.get_folded_tools_list( getmaxx( w_msg ) - 2, c_white, inv );
    for( const std::string &line : tools ) {
        msg += line + "\n";
    }

    return ok;
}

struct veh_interact::install_info_t {
    int pos = 0;
    std::vector<const vpart_info *> tab_vparts;
    std::string filter;
    bool available_materials_only = false;
    bool show_all = false;
    bool dirty = true;
    bool selected_can_install = false;
    std::map<std::string, bool> materials_available;
    std::string last_clicked_part;
    std::optional<std::chrono::steady_clock::time_point> last_click_time;
};

struct veh_interact::remove_info_t {
    int pos = 0;
    size_t tab = 0;
};

struct veh_interact::refuel_info_t {
    enum class stage_t {
        tank,
        source,
        quick_fuel
    };

    struct source_t {
        item_location location;
        std::string label;
        bool selected = false;
    };

    stage_t stage = stage_t::tank;
    std::vector<int> tanks;
    int tank_pos = 0;
    int tank_scroll = 0;
    int selected_tank_slot = -1;

    std::vector<source_t> sources;
    int source_pos = 0;
    int source_scroll = 0;
    int source_range_anchor = -1;
    item_location last_clicked_source;
    std::optional<std::chrono::steady_clock::time_point> last_source_click_time;

    std::vector<itype_id> quick_fuels;
    int quick_fuel_pos = 0;
    int quick_fuel_scroll = 0;
};

shared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor( map &here )
{
    shared_ptr_fast<ui_adaptor> current_ui = ui.lock();
    if( !current_ui ) {
        ui = current_ui = make_shared_fast<ui_adaptor>();
        current_ui->on_screen_resize( [this]( ui_adaptor & current_ui ) {
            if( ui_hidden ) {
                current_ui.position( point::zero, point::zero );
                return;
            }
            allocate_windows();
            current_ui.position_from_window( catacurses::stdscr );
        } );
        current_ui->mark_resize();
        current_ui->on_redraw( [&here, this]( const ui_adaptor & ) {
            if( ui_hidden ) {
                return;
            }
            display_grid();
            display_name();
            display_stats( here );
            display_veh( here );
            if( refuel_info ) {
                // Preserve the regular editor behind the compact modal.
                display_part_inspector();
                display_part_details();
                display_refuel_pane( here );
                display_mode( here );
#if defined(TILES)
                // SDL map previews are outside curses window ordering and can
                // otherwise draw over the modal.
                clear_map_preview_window();
#endif
                return;
            }

            const auto draw_message_window = [&]() {
                werase( w_msg );
                if( !msg.has_value() ) {
                    veh->print_vparts_descs( w_msg, getmaxy( w_msg ), getmaxx( w_msg ), cpart,
                                             start_at, start_limit );
                } else {
                    const int height = catacurses::getmaxy( w_msg );
                    const int width = catacurses::getmaxx( w_msg ) - 2;
                    std::vector<std::string> buffer;
                    std::istringstream msg_stream( msg.value() );
                    while( !msg_stream.eof() ) {
                        std::string line;
                        getline( msg_stream, line );
                        if( utf8_width( line ) <= width ) {
                            buffer.emplace_back( line );
                        } else {
                            std::vector<std::string> folded = foldstring( line, width );
                            std::copy( folded.begin(), folded.end(), std::back_inserter( buffer ) );
                        }
                    }
                    const int page_height = std::max( 1, height - 1 );
                    const int pages = static_cast<int>( buffer.size() / page_height );
                    w_msg_scroll_offset = clamp( w_msg_scroll_offset, 0, pages );
                    for( int line = 0; line < height; ++line ) {
                        const int idx = w_msg_scroll_offset * page_height + line;
                        if( static_cast<size_t>( idx ) >= buffer.size() ) {
                            break;
                        }
                        nc_color dummy = c_unset;
                        print_colored_text( w_msg, point( 1, line ), dummy, c_unset, buffer[idx] );
                    }
                }
                wnoutrefresh( w_msg );
            };

            if( !install_info && !remove_info ) {
                display_part_inspector();
                if( msg.has_value() ) {
                    draw_message_window();
                } else {
                    display_part_details();
                }
            } else {
                werase( w_parts );
                wnoutrefresh( w_parts );
                draw_message_window();

                if( install_info ) {
                    display_list( install_info->pos, install_info->tab_vparts, 2 );
                    display_details( sel_vpart_info );
                } else {
                    display_details( sel_vpart_info );
                    display_overview( here );
                }
            }
            display_editor_context_menu();
            display_mode( here );
            display_live_preview( here );
        } );
    }
    return current_ui;
}

void veh_interact::hide_ui( map &here, const bool hide )
{
    if( hide != ui_hidden ) {
        ui_hidden = hide;
        create_or_get_ui_adaptor( here )->mark_resize();
    }
}

void veh_interact::do_main_loop( map &here )
{
    bool finish = false;
    Character &player_character = get_player_character();
    const bool owned_by_player = veh->handle_potential_theft( player_character, true );
    faction *owner_fac;
    if( veh->has_owner() ) {
        owner_fac = g->faction_manager_ptr->get( veh->get_owner() );
    } else {
        owner_fac = g->faction_manager_ptr->get( faction_no_faction );
    }

    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );

    while( !finish ) {
        calc_overview( here );
        if( install_info ) {
            refresh_install_candidates();
            sync_install_selection( here );
        }
        ui_manager::redraw();
        const int description_scroll_lines = std::max( 1, catacurses::getmaxy( w_msg ) - 4 );
        std::string action = main_context.handle_input();

        const bool mouse_handled = handle_editor_mouse( here, action );
        if( !pending_editor_action.empty() ) {
            action = pending_editor_action;
            pending_editor_action.clear();
        } else if( mouse_handled ) {
            if( sel_cmd != ' ' ) {
                finish = true;
            }
            continue;
        }

        if( refuel_info ) {
            using refuel_stage = refuel_info_t::stage_t;
            if( action == "QUIT" ) {
                // QUIT/Esc is Cancel for the entire transactional refuel workflow.
                // The explicit Back button is what returns to the tank-selection stage.
                close_refuel_mode();
                continue;
            }

            if( action == "UP" || action == "DOWN" ||
                action == "PAGE_UP" || action == "PAGE_DOWN" ) {
                const int page = std::max( 1, getmaxy( w_refuel_overlay ) - 8 );
                const int delta = action == "UP" ? -1 : action == "DOWN" ? 1 :
                                  action == "PAGE_UP" ? -page : page;
                if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {
                    refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,
                                            static_cast<int>( refuel_info->tanks.size() ) - 1 );
                } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {
                    refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,
                                              static_cast<int>( refuel_info->sources.size() ) - 1 );
                } else if( refuel_info->stage == refuel_stage::quick_fuel &&
                           !refuel_info->quick_fuels.empty() ) {
                    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,
                                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
                }
                continue;
            }

            if( action == "REFILL" || action == "CONFIRM" ) {
                if( refuel_info->stage == refuel_stage::tank ) {
                    if( !refuel_info->tanks.empty() ) {
                        refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,
                                                static_cast<int>( refuel_info->tanks.size() ) - 1 );
                        const int part_index = refuel_info->tanks[refuel_info->tank_pos];
                        if( part_index >= 0 && part_index < veh->part_count() &&
                            veh->part( part_index ).can_reload() ) {
                            refuel_info->selected_tank_slot = refuel_info->tank_pos;
                            refuel_info->stage = refuel_stage::source;
                            refuel_info->source_pos = 0;
                            refuel_info->source_range_anchor = -1;
                            refresh_refuel_sources( here );
                        } else {
                            msg = _( "That fuel store is already full or cannot currently be refilled." );
                        }
                    }
                } else if( refuel_info->stage == refuel_stage::source ) {
                    const bool any_selected = std::any_of( refuel_info->sources.begin(),
                                              refuel_info->sources.end(),
                    []( const refuel_info_t::source_t &entry ) {
                        return entry.selected;
                    } );
                    if( !any_selected && !refuel_info->sources.empty() ) {
                        refuel_info->sources[refuel_info->source_pos].selected = true;
                    }
                    if( queue_selected_refill_source( here ) ) {
                        finish = true;
                    }
                } else if( queue_quick_refill_all( here ) ) {
                    finish = true;
                }
                continue;
            }

            // Refuel modal consumes unrelated editor/navigation input rather than
            // moving the vehicle mount behind it.
            continue;
        } else if( install_info ) {
            if( action == "QUIT" ) {
                close_install_mode();
                continue;
            }
            if( action == "FILTER" ) {
                string_input_popup()
                .title( _( "Search installable parts" ) )
                .width( 50 )
                .description( _( "Search" ) )
                .max_length( 100 )
                .edit( install_info->filter );
                install_search_cache = install_info->filter;
                install_info->pos = 0;
                install_info->dirty = true;
                refresh_install_candidates();
                sync_install_selection( here );
                continue;
            }
            if( action == "INSTALL" || action == "CONFIRM" ) {
                if( confirm_install( here ) ) {
                    finish = true;
                }
                continue;
            }
            if( action == "UP" || action == "DOWN" || action == "PAGE_UP" || action == "PAGE_DOWN" ) {
                if( !install_info->tab_vparts.empty() ) {
                    const int old_pos = install_info->pos;
                    if( action == "UP" ) {
                        install_info->pos = std::max( 0, install_info->pos - 1 );
                    } else if( action == "DOWN" ) {
                        install_info->pos = std::min(
                                                static_cast<int>( install_info->tab_vparts.size() ) - 1,
                                                install_info->pos + 1 );
                    } else {
                        const int page = std::max( 1, getmaxy( w_list ) - 4 );
                        const int delta = action == "PAGE_UP" ? -page : page;
                        install_info->pos = std::clamp(
                                                install_info->pos + delta, 0,
                                                static_cast<int>( install_info->tab_vparts.size() ) - 1 );
                    }
                    if( install_info->pos != old_pos ) {
                        sync_install_selection( here );
                    }
                }
                continue;
            }
            if( action == "DESC_LIST_DOWN" ) {
                ++w_msg_scroll_offset;
                continue;
            }
            if( action == "DESC_LIST_UP" ) {
                w_msg_scroll_offset = std::max( 0, w_msg_scroll_offset - 1 );
                continue;
            }
        } else {
            msg.reset();
        }

        if( const std::optional<tripoint_rel_ms> vec = main_context.get_direction_rel_ms( action ) ) {
            move_cursor( here, vec->xy() );
        } else if( action == "QUIT" ) {
            finish = true;
        } else if( action == "INSTALL" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_install( here );
            }
        } else if( action == "REPAIR" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_repair( here );
            }
        } else if( action == "MEND" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_mend( here );
            }
        } else if( action == "REFILL" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_refill( here );
            }
        } else if( action == "REMOVE" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_remove( here );
            }
        } else if( action == "RENAME" ) {
            if( owned_by_player ) {
                do_rename();
            } else if( owner_fac ) {
                popup( _( "You cannot rename this vehicle as it is owned by: %s." ), _( owner_fac->name ) );
            }
        } else if( action == "SIPHON" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                do_siphon( here );
                finish = !player_character.activity.is_null();
                if( !finish ) {
                    cache_tool_availability();
                }
            }
        } else if( action == "UNLOAD" ) {
            if( veh->handle_potential_theft( player_character ) ) {
                finish = do_unload( here );
            }
        } else if( action == "CHANGE_SHAPE" ) {
            sel_cmd = 'p';
        } else if( action == "ASSIGN_CREW" ) {
            if( owned_by_player ) {
                do_assign_crew( here );
            } else if( owner_fac ) {
                popup( _( "You cannot assign crew on this vehicle as it is owned by: %s." ),
                       _( owner_fac->name ) );
            }
        } else if( action == "RELABEL" ) {
            if( owned_by_player ) {
                do_relabel( here );
            } else if( owner_fac ) {
                popup( _( "You cannot relabel this vehicle as it is owned by: %s." ), _( owner_fac->name ) );
            }
        } else if( action == "FUEL_LIST_DOWN" ) {
            move_fuel_cursor( here, 1 );
        } else if( action == "FUEL_LIST_UP" ) {
            move_fuel_cursor( here, -1 );
        } else if( action == "OVERVIEW_DOWN" ) {
            move_overview_line( 1 );
        } else if( action == "OVERVIEW_UP" ) {
            move_overview_line( -1 );
        } else if( action == "DESC_LIST_DOWN" ) {
            if( !remove_info ) {
                scroll_part_details( 1 );
            } else {
                move_cursor( here, point_rel_ms::zero, 1 );
            }
        } else if( action == "DESC_LIST_UP" ) {
            if( !remove_info ) {
                scroll_part_details( -1 );
            } else {
                move_cursor( here, point_rel_ms::zero, -1 );
            }
        } else if( action == "PAGE_DOWN" ) {
            if( !remove_info ) {
                scroll_part_details( description_scroll_lines );
            } else {
                move_cursor( here, point_rel_ms::zero, description_scroll_lines );
            }
        } else if( action == "PAGE_UP" ) {
            if( !remove_info ) {
                scroll_part_details( -description_scroll_lines );
            } else {
                move_cursor( here, point_rel_ms::zero, -description_scroll_lines );
            }
        }
        if( sel_cmd != ' ' ) {
            finish = true;
        }
    }
}

void veh_interact::cache_tool_availability()
{
    map &here = get_map();

    Character &player_character = get_player_character();
    crafting_inv = &player_character.crafting_inventory();

    cache_tool_availability_update_lifting( player_character.pos_bub() );
    int mech_jack = 0;
    if( player_character.is_mounted() ) {
        mech_jack = player_character.mounted_creature->mech_str_addition() + 10;
    }
    int max_quality = std::max( { player_character.max_quality( qual_JACK ), mech_jack,
                                  map_selector( player_character.pos_bub(), PICKUP_RANGE ).max_quality( qual_JACK ),
                                  vehicle_selector( here, player_character.pos_bub(), 2, true, *veh ).max_quality( qual_JACK )
                                } );
    max_jack = lifting_quality_to_mass( max_quality );
}

void veh_interact::cache_tool_availability_update_lifting( const tripoint_bub_ms &world_cursor_pos )
{
    max_lift = get_player_character().best_nearby_lifting_assist( world_cursor_pos );
}

/**
 * Checks if the player is able to perform some command, and returns a nonzero
 * error code if they are unable to perform it. The return from this function
 * should be passed into the various do_whatever functions further down.
 * @param mode The command the player is trying to perform (i.e. 'r' for repair).
 * @return CAN_DO if the player has everything they need,
 *         INVALID_TARGET if the command can't target that square,
 *         LACK_TOOLS if the player lacks tools,
 *         NOT_FREE if something else obstructs the action,
 *         LACK_SKILL if the player's skill isn't high enough,
 *         LOW_MORALE if the player's morale is too low while trying to perform
 *             an action requiring a minimum morale,
 *         UNKNOWN_TASK if the requested operation is unrecognized.
 */
task_reason veh_interact::cant_do( const map &here,  char mode )
{
    bool enough_morale = true;
    bool valid_target = false;
    bool has_tools = false;
    bool part_free = true;
    bool has_skill = true;
    bool enough_light = true;
    const vehicle_part_range vpr = veh->get_all_parts();
    avatar &player_character = get_avatar();
    switch( mode ) {
        case 'i':
            // install mode
            enough_morale = player_character.has_morale_to_craft();
            valid_target = !can_mount.empty();
            //tool checks processed later
            enough_light = player_character.fine_detail_vision_mod() <= 4;
            has_tools = true;
            break;

        case 'r':
            // repair mode
            enough_morale = player_character.has_morale_to_craft();
            valid_target = !need_repair.empty() && cpart >= 0;
            // checked later
            has_tools = true;
            enough_light = player_character.fine_detail_vision_mod() <= 4;
            break;

        case 'm': {
            // mend mode
            enough_morale = player_character.has_morale_to_craft();
            const bool toggling = player_character.has_trait( trait_DEBUG_HS );
            valid_target = std::any_of( vpr.begin(), vpr.end(), [toggling]( const vpart_reference & pt ) {
                if( toggling ) {
                    return pt.part().is_available() && !pt.part().faults_potential().empty();
                } else {
                    return pt.part().is_available() && !pt.part().faults().empty();
                }
            } );
            enough_light = player_character.fine_detail_vision_mod() <= 4;
            // checked later
            has_tools = true;
        }
        break;

        case 'f':
            valid_target = std::any_of( vpr.begin(), vpr.end(), [&here]( const vpart_reference & pt ) {
                return can_refill( here, pt.part() );
            } );
            has_tools = true;
            break;

        case 'o':
            // remove mode
            enough_morale = player_character.has_morale_to_craft();
            valid_target = cpart >= 0;
            part_free = parts_here.size() > 1 ||
                        ( cpart >= 0 && veh->can_unmount( veh->part( cpart ) ).success() );
            //tool and skill checks processed later
            has_tools = true;
            has_skill = true;
            enough_light = player_character.fine_detail_vision_mod() <= 4;
            break;

        case 's':
            // siphon mode
            valid_target = false;
            for( const vpart_reference &vp : veh->get_any_parts( VPFLAG_FLUIDTANK ) ) {
                if( vp.part().base.has_item_with( []( const item & it ) {
                return it.made_of( phase_id::LIQUID );
                } ) ) {
                    valid_target = true;
                    break;
                }
            }
            has_tools = player_character.crafting_inventory( false ).has_quality( qual_HOSE );
            break;

        case 'd':
            // unload mode
            valid_target = false;
            has_tools = true;
            for( auto &e : veh->fuels_left( ) ) {
                if( e.first != fuel_type_battery && item::find_type( e.first )->phase == phase_id::SOLID ) {
                    valid_target = true;
                    break;
                }
            }
            break;

        case 'w':
            // assign crew
            if( g->allies().empty() ) {
                return task_reason::INVALID_TARGET;
            }
            return std::any_of( vpr.begin(), vpr.end(), []( const vpart_reference & e ) {
                return e.part().is_seat();
            } ) ? task_reason::CAN_DO : task_reason::INVALID_TARGET;

        case 'p':
        // change part shape
        // intentional fall-through
        case 'a':
            // relabel
            valid_target = cpart >= 0;
            has_tools = true;
            break;
        default:
            return task_reason::UNKNOWN_TASK;
    }

    if( std::abs( veh->velocity ) > 100 || player_character.controlling_vehicle ) {
        return task_reason::MOVING_VEHICLE;
    }
    if( !valid_target ) {
        return task_reason::INVALID_TARGET;
    }
    if( !enough_morale ) {
        return task_reason::LOW_MORALE;
    }
    if( !enough_light ) {
        return task_reason::LOW_LIGHT;
    }
    if( !has_tools ) {
        return task_reason::LACK_TOOLS;
    }
    if( !part_free ) {
        return task_reason::NOT_FREE;
    }
    // TODO: that is always false!
    if( !has_skill ) {
        return task_reason::LACK_SKILL;
    }
    return task_reason::CAN_DO;
}

bool veh_interact::can_self_jack( map &here )
{
    int lvl = jack_quality( here, *veh );

    for( const vpart_reference &vp : veh->get_avail_parts( "SELF_JACK" ) ) {
        if( vp.part().base.has_quality( qual_SELF_JACK, lvl ) ) {
            return true;
        }
    }
    return false;
}

bool veh_interact::update_part_requirements( map &here )
{
    if( sel_vpart_info == nullptr ) {
        return false;
    }

    if( std::any_of( parts_here.begin(), parts_here.end(), [&]( const int e ) {
    return veh->part( e ).has_flag( vp_flag::carried_flag );
    } ) ) {
        msg = _( "Unracking is required before installing any parts here." );
        return false;
    }

    if( const std::optional<std::string> conflict = veh->has_engine_conflict( *sel_vpart_info ) ) {
        //~ %1$s is fuel_type
        msg = string_format( _( "Only one %1$s powered engine can be installed." ), conflict.value() );
        return false;
    }
    if( veh->has_part( "NO_MODIFY_VEHICLE" ) && !sel_vpart_info->has_flag( "SIMPLE_PART" ) ) {
        msg = _( "This vehicle cannot be modified in this way.\n" );
        return false;
    } else if( sel_vpart_info->has_flag( "NO_INSTALL_PLAYER" ) ) {
        msg = _( "This part cannot be installed.\n" );
        return false;
    }

    if( sel_vpart_info->has_flag( "FUNNEL" ) ) {
        if( std::none_of( parts_here.begin(), parts_here.end(), [&]( const int e ) {
        return veh->part( e ).is_tank();
        } ) ) {
            msg = _( "Funnels need to be installed over a tank." );
            return false;
        }
    }

    if( sel_vpart_info->has_flag( "TURRET" ) ) {
        if( std::any_of( parts_here.begin(), parts_here.end(), [&]( const int e ) {
        return veh->part( e ).is_turret();
        } ) ) {
            msg = _( "Can't install turret on another turret." );
            return false;
        }
    }

    bool is_engine = sel_vpart_info->has_flag( "ENGINE" );
    //count current engines, some engines don't require higher skill
    int engines = 0;
    int dif_eng = 0;
    if( is_engine && sel_vpart_info->has_flag( "E_HIGHER_SKILL" ) ) {
        for( const vpart_reference &vp : veh->get_avail_parts( "ENGINE" ) ) {
            if( vp.has_feature( "E_HIGHER_SKILL" ) ) {
                engines++;
                dif_eng = dif_eng / 2 + 8;
            }
        }
    }

    int dif_steering = 0;
    if( sel_vpart_info->has_flag( "STEERABLE" ) ) {
        std::set<int> axles;
        for( const int p : veh->steering ) {
            const vehicle_part &vp = veh->part( p );
            if( !vp.info().has_flag( "TRACKED" ) ) {
                // tracked parts don't contribute to axle complexity
                axles.insert( vp.mount.x() );
            }
        }

        if( !axles.empty() && axles.count( -dd.x() ) == 0 ) {
            // Installing more than one steerable axle is hard
            // (but adding a wheel to an existing axle isn't)
            dif_steering = axles.size() + 5;
        }
    }

    const requirement_data reqs = sel_vpart_info->install_requirements();

    avatar &player_character = get_avatar();
    std::string nmsg;
    bool ok = format_reqs( nmsg, reqs, sel_vpart_info->install_skills,
                           sel_vpart_info->install_time( player_character ) );

    nmsg += _( "<color_white>Additional requirements:</color>\n" );

    bool allow_more_eng = engines < 2 || player_character.has_trait( trait_DEBUG_HS );

    if( dif_eng > 0 ) {
        const bool engine_skill_met = editor_test_mode ||
                                      player_character.get_knowledge_level( skill_mechanics ) >= dif_eng;
        if( !allow_more_eng || !engine_skill_met ) {
            ok = false;
        }
        if( allow_more_eng ) {
            //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
            nmsg += string_format( _( "> %1$s%2$s %3$i</color> for extra engines." ),
                                   status_color( engine_skill_met ),
                                   skill_mechanics.obj().name(), dif_eng ) + "\n";
        } else {
            nmsg += _( "> <color_red>You cannot install any more engines on this vehicle.</color>" ) +
                    std::string( "\n" );
        }
    }

    if( dif_steering > 0 ) {
        const bool steering_skill_met = editor_test_mode ||
                                        player_character.get_knowledge_level( skill_mechanics ) >= dif_steering;
        if( !steering_skill_met ) {
            ok = false;
        }
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
        nmsg += string_format( _( "> %1$s%2$s %3$i</color> for extra steering axles." ),
                               status_color( steering_skill_met ),
                               skill_mechanics.obj().name(), dif_steering ) + "\n";
    }

    std::pair<bool, std::string> res = calc_lift_requirements( here, *sel_vpart_info );
    if( !res.first ) {
        ok = res.first;
    }
    nmsg += res.second;

    const ret_val<void> can_mount = veh->can_mount( -dd, *sel_vpart_info );
    if( !can_mount.success() ) {
        ok = false;
        nmsg += _( "<color_white>Cannot install due to:</color>\n> " ) +
                colorize( can_mount.str(), c_red ) + "\n";
    }

    sel_vpart_info->format_description( nmsg, c_light_gray, getmaxx( w_msg ) - 4 );

    msg = colorize( nmsg, c_light_gray );
    return ok || player_character.has_trait( trait_DEBUG_HS );
}

/**
 * Moves list of fuels up or down.
 * @param delta -1 if moving up,
 *              1 if moving down
 */
void veh_interact::move_fuel_cursor( map &here, int delta )
{
    int max_fuel_indicators = static_cast<int>( veh->get_printable_fuel_types( here ).size() );
    int height = 5;
    fuel_index += delta;

    if( fuel_index < 0 ) {
        fuel_index = 0;
    } else if( fuel_index > max_fuel_indicators - height ) {
        fuel_index = std::max( max_fuel_indicators - height, 0 );
    }
}

static void sort_uilist_entries_by_line_drawing( std::vector<uilist_entry> &shape_ui_entries )
{
    // An ordering of the line drawing symbols that does not result in
    // connecting when placed adjacent to each other vertically.
    const static std::map<int, int> symbol_order = {
        { LINE_XOXO, 0 }, { LINE_OXOX, 1 },
        { LINE_XOOX, 2 }, { LINE_XXOO, 3 },
        { LINE_XXXX, 4 }, { LINE_OXXO, 5 },
        { LINE_OOXX, 6 }
    };

    std::sort( shape_ui_entries.begin(), shape_ui_entries.end(),
    []( const uilist_entry & a, const uilist_entry & b ) {
        auto a_iter = symbol_order.find( a.extratxt.sym );
        auto b_iter = symbol_order.find( b.extratxt.sym );
        if( a_iter != symbol_order.end() ) {
            if( b_iter != symbol_order.end() ) {
                return a_iter->second < b_iter->second;
            } else {
                return true;
            }
        } else if( b_iter != symbol_order.end() ) {
            return false;
        } else {
            return a.extratxt.sym < b.extratxt.sym;
        }
    } );
}

void veh_interact::do_install( map &here )
{
    if( !install_info ) {
        install_info = std::make_unique<install_info_t>();
        install_info->filter = install_search_cache;
        install_info->available_materials_only = install_available_materials_only_cache;
        install_info->show_all = install_show_all_cache;
    }
    install_info->dirty = true;
    sel_vehicle_part = nullptr;
    refresh_install_candidates();
    sync_install_selection( here );
}

bool veh_interact::install_materials_available( const vpart_info &vpart )
{
    if( editor_test_mode || get_player_character().has_trait( trait_DEBUG_HS ) ) {
        return true;
    }
    if( !install_info ) {
        return can_potentially_install( vpart );
    }

    const std::string key = vpart.id.str();
    const auto found = install_info->materials_available.find( key );
    if( found != install_info->materials_available.end() ) {
        return found->second;
    }

    const bool available = vpart.install_requirements().can_make_with_inventory(
                               *crafting_inv, is_crafting_component, 1, craft_flags::none, false );
    install_info->materials_available.emplace( key, available );
    return available;
}

void veh_interact::refresh_install_candidates()
{
    if( !install_info || !install_info->dirty ) {
        return;
    }

    // A rebuilt list can represent another mount, layer, system or search.  Do
    // not let the first click in the new list complete a double-click started
    // against the previous candidate set.
    install_info->last_clicked_part.clear();
    install_info->last_click_time.reset();

    std::string previous_id = install_selected_part_cache;
    if( sel_vpart_info != nullptr ) {
        previous_id = sel_vpart_info->id.str();
    }

    std::vector<const vpart_info *> &candidates = install_info->tab_vparts;
    candidates.clear();

    for( const vpart_info *part : can_mount ) {
        if( part == nullptr || !part_info_matches_layer( *part ) ) {
            continue;
        }
        if( active_system_filter != editor_system_filter::all &&
            primary_system_for_part_info( *part ) != active_system_filter ) {
            continue;
        }
        if( !install_info->filter.empty() && !lcmatch( part->name(), install_info->filter ) ) {
            continue;
        }
        if( !install_info->show_all && !veh->can_mount( selected_mount(), *part ).success() ) {
            continue;
        }
        if( install_info->available_materials_only && !install_materials_available( *part ) ) {
            continue;
        }
        candidates.push_back( part );
    }

    if( !install_info->available_materials_only ) {
        std::stable_partition( candidates.begin(), candidates.end(), [&]( const vpart_info *part ) {
            return install_materials_available( *part );
        } );
    }

    install_info->pos = 0;
    if( !previous_id.empty() ) {
        const auto found = std::find_if( candidates.begin(), candidates.end(),
        [&]( const vpart_info *part ) {
            return part->id.str() == previous_id;
        } );
        if( found != candidates.end() ) {
            install_info->pos = static_cast<int>( std::distance( candidates.begin(), found ) );
        }
    }
    install_info->dirty = false;
}

void veh_interact::sync_install_selection( map &here )
{
    if( !install_info ) {
        return;
    }

    refresh_install_candidates();
    std::vector<const vpart_info *> &candidates = install_info->tab_vparts;
    if( candidates.empty() ) {
        sel_vpart_info = nullptr;
        install_info->selected_can_install = false;
        msg = _( "No parts match the current layer, system, search, and visibility filters." );
        return;
    }

    install_info->pos = std::clamp( install_info->pos, 0,
                                    static_cast<int>( candidates.size() ) - 1 );
    const std::string old_id = sel_vpart_info != nullptr ? sel_vpart_info->id.str() : std::string();
    sel_vpart_info = candidates[install_info->pos];
    install_selected_part_cache = sel_vpart_info->id.str();
    if( old_id != install_selected_part_cache ) {
        w_msg_scroll_offset = 0;
    }
    install_info->selected_can_install = update_part_requirements( here );
}

bool veh_interact::confirm_install( map &here )
{
    if( !install_info ) {
        return false;
    }

    sync_install_selection( here );
    if( sel_vpart_info == nullptr || !install_info->selected_can_install ) {
        return false;
    }

    const task_reason reason = cant_do( here, 'i' );
    switch( reason ) {
        case task_reason::LOW_MORALE:
            msg = _( "Your morale is too low to construct…" );
            return false;
        case task_reason::LOW_LIGHT:
            msg = _( "It's too dark to see what you are doing…" );
            return false;
        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't install parts while driving." );
            return false;
        case task_reason::INVALID_TARGET:
            msg = _( "Cannot install any part here." );
            return false;
        default:
            break;
    }

    avatar &player_character = get_avatar();
    if( veh->would_install_prevent_flyable( *sel_vpart_info, player_character ) ) {
        if( query_yn(
                _( "Installing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
            veh->set_flyable( false );
        } else {
            return false;
        }
    }
    if( veh->is_foldable() && !sel_vpart_info->folded_volume &&
        !query_yn( _( "Installing this part will make the vehicle unfoldable.  Continue?" ) ) ) {
        return false;
    }

    sel_vehicle_part = nullptr;
    sel_cmd = 'i';
    return true;
}

void veh_interact::close_install_mode()
{
    if( install_info ) {
        install_search_cache = install_info->filter;
        install_available_materials_only_cache = install_info->available_materials_only;
        install_show_all_cache = install_info->show_all;
        if( sel_vpart_info != nullptr ) {
            install_selected_part_cache = sel_vpart_info->id.str();
        }
    }
    install_info.reset();
    sel_vpart_info = nullptr;
    msg.reset();
    w_msg_scroll_offset = 0;
    reset_part_selection();
}

bool veh_interact::move_in_list( int &pos, const std::string &action, const int size,
                                 const int header ) const
{
    const int lines_per_page = std::max( 1, getmaxy( w_list ) - header );
    if( action == "PREV_TAB" || action == "LEFT" || action == "PAGE_UP" ) {
        pos -= lines_per_page;
    } else if( action == "NEXT_TAB" || action == "RIGHT" || action == "PAGE_DOWN" ) {
        pos += lines_per_page;
    } else if( action == "UP" ) {
        pos--;
    } else if( action == "DOWN" ) {
        pos++;
    } else {
        // Anything else -> no movement
        return false;
    }
    if( pos < 0 ) {
        pos = size - 1;
    } else if( pos >= size ) {
        pos = 0;
    }
    return true;
}

void veh_interact::do_repair( map &here )
{
    task_reason reason = cant_do( here,  'r' );

    if( reason == task_reason::INVALID_TARGET ) {
        vehicle_part *most_repairable = get_most_repairable_part();
        if( most_repairable && most_repairable->is_repairable() ) {
            move_cursor( here, ( most_repairable->mount.raw() + dd ).rotate( 3 ) );
            return;
        }
    }

    auto can_repair = [this, &reason]() {
        switch( reason ) {
            case task_reason::LOW_MORALE:
                msg = _( "Your morale is too low to repair…" );
                return false;
            case task_reason::LOW_LIGHT:
                msg = _( "It's too dark to see what you are doing…" );
                return false;
            case task_reason::MOVING_VEHICLE:
                msg = _( "You can't repair stuff while driving." );
                return false;
            case task_reason::INVALID_TARGET:
                msg = _( "There are no damaged parts on this vehicle." );
                return false;
            default:
                break;
        }
        return true;
    };

    if( !can_repair() ) {
        return;
    }

    restore_on_out_of_scope prev_title( title );
    title = _( "Choose a part here to repair:" );

    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );

    int pos = 0;
    if( selected_part >= 0 ) {
        for( size_t i = 0; i < need_repair.size(); ++i ) {
            if( parts_here[need_repair[i]] == selected_part ) {
                pos = static_cast<int>( i );
                break;
            }
        }
    }

    restore_on_out_of_scope prev_hilight_part( highlight_part );

    avatar &player_character = get_avatar();
    while( true ) {
        vehicle_part &pt = veh->part( parts_here[need_repair[pos]] );
        const vpart_info &vp = pt.info();

        std::string nmsg;

        // this will always be set, but the gcc thinks that sometimes it won't be
        bool ok = true;
        if( pt.is_broken() ) {
            ok = format_reqs( nmsg, vp.install_requirements(), vp.install_skills,
                              vp.install_time( player_character ) );

            if( pt.info().has_flag( "NEEDS_JACKING" ) ) {

                nmsg += _( "<color_white>Additional requirements:</color>\n" );
                std::pair<bool, std::string> res = calc_lift_requirements( here, pt.info() );
                if( !res.first ) {
                    ok = false;
                }
                nmsg += res.second;
            }
            if( pt.has_flag( vp_flag::carried_flag ) ) {
                nmsg += colorize( _( "\nUnracking is required before replacing this part.\n" ),
                                  c_red );
                ok = false;
            }

        } else {
            if( !pt.is_repairable() ) {
                nmsg += colorize( _( "This part cannot be repaired.\n" ), c_light_red );
                ok = false;
            } else if( veh->has_part( "NO_MODIFY_VEHICLE" ) && !vp.has_flag( "SIMPLE_PART" ) ) {
                nmsg += colorize( _( "This vehicle cannot be repaired.\n" ), c_light_red );
                ok = false;
            } else {
                const int levels = pt.base.repairable_levels();
                ok = format_reqs( nmsg, vp.repair_requirements() * levels, vp.repair_skills,
                                  vp.repair_time( player_character ) * levels );
            }
        }

        bool would_prevent_flying = veh->would_repair_prevent_flyable( pt, player_character );
        if( would_prevent_flying &&
            !player_character.has_proficiency( proficiency_prof_aircraft_mechanic ) ) {
            nmsg += string_format(
                        _( "\n<color_yellow>You require the \"%s\" proficiency to repair this part safely!</color>\n\n" ),
                        proficiency_prof_aircraft_mechanic->name() );
        }

        const nc_color desc_color = pt.is_broken() ? c_dark_gray : c_light_gray;
        vp.format_description( nmsg, desc_color, getmaxx( w_msg ) - 4 );

        msg = colorize( nmsg, c_light_gray );

        highlight_part = need_repair[pos];

        ui_manager::redraw();

        const std::string action = main_context.handle_input();
        msg.reset();
        if( ( action == "REPAIR" || action == "CONFIRM" ) && ok ) {
            // Modifying a vehicle with rotors will make in not flightworthy (until we've got a better model)
            if( would_prevent_flying ) {
                // It can only be the player doing this - an npc won't work well with query_yn
                if( query_yn(
                        _( "Repairing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
                    veh->set_flyable( false );
                } else {
                    nmsg += colorize( _( "You chose not to install this part to keep the vehicle flyable.\n" ),
                                      c_light_red );
                    ok = false;
                }
            }
            if( ok ) {
                reason = cant_do( here,  'r' );
                if( !can_repair() ) {
                    return;
                }
                sel_vehicle_part = &pt;
                sel_vpart_info = &vp;
                for( const Character *helper : player_character.get_crafting_helpers() ) {
                    add_msg( m_info, _( "%s helps with this task…" ), helper->get_name() );
                }
                sel_cmd = 'r';
                break;
            }
        } else if( action == "QUIT" ) {
            break;
        } else {
            move_in_list( pos, action, need_repair.size() );
        }
    }
}

void veh_interact::do_mend( map &here )
{
    switch( cant_do( here,  'm' ) ) {
        case task_reason::LOW_MORALE:
            msg = _( "Your morale is too low to mend…" );
            return;
        case task_reason::LOW_LIGHT:
            msg = _( "It's too dark to see what you are doing…" );
            return;
        case task_reason::INVALID_TARGET:
            msg = _( "No faulty parts require mending." );
            return;
        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't mend stuff while driving." );
            return;
        default:
            break;
    }

    restore_on_out_of_scope prev_title( title );
    title = _( "Choose a part here to mend:" );

    avatar &player_character = get_avatar();
    const bool toggling = player_character.has_trait( trait_DEBUG_HS );
    auto sel = [toggling]( const map &, const vehicle_part & pt ) {
        if( toggling ) {
            return !pt.faults_potential().empty();
        } else {
            return !pt.faults().empty();
        }
    };

    auto act = [&]( const map &, const vehicle_part & pt ) {
        player_character.mend_item( veh->part_base( veh->index_of_part( &pt ) ) );
        sel_cmd = 'q';
    };

    overview( here, sel, act );
}

void veh_interact::close_refuel_mode()
{
    refuel_info.reset();
    msg.reset();
}

bool veh_interact::refill_source_compatible( const vehicle_part &part,
        const item_location &source ) const
{
    if( !source ) {
        return false;
    }

    const item &obj = *source;
    if( part.is_tank() ) {
        if( obj.is_watertight_container() && obj.num_item_stacks() == 1 && !obj.empty() ) {
            return part.can_reload( obj.only_item() );
        }
        if( obj.made_of( phase_id::LIQUID ) && !source.has_parent() ) {
            return part.can_reload( obj );
        }
        return false;
    }

    if( part.is_fuel_store() ) {
        return part.can_reload( obj ) || part.get_base().can_reload_with( obj, true );
    }
    return false;
}

int veh_interact::refill_source_available( const item_location &source ) const
{
    if( !source ) {
        return 0;
    }
    const item *payload = source.get_item();
    if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
        payload = &source->only_item();
    }
    if( payload == nullptr ) {
        return 0;
    }
    return payload->count_by_charges() ? std::max( 0, payload->charges ) : 1;
}

int veh_interact::refill_part_remaining( const vehicle_part &part,
        const item_location &source ) const
{
    if( !source ) {
        return 0;
    }
    const item *payload = source.get_item();
    if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
        payload = &source->only_item();
    }
    if( payload == nullptr ) {
        return 0;
    }

    const int capacity = part.item_capacity( payload->typeId() );
    if( capacity <= 0 ) {
        return 0;
    }
    const int current = part.ammo_current() == payload->typeId() ? part.ammo_remaining() : 0;
    return std::max( 0, capacity - current );
}

void veh_interact::refresh_refuel_sources( map &here )
{
    if( !refuel_info ) {
        return;
    }

    std::vector<item_location> previously_selected;
    item_location previous_cursor;
    for( size_t i = 0; i < refuel_info->sources.size(); ++i ) {
        if( refuel_info->sources[i].selected ) {
            previously_selected.push_back( refuel_info->sources[i].location );
        }
        if( static_cast<int>( i ) == refuel_info->source_pos ) {
            previous_cursor = refuel_info->sources[i].location;
        }
    }
    refuel_info->sources.clear();

    Character &player_character = get_player_character();
    const bool target_one_tank = refuel_info->stage == refuel_info_t::stage_t::source &&
                                 refuel_info->selected_tank_slot >= 0 &&
                                 refuel_info->selected_tank_slot < static_cast<int>( refuel_info->tanks.size() );

    const auto add_source = [&]( const item_location &loc ) {
        if( !loc ) {
            return;
        }
        if( loc->made_of( phase_id::LIQUID ) && loc.has_parent() ) {
            return;
        }

        bool compatible = false;
        if( target_one_tank ) {
            const int part_index = refuel_info->tanks[refuel_info->selected_tank_slot];
            compatible = part_index >= 0 && part_index < veh->part_count() &&
                         refill_source_compatible( veh->part( part_index ), loc ) &&
                         refill_part_remaining( veh->part( part_index ), loc ) > 0;
        } else {
            for( const int part_index : refuel_info->tanks ) {
                if( part_index >= 0 && part_index < veh->part_count() &&
                    refill_source_compatible( veh->part( part_index ), loc ) &&
                    refill_part_remaining( veh->part( part_index ), loc ) > 0 ) {
                    compatible = true;
                    break;
                }
            }
        }
        if( !compatible ) {
            return;
        }
        if( std::any_of( refuel_info->sources.begin(), refuel_info->sources.end(),
        [&]( const refuel_info_t::source_t &entry ) {
            return entry.location == loc;
        } ) ) {
            return;
        }
        refuel_info_t::source_t entry;
        entry.location = loc;
        entry.label = string_format( "%s — %s", loc->display_name(), loc.describe( &player_character ) );
        entry.selected = std::any_of( previously_selected.begin(), previously_selected.end(),
        [&]( const item_location &old ) {
            return old == loc;
        } );
        refuel_info->sources.emplace_back( std::move( entry ) );
    };

    for( const item_location &loc : player_character.all_items_loc() ) {
        add_source( loc );
    }

    map_selector nearby_map( player_character.pos_bub(), 1, true );
    for( const map_cursor &cursor : nearby_map ) {
        for( item &it : here.i_at( cursor.pos_bub( here ) ) ) {
            add_source( item_location( cursor, &it ) );
        }
    }

    vehicle_selector nearby_vehicles( here, player_character.pos_bub(), 1, true );
    for( const vehicle_cursor &cursor : nearby_vehicles ) {
        if( cursor.part < 0 || cursor.part >= cursor.veh.part_count() ) {
            continue;
        }

        // vehicle_selector returns one representative part for each occupied tile.  Vehicle
        // tiles are part stacks, so a trunk tile can resolve to its frame/roof instead of CARGO.
        // Resolve the cargo part at that same mount and use it for both stack access and the
        // item_location, otherwise perfectly reachable trunk fuel can disappear from this list.
        const int cargo_index = cursor.veh.part_with_feature( static_cast<int>( cursor.part ),
                                VPFLAG_CARGO, true );
        if( cargo_index < 0 ) {
            continue;
        }
        vehicle_part &cargo = cursor.veh.part( cargo_index );
        vehicle_cursor cargo_cursor( cursor.veh, cargo_index );
        vehicle_stack stack = cursor.veh.get_items( cargo );
        for( item &it : stack ) {
            add_source( item_location( cargo_cursor, &it ) );
        }
    }

    std::stable_sort( refuel_info->sources.begin(), refuel_info->sources.end(),
    []( const refuel_info_t::source_t &lhs, const refuel_info_t::source_t &rhs ) {
        return localized_compare( lhs.label, rhs.label );
    } );

    refuel_info->source_pos = 0;
    if( previous_cursor ) {
        const auto found = std::find_if( refuel_info->sources.begin(), refuel_info->sources.end(),
        [&]( const refuel_info_t::source_t &entry ) {
            return entry.location == previous_cursor;
        } );
        if( found != refuel_info->sources.end() ) {
            refuel_info->source_pos = static_cast<int>( std::distance( refuel_info->sources.begin(), found ) );
        }
    }
    if( refuel_info->sources.empty() ) {
        refuel_info->source_pos = 0;
        refuel_info->source_scroll = 0;
        refuel_info->source_range_anchor = -1;
    } else {
        refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                  static_cast<int>( refuel_info->sources.size() ) - 1 );
        refuel_info->source_range_anchor = std::clamp( refuel_info->source_range_anchor, -1,
                                           static_cast<int>( refuel_info->sources.size() ) - 1 );
    }
}

void veh_interact::refresh_quick_refuel_fuels( map &here )
{
    if( !refuel_info ) {
        return;
    }
    refresh_refuel_sources( here );

    std::set<itype_id> propulsion_fuels;
    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        const vehicle_part &part = vpr.part();
        if( !part.is_engine() || !part.is_available() || !part.info().engine_info ) {
            continue;
        }
        for( const itype_id &fuel : part.info().engine_info->fuel_opts ) {
            if( !fuel.is_null() ) {
                propulsion_fuels.insert( fuel );
            }
        }
        if( !part.fuel_current().is_null() ) {
            propulsion_fuels.insert( part.fuel_current() );
        }
    }

    refuel_info->quick_fuels.clear();
    for( const refuel_info_t::source_t &source : refuel_info->sources ) {
        if( !source.location ) {
            continue;
        }
        const item *payload = source.location.get_item();
        if( source.location->is_watertight_container() &&
            source.location->num_item_stacks() == 1 && !source.location->empty() ) {
            payload = &source.location->only_item();
        }
        if( payload == nullptr || propulsion_fuels.count( payload->typeId() ) == 0 ||
            refill_source_available( source.location ) <= 0 ) {
            continue;
        }

        bool has_target_store = false;
        for( const int part_index : refuel_info->tanks ) {
            if( part_index >= 0 && part_index < veh->part_count() &&
                refill_source_compatible( veh->part( part_index ), source.location ) &&
                refill_part_remaining( veh->part( part_index ), source.location ) > 0 ) {
                has_target_store = true;
                break;
            }
        }
        if( !has_target_store ) {
            continue;
        }
        if( std::find( refuel_info->quick_fuels.begin(), refuel_info->quick_fuels.end(),
                      payload->typeId() ) == refuel_info->quick_fuels.end() ) {
            refuel_info->quick_fuels.push_back( payload->typeId() );
        }
    }

    std::stable_sort( refuel_info->quick_fuels.begin(), refuel_info->quick_fuels.end(),
    []( const itype_id &lhs, const itype_id &rhs ) {
        return localized_compare( item::nname( lhs ), item::nname( rhs ) );
    } );
    if( refuel_info->quick_fuels.empty() ) {
        refuel_info->quick_fuel_pos = 0;
        refuel_info->quick_fuel_scroll = 0;
    } else {
        refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,
                                      static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
    }
}

bool veh_interact::queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan )
{
    if( plan.empty() ) {
        return false;
    }

    refill_part_indices.clear();
    refill_targets.clear();
    for( const std::pair<int, item_location> &transfer : plan ) {
        if( transfer.first < 0 || transfer.first >= veh->part_count() || !transfer.second ) {
            continue;
        }
        refill_part_indices.push_back( transfer.first );
        refill_targets.push_back( transfer.second );
    }
    if( refill_part_indices.empty() ) {
        return false;
    }

    sel_vehicle_part = &veh->part( refill_part_indices.front() );
    sel_vpart_info = &sel_vehicle_part->info();
    sel_cmd = 'f';
    close_refuel_mode();
    return true;
}

bool veh_interact::queue_selected_refill_source( map &here )
{
    if( !refuel_info || refuel_info->stage != refuel_info_t::stage_t::source ||
        refuel_info->selected_tank_slot < 0 ||
        refuel_info->selected_tank_slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
        return false;
    }
    if( refuel_info->sources.empty() ) {
        msg = _( "No compatible fuel source is available within reach." );
        return false;
    }

    const int part_index = refuel_info->tanks[refuel_info->selected_tank_slot];
    vehicle_part &part = veh->part( part_index );
    std::vector<int> selected_sources;
    for( size_t i = 0; i < refuel_info->sources.size(); ++i ) {
        if( refuel_info->sources[i].selected ) {
            selected_sources.push_back( static_cast<int>( i ) );
        }
    }
    if( selected_sources.empty() ) {
        refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                  static_cast<int>( refuel_info->sources.size() ) - 1 );
        selected_sources.push_back( refuel_info->source_pos );
    }

    const auto payload_of = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };

    std::optional<itype_id> fuel_type;
    int remaining = -1;
    std::vector<std::pair<int, item_location>> plan;
    for( const int source_index : selected_sources ) {
        const item_location source = refuel_info->sources[source_index].location;
        const item *payload = payload_of( source );
        if( payload == nullptr || !refill_source_compatible( part, source ) ) {
            continue;
        }
        if( fuel_type && payload->typeId() != *fuel_type ) {
            msg = _( "Selected sources must contain the same fuel type." );
            return false;
        }
        if( !fuel_type ) {
            fuel_type = payload->typeId();
            remaining = refill_part_remaining( part, source );
        }
        if( remaining <= 0 ) {
            break;
        }
        const int available = refill_source_available( source );
        if( available <= 0 ) {
            continue;
        }
        plan.emplace_back( part_index, source );
        remaining -= std::min( remaining, available );
    }

    if( plan.empty() ) {
        msg = _( "The selected sources cannot refill this fuel store." );
        refresh_refuel_sources( here );
        return false;
    }
    return queue_refill_plan( plan );
}

bool veh_interact::queue_quick_refill_all( map &here )
{
    if( !refuel_info || refuel_info->stage != refuel_info_t::stage_t::quick_fuel ) {
        return false;
    }
    refresh_quick_refuel_fuels( here );
    if( refuel_info->quick_fuels.empty() ) {
        msg = _( "No available fuel can currently power an installed, working engine." );
        return false;
    }
    refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,
                                  static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
    const itype_id selected_fuel = refuel_info->quick_fuels[refuel_info->quick_fuel_pos];

    const auto payload_of = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };

    struct source_state_t {
        int remaining = 0;
        bool divisible = false;
    };
    std::vector<source_state_t> source_state( refuel_info->sources.size() );
    for( size_t i = 0; i < refuel_info->sources.size(); ++i ) {
        const item *payload = payload_of( refuel_info->sources[i].location );
        if( payload != nullptr && payload->typeId() == selected_fuel ) {
            source_state[i].remaining = refill_source_available( refuel_info->sources[i].location );
            source_state[i].divisible = payload->count_by_charges();
        }
    }

    struct target_t {
        int part_index = -1;
        int need = 0;
    };
    std::vector<target_t> targets;
    for( const int part_index : refuel_info->tanks ) {
        if( part_index < 0 || part_index >= veh->part_count() ) {
            continue;
        }
        int best_need = 0;
        for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
            if( source_state[s].remaining <= 0 ) {
                continue;
            }
            const item_location &source = refuel_info->sources[s].location;
            if( refill_source_compatible( veh->part( part_index ), source ) ) {
                best_need = std::max( best_need, refill_part_remaining( veh->part( part_index ), source ) );
            }
        }
        if( best_need > 0 ) {
            targets.push_back( { part_index, best_need } );
        }
    }
    std::stable_sort( targets.begin(), targets.end(), []( const target_t &lhs, const target_t &rhs ) {
        return lhs.need > rhs.need;
    } );

    std::vector<std::pair<int, item_location>> plan;
    for( const target_t &target : targets ) {
        int tank_remaining = target.need;
        while( tank_remaining > 0 ) {
            int best_source = -1;
            int best_transfer = 0;
            bool best_finishes = false;
            int best_surplus = INT_MAX;

            for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
                if( source_state[s].remaining <= 0 ) {
                    continue;
                }
                const item_location &source = refuel_info->sources[s].location;
                const item *payload = payload_of( source );
                if( payload == nullptr || payload->typeId() != selected_fuel ||
                    !refill_source_compatible( veh->part( target.part_index ), source ) ) {
                    continue;
                }
                const int transfer = std::min( tank_remaining, source_state[s].remaining );
                const bool finishes = transfer >= tank_remaining;
                const int surplus = finishes ? source_state[s].remaining - tank_remaining : INT_MAX;
                if( best_source < 0 || ( finishes && !best_finishes ) ||
                    ( finishes == best_finishes && finishes && surplus < best_surplus ) ||
                    ( !finishes && !best_finishes && transfer > best_transfer ) ) {
                    best_source = static_cast<int>( s );
                    best_transfer = transfer;
                    best_finishes = finishes;
                    best_surplus = surplus;
                }
            }

            if( best_source < 0 || best_transfer <= 0 ) {
                break;
            }
            plan.emplace_back( target.part_index, refuel_info->sources[best_source].location );
            tank_remaining -= best_transfer;
            source_state[best_source].remaining -= best_transfer;
            if( !source_state[best_source].divisible ) {
                source_state[best_source].remaining = 0;
            }
        }
    }

    if( plan.empty() ) {
        msg = string_format( _( "No connected vehicle fuel stores can be filled with %s." ),
                             item::nname( selected_fuel ) );
        return false;
    }
    // queue_refill_plan preserves the canonical one-action-turn-per-transfer cost.
    return queue_refill_plan( plan );
}

bool veh_interact::add_test_refuel_containers( map &here )
{
    if( !editor_test_mode ) {
        return false;
    }

    std::vector<int> cargo_parts;
    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        const vehicle_part &part = vpr.part();
        if( part.is_available() && part.info().has_flag( VPFLAG_CARGO ) ) {
            cargo_parts.push_back( veh->index_of_part( &part ) );
        }
    }
    if( cargo_parts.empty() ) {
        msg = _( "Test fuel requires at least one valid cargo/trunk part on this vehicle." );
        return false;
    }

    std::set<itype_id> propulsion_liquids;
    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        const vehicle_part &part = vpr.part();
        if( !part.is_engine() || !part.is_available() || !part.info().engine_info ) {
            continue;
        }
        for( const itype_id &fuel : part.info().engine_info->fuel_opts ) {
            if( !fuel.is_null() && item::find_type( fuel )->phase == phase_id::LIQUID ) {
                propulsion_liquids.insert( fuel );
            }
        }
    }

    const itype_id gasoline( "gasoline" );
    itype_id fuel = gasoline;
    if( propulsion_liquids.count( gasoline ) == 0 && !propulsion_liquids.empty() ) {
        fuel = *propulsion_liquids.begin();
    }

    const std::array<itype_id, 4> container_types = { {
            itype_id( "bottle_plastic" ), itype_id( "bottle_glass" ),
            itype_id( "canteen" ), itype_id( "jerrycan" )
        } };

    int added = 0;
    for( const itype_id &container_type : container_types ) {
        item container( container_type, calendar::turn );
        item liquid( fuel, calendar::turn );
        const int capacity = container.get_remaining_capacity_for_liquid( liquid );
        if( capacity <= 0 ) {
            continue;
        }
        liquid.charges = capacity;
        if( container.fill_with( liquid, capacity, true, true, true ) <= 0 ) {
            continue;
        }

        for( const int cargo_index : cargo_parts ) {
            if( veh->add_item( here, veh->part( cargo_index ), container ) ) {
                ++added;
                break;
            }
        }
    }

    if( added <= 0 ) {
        msg = _( "No test fuel containers fit in this vehicle's cargo storage." );
        return false;
    }

    veh->invalidate_mass();
    refresh_refuel_sources( here );
    refresh_quick_refuel_fuels( here );
    msg = string_format( _( "Added %1$d filled %2$s test containers directly to vehicle cargo." ),
                         added, item::nname( fuel ) );
    return true;
}

void veh_interact::display_refuel_pane( map &here )
{
    if( !refuel_info || !w_refuel_overlay ) {
        return;
    }

    werase( w_refuel_overlay );
    draw_border( w_refuel_overlay, c_light_gray );
    const int width = getmaxx( w_refuel_overlay );
    const int height = getmaxy( w_refuel_overlay );
    if( width < 4 || height < 4 ) {
        wnoutrefresh( w_refuel_overlay );
        return;
    }

    const auto payload_of = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };
    const auto source_amount = [&]( const item_location &source ) {
        const item *payload = payload_of( source );
        if( payload == nullptr ) {
            return std::string();
        }
        if( payload->made_of( phase_id::LIQUID ) ) {
            return string_format( "%.1f L", units::to_liter( payload->volume() ) );
        }
        return string_format( _( "%d charges" ), refill_source_available( source ) );
    };
    const auto tank_amount = []( const vehicle_part &part ) {
        if( part.is_tank() ) {
            units::volume current = 0_ml;
            if( !part.base.empty() && part.base.only_item().made_of( phase_id::LIQUID ) ) {
                current = part.base.only_item().volume();
            }
            return string_format( "%.1f / %.1f L", units::to_liter( current ),
                                  units::to_liter( part.info().size ) );
        }
        if( !part.ammo_current().is_null() ) {
            return string_format( "%d / %d", part.ammo_remaining(),
                                  part.item_capacity( part.ammo_current() ) );
        }
        return std::string( "0" );
    };

    using refuel_stage = refuel_info_t::stage_t;
    if( refuel_info->stage == refuel_stage::tank ) {
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        _( "Refuel vehicle" ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        _( "Select a fuel store. Quick fill chooses propulsion fuel separately." ) );

        const int first_row = 3;
        const int button_rows = editor_test_mode ? 4 : 3;
        const int visible = std::max( 1, height - first_row - button_rows );
        if( !refuel_info->tanks.empty() ) {
            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos, 0,
                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );
            if( refuel_info->tank_pos < refuel_info->tank_scroll ) {
                refuel_info->tank_scroll = refuel_info->tank_pos;
            } else if( refuel_info->tank_pos >= refuel_info->tank_scroll + visible ) {
                refuel_info->tank_scroll = refuel_info->tank_pos - visible + 1;
            }
            refuel_info->tank_scroll = std::clamp( refuel_info->tank_scroll, 0,
                                       std::max( 0, static_cast<int>( refuel_info->tanks.size() ) - visible ) );
        }
        for( int row = 0; row < visible; ++row ) {
            const int slot = refuel_info->tank_scroll + row;
            if( slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
                break;
            }
            const vehicle_part &part = veh->part( refuel_info->tanks[slot] );
            const bool usable = part.can_reload();
            std::string fuel = part.ammo_current().is_null() ? _( "empty" ) : item::nname( part.ammo_current() );
            const std::string line = string_format( "%s  %s  [%s]", part.name(), tank_amount( part ), fuel );
            nc_color color = usable ? c_light_gray : c_dark_gray;
            if( slot == refuel_info->tank_pos ) {
                color = hilite( color );
            }
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );
        }

        const int quick_y = height - ( editor_test_mode ? 4 : 3 );
        trim_and_print( w_refuel_overlay, point( 2, quick_y ), width - 4, c_light_cyan,
                        _( "[ Quick fill… ]" ) );
        if( editor_test_mode ) {
            trim_and_print( w_refuel_overlay, point( 2, quick_y + 1 ), width - 4, c_light_red,
                            _( "[ Test: add filled fuel containers to cargo ]" ) );
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        _( "[ Close ]" ) );
    } else if( refuel_info->stage == refuel_stage::source ) {
        if( refuel_info->selected_tank_slot < 0 ||
            refuel_info->selected_tank_slot >= static_cast<int>( refuel_info->tanks.size() ) ) {
            refuel_info->stage = refuel_stage::tank;
            wnoutrefresh( w_refuel_overlay );
            return;
        }
        const vehicle_part &tank = veh->part( refuel_info->tanks[refuel_info->selected_tank_slot] );
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        string_format( _( "Refuel: %s" ), tank.name() ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        string_format( _( "Current: %s" ), tank_amount( tank ) ) );
        trim_and_print( w_refuel_overlay, point( 2, 2 ), width - 4, c_dark_gray,
                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range" ) );

        constexpr int first_row = 4;
        const int visible = std::max( 1, height - first_row - 5 );
        if( !refuel_info->sources.empty() ) {
            refuel_info->source_pos = std::clamp( refuel_info->source_pos, 0,
                                      static_cast<int>( refuel_info->sources.size() ) - 1 );
            if( refuel_info->source_pos < refuel_info->source_scroll ) {
                refuel_info->source_scroll = refuel_info->source_pos;
            } else if( refuel_info->source_pos >= refuel_info->source_scroll + visible ) {
                refuel_info->source_scroll = refuel_info->source_pos - visible + 1;
            }
            refuel_info->source_scroll = std::clamp( refuel_info->source_scroll, 0,
                                         std::max( 0, static_cast<int>( refuel_info->sources.size() ) - visible ) );
        }
        for( int row = 0; row < visible; ++row ) {
            const int index = refuel_info->source_scroll + row;
            if( index >= static_cast<int>( refuel_info->sources.size() ) ) {
                break;
            }
            const refuel_info_t::source_t &source = refuel_info->sources[index];
            const std::string marker = source.selected ? "[x]" : "[ ]";
            const std::string line = string_format( "%s %s  %s", marker,
                                     source_amount( source.location ), source.label );
            nc_color color = source.selected ? c_light_cyan : c_light_gray;
            if( index == refuel_info->source_pos ) {
                color = hilite( color );
            }
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4, color, line );
        }
        if( refuel_info->sources.empty() ) {
            trim_and_print( w_refuel_overlay, point( 2, first_row ), width - 4, c_dark_gray,
                            _( "No compatible carried, adjacent, cargo, or map fuel source is in reach." ) );
        }

        int selected_count = 0;
        int effective_actions = 0;
        int simulated_remaining = -1;
        std::optional<itype_id> selected_fuel;
        for( const refuel_info_t::source_t &source : refuel_info->sources ) {
            if( !source.selected ) {
                continue;
            }
            ++selected_count;
            const item *payload = payload_of( source.location );
            if( payload == nullptr ) {
                continue;
            }
            if( !selected_fuel ) {
                selected_fuel = payload->typeId();
                simulated_remaining = refill_part_remaining( tank, source.location );
            }
            if( payload->typeId() != *selected_fuel || simulated_remaining <= 0 ) {
                continue;
            }
            const int available = refill_source_available( source.location );
            if( available > 0 ) {
                ++effective_actions;
                simulated_remaining -= std::min( simulated_remaining, available );
            }
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 4 ), width - 4, c_light_gray,
                        string_format( _( "Selected: %1$d source(s)   Cost: %2$d refill action(s)" ),
                                       selected_count, effective_actions ) );
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4, c_light_green,
                        _( "[ Refuel selected ]" ) );
        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        back_label );
        const int cancel_x = std::max( 2, width - 2 - utf8_width( cancel_label ) );
        trim_and_print( w_refuel_overlay, point( cancel_x, height - 2 ),
                        width - cancel_x - 1, c_light_gray, cancel_label );
    } else {
        refresh_quick_refuel_fuels( here );
        trim_and_print( w_refuel_overlay, point( 2, 0 ), width - 4, c_light_green,
                        _( "Quick fill — propulsion fuel" ) );
        trim_and_print( w_refuel_overlay, point( 2, 1 ), width - 4, c_light_gray,
                        _( "Only fuel usable by an installed working engine and available now is listed." ) );

        constexpr int first_row = 3;
        const int visible = std::max( 1, height - first_row - 4 );
        if( !refuel_info->quick_fuels.empty() ) {
            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos, 0,
                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
            if( refuel_info->quick_fuel_pos < refuel_info->quick_fuel_scroll ) {
                refuel_info->quick_fuel_scroll = refuel_info->quick_fuel_pos;
            } else if( refuel_info->quick_fuel_pos >= refuel_info->quick_fuel_scroll + visible ) {
                refuel_info->quick_fuel_scroll = refuel_info->quick_fuel_pos - visible + 1;
            }
        }
        for( int row = 0; row < visible; ++row ) {
            const int index = refuel_info->quick_fuel_scroll + row;
            if( index >= static_cast<int>( refuel_info->quick_fuels.size() ) ) {
                break;
            }
            const itype_id fuel = refuel_info->quick_fuels[index];
            double liters = 0.0;
            int charges = 0;
            bool liquid = item::find_type( fuel )->phase == phase_id::LIQUID;
            for( const refuel_info_t::source_t &source : refuel_info->sources ) {
                const item *payload = payload_of( source.location );
                if( payload == nullptr || payload->typeId() != fuel ) {
                    continue;
                }
                if( liquid ) {
                    liters += units::to_liter( payload->volume() );
                } else {
                    charges += refill_source_available( source.location );
                }
            }
            const std::string amount = liquid ? string_format( "%.1f L", liters ) :
                                       string_format( _( "%d charges" ), charges );
            trim_and_print( w_refuel_overlay, point( 2, first_row + row ), width - 4,
                            index == refuel_info->quick_fuel_pos ? h_light_cyan : c_light_gray,
                            string_format( "%s  —  %s available", item::nname( fuel ), amount ) );
        }
        if( refuel_info->quick_fuels.empty() ) {
            trim_and_print( w_refuel_overlay, point( 2, first_row ), width - 4, c_dark_gray,
                            _( "No currently available source matches a working propulsion engine." ) );
        }
        trim_and_print( w_refuel_overlay, point( 2, height - 3 ), width - 4,
                        refuel_info->quick_fuels.empty() ? c_dark_gray : c_light_green,
                        _( "[ Quick fill selected fuel ]" ) );
        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        trim_and_print( w_refuel_overlay, point( 2, height - 2 ), width - 4, c_light_gray,
                        back_label );
        const int cancel_x = std::max( 2, width - 2 - utf8_width( cancel_label ) );
        trim_and_print( w_refuel_overlay, point( cancel_x, height - 2 ),
                        width - cancel_x - 1, c_light_gray, cancel_label );
    }

    if( msg && height > 5 ) {
        trim_and_print( w_refuel_overlay, point( 2, height - 5 ), width - 4, c_light_red, *msg );
    }
    wnoutrefresh( w_refuel_overlay );
}

bool veh_interact::handle_refuel_mouse( map &here, const std::string &action )
{
    if( !refuel_info ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_refuel_overlay );
    const bool inside = pos && pos->x >= 0 && pos->y >= 0 &&
                        pos->x < getmaxx( w_refuel_overlay ) && pos->y < getmaxy( w_refuel_overlay );
    if( !inside ) {
        // The modal owns mouse input while open; clicks outside do not alter the editor behind it.
        return action == "SELECT" || action == "SEC_SELECT" || action == "SCROLL_UP" ||
               action == "SCROLL_DOWN" || action == "MOUSE_MOVE";
    }

    const int height = getmaxy( w_refuel_overlay );
    using refuel_stage = refuel_info_t::stage_t;

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        const int delta = action == "SCROLL_UP" ? -1 : 1;
        if( refuel_info->stage == refuel_stage::tank && !refuel_info->tanks.empty() ) {
            refuel_info->tank_pos = std::clamp( refuel_info->tank_pos + delta, 0,
                                    static_cast<int>( refuel_info->tanks.size() ) - 1 );
        } else if( refuel_info->stage == refuel_stage::source && !refuel_info->sources.empty() ) {
            refuel_info->source_pos = std::clamp( refuel_info->source_pos + delta, 0,
                                      static_cast<int>( refuel_info->sources.size() ) - 1 );
        } else if( refuel_info->stage == refuel_stage::quick_fuel && !refuel_info->quick_fuels.empty() ) {
            refuel_info->quick_fuel_pos = std::clamp( refuel_info->quick_fuel_pos + delta, 0,
                                          static_cast<int>( refuel_info->quick_fuels.size() ) - 1 );
        }
        return true;
    }

    if( action != "SELECT" ) {
        return true;
    }

    msg.reset();
    if( refuel_info->stage == refuel_stage::tank ) {
        constexpr int first_row = 3;
        const int button_rows = editor_test_mode ? 4 : 3;
        const int visible = std::max( 1, height - first_row - button_rows );
        if( pos->y >= first_row && pos->y < first_row + visible ) {
            const int slot = refuel_info->tank_scroll + pos->y - first_row;
            if( slot >= 0 && slot < static_cast<int>( refuel_info->tanks.size() ) ) {
                refuel_info->tank_pos = slot;
                const int part_index = refuel_info->tanks[slot];
                if( veh->part( part_index ).can_reload() ) {
                    refuel_info->selected_tank_slot = slot;
                    refuel_info->stage = refuel_stage::source;
                    refuel_info->source_pos = 0;
                    refuel_info->source_range_anchor = -1;
                    refresh_refuel_sources( here );
                } else {
                    msg = _( "That fuel store is already full or cannot currently be refilled." );
                }
            }
            return true;
        }
        const int quick_y = height - ( editor_test_mode ? 4 : 3 );
        if( pos->y == quick_y ) {
            refuel_info->stage = refuel_stage::quick_fuel;
            refuel_info->quick_fuel_pos = 0;
            refresh_quick_refuel_fuels( here );
            return true;
        }
        if( editor_test_mode && pos->y == quick_y + 1 ) {
            add_test_refuel_containers( here );
            return true;
        }
        if( pos->y == height - 2 ) {
            close_refuel_mode();
            return true;
        }
        return true;
    }

    if( refuel_info->stage == refuel_stage::source ) {
        constexpr int first_row = 4;
        const int visible = std::max( 1, height - first_row - 5 );
        if( pos->y >= first_row && pos->y < first_row + visible ) {
            const int index = refuel_info->source_scroll + pos->y - first_row;
            if( index < 0 || index >= static_cast<int>( refuel_info->sources.size() ) ) {
                return true;
            }

            const input_event raw = main_context.get_raw_input();
            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;
            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;
            const item_location clicked = refuel_info->sources[index].location;
            const auto now = std::chrono::steady_clock::now();
            const bool double_click = !ctrl && !shift && refuel_info->last_clicked_source &&
                                      refuel_info->last_clicked_source == clicked &&
                                      refuel_info->last_source_click_time &&
                                      now - *refuel_info->last_source_click_time <= std::chrono::milliseconds( 500 );

            refuel_info->source_pos = index;
            if( shift && refuel_info->source_range_anchor >= 0 ) {
                if( !ctrl ) {
                    for( refuel_info_t::source_t &source : refuel_info->sources ) {
                        source.selected = false;
                    }
                }
                const int first = std::min( refuel_info->source_range_anchor, index );
                const int last = std::max( refuel_info->source_range_anchor, index );
                for( int i = first; i <= last; ++i ) {
                    refuel_info->sources[i].selected = true;
                }
            } else if( ctrl ) {
                refuel_info->sources[index].selected = !refuel_info->sources[index].selected;
                refuel_info->source_range_anchor = index;
            } else {
                for( refuel_info_t::source_t &source : refuel_info->sources ) {
                    source.selected = false;
                }
                refuel_info->sources[index].selected = true;
                refuel_info->source_range_anchor = index;
            }

            if( double_click ) {
                refuel_info->last_clicked_source = item_location();
                refuel_info->last_source_click_time.reset();
                queue_selected_refill_source( here );
            } else {
                refuel_info->last_clicked_source = clicked;
                refuel_info->last_source_click_time = now;
            }
            return true;
        }
        if( pos->y == height - 3 ) {
            queue_selected_refill_source( here );
            return true;
        }
        if( pos->y == height - 2 ) {
            const std::string back_label = _( "[ Back ]" );
            const std::string cancel_label = _( "[ Cancel ]" );
            const int back_x = 2;
            const int cancel_x = std::max( 2, getmaxx( w_refuel_overlay ) - 2 -
                                           utf8_width( cancel_label ) );
            if( pos->x >= cancel_x && pos->x < cancel_x + utf8_width( cancel_label ) ) {
                close_refuel_mode();
            } else if( pos->x >= back_x && pos->x < back_x + utf8_width( back_label ) ) {
                refuel_info->stage = refuel_stage::tank;
                refuel_info->source_range_anchor = -1;
                refresh_refuel_sources( here );
            }
            return true;
        }
        return true;
    }

    const int first_row = 3;
    const int visible = std::max( 1, height - first_row - 4 );
    if( pos->y >= first_row && pos->y < first_row + visible ) {
        const int index = refuel_info->quick_fuel_scroll + pos->y - first_row;
        if( index >= 0 && index < static_cast<int>( refuel_info->quick_fuels.size() ) ) {
            refuel_info->quick_fuel_pos = index;
        }
        return true;
    }
    if( pos->y == height - 3 ) {
        queue_quick_refill_all( here );
        return true;
    }
    if( pos->y == height - 2 ) {
        const std::string back_label = _( "[ Back ]" );
        const std::string cancel_label = _( "[ Cancel ]" );
        const int back_x = 2;
        const int cancel_x = std::max( 2, getmaxx( w_refuel_overlay ) - 2 -
                                       utf8_width( cancel_label ) );
        if( pos->x >= cancel_x && pos->x < cancel_x + utf8_width( cancel_label ) ) {
            close_refuel_mode();
        } else if( pos->x >= back_x && pos->x < back_x + utf8_width( back_label ) ) {
            refuel_info->stage = refuel_stage::tank;
            refresh_refuel_sources( here );
        }
        return true;
    }
    return true;
}

void veh_interact::do_refill( map &here )
{
    if( refuel_info ) {
        refresh_refuel_sources( here );
        return;
    }

    switch( cant_do( here, 'f' ) ) {
        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't refill a moving vehicle." );
            return;
        case task_reason::INVALID_TARGET:
            msg = _( "No parts can currently be refilled." );
            return;
        default:
            break;
    }

    refuel_info = std::make_unique<refuel_info_t>();
    for( const vpart_reference &ref : veh->get_all_parts() ) {
        const vehicle_part &part = ref.part();
        if( part.removed || !( part.is_tank() || part.is_fuel_store() ) ) {
            continue;
        }
        refuel_info->tanks.push_back( veh->index_of_part( &part ) );
    }

    for( size_t i = 0; i < refuel_info->tanks.size(); ++i ) {
        if( refuel_info->tanks[i] == selected_part && veh->part( refuel_info->tanks[i] ).can_reload() ) {
            refuel_info->tank_pos = static_cast<int>( i );
            break;
        }
        if( !veh->part( refuel_info->tanks[refuel_info->tank_pos] ).can_reload() &&
            veh->part( refuel_info->tanks[i] ).can_reload() ) {
            refuel_info->tank_pos = static_cast<int>( i );
        }
    }
    refresh_refuel_sources( here );
    msg.reset();
}

void veh_interact::calc_overview( map &here )
{
    const hotkey_queue &hotkeys = hotkey_queue::alphabets();

    const auto next_hotkey = [&]( input_event & evt ) {
        input_event prev = evt;
        evt = main_context.next_unassigned_hotkey( hotkeys, evt );
        return prev;
    };
    auto is_selectable = [&]( const vehicle_part & pt ) {
        return overview_action && overview_enable && overview_enable( here,  pt );
    };

    overview_opts.clear();
    overview_headers.clear();

    units::power epower = veh->net_battery_charge_rate( here, /* include_reactors = */ true );
    overview_headers["1_ENGINE"] = [this, &here]( const catacurses::window & w, int y ) {
        trim_and_print( w, point( 1, y ), getmaxx( w ) - 2, c_light_gray,
                        string_format( _( "Engines: %sSafe %4d kW</color> %sMax %4d kW</color>" ),
                                       health_color( true ), units::to_kilowatt( veh->total_power( here, true, true ) ),
                                       health_color( false ), units::to_kilowatt( veh->total_power( here ) ) ) );
        right_print( w, y, 1, c_light_gray, _( "Fuel     Use" ) );
    };
    overview_headers["2_TANK"] = []( const catacurses::window & w, int y ) {
        trim_and_print( w, point( 1, y ), getmaxx( w ) - 2, c_light_gray, _( "Tanks" ) );
        right_print( w, y, 1, c_light_gray, _( "Contents     Qty" ) );
    };
    overview_headers["3_BATTERY"] = [epower]( const catacurses::window & w, int y ) {
        std::string batt;
        if( epower < 10_kW || epower > 10_kW ) {
            batt = string_format( _( "Batteries: %s%+4d W</color>" ),
                                  health_color( epower >= 0_W ), units::to_watt( epower ) );
        } else {
            batt = string_format( _( "Batteries: %s%+4.1f kW</color>" ),
                                  health_color( epower >= 0_W ), units::to_watt( epower ) / 1000.0 );
        }
        trim_and_print( w, point( 1, y ), getmaxx( w ) - 2, c_light_gray, batt );
        right_print( w, y, 1, c_light_gray, _( "Capacity  Status" ) );
    };
    overview_headers["4_REACTOR"] = [this]( const catacurses::window & w, int y ) {
        units::power reactor_epower = veh->max_reactor_epower();
        std::string reactor;
        if( reactor_epower == 0_W ) {
            reactor = _( "Reactors" );
        } else if( reactor_epower < 10_kW ) {
            reactor = string_format( _( "Reactors: Up to %s%+4d W</color>" ),
                                     health_color( reactor_epower > 0_W ), units::to_watt( reactor_epower ) );
        } else {
            reactor = string_format( _( "Reactors: Up to %s%+4.1f kW</color>" ),
                                     health_color( reactor_epower > 0_W ), units::to_watt( reactor_epower ) / 1000.0 );
        }
        trim_and_print( w, point( 1, y ), getmaxx( w ) - 2, c_light_gray, reactor );
        right_print( w, y, 1, c_light_gray, _( "Contents     Qty" ) );
    };
    overview_headers["5_TURRET"] = []( const catacurses::window & w, int y ) {
        trim_and_print( w, point( 1, y ), getmaxx( w ) - 2, c_light_gray, _( "Turrets" ) );
        right_print( w, y, 1, c_light_gray, _( "Ammo     Qty" ) );
    };
    overview_headers["6_SEAT"] = []( const catacurses::window & w, int y ) {
        trim_and_print( w, point( 1, y ), getmaxx( w ) - 2, c_light_gray, _( "Seats" ) );
        right_print( w, y, 1, c_light_gray, _( "Who" ) );
    };

    input_event hotkey = main_context.first_unassigned_hotkey( hotkeys );
    bool selectable;

    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        if( !vpr.part().is_available() ) {
            continue;
        }

        if( vpr.part().is_engine() ) {
            // if tank contains something then display the contents in milliliters
            auto details = []( const vehicle_part & pt, const catacurses::window & w, int y ) {
                right_print(
                    w, y, 1, item::find_type( pt.ammo_current() )->color,
                    string_format(
                        "%s     <color_light_gray>%s</color>",
                        !pt.fuel_current().is_null() ? item::nname( pt.fuel_current() ) : "",
                        //~ translation should not exceed 3 console cells
                        right_justify( pt.enabled ? _( "Yes" ) : _( "No" ), 3 ) ) );
            };

            // display engine faults (if any)
            auto msg_cb = [&]( const vehicle_part & pt ) {
                msg = std::string();
                for( const auto &e : pt.faults() ) {
                    msg = msg.value() + string_format( "%s\n  %s\n\n", colorize( e->name(), c_red ),
                                                       colorize( e->description(), c_light_gray ) );
                }
            };
            selectable = is_selectable( vpr.part() );
            overview_opts.emplace_back( "1_ENGINE", &vpr.part(), selectable,
                                        selectable ? next_hotkey( hotkey ) : input_event(),
                                        details,
                                        msg_cb );
        }

        if( vpr.part().is_tank() || ( vpr.part().is_fuel_store() &&
                                      !( vpr.part().is_turret() || vpr.part().is_battery() || vpr.part().is_reactor() ) ) ) {
            auto tank_details = []( const vehicle_part & pt, const catacurses::window & w, int y ) {
                if( !pt.ammo_current().is_null() ) {
                    std::string specials;
                    // vehicle parts can only have one pocket, and we are showing a liquid,
                    // which can only be one.
                    const item &it = pt.base.legacy_front();
                    // a space isn't actually needed in front of the tags here,
                    // but item::display_name tags use a space so this prevents
                    // needing *second* translation for the same thing with a
                    // space in front of it
                    if( it.has_own_flag( flag_FROZEN ) ) {
                        specials += _( " (frozen)" );
                    } else if( it.rotten() ) {
                        specials += _( " (rotten)" );
                    }
                    const itype *pt_ammo_cur = item::find_type( pt.ammo_current() );
                    int offset = 1;
                    std::string fmtstring = "%s %s  %5.1fL";
                    if( pt.is_leaking() ) {
                        fmtstring = str_cat( "%s %s ", leak_marker, "%5.1fL", leak_marker );
                        offset = 0;
                    }
                    right_print( w, y, offset, pt_ammo_cur->color,
                                 string_format( fmtstring, specials, pt_ammo_cur->nname( 1 ),
                                                round_up( units::to_liter( it.volume() ), 1 ) ) );
                } else {
                    if( pt.is_leaking() ) {
                        std::string outputstr = str_cat( leak_marker, "      ", leak_marker );
                        right_print( w, y, 0, c_light_gray, outputstr );
                    }
                }
            };
            auto no_tank_details = []( const vehicle_part & pt, const catacurses::window & w, int y ) {
                if( !pt.ammo_current().is_null() ) {
                    const itype *pt_ammo_cur = item::find_type( pt.ammo_current() );
                    double vol_L = to_liter( pt.ammo_remaining( ) * 250_ml /
                                             pt_ammo_cur->stack_size );
                    int offset = 1;
                    std::string fmtstring = "%s  %5.1fL";
                    if( pt.is_leaking() ) {
                        fmtstring = str_cat( "%s  ", leak_marker, "%5.1fL", leak_marker );
                        offset = 0;
                    }
                    right_print( w, y, offset, pt_ammo_cur->color,
                                 string_format( fmtstring, item::nname( pt.ammo_current() ),
                                                round_up( vol_L, 1 ) ) );
                }
            };

            selectable = is_selectable( vpr.part() );
            if( vpr.part().is_tank() ) {
                overview_opts.emplace_back( "2_TANK", &vpr.part(), selectable, selectable ? next_hotkey(
                                                hotkey ) : input_event(),
                                            tank_details );
            } else if( vpr.part().is_fuel_store() && !( vpr.part().is_turret() ||
                       vpr.part().is_battery() || vpr.part().is_reactor() ) ) {
                overview_opts.emplace_back( "2_TANK", &vpr.part(), selectable, selectable ? next_hotkey(
                                                hotkey ) : input_event(),
                                            no_tank_details );
            }
        }

        if( vpr.part().is_battery() ) {
            // always display total battery capacity and percentage charge
            auto details = []( const vehicle_part & pt, const catacurses::window & w, int y ) {
                int pct = ( static_cast<double>( pt.ammo_remaining( ) ) / pt.ammo_capacity(
                                ammo_battery ) ) * 100;
                int offset = 1;
                std::string fmtstring = "%i    %3i%%";
                if( pt.is_leaking() ) {
                    fmtstring = str_cat( "%i   ", leak_marker, "%3i%%", leak_marker );
                    offset = 0;
                }
                right_print( w, y, offset, item::find_type( pt.ammo_current() )->color,
                             string_format( fmtstring, pt.ammo_capacity( ammo_battery ), pct ) );
            };
            selectable = is_selectable( vpr.part() );
            overview_opts.emplace_back( "3_BATTERY", &vpr.part(), selectable,
                                        selectable ? next_hotkey( hotkey ) : input_event(), details );
        }

        if( vpr.part().is_reactor() || vpr.part().is_turret() ) {
            auto details_ammo = []( const vehicle_part & pt, const catacurses::window & w, int y ) {
                if( pt.ammo_remaining( ) ) {
                    int offset = 1;
                    std::string fmtstring = "%s   %5i";
                    if( pt.is_leaking() ) {
                        fmtstring = str_cat( "%s  ", leak_marker, "%5i", leak_marker );
                        offset = 0;
                    }
                    right_print( w, y, offset, item::find_type( pt.ammo_current() )->color,
                                 string_format( fmtstring, item::nname( pt.ammo_current() ), pt.ammo_remaining( ) ) );
                }
            };
            selectable = is_selectable( vpr.part() );
            if( vpr.part().is_reactor() ) {
                overview_opts.emplace_back( "4_REACTOR", &vpr.part(), selectable,
                                            selectable ? next_hotkey( hotkey ) : input_event(),
                                            details_ammo );
            }
            if( vpr.part().is_turret() ) {
                overview_opts.emplace_back( "5_TURRET", &vpr.part(), selectable,
                                            selectable ? next_hotkey( hotkey ) : input_event(),
                                            details_ammo );
            }
        }

        if( vpr.part().is_seat() ) {
            auto details = []( const vehicle_part & pt, const catacurses::window & w, int y ) {
                const npc *who = pt.crew();
                if( who ) {
                    right_print( w, y, 1, pt.passenger_id == who->getID() ? c_green : c_light_gray, who->get_name() );
                }
            };
            selectable = is_selectable( vpr.part() );
            overview_opts.emplace_back( "6_SEAT", &vpr.part(), selectable, selectable ? next_hotkey(
                                            hotkey ) : input_event(), details );
        }
    }

    auto compare = []( veh_interact::part_option & s1,
    veh_interact::part_option & s2 ) {
        // NOLINTNEXTLINE cata-use-localized-sorting
        return  s1.key <  s2.key;
    };
    std::sort( overview_opts.begin(), overview_opts.end(), compare );

}

void veh_interact::display_overview( const map &here )
{
    werase( w_list );
    std::string last;
    int y = 0;
    if( overview_offset ) {
        trim_and_print( w_list, point( 1, y ), getmaxx( w_list ) - 1,
                        c_yellow, _( "'{' to scroll up" ) );
        y++;
    }
    for( int idx = overview_offset; idx != static_cast<int>( overview_opts.size() ); ++idx ) {
        const vehicle_part &pt = *overview_opts[idx].part;

        // if this is a new section print a header row
        if( last != overview_opts[idx].key ) {
            y += last.empty() ? 0 : 1;
            overview_headers[overview_opts[idx].key]( w_list, y );
            y += 2;
            last = overview_opts[idx].key;
        }

        bool highlighted = false;
        // No action means no selecting, just highlight relevant ones
        if( overview_pos < 0 && overview_enable && !overview_action ) {
            highlighted = overview_enable( here, pt );
        } else if( overview_pos == idx ) {
            highlighted = true;
        }

        // print part name
        nc_color col = overview_opts[idx].selectable ? c_white : c_dark_gray;
        trim_and_print( w_list, point( 1, y ), getmaxx( w_list ) - 1,
                        highlighted ? hilite( col ) : col,
                        "<color_dark_gray>%s </color>%s",
                        right_justify( overview_opts[idx].hotkey.short_description(), 2 ), pt.name() );

        // print extra columns (if any)
        overview_opts[idx].details( pt, w_list, y );
        y++;
        if( y < ( getmaxy( w_list ) - 1 ) ) {
            overview_limit = overview_offset;
        } else {
            overview_limit = idx;
            trim_and_print( w_list, point( 1, y ), getmaxx( w_list ) - 1,
                            c_yellow, _( "'}' to scroll down" ) );
            break;
        }
    }

    wnoutrefresh( w_list );
}

void veh_interact::overview( map &here,
                             const overview_enable_t &enable,
                             const overview_action_t &action )
{
    restore_on_out_of_scope prev_overview_enable( overview_enable );
    restore_on_out_of_scope prev_overview_action( overview_action );
    overview_enable = enable;
    overview_action = action;

    restore_on_out_of_scope prev_overview_pos( overview_pos );

    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );

    while( true ) {
        calc_overview( here );

        if( overview_pos < 0 || static_cast<size_t>( overview_pos ) >= overview_opts.size() ) {
            overview_pos = -1;
            do {
                if( ++overview_pos >= static_cast<int>( overview_opts.size() ) ) {
                    overview_pos = -1;
                    break; // nothing could be selected
                }
            } while( !overview_opts[overview_pos].selectable );
        }

        const bool has_any_selectable_part = std::any_of( overview_opts.begin(), overview_opts.end(),
        []( const part_option & e ) {
            return e.selectable;
        } );
        if( !has_any_selectable_part ) {
            return; // nothing is selectable
        }

        if( overview_pos >= 0 && static_cast<size_t>( overview_pos ) < overview_opts.size() ) {
            move_cursor( here, ( overview_opts[overview_pos].part->mount.raw() + dd ).rotate( 3 ) );
        }

        if( overview_pos >= 0 && static_cast<size_t>( overview_pos ) < overview_opts.size() &&
            overview_opts[overview_pos].message ) {
            overview_opts[overview_pos].message( *overview_opts[overview_pos].part );
        } else {
            msg.reset();
        }

        ui_manager::redraw();

        const std::string input = main_context.handle_input();
        msg.reset();
        if( input == "CONFIRM" && overview_opts[overview_pos].selectable && overview_action ) {
            overview_action( here, *overview_opts[overview_pos].part );
            break;

        } else if( input == "QUIT" ) {
            break;

        } else if( input == "UP" ) {
            do {
                move_overview_line( -1 );
                if( --overview_pos < 0 ) {
                    overview_pos = overview_opts.size() - 1;
                }
            } while( !overview_opts[overview_pos].selectable );
        } else if( input == "DOWN" ) {
            do {
                move_overview_line( 1 );
                if( ++overview_pos >= static_cast<int>( overview_opts.size() ) ) {
                    overview_pos = 0;
                }
            } while( !overview_opts[overview_pos].selectable );
        } else if( input == "ANY_INPUT" ) {
            // did we try and activate a hotkey option?
            const input_event hotkey = main_context.get_raw_input();
            if( hotkey != input_event() && overview_action ) {
                auto iter = std::find_if( overview_opts.begin(),
                overview_opts.end(), [&hotkey]( const part_option & e ) {
                    return e.hotkey == hotkey;
                } );
                if( iter != overview_opts.end() ) {
                    overview_action( here,  *iter->part );
                    break;
                }
            }
        }
    }
}

void veh_interact::move_overview_line( int amount )
{
    overview_offset += amount;
    overview_offset = std::max( 0, overview_offset );
    overview_offset = std::min( overview_limit, overview_offset );
}

vehicle_part *veh_interact::get_most_damaged_part() const
{
    auto part_damage_comparison = []( const vpart_reference & a, const vpart_reference & b ) {
        return !b.part().removed && b.part().base.damage() > a.part().base.damage();
    };
    const vehicle_part_range vpr = veh->get_all_parts();
    auto high_damage_iterator = std::max_element( vpr.begin(),
                                vpr.end(),
                                part_damage_comparison );
    if( high_damage_iterator == vpr.end() ||
        high_damage_iterator->part().removed ) {
        return nullptr;
    }

    return &( *high_damage_iterator ).part();
}

vehicle_part *veh_interact::get_most_repairable_part() const
{
    return veh_utils::most_repairable_part( *veh, get_player_character() );
}

bool veh_interact::can_remove_part( map &here, int idx, const Character &you )
{
    sel_vehicle_part = &veh->part( idx );
    sel_vpart_info = &sel_vehicle_part->info();
    std::string nmsg;
    bool smash_remove = sel_vpart_info->has_flag( "SMASH_REMOVE" );

    if( veh->has_part( "NO_MODIFY_VEHICLE" ) && !sel_vpart_info->has_flag( "SIMPLE_PART" ) &&
        !smash_remove ) {
        msg = _( "This vehicle cannot be modified in this way.\n" );
        return false;
    } else if( sel_vpart_info->has_flag( "NO_UNINSTALL" ) ) {
        msg = _( "This part cannot be uninstalled.\n" );
        return false;
    }

    if( sel_vehicle_part->is_broken() ) {
        nmsg += string_format(
                    _( "<color_white>Removing the broken %1$s may yield some fragments.</color>\n" ),
                    sel_vehicle_part->name() );
    } else if( smash_remove ) {
        std::set<std::string> removed_names;
        for( const item &it : sel_vehicle_part->pieces_for_broken_part() ) {
            removed_names.insert( it.tname() );
        }
        nmsg += string_format( _( "<color_white>Removing the %1$s may yield:</color>\n> %2$s\n" ),
                               sel_vehicle_part->name(), enumerate_as_string( removed_names ) );
    } else {
        item result_of_removal = veh->part_to_item( here, *sel_vehicle_part );
        nmsg += string_format(
                    _( "<color_white>Removing the %1$s will yield:</color>\n> %2$s\n" ),
                    sel_vehicle_part->name(), result_of_removal.display_name() );
        for( const item &it : sel_vehicle_part->get_salvageable() ) {
            nmsg += "> " + it.display_name() + "\n";
        }
    }

    const requirement_data reqs = sel_vpart_info->removal_requirements();
    bool ok = format_reqs( nmsg, reqs, sel_vpart_info->removal_skills,
                           sel_vpart_info->removal_time( you ) );

    nmsg += _( "<color_white>Additional requirements:</color>\n" );

    std::pair<bool, std::string> res = calc_lift_requirements( here, *sel_vpart_info );
    if( !res.first ) {
        ok = res.first;
    }
    nmsg += res.second;

    const ret_val<void> unmount = veh->can_unmount( *sel_vehicle_part );
    if( !unmount.success() ) {
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is pre-translated reason
        nmsg += string_format( _( "> %1$s%2$s</color>" ), status_color( false ), unmount.str() ) + "\n";
        ok = false;
    }
    const nc_color desc_color = sel_vehicle_part->is_broken() ? c_dark_gray : c_light_gray;
    sel_vehicle_part->info().format_description( nmsg, desc_color, getmaxx( w_msg ) - 4 );

    msg = colorize( nmsg, c_light_gray );
    return ok || get_avatar().has_trait( trait_DEBUG_HS );
}

void veh_interact::do_remove( map &here )
{
    task_reason reason = cant_do( here,  'o' );

    if( reason == task_reason::INVALID_TARGET ) {
        msg = _( "No parts here." );
        return;
    }

    restore_on_out_of_scope prev_title( title );
    title = _( "Choose a part here to remove:" );

    restore_on_out_of_scope prev_remove_info( std::move(
                remove_info ) );
    remove_info = std::make_unique<remove_info_t>();

    avatar &player_character = get_avatar();
    int pos = 0;
    bool selected_remove_target = false;
    if( selected_part >= 0 ) {
        for( size_t i = 0; i < parts_here.size(); ++i ) {
            if( parts_here[i] == selected_part ) {
                pos = static_cast<int>( i );
                selected_remove_target = true;
                break;
            }
        }
    }
    if( !selected_remove_target ) {
        for( size_t i = 0; i < parts_here.size(); i++ ) {
            if( can_remove_part( here, parts_here[ i ], player_character ) ) {
                pos = i;
                break;
            }
        }
    }
    msg.reset();

    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );

    restore_on_out_of_scope prev_overview_enable( overview_enable );

    restore_on_out_of_scope prev_hilight_part( highlight_part );

    while( true ) {
        int part = parts_here[ pos ];

        bool can_remove = can_remove_part( here, part, player_character );

        overview_enable = [this, part]( const map &,  const vehicle_part & pt ) {
            return &pt == &veh->part( part );
        };

        highlight_part = pos;

        calc_overview( here );
        ui_manager::redraw();

        //read input
        const std::string action = main_context.handle_input();
        msg.reset();
        if( can_remove && ( action == "REMOVE" || action == "CONFIRM" ) ) {
            switch( reason ) {
                case task_reason::LOW_MORALE:
                    msg = _( "Your morale is too low to construct…" );
                    return;
                case task_reason::LOW_LIGHT:
                    msg = _( "It's too dark to see what you are doing…" );
                    return;
                case task_reason::NOT_FREE:
                    msg = _( "You cannot remove that part while something is attached to it." );
                    return;
                case task_reason::MOVING_VEHICLE:
                    msg = _( "Better not remove something while driving." );
                    return;
                default:
                    break;
            }

            // Modifying a vehicle with rotors will make in not flightworthy (until we've got a better model)
            // It can only be the player doing this - an npc won't work well with query_yn
            if( veh->would_removal_prevent_flyable( veh->part( part ), player_character ) ) {
                if( query_yn(
                        _( "Removing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
                    veh->set_flyable( false );
                } else {
                    return;
                }
            }
            for( const Character *helper : player_character.get_crafting_helpers() ) {
                add_msg( m_info, _( "%s helps with this task…" ), helper->get_name() );
            }
            sel_cmd = 'o';
            break;
        } else if( action == "QUIT" ) {
            break;
        } else {
            move_in_list( pos, action, parts_here.size() );
        }
    }
    veh->recalculate_enchantment_cache();
}

void veh_interact::do_siphon( map &here )
{
    switch( cant_do( here,  's' ) ) {
        case task_reason::INVALID_TARGET:
            msg = _( "The vehicle has no liquid fuel left to siphon." );
            return;

        case task_reason::LACK_TOOLS:
            msg = _( "You need a <color_red>hose</color> to siphon liquid fuel." );
            return;

        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't siphon from a moving vehicle." );
            return;

        default:
            break;
    }

    restore_on_out_of_scope prev_title( title );
    title = _( "Select part to siphon:" );

    auto sel = [&]( const map &,  const vehicle_part & pt ) {
        return pt.is_tank() && !pt.base.empty() &&
               pt.base.only_item().made_of( phase_id::LIQUID );
    };

    auto act = [&]( map & here, const vehicle_part & pt ) {
        on_out_of_scope restore_ui( [&]() {
            hide_ui( here, false );
        } );
        hide_ui( here, true );
        const item &base = pt.get_base();
        const int idx = veh->index_of_part( &pt );
        item liquid( base.legacy_front() );
        const int liq_charges = liquid.charges;
        liquid_dest_opt liquid_target;
        if( liquid_handler::handle_liquid( liquid, liquid_target, nullptr, 1, nullptr, veh, idx ) ) {
            veh->drain( here, idx, liq_charges - liquid.charges );
        }
    };

    overview( here, sel, act );
}

bool veh_interact::do_unload( map &here )
{
    switch( cant_do( here, 'd' ) ) {
        case task_reason::INVALID_TARGET:
            msg = _( "The vehicle has no solid fuel left to remove." );
            return false;

        case task_reason::MOVING_VEHICLE:
            msg = _( "You can't unload from a moving vehicle." );
            return false;

        default:
            break;
    }

    act_vehicle_unload_fuel( here, veh );
    return true;
}

static void do_change_shape_menu( vehicle_part &vp )
{
    const vpart_info &vpi = vp.info();
    uilist smenu;
    smenu.text = _( "Choose cosmetic variant:" );
    int ret_code = 0;
    int default_selection = 0;
    std::vector<std::string> variants;
    for( const auto& [variant_id, vv] : vpi.variants ) {
        if( variant_id == vp.variant ) {
            default_selection = ret_code;
        }
        uilist_entry entry( vv.get_label() );
        entry.txt = entry.txt.empty() ? _( "Default" ) : entry.txt;
        entry.retval = ret_code++;
        entry.extratxt.left = 1;
        entry.extratxt.sym = vv.get_symbol_curses( 0_degrees, false );
        entry.extratxt.color = vpi.color;
        variants.emplace_back( variant_id );
        smenu.entries.emplace_back( entry );
    }
    sort_uilist_entries_by_line_drawing( smenu.entries );

    // get default selection after sorting
    for( std::size_t i = 0; i < smenu.entries.size(); ++i ) {
        if( smenu.entries[i].retval == default_selection ) {
            default_selection = i;
            break;
        }
    }

    smenu.selected = default_selection;
    smenu.query();
    if( smenu.ret >= 0 ) {
        vp.variant = variants[smenu.ret];
    }
}

void veh_interact::do_assign_crew( map &here )
{
    if( cant_do( here,  'w' ) != task_reason::CAN_DO ) {
        msg = _( "Need at least one seat and an ally to assign crew members." );
        return;
    }

    restore_on_out_of_scope prev_title( title );
    title = _( "Assign crew positions:" );

    auto sel = []( const map &, const vehicle_part & pt ) {
        return pt.is_seat();
    };

    auto act = [&]( map &, vehicle_part & pt ) {
        uilist menu;
        menu.text = _( "Select crew member" );

        if( pt.crew() ) {
            menu.addentry( 0, true, 'c', _( "Clear assignment" ) );
        }

        for( const npc *e : g->allies() ) {
            menu.addentry( e->getID().get_value(), true, -1, e->get_name() );
        }

        menu.query();
        if( menu.ret == 0 ) {
            pt.unset_crew();
        } else if( menu.ret > 0 ) {
            const npc &who = *g->critter_by_id<npc>( character_id( menu.ret ) );
            veh->assign_seat( pt, who );
        }
    };

    overview( here, sel, act );
}

void veh_interact::do_rename()
{
    std::string name = string_input_popup()
                       .title( _( "Enter new vehicle name:" ) )
                       .width( 20 )
                       .query_string();
    if( !name.empty() ) {
        veh->name = name;
        if( veh->tracking_on ) {
            overmap_buffer.remove_vehicle( veh );
            // Add the vehicle again, this time with the new name
            overmap_buffer.add_vehicle( veh );
        }
    }
}

void veh_interact::do_relabel( const map &here )
{
    if( cant_do( here,  'a' ) == task_reason::INVALID_TARGET ) {
        msg = _( "There are no parts here to label." );
        return;
    }

    const vpart_position vp( *veh, cpart );
    string_input_popup pop;
    std::string text = pop
                       .title( _( "New label:" ) )
                       .width( 20 )
                       .text( vp.get_label().value_or( "" ) )
                       .query_string();
    if( pop.confirmed() ) {
        vp.set_label( text );
    }
}

std::pair<bool, std::string> veh_interact::calc_lift_requirements( map &here, const vpart_info
        &sel_vpart_info )
{
    int lvl = 0;
    int str = 0;
    quality_id qual;
    bool use_aid = false;
    bool use_str = false;
    bool ok = true;
    std::string nmsg;
    avatar &player_character = get_avatar();

    if( sel_vpart_info.has_flag( "NEEDS_JACKING" ) ) {
        if( terrain_here.has_flag( ter_furn_flag::TFLAG_LIQUID ) ) {
            const auto wrap_badter = foldstring(
                                         _( "<color_red>Unsuitable terrain</color> for working on part that requires jacking." ),
                                         getmaxx( w_msg ) - 4 );
            nmsg += "> " + wrap_badter[0] + "\n";
            for( size_t i = 1; i < wrap_badter.size(); i++ ) {
                nmsg += "  " + wrap_badter[i] + "\n";
            }
            return std::pair<bool, std::string> ( false, nmsg );
        }
        qual = qual_JACK;
        lvl = jack_quality( here, *veh );
        str = veh->lift_strength( here );
        use_aid = ( max_jack >= lifting_quality_to_mass( lvl ) ) || can_self_jack( here );
        use_str = player_character.can_lift( *veh, here );
    } else {
        item base( sel_vpart_info.base_item );
        qual = qual_LIFT;
        lvl = std::ceil( units::quantity<double, units::mass::unit_type>( base.weight() ) /
                         lifting_quality_to_mass( 1 ) );
        str = base.lift_strength();
        use_aid = max_lift >= base.weight();
        use_str = player_character.can_lift( base );
    }

    if( !( use_aid || use_str ) ) {
        ok = false;
    }

    std::string str_suffix;
    int lift_strength = player_character.get_lift_str();
    int total_lift_strength = lift_strength + player_character.get_lift_assist();
    int total_base_strength = player_character.get_arm_str() + player_character.get_lift_assist();

    if( player_character.has_trait( trait_STRONGBACK ) && total_lift_strength >= str &&
        total_base_strength < str ) {
        str_suffix = string_format( _( "(Strong Back helped, giving +%d strength)" ),
                                    lift_strength - player_character.get_str() );
    } else if( player_character.has_trait( trait_BADBACK ) && total_base_strength >= str &&
               total_lift_strength < str ) {
        str_suffix = string_format( _( "(Bad Back reduced usable strength by %d)" ),
                                    lift_strength - player_character.get_str() );
    }
    if( player_character.get_str() > lift_strength ) {
        str_suffix += str_suffix.empty() ? "" : "  ";
        str_suffix += string_format( _( "(Effective lifting strength is %d)" ), lift_strength );
    }

    nc_color aid_color = use_aid ? c_green : ( use_str ? c_dark_gray : c_red );
    nc_color str_color = use_str ? c_green : ( use_aid ? c_dark_gray : c_red );
    const std::vector<Character *> helpers = player_character.get_crafting_helpers();
    //~ %1$s is quality name, %2$d is quality level
    std::string aid_string = string_format( _( "1 tool with %1$s %2$d" ),
                                            qual.obj().name, lvl );

    std::string str_string;
    if( !helpers.empty() ) {
        str_string = string_format( _( "strength ( assisted ) %d %s" ), str, str_suffix );
    } else {
        str_string = string_format( _( "strength %d %s" ), str, str_suffix );
    }

    nmsg += string_format( _( "> %1$s <color_white>OR</color> %2$s" ),
                           colorize( aid_string, aid_color ),
                           colorize( str_string, str_color ) ) + "\n";

    std::pair<bool, std::string> result( ok, nmsg );
    return result;
}

/**
 * Returns the first part on the vehicle at the given position.
 * @param d The coordinates, relative to the viewport's 0-point (?)
 * @return The first vehicle part at the specified coordinates.
 */
int veh_interact::part_at( const point_rel_ms &d )
{
    const point_rel_ms vd{ -dd + d.rotate( 1 ) };
    return veh->part_displayed_at( vd );
}

/**
 * Checks to see if you can potentially install this part at current position.
 * Affects coloring in display_list() and is also used to
 * sort can_mount so potentially installable parts come first.
 */
bool veh_interact::can_potentially_install( const vpart_info &vpart )
{
    bool engine_reqs_met = true;
    bool can_make = editor_test_mode || vpart.install_requirements().can_make_with_inventory( *crafting_inv,
                    is_crafting_component, 1, craft_flags::none, false );
    bool hammerspace = get_player_character().has_trait( trait_DEBUG_HS );

    int engines = 0;
    if( vpart.has_flag( VPFLAG_ENGINE ) && vpart.has_flag( "E_HIGHER_SKILL" ) ) {
        for( const vpart_reference &vp : veh->get_avail_parts( "ENGINE" ) ) {
            if( vp.has_feature( "E_HIGHER_SKILL" ) ) {
                engines++;
            }
        }
        engine_reqs_met = engines < 2;
    }

    return hammerspace || ( can_make && engine_reqs_met && !vpart.has_flag( VPFLAG_APPLIANCE ) );
}

/**
 * Moves the cursor on the vehicle editing window.
 * @param d How far to move the cursor.
 * @param dstart_at How far to change the start position for vehicle part descriptions
 */
void veh_interact::move_cursor( map &here, const point_rel_ms &d, int dstart_at )
{
    dd += d.rotate( 3 );
    if( d != point_rel_ms::zero ) {
        start_limit = 0;
    } else {
        start_at += dstart_at;
    }

    // Update the current active component index to the new position.
    cpart = part_at( point_rel_ms::zero );
    const point_rel_ms vd = -dd;
    const point_rel_ms q = veh->coord_translate( vd );
    const tripoint_bub_ms vehp = veh->pos_bub( here ) + q;
    const bool has_critter = get_creature_tracker().creature_at( vehp );
    terrain_here = here.ter( vehp ).obj();
    bool obstruct = here.impassable_ter_furn( vehp );
    const optional_vpart_position ovp = here.veh_at( vehp );
    if( ovp && &ovp->vehicle() != veh ) {
        obstruct = true;
    }

    can_mount.clear();
    if( !obstruct ) {
        std::vector<const vpart_info *> req_missing;
        for( const vpart_info &vpi : vehicles::parts::get_all() ) {
            if( has_critter && vpi.has_flag( VPFLAG_OBSTACLE ) ) {
                continue;
            }
            if( vpi.has_flag( "NO_INSTALL_HIDDEN" ) ||
                vpi.has_flag( VPFLAG_APPLIANCE ) ) {
                continue; // hide parts with incompatible flags
            }
            if( can_potentially_install( vpi ) ) {
                can_mount.push_back( &vpi );
            } else {
                req_missing.push_back( &vpi );
            }
        }
        auto vpart_localized_sort = []( const vpart_info * a, const vpart_info * b ) {
            return localized_compare( a->name(), b->name() );
        };
        std::sort( can_mount.begin(), can_mount.end(), vpart_localized_sort );
        std::sort( req_missing.begin(), req_missing.end(), vpart_localized_sort );
        can_mount.insert( can_mount.end(), req_missing.cbegin(), req_missing.cend() );
    }

    need_repair.clear();
    parts_here.clear();
    if( cpart >= 0 ) {
        parts_here = veh->parts_at_relative( veh->part( cpart ).mount, true );
        for( size_t i = 0; i < parts_here.size(); i++ ) {
            vehicle_part &pt = veh->part( parts_here[i] );

            if( pt.is_repairable() || pt.is_broken() ) {
                need_repair.push_back( i );
            }
        }
    }

    /* Update the lifting quality to be the that is available for this newly selected tile */
    cache_tool_availability_update_lifting( vehp );

    if( d != point_rel_ms::zero ) {
        reset_part_selection();
        if( install_info ) {
            install_info->dirty = true;
        }
        if( viewport_initialized ) {
            ensure_selected_mount_visible();
        }
    }
}

point_rel_ms veh_interact::selected_mount() const
{
    return -dd;
}

point veh_interact::viewport_cell_size() const
{
    switch( viewport_zoom ) {
        case 1:
            return point( 2, 1 );
        case 3:
            return point( 6, 3 );
        case 2:
        default:
            return point( 4, 2 );
    }
}

int veh_interact::editor_viewport_top() const
{
    // Header, layer tabs, and system/condition controls occupy the top rows.
    return std::min( 3, std::max( 1, getmaxy( w_disp ) - 1 ) );
}

int veh_interact::editor_schematic_width() const
{
    const int width = getmaxx( w_disp );
    switch( active_editor_view_mode ) {
        case editor_view_mode::live:
            return 0;
        case editor_view_mode::split:
            return std::max( 1, ( width - 1 ) / 2 );
        case editor_view_mode::editor:
        default:
            return width;
    }
}

bool veh_interact::point_in_editor_schematic( const point &screen ) const
{
    const int schematic_width = editor_schematic_width();
    return schematic_width > 0 && screen.x >= 0 && screen.x < schematic_width &&
           screen.y >= editor_viewport_top() && screen.y < getmaxy( w_disp );
}

bool veh_interact::point_in_live_preview( const point &screen ) const
{
    if( screen.y < editor_viewport_top() || screen.y >= getmaxy( w_disp ) ||
        screen.x < 0 || screen.x >= getmaxx( w_disp ) ) {
        return false;
    }
    if( active_editor_view_mode == editor_view_mode::live ) {
        return true;
    }
    return active_editor_view_mode == editor_view_mode::split &&
           screen.x > editor_schematic_width();
}

point veh_interact::live_preview_cell_size() const
{
    // Match the editor's three zoom levels: 50%, 100%, and 150%.
    return point( live_preview_zoom * 2, live_preview_zoom );
}

tripoint_bub_ms veh_interact::live_preview_vehicle_center( map &here ) const
{
    int min_x = INT_MAX;
    int max_x = INT_MIN;
    int min_y = INT_MAX;
    int max_y = INT_MIN;
    bool found = false;

    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        if( vpr.part().removed ) {
            continue;
        }
        const tripoint_bub_ms pos = vpr.pos_bub( here );
        min_x = std::min( min_x, pos.x() );
        max_x = std::max( max_x, pos.x() );
        min_y = std::min( min_y, pos.y() );
        max_y = std::max( max_y, pos.y() );
        found = true;
    }

    if( !found ) {
        return veh->pos_bub( here );
    }
    const point center_xy( ( min_x + max_x ) / 2, ( min_y + max_y ) / 2 );
    return tripoint_bub_ms( point_bub_ms( center_xy ), veh->pos_bub( here ).z() );
}

point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const
{
    const point cell = viewport_cell_size();
    const int content_top = editor_viewport_top();
    const int content_height = std::max( 1, getmaxy( w_disp ) - content_top );
    const int schematic_width = std::max( 1, editor_schematic_width() );
    const point center( schematic_width / 2, content_top + content_height / 2 );

    // Use the exact live mount-to-map transform used by vehicle placement and
    // construction checks.  The editor therefore stays north-up and the vehicle
    // appears in the same direction it actually occupies in the world.
    const point grid_mount = veh->coord_translate( mount ).raw();
    const point grid_center = veh->coord_translate( viewport_center_mount ).raw();
    return center + viewport_pan + point( ( grid_mount.x - grid_center.x ) * cell.x,
                                          ( grid_mount.y - grid_center.y ) * cell.y );
}

std::optional<point_rel_ms> veh_interact::viewport_to_mount( const point &screen ) const
{
    if( !point_in_editor_schematic( screen ) ) {
        return std::nullopt;
    }

    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );
    const point cell = viewport_cell_size();
    std::optional<point_rel_ms> best_mount;
    long long best_distance = LLONG_MAX;

    for( int x = bounds.p1.x() - editor_margin; x <= bounds.p2.x() + editor_margin; ++x ) {
        for( int y = bounds.p1.y() - editor_margin; y <= bounds.p2.y() + editor_margin; ++y ) {
            const point_rel_ms mount( x, y );
            const point projected = mount_to_viewport( mount );
            const long long dx = static_cast<long long>( screen.x - projected.x ) * cell.y;
            const long long dy = static_cast<long long>( screen.y - projected.y ) * cell.x;
            const long long distance = dx * dx + dy * dy;
            if( distance < best_distance ) {
                best_distance = distance;
                best_mount = mount;
            }
        }
    }

    return best_mount;
}

void veh_interact::center_viewport_on_vehicle()
{
    const bounding_box bounds = veh->get_bounding_box( false, true );
    viewport_center_mount = point_rel_ms( ( bounds.p1.x() + bounds.p2.x() ) / 2,
                                          ( bounds.p1.y() + bounds.p2.y() ) / 2 );
    viewport_pan = point::zero;
    viewport_initialized = true;
}

void veh_interact::clamp_viewport_pan()
{
    const int schematic_width = editor_schematic_width();
    if( schematic_width <= 0 || getmaxy( w_disp ) <= editor_viewport_top() ) {
        return;
    }

    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );
    const int min_x = bounds.p1.x() - editor_margin;
    const int max_x = bounds.p2.x() + editor_margin;
    const int min_y = bounds.p1.y() - editor_margin;
    const int max_y = bounds.p2.y() + editor_margin;
    const std::array<point_rel_ms, 4> corners = { {
            point_rel_ms( min_x, min_y ), point_rel_ms( min_x, max_y ),
            point_rel_ms( max_x, min_y ), point_rel_ms( max_x, max_y )
        } };

    int min_grid_x = INT_MAX;
    int max_grid_x = INT_MIN;
    int min_grid_y = INT_MAX;
    int max_grid_y = INT_MIN;
    for( const point_rel_ms &corner : corners ) {
        const point grid = veh->coord_translate( corner ).raw();
        min_grid_x = std::min( min_grid_x, grid.x );
        max_grid_x = std::max( max_grid_x, grid.x );
        min_grid_y = std::min( min_grid_y, grid.y );
        max_grid_y = std::max( max_grid_y, grid.y );
    }

    const point grid_center = veh->coord_translate( viewport_center_mount ).raw();
    const point cell = viewport_cell_size();
    const int content_height = std::max( 1, getmaxy( w_disp ) - editor_viewport_top() );
    const point view_size( schematic_width, content_height );
    const point half( view_size.x / 2, view_size.y / 2 );

    const auto clamp_axis = []( int &pan, const int min_grid, const int max_grid,
    const int center_grid, const int pitch, const int half_view, const int view_size ) {
        const int canvas_min = ( min_grid - center_grid ) * pitch;
        const int canvas_max = ( max_grid - center_grid ) * pitch;
        const int low = pitch - half_view - canvas_max;
        const int high = view_size - pitch - half_view - canvas_min;
        if( low <= high ) {
            pan = std::clamp( pan, low, high );
        } else {
            pan = 0;
        }
    };

    clamp_axis( viewport_pan.x, min_grid_x, max_grid_x, grid_center.x, cell.x, half.x,
                view_size.x );
    clamp_axis( viewport_pan.y, min_grid_y, max_grid_y, grid_center.y, cell.y, half.y,
                view_size.y );
}

void veh_interact::ensure_selected_mount_visible()
{
    const int schematic_width = editor_schematic_width();
    if( schematic_width <= 0 ) {
        return;
    }
    const point cell = viewport_cell_size();
    const point p = mount_to_viewport( selected_mount() );
    const int left = cell.x;
    const int right = schematic_width - cell.x - 1;
    const int top = editor_viewport_top() + cell.y;
    const int bottom = getmaxy( w_disp ) - cell.y - 1;

    if( p.x < left ) {
        viewport_pan.x += left - p.x;
    } else if( p.x > right ) {
        viewport_pan.x -= p.x - right;
    }
    if( p.y < top ) {
        viewport_pan.y += top - p.y;
    } else if( p.y > bottom ) {
        viewport_pan.y -= p.y - bottom;
    }
    clamp_viewport_pan();
}

void veh_interact::select_mount( map &here, const point_rel_ms &mount )
{
    if( mount == selected_mount() ) {
        return;
    }
    dd = -mount;
    start_at = 0;
    start_limit = 0;
    w_msg_scroll_offset = 0;
    move_cursor( here, point_rel_ms::zero );
    reset_part_selection();
    if( install_info ) {
        install_info->dirty = true;
    }
}

veh_interact::editor_layer veh_interact::editor_layer_for_part( const vpart_info &vpi ) const
{
    const std::string &location = vpi.location;
    if( location == "under" || location == "engine_block" ||
        location == "on_battery_mount" || location == "fuel_source" ) {
        return editor_layer::ground;
    }
    if( location == "roof" || location == "on_roof" ) {
        return editor_layer::roof;
    }
    return editor_layer::middle;
}

bool veh_interact::part_info_matches_layer( const vpart_info &vpi ) const
{
    return active_editor_layer == editor_layer::composite ||
           editor_layer_for_part( vpi ) == active_editor_layer;
}

bool veh_interact::part_matches_layer( const vehicle_part &vp ) const
{
    return part_info_matches_layer( vp.info() );
}

veh_interact::editor_system_filter veh_interact::primary_system_for_part_info(
    const vpart_info &vpi ) const
{
    if( vpi.has_flag( "TURRET" ) || vpi.has_flag( VPFLAG_TURRET_CONTROLS ) ) {
        return editor_system_filter::turrets;
    }
    if( vpi.has_category( "passengers" ) ) {
        return editor_system_filter::passenger;
    }
    if( vpi.has_category( "cargo" ) ) {
        return editor_system_filter::storage;
    }
    if( vpi.has_category( "movement" ) && vpi.has_flag( VPFLAG_FLUIDTANK ) ) {
        return editor_system_filter::fuel;
    }
    if( vpi.has_category( "movement" ) ) {
        return editor_system_filter::propulsion;
    }
    if( vpi.has_category( "operations" ) ) {
        return editor_system_filter::controls;
    }
    if( vpi.has_category( "energy" ) ) {
        return editor_system_filter::electrical;
    }
    if( vpi.has_category( "lighting" ) ) {
        return editor_system_filter::lighting;
    }
    if( vpi.has_category( "utility" ) ) {
        return editor_system_filter::utility;
    }
    if( vpi.has_category( "hull" ) ) {
        return editor_system_filter::structural;
    }
    if( vpi.has_category( "warfare" ) ) {
        return editor_system_filter::combat;
    }
    return editor_system_filter::other;
}

veh_interact::editor_system_filter veh_interact::primary_system_for_part(
    const vehicle_part &vp ) const
{
    if( vp.is_turret() ) {
        return editor_system_filter::turrets;
    }
    return primary_system_for_part_info( vp.info() );
}

bool veh_interact::part_matches_system( const vehicle_part &vp ) const
{
    return active_system_filter == editor_system_filter::all ||
           primary_system_for_part( vp ) == active_system_filter;
}

bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
{
    if( active_condition_filter == editor_condition_filter::all ) {
        return true;
    }

    const double health = vp.health_percent();
    const bool healthy = health >= 0.999;
    const bool destroyed = vp.is_broken();
    const bool replacement = destroyed && !vp.is_repairable();
    const bool broken = destroyed && vp.is_repairable();
    const bool damaged = !destroyed && health < 0.999;

    switch( active_condition_filter ) {
        case editor_condition_filter::healthy:
            return healthy;
        case editor_condition_filter::damaged:
            return damaged;
        case editor_condition_filter::broken:
            return broken;
        case editor_condition_filter::replacement:
            return replacement;
        case editor_condition_filter::all:
        default:
            return true;
    }
}

std::string veh_interact::editor_layer_name( const editor_layer layer ) const
{
    switch( layer ) {
        case editor_layer::ground:
            return _( "Ground" );
        case editor_layer::middle:
            return _( "Middle" );
        case editor_layer::roof:
            return _( "Roof" );
        case editor_layer::composite:
        default:
            return _( "Composite" );
    }
}

std::string veh_interact::editor_system_name( const editor_system_filter filter ) const
{
    switch( filter ) {
        case editor_system_filter::structural:
            return _( "Structural" );
        case editor_system_filter::propulsion:
            return _( "Propulsion" );
        case editor_system_filter::fuel:
            return _( "Fuel" );
        case editor_system_filter::electrical:
            return _( "Electrical" );
        case editor_system_filter::storage:
            return _( "Storage" );
        case editor_system_filter::controls:
            return _( "Controls" );
        case editor_system_filter::passenger:
            return _( "Passenger" );
        case editor_system_filter::lighting:
            return _( "Lighting" );
        case editor_system_filter::utility:
            return _( "Utility" );
        case editor_system_filter::turrets:
            return _( "Turrets" );
        case editor_system_filter::combat:
            return _( "Combat" );
        case editor_system_filter::other:
            return _( "Other" );
        case editor_system_filter::all:
        default:
            return _( "All parts" );
    }
}

std::string veh_interact::editor_condition_name( const editor_condition_filter filter ) const
{
    switch( filter ) {
        case editor_condition_filter::healthy:
            return _( "Healthy" );
        case editor_condition_filter::damaged:
            return _( "Damaged" );
        case editor_condition_filter::broken:
            return _( "Broken" );
        case editor_condition_filter::replacement:
            return _( "Needs replacement" );
        case editor_condition_filter::all:
        default:
            return _( "All conditions" );
    }
}

void veh_interact::editor_filter_button_geometry( const editor_dropdown which, int &x, int &width ) const
{
    const std::string system_button = string_format( "[ %s ▼ ]", editor_system_name( active_system_filter ) );
    const int system_x = 9;
    if( which == editor_dropdown::system ) {
        x = system_x;
        width = utf8_width( system_button );
        return;
    }

    const int condition_label_x = system_x + utf8_width( system_button ) + 2;
    x = condition_label_x + utf8_width( _( "Condition: " ) );
    const std::string condition_button = string_format( "[ %s ▼ ]",
                                         editor_condition_name( active_condition_filter ) );
    width = utf8_width( condition_button );
}

void veh_interact::editor_dropdown_geometry( const editor_dropdown which, int &x, int &y,
        int &width, int &height ) const
{
    std::vector<std::string> options;
    if( which == editor_dropdown::system ) {
        for( int i = 0; i <= static_cast<int>( editor_system_filter::other ); ++i ) {
            options.push_back( editor_system_name( static_cast<editor_system_filter>( i ) ) );
        }
    } else {
        for( int i = 0; i <= static_cast<int>( editor_condition_filter::replacement ); ++i ) {
            options.push_back( editor_condition_name( static_cast<editor_condition_filter>( i ) ) );
        }
    }

    int button_width = 0;
    editor_filter_button_geometry( which, x, button_width );
    width = 4;
    for( const std::string &option : options ) {
        width = std::max( width, utf8_width( option ) + 4 );
    }
    width = std::min( width, std::max( 4, getmaxx( w_disp ) - 2 ) );
    if( x + width >= getmaxx( w_disp ) ) {
        x = std::max( 1, getmaxx( w_disp ) - width - 1 );
    }
    y = editor_viewport_top();
    height = static_cast<int>( options.size() ) + 2;
}

int veh_interact::editor_part_symbol( const vehicle_part &vp ) const
{
    const vpart_info &vpi = vp.info();
    if( vp.open && vpi.has_flag( VPFLAG_OPENABLE ) ) {
        return '\'';
    }

    auto variant = vpi.variants.find( vp.variant );
    if( variant == vpi.variants.end() ) {
        variant = vpi.variants.begin();
    }
    if( variant == vpi.variants.end() ) {
        return '?';
    }
    return variant->second.get_symbol_curses( 270_degrees - veh->face.dir(), vp.is_broken() );
}

nc_color veh_interact::editor_condition_color( const vehicle_part &vp ) const
{
    if( vp.is_broken() ) {
        return vp.is_repairable() ? c_brown : c_light_red;
    }
    if( vp.health_percent() < 0.999 ) {
        return c_yellow;
    }
    return c_light_green;
}

std::optional<std::pair<int, nc_color>> veh_interact::editor_mount_display(
    const point_rel_ms &mount ) const
{
    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );
    if( all_parts.empty() ) {
        return std::nullopt;
    }

    // Use a shape that cannot be mistaken for a normal vehicle part when a mount
    // belongs to the vehicle but is outside the current layer/filter view.
    const int ghost_symbol = 0x25A1; // U+25A1 WHITE SQUARE: occupied mount hidden by this view.
    const bool system_active = active_system_filter != editor_system_filter::all;
    const bool condition_active = active_condition_filter != editor_condition_filter::all;
    const bool filter_active = system_active || condition_active;

    const auto matches_filters = [&]( const int idx ) {
        const vehicle_part &part = veh->part( idx );
        return part_matches_system( part ) && part_matches_condition( part );
    };

    // System colors deliberately avoid green/yellow/brown/red, which are reserved
    // for health state: healthy, damaged, broken, and needs replacement.
    const auto system_color = [&]() -> nc_color {
        switch( active_system_filter ) {
            case editor_system_filter::structural:
                return c_white;
            case editor_system_filter::propulsion:
                return c_magenta;
            case editor_system_filter::fuel:
                return c_light_blue;
            case editor_system_filter::electrical:
                return c_light_cyan;
            case editor_system_filter::storage:
                return c_pink;
            case editor_system_filter::controls:
                return c_cyan;
            case editor_system_filter::passenger:
                return c_blue;
            case editor_system_filter::lighting:
                return c_light_gray;
            case editor_system_filter::utility:
                return c_magenta;
            case editor_system_filter::turrets:
                return c_cyan;
            case editor_system_filter::combat:
                return c_pink;
            case editor_system_filter::other:
                return c_light_gray;
            case editor_system_filter::all:
            default:
                return c_white;
        }
    };

    const auto filtered_color = [&]( const vehicle_part &part ) -> nc_color {
        // Condition takes precedence when both filters are active so the reserved
        // health colors always keep one unambiguous meaning.
        if( condition_active ) {
            return editor_condition_color( part );
        }
        if( system_active ) {
            return system_color();
        }
        return part.is_broken() ? part.info().color_broken : part.info().color;
    };

    if( active_editor_layer == editor_layer::composite ) {
        const int displayed = veh->part_displayed_at( mount, false );
        if( displayed < 0 ) {
            return std::nullopt;
        }
        const vpart_display shown = veh->get_display_of_tile( mount, true, false );

        // With no filters, Composite is exactly the normal in-game vehicle display.
        if( !filter_active ) {
            return std::make_pair( shown.symbol_curses, shown.color );
        }

        int best_match = -1;
        int best_match_z = INT_MIN;
        int best_match_order = INT_MIN;
        for( const int idx : all_parts ) {
            if( !matches_filters( idx ) ) {
                continue;
            }
            const vpart_info &info = veh->part( idx ).info();
            if( info.z_order > best_match_z ||
                ( info.z_order == best_match_z && info.list_order >= best_match_order ) ) {
                best_match = idx;
                best_match_z = info.z_order;
                best_match_order = info.list_order;
            }
        }
        if( best_match < 0 ) {
            return std::make_pair( ghost_symbol, c_light_gray );
        }
        const vehicle_part &match_part = veh->part( best_match );
        return std::make_pair( editor_part_symbol( match_part ), filtered_color( match_part ) );
    }

    int best_part = -1;
    int best_z = INT_MIN;
    int best_order = INT_MIN;
    for( const int idx : all_parts ) {
        const vehicle_part &part = veh->part( idx );
        if( !part_matches_layer( part ) ) {
            continue;
        }
        const vpart_info &info = part.info();
        if( info.z_order > best_z || ( info.z_order == best_z && info.list_order >= best_order ) ) {
            best_part = idx;
            best_z = info.z_order;
            best_order = info.list_order;
        }
    }

    if( best_part < 0 ) {
        return std::make_pair( ghost_symbol, c_light_gray );
    }

    const vehicle_part &part = veh->part( best_part );
    if( filter_active && !matches_filters( best_part ) ) {
        return std::make_pair( ghost_symbol, c_light_gray );
    }
    return std::make_pair( editor_part_symbol( part ), filtered_color( part ) );
}

std::vector<int> veh_interact::inspector_parts() const
{
    std::vector<int> result;
    for( const int idx : veh->parts_at_relative( selected_mount(), true, false ) ) {
        const vehicle_part &vp = veh->part( idx );
        if( part_matches_layer( vp ) && part_matches_system( vp ) && part_matches_condition( vp ) ) {
            result.push_back( idx );
        }
    }
    return result;
}

void veh_interact::reset_part_selection()
{
    const std::vector<int> parts = inspector_parts();
    const int previous_part = selected_part;
    selected_part = -1;
    if( previous_part >= 0 && std::find( parts.begin(), parts.end(), previous_part ) != parts.end() ) {
        selected_part = previous_part;
    } else if( cpart >= 0 && std::find( parts.begin(), parts.end(), cpart ) != parts.end() ) {
        selected_part = cpart;
    } else if( !parts.empty() ) {
        selected_part = parts.front();
    }
    part_scroll = 0;
    part_detail_scroll = 0;
}

void veh_interact::scroll_part_inspector( const int delta )
{
    const std::vector<int> parts = inspector_parts();
    const int visible = std::max( 1, getmaxy( w_parts ) - 3 );
    const int max_scroll = std::max( 0, static_cast<int>( parts.size() ) - visible );
    part_scroll = std::clamp( part_scroll + delta, 0, max_scroll );
}

void veh_interact::scroll_part_details( const int delta )
{
    part_detail_scroll = std::max( 0, part_detail_scroll + delta );
}

bool veh_interact::handle_editor_controls_click( const point &pos )
{
    if( pos.x < 0 || pos.x >= getmaxx( w_disp ) || pos.y < 0 || pos.y >= getmaxy( w_disp ) ) {
        return false;
    }

    if( pos.y == 0 ) {
        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{
                { editor_view_mode::editor, _( "Editor" ) },
                { editor_view_mode::live, _( "Live" ) },
                { editor_view_mode::split, _( "Split" ) }
            }};
        int total_width = 0;
        for( const auto &view : views ) {
            total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;
        }
        int x = std::max( 1, getmaxx( w_disp ) - total_width );
        for( const auto &view : views ) {
            const std::string label = string_format( "[ %s ]", view.second );
            const int label_width = utf8_width( label );
            if( pos.x >= x && pos.x < x + label_width ) {
                const editor_view_mode previous_view_mode = active_editor_view_mode;
                active_editor_view_mode = view.first;
                vehicle_editor_view_mode_latched = static_cast<int>( active_editor_view_mode );
#if defined(TILES)
                const window_dimensions full_dim = get_window_dimensions( w_live_preview_full );
                const window_dimensions split_dim = get_window_dimensions( w_live_preview_split );
                DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] mode-switch "
                                          << static_cast<int>( previous_view_mode ) << "->"
                                          << static_cast<int>( active_editor_view_mode )
                                          << " pan=(" << live_preview_pan.x << "," << live_preview_pan.y << ")"
                                          << " zoom=" << live_preview_zoom
                                          << " full_px_pos=(" << full_dim.window_pos_pixel.x << ","
                                          << full_dim.window_pos_pixel.y << ")"
                                          << " full_px_size=(" << full_dim.window_size_pixel.x << ","
                                          << full_dim.window_size_pixel.y << ")"
                                          << " split_px_pos=(" << split_dim.window_pos_pixel.x << ","
                                          << split_dim.window_pos_pixel.y << ")"
                                          << " split_px_size=(" << split_dim.window_size_pixel.x << ","
                                          << split_dim.window_size_pixel.y << ")";
#endif
                open_editor_dropdown = editor_dropdown::none;
                close_editor_context_menu();
                viewport_dragging = false;
                live_preview_dragging = false;
#if defined(TILES)
                set_sdl_mouse_capture( false );
#endif
                if( active_editor_view_mode != editor_view_mode::live ) {
                    ensure_selected_mount_visible();
                }
                return true;
            }
            x += label_width + 1;
        }
        return false;
    }

    if( pos.y == 1 ) {
        int x = utf8_width( _( "Layer: " ) ) + 1;
        for( int i = 0; i <= static_cast<int>( editor_layer::roof ); ++i ) {
            const editor_layer layer = static_cast<editor_layer>( i );
            const std::string label = string_format( "[ %s ]", editor_layer_name( layer ) );
            const int width = utf8_width( label );
            if( pos.x >= x && pos.x < x + width ) {
                active_editor_layer = layer;
                open_editor_dropdown = editor_dropdown::none;
                reset_part_selection();
                if( install_info ) {
                    install_info->dirty = true;
                }
                return true;
            }
            x += width + 1;
        }
        return true;
    }

    if( pos.y == 2 ) {
        for( const editor_dropdown which : { editor_dropdown::system, editor_dropdown::condition } ) {
            int x = 0;
            int width = 0;
            editor_filter_button_geometry( which, x, width );
            if( pos.x >= x && pos.x < x + width ) {
                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;
                close_editor_context_menu();
                return true;
            }
        }
        if( vehicle_editor_test_mode_visible ) {
            int condition_x = 0;
            int condition_width = 0;
            editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );
            const int test_x = condition_x + condition_width + 2;
            const int test_width = utf8_width( _( "[ ] Test" ) );
            if( pos.x >= test_x && pos.x < test_x + test_width ) {
                editor_test_mode = !editor_test_mode;
                vehicle_editor_test_mode_latched = editor_test_mode;
                open_editor_dropdown = editor_dropdown::none;
                close_editor_context_menu();
                if( install_info ) {
                    install_info->materials_available.clear();
                    install_info->dirty = true;
                }
                msg = editor_test_mode ?
                      _( "Test mode enabled: components, tools, and skill requirements are ignored; vehicle legality still applies." ) :
                      _( "Test mode disabled." );
                return true;
            }
        }
        return true;
    }

    if( open_editor_dropdown != editor_dropdown::none ) {
        int x = 0;
        int y = 0;
        int width = 0;
        int height = 0;
        editor_dropdown_geometry( open_editor_dropdown, x, y, width, height );
        if( pos.x >= x && pos.x < x + width && pos.y >= y && pos.y < y + height ) {
            const int option = pos.y - y - 1;
            if( option >= 0 && option < height - 2 ) {
                if( open_editor_dropdown == editor_dropdown::system ) {
                    active_system_filter = static_cast<editor_system_filter>( option );
                    if( install_info ) {
                        install_info->dirty = true;
                    }
                } else {
                    active_condition_filter = static_cast<editor_condition_filter>( option );
                }
                open_editor_dropdown = editor_dropdown::none;
                reset_part_selection();
            }
            return true;
        }
        open_editor_dropdown = editor_dropdown::none;
        return true;
    }

    return pos.y < editor_viewport_top();
}

void veh_interact::close_editor_context_menu()
{
    if( !editor_context_hover_action.empty() ) {
        msg.reset();
        w_msg_scroll_offset = 0;
    }
    editor_context_hover_action.clear();
    editor_context_open = false;
    editor_context_target = editor_context_surface::none;
    editor_context_buttons.clear();
    editor_context_width = 0;
    editor_context_height = 0;
}

void veh_interact::open_editor_context_menu( map &here, const point &pos,
        const editor_context_surface surface )
{
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    editor_context_target = surface;
    editor_context_anchor = pos;
    editor_mouse_pos = pos;

    const auto add_entry = [&]( const std::string &label, const std::string &action,
                                const bool enabled = true,
                                const std::string &disabled_reason = std::string() ) {
        editor_context_buttons.push_back( { label, point::zero, 0, action, disabled_reason, enabled } );
    };

    if( surface == editor_context_surface::viewport ) {
        add_entry( _( "Install…" ), "EDITOR_INSTALL" );
    } else if( surface == editor_context_surface::parts && selected_part >= 0 &&
               selected_part < veh->part_count() ) {
        vehicle_part &part = veh->part( selected_part );
        if( !part.removed && part.mount == selected_mount() ) {
            if( part.health_percent() < 0.999 ) {
                if( part.is_broken() ) {
                    add_entry( _( "Replace" ), "EDITOR_REPAIR" );
                } else {
                    add_entry( _( "Repair" ), "EDITOR_REPAIR", part.is_repairable(),
                               _( "This damaged part has no valid repair operation." ) );
                }
            }

            const vpart_info &vpi = part.info();
            const bool uninstallable = !vpi.has_flag( "NO_UNINSTALL" ) &&
                                       veh->can_unmount( part ).success();
            add_entry( _( "Remove" ), "EDITOR_REMOVE", uninstallable,
                       uninstallable ? std::string() :
                       _( "This part cannot be removed in the current vehicle state." ) );
        }
    }

    if( editor_context_buttons.empty() ) {
        close_editor_context_menu();
        return;
    }
    editor_context_open = true;

    const catacurses::window &target = surface == editor_context_surface::parts ? w_parts : w_disp;
    const int target_width = getmaxx( target );
    const int target_height = getmaxy( target );
    int widest = 0;
    for( const editor_context_button &button : editor_context_buttons ) {
        widest = std::max( widest, utf8_width( button.label ) );
    }
    editor_context_width = std::clamp( widest + 4, 12, std::max( 12, target_width - 2 ) );
    editor_context_height = std::min( static_cast<int>( editor_context_buttons.size() ) + 2,
                                      std::max( 3, target_height ) );
    if( static_cast<int>( editor_context_buttons.size() ) > editor_context_height - 2 ) {
        editor_context_buttons.resize( editor_context_height - 2 );
    }

    int menu_x = pos.x + 2;
    if( menu_x + editor_context_width >= target_width ) {
        menu_x = pos.x - editor_context_width - 1;
    }
    menu_x = std::clamp( menu_x, 0, std::max( 0, target_width - editor_context_width ) );

    const int min_y = surface == editor_context_surface::viewport ? editor_viewport_top() : 0;
    int menu_y = pos.y;
    if( menu_y + editor_context_height > target_height ) {
        menu_y = target_height - editor_context_height;
    }
    menu_y = std::clamp( menu_y, min_y,
                         std::max( min_y, target_height - editor_context_height ) );
    editor_context_pos = point( menu_x, menu_y );
}

bool veh_interact::set_editor_repair_requirements( map &here, vehicle_part &part )
{
    avatar &player_character = get_avatar();
    const vpart_info &vpi = part.info();
    std::string nmsg;
    bool ok = true;
    if( part.is_broken() ) {
        ok = format_reqs( nmsg, vpi.install_requirements(), vpi.install_skills,
                          vpi.install_time( player_character ) );
        if( vpi.has_flag( "NEEDS_JACKING" ) ) {
            nmsg += _( "<color_white>Additional requirements:</color>\n" );
            const std::pair<bool, std::string> res = calc_lift_requirements( here, vpi );
            ok = ok && res.first;
            nmsg += res.second;
        }
        if( part.has_flag( vp_flag::carried_flag ) ) {
            nmsg += colorize( _( "\nUnracking is required before replacing this part.\n" ), c_red );
            ok = false;
        }
    } else if( !part.is_repairable() ) {
        nmsg += colorize( _( "This part cannot be repaired.\n" ), c_light_red );
        ok = false;
    } else if( veh->has_part( "NO_MODIFY_VEHICLE" ) && !vpi.has_flag( "SIMPLE_PART" ) ) {
        nmsg += colorize( _( "This vehicle cannot be repaired.\n" ), c_light_red );
        ok = false;
    } else {
        const int levels = part.base.repairable_levels();
        ok = format_reqs( nmsg, vpi.repair_requirements() * levels, vpi.repair_skills,
                          vpi.repair_time( player_character ) * levels );
    }

    const bool would_prevent_flying = veh->would_repair_prevent_flyable( part, player_character );
    if( would_prevent_flying &&
        !player_character.has_proficiency( proficiency_prof_aircraft_mechanic ) ) {
        nmsg += string_format(
                    _( "\n<color_yellow>You require the \"%s\" proficiency to repair this part safely!</color>\n\n" ),
                    proficiency_prof_aircraft_mechanic->name() );
    }
    const nc_color desc_color = part.is_broken() ? c_dark_gray : c_light_gray;
    vpi.format_description( nmsg, desc_color, getmaxx( w_msg ) - 4 );
    msg = colorize( nmsg, c_light_gray );
    return ok;
}

void veh_interact::update_editor_context_hover( map &here )
{
    if( !editor_context_open ) {
        return;
    }

    const editor_context_button *hovered = nullptr;
    for( const editor_context_button &button : editor_context_buttons ) {
        if( editor_mouse_pos.y == button.pos.y && editor_mouse_pos.x >= button.pos.x &&
            editor_mouse_pos.x < button.pos.x + button.width ) {
            hovered = &button;
            break;
        }
    }

    const std::string new_action = hovered != nullptr ? hovered->action : std::string();
    if( new_action == editor_context_hover_action ) {
        return;
    }

    const bool had_preview = !editor_context_hover_action.empty();
    editor_context_hover_action = new_action;
    w_msg_scroll_offset = 0;

    if( hovered == nullptr || ( hovered->action != "EDITOR_REMOVE" &&
                                hovered->action != "EDITOR_REPAIR" ) ) {
        if( had_preview ) {
            msg.reset();
        }
        return;
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return;
    }

    if( hovered->action == "EDITOR_REPAIR" ) {
        set_editor_repair_requirements( here, part );
        return;
    }

    // can_remove_part already owns the canonical removal requirements display,
    // including tools, skills, time, lifting/jacking and can_unmount reasons.
    // It historically updates command-side pointers, so preserve them while
    // using it as a read-only hover preview.
    const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
    const vpart_info *old_sel_vpart_info = sel_vpart_info;
    can_remove_part( here, selected_part, get_avatar() );
    sel_vehicle_part = old_sel_vehicle_part;
    sel_vpart_info = old_sel_vpart_info;
}

bool veh_interact::run_editor_context_action( map &here, const std::string &action )
{
    // Context-menu actions are stored in editor_context_buttons.  The menu is
    // destroyed before dispatch, so preserve the selected action before clearing
    // that vector.  Otherwise `action` can refer to a destroyed std::string.
    const std::string selected_action = action;
    close_editor_context_menu();

    if( selected_action == "EDITOR_INSTALL" ) {
        if( veh->handle_potential_theft( get_player_character() ) ) {
            do_install( here );
        }
        return sel_cmd == ' ';
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return true;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return true;
    }
    if( !veh->handle_potential_theft( get_player_character() ) ) {
        return true;
    }

    avatar &player_character = get_avatar();

    if( selected_action == "EDITOR_REMOVE" ) {
        const task_reason reason = cant_do( here, 'o' );
        switch( reason ) {
            case task_reason::LOW_MORALE:
                msg = _( "Your morale is too low to construct…" );
                return true;
            case task_reason::LOW_LIGHT:
                msg = _( "It's too dark to see what you are doing…" );
                return true;
            case task_reason::MOVING_VEHICLE:
                msg = _( "Better not remove something while driving." );
                return true;
            default:
                break;
        }

        // can_remove_part validates the exact stacked part selected in the inspector;
        // cant_do('o') only knows about the mount's legacy displayed part.
        if( !can_remove_part( here, selected_part, player_character ) ) {
            return true;
        }
        if( veh->would_removal_prevent_flyable( part, player_character ) ) {
            if( query_yn(
                    _( "Removing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
                veh->set_flyable( false );
            } else {
                return true;
            }
        }
        for( const Character *helper : player_character.get_crafting_helpers() ) {
            add_msg( m_info, _( "%s helps with this task…" ), helper->get_name() );
        }
        sel_vehicle_part = &part;
        sel_vpart_info = &part.info();
        sel_cmd = 'o';
        veh->recalculate_enchantment_cache();
        return false;
    }

    if( selected_action == "EDITOR_REPAIR" ) {
        const task_reason reason = cant_do( here, 'r' );
        switch( reason ) {
            case task_reason::LOW_MORALE:
                msg = _( "Your morale is too low to repair…" );
                return true;
            case task_reason::LOW_LIGHT:
                msg = _( "It's too dark to see what you are doing…" );
                return true;
            case task_reason::MOVING_VEHICLE:
                msg = _( "You can't repair stuff while driving." );
                return true;
            case task_reason::INVALID_TARGET:
                msg = _( "This part does not need repair." );
                return true;
            default:
                break;
        }

        const vpart_info &vpi = part.info();
        if( !set_editor_repair_requirements( here, part ) ) {
            return true;
        }
        const bool would_prevent_flying = veh->would_repair_prevent_flyable( part, player_character );

        if( would_prevent_flying ) {
            if( query_yn(
                    _( "Repairing this part will mean that this vehicle is no longer flightworthy.  Continue?" ) ) ) {
                veh->set_flyable( false );
            } else {
                return true;
            }
        }
        sel_vehicle_part = &part;
        sel_vpart_info = &vpi;
        for( const Character *helper : player_character.get_crafting_helpers() ) {
            add_msg( m_info, _( "%s helps with this task…" ), helper->get_name() );
        }
        sel_cmd = 'r';
        return false;
    }

    return true;
}

bool veh_interact::handle_editor_context_click( map &here, const point &pos )
{
    if( !editor_context_open ) {
        return false;
    }
    for( const editor_context_button &button : editor_context_buttons ) {
        if( pos.y == button.pos.y && pos.x >= button.pos.x && pos.x < button.pos.x + button.width ) {
            if( !button.enabled ) {
                msg = button.disabled_reason.empty() ? _( "That action is not available." ) : button.disabled_reason;
                return true;
            }
            return run_editor_context_action( here, button.action );
        }
    }
    close_editor_context_menu();
    return true;
}

void veh_interact::display_editor_context_menu()
{
    if( !editor_context_open || editor_context_target == editor_context_surface::none ||
        editor_context_width <= 0 || editor_context_height < 3 ) {
        return;
    }

    catacurses::window &target = editor_context_target == editor_context_surface::parts ? w_parts : w_disp;
    const std::string blank( editor_context_width, ' ' );
    for( int row = 0; row < editor_context_height; ++row ) {
        mvwprintz( target, editor_context_pos + point( 0, row ), c_black, "%s", blank );
    }
    mvwhline( target, editor_context_pos, c_light_gray, LINE_OXOX, editor_context_width );
    mvwhline( target, editor_context_pos + point( 0, editor_context_height - 1 ), c_light_gray,
              LINE_OXOX, editor_context_width );
    mvwvline( target, editor_context_pos, c_light_gray, LINE_XOXO, editor_context_height );
    mvwvline( target, editor_context_pos + point( editor_context_width - 1, 0 ), c_light_gray,
              LINE_XOXO, editor_context_height );
    mvwputch( target, editor_context_pos, c_light_gray, LINE_OXXO );
    mvwputch( target, editor_context_pos + point( editor_context_width - 1, 0 ), c_light_gray, LINE_OOXX );
    mvwputch( target, editor_context_pos + point( 0, editor_context_height - 1 ), c_light_gray, LINE_XXOO );
    mvwputch( target, editor_context_pos + point( editor_context_width - 1,
             editor_context_height - 1 ), c_light_gray, LINE_XOOX );

    for( int row = 0; row < static_cast<int>( editor_context_buttons.size() ); ++row ) {
        editor_context_button &button = editor_context_buttons[row];
        button.pos = editor_context_pos + point( 1, row + 1 );
        button.width = editor_context_width - 2;
        const bool hovered = editor_mouse_pos.y == button.pos.y &&
                             editor_mouse_pos.x >= button.pos.x &&
                             editor_mouse_pos.x < button.pos.x + button.width;
        const nc_color color = !button.enabled ? c_dark_gray : hovered ? h_green : c_light_green;
        trim_and_print( target, button.pos, button.width, color, button.label );
    }
    wnoutrefresh( target );
}

bool veh_interact::handle_editor_mouse( map &here, const std::string &action )
{
    const auto mouse_pos_in = [&]( const catacurses::window & win ) -> std::optional<point> {
        const std::optional<point> pos = main_context.get_coordinates_text( win );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( win ) ||
            pos->y >= getmaxy( win ) ) {
            return std::nullopt;
        }
        return pos;
    };

    const std::optional<point> mode_pos = mouse_pos_in( w_mode );
    const std::optional<point> viewport_pos = mouse_pos_in( w_disp );
    const std::optional<point> parts_pos = mouse_pos_in( w_parts );
    const std::optional<point> list_pos = mouse_pos_in( w_list );
    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );

    // The toolbar is a first-class pane.  If a click chooses a command it stores
    // the existing VEH_INTERACT action ID in pending_editor_action; return false
    // immediately so do_main_loop() dispatches that action through the normal
    // keyboard/backend path instead of adding mouse-only vehicle mechanics.
    if( action == "MOUSE_MOVE" || mode_pos || editor_toolbar_hover_button >= 0 ) {
        const bool toolbar_handled = handle_editor_toolbar_mouse( here, action, mode_pos );
        if( !pending_editor_action.empty() ) {
            return false;
        }
        if( toolbar_handled ) {
            return true;
        }
    }

    if( refuel_info ) {
        return handle_refuel_mouse( here, action );
    }

    if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    } else if( editor_context_target == editor_context_surface::parts && parts_pos ) {
        editor_mouse_pos = *parts_pos;
    } else if( viewport_pos ) {
        editor_mouse_pos = *viewport_pos;
    }

    if( action == "MOUSE_MOVE" && editor_context_open ) {
        update_editor_context_hover( here );
        return true;
    }

#if defined(TILES)
    const bool middle_mouse_down = is_middle_mouse_button_down();
    const bool mouse_focused = has_sdl_mouse_focus();
    if( ( viewport_dragging || live_preview_dragging ) && ( !middle_mouse_down || !mouse_focused ) ) {
        viewport_dragging = false;
        live_preview_dragging = false;
        set_sdl_mouse_capture( false );
    }
    if( action == "MOUSE_MOVE" && !viewport_dragging && !live_preview_dragging &&
        middle_mouse_down && mouse_focused && open_editor_dropdown == editor_dropdown::none &&
        !editor_context_open ) {
        if( over_live_preview ) {
            live_preview_dragging = true;
            live_preview_drag_anchor = *viewport_pos;
            live_preview_drag_pan_origin = live_preview_pan;
            set_sdl_mouse_capture( true );
            return true;
        }
        if( over_schematic_content ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
            set_sdl_mouse_capture( true );
            return true;
        }
    }
#endif

    if( action == "CAMERA_PAN_START" ) {
        if( open_editor_dropdown != editor_dropdown::none || editor_context_open || !viewport_pos ) {
            return false;
        }
        if( over_live_preview ) {
            live_preview_dragging = true;
            live_preview_drag_anchor = *viewport_pos;
            live_preview_drag_pan_origin = live_preview_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        if( over_schematic_content ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        return false;
    }
    if( action == "CAMERA_PAN_END" ) {
        if( viewport_dragging || live_preview_dragging ) {
            viewport_dragging = false;
            live_preview_dragging = false;
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            return true;
        }
#if defined(TILES)
        set_sdl_mouse_capture( false );
#endif
        return false;
    }
    if( action == "MOUSE_MOVE" && live_preview_dragging ) {
        if( viewport_pos ) {
            const point delta = *viewport_pos - live_preview_drag_anchor;
            const point cell = live_preview_cell_size();
            const auto rounded_div = []( const int value, const int divisor ) {
                if( value >= 0 ) {
                    return ( value + divisor / 2 ) / divisor;
                }
                return -( ( -value + divisor / 2 ) / divisor );
            };
            live_preview_pan = live_preview_drag_pan_origin -
                               point( rounded_div( delta.x, std::max( 1, cell.x ) ),
                                      rounded_div( delta.y, std::max( 1, cell.y ) ) );
        }
        return true;
    }
    if( action == "MOUSE_MOVE" && viewport_dragging ) {
        if( viewport_pos ) {
            viewport_pan = viewport_drag_pan_origin + ( *viewport_pos - viewport_drag_anchor );
            clamp_viewport_pan();
        }
        return true;
    }

    if( action == "SEC_SELECT" && !remove_info ) {
        close_editor_context_menu();

        if( !install_info && parts_pos ) {
            if( parts_pos->y >= 3 ) {
                const std::vector<int> parts = inspector_parts();
                const int row = part_scroll + parts_pos->y - 3;
                if( row >= 0 && row < static_cast<int>( parts.size() ) ) {
                    selected_part = parts[row];
                    part_detail_scroll = 0;
                    open_editor_context_menu( here, *parts_pos, editor_context_surface::parts );
                }
            }
            return true;
        }

        if( over_schematic_content ) {
            if( const std::optional<point_rel_ms> mount = viewport_to_mount( *viewport_pos ) ) {
                select_mount( here, *mount );
                open_editor_context_menu( here, *viewport_pos, editor_context_surface::viewport );
            }
            return true;
        }
        return install_info && list_pos;
    }

    if( action == "SELECT" && !remove_info ) {
        if( editor_context_open ) {
            if( editor_context_target == editor_context_surface::viewport && viewport_pos ) {
                return handle_editor_context_click( here, *viewport_pos );
            }
            if( editor_context_target == editor_context_surface::parts && parts_pos ) {
                return handle_editor_context_click( here, *parts_pos );
            }
            close_editor_context_menu();
            return true;
        }

        if( viewport_pos && handle_editor_controls_click( *viewport_pos ) ) {
            return true;
        }
        if( open_editor_dropdown != editor_dropdown::none ) {
            open_editor_dropdown = editor_dropdown::none;
            return true;
        }
        if( over_schematic_content ) {
            if( const std::optional<point_rel_ms> mount = viewport_to_mount( *viewport_pos ) ) {
                select_mount( here, *mount );
            }
            return true;
        }

        if( install_info && list_pos ) {
            const int width = getmaxx( w_list );
            const std::string install_button = _( "[ Install ]" );
            const std::string close_button = _( "[ Close ]" );
            const int close_width = utf8_width( close_button );
            const int install_width = utf8_width( install_button );
            const int close_x = std::max( 1, width - close_width - 1 );
            const int install_x = std::max( 1, close_x - install_width - 1 );

            if( list_pos->y == 1 ) {
                string_input_popup()
                .title( _( "Search installable parts" ) )
                .width( 50 )
                .description( _( "Search" ) )
                .max_length( 100 )
                .edit( install_info->filter );
                install_search_cache = install_info->filter;
                install_info->pos = 0;
                install_info->dirty = true;
                refresh_install_candidates();
                sync_install_selection( here );
                return true;
            }

            if( list_pos->y == 2 ) {
                if( list_pos->x >= close_x ) {
                    close_install_mode();
                    return true;
                }
                if( list_pos->x >= install_x && list_pos->x < close_x ) {
                    confirm_install( here );
                    return true;
                }

                const std::string availability_label = install_info->available_materials_only ?
                                                       _( "[x] Materials" ) : _( "[ ] Materials" );
                const std::string show_all_label = install_info->show_all ?
                                                   _( "[x] Show all" ) : _( "[ ] Show all" );
                const int availability_x = 1;
                const int show_all_x = availability_x + utf8_width( availability_label ) + 1;
                if( list_pos->x >= availability_x &&
                    list_pos->x < availability_x + utf8_width( availability_label ) ) {
                    install_info->available_materials_only = !install_info->available_materials_only;
                    install_available_materials_only_cache = install_info->available_materials_only;
                } else if( list_pos->x >= show_all_x &&
                           list_pos->x < show_all_x + utf8_width( show_all_label ) ) {
                    install_info->show_all = !install_info->show_all;
                    install_show_all_cache = install_info->show_all;
                } else {
                    return true;
                }
                install_info->pos = 0;
                install_info->dirty = true;
                refresh_install_candidates();
                sync_install_selection( here );
                return true;
            }

            constexpr int first_row = 4;
            if( list_pos->y >= first_row ) {
                const int lines_per_page = std::max( 1, getmaxy( w_list ) - first_row );
                const int page = install_info->pos / lines_per_page;
                const int row = page * lines_per_page + list_pos->y - first_row;
                if( row >= 0 && row < static_cast<int>( install_info->tab_vparts.size() ) ) {
                    const vpart_info *const clicked_part = install_info->tab_vparts[row];
                    const std::string clicked_id = clicked_part != nullptr ? clicked_part->id.str() : std::string();
                    const auto now = std::chrono::steady_clock::now();
                    const bool double_click = !clicked_id.empty() &&
                                              install_info->last_clicked_part == clicked_id &&
                                              install_info->last_click_time.has_value() &&
                                              now - *install_info->last_click_time <= std::chrono::milliseconds( 500 );

                    install_info->pos = row;
                    sync_install_selection( here );

                    if( double_click ) {
                        install_info->last_clicked_part.clear();
                        install_info->last_click_time.reset();
                        confirm_install( here );
                    } else {
                        install_info->last_clicked_part = clicked_id;
                        install_info->last_click_time = now;
                    }
                }
                return true;
            }
            return true;
        }

        if( !install_info && parts_pos && parts_pos->y >= 3 ) {
            const std::vector<int> parts = inspector_parts();
            const int row = part_scroll + parts_pos->y - 3;
            if( row >= 0 && row < static_cast<int>( parts.size() ) ) {
                selected_part = parts[row];
                part_detail_scroll = 0;
            }
            return true;
        }
    }

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        if( open_editor_dropdown != editor_dropdown::none || editor_context_open ) {
            return true;
        }
        const int direction = action == "SCROLL_UP" ? -1 : 1;
#if defined(TILES)
        {
            const input_event raw_input = main_context.get_raw_input();
            DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] wheel-route action=" << action
                                      << " mode=" << static_cast<int>( active_editor_view_mode )
                                      << " viewport=" << ( viewport_pos.has_value() ? 1 : 0 )
                                      << " schematic=" << over_schematic_content
                                      << " live=" << over_live_preview
                                      << " list=" << ( list_pos.has_value() ? 1 : 0 )
                                      << " parts=" << ( parts_pos.has_value() ? 1 : 0 )
                                      << " details=" << ( details_pos.has_value() ? 1 : 0 )
                                      << " raw_type=" << static_cast<int>( raw_input.type )
                                      << " raw_mouse=(" << raw_input.mouse_pos.x << ","
                                      << raw_input.mouse_pos.y << ")";
            if( viewport_pos ) {
                DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] wheel-route viewport_cell=("
                                          << viewport_pos->x << "," << viewport_pos->y << ")";
            }
        }
#endif

        if( install_info && list_pos ) {
            if( !install_info->tab_vparts.empty() ) {
                install_info->pos = std::clamp(
                                        install_info->pos + direction, 0,
                                        static_cast<int>( install_info->tab_vparts.size() ) - 1 );
                sync_install_selection( here );
            }
            return true;
        }
        if( install_info && details_pos ) {
            w_msg_scroll_offset = std::max( 0, w_msg_scroll_offset + direction );
            return true;
        }
        if( !install_info && parts_pos ) {
            scroll_part_inspector( direction );
            return true;
        }
        if( !install_info && details_pos ) {
            scroll_part_details( direction );
            return true;
        }
        if( over_live_preview ) {
            // Preserve the exact map square beneath the cursor across either
            // zoom direction. Re-project at the new renderer scale rather than
            // assuming the auxiliary preview follows the terrain camera ratio.
            // Pane routing above remains authoritative.
#if defined(TILES)
            catacurses::window &preview = active_editor_view_mode == editor_view_mode::live ?
                                          w_live_preview_full : w_live_preview_split;
            const int old_zoom = live_preview_zoom;
            const int new_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );
            const input_event raw_input = main_context.get_raw_input();
            const window_dimensions dim = get_window_dimensions( preview );
            const point local_pixel = raw_input.mouse_pos - dim.window_pos_pixel;
            const tripoint_bub_ms vehicle_center = live_preview_vehicle_center( here );
            const tripoint_bub_ms old_center = vehicle_center +
                    tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );

            std::optional<tripoint_bub_ms> old_cursor_map;
            std::optional<tripoint_bub_ms> new_cursor_map_same_center;
            if( raw_input.type == input_event_t::mouse && new_zoom != old_zoom ) {
                old_cursor_map = map_preview_pixel_to_map( preview, local_pixel, old_center,
                                 old_zoom * 8 );
                new_cursor_map_same_center = map_preview_pixel_to_map( preview, local_pixel, old_center,
                                             new_zoom * 8 );
            }

            point camera_delta = point::zero;
            live_preview_zoom = new_zoom;
            if( old_cursor_map && new_cursor_map_same_center ) {
                camera_delta.x = old_cursor_map->x() - new_cursor_map_same_center->x();
                camera_delta.y = old_cursor_map->y() - new_cursor_map_same_center->y();
                live_preview_pan += camera_delta;
            }

            const tripoint_bub_ms new_center = vehicle_center +
                    tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );
            std::optional<tripoint_bub_ms> verified_cursor_map;
            if( raw_input.type == input_event_t::mouse ) {
                verified_cursor_map = map_preview_pixel_to_map( preview, local_pixel, new_center,
                                      live_preview_zoom * 8 );
            }

            DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] zoom-exact action=" << action
                                      << " mode=" << static_cast<int>( active_editor_view_mode )
                                      << " zoom=" << old_zoom << "->" << new_zoom
                                      << " raw_mouse=(" << raw_input.mouse_pos.x << ","
                                      << raw_input.mouse_pos.y << ")"
                                      << " local_px=(" << local_pixel.x << "," << local_pixel.y << ")"
                                      << " old_center=(" << old_center.x() << "," << old_center.y() << ")"
                                      << " delta=(" << camera_delta.x << "," << camera_delta.y << ")"
                                      << " new_center=(" << new_center.x() << "," << new_center.y() << ")";
            if( old_cursor_map ) {
                DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] zoom-anchor before=("
                                          << old_cursor_map->x() << "," << old_cursor_map->y() << ")"
                                          << " same_center_after=("
                                          << ( new_cursor_map_same_center ? new_cursor_map_same_center->x() : 0 )
                                          << ","
                                          << ( new_cursor_map_same_center ? new_cursor_map_same_center->y() : 0 )
                                          << ") verified=("
                                          << ( verified_cursor_map ? verified_cursor_map->x() : 0 ) << ","
                                          << ( verified_cursor_map ? verified_cursor_map->y() : 0 ) << ")";
            }
#else
            live_preview_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );
#endif
            return true;
        }
        if( over_schematic_content ) {
            const std::optional<point_rel_ms> anchor = viewport_to_mount( *viewport_pos );
            const int old_zoom = viewport_zoom;
            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 3 );
            if( viewport_zoom != old_zoom && anchor ) {
                const point after = mount_to_viewport( *anchor );
                viewport_pan += *viewport_pos - after;
                clamp_viewport_pan();
            }
            return true;
        }
    }

    return false;
}

void veh_interact::display_grid()
{
    werase( w_border );
    draw_border( w_border );
    wattron( w_border, BORDER_COLOR );

    const int grid_w = getmaxx( w_border ) - 2;
    const int top_y = getmaxy( w_mode ) + 1;
    const int main_y = top_y + 1;
    const int bottom_y = main_y + page_size;
    const int split_x = getmaxx( w_disp ) + 1;
    const int inspector_split_y = getbegy( w_msg ) - 1;

    mvwhline( w_border, point( 1, top_y ), LINE_OXOX, grid_w );
    mvwhline( w_border, point( 1, bottom_y ), LINE_OXOX, grid_w );
    mvwvline( w_border, point( split_x, main_y ), LINE_XOXO, page_size );
    mvwhline( w_border, point( split_x + 1, inspector_split_y ), LINE_OXOX,
              std::max( 0, TERMX - split_x - 2 ) );

    mvwaddch( w_border, point( 0, top_y ), LINE_XXXO );
    mvwaddch( w_border, point( TERMX - 1, top_y ), LINE_XOXX );
    mvwaddch( w_border, point( 0, bottom_y ), LINE_XXXO );
    mvwaddch( w_border, point( TERMX - 1, bottom_y ), LINE_XOXX );
    mvwaddch( w_border, point( split_x, top_y ), LINE_OXXX );
    mvwaddch( w_border, point( split_x, bottom_y ), LINE_XXOX );
    mvwaddch( w_border, point( split_x, inspector_split_y ), LINE_XXXO );
    mvwaddch( w_border, point( TERMX - 1, inspector_split_y ), LINE_XOXX );

    wattroff( w_border, BORDER_COLOR );
    wnoutrefresh( w_border );
}

/**
 * Draws the primary vehicle editor viewport.
 */
void veh_interact::display_editor_controls()
{
    const int width = getmaxx( w_disp );
    if( width <= 2 ) {
        return;
    }

    // View-mode tabs live at the top-right of the editor pane.  The renderer
    // itself is switched separately; this state is shared by the forthcoming
    // Editor / Live / Split viewport implementations.
    const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{
            { editor_view_mode::editor, _( "Editor" ) },
            { editor_view_mode::live, _( "Live" ) },
            { editor_view_mode::split, _( "Split" ) }
        }};
    int view_total_width = 0;
    for( const auto &view : views ) {
        view_total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;
    }
    int view_x = std::max( 1, width - view_total_width );
    for( const auto &view : views ) {
        const std::string label = string_format( "[ %s ]", view.second );
        const int label_width = utf8_width( label );
        if( view_x < width - 1 ) {
            trim_and_print( w_disp, point( view_x, 0 ), std::max( 1, width - view_x - 1 ),
                            view.first == active_editor_view_mode ? h_light_cyan : c_light_cyan,
                            label );
        }
        view_x += label_width + 1;
    }

    // Layer tabs: persistent and directly clickable because there are only four.
    mvwprintz( w_disp, point( 1, 1 ), c_light_gray, _( "Layer: " ) );
    int layer_x = utf8_width( _( "Layer: " ) ) + 1;
    for( int i = 0; i <= static_cast<int>( editor_layer::roof ); ++i ) {
        const editor_layer layer = static_cast<editor_layer>( i );
        const std::string label = string_format( "[ %s ]", editor_layer_name( layer ) );
        const nc_color color = layer == active_editor_layer ? h_light_cyan : c_light_cyan;
        const int label_width = utf8_width( label );
        if( layer_x < width - 1 ) {
            trim_and_print( w_disp, point( layer_x, 1 ), std::max( 1, width - layer_x - 1 ), color, label );
        }
        layer_x += label_width + 1;
    }

    mvwprintz( w_disp, point( 1, 2 ), c_light_gray, _( "System: " ) );
    int system_x = 0;
    int system_width = 0;
    editor_filter_button_geometry( editor_dropdown::system, system_x, system_width );
    const std::string system_button = string_format( "[ %s ▼ ]",
                                      editor_system_name( active_system_filter ) );
    if( system_x < width - 1 ) {
        trim_and_print( w_disp, point( system_x, 2 ), std::max( 1, width - system_x - 1 ),
                        open_editor_dropdown == editor_dropdown::system ? h_light_cyan : c_light_cyan,
                        system_button );
    }

    const int condition_label_x = system_x + system_width + 2;
    if( condition_label_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_label_x, 2 ), std::max( 1, width - condition_label_x - 1 ),
                        c_light_gray, _( "Condition: " ) );
    }
    int condition_x = 0;
    int condition_width = 0;
    editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );
    const std::string condition_button = string_format( "[ %s ▼ ]",
                                         editor_condition_name( active_condition_filter ) );
    if( condition_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),
                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,
                        condition_button );
    }

    if( vehicle_editor_test_mode_visible ) {
        const int test_x = condition_x + condition_width + 2;
        const std::string test_label = editor_test_mode ? _( "[x] Test" ) : _( "[ ] Test" );
        if( test_x < width - 1 ) {
            trim_and_print( w_disp, point( test_x, 2 ), std::max( 1, width - test_x - 1 ),
                            editor_test_mode ? h_light_red : c_light_gray, test_label );
        }
    }

    if( open_editor_dropdown == editor_dropdown::none ) {
        return;
    }

    int x = 0;
    int y = 0;
    int dropdown_width = 0;
    int dropdown_height = 0;
    editor_dropdown_geometry( open_editor_dropdown, x, y, dropdown_width, dropdown_height );
    const int max_height = std::max( 0, getmaxy( w_disp ) - y );
    dropdown_height = std::min( dropdown_height, max_height );
    if( dropdown_height < 3 ) {
        return;
    }

    const std::string blank( dropdown_width, ' ' );
    for( int row = 0; row < dropdown_height; ++row ) {
        trim_and_print( w_disp, point( x, y + row ), dropdown_width, c_black, blank );
    }
    wattron( w_disp, c_light_cyan );
    mvwhline( w_disp, point( x, y ), LINE_OXOX, dropdown_width );
    mvwhline( w_disp, point( x, y + dropdown_height - 1 ), LINE_OXOX, dropdown_width );
    mvwvline( w_disp, point( x, y ), LINE_XOXO, dropdown_height );
    mvwvline( w_disp, point( x + dropdown_width - 1, y ), LINE_XOXO, dropdown_height );
    wattroff( w_disp, c_light_cyan );
    mvwputch( w_disp, point( x, y ), c_light_cyan, LINE_OXXO );
    mvwputch( w_disp, point( x + dropdown_width - 1, y ), c_light_cyan, LINE_OOXX );
    mvwputch( w_disp, point( x, y + dropdown_height - 1 ), c_light_cyan, LINE_XXOO );
    mvwputch( w_disp, point( x + dropdown_width - 1, y + dropdown_height - 1 ),
              c_light_cyan, LINE_XOOX );

    const int option_count = dropdown_height - 2;
    for( int i = 0; i < option_count; ++i ) {
        std::string option;
        bool selected = false;
        if( open_editor_dropdown == editor_dropdown::system ) {
            const editor_system_filter filter = static_cast<editor_system_filter>( i );
            option = editor_system_name( filter );
            selected = filter == active_system_filter;
        } else {
            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );
            option = editor_condition_name( filter );
            selected = filter == active_condition_filter;
        }
        trim_and_print( w_disp, point( x + 2, y + 1 + i ), std::max( 1, dropdown_width - 4 ),
                        selected ? h_light_cyan : c_light_gray, option );
    }
}

/**
 * Draws the primary vehicle editor viewport.
 */
void veh_interact::display_veh( map &here )
{
    werase( w_disp );
    if( !viewport_initialized ) {
        center_viewport_on_vehicle();
    }
    clamp_viewport_pan();

    const int schematic_width = editor_schematic_width();
    const point cell = viewport_cell_size();
    const int content_top = editor_viewport_top();
    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );

    if( schematic_width > 0 ) {
        for( int x = bounds.p1.x() - editor_margin; x <= bounds.p2.x() + editor_margin; ++x ) {
            for( int y = bounds.p1.y() - editor_margin; y <= bounds.p2.y() + editor_margin; ++y ) {
                const point_rel_ms mount( x, y );
                const point screen = mount_to_viewport( mount );
                if( screen.x >= 0 && screen.y >= content_top && screen.x < schematic_width &&
                    screen.y < getmaxy( w_disp ) ) {
                    mvwputch( w_disp, screen, c_dark_gray, '.' );
                    if( const std::optional<std::pair<int, nc_color>> shown = editor_mount_display( mount ) ) {
                        mvwputch( w_disp, screen, shown->second, shown->first );
                    }
                }
            }
        }

        if( debug_mode ) {
            const point_rel_ms &pivot = veh->pivot_point( here );
            const point_rel_ms &com = veh->local_center_of_mass( here );
            const point com_s = mount_to_viewport( com );
            const point pivot_s = mount_to_viewport( pivot );
            if( com_s.x >= 0 && com_s.y >= content_top && com_s.x < schematic_width &&
                com_s.y < getmaxy( w_disp ) ) {
                mvwputch( w_disp, com_s, c_green, 'C' );
            }
            if( pivot_s.x >= 0 && pivot_s.y >= content_top && pivot_s.x < schematic_width &&
                pivot_s.y < getmaxy( w_disp ) ) {
                mvwputch( w_disp, pivot_s, c_red, 'P' );
            }
        }

        const point selected_screen = mount_to_viewport( selected_mount() );
        if( selected_screen.x >= 0 && selected_screen.y >= content_top &&
            selected_screen.x < schematic_width && selected_screen.y < getmaxy( w_disp ) ) {
            int sym = '.';
            nc_color col = c_dark_gray;
            if( const std::optional<std::pair<int, nc_color>> shown = editor_mount_display( selected_mount() ) ) {
                sym = shown->first;
                col = shown->second;
            }

            const tripoint_bub_ms world_pos = veh->pos_bub( here ) + veh->coord_translate( selected_mount() );
            const optional_vpart_position ovp = here.veh_at( world_pos );
            col = hilite( col );
            if( here.impassable_ter_furn( world_pos ) || ( ovp && &ovp->vehicle() != veh ) ) {
                col = red_background( col );
            }

            mvwputch( w_disp, selected_screen, col, sym );
            if( selected_screen.x > 0 ) {
                mvwputch( w_disp, point( selected_screen.x - 1, selected_screen.y ), c_yellow, '[' );
            }
            if( selected_screen.x + 1 < schematic_width ) {
                mvwputch( w_disp, point( selected_screen.x + 1, selected_screen.y ), c_yellow, ']' );
            }
            if( cell.y >= 2 && selected_screen.y > content_top ) {
                mvwputch( w_disp, point( selected_screen.x, selected_screen.y - 1 ), c_yellow, '^' );
            }
            if( cell.y >= 2 && selected_screen.y + 1 < getmaxy( w_disp ) ) {
                mvwputch( w_disp, point( selected_screen.x, selected_screen.y + 1 ), c_yellow, 'v' );
            }
        }
    }

    if( active_editor_view_mode == editor_view_mode::split && schematic_width > 0 &&
        schematic_width < getmaxx( w_disp ) ) {
        wattron( w_disp, c_dark_gray );
        mvwvline( w_disp, point( schematic_width, content_top ), LINE_XOXO,
                  std::max( 0, getmaxy( w_disp ) - content_top ) );
        wattroff( w_disp, c_dark_gray );
    }

    if( active_editor_view_mode == editor_view_mode::split ) {
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   install_info ?
                   _( "Vehicle editor  Mount (%+d,%+d)  Editor %d%% / Live %d%%  <color_light_cyan>INSTALL MODE</color>" ) :
                   _( "Vehicle editor  Mount (%+d,%+d)  Editor %d%% / Live %d%%" ),
                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50,
                   live_preview_zoom * 50 );
    } else {
        const int shown_zoom = active_editor_view_mode == editor_view_mode::live ?
                               live_preview_zoom : viewport_zoom;
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   install_info ?
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%  <color_light_cyan>INSTALL MODE</color>" ) :
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%" ),
                   selected_mount().x(), selected_mount().y(), shown_zoom * 50 );
    }
    display_editor_controls();
#if !defined(TILES)
    if( active_editor_view_mode != editor_view_mode::editor ) {
        const int x = active_editor_view_mode == editor_view_mode::split ? schematic_width + 2 : 2;
        trim_and_print( w_disp, point( x, content_top + 1 ),
                        std::max( 1, getmaxx( w_disp ) - x - 1 ), c_dark_gray,
                        _( "Live vehicle preview requires the tiles build." ) );
    }
#endif
    wnoutrefresh( w_disp );
}

void veh_interact::display_live_preview( map &here )
{
#if defined(TILES)
    if( active_editor_view_mode == editor_view_mode::editor ) {
        live_preview_last_draw_mode.reset();
        clear_map_preview_window();
        return;
    }

    catacurses::window &preview = active_editor_view_mode == editor_view_mode::live ?
                                  w_live_preview_full : w_live_preview_split;
    if( !preview ) {
        clear_map_preview_window();
        return;
    }

    // Use the real transformed positions of all installed parts.  Vehicle
    // mount-space bounding boxes can be far from the visual center when a large
    // vehicle has an offset pivot or asymmetric construction.
    const tripoint_bub_ms vehicle_center = live_preview_vehicle_center( here );
    tripoint_bub_ms world_center = vehicle_center +
                                   tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );
    const window_dimensions dim = get_window_dimensions( preview );

    // Live and Split have different destination rectangles. Preserve the map
    // square at the old preview's visual center when switching layouts so tile
    // parity / renderer alignment cannot move the apparent camera.
    if( live_preview_last_draw_mode && *live_preview_last_draw_mode != active_editor_view_mode &&
        *live_preview_last_draw_mode != editor_view_mode::editor ) {
        catacurses::window &old_preview = *live_preview_last_draw_mode == editor_view_mode::live ?
                                          w_live_preview_full : w_live_preview_split;
        if( old_preview ) {
            const window_dimensions old_dim = get_window_dimensions( old_preview );
            const point old_mid( old_dim.window_size_pixel.x / 2, old_dim.window_size_pixel.y / 2 );
            const point new_mid( dim.window_size_pixel.x / 2, dim.window_size_pixel.y / 2 );
            const std::optional<tripoint_bub_ms> old_mid_map = map_preview_pixel_to_map(
                        old_preview, old_mid, world_center, live_preview_zoom * 8 );
            const std::optional<tripoint_bub_ms> new_mid_map = map_preview_pixel_to_map(
                        preview, new_mid, world_center, live_preview_zoom * 8 );
            if( old_mid_map && new_mid_map ) {
                const point transition_delta( old_mid_map->x() - new_mid_map->x(),
                                              old_mid_map->y() - new_mid_map->y() );
                live_preview_pan += transition_delta;
                world_center = vehicle_center +
                               tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );
                DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] mode-reanchor "
                                          << static_cast<int>( *live_preview_last_draw_mode ) << "->"
                                          << static_cast<int>( active_editor_view_mode )
                                          << " old_mid_map=(" << old_mid_map->x() << ","
                                          << old_mid_map->y() << ") new_mid_map=("
                                          << new_mid_map->x() << "," << new_mid_map->y() << ")"
                                          << " delta=(" << transition_delta.x << ","
                                          << transition_delta.y << ") center=("
                                          << world_center.x() << "," << world_center.y() << ")";
            }
        }
    }
    live_preview_last_draw_mode = active_editor_view_mode;

    static int debug_last_mode = -1;
    static int debug_last_center_x = INT_MIN;
    static int debug_last_center_y = INT_MIN;
    static int debug_last_center_z = INT_MIN;
    static int debug_last_zoom = -1;
    static int debug_last_px_x = INT_MIN;
    static int debug_last_px_y = INT_MIN;
    static int debug_last_px_w = INT_MIN;
    static int debug_last_px_h = INT_MIN;
    const int debug_mode_id = static_cast<int>( active_editor_view_mode );
    if( debug_last_mode != debug_mode_id || debug_last_center_x != world_center.x() ||
        debug_last_center_y != world_center.y() || debug_last_center_z != world_center.z() ||
        debug_last_zoom != live_preview_zoom || debug_last_px_x != dim.window_pos_pixel.x ||
        debug_last_px_y != dim.window_pos_pixel.y || debug_last_px_w != dim.window_size_pixel.x ||
        debug_last_px_h != dim.window_size_pixel.y ) {
        DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_CAMERA] preview-register mode=" << debug_mode_id
                                  << " zoom=" << live_preview_zoom
                                  << " draw_scale=" << live_preview_zoom * 8
                                  << " vehicle_center=(" << vehicle_center.x() << ","
                                  << vehicle_center.y() << "," << vehicle_center.z() << ")"
                                  << " pan=(" << live_preview_pan.x << "," << live_preview_pan.y << ")"
                                  << " world_center=(" << world_center.x() << "," << world_center.y()
                                  << "," << world_center.z() << ")"
                                  << " preview_px_pos=(" << dim.window_pos_pixel.x << ","
                                  << dim.window_pos_pixel.y << ")"
                                  << " preview_px_size=(" << dim.window_size_pixel.x << ","
                                  << dim.window_size_pixel.y << ")";
        debug_last_mode = debug_mode_id;
        debug_last_center_x = world_center.x();
        debug_last_center_y = world_center.y();
        debug_last_center_z = world_center.z();
        debug_last_zoom = live_preview_zoom;
        debug_last_px_x = dim.window_pos_pixel.x;
        debug_last_px_y = dim.window_pos_pixel.y;
        debug_last_px_w = dim.window_size_pixel.x;
        debug_last_px_h = dim.window_size_pixel.y;
    }

    set_map_preview_window( preview, world_center, live_preview_zoom * 8 );
    werase( preview );
    wnoutrefresh( preview );
#else
    ( void )here;
#endif
}

void veh_interact::display_part_inspector()
{
    werase( w_parts );
    const int width = getmaxx( w_parts );
    const int height = getmaxy( w_parts );
    const point_rel_ms mount = selected_mount();
    const std::vector<int> all_parts = veh->parts_at_relative( mount, true, false );
    const std::vector<int> parts = inspector_parts();

    mvwprintz( w_parts, point( 1, 0 ), c_light_green, _( "Mount (%+d,%+d)" ), mount.x(), mount.y() );
    if( parts.size() == all_parts.size() ) {
        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d" ),
                   static_cast<int>( parts.size() ) );
    } else {
        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d/%d" ),
                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );
    }
    if( height > 2 ) {
        wattron( w_parts, c_dark_gray );
        mvwhline( w_parts, point( 1, 2 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_parts, c_dark_gray );
    }

    const int first_row = 3;
    const int visible = std::max( 1, height - first_row );
    const int max_scroll = std::max( 0, static_cast<int>( parts.size() ) - visible );
    part_scroll = std::clamp( part_scroll, 0, max_scroll );

    if( parts.empty() && first_row < height ) {
        trim_and_print( w_parts, point( 2, first_row ), std::max( 1, width - 4 ), c_dark_gray,
                        _( "No parts match this view." ) );
    }

    for( int row = 0; row < visible; ++row ) {
        const int idx = part_scroll + row;
        if( idx >= static_cast<int>( parts.size() ) ) {
            break;
        }
        const int part_idx = parts[idx];
        const vehicle_part &vp = veh->part( part_idx );
        const bool selected = part_idx == selected_part;
        const int health = static_cast<int>( std::lround( vp.health_percent() * 100.0 ) );
        nc_color name_color = vp.is_broken() ? c_dark_gray : c_light_gray;
        nc_color condition_color = editor_condition_color( vp );
        if( selected ) {
            name_color = hilite( name_color );
            condition_color = hilite( condition_color );
        }
        const int percent_x = std::max( 4, width - 6 );
        trim_and_print( w_parts, point( 2, first_row + row ), std::max( 1, percent_x - 3 ),
                        name_color, vp.name() );
        mvwprintz( w_parts, point( percent_x, first_row + row ), condition_color, "%3d%%", health );
    }

    if( static_cast<int>( parts.size() ) > visible ) {
        scrollbar().offset_x( width - 1 ).offset_y( first_row )
        .content_size( static_cast<int>( parts.size() ) ).viewport_pos( part_scroll )
        .viewport_size( visible ).apply( w_parts );
    }
    wnoutrefresh( w_parts );
}

void veh_interact::display_part_details()
{
    werase( w_msg );
    const int width = getmaxx( w_msg );
    const int height = getmaxy( w_msg );
    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        mvwprintz( w_msg, point( 1, 0 ), c_dark_gray, _( "No part selected." ) );
        wnoutrefresh( w_msg );
        return;
    }

    const vehicle_part &vp = veh->part( selected_part );
    if( vp.removed || vp.mount != selected_mount() ) {
        mvwprintz( w_msg, point( 1, 0 ), c_dark_gray, _( "No part selected." ) );
        wnoutrefresh( w_msg );
        return;
    }

    int line = 0;
    trim_and_print( w_msg, point( 1, line++ ), std::max( 1, width - 2 ), c_light_green, vp.name() );
    const int health = static_cast<int>( std::lround( vp.health_percent() * 100.0 ) );
    const nc_color health_col = editor_condition_color( vp );
    mvwprintz( w_msg, point( 1, line ), c_light_gray, _( "Condition: " ) );
    wprintz( w_msg, health_col, "%d%%", health );
    ++line;
    mvwprintz( w_msg, point( 1, line++ ), c_light_gray, _( "Location: (%+d,%+d)" ),
               vp.mount.x(), vp.mount.y() );

    if( vp.is_fuel_store( false ) && !vp.ammo_current().is_null() && line < height ) {
        const int capacity = vp.item_capacity( vp.ammo_current() );
        trim_and_print( w_msg, point( 1, line++ ), std::max( 1, width - 2 ), c_light_gray,
                        string_format( _( "Fuel: %s  Contents: %d/%d" ),
                                       item::nname( vp.ammo_current() ), vp.ammo_remaining(), capacity ) );
    }
    if( vp.info().has_flag( VPFLAG_CARGO ) && line < height ) {
        const vehicle_stack storage = veh->get_items( const_cast<vehicle_part &>( vp ) );
        trim_and_print( w_msg, point( 1, line++ ), std::max( 1, width - 2 ), c_light_gray,
                        string_format( _( "Cargo: %s/%s %s" ),
                                       format_volume( storage.stored_volume() ),
                                       format_volume( storage.max_volume() ), volume_units_abbr() ) );
    }

    if( line < height ) {
        wattron( w_msg, c_dark_gray );
        mvwhline( w_msg, point( 1, line++ ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_msg, c_dark_gray );
    }

    std::string description;
    vp.info().format_description( description, c_light_gray, std::max( 1, width - 3 ) );
    const int available = std::max( 1, height - line );
    const std::vector<std::string> folded = foldstring( description, std::max( 1, width - 3 ) );
    const int max_scroll = std::max( 0, static_cast<int>( folded.size() ) - available );
    part_detail_scroll = std::clamp( part_detail_scroll, 0, max_scroll );
    fold_and_print_from( w_msg, point( 1, line ), std::max( 1, width - 3 ), part_detail_scroll,
                         c_light_gray, description );
    if( max_scroll > 0 ) {
        scrollbar().offset_x( width - 1 ).offset_y( line )
        .content_size( static_cast<int>( folded.size() ) ).viewport_pos( part_detail_scroll )
        .viewport_size( available ).apply( w_msg );
    }
    wnoutrefresh( w_msg );
}

static std::string wheel_state_description( map &here, const vehicle &veh )
{
    bool is_boat = !veh.floating.empty();
    bool is_land = !veh.wheelcache.empty() || !is_boat;

    bool suf_land = veh.sufficient_wheel_config();
    bool bal_land = veh.balanced_wheel_config( here );

    bool suf_boat = veh.can_float( here );

    float steer = veh.steering_effectiveness( here );

    std::string wheel_status;
    if( !suf_land && is_boat ) {
        wheel_status = _( "<color_light_red>disabled</color>" );
    } else if( !suf_land ) {
        wheel_status = _( "<color_light_red>lack</color>" );
    } else if( !bal_land ) {
        wheel_status = _( "<color_light_red>unbalanced</color>" );
    } else if( steer < 0 ) {
        wheel_status = _( "<color_light_red>no steering</color>" );
    } else if( steer < 0.033 ) {
        wheel_status = _( "<color_light_red>broken steering</color>" );
    } else if( steer < 0.5 ) {
        wheel_status = _( "<color_light_red>poor steering</color>" );
    } else {
        wheel_status = _( "<color_light_green>enough</color>" );
    }

    std::string boat_status;
    if( !suf_boat ) {
        boat_status = _( "<color_light_red>sinks</color>" );
    } else {
        boat_status = _( "<color_light_blue>floats</color>" );
    }

    if( is_boat && is_land ) {
        return string_format( _( "Wheels/boat: %s/%s" ), wheel_status, boat_status );
    }

    if( is_boat ) {
        return string_format( _( "Boat: %s" ), boat_status );
    }

    return string_format( _( "Wheels: %s" ), wheel_status );
}

/**
 * Displays the vehicle's stats at the bottom of the window.
 */
void veh_interact::display_stats( map &here ) const
{
    werase( w_stats_1 );
    werase( w_stats_2 );
    werase( w_stats_3 );

    on_out_of_scope refresh_windows( [&]() {
        wnoutrefresh( w_stats_1 );
        wnoutrefresh( w_stats_2 );
        wnoutrefresh( w_stats_3 );
    } );

    // 3 * stats_h
    const int slots = 24;
    std::array<const catacurses::window *, slots> win;
    std::array<int, slots> row;

    units::volume total_cargo = 0_ml;
    units::volume free_cargo = 0_ml;
    for( const vpart_reference &vpr : veh->get_any_parts( VPFLAG_CARGO ) ) {
        const vehicle_stack vs = vpr.items();
        total_cargo += vs.max_volume();
        free_cargo += vs.free_volume();
    }

    for( int i = 0; i < slots; i++ ) {
        if( i < stats_h ) {
            // First column
            win[i] = &w_stats_1;
            row[i] = i;
        } else if( i < ( 2 * stats_h ) ) {
            // Second column
            win[i] = &w_stats_2;
            row[i] = i - stats_h;
        } else {
            // Third column
            win[i] = &w_stats_3;
            row[i] = i - 2 * stats_h;
        }
    }

    bool is_boat = !veh->floating.empty();
    bool is_ground = !veh->wheelcache.empty() || !is_boat;
    bool is_aircraft = veh->is_rotorcraft( here ) && veh->is_flying_in_air();

    const auto vel_to_int = []( const double vel ) {
        return static_cast<int>( convert_velocity( vel, VU_VEHICLE ) );
    };

    int i = 0;
    if( is_aircraft ) {
        fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                        _( "Air Safe/Top speed: <color_light_green>%3d</color>/<color_light_red>%3d</color> %s" ),
                        vel_to_int( veh->safe_rotor_velocity( here, false ) ),
                        vel_to_int( veh->max_rotor_velocity( here, false ) ),
                        velocity_units( VU_VEHICLE ) );
        i += 1;
        fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                        _( "Air acceleration: <color_light_blue>%3d</color> %s/s" ),
                        vel_to_int( veh->rotor_acceleration( here, false ) ),
                        velocity_units( VU_VEHICLE ) );
        i += 1;
    } else {
        if( is_ground ) {
            fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                            _( "Safe/Top speed: <color_light_green>%3d</color>/<color_light_red>%3d</color> %s" ),
                            vel_to_int( veh->safe_ground_velocity( here, false ) ),
                            vel_to_int( veh->max_ground_velocity( here, false ) ),
                            velocity_units( VU_VEHICLE ) );
            i += 1;
            // TODO: extract accelerations units to its own function
            fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                            //~ /t means per turn
                            _( "Acceleration: <color_light_blue>%3d</color> %s/s" ),
                            vel_to_int( veh->ground_acceleration( here, false ) ),
                            velocity_units( VU_VEHICLE ) );
            i += 1;
        } else {
            i += 2;
        }
        if( is_boat ) {
            fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                            _( "Water Safe/Top speed: <color_light_green>%3d</color>/<color_light_red>%3d</color> %s" ),
                            vel_to_int( veh->safe_water_velocity( here, false ) ),
                            vel_to_int( veh->max_water_velocity( here, false ) ),
                            velocity_units( VU_VEHICLE ) );
            i += 1;
            // TODO: extract accelerations units to its own function
            fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                            //~ /t means per turn
                            _( "Water acceleration: <color_light_blue>%3d</color> %s/s" ),
                            vel_to_int( veh->water_acceleration( here, false ) ),
                            velocity_units( VU_VEHICLE ) );
            i += 1;
        } else {
            i += 2;
        }
    }
    fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                    _( "Mass: <color_light_blue>%5.0f</color> %s" ),
                    convert_weight( veh->total_mass( here ) ), weight_units() );
    i += 1;
    fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                    disp_w > 35 ? _( "Cargo volume: <color_light_blue>%s</color> / <color_light_blue>%s</color> %s" ) :
                    _( "Cargo: <color_light_blue>%s</color> / <color_light_blue>%s</color> %s" ),
                    format_volume( total_cargo - free_cargo ),
                    format_volume( total_cargo ), volume_units_abbr() );
    i += 1;
    // Write the overall damage
    mvwprintz( *win[i], point( 0, row[i] ), c_light_gray, _( "Status: " ) );
    fold_and_print( *win[i], point( utf8_width( _( "Status: " ) ), row[i] ), getmaxx( *win[i] ),
                    total_durability_color, total_durability_text );
    i += 1;

    fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                    wheel_state_description( here, *veh ) );
    i += 1;

    if( install_info || remove_info ) {
        // don't draw the second and third columns which would be overwritten by w_details
        return;
    }

    // advance to next column if necessary
    i = std::max( i, stats_h );

    //This lambda handles printing parts in the "Most damaged" and "Needs repair" cases
    //for the veh_interact ui
    const auto print_part = [&]( const std::string & str, int slot, vehicle_part * pt ) {
        mvwprintz( *win[slot], point( 0, row[slot] ), c_light_gray, str );
        int iw = utf8_width( str ) + 1;
        return fold_and_print( *win[slot], point( iw, row[slot] ), getmaxx( *win[slot] ), c_light_gray,
                               pt->name() );
    };

    vehicle_part *mostDamagedPart = get_most_damaged_part();
    vehicle_part *most_repairable = get_most_repairable_part();

    // Write the most damaged part
    if( mostDamagedPart && mostDamagedPart->damage_percent() ) {
        const std::string damaged_header = mostDamagedPart == most_repairable ?
                                           _( "Most damaged:" ) :
                                           _( "Most damaged (can't repair):" );
        i += print_part( damaged_header, i, mostDamagedPart );
    } else {
        i += 1;
    }

    // Write the part that needs repair the most.
    if( most_repairable && most_repairable != mostDamagedPart ) {
        const std::string needsRepair = _( "Needs repair:" );
        i += print_part( needsRepair, i, most_repairable );
    } else {
        i += 1;
    }

    fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                    _( "Air drag:       <color_light_blue>%5.2f</color>" ),
                    veh->coeff_air_drag() );
    i += 1;

    if( is_boat ) {
        fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                        _( "Water drag:     <color_light_blue>%5.2f</color>" ),
                        veh->coeff_water_drag( here ) );
    }
    i += 1;

    if( is_ground ) {
        fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                        _( "Rolling drag:   <color_light_blue>%5.2f</color>" ),
                        veh->coeff_rolling_drag( here ) );
    }
    i += 1;

    fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                    _( "Static drag:    <color_light_blue>%5d</color>" ),
                    units::to_watt( veh->static_drag( false ) ) );
    i += 1;

    fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                    _( "Offroad:        <color_light_blue>%4d</color>%%" ),
                    static_cast<int>( veh->k_traction( here, veh->wheel_area() *
                                      veh->average_offroad_rating() ) * 100 ) );
    i += 1;

    if( is_boat ) {

        const double water_clearance = veh->water_hull_height( here ) - veh->water_draft( here );
        const char *draft_string = water_clearance > 0 ?
                                   _( "Draft/Clearance:<color_light_blue>%4.2f</color>m/<color_light_blue>%4.2f</color>m" ) :
                                   _( "Draft/Clearance:<color_light_blue>%4.2f</color>m/<color_light_red>%4.2f</color>m" ) ;

        fold_and_print( *win[i], point( 0, row[i] ), getmaxx( *win[i] ), c_light_gray,
                        draft_string,
                        veh->water_draft( here ), water_clearance );
        i += 1;
    }

    // advance to next column if necessary
    i = std::max( i, 2 * stats_h );

    // Print fuel percentage & type name only if it fits in the window, 10 is width of "E...F 100%"
    veh->print_fuel_indicators( here, *win[i], point( 0, row[i] ), fuel_index, true,
                                ( getmaxx( *win[i] ) > 10 ),
                                ( getmaxx( *win[i] ) > 10 ) );

}

void veh_interact::display_name()
{
    werase( w_name );
    // NOLINTNEXTLINE(cata-use-named-point-constants)
    mvwprintz( w_name, point( 1, 0 ), c_light_gray, _( "Name: " ) );

    mvwprintz( w_name, point( 1 + utf8_width( _( "Name: " ) ), 0 ),
               !veh->is_owned_by( get_player_character(), true ) ? c_light_red : c_light_green,
               string_format( _( "%s (%s)" ), veh->name, veh->get_owner_name() ) );
    wnoutrefresh( w_name );
}

bool veh_interact::editor_toolbar_action_enabled( const map &here, const std::string &action )
{
    if( refuel_info ) {
        return action == "REFILL" || action == "QUIT";
    }
    if( install_info ) {
        // Install is a persistent editor mode.  Do not allow another command to
        // start on top of it; Back still routes through QUIT and closes the mode.
        return action == "INSTALL" || action == "QUIT";
    }

    const auto selected = [&]() -> const vehicle_part * {
        if( selected_part < 0 || selected_part >= veh->part_count() ) {
            return nullptr;
        }
        const vehicle_part &part = veh->part( selected_part );
        return !part.removed && part.mount == selected_mount() ? &part : nullptr;
    };

    if( action == "INSTALL" ) {
        return cant_do( here, 'i' ) == task_reason::CAN_DO;
    }
    if( action == "REPAIR" ) {
        const vehicle_part *part = selected();
        return part != nullptr && part->health_percent() < 0.999 &&
               ( part->is_broken() || part->is_repairable() );
    }
    if( action == "REMOVE" ) {
        const vehicle_part *part = selected();
        return part != nullptr && !part->info().has_flag( "NO_UNINSTALL" ) &&
               veh->can_unmount( *part ).success();
    }
    if( action == "REFILL" ) {
        return cant_do( here, 'f' ) == task_reason::CAN_DO;
    }
    if( action == "MEND" ) {
        return cant_do( here, 'm' ) == task_reason::CAN_DO;
    }
    if( action == "CHANGE_SHAPE" || action == "RELABEL" ) {
        return selected() != nullptr;
    }
    if( action == "ASSIGN_CREW" ) {
        return cant_do( here, 'w' ) == task_reason::CAN_DO;
    }
    if( action == "SIPHON" ) {
        return cant_do( here, 's' ) == task_reason::CAN_DO;
    }
    if( action == "UNLOAD" ) {
        return cant_do( here, 'd' ) == task_reason::CAN_DO;
    }
    return action == "RENAME" || action == "QUIT";
}

void veh_interact::rebuild_editor_toolbar( const map &here )
{
    editor_toolbar_buttons.clear();
    const int width = getmaxx( w_mode );
    if( width <= 2 ) {
        return;
    }

    struct toolbar_candidate {
        std::string label;
        std::string action;
        int group = 0;
    };
    const auto direct = []( const std::string &label, const std::string &action, const int group ) {
        return toolbar_candidate{ label, action, group };
    };
    const auto menu = []( const std::string &label, const std::string &menu_id, const int group ) {
        return toolbar_candidate{ label, menu_id, group };
    };
    const auto is_menu = []( const toolbar_candidate &entry ) {
        return entry.action.starts_with( "TOOLBAR_MENU_" );
    };
    const auto rendered = [&]( const toolbar_candidate &entry ) {
        return is_menu( entry ) ? string_format( "[ %s ▼ ]", entry.label ) :
               string_format( "[ %s ]", entry.label );
    };

    const toolbar_candidate back = direct( _( "Back" ), "QUIT", 4 );
    const int back_width = utf8_width( rendered( back ) );

    const std::vector<toolbar_candidate> wide = {
        direct( _( "Install" ), "INSTALL", 0 ),
        direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ),
        direct( _( "Refuel" ), "REFILL", 0 ),
        menu( _( "Modify" ), "TOOLBAR_MENU_MODIFY", 1 ),
        direct( _( "Crew" ), "ASSIGN_CREW", 2 ),
        direct( _( "Rename" ), "RENAME", 2 ),
        menu( _( "More" ), "TOOLBAR_MENU_MORE", 3 )
    };
    const std::vector<toolbar_candidate> medium = {
        direct( _( "Install" ), "INSTALL", 0 ),
        direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ),
        direct( _( "Refuel" ), "REFILL", 0 ),
        menu( _( "Modify" ), "TOOLBAR_MENU_MODIFY", 1 ),
        menu( _( "More" ), "TOOLBAR_MENU_MORE", 2 )
    };
    const std::vector<toolbar_candidate> narrow = {
        direct( _( "Install" ), "INSTALL", 0 ),
        direct( _( "Repair" ), "REPAIR", 0 ),
        direct( _( "Remove" ), "REMOVE", 0 ),
        menu( _( "Actions" ), "TOOLBAR_MENU_ACTIONS", 1 )
    };
    const std::vector<toolbar_candidate> tiny = {
        menu( _( "Actions" ), "TOOLBAR_MENU_ACTIONS", 0 )
    };

    const auto required_width = [&]( const std::vector<toolbar_candidate> &entries ) {
        int total = 1 + back_width + 1;
        int previous_group = -1;
        for( const toolbar_candidate &entry : entries ) {
            if( previous_group >= 0 ) {
                total += entry.group == previous_group ? 1 : 3;
            }
            total += utf8_width( rendered( entry ) );
            previous_group = entry.group;
        }
        return total + 1;
    };

    const std::vector<toolbar_candidate> *chosen = &tiny;
    if( required_width( wide ) <= width ) {
        chosen = &wide;
    } else if( required_width( medium ) <= width ) {
        chosen = &medium;
    } else if( required_width( narrow ) <= width ) {
        chosen = &narrow;
    }

    int x = 1;
    int previous_group = -1;
    for( const toolbar_candidate &entry : *chosen ) {
        if( previous_group >= 0 ) {
            x += entry.group == previous_group ? 1 : 3;
        }
        const int button_width = utf8_width( rendered( entry ) );
        if( x + button_width >= width - back_width - 1 ) {
            break;
        }
        const bool menu_button = is_menu( entry );
        editor_toolbar_buttons.push_back( { entry.label, entry.action, point( x, 0 ), button_width,
                                            menu_button || editor_toolbar_action_enabled( here, entry.action ),
                                            entry.group } );
        x += button_width;
        previous_group = entry.group;
    }

    editor_toolbar_buttons.push_back( { back.label, back.action,
                                        point( std::max( 1, width - back_width - 1 ), 0 ),
                                        back_width, true, back.group } );
}

void veh_interact::update_editor_toolbar_hover( map &here, const std::optional<point> &pos )
{
    int hovered_index = -1;
    if( pos ) {
        for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
            const editor_toolbar_button &button = editor_toolbar_buttons[i];
            if( pos->y == button.pos.y && pos->x >= button.pos.x &&
                pos->x < button.pos.x + button.width ) {
                hovered_index = i;
                break;
            }
        }
    }

    std::string preview_action;
    if( hovered_index >= 0 ) {
        const std::string &action = editor_toolbar_buttons[hovered_index].action;
        if( action == "REPAIR" || action == "REMOVE" ) {
            preview_action = action;
        }
    }

    editor_toolbar_hover_button = hovered_index;
    if( preview_action == editor_toolbar_hover_action ) {
        return;
    }

    const bool had_preview = !editor_toolbar_hover_action.empty();
    editor_toolbar_hover_action = preview_action;
    w_msg_scroll_offset = 0;
    if( preview_action.empty() ) {
        if( had_preview ) {
            msg.reset();
        }
        return;
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return;
    }

    if( preview_action == "REPAIR" ) {
        set_editor_repair_requirements( here, part );
        return;
    }

    // Removal already has one canonical formatter.  Preserve the transient
    // command pointers so hovering remains a read-only preview.
    const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
    const vpart_info *old_sel_vpart_info = sel_vpart_info;
    can_remove_part( here, selected_part, get_avatar() );
    sel_vehicle_part = old_sel_vehicle_part;
    sel_vpart_info = old_sel_vpart_info;
}

void veh_interact::open_editor_toolbar_menu( const map &here, const std::string &which )
{
    struct toolbar_menu_entry {
        std::string label;
        std::string action;
    };
    std::vector<toolbar_menu_entry> entries;

    const auto has_direct = [&]( const std::string &action ) {
        return std::any_of( editor_toolbar_buttons.begin(), editor_toolbar_buttons.end(),
        [&]( const editor_toolbar_button &button ) {
            return !button.action.starts_with( "TOOLBAR_MENU_" ) && button.action == action;
        } );
    };
    const auto add = [&]( const std::string &label, const std::string &action ) {
        entries.push_back( { label, action } );
    };

    if( which == "TOOLBAR_MENU_MODIFY" ) {
        add( _( "Mend faults…" ), "MEND" );
        add( _( "Change shape…" ), "CHANGE_SHAPE" );
        add( _( "Relabel…" ), "RELABEL" );
    } else if( which == "TOOLBAR_MENU_MORE" ) {
        if( !has_direct( "ASSIGN_CREW" ) ) {
            add( _( "Crew…" ), "ASSIGN_CREW" );
        }
        if( !has_direct( "RENAME" ) ) {
            add( _( "Rename vehicle…" ), "RENAME" );
        }
        add( _( "Siphon liquid…" ), "SIPHON" );
        add( _( "Unload fuel…" ), "UNLOAD" );
    } else if( which == "TOOLBAR_MENU_ACTIONS" ) {
        if( !has_direct( "INSTALL" ) ) {
            add( _( "Install…" ), "INSTALL" );
        }
        if( !has_direct( "REPAIR" ) ) {
            add( _( "Repair…" ), "REPAIR" );
        }
        if( !has_direct( "REMOVE" ) ) {
            add( _( "Remove…" ), "REMOVE" );
        }
        if( !has_direct( "REFILL" ) ) {
            add( _( "Refuel…" ), "REFILL" );
        }
        add( _( "Mend faults…" ), "MEND" );
        add( _( "Change shape…" ), "CHANGE_SHAPE" );
        add( _( "Relabel…" ), "RELABEL" );
        add( _( "Crew…" ), "ASSIGN_CREW" );
        add( _( "Rename vehicle…" ), "RENAME" );
        add( _( "Siphon liquid…" ), "SIPHON" );
        add( _( "Unload fuel…" ), "UNLOAD" );
    }

    if( entries.empty() ) {
        return;
    }

    uilist menu;
    if( which == "TOOLBAR_MENU_MODIFY" ) {
        menu.text = _( "Modify selected part" );
    } else if( which == "TOOLBAR_MENU_MORE" ) {
        menu.text = _( "More vehicle actions" );
    } else {
        menu.text = _( "Vehicle actions" );
    }

    for( int i = 0; i < static_cast<int>( entries.size() ); ++i ) {
        menu.addentry( i, editor_toolbar_action_enabled( here, entries[i].action ), -1,
                       entries[i].label );
    }
    menu.query();
    if( menu.ret >= 0 && menu.ret < static_cast<int>( entries.size() ) &&
        editor_toolbar_action_enabled( here, entries[menu.ret].action ) ) {
        pending_editor_action = entries[menu.ret].action;
    }
}

bool veh_interact::handle_editor_toolbar_mouse( map &here, const std::string &action,
        const std::optional<point> &pos )
{
    // Legacy modal command choosers temporarily own w_mode for their title.
    // Do not make an invisible toolbar clickable underneath them.
    if( title.has_value() && !install_info ) {
        if( editor_toolbar_hover_button >= 0 || !editor_toolbar_hover_action.empty() ) {
            editor_toolbar_hover_button = -1;
            editor_toolbar_hover_action.clear();
        }
        return false;
    }

    rebuild_editor_toolbar( here );
    if( action == "MOUSE_MOVE" || editor_toolbar_hover_button >= 0 ) {
        update_editor_toolbar_hover( here, pos );
        if( action == "MOUSE_MOVE" && pos ) {
            return true;
        }
    }
    if( !pos ) {
        return false;
    }

    int hit = -1;
    for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[i];
        if( pos->y == button.pos.y && pos->x >= button.pos.x &&
            pos->x < button.pos.x + button.width ) {
            hit = i;
            break;
        }
    }
    if( hit < 0 ) {
        return true;
    }

    if( action == "SELECT" ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[hit];
        if( button.action.starts_with( "TOOLBAR_MENU_" ) ) {
            close_editor_context_menu();
            open_editor_toolbar_menu( here, button.action );
            return pending_editor_action.empty();
        }
        if( !button.enabled ) {
            return true;
        }
        pending_editor_action = button.action;
        return false;
    }

    // The toolbar consumes wheel/secondary clicks over its own row so those
    // inputs never leak into the viewport, inspector, or live-preview camera.
    return action == "SEC_SELECT" || action == "SCROLL_UP" || action == "SCROLL_DOWN";
}

/**
 * Mouse-first action toolbar.  The old keyboard bindings remain registered in
 * VEH_INTERACT; toolbar clicks inject those same action IDs into do_main_loop().
 */
void veh_interact::display_mode( const map &here )
{
    werase( w_mode );

    if( title.has_value() && !install_info ) {
        nc_color title_col = c_light_gray;
        print_colored_text( w_mode, point( 1, 0 ), title_col, title_col, title.value() );
        wnoutrefresh( w_mode );
        return;
    }

    rebuild_editor_toolbar( here );
    for( int i = 0; i < static_cast<int>( editor_toolbar_buttons.size() ); ++i ) {
        const editor_toolbar_button &button = editor_toolbar_buttons[i];
        const bool menu_button = button.action.starts_with( "TOOLBAR_MENU_" );
        const std::string text = menu_button ? string_format( "[ %s ▼ ]", button.label ) :
                                 string_format( "[ %s ]", button.label );
        const bool hovered = i == editor_toolbar_hover_button;
        const nc_color color = !button.enabled ? c_dark_gray :
                               hovered ? h_light_cyan : c_light_cyan;
        trim_and_print( w_mode, button.pos, button.width, color, text );
    }
    wnoutrefresh( w_mode );
}

/**
 * Draws the list of parts that can be mounted in the selected square. Used
 * when installing new parts.
 * @param pos The current cursor position in the list.
 * @param list The list to display parts from.
 * @param header Number of lines occupied by the list header
 */
void veh_interact::display_list( size_t pos, const std::vector<const vpart_info *> &list,
                                 const int )
{
    werase( w_list );
    if( !install_info ) {
        wnoutrefresh( w_list );
        return;
    }

    const int width = getmaxx( w_list );
    const int height = getmaxy( w_list );
    constexpr int first_row = 4;

    trim_and_print( w_list, point( 1, 0 ), std::max( 1, width - 2 ), c_light_green,
                    string_format( _( "Install at (%+d,%+d)  Layer: %s  System: %s" ),
                                   selected_mount().x(), selected_mount().y(),
                                   editor_layer_name( active_editor_layer ),
                                   editor_system_name( active_system_filter ) ) );

    const std::string search_text = install_info->filter.empty() ? _( "All parts" ) : install_info->filter;
    trim_and_print( w_list, point( 1, 1 ), std::max( 1, width - 2 ), c_light_cyan,
                    string_format( _( "Search: [ %s ]" ), search_text ) );

    const std::string install_button = _( "[ Install ]" );
    const std::string close_button = _( "[ Close ]" );
    const int close_width = utf8_width( close_button );
    const int install_width = utf8_width( install_button );
    const int close_x = std::max( 1, width - close_width - 1 );
    const int install_x = std::max( 1, close_x - install_width - 1 );

    const std::string availability = install_info->available_materials_only ?
                                     _( "[x] Materials" ) : _( "[ ] Materials" );
    const std::string show_all = install_info->show_all ?
                                 _( "[x] Show all" ) : _( "[ ] Show all" );
    const int show_all_x = 1 + utf8_width( availability ) + 1;
    trim_and_print( w_list, point( 1, 2 ), std::max( 1, install_x - 2 ), c_light_cyan, availability );
    if( show_all_x < install_x - 1 ) {
        trim_and_print( w_list, point( show_all_x, 2 ), std::max( 1, install_x - show_all_x - 1 ),
                        c_light_cyan, show_all );
    }
    trim_and_print( w_list, point( install_x, 2 ), install_width,
                    install_info->selected_can_install ? c_light_green : c_dark_gray, install_button );
    trim_and_print( w_list, point( close_x, 2 ), close_width, c_light_gray, close_button );

    if( height > 3 ) {
        wattron( w_list, c_dark_gray );
        mvwhline( w_list, point( 1, 3 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_list, c_dark_gray );
    }

    const int lines_per_page = std::max( 1, height - first_row );
    const size_t page = pos / lines_per_page;
    const size_t begin = page * lines_per_page;

    if( list.empty() && first_row < height ) {
        trim_and_print( w_list, point( 2, first_row ), std::max( 1, width - 4 ), c_dark_gray,
                        _( "No parts match the current layer/system/search filters." ) );
    }

    for( size_t i = begin; i < begin + lines_per_page && i < list.size(); ++i ) {
        const vpart_info &info = *list[i];
        const vpart_variant &vv = info.variants.at( info.variant_default );
        const int y = static_cast<int>( i - begin ) + first_row;
        mvwputch( w_list, point( 1, y ), info.color, vv.get_symbol_curses( 0_degrees, false ) );

        const bool materials = install_materials_available( info );
        const bool mount_compatible = veh->can_mount( selected_mount(), info ).success();
        nc_color col = materials && mount_compatible ? c_white : c_dark_gray;
        std::string label = info.name();
        if( active_editor_layer == editor_layer::composite ) {
            label = string_format( "[%s] %s", editor_layer_name( editor_layer_for_part( info ) ), label );
        }
        trim_and_print( w_list, point( 3, y ), std::max( 1, width - 4 ),
                        pos == i ? hilite( col ) : col, label );
    }

    if( static_cast<int>( list.size() ) > lines_per_page ) {
        scrollbar().offset_x( width - 1 ).offset_y( first_row )
        .content_size( static_cast<int>( list.size() ) )
        .viewport_pos( static_cast<int>( begin ) )
        .viewport_size( lines_per_page ).apply( w_list );
    }
    wnoutrefresh( w_list );
}

/**
 * Used when installing parts.
 * Opens up w_details containing info for part currently selected in w_list.
 */
void veh_interact::display_details( const vpart_info *part )
{
    const int details_w = getmaxx( w_details );

    werase( w_details );

    draw_border( w_details );

    if( part == nullptr ) {
        wnoutrefresh( w_details );
        return;
    }
    // displays data in two columns
    int column_width = details_w / 2;
    int col_1 = 2;
    int col_2 = col_1 + column_width;
    int line = 0;
    bool small_mode = column_width < 20;

    // line 0: part name
    fold_and_print( w_details, point( col_1, line ), details_w, c_light_green, part->name() );

    // line 1: (column 1) durability   (column 2) damage mod
    fold_and_print( w_details, point( col_1, line + 1 ), column_width, c_white,
                    "%s: <color_light_gray>%d</color>",
                    small_mode ? _( "Dur" ) : _( "Durability" ),
                    part->durability );
    fold_and_print( w_details, point( col_2, line + 1 ), column_width, c_white,
                    "%s: <color_light_gray>%d%%</color>",
                    small_mode ? _( "Dmg" ) : _( "Damage" ),
                    part->dmg_mod );

    // line 2: (column 1) weight   (column 2) folded volume (if applicable)
    fold_and_print( w_details, point( col_1, line + 2 ), column_width, c_white,
                    "%s: <color_light_gray>%.1f%s</color>",
                    small_mode ? _( "Wgt" ) : _( "Weight" ),
                    convert_weight( item::find_type( part->base_item )->weight ),
                    weight_units() );
    if( part->folded_volume ) {
        fold_and_print( w_details, point( col_2, line + 2 ), column_width, c_white,
                        "%s: <color_light_gray>%s %s</color>",
                        small_mode ? _( "FoldVol" ) : _( "Folded Volume" ),
                        format_volume( part->folded_volume.value() ),
                        volume_units_abbr() );
    }

    // line 3: (column 1) size, bonus, wheel diameter (if applicable)    (column 2) epower, wheel width (if applicable)
    if( part->size > 0_ml && part->has_flag( VPFLAG_CARGO ) ) {
        fold_and_print( w_details, point( col_1, line + 3 ), column_width, c_white,
                        "%s: <color_light_gray>%s %s</color>",
                        small_mode ? _( "Cap" ) : _( "Capacity" ),
                        format_volume( part->size ), volume_units_abbr() );
    }

    if( part->bonus > 0 ) {
        std::string label;
        if( part->has_flag( VPFLAG_SEATBELT ) ) {
            label = small_mode ? _( "Str" ) : _( "Strength" );
        } else if( part->has_flag( "HORN" ) ) {
            label = _( "Noise" );
        } else if( part->has_flag( "MUFFLER" ) ) {
            label = small_mode ? _( "NoisRed" ) : _( "Noise Reduction" );
        } else if( part->has_flag( VPFLAG_EXTENDS_VISION ) ) {
            label = _( "Range" );
        } else if( part->has_flag( VPFLAG_LIGHT ) || part->has_flag( VPFLAG_CONE_LIGHT ) ||
                   part->has_flag( VPFLAG_WIDE_CONE_LIGHT ) ||
                   part->has_flag( VPFLAG_CIRCLE_LIGHT ) || part->has_flag( VPFLAG_DOME_LIGHT ) ||
                   part->has_flag( VPFLAG_AISLE_LIGHT ) || part->has_flag( VPFLAG_EVENTURN ) ||
                   part->has_flag( VPFLAG_ODDTURN ) || part->has_flag( VPFLAG_ATOMIC_LIGHT ) ) {
            label = _( "Light" );
        }

        if( !label.empty() ) {
            fold_and_print( w_details, point( col_1, line + 3 ), column_width, c_white,
                            "%s: <color_light_gray>%d</color>", label,
                            part->bonus );
        }
    }

    if( part->has_flag( VPFLAG_WHEEL ) ) {
        // Note: there is no guarantee that whl is non-empty!
        const cata::value_ptr<islot_wheel> &whl = item::find_type( part->base_item )->wheel;
        fold_and_print( w_details, point( col_1, line + 3 ), column_width, c_white,
                        "%s: <color_light_gray>%d\"</color>",
                        small_mode ? _( "Dia" ) : _( "Wheel Diameter" ),
                        whl ? whl->diameter : 0 );
        fold_and_print( w_details, point( col_2, line + 3 ), column_width, c_white,
                        "%s: <color_light_gray>%d\"</color>",
                        small_mode ? _( "Wdt" ) : _( "Wheel Width" ),
                        whl ? whl->width : 0 );
    }

    if( part->epower != 0_W ) {
        fold_and_print( w_details, point( col_2, line + 3 ), column_width, c_white,
                        "%s: <color_light_gray>%+4d</color>",
                        small_mode ? _( "Epwr" ) : _( "Electric Power" ),
                        units::to_watt( part->epower ) );
    }

    // line 4 [horizontal]: fuel_type (if applicable)
    // line 4 [vertical/hybrid]: (column 1) fuel_type (if applicable)    (column 2) power (if applicable)
    // line 5 [horizontal]: power (if applicable)
    if( !part->fuel_type.is_null() ) {
        fold_and_print( w_details, point( col_1, line + 4 ), column_width,
                        c_white, _( "Charge: <color_light_gray>%s</color>" ),
                        item::nname( part->fuel_type ) );
    }
    int part_consumption = units::to_watt( part->energy_consumption );
    if( part_consumption != 0 ) {
        fold_and_print( w_details, point( col_2, line + 4 ), column_width, c_white,
                        _( "Drain: <color_light_gray>%+8d</color>" ), -part_consumption );
    }

    // line 5 [vertical/hybrid] flags
    std::vector<std::string> flags = { { "OPAQUE", "OPENABLE", "BOARDABLE" } };
    std::vector<std::string> flag_labels = { { _( "opaque" ), _( "openable" ), _( "boardable" ) } };
    std::string label;
    for( size_t i = 0; i < flags.size(); i++ ) {
        if( part->has_flag( flags[i] ) ) {
            label += ( label.empty() ? "" : " " ) + flag_labels[i];
        }
    }
    // 6 [horizontal]: (column 1) flags    (column 2) battery capacity (if applicable)
    fold_and_print( w_details, point( col_1, line + 5 ), details_w, c_yellow, label );

    if( part->fuel_type == itype_battery && !part->has_flag( VPFLAG_ENGINE ) &&
        !part->has_flag( VPFLAG_ALTERNATOR ) ) {
        const cata::value_ptr<islot_magazine> &battery = item::find_type( part->base_item )->magazine;
        fold_and_print( w_details, point( col_2, line + 5 ), column_width, c_white,
                        "%s: <color_light_gray>%8d</color>",
                        small_mode ? _( "BatCap" ) : _( "Battery Capacity" ),
                        battery->capacity );
    } else {
        units::power part_power = part->power;
        if( part_power != 0_W ) {
            fold_and_print( w_details, point( col_2, line + 5 ), column_width, c_white,
                            _( "Power: <color_light_gray>%+8d</color>" ), units::to_watt( part_power ) );
        }
    }

    wnoutrefresh( w_details );
}

void veh_interact::count_durability()
{
    const vehicle_part_range vpr = veh->get_all_parts();
    int qty = std::accumulate( vpr.begin(), vpr.end(), 0,
    []( int lhs, const vpart_reference & rhs ) {
        return lhs + std::max( rhs.part().base.damage(), rhs.part().base.degradation() );
    } );

    int total = std::accumulate( vpr.begin(), vpr.end(), 0,
    []( int lhs, const vpart_reference & rhs ) {
        return lhs + rhs.part().base.max_damage();
    } );

    int pct = total ? 100 * qty / total : 0;

    if( pct < 5 ) {
        total_durability_text = _( "like new" );
        total_durability_color = c_light_green;

    } else if( pct < 33 ) {
        total_durability_text = _( "dented" );
        total_durability_color = c_yellow;

    } else if( pct < 66 ) {
        total_durability_text = _( "battered" );
        total_durability_color = c_magenta;

    } else if( pct < 100 ) {
        total_durability_text = _( "wrecked" );
        total_durability_color = c_red;

    } else {
        total_durability_text = _( "destroyed" );
        total_durability_color = c_dark_gray;
    }
}

void act_vehicle_siphon( map &here, vehicle *veh )
{
    std::vector<itype_id> fuels;
    bool has_liquid = false;
    // Check all tanks on this vehicle to see if they contain any liquid
    for( const vpart_reference &vp : veh->get_any_parts( VPFLAG_FLUIDTANK ) ) {
        if( vp.part().contains_liquid() ) {
            has_liquid = true;
            break;
        }
    }
    if( !has_liquid ) {
        add_msg( m_info, _( "The vehicle has no liquid fuel left to siphon." ) );
        return;
    }

    std::string title = _( "Select tank to siphon:" );
    auto sel = []( const map &, const vehicle_part & pt ) {
        return pt.contains_liquid();
    };
    if( const std::optional<vpart_reference> tank = veh_interact::select_part( here, *veh, sel,
            title ) ) {
        item liquid( tank->part().get_base().only_item() );
        const int liq_charges = liquid.charges;
        liquid_dest_opt liquid_target;
        if( liquid_handler::handle_liquid( liquid, liquid_target, nullptr, 1, nullptr, veh,
                                           tank->part_index() ) ) {
            veh->drain( here, tank->part_index(), liq_charges - liquid.charges );
            veh->invalidate_mass();
        }
    }
}

void act_vehicle_unload_fuel( map &here, vehicle *veh )
{
    std::vector<itype_id> fuels;
    for( auto &e : veh->fuels_left( ) ) {
        const itype *type = item::find_type( e.first );

        if( e.first == fuel_type_battery || type->phase != phase_id::SOLID ) {
            // This skips battery and plutonium cells
            continue;
        }
        fuels.push_back( e.first );
    }
    if( fuels.empty() ) {
        add_msg( m_info, _( "The vehicle has no solid fuel left to remove." ) );
        return;
    }
    itype_id fuel;
    if( fuels.size() > 1 ) {
        uilist smenu;
        smenu.text = _( "Remove what?" );
        for( auto &fuel : fuels ) {
            if( fuel == itype_plut_cell && veh->fuel_left( here,  fuel ) < PLUTONIUM_CHARGES ) {
                continue;
            }
            smenu.addentry( item::nname( fuel ) );
        }
        smenu.query();
        if( smenu.ret < 0 || static_cast<size_t>( smenu.ret ) >= fuels.size() ) {
            add_msg( m_info, _( "Never mind." ) );
            return;
        }
        fuel = fuels[smenu.ret];
    } else {
        fuel = fuels.front();
    }

    Character &player_character = get_player_character();
    int qty = veh->fuel_left( here, fuel );
    if( fuel == itype_plut_cell ) {
        if( qty / PLUTONIUM_CHARGES == 0 ) {
            add_msg( m_info, _( "The vehicle has no charged plutonium cells." ) );
            return;
        }
        item plutonium( fuel, calendar::turn, qty / PLUTONIUM_CHARGES );
        player_character.i_add( plutonium );
        veh->drain( here, fuel, qty - ( qty % PLUTONIUM_CHARGES ) );
    } else {
        item solid_fuel( fuel, calendar::turn, qty );
        player_character.i_add( solid_fuel );
        veh->drain( here, fuel, qty );
    }

}

/**
 * Called when the activity timer for installing parts, repairing, etc times
 * out and the action is complete.
 */
void veh_interact::complete_vehicle( map &here, Character &you )
{
    if( you.activity.values.size() < 7 ) {
        debugmsg( "ACT_VEHICLE values.size() is %d", you.activity.values.size() );
        return;
    }
    if( you.activity.str_values.empty() ) {
        debugmsg( "ACT_VEHICLE str_values is empty" );
        return;
    }
    const tripoint_abs_ms act_pos( you.activity.values[0], you.activity.values[1], you.posz() );
    optional_vpart_position ovp = here.veh_at( act_pos );
    if( !ovp ) {
        // so the vehicle could have lost some of its parts from other NPCS works
        // during this player/NPCs activity.
        // check the vehicle points that were stored at beginning of activity.
        for( const tripoint_abs_ms &pt : you.activity.coord_set ) {
            ovp = here.veh_at( here.get_bub( pt ) );
            if( ovp ) {
                break;
            }
        }
        // check again, to see if it really is a case of vehicle gone missing.
        if( !ovp ) {
            debugmsg( "Activity ACT_VEHICLE: vehicle not found" );
            return;
        }
    }

    vehicle &veh = ovp->vehicle();
    const point_rel_ms d( you.activity.values[4], you.activity.values[5] );
    const vpart_id part_id( you.activity.str_values[0] );
    const vpart_info &vpinfo = part_id.obj();
    const bool editor_test = you.activity.str_values.size() > 1 &&
                             you.activity.str_values[1] == "vehicle_editor_test";

    // cmd = Install Repair reFill remOve Siphon Unload reName relAbel
    switch( static_cast<char>( you.activity.index ) ) {
        case 'i': {
            const inventory &inv = you.crafting_inventory();
            const requirement_data reqs = vpinfo.install_requirements();
            if( !editor_test &&
                !reqs.can_make_with_inventory( inv, is_crafting_component, 1, craft_flags::none, false ) ) {
                you.add_msg_player_or_npc( m_info,
                                           _( "You don't meet the requirements to install the %s." ),
                                           _( "<npcname> doesn't meet the requirements to install the %s." ),
                                           vpinfo.name() );
                break;
            }

            item base;
            std::vector<item> installed_with;
            if( editor_test ) {
                base = item( vpinfo.base_item );
            } else {
                for( const std::vector<item_comp> &e : reqs.get_components() ) {
                    for( item &obj : you.consume_items( e, 1, is_crafting_component, [&vpinfo]( const itype_id & itm ) {
                    return itm == vpinfo.base_item;
                } ) ) {
                        if( obj.typeId() == vpinfo.base_item ) {
                            base = obj;
                        } else {
                            installed_with.push_back( obj );
                        }
                    }
                }
                if( base.is_null() ) {
                    if( !you.has_trait( trait_DEBUG_HS ) ) {
                        add_msg( m_info, _( "Could not find base part in requirements for %s." ), vpinfo.name() );
                        break;
                    }
                    base = item( vpinfo.base_item );
                }

                for( const auto &e : reqs.get_tools() ) {
                    you.consume_tools( e );
                }
                you.invalidate_crafting_inventory();
            }
            const int partnum = veh.install_part( here, d, part_id, std::move( base ), installed_with );
            if( partnum < 0 ) {
                debugmsg( "complete_vehicle install part fails dx=%d dy=%d id=%s",
                          d.x(), d.y(), part_id.c_str() );
                break;
            }
            ::vehicle_part &vp_new = veh.part( partnum );
            if( vp_new.info().variants.size() > 1 ) {
                do_change_shape_menu( vp_new );
            }

            // Need map-relative coordinates to compare to output of look_around.
            // Need to call coord_translate() directly since it's a new part.
            const point_rel_ms q = veh.coord_translate( d );

            if( vpinfo.has_flag( VPFLAG_CONE_LIGHT ) ||
                vpinfo.has_flag( VPFLAG_WIDE_CONE_LIGHT ) ||
                vpinfo.has_flag( VPFLAG_HALF_CIRCLE_LIGHT ) ) {
                orient_part( here, &veh, vpinfo, partnum, q );
            }

            const tripoint_bub_ms vehp = veh.pos_bub( here ) + tripoint_rel_ms( q, 0 );
            // TODO: allow boarding for non-players as well.
            Character *const pl = get_creature_tracker().creature_at<Character>( vehp );
            if( vpinfo.has_flag( VPFLAG_BOARDABLE ) && pl ) {
                here.board_vehicle( vehp, pl );
            }

            you.add_msg_if_player( m_good, _( "You install a %1$s into the %2$s." ), vp_new.name(), veh.name );

            if( !editor_test ) {
                for( const auto &sk : vpinfo.install_skills ) {
                    you.practice( sk.first, veh_utils::calc_xp_gain( vpinfo, sk.first, you ) );
                }
            }
            here.add_vehicle_to_cache( &veh );
            break;
        }

        case 'r': {
            vehicle_part &vp = veh.part( you.activity.values[6] );
            veh_utils::repair_part( here, veh, vp, you, !editor_test );
            break;
        }

        case 'f': {
            const bool batch = you.activity.str_values.size() > 2 &&
                               you.activity.str_values[2] == "vehicle_refill_batch";
            const size_t transfer_count = batch ? you.activity.targets.size() :
                                          std::min<size_t>( 1, you.activity.targets.size() );
            if( transfer_count == 0 ) {
                debugmsg( "Activity ACT_VEHICLE: missing refill source" );
                break;
            }

            const auto refill_one = [&]( vehicle_part &vp, item_location &src ) {
                if( !src ) {
                    debugmsg( "Activity ACT_VEHICLE: refill source became invalid" );
                    return;
                }

                if( vp.is_tank() ) {
                    item_location liquid;
                    if( src->is_container() && !src->empty() ) {
                        liquid = item_location( src, &src->only_item() );
                    } else if( src->made_of( phase_id::LIQUID ) ) {
                        liquid = src;
                    }
                    if( !liquid || !liquid->made_of( phase_id::LIQUID ) ) {
                        debugmsg( "Activity ACT_VEHICLE: invalid liquid refill source" );
                        return;
                    }

                    const itype_id fuel_type = liquid->typeId();
                    contents_change_handler handler;
                    if( liquid.has_parent() ) {
                        handler.unseal_pocket_containing( liquid );
                    }
                    const int moved = vp.base.fill_with( *liquid, liquid->charges );
                    liquid->charges -= moved;
                    if( moved <= 0 ) {
                        return;
                    }

                    const int remaining_ammo_capacity = std::max( 0,
                            vp.item_capacity( fuel_type ) - vp.ammo_remaining() );
                    if( remaining_ammo_capacity ) {
                        you.add_msg_if_player( m_good, _( "You refill the %1$s's %2$s." ), veh.name, vp.name() );
                    } else {
                        you.add_msg_if_player( m_good, _( "You completely refill the %1$s's %2$s." ),
                                               veh.name, vp.name() );
                    }

                    if( liquid->charges <= 0 ) {
                        liquid.remove_item();
                    } else {
                        liquid.on_contents_changed();
                    }
                    handler.handle_by( you );
                    return;
                }

                if( vp.is_fuel_store() ) {
                    contents_change_handler handler;
                    handler.unseal_pocket_containing( src );
                    const int qty = src->charges;
                    vp.base.reload( you, std::move( src ), qty );
                    you.add_msg_if_player( m_good, _( "You refuel the %1$s's %2$s." ), veh.name, vp.name() );
                    handler.handle_by( you );
                    return;
                }

                debugmsg( "vehicle part is not reloadable" );
            };

            for( size_t i = 0; i < transfer_count; ++i ) {
                if( 6 + i >= you.activity.values.size() ) {
                    debugmsg( "Activity ACT_VEHICLE: missing refill part index" );
                    break;
                }
                const int part_index = you.activity.values[6 + i];
                if( part_index < 0 || part_index >= veh.part_count() ) {
                    debugmsg( "Activity ACT_VEHICLE: invalid refill part index %d", part_index );
                    continue;
                }
                refill_one( veh.part( part_index ), you.activity.targets[i] );
            }

            veh.invalidate_mass();
            break;
        }

        case 'O': // 'O' = remove appliance
        case 'o': {
            int vp_index = you.activity.values[6];
            if( vp_index >= veh.part_count() ) {
                vp_index = veh.get_next_shifted_index( vp_index, you );
                if( vp_index == -1 ) {
                    you.add_msg_if_player( m_info,
                                           //~ 1$s is the vehicle part name
                                           _( "The %1$s has already been removed by someone else." ),
                                           vpinfo.name() );
                    return;
                }
            }
            vehicle_part *vp = &veh.part( vp_index );
            const vpart_info &vpi = vp->info();
            const bool appliance_removal = static_cast<char>( you.activity.index ) == 'O';
            const bool wall_wire_removal = appliance_removal && vpi.id == vpart_ap_wall_wiring;
            const bool broken = vp->is_broken();
            const bool smash_remove = vpi.has_flag( "SMASH_REMOVE" );
            const inventory &inv = you.crafting_inventory();
            const requirement_data &reqs = vpi.removal_requirements();
            if( !editor_test && !reqs.can_make_with_inventory( inv, is_crafting_component ) ) {
                //~  1$s is the vehicle part name
                add_msg( m_info, _( "You don't meet the requirements to remove the %1$s." ), vpi.name() );
                break;
            }
            if( !editor_test ) {
                for( const auto &e : reqs.get_components() ) {
                    you.consume_items( e, 1, is_crafting_component );
                }
                for( const auto &e : reqs.get_tools() ) {
                    you.consume_tools( e );
                }
                you.invalidate_crafting_inventory();
            }

            // This will be a list of all the items which arise from this removal.
            std::list<item> resulting_items;

            // First we get all the contents of the part
            vehicle_stack contents = veh.get_items( *vp );
            resulting_items.insert( resulting_items.end(), contents.begin(), contents.end() );
            contents.clear();

            if( broken ) {
                you.add_msg_if_player( _( "You remove the broken %1$s from the %2$s." ), vp->name(), veh.name );
            } else if( smash_remove ) {
                you.add_msg_if_player( _( "You smash the %1$s to bits, removing it from the %2$s." ),
                                       vp->name(), veh.name );
            } else {
                you.add_msg_if_player( _( "You remove the %1$s from the %2$s." ), vp->name(), veh.name );
            }

            if( wall_wire_removal ) {
                if( !editor_test ) {
                    veh.part_to_item( here, *vp );
                }
            } else if( vpi.has_flag( "TOW_CABLE" ) ) {
                veh.invalidate_towing( here, true, &you );
            } else if( editor_test ) {
                // Test removal intentionally produces no part/salvage items.
            } else if( broken ) {
                item_group::ItemList pieces = vp->pieces_for_broken_part();
                resulting_items.insert( resulting_items.end(), pieces.begin(), pieces.end() );
            } else {
                if( smash_remove ) {
                    item_group::ItemList pieces = vp->pieces_for_broken_part();
                    resulting_items.insert( resulting_items.end(), pieces.begin(), pieces.end() );
                } else {
                    resulting_items.push_back( veh.removed_part( here, *vp ) );

                    // damage reduces chance of success (0.8^damage_level)
                    const double component_success_chance = std::pow( 0.8, vp->damage_level() );
                    const double charges_min = std::clamp( component_success_chance, 0.0, 1.0 );
                    const double charges_max = std::clamp( component_success_chance + 0.1, 0.0, 1.0 );
                    for( item &it : vp->get_salvageable() ) {
                        if( it.count_by_charges() ) {
                            const int charges_befor = it.charges;
                            it.charges *= rng_float( charges_min, charges_max );
                            const int charges_destroyed = charges_befor - it.charges;
                            if( charges_destroyed > 0 ) {
                                you.add_msg_player_or_npc( m_bad,
                                                           _( "You fail to recover %1$d %2$s." ),
                                                           _( "<npcname> fails to recover %1$d %2$s." ),
                                                           charges_destroyed,
                                                           it.type_name( charges_destroyed ) );
                            }
                            if( it.charges > 0 ) {
                                resulting_items.push_back( it );
                            }
                        } else if( component_success_chance > rng_float( 0, 1 ) ) {
                            resulting_items.push_back( it );
                        } else {
                            you.add_msg_player_or_npc( m_bad,
                                                       _( "You fail to recover %1$s." ),
                                                       _( "<npcname> fails to recover %1$s." ),
                                                       it.type_name() );
                        }
                    }
                }
                if( !editor_test ) {
                    for( const std::pair<const skill_id, int> &sk : vpi.install_skills ) {
                        // removal is half as educational as installation
                        you.practice( sk.first, veh_utils::calc_xp_gain( vpi, sk.first, you ) / 2 );
                    }
                }
            }

            // Power cables must remove parts from the target vehicle, too.
            if( vpi.has_flag( VPFLAG_POWER_TRANSFER ) ) {
                veh.remove_remote_part( here, *vp );
            }

            if( appliance_removal && veh.part_count() > 1 ) {
                // Split up power grids
                veh.find_and_split_vehicles( here, { vp_index } );
                veh.part_removal_cleanup( here );
                // Ensure the position, pivot, and precalc points are up-to-date
                veh.pos -= veh.pivot_anchor[0];
                veh.precalc_mounts( 0, veh.turn_dir, point_rel_ms::zero );
                here.rebuild_vehicle_level_caches();

                if( auto newpart = here.veh_at( act_pos ).part_with_feature( VPFLAG_APPLIANCE, false ) ) {
                    vp = &newpart->part();
                } else {
                    debugmsg( "No appliance part left to remove after splitting vehicle!" );
                    vp = nullptr;
                }
                //always stop after removing an appliance
                you.activity.set_to_null();
            }

            // Save these values now so they aren't lost when parts or vehicles are destroyed.
            const point_rel_ms part_mount = vp->mount;
            const tripoint_bub_ms part_pos = veh.bub_part_pos( here, *vp );

            veh.unlink_cables( here, part_mount, you,
                               false, /* unneeded as items will be unlinked if the connected part is removed */
                               appliance_removal || vpi.location == "structure",
                               appliance_removal || vpi.has_flag( VPFLAG_CABLE_PORTS ) || vpi.has_flag( VPFLAG_BATTERY ) );

            if( veh.part_count_real() <= 1 ) {
                you.add_msg_if_player( _( "You completely dismantle the %s." ), veh.name );
                you.activity.set_to_null();
                // destroy vehicle clears the cache
                here.destroy_vehicle( &veh );
            } else if( vp ) {
                veh.remove_part( *vp );
                // part_removal_cleanup calls refresh, so parts_at_relative is valid
                veh.part_removal_cleanup( here );
                if( veh.parts_at_relative( part_mount, true ).empty() ) {
                    here.clear_vehicle_point_from_cache( &veh, part_pos );
                }
            }
            // This will be part of an NPC "job" where they need to clean up the activity
            // items afterwards
            if( you.is_npc() ) {
                for( item &it : resulting_items ) {
                    it.set_var( "activity_var", you.name );
                }
            }
            // Finally, put all the results somewhere (we wanted to wait until this
            // point because we don't want to put them back into the vehicle part
            // that just got removed).
            std::vector<item_location> locs = put_into_vehicle_or_drop_ret_locs( you,
                                              item_drop_reason::deliberate,
                                              resulting_items );
            if( you.is_npc() ) {
                for( const item_location &itl : locs ) {
                    you.may_activity_occupancy_after_end_items_loc.push_back( itl );
                }
            }
            break;
        }
        case 'u': {
            // Unplug action just sheds loose connections,
            // assuming vehicle::shed_loose_parts was already called so that
            // the removed parts have had time to be processed
            you.add_msg_if_player( _( "You disconnect the %s's power connection." ), veh.name );
            break;
        }
    }
    you.invalidate_crafting_inventory();
    you.invalidate_weight_carried_cache();
}
