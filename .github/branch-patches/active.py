from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


header = r'''#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
#define CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H

#include <optional>
#include <string>

#include "../../color.h"
#include "../../coordinates.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../game_constants.h"
#include "../../mapdata.h"
#include "../../point.h"

class Character;
class input_context;

enum class ui_world_viewport_action_type : int {
    ignored,
    handled,
    hover,
    select,
    context,
    pan_start,
    pan_move,
    pan_end,
    zoom_in,
    zoom_out
};

struct ui_world_viewport_action {
    ui_world_viewport_action_type type = ui_world_viewport_action_type::ignored;
    std::optional<point> position;
    std::optional<tripoint_bub_ms> world_position;

    bool consumed() const {
        return type != ui_world_viewport_action_type::ignored;
    }
};

/** Camera policy for an auxiliary world viewport.
 *
 * Every scale limit is caller-overridable so screens can choose an appropriate
 * zoom range without duplicating the camera/input implementation.  Draw scales
 * use the same units as cata_tiles::set_draw_scale().
 */
struct ui_world_viewport_map_config {
    int initial_draw_scale = DEFAULT_TILESET_ZOOM;
    int minimum_draw_scale = MINIMUM_TILESET_ZOOM;
    int maximum_draw_scale = MAXIMUM_TILESET_ZOOM;
    int zoom_factor = 2;
    bool cursor_anchored_zoom = true;
};

/**
 * Screen-space input controller for map-backed workspaces.
 *
 * The helper owns clipping, hover, pointer capture, click routing and wheel
 * semantics.  It supports both the legacy main-map camera and a true auxiliary
 * map viewport with independent center/zoom.  Callers own screen placement and
 * feature-specific actions at returned world positions.
 */
class ui_world_viewport
{
    public:
        ui_world_viewport() = default;
        ~ui_world_viewport();

        ui_world_viewport( const ui_world_viewport & ) = delete;
        ui_world_viewport &operator=( const ui_world_viewport & ) = delete;

        void configure( const inclusive_rectangle<point> &bounds ) {
            bounds_ = bounds;
            configured_ = bounds.p_max.x >= bounds.p_min.x && bounds.p_max.y >= bounds.p_min.y;
            if( !configured_ ) {
                cancel_capture();
            }
        }

        void hide() {
            configured_ = false;
            hovered_.reset();
            cancel_capture();
        }

        bool contains( const std::optional<point> &position ) const {
            return configured_ && position && bounds_.contains( *position );
        }

        bool has_capture() const {
            return captured_;
        }

        std::optional<point> hovered_position() const {
            return hovered_;
        }

        void cancel_capture() {
            captured_ = false;
            capture_anchor_.reset();
        }

        ui_world_viewport_action handle_input( const std::string &action,
                                               const std::optional<point> &position ) {
            if( action == "CAMERA_PAN_END" ) {
                if( !captured_ ) {
                    return {};
                }
                cancel_capture();
                hovered_ = contains( position ) ? position : std::nullopt;
                return { ui_world_viewport_action_type::pan_end, position, std::nullopt };
            }

            if( action == "CAMERA_PAN_START" ) {
                if( !contains( position ) ) {
                    return {};
                }
                captured_ = true;
                capture_anchor_ = position;
                hovered_ = position;
                return { ui_world_viewport_action_type::pan_start, position, std::nullopt };
            }

            if( captured_ ) {
                if( action == "MOUSE_MOVE" || action == "CLICK_AND_DRAG" ) {
                    hovered_ = position;
                    capture_anchor_ = position;
                    return { ui_world_viewport_action_type::pan_move, position, std::nullopt };
                }
                return { ui_world_viewport_action_type::handled, position, std::nullopt };
            }

            if( action == "MOUSE_MOVE" ) {
                hovered_ = contains( position ) ? position : std::nullopt;
                return { ui_world_viewport_action_type::hover, hovered_, std::nullopt };
            }
            if( !contains( position ) ) {
                return {};
            }
            if( action == "SELECT" ) {
                return { ui_world_viewport_action_type::select, position, std::nullopt };
            }
            if( action == "SEC_SELECT" ) {
                return { ui_world_viewport_action_type::context, position, std::nullopt };
            }
            if( action == "SCROLL_UP" ) {
                return { ui_world_viewport_action_type::zoom_in, position, std::nullopt };
            }
            if( action == "SCROLL_DOWN" ) {
                return { ui_world_viewport_action_type::zoom_out, position, std::nullopt };
            }
            return {};
        }

        /** Configure a camera that is independent from Character::view_offset
         * and the normal gameplay zoom.  Screens may override every zoom policy
         * field through @p config. */
        void configure_map_camera( const tripoint_bub_ms &center,
                                   const ui_world_viewport_map_config &config = {} );

        /** Bind/rebind the auxiliary renderer to a screen-owned window.  Camera
         * state survives reattachment so a resize does not reset pan/zoom. */
        void attach_map_preview( const catacurses::window &window );
        void detach_map_preview();
        bool has_map_preview() const;
        void draw_map_preview() const;

        /** Clear preview-local transient overlays before the caller describes
         * the next frame. */
        void begin_map_overlay_frame() const;

        /** Route an event through the active map backend and apply camera
         * pan/zoom behavior.  Selection/context/hover are returned for feature
         * semantics; camera changes are completed inside the helper. */
        ui_world_viewport_action handle_map_input( const std::string &action,
                input_context &context, Character &viewer,
                const std::optional<point> &position );

        std::optional<tripoint_bub_ms> map_position( const input_context &context,
                const Character &viewer, const std::optional<point> &position,
                bool allow_outside = false ) const;
        tripoint_bub_ms map_camera_center( const Character &viewer ) const;
        void center_map_on( Character &viewer, const tripoint_bub_ms &target );
        void center_map_on_viewer( Character &viewer );
        void move_map_camera( Character &viewer, const tripoint_rel_ms &delta );
        void zoom_map_camera( int direction, input_context &context, Character &viewer,
                              const std::optional<tripoint_bub_ms> &anchor = std::nullopt );
        void cancel_map_capture();
        int map_zoom_percent() const;
        int map_draw_scale() const;

        /** Preview-aware world-space annotations.  With an auxiliary viewport
         * these are registered on that viewport's tile renderer only; otherwise
         * they preserve the legacy main-map behavior. */
        void draw_map_marker( const tripoint_bub_ms &position, const std::string &symbol,
                              const nc_color &color ) const;
        void draw_map_highlight( const tripoint_bub_ms &position ) const;
        void draw_map_cursor( const tripoint_bub_ms &position ) const;
        void draw_map_terrain_override( const tripoint_bub_ms &position, const ter_id &id ) const;
        void draw_map_furniture_override( const tripoint_bub_ms &position, const furn_id &id ) const;

    private:
        void refresh_map_preview_registration() const;

        inclusive_rectangle<point> bounds_;
        std::optional<point> hovered_;
        std::optional<point> capture_anchor_;
        std::optional<tripoint_bub_ms> map_pan_anchor_;
        bool configured_ = false;
        bool captured_ = false;

        ui_world_viewport_map_config map_config_;
        std::optional<tripoint_bub_ms> independent_center_;
        int independent_draw_scale_ = DEFAULT_TILESET_ZOOM;
        catacurses::window map_preview_window_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
'''

cpp = r'''#include "world_viewport.h"

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
    independent_center_ = center;
    independent_draw_scale_ = map_config_.initial_draw_scale;
    refresh_map_preview_registration();
}

void ui_world_viewport::attach_map_preview( const catacurses::window &window )
{
#if defined(TILES)
    if( map_preview_window_ ) {
        clear_map_preview_window();
    }
#endif
    map_preview_window_ = window;
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
        if( direction > 0 ) {
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
    return map_draw_scale() * 100 / DEFAULT_TILESET_ZOOM;
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
'''

Path("src/ui_helpers/controls/world_viewport.h").write_text(header)
Path("src/ui_helpers/controls/world_viewport.cpp").write_text(cpp)

path = Path("src/construction_ui.cpp")
s = path.read_text()

s = replace_once(
    s,
    '''        catacurses::window inspector_window;\n        catacurses::window footer;\n''',
    '''        catacurses::window inspector_window;\n        catacurses::window footer;\n#if defined(TILES)\n        catacurses::window viewport_window;\n#endif\n''',
    "viewport window member",
)

s = replace_once(
    s,
    '''construction_workspace::construction_workspace() :\n    you( get_avatar() ), here( get_map() ), original_zoom( g->get_zoom() )\n{\n    search = uistate.construction_filter;\n''',
    '''construction_workspace::construction_workspace() :\n    you( get_avatar() ), here( get_map() ), original_zoom( g->get_zoom() )\n{\n#if defined(TILES)\n    // The Construction map is a real auxiliary viewport.  Its camera and zoom\n    // are owned by ui_world_viewport and never alter the gameplay camera.\n    viewport.configure_map_camera( you.pos_bub() );\n#endif\n    search = uistate.construction_filter;\n''',
    "configure independent camera",
)

s = replace_once(
    s,
    '''    const int viewport_left = palette_width;\n    const int viewport_right = std::max( viewport_left, width - inspector_width - 1 );\n    viewport.configure( inclusive_rectangle<point>( point( viewport_left, content_top ),\n            point( viewport_right, content_bottom ) ) );\n''',
    '''    const int viewport_left = palette_width;\n    const int viewport_right = std::max( viewport_left, width - inspector_width - 1 );\n    viewport.configure( inclusive_rectangle<point>( point( viewport_left, content_top ),\n            point( viewport_right, content_bottom ) ) );\n#if defined(TILES)\n    const int viewport_width = std::max( 1, viewport_right - viewport_left + 1 );\n    viewport_window = catacurses::newwin( content_height, viewport_width,\n                                         point( viewport_left, content_top ) );\n    viewport.attach_map_preview( viewport_window );\n#endif\n''',
    "attach auxiliary viewport",
)

s = replace_once(
    s,
    '''#if defined(TILES)\n        g->draw_highlight( position );\n#else\n        here.drawsq( g->w_terrain, position,\n                     drawsq_params().highlight( true ).show_items( true )\n                     .center( you.pos_bub() + you.view_offset ) );\n#endif\n        viewport.draw_map_marker( position, symbol, color );\n''',
    '''#if defined(TILES)\n        viewport.draw_map_highlight( position );\n#else\n        here.drawsq( g->w_terrain, position,\n                     drawsq_params().highlight( true ).show_items( true )\n                     .center( you.pos_bub() + you.view_offset ) );\n#endif\n        viewport.draw_map_marker( position, symbol, color );\n''',
    "preview-local highlight",
)

s = replace_once(
    s,
    '''        if( con->post_is_furniture ) {\n            g->draw_furniture_override( *target, furn_str_id( con->post_terrain ) );\n        } else {\n            g->draw_terrain_override( *target, ter_str_id( con->post_terrain ) );\n        }\n''',
    '''        if( con->post_is_furniture ) {\n            viewport.draw_map_furniture_override( *target, furn_str_id( con->post_terrain ) );\n        } else {\n            viewport.draw_map_terrain_override( *target, ter_str_id( con->post_terrain ) );\n        }\n''',
    "preview-local ghost",
)

s = replace_once(
    s,
    '''    if( selected_target ) {\n        g->draw_cursor_unobscuring( *selected_target );\n    }\n}\n\nvoid construction_workspace::draw( ui_adaptor &ui )\n{\n    draw_header();\n''',
    '''    if( selected_target ) {\n        viewport.draw_map_cursor( *selected_target );\n    }\n}\n\nvoid construction_workspace::draw( ui_adaptor &ui )\n{\n#if defined(TILES)\n    viewport.begin_map_overlay_frame();\n    draw_world_overlay();\n    // Draw the live map first.  Panels/tooltips/dropdowns then composite over\n    // it, and the next frame repaints anything they previously covered.\n    viewport.draw_map_preview();\n#endif\n    draw_header();\n''',
    "draw auxiliary viewport",
)

s = s.replace(
    '''            selected_target = you.pos_bub() + you.view_offset;\n''',
    '''            selected_target = viewport.map_camera_center( you );\n'''
)
if s.count('selected_target = viewport.map_camera_center( you );') != 2:
    raise SystemExit("keyboard camera selection: expected 2 replacements")

s = replace_once(
    s,
    '''    if( action == "TIMEOUT" ) {\n        blink = !blink;\n        g->invalidate_main_ui_adaptor();\n        return true;\n    }\n''',
    '''    if( action == "TIMEOUT" ) {\n        blink = !blink;\n#if defined(TILES)\n        ui.invalidate_ui();\n#else\n        g->invalidate_main_ui_adaptor();\n#endif\n        return true;\n    }\n''',
    "timeout invalidation",
)

s = replace_once(
    s,
    '''        on_out_of_scope restore_ui( [this]() {\n            viewport.cancel_map_capture();\n#if defined(TILES)\n            clear_ui_tile_previews();\n            tilecontext->set_disable_occlusion( false );\n#endif\n            g->invalidate_main_ui_adaptor();\n        } );\n#if defined(TILES)\n        tilecontext->set_disable_occlusion( true );\n#endif\n        g->invalidate_main_ui_adaptor();\n''',
    '''        on_out_of_scope restore_ui( [this]() {\n            viewport.cancel_map_capture();\n#if defined(TILES)\n            viewport.detach_map_preview();\n            clear_ui_tile_previews();\n            if( tilecontext ) {\n                tilecontext->set_disable_occlusion( false );\n            }\n            if( closetilecontext ) {\n                closetilecontext->set_disable_occlusion( false );\n            }\n#endif\n            g->invalidate_main_ui_adaptor();\n        } );\n#if defined(TILES)\n        if( tilecontext ) {\n            tilecontext->set_disable_occlusion( true );\n        }\n        if( closetilecontext ) {\n            closetilecontext->set_disable_occlusion( true );\n        }\n#else\n        g->invalidate_main_ui_adaptor();\n#endif\n''',
    "preview cleanup and lower-map isolation",
)

s = replace_once(
    s,
    '''        ui_adaptor ui;\n''',
    '''#if defined(TILES)\n        // Construction is opaque and supplies its own map viewport.  Prevent\n        // gameplay HUD/buttons below it from redrawing through the workspace.\n        ui_adaptor ui( ui_adaptor::disable_uis_below{} );\n#else\n        ui_adaptor ui;\n#endif\n''',
    "opaque construction adaptor",
)

s = replace_once(
    s,
    '''        shared_ptr_fast<game::draw_callback_t> overlay =\n        make_shared_fast<game::draw_callback_t>( [this]() {\n            draw_world_overlay();\n        } );\n        g->add_draw_callback( overlay );\n\n        while( !exit_requested ) {\n            g->invalidate_main_ui_adaptor();\n            ui_manager::redraw();\n''',
    '''#if !defined(TILES)\n        shared_ptr_fast<game::draw_callback_t> overlay =\n        make_shared_fast<game::draw_callback_t>( [this]() {\n            draw_world_overlay();\n        } );\n        g->add_draw_callback( overlay );\n#endif\n\n        while( !exit_requested ) {\n#if !defined(TILES)\n            g->invalidate_main_ui_adaptor();\n#endif\n            ui_manager::redraw();\n''',
    "remove gameplay redraw dependency",
)

s = replace_once(
    s,
    '''        overlay.reset();\n        ui.reset();\n''',
    '''#if !defined(TILES)\n        overlay.reset();\n#endif\n        ui.reset();\n''',
    "conditional legacy overlay reset",
)

path.write_text(s)
Path("/tmp/branch_patch_commit_message").write_text(
    "Give construction an independent map viewport [skip ci]\n"
)
