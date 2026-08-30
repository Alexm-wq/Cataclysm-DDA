#include "world_viewport.h"

#include <algorithm>
#include <limits>

#include "../../character.h"
#include "../../game.h"
#include "../../input_context.h"

#if defined(TILES)
#include "../../cata_tiles.h"
#include "../../sdl_utils.h"
#include "../../sdltiles.h"
#endif

#if defined(TILES)
static std::shared_ptr<cata_tiles> active_preview_tiles()
{
    return closetilecontext ? closetilecontext : tilecontext;
}
#endif

ui_world_viewport::~ui_world_viewport()
{
    cancel_map_capture();
    detach_map_preview();
}

void ui_world_viewport::configure_map_camera( const tripoint_bub_ms &center,
        const ui_world_viewport_map_config &config )
{
    map_config_ = config;
    map_config_.minimum_draw_scale = std::max( 1, map_config_.minimum_draw_scale );
    map_config_.maximum_draw_scale = std::max( map_config_.minimum_draw_scale,
                                      map_config_.maximum_draw_scale );
    map_config_.initial_draw_scale = std::clamp( map_config_.initial_draw_scale,
                                     map_config_.minimum_draw_scale,
                                     map_config_.maximum_draw_scale );
    map_config_.zoom_factor = std::max( 2, map_config_.zoom_factor );
    for( int &scale : map_config_.draw_scale_steps ) {
        scale = std::clamp( scale, map_config_.minimum_draw_scale,
                            map_config_.maximum_draw_scale );
    }
    std::sort( map_config_.draw_scale_steps.begin(), map_config_.draw_scale_steps.end() );
    map_config_.draw_scale_steps.erase(
        std::unique( map_config_.draw_scale_steps.begin(), map_config_.draw_scale_steps.end() ),
        map_config_.draw_scale_steps.end() );
    if( !map_config_.draw_scale_steps.empty() ) {
        const auto closest = std::min_element( map_config_.draw_scale_steps.begin(),
                                               map_config_.draw_scale_steps.end(),
        [&]( const int lhs, const int rhs ) {
            return std::abs( lhs - map_config_.initial_draw_scale ) <
                   std::abs( rhs - map_config_.initial_draw_scale );
        } );
        map_config_.initial_draw_scale = *closest;
    }
    independent_center_ = center;
    independent_draw_scale_ = map_config_.initial_draw_scale;
    refresh_map_preview_registration();
}

void ui_world_viewport::attach_map_preview( const catacurses::window &window,
        const bool preserve_visual_center )
{
#if defined(TILES)
    std::optional<tripoint_bub_ms> old_mid_map;
    if( preserve_visual_center && map_preview_window_ && independent_center_ ) {
        const window_dimensions old_dim = get_window_dimensions( map_preview_window_ );
        const point old_mid( old_dim.window_size_pixel.x / 2, old_dim.window_size_pixel.y / 2 );
        old_mid_map = map_preview_pixel_to_map( map_preview_window_, old_mid,
                      *independent_center_, independent_draw_scale_ );
    }
    if( map_preview_window_ ) {
        clear_map_preview_window();
    }
#endif
    map_preview_window_ = window;
#if defined(TILES)
    if( preserve_visual_center && old_mid_map && map_preview_window_ && independent_center_ ) {
        const window_dimensions new_dim = get_window_dimensions( map_preview_window_ );
        const point new_mid( new_dim.window_size_pixel.x / 2, new_dim.window_size_pixel.y / 2 );
        const std::optional<tripoint_bub_ms> new_mid_map = map_preview_pixel_to_map(
                    map_preview_window_, new_mid, *independent_center_, independent_draw_scale_ );
        if( new_mid_map ) {
            *independent_center_ += *old_mid_map - *new_mid_map;
        }
    }
#endif
    refresh_map_preview_registration();
}

void ui_world_viewport::detach_map_preview()
{
#if defined(TILES)
    if( map_preview_window_ ) {
        if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
            tiles->void_cursor();
            tiles->void_highlight();
            tiles->void_ui_markers();
            tiles->void_terrain_override();
            tiles->void_furniture_override();
        }
        clear_map_preview_window();
    }
#endif
    map_preview_window_ = catacurses::window();
}

bool ui_world_viewport::has_map_preview() const
{
#if defined(TILES)
    return map_preview_window_ && independent_center_.has_value();
#else
    return false;
#endif
}

void ui_world_viewport::refresh_map_preview_registration() const
{
#if defined(TILES)
    if( map_preview_window_ && independent_center_ ) {
        set_map_preview_window( map_preview_window_, *independent_center_, independent_draw_scale_ );
    }
#endif
}

void ui_world_viewport::draw_map_preview() const
{
#if defined(TILES)
    if( !has_map_preview() ) {
        return;
    }
    refresh_map_preview_registration();
    // Touch the complete preview every frame.  Besides keeping the world live,
    // this guarantees that a dismissed tooltip/dropdown is repainted by the map
    // instead of leaving stale pixels over the viewport.
    werase( map_preview_window_ );
    wnoutrefresh( map_preview_window_ );
#endif
}

void ui_world_viewport::begin_map_overlay_frame() const
{
#if defined(TILES)
    if( !has_map_preview() ) {
        return;
    }
    if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
        tiles->void_cursor();
        tiles->void_highlight();
        tiles->void_ui_markers();
        tiles->void_terrain_override();
        tiles->void_furniture_override();
    }
#endif
}

std::optional<tripoint_bub_ms> ui_world_viewport::map_position(
    const input_context &context, const Character &viewer,
    const std::optional<point> &position, const bool allow_outside ) const
{
    if( !allow_outside && !contains( position ) ) {
        return std::nullopt;
    }

#if defined(TILES)
    if( has_map_preview() ) {
        const std::optional<point> screen_pixel = context.get_coordinates_pixel();
        if( !screen_pixel ) {
            return std::nullopt;
        }
        const window_dimensions dim = get_window_dimensions( map_preview_window_ );
        point local_pixel = *screen_pixel - dim.window_pos_pixel;
        if( allow_outside && dim.window_size_pixel.x > 0 && dim.window_size_pixel.y > 0 ) {
            local_pixel.x = std::clamp( local_pixel.x, 0, dim.window_size_pixel.x - 1 );
            local_pixel.y = std::clamp( local_pixel.y, 0, dim.window_size_pixel.y - 1 );
        }
        return map_preview_pixel_to_map( map_preview_window_, local_pixel,
                                         *independent_center_, independent_draw_scale_ );
    }
#endif

    const std::optional<tripoint_bub_ms> world = context.get_coordinates(
            g->w_terrain, g->ter_view_p.raw().xy(), true );
    return world && world->z() == viewer.pos_bub().z() ? world : std::nullopt;
}

tripoint_bub_ms ui_world_viewport::map_camera_center( const Character &viewer ) const
{
    if( independent_center_ ) {
        return *independent_center_;
    }
    return viewer.pos_bub() + viewer.view_offset;
}

void ui_world_viewport::center_map_on( Character &viewer,
                                       const tripoint_bub_ms &target )
{
    if( independent_center_ ) {
        independent_center_ = target;
        refresh_map_preview_registration();
        return;
    }
    viewer.view_offset = target - viewer.pos_bub();
    g->normalize_map_camera();
    g->invalidate_main_ui_adaptor();
}

void ui_world_viewport::center_map_on_viewer( Character &viewer )
{
    if( independent_center_ ) {
        independent_center_ = viewer.pos_bub();
        refresh_map_preview_registration();
        return;
    }
    viewer.view_offset = tripoint_rel_ms::zero;
    g->normalize_map_camera();
    g->invalidate_main_ui_adaptor();
}

void ui_world_viewport::move_map_camera( Character &viewer,
        const tripoint_rel_ms &delta )
{
    if( independent_center_ ) {
        *independent_center_ += delta;
        refresh_map_preview_registration();
        return;
    }
    viewer.view_offset += delta;
    g->normalize_map_camera();
    g->invalidate_main_ui_adaptor();
}

void ui_world_viewport::zoom_map_camera( const int direction, input_context &context,
        Character &viewer, const std::optional<tripoint_bub_ms> &anchor )
{
    if( independent_center_ ) {
        const int old_zoom = independent_draw_scale_;
        int next = old_zoom;
        if( !map_config_.draw_scale_steps.empty() ) {
            if( direction > 0 ) {
                const auto it = std::upper_bound( map_config_.draw_scale_steps.begin(),
                                                  map_config_.draw_scale_steps.end(), old_zoom );
                if( it != map_config_.draw_scale_steps.end() ) {
                    next = *it;
                }
            } else {
                auto it = std::lower_bound( map_config_.draw_scale_steps.begin(),
                                            map_config_.draw_scale_steps.end(), old_zoom );
                if( it == map_config_.draw_scale_steps.end() || *it >= old_zoom ) {
                    if( it != map_config_.draw_scale_steps.begin() ) {
                        --it;
                        next = *it;
                    }
                } else {
                    next = *it;
                }
            }
        } else if( direction > 0 ) {
            if( old_zoom > map_config_.maximum_draw_scale / map_config_.zoom_factor ) {
                next = map_config_.maximum_draw_scale;
            } else {
                next = old_zoom * map_config_.zoom_factor;
            }
        } else {
            next = old_zoom / map_config_.zoom_factor;
        }
        next = std::clamp( next, map_config_.minimum_draw_scale,
                           map_config_.maximum_draw_scale );
        if( next == old_zoom ) {
            return;
        }

        independent_draw_scale_ = next;
        if( anchor && map_config_.cursor_anchored_zoom ) {
            const std::optional<tripoint_bub_ms> after = map_position(
                        context, viewer, hovered_, false );
            if( after ) {
                *independent_center_ += *anchor - *after;
            }
        }
        refresh_map_preview_registration();
        return;
    }

    const int old_zoom = g->get_zoom();
    const int next = std::clamp( direction > 0 ? old_zoom * 2 : old_zoom / 2,
                                 MINIMUM_TILESET_ZOOM, MAXIMUM_TILESET_ZOOM );
    if( next == old_zoom ) {
        return;
    }

    g->set_zoom( next );
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
                if( independent_center_ ) {
                    *independent_center_ += *map_pan_anchor_ - *result.world_position;
                    refresh_map_preview_registration();
                } else {
                    viewer.view_offset += *map_pan_anchor_ - *result.world_position;
                    g->normalize_map_camera();
                    g->invalidate_main_ui_adaptor();
                }
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
    return map_draw_scale() * 100 / ui_world_viewport_default_draw_scale;
}

int ui_world_viewport::map_draw_scale() const
{
    return independent_center_ ? independent_draw_scale_ : g->get_zoom();
}

void ui_world_viewport::draw_map_marker( const tripoint_bub_ms &position,
        const std::string &symbol, const nc_color &color ) const
{
#if defined(TILES)
    if( has_map_preview() ) {
        if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
            tiles->init_draw_ui_marker( position, symbol, color.to_color_pair_index() );
            return;
        }
    }
#endif
    g->draw_ui_marker( position, symbol, color );
}

void ui_world_viewport::draw_map_highlight( const tripoint_bub_ms &position ) const
{
#if defined(TILES)
    if( has_map_preview() ) {
        if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
            tiles->init_draw_highlight( position );
            return;
        }
    }
#endif
    g->draw_highlight( position );
}

void ui_world_viewport::draw_map_cursor( const tripoint_bub_ms &position ) const
{
#if defined(TILES)
    if( has_map_preview() ) {
        if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
            tiles->init_draw_cursor( position );
            return;
        }
    }
#endif
    g->draw_cursor_unobscuring( position );
}

void ui_world_viewport::draw_map_terrain_override( const tripoint_bub_ms &position,
        const ter_id &id ) const
{
#if defined(TILES)
    if( has_map_preview() ) {
        if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
            tiles->init_draw_terrain_override( position, id );
            return;
        }
    }
#endif
    g->draw_terrain_override( position, id );
}

void ui_world_viewport::draw_map_furniture_override( const tripoint_bub_ms &position,
        const furn_id &id ) const
{
#if defined(TILES)
    if( has_map_preview() ) {
        if( const std::shared_ptr<cata_tiles> tiles = active_preview_tiles() ) {
            tiles->init_draw_furniture_override( position, id );
            return;
        }
    }
#endif
    g->draw_furniture_override( position, id );
}
