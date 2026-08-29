#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
#define CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H

#include <optional>
#include <string>

#include "../../cuboid_rectangle.h"
#include "../../point.h"

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

    bool consumed() const {
        return type != ui_world_viewport_action_type::ignored;
    }
};

/**
 * Screen-space input controller for map-backed workspaces.
 *
 * The helper owns clipping, hover, pointer capture, click routing and wheel
 * semantics.  Callers own screen placement, screen-to-world conversion, camera
 * movement and feature-specific actions.
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
                return { ui_world_viewport_action_type::pan_end, position };
            }

            if( action == "CAMERA_PAN_START" ) {
                if( !contains( position ) ) {
                    return {};
                }
                captured_ = true;
                capture_anchor_ = position;
                hovered_ = position;
                return { ui_world_viewport_action_type::pan_start, position };
            }

            if( captured_ ) {
                if( action == "MOUSE_MOVE" || action == "CLICK_AND_DRAG" ) {
                    hovered_ = position;
                    capture_anchor_ = position;
                    return { ui_world_viewport_action_type::pan_move, position };
                }
                return { ui_world_viewport_action_type::handled, position };
            }

            if( action == "MOUSE_MOVE" ) {
                hovered_ = contains( position ) ? position : std::nullopt;
                return { ui_world_viewport_action_type::hover, hovered_ };
            }
            if( !contains( position ) ) {
                return {};
            }
            if( action == "SELECT" ) {
                return { ui_world_viewport_action_type::select, position };
            }
            if( action == "SEC_SELECT" ) {
                return { ui_world_viewport_action_type::context, position };
            }
            if( action == "SCROLL_UP" ) {
                return { ui_world_viewport_action_type::zoom_in, position };
            }
            if( action == "SCROLL_DOWN" ) {
                return { ui_world_viewport_action_type::zoom_out, position };
            }
            return {};
        }

    private:
        inclusive_rectangle<point> bounds_;
        std::optional<point> hovered_;
        std::optional<point> capture_anchor_;
        bool configured_ = false;
        bool captured_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_WORLD_VIEWPORT_H
