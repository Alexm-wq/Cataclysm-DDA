#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
#define CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H

#include <optional>
#include <string>

#include "../../coordinates.h"
#include "../../cuboid_rectangle.h"
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

/**
 * Screen-space input controller for map-backed workspaces.
 *
 * The helper owns clipping, hover, pointer capture, click routing and wheel
 * semantics.  Its main-map adapter additionally owns screen-to-world
 * projection, camera panning and capped cursor-anchored zoom.  Callers own
 * screen placement and feature-specific actions at returned world positions.
 */
class ui_world_viewport
{
    public:
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

        /** Route an event through the normal terrain viewport and apply camera
         * pan/zoom behavior.  Selection/context/hover are returned for feature
         * semantics; camera changes are completed inside the helper. */
        ui_world_viewport_action handle_map_input( const std::string &action,
                input_context &context, Character &viewer,
                const std::optional<point> &position );

        std::optional<tripoint_bub_ms> map_position( const input_context &context,
                const Character &viewer, const std::optional<point> &position,
                bool allow_outside = false ) const;
        void center_map_on( Character &viewer, const tripoint_bub_ms &target ) const;
        void center_map_on_viewer( Character &viewer ) const;
        void move_map_camera( Character &viewer, const tripoint_rel_ms &delta ) const;
        void zoom_map_camera( int direction, input_context &context, Character &viewer,
                              const std::optional<tripoint_bub_ms> &anchor = std::nullopt ) const;
        void cancel_map_capture();
        int map_zoom_percent() const;

    private:
        inclusive_rectangle<point> bounds_;
        std::optional<point> hovered_;
        std::optional<point> capture_anchor_;
        std::optional<tripoint_bub_ms> map_pan_anchor_;
        bool configured_ = false;
        bool captured_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
