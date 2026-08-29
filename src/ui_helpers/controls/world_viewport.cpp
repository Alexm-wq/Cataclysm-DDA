#include "world_viewport.h"

#include <algorithm>

#include "../../character.h"
#include "../../game.h"
#include "../../game_constants.h"
#include "../../input_context.h"

#if defined(TILES)
#include "../../sdl_utils.h"
#endif

std::optional<tripoint_bub_ms> ui_world_viewport::map_position(
    const input_context &context, const Character &viewer,
    const std::optional<point> &position, const bool allow_outside ) const
{
    if( !allow_outside && !contains( position ) ) {
        return std::nullopt;
    }
    const std::optional<tripoint_bub_ms> world = context.get_coordinates(
            g->w_terrain, g->ter_view_p.raw().xy(), true );
    return world && world->z() == viewer.pos_bub().z() ? world : std::nullopt;
}

void ui_world_viewport::center_map_on( Character &viewer,
                                       const tripoint_bub_ms &target ) const
{
    viewer.view_offset = target - viewer.pos_bub();
    g->normalize_map_camera();
    g->invalidate_main_ui_adaptor();
}

void ui_world_viewport::center_map_on_viewer( Character &viewer ) const
{
    viewer.view_offset = tripoint_rel_ms::zero;
    g->normalize_map_camera();
    g->invalidate_main_ui_adaptor();
}

void ui_world_viewport::move_map_camera( Character &viewer,
        const tripoint_rel_ms &delta ) const
{
    viewer.view_offset += delta;
    g->normalize_map_camera();
    g->invalidate_main_ui_adaptor();
}

void ui_world_viewport::zoom_map_camera( const int direction, input_context &context,
        Character &viewer, const std::optional<tripoint_bub_ms> &anchor ) const
{
    const int old_zoom = g->get_zoom();
    const int next = std::clamp( direction > 0 ? old_zoom * 2 : old_zoom / 2,
                                 MINIMUM_TILESET_ZOOM, MAXIMUM_TILESET_ZOOM );
    if( next == old_zoom ) {
        return;
    }

    g->set_zoom( next );
    // The normal game zoom path rebuilds the terrain adaptor after rescaling.
    // Without this, a workspace can report the new percentage while retaining
    // the old terrain geometry until a later unrelated resize.
    g->mark_main_ui_adaptor_resize();
    if( anchor ) {
        const std::optional<tripoint_bub_ms> after = context.get_coordinates(
                g->w_terrain, g->ter_view_p.raw().xy(), true );
        if( after ) {
            viewer.view_offset += *anchor - *after;
            g->normalize_map_camera();
        }
    }
    g->invalidate_main_ui_adaptor();
}

ui_world_viewport_action ui_world_viewport::handle_map_input(
    const std::string &action, input_context &context, Character &viewer,
    const std::optional<point> &position )
{
    const bool had_capture = has_capture();
    ui_world_viewport_action result = handle_input( action, position );
    const bool allow_outside = had_capture || has_capture();
    result.world_position = map_position( context, viewer, position, allow_outside );

    switch( result.type ) {
        case ui_world_viewport_action_type::pan_start:
            map_pan_anchor_ = result.world_position;
            if( !map_pan_anchor_ ) {
                cancel_capture();
                result.type = ui_world_viewport_action_type::ignored;
                break;
            }
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            break;
        case ui_world_viewport_action_type::pan_move:
            if( map_pan_anchor_ && result.world_position ) {
                viewer.view_offset += *map_pan_anchor_ - *result.world_position;
                g->normalize_map_camera();
                g->invalidate_main_ui_adaptor();
                map_pan_anchor_ = map_position( context, viewer, position, true );
            }
            break;
        case ui_world_viewport_action_type::pan_end:
            map_pan_anchor_.reset();
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            break;
        case ui_world_viewport_action_type::zoom_in:
            zoom_map_camera( 1, context, viewer, result.world_position );
            break;
        case ui_world_viewport_action_type::zoom_out:
            zoom_map_camera( -1, context, viewer, result.world_position );
            break;
        default:
            break;
    }
    return result;
}

void ui_world_viewport::cancel_map_capture()
{
    cancel_capture();
    map_pan_anchor_.reset();
#if defined(TILES)
    set_sdl_mouse_capture( false );
#endif
}

int ui_world_viewport::map_zoom_percent() const
{
    return g->get_zoom() * 100 / DEFAULT_TILESET_ZOOM;
}
