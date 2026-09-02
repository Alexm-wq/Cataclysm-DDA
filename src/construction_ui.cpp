#include "construction_ui.h"

#include <algorithm>
#include <chrono>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "cata_scope_helpers.h"
#include "catacharset.h"
#include "character.h"
#include "color.h"
#include "construction.h"
#include "construction_category.h"
#include "construction_group.h"
#include "construction_plan.h"
#include "construction_target.h"
#include "crafting.h"
#include "cursesdef.h"
#include "debug.h"
#include "display.h"
#include "game.h"
#include "game_constants.h"
#include "input.h"
#include "input_context.h"
#include "inventory.h"
#include "line.h"
#include "map.h"
#include "mapdata.h"
#include "memory_fast.h"
#include "messages.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "requirements.h"
#include "ret_val.h"
#include "skill.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/dropdown.h"
#include "ui_helpers/controls/scroll_view.h"
#include "ui_helpers/controls/selection_list.h"
#include "ui_helpers/controls/text_field.h"
#include "ui_helpers/controls/text_input_dialog.h"
#include "ui_helpers/controls/world_viewport.h"
#include "ui_manager.h"
#include "uistate.h"
#include "weather.h"
#include "weather_type.h"

#if defined(TILES)
#include "cata_tiles.h"
#include "sdl_utils.h"
#include "sdltiles.h"
#endif

namespace
{

static const construction_category_id construction_category_ALL( "ALL" );
static const construction_category_id construction_category_FILTER( "FILTER" );
static const activity_id ACT_MULTIPLE_CONSTRUCTION( "ACT_MULTIPLE_CONSTRUCTION" );
static constexpr int viewport_animation_interval_ms = 125;

static std::optional<point> input_event_window_position( const input_event &event,
        const catacurses::window &window )
{
    if( event.type != input_event_t::mouse || !window ) {
        return std::nullopt;
    }
#if defined(TILES)
    const window_dimensions dimensions = get_window_dimensions( window );
    if( dimensions.scaled_font_size.x <= 0 || dimensions.scaled_font_size.y <= 0 ) {
        return std::nullopt;
    }
    const point relative_pixel = event.mouse_pos - dimensions.window_pos_pixel;
    if( relative_pixel.x < 0 || relative_pixel.y < 0 ) {
        return std::nullopt;
    }
    const point result( relative_pixel.x / dimensions.scaled_font_size.x,
                        relative_pixel.y / dimensions.scaled_font_size.y );
#else
    const point result = event.mouse_pos - point( getbegx( window ), getbegy( window ) );
#endif
    if( result.x < 0 || result.y < 0 || result.x >= getmaxx( window ) ||
        result.y >= getmaxy( window ) ) {
        return std::nullopt;
    }
    return result;
}

enum class workspace_focus : int {
    palette,
    viewport,
    inspector
};

enum class construction_workspace_mode : int {
    build,
    place,
    remove,
    markers,
    plan,
    plans
};

static std::string construction_plan_entry_id( const tripoint_abs_ms &position )
{
    return string_format( "PLAN_%d_%d_%d", position.x(), position.y(), position.z() );
}

static std::pair<std::string, nc_color> construction_plan_marker(
    const construction_plan_status status )
{
    switch( status ) {
        case construction_plan_status::ready:
            return { "◆", c_light_green };
        case construction_plan_status::missing_requirements:
            return { "!", c_yellow };
        case construction_plan_status::unreachable:
            return { "×", c_light_red };
        case construction_plan_status::invalidated:
            return { "×", c_red };
        case construction_plan_status::in_progress:
            return { "▣", c_light_blue };
        case construction_plan_status::completed:
            return { "✓", c_dark_gray };
    }
    return { "?", c_light_red };
}

static bool construction_plan_can_execute( const construction_plan_status status )
{
    return status == construction_plan_status::ready ||
           status == construction_plan_status::missing_requirements ||
           status == construction_plan_status::in_progress;
}

struct construction_build_order {
    construction_id id = construction_id( -1 );
    tripoint_bub_ms target;
    bool resume = false;
    bool carried_source_only = false;
};

static std::string construction_result_name( const construction &con )
{
    if( con.post_terrain.empty() ) {
        return _( "Special construction operation" );
    }
    return con.post_is_furniture ? furn_str_id( con.post_terrain )->name() :
           ter_str_id( con.post_terrain )->name();
}

static std::string construction_result_description( const construction &con )
{
    if( con.post_terrain.empty() ) {
        return con.pre_note.empty() ? std::string() : con.pre_note.translated();
    }
    return con.post_is_furniture ? furn_str_id( con.post_terrain )->description.translated() :
           ter_str_id( con.post_terrain )->description.translated();
}

static std::string contextual_intent_label( const construction_ui_intent intent )
{
    switch( intent ) {
        case construction_ui_intent::place:
            return _( "Place" );
        case construction_ui_intent::repair:
            return _( "Repair" );
        case construction_ui_intent::finish:
            return _( "Finish" );
        case construction_ui_intent::modify:
            return _( "Modify" );
        case construction_ui_intent::upgrade:
            return _( "Upgrade" );
        case construction_ui_intent::terrain_work:
            return _( "Terrain work" );
        case construction_ui_intent::decorate:
            return _( "Decorate" );
        case construction_ui_intent::marker:
            return _( "Mark" );
        case construction_ui_intent::remove:
            return _( "Remove" );
        case construction_ui_intent::build:
            return _( "Build" );
    }
    return _( "Work" );
}

static std::string contextual_action_label( const construction_context_action &action )
{
    if( action.resolution.id.is_valid() ) {
        const construction &chosen = action.resolution.id.obj();
        if( !chosen.ui_name.empty() ) {
            return chosen.ui_name.translated();
        }
        if( action.intent == construction_ui_intent::repair ) {
            return contextual_intent_label( action.intent );
        }
        if( !chosen.ui_action.empty() && chosen.ui_action != chosen.group.str() ) {
            return contextual_intent_label( action.intent );
        }
        return chosen.group->name();
    }
    return contextual_intent_label( action.intent );
}

static std::string contextual_action_id( const construction_context_action &action )
{
    return string_format( "CONTEXT_%d_%s", static_cast<int>( action.intent ), action.key );
}

static std::string catalog_section_label( const construction_ui_section section )
{
    switch( section ) {
        case construction_ui_section::structures:
            return _( "Structures" );
        case construction_ui_section::furniture:
            return _( "Furniture" );
        case construction_ui_section::workshop:
            return _( "Workshop & utilities" );
        case construction_ui_section::outdoor:
            return _( "Outdoor" );
        case construction_ui_section::infrastructure:
            return _( "Infrastructure" );
        case construction_ui_section::appliances:
            return _( "Appliances" );
        case construction_ui_section::other:
            return _( "Other" );
    }
    return _( "Other" );
}

static std::string catalog_section_id( const construction_ui_section section )
{
    return string_format( "SECTION_%d", static_cast<int>( section ) );
}

static std::optional<construction_ui_section> catalog_section_from_id( const std::string &id )
{
    for( const construction_ui_section section : {
             construction_ui_section::structures, construction_ui_section::furniture,
             construction_ui_section::workshop, construction_ui_section::outdoor,
             construction_ui_section::infrastructure, construction_ui_section::appliances,
             construction_ui_section::other
         } ) {
        if( catalog_section_id( section ) == id ) {
            return section;
        }
    }
    return std::nullopt;
}

class construction_workspace
{
    public:
        construction_workspace();
        ~construction_workspace();
        bool run();
        bool activity_handoff_active() const;
        void begin_activity_handoff();
        void resume_activity_handoff( bool construction_completed = false );
        void suspend_for_query();
        void restore_after_query();
        bool poll_activity_input();
        void redraw_handoff_if_needed();
        void set_activity_failure( std::string reason );
        void mark_construction_started();
        bool preserve_on_activity_cancel() const;

    private:
        shared_ptr_fast<ui_adaptor> create_or_get_ui_adaptor();
        void create_layout( ui_adaptor &ui );
        void draw( ui_adaptor &ui );
        void draw_header();
        void draw_palette();
        void draw_inspector();
        void draw_footer();
        void draw_world_overlay() const;
        void rebuild_palette();
        void rebuild_inspector();
        void refresh_active_target();
        void clear_selection();
        void set_focus( workspace_focus next, ui_adaptor &ui );
        void set_workspace_mode( construction_workspace_mode next, ui_adaptor &ui );
        void edit_search();
        void open_category_menu();
        void open_context_menu( const point &anchor, const tripoint_bub_ms &target );
        void open_context_intent_menu( const point &anchor, const tripoint_bub_ms &target,
                                       construction_ui_intent intent );
        bool execute_context_action( const std::string &id );
        bool request_action( const tripoint_bub_ms &target );
        bool request_plan( const tripoint_bub_ms &target );
        bool remove_selected_plan();
        bool request_execute_plans();
        bool request_context_action( const std::string &id, const tripoint_bub_ms &target );
        bool handle_input( const std::string &action, input_context &context, ui_adaptor &ui );
        bool handle_pointer( const std::string &action, input_context &context, ui_adaptor &ui );
        bool handle_viewport_action( const ui_world_viewport_action &action, ui_adaptor &ui );
        int handoff_progress_step() const;
        bool handoff_visual_changed() const;
        void remember_handoff_visual_state();
        void audit_camera_state( const char *source, bool intentional_change = false );
        void synchronize_handoff_coordinates();
        bool target_is_adjacent( const tripoint_bub_ms &target ) const;
        std::optional<tripoint_bub_ms> displayed_target() const;
        const construction *resolved_construction() const;
        const construction *catalog_preview_construction(
            const construction_group_str_id &group ) const;
        bool palette_accepts( const construction &con ) const;
        const read_only_visitable &active_inventory() const;
        construction_target_resolution resolve_active_target( const tripoint_bub_ms &target ) const;
        std::string category_label() const;
        std::string placement_prompt() const;
        std::string player_status_line() const;
        std::string footer_status() const;
        void refresh_nearby_plans();
        void rebuild_plan_palette();
        void rebuild_plans_inspector();
        const construction_plan *plan_at( const tripoint_abs_ms &position ) const;
        const construction_plan *selected_plan() const;
        void select_plan( const tripoint_abs_ms &position, bool center_view );

        avatar &you;
        map &here;
        const int original_zoom;

        catacurses::window header;
        catacurses::window palette_window;
        catacurses::window inspector_window;
        catacurses::window footer;
#if defined(TILES)
        catacurses::window viewport_window;
#endif

        ui_action_strip header_actions;
        ui_action_strip palette_actions;
        ui_action_strip contextual_action_strip;
        ui_action_strip primary_action;
        ui_text_field search_field;
        ui_selection_list palette;
        ui_scroll_view inspector;
        ui_dropdown category_menu;
        ui_dropdown context_menu;
        ui_world_viewport viewport;
        shared_ptr_fast<ui_adaptor> ui;
#if !defined(TILES)
        shared_ptr_fast<game::draw_callback_t> overlay;
#endif

        workspace_focus focus = workspace_focus::palette;
        construction_workspace_mode mode = construction_workspace_mode::build;
        construction_operation operation = construction_operation::build;
        std::optional<construction_ui_section> section_filter;
        construction_group_str_id selected_group = construction_group_str_id::NULL_ID();
        std::vector<construction_group_str_id> visible_groups;
        std::string search;
        std::string plans_search;
        std::string transient_status;
        bool show_unavailable = true;
        bool selection_cleared_by_user = false;
        bool compact = false;
        bool palette_visible = true;
        bool inspector_visible = true;
        bool exit_requested = false;
        bool activity_handoff = false;
        bool ui_hidden = false;
        bool handoff_repaint_pending = false;
        std::string handoff_failure_status;
        std::optional<tripoint_bub_ms> last_handoff_player_position;
        int last_handoff_progress_step = -1;
        bool last_handoff_walking = false;
        bool last_handoff_building = false;
        bool handoff_waiting_for_start = false;
        int last_handoff_light_level = -1;
        weather_type_id last_handoff_weather = WEATHER_NULL;
        std::chrono::steady_clock::time_point next_handoff_animation_frame;
        std::string last_handoff_player_status;

        std::optional<tripoint_bub_ms> last_camera_center;
        std::optional<tripoint_abs_ms> last_camera_center_abs;
        std::optional<tripoint_abs_ms> last_camera_player_abs;
        std::optional<tripoint_abs_ms> last_camera_selected_abs;
        std::optional<tripoint_abs_ms> handoff_target_abs;
        std::optional<tripoint_abs_ms> handoff_camera_center_abs;
        construction_id handoff_construction_id = construction_id( -1 );
        bool suppress_next_select_release = false;
        bool suppress_next_secondary_release = false;

        int palette_width = 0;
        int inspector_width = 0;
        int content_top = 4;
        int content_bottom = 0;

        std::optional<tripoint_bub_ms> hovered_target;
        std::optional<tripoint_bub_ms> selected_target;
        std::optional<tripoint_bub_ms> context_target;
        std::optional<point> context_anchor;
        construction_target_resolution resolution;
        std::vector<construction_context_action> context_actions;
        std::vector<std::pair<tripoint_bub_ms, construction_target_resolution>> adjacent_resolutions;
        std::vector<std::string> inspector_lines;
        std::optional<construction_build_order> build_order;
        std::vector<construction_plan> nearby_plans;
        std::vector<tripoint_abs_ms> visible_plan_positions;
        std::optional<tripoint_abs_ms> selected_plan_abs;
        construction_group_str_id catalog_group_before_plans =
            construction_group_str_id::NULL_ID();
        bool execute_plans_order = false;
};

construction_workspace *persistent_workspace = nullptr;

construction_workspace::construction_workspace() :
    you( get_avatar() ), here( get_map() ), original_zoom( g->get_zoom() )
{
#if defined(TILES)
    // The Construction map is a real auxiliary viewport.  Its camera and zoom
    // are owned by ui_world_viewport and never alter the gameplay camera.
    viewport.configure_map_camera( you.pos_bub() );
#endif
    search = uistate.construction_filter;
    if( uistate.last_construction.is_valid() ) {
        selected_group = uistate.last_construction;
        const std::vector<construction *> variants = constructions_by_group( selected_group );
        if( std::none_of( variants.begin(), variants.end(), []( const construction * candidate ) {
        return candidate != nullptr && construction_is_catalog_action( *candidate );
        } ) ) {
            selected_group = construction_group_str_id::NULL_ID();
        }
    }
    palette.hover_previews( false );
    rebuild_palette();
    refresh_active_target();
}

construction_workspace::~construction_workspace()
{
    viewport.cancel_map_capture();
#if defined(TILES)
    viewport.detach_map_preview();
    clear_ui_tile_previews();
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( false );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( false );
    }
#else
    overlay.reset();
#endif
    if( ui ) {
        ui->set_disable_uis_below( false );
        ui.reset();
    }
    g->invalidate_main_ui_adaptor();
}

shared_ptr_fast<ui_adaptor> construction_workspace::create_or_get_ui_adaptor()
{
    shared_ptr_fast<ui_adaptor> current_ui = ui;
    if( !current_ui ) {
#if defined(TILES)
        ui = current_ui = make_shared_fast<ui_adaptor>( ui_adaptor::disable_uis_below{} );
#else
        ui = current_ui = make_shared_fast<ui_adaptor>();
#endif
        current_ui->on_screen_resize( [this]( ui_adaptor & adaptor ) {
            if( ui_hidden ) {
                adaptor.position( point::zero, point::zero );
                return;
            }
            create_layout( adaptor );
        } );
        current_ui->on_redraw( [this]( ui_adaptor & adaptor ) {
            if( ui_hidden ) {
                return;
            }
            // The game invalidates the top UI every simulated turn.  During a
            // walk/build handoff, repaint only when the player moves, the phase
            // changes, or the compact progress bar advances.
            if( activity_handoff && !handoff_repaint_pending && !handoff_visual_changed() ) {
                return;
            }
            draw( adaptor );
            remember_handoff_visual_state();
            handoff_repaint_pending = false;
        } );
    }
    return current_ui;
}

bool construction_workspace::activity_handoff_active() const
{
    return activity_handoff;
}

int construction_workspace::handoff_progress_step() const
{
    const std::optional<tripoint_bub_ms> target = activity_handoff && handoff_target_abs ?
            std::optional<tripoint_bub_ms>( here.get_bub( *handoff_target_abs ) ) : selected_target;
    if( !target ) {
        return -1;
    }
    const partial_con *partial = here.partial_con_at( *target );
    if( partial == nullptr ) {
        return -1;
    }
    return std::clamp( partial->counter / 500000, 0, 20 );
}

bool construction_workspace::handoff_visual_changed() const
{
    const bool animation_due = viewport.has_animated_weather() &&
                               std::chrono::steady_clock::now() >= next_handoff_animation_frame;
    const std::optional<tripoint_abs_ms> selected_abs = selected_target ?
            std::optional<tripoint_abs_ms>( here.get_abs( *selected_target ) ) : std::nullopt;
    const bool target_drifted = handoff_target_abs && selected_abs != handoff_target_abs;
    const bool camera_drifted = handoff_camera_center_abs && viewport.has_map_preview() &&
                                here.get_abs( viewport.map_camera_center( you ) ) !=
                                *handoff_camera_center_abs;
    const bool walking = you.has_destination() || you.has_destination_activity();
    return last_handoff_player_position != you.pos_bub() ||
           last_handoff_progress_step != handoff_progress_step() ||
           last_handoff_walking != walking ||
           last_handoff_building != static_cast<bool>( you.activity ) ||
           last_handoff_light_level != g->light_level( you.posz() ) ||
           last_handoff_weather != get_weather().weather_id ||
           last_handoff_player_status != player_status_line() || target_drifted ||
           camera_drifted || animation_due;
}

void construction_workspace::remember_handoff_visual_state()
{
    if( !activity_handoff ) {
        return;
    }
    last_handoff_player_position = you.pos_bub();
    last_handoff_progress_step = handoff_progress_step();
    last_handoff_walking = you.has_destination() || you.has_destination_activity();
    last_handoff_building = static_cast<bool>( you.activity );
    last_handoff_light_level = g->light_level( you.posz() );
    last_handoff_weather = get_weather().weather_id;
    last_handoff_player_status = player_status_line();
    next_handoff_animation_frame = std::chrono::steady_clock::now() +
                                   std::chrono::milliseconds( viewport_animation_interval_ms );
}

void construction_workspace::audit_camera_state( const char *source,
        const bool intentional_change )
{
    if( !viewport.has_map_preview() ) {
        return;
    }
    const tripoint_bub_ms center = viewport.map_camera_center( you );
    const tripoint_abs_ms center_abs = here.get_abs( center );
    const tripoint_abs_ms player_abs = you.pos_abs();
    const std::optional<tripoint_abs_ms> selected_abs = selected_target ?
            std::optional<tripoint_abs_ms>( here.get_abs( *selected_target ) ) : std::nullopt;
    const bool target_drifted = activity_handoff && handoff_target_abs &&
                                selected_abs != handoff_target_abs;
    const bool camera_drifted = activity_handoff && handoff_camera_center_abs &&
                                center_abs != *handoff_camera_center_abs;

    const bool previous_camera_changed = last_camera_center && last_camera_center_abs &&
                                         ( *last_camera_center != center ||
                                           *last_camera_center_abs != center_abs );
    if( !intentional_change && ( previous_camera_changed || target_drifted || camera_drifted ) ) {
        const bool bubble_rebased = last_camera_center && last_camera_center_abs &&
                                    *last_camera_center == center &&
                                    *last_camera_center_abs != center_abs;
        DebugLog( D_WARNING, D_GAME )
                << "[CONSTRUCTION_CAMERA_ANOMALY] source=" << source
                << " suspected=" << ( target_drifted ? "selected-target-drift" :
                                       bubble_rebased || camera_drifted ? "reality-bubble-rebase" :
                                       "unrequested-camera-change" )
                << " old_center_bub=" << ( last_camera_center ?
                                              last_camera_center->to_string_writable() : "none" )
                << " new_center_bub=" << center.to_string_writable()
                << " old_center_abs=" << ( last_camera_center_abs ?
                                              last_camera_center_abs->to_string_writable() : "none" )
                << " new_center_abs=" << center_abs.to_string_writable()
                << " old_player_abs=" << ( last_camera_player_abs ?
                                             last_camera_player_abs->to_string_writable() : "none" )
                << " new_player_bub=" << you.pos_bub().to_string_writable()
                << " new_player_abs=" << player_abs.to_string_writable()
                << " old_selected_abs=" << ( last_camera_selected_abs ?
                                               last_camera_selected_abs->to_string_writable() : "none" )
                << " selected_bub=" << ( selected_target ?
                                           selected_target->to_string_writable() : "none" )
                << " selected_abs=" << ( selected_abs ?
                                           selected_abs->to_string_writable() : "none" )
                << " anchored_target_abs=" << ( handoff_target_abs ?
                                                  handoff_target_abs->to_string_writable() : "none" )
                << " anchored_camera_abs=" << ( handoff_camera_center_abs ?
                                                  handoff_camera_center_abs->to_string_writable() : "none" )
                << " map_origin_abs_sm=" << here.get_abs_sub().to_string_writable()
                << " zoom=" << viewport.map_zoom_percent()
                << " operation=" << static_cast<int>( operation )
                << " handoff=" << activity_handoff
                << " walking=" << you.has_destination()
                << " activity=" << ( you.activity ? you.activity.id().str() : "none" );
    }

    last_camera_center = center;
    last_camera_center_abs = center_abs;
    last_camera_player_abs = player_abs;
    last_camera_selected_abs = selected_abs;
}

void construction_workspace::synchronize_handoff_coordinates()
{
    if( !activity_handoff ) {
        return;
    }

    bool target_changed = false;
    if( handoff_target_abs ) {
        const tripoint_bub_ms rebased_target = here.get_bub( *handoff_target_abs );
        if( !selected_target || *selected_target != rebased_target ) {
            selected_target = rebased_target;
            hovered_target.reset();
            context_target.reset();
            target_changed = true;
        }
    }
    if( target_changed ) {
        refresh_active_target();
    }

    if( handoff_camera_center_abs ) {
        const tripoint_bub_ms rebased_center = here.get_bub( *handoff_camera_center_abs );
        if( viewport.map_camera_center( you ) != rebased_center ) {
            viewport.center_map_on( you, rebased_center );
        }
    }
    // The correction above is deliberate.  Record its rebased bubble values so
    // the next frame reports only a new drift, not this repair itself.
    audit_camera_state( "handoff-coordinate-rebase", true );
}

void construction_workspace::begin_activity_handoff()
{
    // Keep this exact workspace and adaptor registered while the player walks
    // to the site and while ACT_BUILD advances.
    activity_handoff = ui != nullptr;
    handoff_repaint_pending = activity_handoff;
    last_handoff_player_position.reset();
    last_handoff_progress_step = -1;
    last_handoff_walking = false;
    last_handoff_building = false;
    last_handoff_light_level = -1;
    last_handoff_weather = WEATHER_NULL;
    next_handoff_animation_frame = std::chrono::steady_clock::time_point();
    last_handoff_player_status.clear();
    handoff_target_abs = selected_target ?
                         std::optional<tripoint_abs_ms>( here.get_abs( *selected_target ) ) : std::nullopt;
    handoff_camera_center_abs = viewport.has_map_preview() ?
                                std::optional<tripoint_abs_ms>( here.get_abs(
                                            viewport.map_camera_center( you ) ) ) : std::nullopt;
    if( selected_target ) {
        const partial_con *partial = here.partial_con_at( *selected_target );
        handoff_construction_id = partial != nullptr && partial->id.is_valid() ?
                                  partial->id : resolution.id;
    } else {
        handoff_construction_id = construction_id( -1 );
    }
    handoff_waiting_for_start = activity_handoff && you.has_destination() &&
                                selected_target &&
                                here.partial_con_at( *selected_target ) == nullptr;
}

void construction_workspace::resume_activity_handoff( const bool construction_completed )
{
    synchronize_handoff_coordinates();
    if( handoff_failure_status.empty() ) {
        if( selected_target && here.partial_con_at( *selected_target ) != nullptr ) {
            handoff_failure_status =
                _( "Construction was interrupted.  The unfinished work remains at the selected tile." );
        } else if( handoff_waiting_for_start ) {
            handoff_failure_status =
                _( "Walking was interrupted before construction started.  No components were used." );
        }
    }
    activity_handoff = false;
    handoff_repaint_pending = false;
    ui_hidden = false;
    exit_requested = false;
    build_order.reset();
    category_menu.close();
    context_menu.close();
    transient_status = std::move( handoff_failure_status );
    handoff_failure_status.clear();
    if( construction_completed ) {
        // The catalog choice is intentionally sticky so the player can place
        // the same result repeatedly.  The committed tile is not: after its
        // terrain/furniture changes it usually no longer resolves that recipe,
        // and selected_target would continue to outrank mouse hover.  Releasing
        // only the target returns the selected result to cursor placement.
        selected_target.reset();
        hovered_target.reset();
        context_target.reset();
        context_anchor.reset();
        transient_status = selected_group.is_null() ?
                           _( "Construction finished.  Select another construction or tile." ) :
                           _( "Construction finished.  Move the ghost and click to build again." );
    }
    rebuild_palette();
    refresh_active_target();
    last_handoff_player_position.reset();
    last_handoff_progress_step = -1;
    last_handoff_walking = false;
    last_handoff_building = false;
    last_handoff_light_level = -1;
    last_handoff_weather = WEATHER_NULL;
    next_handoff_animation_frame = std::chrono::steady_clock::time_point();
    last_handoff_player_status.clear();
    handoff_target_abs.reset();
    handoff_camera_center_abs.reset();
    handoff_construction_id = construction_id( -1 );
    handoff_waiting_for_start = false;
#if defined(TILES)
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( true );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( true );
    }
#endif
    if( ui ) {
#if defined(TILES)
        ui->set_disable_uis_below( true );
#endif
        ui->mark_resize();
        ui->invalidate_ui();
    }
}

void construction_workspace::suspend_for_query()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return;
    }
    // A distraction warning owns a clean game frame.  Only rendering is
    // suspended; camera, selection, filters, scroll state and handoff survive.
    ui_hidden = true;
    viewport.cancel_map_capture();
#if defined(TILES)
    viewport.detach_map_preview();
    clear_ui_tile_previews();
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( false );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( false );
    }
#else
    overlay.reset();
#endif
    ui->set_disable_uis_below( false );
    ui->mark_resize();
    ui->invalidate_ui();
    g->invalidate_main_ui_adaptor();
    ui_manager::redraw_invalidated();
}

void construction_workspace::restore_after_query()
{
    if( !activity_handoff || !ui_hidden || !ui ) {
        return;
    }
    ui_hidden = false;
    // The popup overwrote the editor, so this is one of the few redraws that
    // must be allowed while the world handoff is still running.
    handoff_repaint_pending = true;
#if defined(TILES)
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( true );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( true );
    }
    ui->set_disable_uis_below( true );
#else
    if( !overlay ) {
        overlay = make_shared_fast<game::draw_callback_t>( [this]() {
            draw_world_overlay();
        } );
        g->add_draw_callback( overlay );
    }
#endif
    ui->mark_resize();
    ui->invalidate_ui();
    ui_manager::redraw_invalidated();
    g->invalidate_main_ui_adaptor();
}

bool construction_workspace::preserve_on_activity_cancel() const
{
    return activity_handoff;
}

void construction_workspace::set_activity_failure( std::string reason )
{
    // Several layers can observe the same failed auto-move.  Keep the first,
    // most specific explanation instead of replacing it with a later generic
    // "movement failed" fallback.
    if( activity_handoff && handoff_failure_status.empty() ) {
        handoff_failure_status = std::move( reason );
    }
}

void construction_workspace::mark_construction_started()
{
    handoff_waiting_for_start = false;
}

void construction_workspace::redraw_handoff_if_needed()
{
    if( !activity_handoff || ui_hidden || !ui ||
        ( !handoff_repaint_pending && !handoff_visual_changed() ) ) {
        return;
    }
    ui->invalidate_ui();
#if !defined(TILES)
    g->invalidate_main_ui_adaptor();
#endif
    ui_manager::redraw_invalidated();
}

bool construction_workspace::poll_activity_input()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return false;
    }

    // Map shifts can happen between input polls while auto-walk owns the turn
    // loop.  Keep the UI selection and auxiliary camera tied to their absolute
    // world positions before interpreting any new input.
    audit_camera_state( "activity-input" );
    synchronize_handoff_coordinates();

    // This poll runs while auto-walk or ACT_BUILD owns the turn loop.  Do not route it
    // through input_context::handle_input(): that path also updates the global
    // clipped-text hover helper and may synchronously redraw the UI for every
    // queued MOUSE_MOVE.  The performance trace showed those harmless mouse
    // moves taking hundreds of milliseconds and starving the click behind them.
    // Here we only need to distinguish passive pointer motion from an intentional
    // input that should pause work and return control to the editor.
    const int previous_timeout = inp_mngr.get_timeout();
    inp_mngr.set_timeout( 0 );
    const input_event raw_input = inp_mngr.get_input_event( keyboard_mode::keycode );
    inp_mngr.set_timeout( previous_timeout );

    if( raw_input.type == input_event_t::timeout || raw_input.type == input_event_t::error ) {
        return false;
    }

    const bool passive_mouse_move = raw_input.type == input_event_t::mouse &&
                                    raw_input.get_first_input() ==
                                    static_cast<int>( MouseInput::Move );
    const int mouse_input = raw_input.type == input_event_t::mouse ?
                            raw_input.get_first_input() : 0;
    const bool mouse_button_release = raw_input.type == input_event_t::mouse &&
                                      ( mouse_input == static_cast<int>( MouseInput::LeftButtonReleased ) ||
                                        mouse_input == static_cast<int>( MouseInput::RightButtonReleased ) ||
                                        mouse_input == static_cast<int>( MouseInput::MiddleButtonReleased ) ||
                                        mouse_input == static_cast<int>( MouseInput::X1ButtonReleased ) ||
                                        mouse_input == static_cast<int>( MouseInput::X2ButtonReleased ) );
    if( passive_mouse_move ) {
        return false;
    }
    if( mouse_button_release ) {
        if( mouse_input == static_cast<int>( MouseInput::LeftButtonReleased ) ) {
            suppress_next_select_release = false;
        } else if( mouse_input == static_cast<int>( MouseInput::RightButtonReleased ) ) {
            suppress_next_secondary_release = false;
        }
        return false;
    }

    // Continue is selected while the handoff is already running.  Clicking it
    // should not accidentally enter the generic click-to-pause path; Pause and
    // deliberate input everywhere else still stop the handoff immediately.
    if( raw_input.type == input_event_t::mouse &&
        raw_input.get_first_input() == static_cast<int>( MouseInput::LeftButtonPressed ) ) {
        const std::optional<point> inspector_pos = input_event_window_position(
                    raw_input, inspector_window );
        if( inspector_pos ) {
            const std::optional<int> hit = primary_action.hit_test( *inspector_pos );
            const ui_action_entry *entry = hit ? primary_action.entry( *hit ) : nullptr;
            if( entry != nullptr && entry->id == "APPLY" && entry->selected ) {
                transient_status = _( "Construction is already in progress.  Choose Pause to stop work." );
                ui->invalidate_ui();
                return true;
            }
        }
    }

    // A pointer press pauses immediately, before SDL delivers its matching
    // release.  The editor is reopened synchronously below, so remember which
    // release belongs to this pause and consume it there.  Otherwise that same
    // physical click can become a fresh SELECT and place a second ghost.
    if( raw_input.type == input_event_t::mouse ) {
        suppress_next_select_release =
            mouse_input == static_cast<int>( MouseInput::LeftButtonPressed );
        suppress_next_secondary_release =
            mouse_input == static_cast<int>( MouseInput::RightButtonPressed );
    }

    DebugLog( D_INFO, D_GAME )
            << "[CONSTRUCTION_HANDOFF_PAUSE] input_type=" << static_cast<int>( raw_input.type )
            << " input_code=" << raw_input.get_first_input()
            << " mouse_pos=(" << raw_input.mouse_pos.x << "," << raw_input.mouse_pos.y << ")"
            << " target_abs=" << ( handoff_target_abs ?
                                      handoff_target_abs->to_string_writable() : "none" )
            << " player_abs=" << you.pos_abs().to_string_writable()
            << " walking=" << you.has_destination()
            << " activity=" << ( you.activity ? you.activity.id().str() : "none" );

    if( you.has_destination() || you.has_destination_activity() ) {
        you.clear_destination();
    }
    if( you.activity ) {
        you.cancel_activity();
    }

    // If cancellation handed control to some other activity, do not open a modal
    // editor on top of it; the normal activity lifecycle will resolve that case.
    if( you.activity ) {
        return true;
    }

    g->wait_popup_reset();
    resume_activity_handoff();
    const bool unfinished = selected_target && here.partial_con_at( *selected_target ) != nullptr;
    transient_status = unfinished ?
                       _( "Construction paused.  Move the ghost to another tile or continue the "
                          "unfinished work." ) :
                       _( "Walking paused before construction started.  No components were used." );
    if( ui ) {
        ui->invalidate_ui();
    }
    return true;
}

bool construction_workspace::target_is_adjacent( const tripoint_bub_ms &target ) const
{
    return target.z() == you.pos_bub().z() && target != you.pos_bub() &&
           square_dist( target.raw(), you.pos_bub().raw() ) <= 1;
}

std::optional<tripoint_bub_ms> construction_workspace::displayed_target() const
{
    return selected_target ? selected_target : hovered_target;
}

const construction *construction_workspace::resolved_construction() const
{
    return resolution.id.is_valid() ? &resolution.id.obj() : nullptr;
}

bool construction_workspace::palette_accepts( const construction &con ) const
{
    if( !con.on_display ) {
        return false;
    }
    switch( operation ) {
        case construction_operation::build:
            return construction_is_catalog_action( con );
        case construction_operation::place:
            return construction_is_place_action( con );
        case construction_operation::markers:
            return construction_is_marker_action( con );
        case construction_operation::remove:
            return false;
    }
    return false;
}

const read_only_visitable &construction_workspace::active_inventory() const
{
    // Place is selected from carried items, but tool/skill readiness can still
    // use the normal crafting reach.  The resolver separately enforces that a
    // concrete source item is carried.
    return you.crafting_inventory();
}

construction_target_resolution construction_workspace::resolve_active_target(
    const tripoint_bub_ms &target ) const
{
    switch( operation ) {
        case construction_operation::build:
            return resolve_construction_target( you, active_inventory(), selected_group, target );
        case construction_operation::place:
            return resolve_place_target( you, active_inventory(), selected_group, target );
        case construction_operation::markers:
            return resolve_marker_target( you, active_inventory(), selected_group, target );
        case construction_operation::remove:
            return resolve_remove_target( you, active_inventory(), target );
    }
    return construction_target_resolution();
}

const construction *construction_workspace::catalog_preview_construction(
    const construction_group_str_id &group ) const
{
    const std::vector<construction *> variants = constructions_by_group( group );
    const auto first = std::find_if( variants.begin(), variants.end(),
    [this]( const construction * candidate ) {
        return candidate != nullptr && palette_accepts( *candidate );
    } );
    if( first == variants.end() ) {
        return nullptr;
    }

    if( operation != construction_operation::build || ( *first )->post_terrain.empty() ) {
        return *first;
    }

    // Follow actual catalog stages to the completed result, but never cross
    // into contextual or placement definitions that happen to share a group.
    const construction *result = *first;
    std::set<construction_id> visited;
    while( visited.insert( result->id ).second ) {
        const auto next = std::find_if( variants.begin(), variants.end(),
        [this, result, &visited]( const construction * candidate ) {
            return candidate != nullptr && palette_accepts( *candidate ) &&
                   visited.count( candidate->id ) == 0 &&
                   candidate->pre_terrain.count( result->post_terrain ) != 0;
        } );
        if( next == variants.end() ) {
            break;
        }
        result = *next;
    }
    return result;
}

const construction_plan *construction_workspace::plan_at(
    const tripoint_abs_ms &position ) const
{
    const auto found = std::find_if( nearby_plans.begin(), nearby_plans.end(),
    [&position]( const construction_plan & plan ) {
        return plan.position == position;
    } );
    return found == nearby_plans.end() ? nullptr : &*found;
}

const construction_plan *construction_workspace::selected_plan() const
{
    return selected_plan_abs ? plan_at( *selected_plan_abs ) : nullptr;
}

void construction_workspace::refresh_nearby_plans()
{
    nearby_plans = get_nearby_construction_plans( you, MAX_VIEW_DISTANCE );
    if( selected_plan_abs && plan_at( *selected_plan_abs ) == nullptr ) {
        selected_plan_abs.reset();
    }
}

void construction_workspace::select_plan( const tripoint_abs_ms &position,
        const bool center_view )
{
    const construction_plan *plan = plan_at( position );
    if( plan == nullptr ) {
        selected_plan_abs.reset();
        return;
    }
    selected_plan_abs = position;
    selected_target = here.get_bub( position );
    hovered_target.reset();
    if( center_view ) {
        viewport.center_map_on( you, *selected_target );
        audit_camera_state( "plan-selection", true );
    }
}

void construction_workspace::rebuild_plan_palette()
{
    refresh_nearby_plans();
    visible_plan_positions.clear();
    std::vector<ui_action_entry> entries;
    for( const construction_plan &plan : nearby_plans ) {
        const std::string status = construction_plan_status_name( plan.status );
        if( !plans_search.empty() && !lcmatch( plan.name, plans_search ) &&
            !lcmatch( status, plans_search ) ) {
            continue;
        }
        const std::pair<std::string, nc_color> marker = construction_plan_marker( plan.status );
        ui_action_entry entry( marker.first + "  " + plan.name,
                               construction_plan_entry_id( plan.position ), true,
                               selected_plan_abs && *selected_plan_abs == plan.position );
        if( plan.status == construction_plan_status::ready ||
            plan.status == construction_plan_status::in_progress ) {
            entry.tone = ui_action_tone::positive;
        }
        entries.push_back( std::move( entry ) );
        visible_plan_positions.push_back( plan.position );
    }
    palette.set_entries( std::move( entries ), false );
    palette.set_row_accessories( {} );
    if( selected_plan_abs ) {
        const auto selected = std::find( visible_plan_positions.begin(),
                                        visible_plan_positions.end(), *selected_plan_abs );
        if( selected != visible_plan_positions.end() ) {
            palette.select_only( static_cast<int>( selected - visible_plan_positions.begin() ) );
        } else {
            palette.clear_selection();
        }
    } else {
        palette.clear_selection();
    }
    rebuild_plans_inspector();
}

void construction_workspace::rebuild_plans_inspector()
{
    inspector_lines.clear();
    const int wrap_width = std::max( 8, inspector_width - 4 );
    const auto add = [&]( const std::string & line ) {
        const std::vector<std::string> folded = foldstring( line, wrap_width );
        inspector_lines.insert( inspector_lines.end(), folded.begin(), folded.end() );
    };
    const auto blank = [&]() {
        inspector_lines.emplace_back();
    };

    const construction_plan *chosen = selected_plan();
    add( colorize( chosen == nullptr ? _( "Nearby plans" ) : chosen->name, c_light_green ) );
    if( chosen != nullptr ) {
        blank();
        add( colorize( _( "Status" ), c_light_gray ) );
        add( construction_plan_status_name( chosen->status ) + "  •  " + chosen->reason );
        const tripoint_bub_ms target = here.get_bub( chosen->position );
        const int distance = square_dist( target.raw(), you.pos_bub().raw() );
        add( string_format( n_gettext( "%d tile away", "%d tiles away", distance ), distance ) );
        if( chosen->desired.is_valid() ) {
            const construction &con = chosen->desired.obj();
            const std::string description = construction_result_description( con );
            if( !description.empty() ) {
                blank();
                add( colorize( _( "About" ), c_light_gray ) );
                add( description );
            }
            blank();
            const std::vector<std::string> time = con.get_folded_time_string( wrap_width );
            inspector_lines.insert( inspector_lines.end(), time.begin(), time.end() );
        }
        blank();
        add( _( "Select Remove plan to clear only this tile.  Rectangular legacy "
                "blueprints are split so their other tiles remain." ) );
    } else {
        std::map<construction_plan_status, int> status_counts;
        std::map<std::string, int> group_counts;
        for( const construction_plan &plan : nearby_plans ) {
            ++status_counts[plan.status];
            ++group_counts[plan.name];
        }
        blank();
        add( string_format( n_gettext( "%d nearby plan", "%d nearby plans", nearby_plans.size() ),
                            nearby_plans.size() ) );
        for( const construction_plan_status status : {
                 construction_plan_status::ready,
                 construction_plan_status::missing_requirements,
                 construction_plan_status::unreachable,
                 construction_plan_status::invalidated,
                 construction_plan_status::in_progress,
                 construction_plan_status::completed
             } ) {
            const auto count = status_counts.find( status );
            if( count != status_counts.end() ) {
                add( string_format( "%s  %d", construction_plan_status_name( status ),
                                    count->second ) );
            }
        }
        if( !group_counts.empty() ) {
            blank();
            add( colorize( _( "By construction" ), c_light_gray ) );
            for( const auto &entry : group_counts ) {
                add( string_format( "%s  %d", entry.first, entry.second ) );
            }
        }
        blank();
        add( _( "Select a plan to center it on the map, or execute all nearby plans "
                "through the normal multi-construction activity." ) );
    }
    inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
    inspector.model().scroll_to_start();
}

std::string construction_workspace::category_label() const
{
    return section_filter ? catalog_section_label( *section_filter ) : _( "All" );
}

void construction_workspace::rebuild_palette()
{
    const construction_group_str_id previous = selected_group;
    visible_groups.clear();
    if( mode == construction_workspace_mode::plans ) {
        rebuild_plan_palette();
        return;
    }
    if( operation == construction_operation::remove ) {
        palette.set_entries( {}, false );
        palette.set_row_accessories( {} );
        return;
    }

    if( section_filter ) {
        const bool section_has_entries = std::any_of( get_constructions().begin(),
        get_constructions().end(), [this]( const construction &con ) {
            return palette_accepts( con ) && con.ui_section == *section_filter;
        } );
        if( !section_has_entries ) {
            section_filter.reset();
        }
    }

    std::set<construction_group_str_id> seen;
    std::map<construction_group_str_id, bool> currently_available;
    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );
    for( const construction &con : get_constructions() ) {
        if( !palette_accepts( con ) || !seen.insert( con.group ).second ) {
            continue;
        }

        const std::vector<construction *> variants = constructions_by_group( con.group );
        bool has_carried_source = operation != construction_operation::place || free_test_mode;
        bool available = free_test_mode;
        for( const construction *candidate : variants ) {
            if( candidate == nullptr || !palette_accepts( *candidate ) ) {
                continue;
            }
            if( operation == construction_operation::place &&
                construction_has_place_source( *candidate, you ) ) {
                has_carried_source = true;
            }
            if( player_can_build( you, active_inventory(), *candidate, true ) ) {
                available = true;
            }
        }
        if( operation == construction_operation::place && !has_carried_source ) {
            continue;
        }
        currently_available[con.group] = available;
        if( operation == construction_operation::build && !show_unavailable && !available ) {
            continue;
        }

        const construction *representative = catalog_preview_construction( con.group );
        if( representative == nullptr ) {
            continue;
        }
        const bool section_matches = !section_filter ||
                                     representative->ui_section == *section_filter;
        const std::string result_name = representative->post_terrain.empty() ?
                                        representative->group->name() :
                                        construction_result_name( *representative );
        const std::string section_name = catalog_section_label( representative->ui_section );
        const bool search_matches = search.empty() || lcmatch( con.group->name(), search ) ||
                                    lcmatch( result_name, search ) || lcmatch( section_name, search );
        if( section_matches && search_matches ) {
            visible_groups.push_back( con.group );
        }
    }

    std::sort( visible_groups.begin(), visible_groups.end(), [this](
    const construction_group_str_id &lhs, const construction_group_str_id &rhs ) {
        const construction *left = catalog_preview_construction( lhs );
        const construction *right = catalog_preview_construction( rhs );
        if( left != nullptr && right != nullptr && left->ui_section != right->ui_section ) {
            return static_cast<int>( left->ui_section ) < static_cast<int>( right->ui_section );
        }
        const std::string left_name = left != nullptr && !left->post_terrain.empty() ?
                                      construction_result_name( *left ) : lhs->name();
        const std::string right_name = right != nullptr && !right->post_terrain.empty() ?
                                       construction_result_name( *right ) : rhs->name();
        return left_name < right_name;
    } );

    std::vector<ui_action_entry> entries;
    std::vector<std::vector<ui_row_accessory>> row_accessories;
    entries.reserve( visible_groups.size() );
    row_accessories.reserve( visible_groups.size() );
    for( const construction_group_str_id &group : visible_groups ) {
        const construction *representative = catalog_preview_construction( group );
        std::string label = group->name();
        if( representative != nullptr ) {
            if( operation == construction_operation::markers && !representative->ui_name.empty() ) {
                label = representative->ui_name.translated();
            } else if( !representative->post_terrain.empty() ) {
                label = construction_result_name( *representative );
            }
        }
        ui_action_entry entry( label, group.str(), true, group == selected_group );
        if( currently_available[group] ) {
            entry.tone = ui_action_tone::positive;
        }
        entries.push_back( std::move( entry ) );
        row_accessories.push_back( { ui_row_accessory{
                ui_action_entry( "    ", "PREVIEW_" + group.str() ),
                ui_row_accessory_side::leading, false, 4 } } );
    }
    palette.set_entries( std::move( entries ), false );
    palette.set_row_accessories( std::move( row_accessories ) );
    const auto selected = std::find( visible_groups.begin(), visible_groups.end(), selected_group );
    if( selected != visible_groups.end() ) {
        palette.select_only( static_cast<int>( selected - visible_groups.begin() ) );
    } else {
        const auto remembered = operation == construction_operation::build ?
                                std::find( visible_groups.begin(), visible_groups.end(),
                                           uistate.last_construction ) : visible_groups.end();
        if( !selection_cleared_by_user && remembered != visible_groups.end() ) {
            selected_group = *remembered;
            palette.select_only( static_cast<int>( remembered - visible_groups.begin() ) );
        } else {
            selected_group = construction_group_str_id::NULL_ID();
            palette.clear_selection();
        }
    }
    if( selected_group != previous ) {
        refresh_active_target();
        inspector.model().scroll_to_start();
    }
}

void construction_workspace::refresh_active_target()
{
    if( mode == construction_workspace_mode::plans ) {
        rebuild_plans_inspector();
        return;
    }
    const std::optional<tripoint_bub_ms> target = displayed_target();
    context_actions.clear();
    if( target && mode == construction_workspace_mode::build && selected_group.is_null() ) {
        context_actions = resolve_context_construction_actions(
                              you, you.crafting_inventory(), *target );
    }

    const bool catalog_selection_missing =
        ( operation == construction_operation::place ||
          operation == construction_operation::markers ) && selected_group.is_null();
    if( !target || catalog_selection_missing ) {
        resolution = construction_target_resolution();
    } else {
        resolution = resolve_active_target( *target );
    }

    adjacent_resolutions.clear();
    if( ( operation == construction_operation::place ||
          operation == construction_operation::markers ) && !selected_group.is_null() ) {
        for( int x = -1; x <= 1; ++x ) {
            for( int y = -1; y <= 1; ++y ) {
                if( x == 0 && y == 0 ) {
                    continue;
                }
                const tripoint_bub_ms candidate = you.pos_bub() + tripoint_rel_ms( x, y, 0 );
                adjacent_resolutions.emplace_back( candidate, resolve_active_target( candidate ) );
            }
        }
    }
    rebuild_inspector();
}

void construction_workspace::clear_selection()
{
    selection_cleared_by_user = true;
    selected_group = construction_group_str_id::NULL_ID();
    selected_target.reset();
    selected_plan_abs.reset();
    hovered_target.reset();
    context_target.reset();
    context_anchor.reset();
    context_actions.clear();
    adjacent_resolutions.clear();
    resolution = construction_target_resolution();
    transient_status.clear();
    palette.clear_selection();
    rebuild_inspector();
}

void construction_workspace::rebuild_inspector()
{
    if( mode == construction_workspace_mode::plans ) {
        rebuild_plans_inspector();
        return;
    }
    inspector_lines.clear();
    const int wrap_width = std::max( 8, inspector_width - 4 );
    const auto add = [&]( const std::string & line ) {
        const std::vector<std::string> folded = foldstring( line, wrap_width );
        inspector_lines.insert( inspector_lines.end(), folded.begin(), folded.end() );
    };
    const auto blank = [&]() {
        inspector_lines.emplace_back();
    };

    const bool inspect_mode = mode == construction_workspace_mode::build &&
                              selected_group.is_null();
    const bool selection_missing = operation != construction_operation::remove && selected_group.is_null();
    std::string heading = _( "Remove" );
    if( operation == construction_operation::build ) {
        if( mode == construction_workspace_mode::plan ) {
            heading = selection_missing ? _( "Plan construction" ) :
                      string_format( _( "Plan: %s" ), selected_group->name() );
        } else {
            heading = inspect_mode ? _( "Inspect & work" ) : selected_group->name();
        }
    } else if( operation == construction_operation::place ) {
        heading = selection_missing ? _( "Place from inventory" ) : selected_group->name();
    } else if( operation == construction_operation::markers ) {
        heading = selection_missing ? _( "Markers" ) : selected_group->name();
    }
    add( colorize( heading, c_light_green ) );

    const construction *catalog_preview = selected_group.is_null() ? nullptr :
                                          catalog_preview_construction( selected_group );
    if( catalog_preview != nullptr ) {
        const std::string description = construction_result_description( *catalog_preview );
        if( !description.empty() ) {
            blank();
            add( colorize( _( "About" ), c_light_gray ) );
            add( description );
        }
    }

    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        blank();
        add( colorize( _( "Target" ), c_light_gray ) );
        add( operation == construction_operation::remove ?
             _( "Select a world tile to inspect its removal action." ) :
             inspect_mode ?
             _( "Select a tile to inspect contextual work such as repairs, or choose a build result from the catalog." ) :
             selection_missing && operation == construction_operation::place ?
             _( "Choose one of the placeable items currently carried." ) :
             selection_missing && operation == construction_operation::markers ?
             _( "Choose a marker, then select a world tile." ) :
             _( "Hover or select a world tile." ) );
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
    }

    blank();
    add( colorize( _( "Target" ), c_light_gray ) );
    const std::string existing = here.has_furn( *target ) ? here.furn( *target )->name() :
                                 here.ter( *target )->name();
    const int distance = square_dist( target->raw(), you.pos_bub().raw() );
    const std::string direction = direction_name( direction_from( you.pos_bub(), *target ) );
    std::string target_description = distance == 1 ?
                                     string_format( _( "%s  •  Adjacent %s" ), existing, direction ) :
                                     string_format( n_gettext( "%s  •  %d tile %s",
                                         "%s  •  %d tiles %s", distance ),
                                         existing, distance, direction );
    if( debug_mode ) {
        target_description += string_format( "  (%d, %d, %d)", target->x(), target->y(), target->z() );
    }
    add( target_description );
    if( get_option<bool>( "UI_TEST_MODE" ) ) {
        add( colorize( _( "UI test mode: skills, tools and components are free." ), c_light_blue ) );
    }

    if( operation == construction_operation::build && !context_actions.empty() ) {
        blank();
        add( colorize( _( "Tile actions" ), c_light_gray ) );
        for( const construction_context_action &action : context_actions ) {
            const nc_color action_color = action.resolution.ready() ? c_light_green : c_yellow;
            std::string summary = contextual_action_label( action );
            if( action.resolution.id.is_valid() ) {
                summary += "  •  " + to_string( time_duration::from_moves(
                                                   action.resolution.id.obj().adjusted_time() ) );
            }
            if( action.resolution.alternative_ids.size() > 1 ) {
                summary += string_format( n_gettext( "  •  %d method", "  •  %d methods",
                                                       action.resolution.alternative_ids.size() ),
                                          action.resolution.alternative_ids.size() );
            }
            summary += "  •  " + action.resolution.reason;
            add( colorize( summary, action_color ) );
        }
    }
    if( inspect_mode && !resolution.unfinished ) {
        if( context_actions.empty() ) {
            blank();
            add( colorize( _( "No construction work is available for this tile." ), c_dark_gray ) );
        }
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
    }
    if( selection_missing && !resolution.unfinished ) {
        blank();
        add( colorize( mode == construction_workspace_mode::plan ?
                       _( "Choose a construction from the left." ) :
                       operation == construction_operation::place ?
                       _( "Choose a carried item from the left." ) :
                       _( "Choose a marker from the left." ), c_dark_gray ) );
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
    }

    nc_color status_color = c_light_red;
    if( resolution.unfinished && resolution.ready() ) {
        status_color = c_light_blue;
    } else if( resolution.ready() ) {
        status_color = c_light_green;
    } else if( resolution.status == construction_target_status::unavailable_requirements ) {
        status_color = c_yellow;
    }
    blank();
    add( colorize( _( "Status" ), c_light_gray ) );
    add( colorize( resolution.reason, status_color ) );
    if( mode == construction_workspace_mode::plan &&
        resolution.status == construction_target_status::unavailable_requirements ) {
        add( colorize( _( "This tile can still be planned.  Requirements are checked "
                         "again when plans execute." ),
                       c_light_blue ) );
    }

    const construction *con = resolved_construction();
    if( con == nullptr ) {
        inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
        inspector.model().scroll_to_start();
        return;
    }

    blank();
    add( colorize( operation == construction_operation::remove ? _( "Action" ) :
                   operation == construction_operation::place ? _( "Place" ) :
                   operation == construction_operation::markers ? _( "Marker" ) : _( "Result" ),
                   c_light_gray ) );
    add( operation == construction_operation::remove ? con->group->name() :
         construction_result_name( *con ) );
    if( resolution.alternative_ids.size() > 1 ) {
        add( string_format( n_gettext( "%d alternative requirement path",
                                       "%d alternative requirement paths",
                                       resolution.alternative_ids.size() - 1 ),
                            resolution.alternative_ids.size() - 1 ) );
    }
    const std::string description = construction_result_description( *con );
    if( !description.empty() && con != catalog_preview ) {
        add( description );
    }

    blank();
    const std::vector<std::string> time = con->get_folded_time_string( wrap_width );
    inspector_lines.insert( inspector_lines.end(), time.begin(), time.end() );

    blank();
    add( colorize( _( "Skills" ), c_light_gray ) );
    if( con->required_skills.empty() ) {
        add( _( "None" ) );
    } else {
        for( const std::pair<const skill_id, int> &skill : con->required_skills ) {
            const int have = you.get_knowledge_level( skill.first );
            const nc_color color = have >= skill.second ? c_light_green : c_light_red;
            add( colorize( string_format( "%s  %d / %d", skill.first->name(), have, skill.second ), color ) );
        }
    }

    con->requirements->can_make_with_inventory( active_inventory(), is_crafting_component, 1,
            craft_flags::none, false );
    blank();
    const std::vector<std::string> tools = con->requirements->get_folded_tools_list(
            wrap_width, c_light_gray, active_inventory() );
    inspector_lines.insert( inspector_lines.end(), tools.begin(), tools.end() );
    blank();
    const std::vector<std::string> components = con->requirements->get_folded_components_list(
            wrap_width, c_light_gray, operation == construction_operation::place ?
            static_cast<const read_only_visitable &>( you ) : active_inventory(), is_crafting_component );
    inspector_lines.insert( inspector_lines.end(), components.begin(), components.end() );
    inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
}

void construction_workspace::create_layout( ui_adaptor &ui )
{
    const int width = TERMX;
    const int height = TERMY;
    content_bottom = std::max( content_top, height - 4 );
    compact = width < 104;
    palette_visible = operation != construction_operation::remove &&
                      ( !compact || focus == workspace_focus::palette );
    inspector_visible = !compact || focus == workspace_focus::inspector;

    palette_width = palette_visible ? std::min( compact ? 34 : 38,
        std::max( 24, width / 4 ) ) : 0;
    inspector_width = inspector_visible ? std::min( compact ? 40 : 46,
        std::max( 28, width / 4 ) ) : 0;
    const int content_height = std::max( 1, content_bottom - content_top + 1 );

    header = catacurses::newwin( content_top, width, point::zero );
    footer = catacurses::newwin( 3, width, point( 0, std::max( 0, height - 3 ) ) );
    palette_window = palette_visible ? catacurses::newwin( content_height, palette_width,
        point( 0, content_top ) ) : catacurses::window();
    inspector_window = inspector_visible ? catacurses::newwin( content_height, inspector_width,
        point( std::max( 0, width - inspector_width ), content_top ) ) : catacurses::window();

    const int viewport_left = palette_width;
    const int viewport_right = std::max( viewport_left, width - inspector_width - 1 );
    viewport.configure( inclusive_rectangle<point>( point( viewport_left, content_top ),
            point( viewport_right, content_bottom ) ) );
#if defined(TILES)
    const int viewport_width = std::max( 1, viewport_right - viewport_left + 1 );
    viewport_window = catacurses::newwin( content_height, viewport_width,
                                         point( viewport_left, content_top ) );
    viewport.attach_map_preview( viewport_window );
#endif
    audit_camera_state( "layout" );
    ui.position_from_window( catacurses::stdscr );
    rebuild_inspector();
}

void construction_workspace::draw_header()
{
    werase( header );
    draw_border( header, c_light_gray );
    trim_and_print( header, point( 2, 1 ), 14, c_light_green, _( "Construction" ) );

    std::vector<ui_action_strip_item> actions = {
        { ui_action_entry( _( "Build" ), "MODE_BUILD", true,
                           mode == construction_workspace_mode::build ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Place" ), "MODE_PLACE", true,
                           mode == construction_workspace_mode::place ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Remove" ), "MODE_REMOVE", true,
                           mode == construction_workspace_mode::remove ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Markers" ), "MODE_MARKERS", true,
                           mode == construction_workspace_mode::markers ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Plan" ), "MODE_PLAN", true,
                           mode == construction_workspace_mode::plan ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Plans" ), "MODE_PLANS", true,
                           mode == construction_workspace_mode::plans ), 0,
          ui_action_alignment::left }
    };
    if( compact && operation != construction_operation::remove ) {
        actions.push_back( { ui_action_entry( _( "Palette" ), "FOCUS_PALETTE", true,
                                              focus == workspace_focus::palette ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Map" ), "FOCUS_VIEWPORT", true,
                                              focus == workspace_focus::viewport ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Inspector" ), "FOCUS_INSPECTOR", true,
                                              focus == workspace_focus::inspector ), 1,
                             ui_action_alignment::left } );
    }
    actions.push_back( { ui_action_entry( _( "Back" ), "BACK" ), 2,
                         ui_action_alignment::right } );
    header_actions.configure( header, point( 17, 1 ), std::move( actions ),
                              std::max( 1, getmaxx( header ) - 19 ), 1 );
    header_actions.draw( header );
    trim_and_print( header, point( 2, 2 ), std::max( 1, getmaxx( header ) - 4 ),
                    c_light_gray, player_status_line() );
    wnoutrefresh( header );
}

void construction_workspace::draw_palette()
{
    if( !palette_window ) {
        palette.invalidate_geometry();
#if defined(TILES)
        clear_ui_tile_previews();
#endif
        return;
    }
    werase( palette_window );
    draw_border( palette_window, focus == workspace_focus::palette ? c_light_cyan : c_light_gray );

    std::string title = _( " Build catalog " );
    if( mode == construction_workspace_mode::plans ) {
        title = _( " Plans " );
    } else if( mode == construction_workspace_mode::plan ) {
        title = _( " Plan catalog " );
    } else if( operation == construction_operation::place ) {
        title = _( " Place from inventory " );
    } else if( operation == construction_operation::markers ) {
        title = _( " Markers " );
    } else if( operation == construction_operation::remove ) {
        title = _( " Remove tool " );
    }
    trim_and_print( palette_window, point( 2, 0 ), std::max( 1, palette_width - 4 ),
                    c_light_green, title );

    if( mode == construction_workspace_mode::plans ) {
        search_field.configure( palette_window, point( 2, 2 ), palette_width - 4,
                                _( "Search: " ), plans_search, _( "plan or status" ), true );
        search_field.draw( palette_window );
        palette_actions.clear();
        const int list_y = 4;
        palette.draw( palette_window, point( 2, list_y ), palette_width - 4,
                      std::max( 1, getmaxy( palette_window ) - list_y - 2 ),
                      ui_selection_list_style(), 2 );
        if( visible_plan_positions.empty() ) {
            trim_and_print( palette_window, point( 2, list_y ), palette_width - 4,
                            c_dark_gray, nearby_plans.empty() ? _( "No nearby plans." ) :
                            _( "No plans match." ) );
        }
        for( int index = 0; index < static_cast<int>( visible_plan_positions.size() ); ++index ) {
            const std::optional<point> row = palette.entry_position( index );
            const construction_plan *plan = plan_at( visible_plan_positions[index] );
            if( !row || plan == nullptr ) {
                continue;
            }
            const int distance = square_dist( here.get_bub( plan->position ).raw(),
                                              you.pos_bub().raw() );
            const std::string detail = string_format(
                                           n_gettext( "%s  •  %d tile", "%s  •  %d tiles",
                                                   distance ),
                                           construction_plan_status_name( plan->status ),
                                           distance );
            const bool selected = selected_plan_abs && *selected_plan_abs == plan->position;
            trim_and_print( palette_window, *row + point( 1, 1 ),
                            std::max( 1, palette_width - row->x - 5 ),
                            selected ? h_dark_gray : c_dark_gray, detail );
        }
#if defined(TILES)
        clear_ui_tile_previews();
#endif
        wnoutrefresh( palette_window );
        return;
    }

    if( operation == construction_operation::remove ) {
        search_field.clear();
        palette_actions.clear();
        palette.invalidate_geometry();
#if defined(TILES)
        clear_ui_tile_previews();
#endif
        trim_and_print( palette_window, point( 2, 2 ), palette_width - 4, c_light_green,
                        _( "Select a tile on the map." ) );
        fold_and_print( palette_window, point( 2, 4 ), palette_width - 4, c_light_gray,
                        _( "Remove resolves the correct dismantle or removal action from the selected terrain or furniture." ) );
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            const std::string existing = here.has_furn( *target ) ? here.furn( *target )->name() :
                                         here.ter( *target )->name();
            trim_and_print( palette_window, point( 2, 8 ), palette_width - 4, c_light_cyan,
                            string_format( _( "Target: %s" ), existing ) );
        }
        wnoutrefresh( palette_window );
        return;
    }

    const std::string hint = operation == construction_operation::place ?
                             _( "carried item" ) : operation == construction_operation::markers ?
                             _( "marker" ) : _( "name or result" );
    search_field.configure( palette_window, point( 2, 2 ), palette_width - 4,
                            _( "Search: " ), search, hint, true );
    search_field.draw( palette_window );

    std::vector<ui_action_entry> palette_entries = {
        ui_action_entry( string_format( _( "Section: %s" ), category_label() ),
                         "CATEGORY", true, category_menu.is_open(), std::string(), std::nullopt, true )
    };
    if( operation == construction_operation::build ) {
        palette_entries.emplace_back( _( "Show unavailable" ), "SHOW_UNAVAILABLE", true, false,
                                      std::string(), show_unavailable );
    }
    palette_actions.configure( palette_window, point( 2, 4 ), std::move( palette_entries ),
                               palette_width - 4, 2 );
    palette_actions.draw( palette_window );

    const int list_y = 7;
    palette.draw( palette_window, point( 2, list_y ), palette_width - 4,
                  std::max( 1, getmaxy( palette_window ) - list_y - 2 ),
                  ui_selection_list_style(), 2 );
    if( visible_groups.empty() ) {
        const std::string empty = operation == construction_operation::place &&
                                  !get_option<bool>( "UI_TEST_MODE" ) ?
                                  _( "No carried items can be placed." ) : _( "No entries match." );
        trim_and_print( palette_window, point( 2, list_y ), palette_width - 4, c_dark_gray, empty );
    }

#if defined(TILES)
    std::vector<ui_tile_preview> previews;
#endif
    for( int index = 0; index < static_cast<int>( visible_groups.size() ); ++index ) {
        const std::optional<point> row = palette.entry_position( index );
        if( !row ) {
            continue;
        }
        const construction *representative = catalog_preview_construction( visible_groups[index] );
        if( representative == nullptr ) {
            continue;
        }
        const bool selected = visible_groups[index] == selected_group;
        if( representative->post_terrain.empty() ) {
            mvwputch( palette_window, *row + point( 1, 0 ),
                      selected ? h_light_cyan : c_light_cyan, '*' );
        } else {
#if defined(TILES)
            const ui_tile_preview_type type = representative->post_is_furniture ?
                                              ui_tile_preview_type::furniture : ui_tile_preview_type::terrain;
            if( has_ui_tile_preview( type, representative->post_terrain ) ) {
                previews.push_back( ui_tile_preview{ *row, point( 4, 2 ), type,
                                                     representative->post_terrain, std::string(), 0 } );
            } else {
                trim_and_print( palette_window, *row, 4, c_light_red, _( "[?]" ) );
            }
#else
            if( representative->post_is_furniture ) {
                const furn_str_id result( representative->post_terrain );
                mvwputch( palette_window, *row + point( 1, 0 ),
                          selected ? hilite( result->color() ) : result->color(), result->symbol() );
            } else {
                const ter_str_id result( representative->post_terrain );
                mvwputch( palette_window, *row + point( 1, 0 ),
                          selected ? hilite( result->color() ) : result->color(), result->symbol() );
            }
#endif
        }

        std::string detail = catalog_section_label( representative->ui_section );
        detail += "  •  " + to_string( time_duration::from_moves( representative->adjusted_time() ) );
        if( !representative->required_skills.empty() ) {
            const auto skill = std::max_element( representative->required_skills.begin(),
            representative->required_skills.end(), []( const auto & lhs, const auto & rhs ) {
                return lhs.second < rhs.second;
            } );
            detail += string_format( "  •  %s %d", skill->first->name(), skill->second );
        }
        trim_and_print( palette_window, *row + point( 5, 1 ),
                        std::max( 1, palette_width - row->x - 8 ),
                        selected ? h_dark_gray : c_dark_gray, detail );
    }
#if defined(TILES)
    set_ui_tile_previews( palette_window, previews );
#endif
    wnoutrefresh( palette_window );
}

void construction_workspace::draw_inspector()
{
    if( !inspector_window ) {
        inspector.hide();
        return;
    }
    werase( inspector_window );
    draw_border( inspector_window, focus == workspace_focus::inspector ? c_light_cyan : c_light_gray );
    trim_and_print( inspector_window, point( 2, 0 ), std::max( 1, inspector_width - 4 ),
                    c_light_green, _( " Inspector " ) );

    if( mode == construction_workspace_mode::plans ) {
        const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
        inspector.configure( point( 2, 1 ), std::max( 2, inspector_width - 4 ),
                             std::max( 1, primary_action_y - 2 ),
                             static_cast<int>( inspector_lines.size() ) );
        for( int line = 0; line < static_cast<int>( inspector_lines.size() ); ++line ) {
            const std::optional<point> pos = inspector.position( line );
            if( pos ) {
                nc_color current = c_light_gray;
                print_colored_text( inspector_window, *pos, current, c_light_gray,
                                    inspector_lines[line] );
            }
        }
        inspector.draw_scrollbar( inspector_window );
        const bool has_executable = std::any_of( nearby_plans.begin(), nearby_plans.end(),
        []( const construction_plan & plan ) {
            return construction_plan_can_execute( plan.status );
        } );
        ui_action_entry execute( _( "Execute plans" ), "EXECUTE_PLANS", has_executable,
                                 false, nearby_plans.empty() ?
                                 _( "There are no nearby plans." ) :
                                 _( "No nearby plan can currently execute.  Select a plan "
                                    "to see what is blocking it." ) );
        execute.tone = ui_action_tone::positive;
        ui_action_entry remove( _( "Remove plan" ), "REMOVE_PLAN",
                                selected_plan() != nullptr, false,
                                _( "Select a plan first." ) );
        remove.tone = ui_action_tone::destructive;
        primary_action.configure( inspector_window, point( 2, primary_action_y ),
                                  { std::move( execute ), std::move( remove ) },
                                  inspector_width - 4, 1 );
        primary_action.draw( inspector_window );
        contextual_action_strip.clear();
        wnoutrefresh( inspector_window );
        return;
    }

    const bool inspect_mode = mode == construction_workspace_mode::build &&
                              selected_group.is_null();
    const bool selection_missing = operation != construction_operation::remove && selected_group.is_null();
    const bool show_context_actions = mode == construction_workspace_mode::build &&
                                      selected_target && !context_actions.empty();
    const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int contextual_action_y = show_context_actions ?
                                    std::max( 2, primary_action_y - ( inspect_mode ? 1 : 3 ) ) :
                                    primary_action_y;
    const int content_height = std::max( 1, contextual_action_y - 2 );
    inspector.configure( point( 2, 1 ), std::max( 2, inspector_width - 4 ), content_height,
                         static_cast<int>( inspector_lines.size() ) );
    for( int line = 0; line < static_cast<int>( inspector_lines.size() ); ++line ) {
        const std::optional<point> pos = inspector.position( line );
        if( pos ) {
            nc_color current = c_light_gray;
            print_colored_text( inspector_window, *pos, current, c_light_gray, inspector_lines[line] );
        }
    }
    inspector.draw_scrollbar( inspector_window );

    ui_action_entry build( _( "Select a target" ), "APPLY", false, false,
                           operation == construction_operation::remove ?
                           _( "Select a world tile first." ) :
                           operation == construction_operation::place ?
                           _( "Select a carried item and a world tile first." ) :
                           operation == construction_operation::markers ?
                           _( "Select a marker and a world tile first." ) :
                           mode == construction_workspace_mode::plan ?
                           _( "Select a construction and a world tile to plan." ) :
                           _( "Select a construction and a world tile first." ) );
    if( !inspect_mode || resolution.unfinished ) {
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            if( !selected_target ) {
                build.label = _( "Select this tile first" );
                build.disabled_reason = _( "Click the world tile to commit this target." );
            } else if( mode == construction_workspace_mode::plan ) {
                const construction_plan *existing = plan_at( here.get_abs( *target ) );
                const bool valid_plan = !resolution.unfinished &&
                                        resolution.has_construction() &&
                                        resolution.status !=
                                        construction_target_status::invalid_location;
                if( existing != nullptr && existing->group == selected_group ) {
                    build.label = _( "Already planned" );
                    build.disabled_reason =
                        _( "That construction is already planned on this tile." );
                } else {
                    build.label = existing == nullptr ? _( "Plan here" ) : _( "Replace plan" );
                    build.enabled = valid_plan;
                    build.disabled_reason = valid_plan ? std::string() : resolution.reason;
                }
            } else if( resolution.unfinished ) {
                const bool can_walk = operation == construction_operation::build ||
                                      operation == construction_operation::remove;
                build.label = target_is_adjacent( *target ) ? _( "Continue" ) :
                              can_walk ? _( "Walk there and continue" ) : _( "Continue" );
                build.enabled = resolution.ready() &&
                                ( target_is_adjacent( *target ) || can_walk );
                build.disabled_reason = resolution.ready() ?
                                        _( "Move adjacent to continue this construction." ) :
                                        resolution.reason;
            } else if( !target_is_adjacent( *target ) ) {
                build.label = operation == construction_operation::build ?
                              _( "Walk there and build" ) :
                              operation == construction_operation::remove ?
                              _( "Go there and remove" ) :
                              operation == construction_operation::place ? _( "Go there and place" ) :
                              operation == construction_operation::markers ? _( "Go there and mark" ) :
                              _( "Go there and build" );
                const bool can_walk = operation == construction_operation::build ||
                                      operation == construction_operation::remove;
                build.enabled = can_walk && resolution.ready();
                build.disabled_reason = can_walk ?
                                        resolution.reason :
                                        operation == construction_operation::place ?
                                        _( "Distant placement orders are not implemented yet." ) :
                                        operation == construction_operation::markers ?
                                        _( "Distant marker orders are not implemented yet." ) :
                                        _( "Distant build orders are planned for the next construction pass." );
            } else {
                if( operation == construction_operation::remove && resolved_construction() ) {
                    build.label = string_format( _( "Remove %s" ), resolved_construction()->group->name() );
                } else if( operation == construction_operation::place ) {
                    build.label = _( "Place here" );
                } else if( operation == construction_operation::markers ) {
                    build.label = _( "Mark here" );
                } else {
                    build.label = _( "Build here" );
                }
                build.enabled = resolution.ready();
                build.disabled_reason = resolution.reason;
            }
        }
    }
    const bool work_running = activity_handoff &&
                              ( you.has_destination() || you.has_destination_activity() ||
                                static_cast<bool>( you.activity ) );
    if( work_running ) {
        const construction *active = handoff_construction_id.is_valid() ?
                                     &handoff_construction_id.obj() : resolved_construction();
        const std::string task_name = active != nullptr ? active->group->name() :
                                      selected_group.is_valid() ? selected_group->name() :
                                      _( "construction" );
        if( you.has_destination() || you.has_destination_activity() ) {
            build.label = string_format( _( "Walking: %s" ), task_name );
        } else if( operation == construction_operation::remove ) {
            build.label = string_format( _( "Removing: %s" ), task_name );
        } else {
            build.label = string_format( _( "Building: %s" ), task_name );
        }
        build.enabled = true;
        build.selected = true;
        build.disabled_reason.clear();
    }
    if( show_context_actions ) {
        std::vector<ui_action_entry> entries;
        entries.reserve( context_actions.size() );
        const bool decorate_ready = std::any_of( context_actions.begin(), context_actions.end(),
        []( const construction_context_action & action ) {
            return action.intent == construction_ui_intent::decorate && action.resolution.ready();
        } );
        bool decorate_group_added = false;
        for( const construction_context_action &action : context_actions ) {
            if( action.intent == construction_ui_intent::decorate ) {
                if( !decorate_group_added ) {
                    const bool adjacent = selected_target && target_is_adjacent( *selected_target );
                    const bool enabled = decorate_ready && adjacent;
                    const std::string reason = !adjacent ? _( "Move adjacent to decorate this tile." ) :
                                               decorate_ready ? std::string() :
                                               _( "No decoration option currently meets its requirements." );
                    ui_action_entry decorate( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",
                                              enabled, false, reason );
                    decorate.tone = ui_action_tone::positive;
                    entries.push_back( std::move( decorate ) );
                    decorate_group_added = true;
                }
                continue;
            }
            bool enabled = action.resolution.ready();
            std::string reason = action.resolution.reason;
            if( selected_target && !target_is_adjacent( *selected_target ) ) {
                enabled = false;
                reason = _( "Move adjacent to use this tile action." );
            }
            ui_action_entry entry( contextual_action_label( action ),
                                   contextual_action_id( action ), enabled, false, reason );
            entry.tone = ui_action_tone::positive;
            entries.push_back( std::move( entry ) );
        }
        contextual_action_strip.configure( inspector_window, point( 2, contextual_action_y ),
                                           std::move( entries ), inspector_width - 4, 2 );
        contextual_action_strip.draw( inspector_window );
    } else {
        contextual_action_strip.clear();
    }

    if( ( inspect_mode || selection_missing ) && !resolution.unfinished ) {
        primary_action.clear();
    } else {
        build.tone = operation == construction_operation::remove ?
                     ui_action_tone::destructive : ui_action_tone::positive;
        ui_action_entry pause( _( "Pause" ), "PAUSE", work_running, false,
                               _( "Construction is already paused." ) );
        std::vector<ui_action_entry> actions = { build };
        if( work_running || resolution.unfinished ) {
            actions.push_back( std::move( pause ) );
        }
        primary_action.configure( inspector_window, point( 2, primary_action_y ), std::move( actions ),
                                  inspector_width - 4, 1 );
        primary_action.draw( inspector_window );
    }
    wnoutrefresh( inspector_window );
}

std::string construction_workspace::placement_prompt() const
{
    if( mode == construction_workspace_mode::plan ) {
        return _( "Move the planning ghost with the mouse and click the map to add a "
                  "persistent plan." );
    }
    if( mode == construction_workspace_mode::plans ) {
        return _( "Select a plan to inspect it, remove it, or execute nearby plans." );
    }
    switch( operation ) {
        case construction_operation::build:
            return _( "Move the construction ghost with the mouse and click the map to build." );
        case construction_operation::place:
            return _( "Move the item ghost with the mouse and click the map "
                      "to choose its location." );
        case construction_operation::markers:
            return _( "Move the marker with the mouse and click the map to choose its location." );
        case construction_operation::remove:
            return _( "Select a world tile to inspect its removal action." );
    }
    return std::string();
}

std::string construction_workspace::player_status_line() const
{
    const auto status = []( const std::string &label,
    std::pair<std::string, nc_color> value, const std::string &fallback ) {
        if( value.first.empty() ) {
            value.first = fallback;
        }
        return string_format( "%s %s", label, colorize( value.first, value.second ) );
    };

    std::vector<std::string> values;
    values.reserve( 5 );
    values.push_back( status( _( "Pain:" ), display::pain_text_color( you ), _( "No pain" ) ) );
    values.push_back( status( _( "Weariness:" ), display::weariness_text_color( you ), _( "Fresh" ) ) );
    values.push_back( status( _( "Hunger:" ), display::hunger_text_color( you ), _( "Satisfied" ) ) );
    values.push_back( status( _( "Thirst:" ), display::thirst_text_color( you ), _( "Not thirsty" ) ) );
    values.push_back( status( _( "Rest:" ), display::sleepiness_text_color( you ), _( "Rested" ) ) );
    std::string result;
    for( const std::string &value : values ) {
        if( !result.empty() ) {
            result += "  •  ";
        }
        result += value;
    }
    return result;
}

std::string construction_workspace::footer_status() const
{
    if( !transient_status.empty() ) {
        return transient_status;
    }
    if( activity_handoff ) {
        if( you.has_destination() || you.has_destination_activity() ) {
            return _( "Walking to the construction site… click or press a key to pause." );
        }
        if( you.activity ) {
            return operation == construction_operation::remove ?
                   _( "Removing… click or press a key to pause." ) :
                   _( "Building… click or press a key to pause." );
        }
    }
    if( mode == construction_workspace_mode::plans ) {
        return selected_plan() != nullptr ?
               _( "Selected plan highlighted  •  Execute plans starts normal automated "
                  "construction" ) :
               _( "Select a plan from the list or map  •  Execute plans starts nearby work" );
    }
    if( mode == construction_workspace_mode::plan && !selected_group.is_null() ) {
        return _( "LMB plan  •  RMB inspect/replace/remove  •  MMB drag/pan  •  Wheel zoom" );
    }
    if( !selected_group.is_null() && !selected_target ) {
        return placement_prompt();
    }
    return _( "LMB select  •  MMB drag/pan  •  Wheel zoom  •  RMB context  •  Esc clear/back  •  Tab focus" );
}

void construction_workspace::draw_footer()
{
    werase( footer );
    draw_border( footer, c_light_gray );
    trim_and_print( footer, point( 2, 1 ), std::max( 1, getmaxx( footer ) - 16 ),
                    transient_status.empty() ? c_light_gray : c_yellow, footer_status() );
    trim_and_print( footer, point( std::max( 2, getmaxx( footer ) - 13 ), 1 ), 11, c_light_cyan,
                    string_format( _( "Zoom %d%%" ), viewport.map_zoom_percent() ) );
    wnoutrefresh( footer );
}

void construction_workspace::draw_world_overlay() const
{
    if( mode == construction_workspace_mode::plan ||
        mode == construction_workspace_mode::plans ) {
        for( const construction_plan &plan : nearby_plans ) {
            const tripoint_bub_ms position = here.get_bub( plan.position );
            if( !here.inbounds( position ) ) {
                continue;
            }
            if( plan.status != construction_plan_status::completed &&
                plan.desired.is_valid() && !plan.desired.obj().post_terrain.empty() ) {
                const construction &desired = plan.desired.obj();
                if( desired.post_is_furniture ) {
                    viewport.draw_map_furniture_override(
                        position, furn_str_id( desired.post_terrain ) );
                } else {
                    viewport.draw_map_terrain_override(
                        position, ter_str_id( desired.post_terrain ) );
                }
            }
            viewport.draw_map_highlight( position );
            const std::pair<std::string, nc_color> marker =
                construction_plan_marker( plan.status );
            viewport.draw_map_marker( position, marker.first, marker.second );
        }
        if( mode == construction_workspace_mode::plans ) {
            if( selected_plan_abs ) {
                viewport.draw_map_cursor( here.get_bub( *selected_plan_abs ) );
            }
            return;
        }
    }

    const auto draw_status = [&]( const tripoint_bub_ms & position,
    const construction_target_resolution & state ) {
        std::string symbol = "×";
        nc_color color = c_light_red;
        if( state.unfinished && state.ready() ) {
            symbol = "▣";
            color = c_light_blue;
        } else if( state.status == construction_target_status::ready ) {
            symbol = "✓";
            color = c_light_green;
        } else if( state.status == construction_target_status::unavailable_requirements ) {
            symbol = "!";
            color = c_yellow;
        }
#if defined(TILES)
        if( operation != construction_operation::remove ) {
            viewport.draw_map_highlight( position );
        }
#else
        here.drawsq( g->w_terrain, position,
                     drawsq_params().highlight( true ).show_items( true )
                     .center( you.pos_bub() + you.view_offset ) );
#endif
        viewport.draw_map_marker( position, symbol, color );
    };

    std::set<tripoint_bub_ms> marked;
    if( operation != construction_operation::build || selected_group.is_null() ) {
        for( const auto &entry : adjacent_resolutions ) {
            draw_status( entry.first, entry.second );
            marked.insert( entry.first );
        }
    }

    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        return;
    }
    if( mode == construction_workspace_mode::build && selected_group.is_null() &&
        !resolution.unfinished ) {
        viewport.draw_map_highlight( *target );
        if( !context_actions.empty() ) {
            viewport.draw_map_marker( *target, "•", c_light_cyan );
        }
        if( selected_target ) {
            viewport.draw_map_cursor( *selected_target );
        }
        return;
    }
    const construction *con = resolved_construction();
    if( operation == construction_operation::remove ) {
        // A removal preview describes the existing visible object, not the
        // terrain that may be exposed afterward.  Preserve every world layer
        // and tint the completed tile red instead of swapping its sprite.
        viewport.draw_map_removal_overlay( *target );
    } else if( con && !con->post_terrain.empty() ) {
        if( con->post_is_furniture ) {
            viewport.draw_map_furniture_override( *target, furn_str_id( con->post_terrain ) );
        } else {
            viewport.draw_map_terrain_override( *target, ter_str_id( con->post_terrain ) );
        }
    }
    if( const partial_con *partial = here.partial_con_at( *target ) ) {
        viewport.draw_map_progress_bar( *target,
                                        std::clamp( partial->counter / 10000000.0f, 0.0f, 1.0f ) );
    }
    if( marked.count( *target ) == 0 ) {
        draw_status( *target, resolution );
    }
    if( selected_target && hovered_target && *hovered_target != *selected_target ) {
        const construction_target_resolution hover_state = resolve_active_target( *hovered_target );
        if( marked.count( *hovered_target ) == 0 ) {
            draw_status( *hovered_target, hover_state );
        }
    }
    if( selected_target ) {
        viewport.draw_map_cursor( *selected_target );
    }
}

void construction_workspace::draw( ui_adaptor &ui )
{
    audit_camera_state( "draw" );
    synchronize_handoff_coordinates();
#if defined(TILES)
    viewport.begin_map_overlay_frame();
    draw_world_overlay();
    // Draw the live map first.  Panels/tooltips/dropdowns then composite over
    // it, and the next frame repaints anything they previously covered.
    viewport.draw_map_preview();
#endif
    draw_header();
    draw_palette();
    draw_inspector();
    draw_footer();
    ui.disable_cursor();
    if( category_menu.is_open() && palette_window ) {
        category_menu.draw( palette_window );
    }
    if( context_menu.is_open() ) {
        context_menu.draw( catacurses::stdscr );
    }
}

void construction_workspace::set_focus( const workspace_focus next, ui_adaptor &ui )
{
    if( operation == construction_operation::remove && next == workspace_focus::palette ) {
        return;
    }
    if( focus == next ) {
        return;
    }
    focus = next;
    transient_status.clear();
    if( compact ) {
        ui.mark_resize();
    }
}

void construction_workspace::set_workspace_mode( const construction_workspace_mode next,
        ui_adaptor &ui )
{
    if( mode == next ) {
        return;
    }
    const construction_workspace_mode previous_mode = mode;
    const bool previous_catalog = previous_mode == construction_workspace_mode::build ||
                                  previous_mode == construction_workspace_mode::plan;
    const bool next_catalog = next == construction_workspace_mode::build ||
                              next == construction_workspace_mode::plan;
    if( previous_catalog ) {
        uistate.construction_filter = search;
    }
    if( next == construction_workspace_mode::plans && !selected_group.is_null() ) {
        catalog_group_before_plans = selected_group;
    }

    switch( next ) {
        case construction_workspace_mode::build:
        case construction_workspace_mode::plan:
        case construction_workspace_mode::plans:
            operation = construction_operation::build;
            break;
        case construction_workspace_mode::place:
            operation = construction_operation::place;
            break;
        case construction_workspace_mode::remove:
            operation = construction_operation::remove;
            break;
        case construction_workspace_mode::markers:
            operation = construction_operation::markers;
            break;
    }
    mode = next;
    search = next_catalog ? uistate.construction_filter : std::string();
    category_menu.close();
    context_menu.close();
    if( next == construction_workspace_mode::plans ) {
        selected_group = construction_group_str_id::NULL_ID();
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
    } else if( previous_mode == construction_workspace_mode::plans && next_catalog ) {
        selected_group = catalog_group_before_plans;
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
    } else if( !( previous_catalog && next_catalog ) ) {
        selected_group = construction_group_str_id::NULL_ID();
        selected_target.reset();
        selected_plan_abs.reset();
        hovered_target.reset();
        context_target.reset();
        section_filter.reset();
        selection_cleared_by_user = false;
    }
    transient_status.clear();
    if( operation == construction_operation::remove ) {
        focus = workspace_focus::viewport;
    } else {
        focus = workspace_focus::palette;
    }
    if( mode == construction_workspace_mode::plan ||
        mode == construction_workspace_mode::plans ) {
        refresh_nearby_plans();
    }
    rebuild_palette();
    refresh_active_target();
    // Remove has no palette window, so every operation switch must rebuild the
    // layout even on wide screens.  Otherwise Build inherits Remove's missing
    // left panel until some unrelated resize occurs.
    ui.mark_resize();
}

void construction_workspace::edit_search()
{
    if( operation == construction_operation::remove ) {
        transient_status = _( "Search is not needed in Remove mode." );
        return;
    }
    if( mode == construction_workspace_mode::plans ) {
        const std::optional<std::string> edited = ui_query_text_input_dialog(
                    _( "Search plans" ), _( "Search" ), plans_search, 30, 100 );
        if( edited ) {
            plans_search = *edited;
            rebuild_plan_palette();
        }
        return;
    }
    const std::string title = operation == construction_operation::place ?
                              _( "Search carried items" ) : operation == construction_operation::markers ?
                              _( "Search markers" ) : _( "Search constructions" );
    const std::optional<std::string> edited = ui_query_text_input_dialog(
            title, _( "Search" ), search, 30, 100 );
    if( edited ) {
        search = *edited;
        if( operation == construction_operation::build ) {
            uistate.construction_filter = search;
        }
        rebuild_palette();
    }
}

void construction_workspace::open_category_menu()
{
    if( !palette_window || operation == construction_operation::remove ||
        mode == construction_workspace_mode::plans ) {
        return;
    }
    std::set<construction_ui_section> sections;
    for( const construction &con : get_constructions() ) {
        if( palette_accepts( con ) ) {
            sections.insert( con.ui_section );
        }
    }
    std::vector<ui_dropdown_entry> entries;
    entries.emplace_back( _( "All sections" ), "SECTION_ALL", true, !section_filter );
    for( const construction_ui_section candidate : {
             construction_ui_section::structures, construction_ui_section::furniture,
             construction_ui_section::workshop, construction_ui_section::outdoor,
             construction_ui_section::infrastructure, construction_ui_section::appliances,
             construction_ui_section::other
         } ) {
        if( sections.count( candidate ) == 0 ) {
            continue;
        }
        entries.emplace_back( catalog_section_label( candidate ), catalog_section_id( candidate ), true,
                              section_filter && *section_filter == candidate );
    }
    category_menu.configure( palette_window, point( 2, 6 ), std::move( entries ),
                             std::max( 16, palette_width - 4 ) );
    category_menu.focus_selected();
}

void construction_workspace::open_context_menu( const point &anchor,
        const tripoint_bub_ms &target )
{
    context_target = target;
    context_anchor = anchor;
    const tripoint_abs_ms target_abs = here.get_abs( target );
    const construction_plan *existing_plan = plan_at( target_abs );
    if( mode == construction_workspace_mode::plan ) {
        const construction_target_resolution target_resolution = resolve_active_target( target );
        const bool plannable = !selected_group.is_null() &&
                               !target_resolution.unfinished &&
                               target_resolution.has_construction() &&
                               target_resolution.status !=
                               construction_target_status::invalid_location;
        const bool same_plan = existing_plan != nullptr && existing_plan->group == selected_group;
        std::vector<ui_dropdown_entry> entries = {
            ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" )
        };
        if( !selected_group.is_null() ) {
            entries.emplace_back( same_plan ? _( "Already planned" ) :
                                  existing_plan == nullptr ? _( "Plan here" ) : _( "Replace plan" ),
                                  "PLAN_HERE", plannable && !same_plan, false,
                                  same_plan ? _( "That construction is already planned here." ) :
                                  plannable ? std::string() : target_resolution.reason );
        }
        if( existing_plan != nullptr ) {
            entries.emplace_back( _( "Remove plan" ), "REMOVE_PLAN_HERE" );
        }
        entries.emplace_back( _( "Center view here" ), "CENTER" );
        entries.emplace_back( _( "Clear selection" ), "CLEAR", selected_target.has_value() ||
                              !selected_group.is_null() );
        context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
        return;
    }
    if( mode == construction_workspace_mode::plans ) {
        const bool has_executable = std::any_of( nearby_plans.begin(), nearby_plans.end(),
        []( const construction_plan & plan ) {
            return construction_plan_can_execute( plan.status );
        } );
        std::vector<ui_dropdown_entry> entries;
        entries.emplace_back( existing_plan == nullptr ? _( "No plan here" ) : _( "Select plan" ),
                              "SELECT_PLAN", existing_plan != nullptr, false,
                              _( "There is no active construction plan on this tile." ) );
        if( existing_plan != nullptr ) {
            entries.emplace_back( _( "Remove plan" ), "REMOVE_PLAN_HERE" );
        }
        entries.emplace_back( _( "Execute plans" ), "EXECUTE_PLANS",
                              has_executable, false,
                              nearby_plans.empty() ? _( "There are no nearby plans." ) :
                              _( "No nearby plan can currently execute." ) );
        entries.emplace_back( _( "Center view here" ), "CENTER" );
        context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
        return;
    }
    const construction_target_resolution target_resolution = resolve_active_target( target );
    const bool adjacent = target_is_adjacent( target );
    const bool can_walk = ( operation == construction_operation::build ||
                            operation == construction_operation::remove ) && !adjacent;
    const ret_val<void> reachable = can_walk ? can_reach_construction_target( you, target ) :
                                    ret_val<void>::make_success();
    const bool buildable = target_resolution.ready() && ( adjacent || can_walk ) &&
                           reachable.success();
    std::string build_reason = target_resolution.reason;
    std::string build_label = operation == construction_operation::remove ? _( "Remove here" ) :
                              operation == construction_operation::place ? _( "Place here" ) :
                              operation == construction_operation::markers ? _( "Mark here" ) : _( "Build here" );
    if( operation == construction_operation::remove && target_resolution.id.is_valid() ) {
        build_label = string_format( _( "Remove %s" ), target_resolution.id.obj().group->name() );
    } else if( target_resolution.unfinished ) {
        build_label = _( "Continue" );
    }
    if( !adjacent ) {
        build_label = target_resolution.unfinished ? _( "Walk there and continue" ) :
                      operation == construction_operation::build ? _( "Walk there and build" ) :
                      operation == construction_operation::remove ? _( "Go there and remove" ) :
                      operation == construction_operation::place ? _( "Go there and place" ) :
                      _( "Go there and mark" );
        build_reason = can_walk && !reachable.success() ? reachable.str() :
                       operation == construction_operation::build ||
                       operation == construction_operation::remove ? target_resolution.reason :
                       operation == construction_operation::place ?
                       _( "Distant placement orders are not implemented yet." ) :
                       _( "Distant marker orders are not implemented yet." );
    }
    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" )
    };
    if( operation == construction_operation::remove || !selected_group.is_null() ||
        target_resolution.unfinished ) {
        entries.emplace_back( build_label, "APPLY", buildable, false, build_reason );
    }
    if( mode == construction_workspace_mode::build ) {
        std::vector<ui_dropdown_entry> contextual_entries;
        bool has_decorate = false;
        bool decorate_ready = false;
        std::string decorate_reason;
        for( const construction_context_action &action :
             resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {
            if( action.intent == construction_ui_intent::decorate ) {
                has_decorate = true;
                decorate_ready = decorate_ready || action.resolution.ready();
                if( decorate_reason.empty() && !action.resolution.ready() ) {
                    decorate_reason = action.resolution.reason;
                }
                continue;
            }
            bool enabled = action.resolution.ready() && adjacent;
            std::string reason = action.resolution.reason;
            if( !adjacent ) {
                reason = _( "Move adjacent to use this tile action." );
            }
            contextual_entries.emplace_back( contextual_action_label( action ),
                                               contextual_action_id( action ),
                                               enabled, false, reason );
        }
        if( has_decorate ) {
            const bool enabled = decorate_ready && adjacent;
            const std::string reason = !adjacent ? _( "Move adjacent to decorate this tile." ) :
                                       decorate_ready ? std::string() : decorate_reason;
            contextual_entries.emplace_back( _( "Decorate…" ), "CONTEXT_GROUP_DECORATE",
                                               enabled, false, reason );
        }
        entries.insert( entries.begin() + 1, contextual_entries.begin(), contextual_entries.end() );
    }
    entries.emplace_back( _( "Center view here" ), "CENTER" );
    entries.emplace_back( _( "Clear selection" ), "CLEAR", selected_target.has_value() ||
                          !selected_group.is_null() );
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
}

void construction_workspace::open_context_intent_menu( const point &anchor,
        const tripoint_bub_ms &target, const construction_ui_intent intent )
{
    context_target = target;
    context_anchor = anchor;
    const bool adjacent = target_is_adjacent( target );
    std::vector<ui_dropdown_entry> entries;
    for( const construction_context_action &action :
         resolve_context_construction_actions( you, you.crafting_inventory(), target ) ) {
        if( action.intent != intent ) {
            continue;
        }
        bool enabled = action.resolution.ready() && adjacent;
        std::string reason = adjacent ? action.resolution.reason :
                             _( "Move adjacent to use this tile action." );
        entries.emplace_back( contextual_action_label( action ), contextual_action_id( action ),
                              enabled, false, reason );
    }
    if( entries.empty() ) {
        entries.emplace_back( _( "No applicable actions" ), "NO_ACTION", false, false,
                              _( "This tile has no applicable action in that group." ) );
    }
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
}

bool construction_workspace::execute_context_action( const std::string &id )
{
    if( !context_target ) {
        return false;
    }
    if( id == "SELECT_TILE" ) {
        selected_target = context_target;
        hovered_target.reset();
        refresh_active_target();
    } else if( id == "SELECT_PLAN" ) {
        select_plan( here.get_abs( *context_target ), true );
        rebuild_plan_palette();
    } else if( id == "PLAN_HERE" ) {
        return request_plan( *context_target );
    } else if( id == "REMOVE_PLAN_HERE" ) {
        selected_plan_abs = here.get_abs( *context_target );
        return remove_selected_plan();
    } else if( id == "EXECUTE_PLANS" ) {
        return request_execute_plans();
    } else if( id == "CONTEXT_GROUP_DECORATE" ) {
        if( context_anchor ) {
            open_context_intent_menu( *context_anchor, *context_target,
                                      construction_ui_intent::decorate );
        }
    } else if( id.rfind( "CONTEXT_", 0 ) == 0 ) {
        return request_context_action( id, *context_target );
    } else if( id == "APPLY" ) {
        return request_action( *context_target );
    } else if( id == "CENTER" ) {
        viewport.center_map_on( you, *context_target );
        audit_camera_state( "context-center", true );
    } else if( id == "CLEAR" ) {
        clear_selection();
    }
    return false;
}

bool construction_workspace::request_action( const tripoint_bub_ms &target )
{
    if( mode == construction_workspace_mode::plan ) {
        return request_plan( target );
    }
    if( mode == construction_workspace_mode::plans ) {
        const construction_plan *plan = plan_at( here.get_abs( target ) );
        if( plan == nullptr ) {
            transient_status = _( "There is no construction plan on that tile." );
            return false;
        }
        select_plan( plan->position, true );
        rebuild_plan_palette();
        return true;
    }
    const construction_target_resolution current = resolve_active_target( target );
    if( operation != construction_operation::remove && selected_group.is_null() &&
        !( operation == construction_operation::build && current.unfinished ) ) {
        transient_status = operation == construction_operation::build ?
                           _( "Choose a build result, or use an available tile action." ) :
                           operation == construction_operation::place ?
                           _( "Choose a carried item to place." ) : _( "Choose a marker." );
        return false;
    }
    const bool can_walk = operation == construction_operation::build ||
                          operation == construction_operation::remove;
    if( !target_is_adjacent( target ) && !can_walk ) {
        transient_status = operation == construction_operation::place ?
                           _( "Distant placement orders are not implemented yet." ) :
                           _( "Distant marker orders are not implemented yet." );
        return false;
    }
    if( !current.ready() ) {
        transient_status = current.reason;
        return false;
    }
    if( can_walk && !target_is_adjacent( target ) ) {
        const ret_val<void> reachable = can_reach_construction_target( you, target );
        if( !reachable.success() ) {
            transient_status = reachable.str();
            return false;
        }
    }
    if( !current.unfinished && !g->warn_player_maybe_anger_local_faction( true ) ) {
        transient_status = _( "Construction canceled." );
        return false;
    }
    selected_target = target;
    hovered_target.reset();
    if( operation == construction_operation::build && current.unfinished &&
        current.id.is_valid() && palette_accepts( current.id.obj() ) ) {
        selected_group = current.id.obj().group;
        selection_cleared_by_user = false;
        rebuild_palette();
    }
    build_order = construction_build_order{ current.id, target,
                                            current.unfinished,
                                            operation == construction_operation::place };
    exit_requested = true;
    return true;
}

bool construction_workspace::request_plan( const tripoint_bub_ms &target )
{
    const construction_plan_mutation planned = set_construction_plan( you, selected_group, target );
    transient_status = planned.message;
    if( !planned.success ) {
        refresh_active_target();
        return false;
    }
    selected_target = target;
    hovered_target.reset();
    selected_plan_abs = here.get_abs( target );
    refresh_nearby_plans();
    refresh_active_target();
    return true;
}

bool construction_workspace::remove_selected_plan()
{
    if( !selected_plan_abs ) {
        transient_status = _( "Select a construction plan first." );
        return false;
    }
    const tripoint_abs_ms removed = *selected_plan_abs;
    const ret_val<void> result = remove_construction_plan( you, removed );
    if( !result.success() ) {
        transient_status = result.str();
        return false;
    }
    selected_plan_abs.reset();
    if( selected_target && here.get_abs( *selected_target ) == removed ) {
        selected_target.reset();
    }
    transient_status = _( "Construction plan removed." );
    refresh_nearby_plans();
    if( mode == construction_workspace_mode::plans ) {
        rebuild_plan_palette();
    } else {
        refresh_active_target();
    }
    return true;
}

bool construction_workspace::request_execute_plans()
{
    refresh_nearby_plans();
    const bool has_executable = std::any_of( nearby_plans.begin(), nearby_plans.end(),
    []( const construction_plan & plan ) {
        return construction_plan_can_execute( plan.status );
    } );
    if( !has_executable ) {
        transient_status = nearby_plans.empty() ?
                           _( "There are no nearby construction plans." ) :
                           _( "No nearby construction plan can currently execute.  "
                              "Select a plan to see why." );
        rebuild_plans_inspector();
        return false;
    }
    execute_plans_order = true;
    exit_requested = true;
    context_menu.close();
    return true;
}

bool construction_workspace::request_context_action( const std::string &id,
        const tripoint_bub_ms &target )
{
    const std::vector<construction_context_action> current =
        resolve_context_construction_actions( you, you.crafting_inventory(), target );
    const auto found = std::find_if( current.begin(), current.end(),
    [&id]( const construction_context_action & action ) {
        return contextual_action_id( action ) == id;
    } );
    if( found == current.end() ) {
        transient_status = _( "That tile action is no longer applicable." );
        return false;
    }
    if( !target_is_adjacent( target ) ) {
        transient_status = _( "Move adjacent to use this tile action." );
        return false;
    }
    if( !found->resolution.ready() ) {
        transient_status = found->resolution.reason;
        return false;
    }
    if( !g->warn_player_maybe_anger_local_faction( true ) ) {
        transient_status = _( "Construction canceled." );
        return false;
    }
    selected_target = target;
    hovered_target.reset();
    build_order = construction_build_order{ found->resolution.id, target, false };
    exit_requested = true;
    return true;
}

bool construction_workspace::handle_viewport_action(
    const ui_world_viewport_action &action, ui_adaptor &ui )
{
    switch( action.type ) {
        case ui_world_viewport_action_type::hover:
            if( hovered_target == action.world_position ) {
                return false;
            }
            hovered_target = action.world_position;
            if( !selected_target ) {
                refresh_active_target();
            }
            return true;
        case ui_world_viewport_action_type::select:
            if( action.world_position ) {
                if( mode == construction_workspace_mode::plans ) {
                    const tripoint_abs_ms position = here.get_abs( *action.world_position );
                    if( plan_at( position ) != nullptr ) {
                        select_plan( position, false );
                    } else {
                        selected_plan_abs.reset();
                        selected_target = action.world_position;
                    }
                    rebuild_plan_palette();
                    set_focus( workspace_focus::viewport, ui );
                    return true;
                }
                selected_target = action.world_position;
                hovered_target.reset();
                refresh_active_target();
                set_focus( workspace_focus::viewport, ui );
                if( mode == construction_workspace_mode::plan ) {
                    const construction_plan *existing = plan_at(
                                here.get_abs( *action.world_position ) );
                    if( existing == nullptr && !selected_group.is_null() ) {
                        request_plan( *action.world_position );
                    }
                } else if( mode == construction_workspace_mode::build &&
                    ( !selected_group.is_null() || resolution.unfinished ) ) {
                    const bool continuing = resolution.unfinished;
                    if( !request_action( *action.world_position ) && !continuing ) {
                        selected_target.reset();
                        hovered_target = action.world_position;
                        refresh_active_target();
                    }
                }
            }
            return true;
        case ui_world_viewport_action_type::context:
            if( action.world_position && action.position ) {
                open_context_menu( *action.position, *action.world_position );
                set_focus( workspace_focus::viewport, ui );
            }
            return true;
        case ui_world_viewport_action_type::pan_start:
        case ui_world_viewport_action_type::pan_move:
        case ui_world_viewport_action_type::pan_end:
        case ui_world_viewport_action_type::zoom_in:
        case ui_world_viewport_action_type::zoom_out:
            audit_camera_state( "pointer-camera", true );
            return true;
        case ui_world_viewport_action_type::handled:
            return true;
        case ui_world_viewport_action_type::ignored:
            return false;
    }
    return false;
}

bool construction_workspace::handle_pointer( const std::string &action,
        input_context &context, ui_adaptor &ui )
{
    // poll_activity_input() can return to this editor between a mouse press and
    // its release.  Swallow that release so a click used to pause construction
    // cannot also select a tile, activate a control, or start another build.
    if( action == "SELECT" && suppress_next_select_release ) {
        suppress_next_select_release = false;
        return true;
    }
    if( action == "SEC_SELECT" && suppress_next_secondary_release ) {
        suppress_next_secondary_release = false;
        return true;
    }

    const std::optional<point> screen_pos = context.get_coordinates_text( catacurses::stdscr );
    const std::optional<point> header_pos = header ? context.get_coordinates_text(
            header ) : std::nullopt;
    const std::optional<point> palette_pos = palette_window ?
        context.get_coordinates_text( palette_window ) : std::nullopt;
    const std::optional<point> inspector_pos = inspector_window ?
        context.get_coordinates_text( inspector_window ) : std::nullopt;

    // Hover is transient preview state.  Crossing into a panel immediately
    // restores the explicitly selected target instead of leaving a stale map
    // tile active beneath buttons or list rows.
    if( action == "MOUSE_MOVE" && !viewport.contains( screen_pos ) && hovered_target ) {
        hovered_target.reset();
        refresh_active_target();
        ui.invalidate_ui();
#if !defined(TILES)
        g->invalidate_main_ui_adaptor();
#endif
    }

    // A captured map drag owns every pointer event through release, even when
    // the pointer crosses a panel.  Route it before dropdowns and controls so
    // releasing or clicking over another surface cannot activate that surface.
    if( viewport.has_capture() ) {
        return handle_viewport_action( viewport.handle_map_input( action, context, you, screen_pos ), ui );
    }

    if( category_menu.is_open() ) {
        std::optional<inclusive_rectangle<point>> trigger;
        if( const auto bounds = palette_actions.bounds_for_id( "CATEGORY" ) ) {
            trigger.emplace( bounds->p_min, bounds->p_max );
        }
        const ui_action_result result = category_menu.handle_input(
                                            action, palette_pos, true,
                                            ui_outside_click_policy::passthrough, trigger, &context );
        if( result.type == ui_action_result_type::activated && result.entry ) {
            if( result.entry->id == "SECTION_ALL" ) {
                section_filter.reset();
            } else {
                section_filter = catalog_section_from_id( result.entry->id );
            }
            rebuild_palette();
            transient_status.clear();
            return true;
        }
        if( result.type == ui_action_result_type::disabled && result.entry ) {
            transient_status = result.entry->disabled_reason;
        }
        if( result.consumed() ) {
            return true;
        }
    }

    if( context_menu.is_open() ) {
        const ui_action_result result = context_menu.handle_input(
                                            action, screen_pos, true,
                                            ui_outside_click_policy::passthrough, std::nullopt, &context );
        if( result.type == ui_action_result_type::activated && result.entry ) {
            execute_context_action( result.entry->id );
            return true;
        }
        if( result.type == ui_action_result_type::disabled && result.entry ) {
            transient_status = result.entry->disabled_reason;
            return true;
        }
        if( result.consumed() ) {
            return true;
        }
    }

    if( palette.has_capture() ) {
        return palette.handle_input( action, context, palette_pos ).consumed();
    }
    if( inspector.has_capture() && inspector.handle_input( action, context, inspector_pos ) ) {
        return true;
    }

    const ui_action_result header_result = header_actions.handle_pointer_input( action, header_pos );
    if( header_result.type == ui_action_result_type::disabled && header_result.entry ) {
        transient_status = header_result.entry->disabled_reason;
        return true;
    }
    if( header_result.type == ui_action_result_type::activated && header_result.entry ) {
        const std::string &id = header_result.entry->id;
        if( id == "BACK" ) {
            exit_requested = true;
        } else if( id == "MODE_BUILD" ) {
            set_workspace_mode( construction_workspace_mode::build, ui );
        } else if( id == "MODE_PLACE" ) {
            set_workspace_mode( construction_workspace_mode::place, ui );
        } else if( id == "MODE_REMOVE" ) {
            set_workspace_mode( construction_workspace_mode::remove, ui );
        } else if( id == "MODE_MARKERS" ) {
            set_workspace_mode( construction_workspace_mode::markers, ui );
        } else if( id == "MODE_PLAN" ) {
            set_workspace_mode( construction_workspace_mode::plan, ui );
        } else if( id == "MODE_PLANS" ) {
            set_workspace_mode( construction_workspace_mode::plans, ui );
        } else if( id == "FOCUS_PALETTE" ) {
            set_focus( workspace_focus::palette, ui );
        } else if( id == "FOCUS_VIEWPORT" ) {
            set_focus( workspace_focus::viewport, ui );
        } else if( id == "FOCUS_INSPECTOR" ) {
            set_focus( workspace_focus::inspector, ui );
        }
        return true;
    }

    if( palette_window && operation != construction_operation::remove ) {
        if( mode == construction_workspace_mode::plans && palette_pos ) {
            if( action == "SELECT" && palette_pos ) {
                const ui_text_field_hit hit = search_field.hit_test( *palette_pos );
                if( hit == ui_text_field_hit::clear ) {
                    plans_search.clear();
                    rebuild_plan_palette();
                    return true;
                }
                if( hit == ui_text_field_hit::edit ) {
                    edit_search();
                    return true;
                }
            }
            const ui_action_result list_result = palette.handle_input(
                    action, context, palette_pos );
            if( list_result.entry &&
                ( list_result.type == ui_action_result_type::handled ||
                  list_result.type == ui_action_result_type::activated ) ) {
                const auto found = std::find_if( visible_plan_positions.begin(),
                visible_plan_positions.end(), [&list_result]( const tripoint_abs_ms & position ) {
                    return construction_plan_entry_id( position ) == list_result.entry->id;
                } );
                if( found != visible_plan_positions.end() ) {
                    select_plan( *found, true );
                    rebuild_plan_palette();
                    inspector.model().scroll_to_start();
                    set_focus( workspace_focus::inspector, ui );
                }
            }
            return list_result.consumed();
        }
        const ui_action_result palette_action = palette_actions.handle_pointer_input( action, palette_pos );
        if( palette_action.type == ui_action_result_type::activated && palette_action.entry ) {
            if( palette_action.entry->id == "CATEGORY" ) {
                open_category_menu();
            } else if( palette_action.entry->id == "SHOW_UNAVAILABLE" &&
                       operation == construction_operation::build ) {
                show_unavailable = !show_unavailable;
                rebuild_palette();
            }
            set_focus( workspace_focus::palette, ui );
            return true;
        }
        if( action == "SELECT" && palette_pos ) {
            const ui_text_field_hit hit = search_field.hit_test( *palette_pos );
            if( hit == ui_text_field_hit::clear ) {
                search.clear();
                if( operation == construction_operation::build ) {
                    uistate.construction_filter.clear();
                }
                rebuild_palette();
                return true;
            }
            if( hit == ui_text_field_hit::edit ) {
                edit_search();
                return true;
            }
        }
        const ui_action_result list_result = palette.handle_input( action, context, palette_pos );
        if( list_result.entry && ( list_result.type == ui_action_result_type::handled ||
                                   list_result.type == ui_action_result_type::activated ) ) {
            selected_group = construction_group_str_id( list_result.entry->id );
            selection_cleared_by_user = false;
            selected_target.reset();
            context_target.reset();
            context_anchor.reset();
            if( operation == construction_operation::build ) {
                uistate.last_construction = selected_group;
            }
            refresh_active_target();
            inspector.model().scroll_to_start();
            set_focus( workspace_focus::viewport, ui );
            transient_status = placement_prompt();
            return true;
        }
        if( list_result.consumed() ) {
            return true;
        }
    }

    if( inspector_window ) {
        const ui_action_result contextual_result =
            contextual_action_strip.handle_pointer_input( action, inspector_pos );
        if( contextual_result.type == ui_action_result_type::disabled && contextual_result.entry ) {
            transient_status = contextual_result.entry->disabled_reason;
            return true;
        }
        if( contextual_result.type == ui_action_result_type::activated && contextual_result.entry ) {
            if( selected_target ) {
                if( contextual_result.entry->id == "CONTEXT_GROUP_DECORATE" && screen_pos ) {
                    open_context_intent_menu( *screen_pos, *selected_target,
                                              construction_ui_intent::decorate );
                } else {
                    request_context_action( contextual_result.entry->id, *selected_target );
                }
            }
            return true;
        }

        const ui_action_result build_result = primary_action.handle_pointer_input( action, inspector_pos );
        if( build_result.type == ui_action_result_type::disabled && build_result.entry ) {
            transient_status = build_result.entry->disabled_reason;
            return true;
        }
        if( build_result.type == ui_action_result_type::activated && build_result.entry ) {
            if( build_result.entry->id == "PAUSE" ) {
                transient_status = _( "Construction is already paused." );
            } else if( build_result.entry->id == "EXECUTE_PLANS" ) {
                request_execute_plans();
            } else if( build_result.entry->id == "REMOVE_PLAN" ) {
                remove_selected_plan();
            } else if( selected_target ) {
                request_action( *selected_target );
            }
            return true;
        }
        if( inspector.handle_input( action, context, inspector_pos ) ) {
            set_focus( workspace_focus::inspector, ui );
            return true;
        }
    }

    return handle_viewport_action( viewport.handle_map_input( action, context, you, screen_pos ), ui );
}

bool construction_workspace::handle_input( const std::string &action,
        input_context &context, ui_adaptor &ui )
{
    if( action != "MOUSE_MOVE" ) {
        if( !transient_status.empty() ) {
            ui.invalidate_ui();
        }
        transient_status.clear();
    }
    if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ||
        action == "SCROLL_UP" || action == "SCROLL_DOWN" ||
        action == "CLICK_AND_DRAG" || action == "CAMERA_PAN_START" ||
        action == "CAMERA_PAN_END" ) {
        return handle_pointer( action, context, ui );
    }
    if( action == "QUIT" ) {
        if( category_menu.is_open() ) {
            category_menu.close();
        } else if( context_menu.is_open() ) {
            context_menu.close();
        } else if( !selected_group.is_null() || selected_target || hovered_target || context_target ) {
            clear_selection();
        } else {
            exit_requested = true;
        }
        return true;
    }
    if( action == "NEXT_TAB" || action == "PREV_TAB" ) {
        const int direction = action == "NEXT_TAB" ? 1 : -1;
        int next = ( static_cast<int>( focus ) + direction + 3 ) % 3;
        if( operation == construction_operation::remove &&
            next == static_cast<int>( workspace_focus::palette ) ) {
            next = ( next + direction + 3 ) % 3;
        }
        set_focus( static_cast<workspace_focus>( next ), ui );
        return true;
    }
    if( action == "FILTER" ) {
        edit_search();
        return true;
    }
    if( action == "TOGGLE_UNAVAILABLE_CONSTRUCTIONS" ) {
        if( mode != construction_workspace_mode::build &&
            mode != construction_workspace_mode::plan ) {
            transient_status =
                _( "Unavailable filtering is only used by the Build and Plan catalogs." );
            return true;
        }
        show_unavailable = !show_unavailable;
        rebuild_palette();
        return true;
    }
    if( action == "CONSTRUCTION_CENTER" ) {
        viewport.center_map_on_viewer( you );
        audit_camera_state( "keyboard-center", true );
        return true;
    }
    if( action == "CONSTRUCTION_BUILD" ) {
        if( mode == construction_workspace_mode::plans ) {
            request_execute_plans();
        } else if( selected_target ) {
            request_action( *selected_target );
        } else {
            transient_status = _( "Select a target first." );
        }
        return true;
    }
    if( action == "zoom_in" || action == "zoom_out" ) {
        viewport.zoom_map_camera( action == "zoom_in" ? 1 : -1, context, you );
        audit_camera_state( "keyboard-zoom", true );
        return true;
    }

    if( focus == workspace_focus::palette && palette_window &&
        operation != construction_operation::remove ) {
        if( mode == construction_workspace_mode::plans ) {
            const ui_action_result result = palette.handle_input( action, context, std::nullopt );
            if( result.entry &&
                ( result.type == ui_action_result_type::handled ||
                  result.type == ui_action_result_type::activated ) ) {
                const auto found = std::find_if( visible_plan_positions.begin(),
                visible_plan_positions.end(), [&result]( const tripoint_abs_ms & position ) {
                    return construction_plan_entry_id( position ) == result.entry->id;
                } );
                if( found != visible_plan_positions.end() ) {
                    select_plan( *found, true );
                    rebuild_plan_palette();
                    inspector.model().scroll_to_start();
                    if( result.type == ui_action_result_type::activated ) {
                        set_focus( workspace_focus::inspector, ui );
                    }
                }
            }
            return result.consumed();
        }
        const ui_action_result result = palette.handle_input( action, context, std::nullopt );
        if( result.entry && ( result.type == ui_action_result_type::handled ||
                              result.type == ui_action_result_type::activated ) ) {
            selected_group = construction_group_str_id( result.entry->id );
            selection_cleared_by_user = false;
            selected_target.reset();
            context_target.reset();
            context_anchor.reset();
            if( operation == construction_operation::build ) {
                uistate.last_construction = selected_group;
            }
            refresh_active_target();
            inspector.model().scroll_to_start();
            if( result.type == ui_action_result_type::activated ) {
                set_focus( workspace_focus::viewport, ui );
                transient_status = placement_prompt();
            }
        }
        return result.consumed();
    }
    if( focus == workspace_focus::inspector && inspector_window &&
        inspector.handle_input( action, context, std::nullopt, true ) ) {
        return true;
    }
    if( focus == workspace_focus::viewport ) {
        const std::optional<tripoint_rel_ms> direction = context.get_direction_rel_ms( action );
        if( direction ) {
            viewport.move_map_camera( you, *direction );
            audit_camera_state( "keyboard-pan", true );
            selected_target = viewport.map_camera_center( you );
            hovered_target.reset();
            refresh_active_target();
            return true;
        }
        if( action == "CONFIRM" ) {
            selected_target = viewport.map_camera_center( you );
            hovered_target.reset();
            if( mode == construction_workspace_mode::plans ) {
                request_action( *selected_target );
                return true;
            }
            refresh_active_target();
            if( mode == construction_workspace_mode::plan ||
                operation == construction_operation::remove ||
                ( mode == construction_workspace_mode::build &&
                  ( !selected_group.is_null() || resolution.unfinished ) ) ) {
                request_action( *selected_target );
            }
            return true;
        }
    }
    return false;
}

bool construction_workspace::run()
{
    restore_on_out_of_scope<tripoint_rel_ms> restore_view( you.view_offset );
    on_out_of_scope restore_zoom( [this]() {
        g->set_zoom( original_zoom );
        g->mark_main_ui_adaptor_resize();
    } );

#if defined(TILES)
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( true );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( true );
    }
#else
    g->invalidate_main_ui_adaptor();
#endif

    input_context context( "CONSTRUCTION" );
    context.register_navigate_ui_list();
    context.register_directions();
    for( const char *action : {
             "NEXT_TAB", "PREV_TAB", "CONFIRM", "QUIT",
             "HELP_KEYBINDINGS", "FILTER", "TOGGLE_UNAVAILABLE_CONSTRUCTIONS",
             "CONSTRUCTION_BUILD", "CONSTRUCTION_CENTER", "zoom_in", "zoom_out",
             "SELECT", "SEC_SELECT", "MOUSE_MOVE", "CLICK_AND_DRAG",
             "SCROLL_UP", "SCROLL_DOWN", "CAMERA_PAN_START", "CAMERA_PAN_END"
         } ) {
        context.register_action( action );
    }
    if( viewport.has_animated_weather() ) {
        context.set_timeout( viewport_animation_interval_ms );
    }
    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor();
    ui_hidden = false;
#if defined(TILES)
    current_ui->set_disable_uis_below( true );
#endif
    current_ui->mark_resize();

#if !defined(TILES)
    if( !overlay ) {
        overlay = make_shared_fast<game::draw_callback_t>( [this]() {
            draw_world_overlay();
        } );
        g->add_draw_callback( overlay );
    }
#endif

    while( true ) {
        exit_requested = false;
        build_order.reset();
        while( !exit_requested ) {
            ui_manager::redraw_invalidated();
            const std::string action = context.handle_input();
            if( action == "TIMEOUT" ) {
                current_ui->invalidate_ui();
                continue;
            }
            if( handle_input( action, context, *current_ui ) ) {
                current_ui->invalidate_ui();
#if !defined(TILES)
                g->invalidate_main_ui_adaptor();
#endif
            }
        }

        if( mode == construction_workspace_mode::build ||
            mode == construction_workspace_mode::plan ) {
            uistate.construction_filter = search;
        }
        if( ( mode == construction_workspace_mode::build ||
              mode == construction_workspace_mode::plan ) && !selected_group.is_null() ) {
            uistate.last_construction = selected_group;
        }

        if( execute_plans_order ) {
            execute_plans_order = false;
            you.assign_activity( ACT_MULTIPLE_CONSTRUCTION );
            add_msg( m_info, _( "Executing nearby construction plans." ) );
            return true;
        }

        if( !build_order || !build_order->id.is_valid() ) {
            return true;
        }

        const construction_build_order order = *build_order;
        build_order.reset();
        const ret_val<void> started = order.resume ?
                                      resume_construction_at_or_walk( you, order.target ) :
                                      start_construction_at_or_walk( you, order.id.obj(),
                                              order.target, order.carried_source_only );
        if( !started.success() ) {
            transient_status = started.str();
            rebuild_palette();
            refresh_active_target();
            current_ui->invalidate_ui();
            continue;
        }

        // Paint the reserved partial before yielding to auto-walk/ACT_BUILD and
        // retain this editor.  Distant orders reserve their components up front,
        // so interruption leaves ordinary unfinished work that can be continued.
        refresh_active_target();
        begin_activity_handoff();
        current_ui->invalidate_ui();
        ui_manager::redraw_invalidated();
        return true;
    }
}

} // namespace

namespace construction_ui
{

void discard_persistent_editor()
{
    if( persistent_workspace != nullptr ) {
        delete persistent_workspace;
        persistent_workspace = nullptr;
    }
}

void suspend_persistent_editor_for_query()
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->suspend_for_query();
    }
}

void restore_persistent_editor_after_query()
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->restore_after_query();
    }
}

void resume_persistent_editor_after_activity( const bool construction_completed )
{
    if( persistent_workspace == nullptr ||
        !persistent_workspace->activity_handoff_active() ) {
        return;
    }
    if( TERMX < 60 || TERMY < 16 ) {
        discard_persistent_editor();
        return;
    }
    persistent_workspace->resume_activity_handoff( construction_completed );
    construction_workspace *const editor = persistent_workspace;
    const bool result = editor->run();
    if( !result ) {
        discard_persistent_editor();
        return;
    }
    if( persistent_workspace == editor && !editor->activity_handoff_active() ) {
        discard_persistent_editor();
    }
}

bool persistent_editor_activity_active()
{
    return persistent_workspace != nullptr &&
           persistent_workspace->activity_handoff_active();
}

bool preserve_persistent_editor_on_activity_cancel()
{
    return persistent_workspace != nullptr &&
           persistent_workspace->preserve_on_activity_cancel();
}

void set_persistent_editor_activity_failure( const std::string &reason )
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->set_activity_failure( reason );
    }
}

void notify_persistent_editor_construction_started()
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->mark_construction_started();
    }
}

bool handle_persistent_editor_activity_input()
{
    if( persistent_workspace == nullptr ||
        !persistent_workspace->activity_handoff_active() ) {
        return false;
    }

    construction_workspace *const editor = persistent_workspace;
    if( !editor->poll_activity_input() ) {
        return false;
    }

    // A deliberate editor interaction paused auto-walk/ACT_BUILD.  Re-enter
    // the exact workspace now.  The input that caused the pause is consumed;
    // the next input operates normally on the live editor.
    if( persistent_workspace == editor &&
        !editor->activity_handoff_active() ) {
        editor->run();
        if( persistent_workspace == editor &&
            !editor->activity_handoff_active() ) {
            discard_persistent_editor();
        }
    }
    return true;
}

void redraw_persistent_editor_if_needed()
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->redraw_handoff_if_needed();
    }
}

bool run()
{
    if( TERMX < 60 || TERMY < 16 ) {
        discard_persistent_editor();
        return false;
    }

    // Reuse only the workspace explicitly retained by its own world handoff.
    // An unrelated manual entry always starts clean.
    if( persistent_workspace != nullptr &&
        !persistent_workspace->activity_handoff_active() ) {
        discard_persistent_editor();
    }
    if( persistent_workspace == nullptr ) {
        persistent_workspace = new construction_workspace();
    } else {
        persistent_workspace->resume_activity_handoff();
    }

    construction_workspace *const editor = persistent_workspace;
    const bool result = editor->run();
    if( editor->activity_handoff_active() ) {
        return result;
    }

    discard_persistent_editor();
    return result;
}

} // namespace construction_ui
