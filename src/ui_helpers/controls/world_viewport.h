#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
#define CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "../../color.h"
#include "../../coordinates.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
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
inline constexpr int ui_world_viewport_default_draw_scale = 16;
inline constexpr int ui_world_viewport_minimum_draw_scale = 4;
inline constexpr int ui_world_viewport_maximum_draw_scale = 64;

struct ui_world_viewport_map_config {
    int initial_draw_scale = ui_world_viewport_default_draw_scale;
    int minimum_draw_scale = ui_world_viewport_minimum_draw_scale;
    int maximum_draw_scale = ui_world_viewport_maximum_draw_scale;
    int zoom_factor = 2;
    std::vector<int> draw_scale_steps;
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
                hovered_ = position;
                return { ui_world_viewport_action_type::zoom_in, position, std::nullopt };
            }
            if( action == "SCROLL_DOWN" ) {
                hovered_ = position;
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
        void attach_map_preview( const catacurses::window &window,
                                 bool preserve_visual_center = false );
        void detach_map_preview();
        bool has_map_preview() const;
        bool has_animated_weather() const;
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
        void draw_map_progress_bar( const tripoint_bub_ms &position, float progress ) const;
        void draw_map_highlight( const tripoint_bub_ms &position ) const;
        void draw_map_removal_overlay( const tripoint_bub_ms &position ) const;
        void draw_map_plan_overlay( const tripoint_bub_ms &position ) const;
        void draw_map_cursor( const tripoint_bub_ms &position ) const;
        void draw_map_terrain_override( const tripoint_bub_ms &position, const ter_id &id ) const;
        void draw_map_furniture_override( const tripoint_bub_ms &position, const furn_id &id ) const;

    private:
        void refresh_map_preview_registration() const;
        void prepare_live_map_state() const;
        void prepare_map_weather() const;

        inclusive_rectangle<point> bounds_;
        std::optional<point> hovered_;
        std::optional<point> capture_anchor_;
        std::optional<tripoint_bub_ms> map_pan_anchor_;
        bool configured_ = false;
        bool captured_ = false;

        ui_world_viewport_map_config map_config_;
        std::optional<tripoint_bub_ms> independent_center_;
        int independent_draw_scale_ = ui_world_viewport_default_draw_scale;
        catacurses::window map_preview_window_;
        mutable std::optional<std::int64_t> last_prepared_turn_;
        mutable std::optional<int> last_prepared_z_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
