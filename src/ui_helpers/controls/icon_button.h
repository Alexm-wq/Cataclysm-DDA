#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_ICON_BUTTON_H
#define CATA_SRC_UI_HELPERS_CONTROLS_ICON_BUTTON_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../output.h"
#include "../../point.h"
#if defined(TILES)
#include "../../sdltiles.h"
#endif
#include "../models/action_entry.h"
#include "../primitive/overlay.h"

struct ui_icon_button_style {
    nc_color border = c_light_gray;
    nc_color fill = i_dark_gray;
    nc_color icon = c_light_gray;
    nc_color hover_border = c_white;
    nc_color hover_fill = i_light_gray;
    nc_color hover_icon = c_white;
    nc_color selected_border = c_light_cyan;
    nc_color selected_fill = i_dark_gray;
    nc_color selected_icon = c_light_cyan;
    nc_color disabled_border = c_dark_gray;
    nc_color disabled_fill = i_dark_gray;
    nc_color disabled_icon = c_dark_gray;
};

/**
 * Bordered icon/tile button with helper-owned rendering and interaction.
 * The caller owns placement.  square_size_for_icon() converts a desired icon
 * footprint in pixels into a visually square cell rectangle using the active
 * SDL-scaled font dimensions, so 16x16 bitmap icons can be added later without
 * changing screen layout code.
 */
class ui_icon_button
{
    public:
        static point square_size_for_icon( const catacurses::window &parent,
                                           const point &icon_pixels,
                                           const int border_cells = 1 ) {
#if defined(TILES)
            const window_dimensions dims = get_window_dimensions( parent );
            const int cell_w = std::max( 1, dims.scaled_font_size.x );
            const int cell_h = std::max( 1, dims.scaled_font_size.y );
            const int border = std::max( 1, border_cells );
            const auto ceil_div = []( const int value, const int divisor ) {
                return ( std::max( 1, value ) + divisor - 1 ) / divisor;
            };
            int cells_w = ceil_div( icon_pixels.x, cell_w ) + border * 2;
            int cells_h = ceil_div( icon_pixels.y, cell_h ) + border * 2;
            const int side_px = std::max( cells_w * cell_w, cells_h * cell_h );
            cells_w = std::max( cells_w, ceil_div( side_px, cell_w ) );
            cells_h = std::max( cells_h, ceil_div( side_px, cell_h ) );
            return point( std::max( 3, cells_w ), std::max( 3, cells_h ) );
#else
            ( void ) parent;
            ( void ) icon_pixels;
            ( void ) border_cells;
            return point( 3, 3 );
#endif
        }

        void close() {
            overlay_.close();
            action_.reset();
            icon_.clear();
            pos_ = point::zero;
            size_ = point::zero;
            hovered_ = false;
            compact_ = false;
        }

        void configure( const catacurses::window &parent, point pos, point size,
                        ui_action_entry action, std::string icon,
                        const ui_icon_button_style &style = ui_icon_button_style() ) {
            configure_impl( parent, pos, size, std::move( action ), std::move( icon ),
                            style, false );
        }

        /**
         * Opt-in compact rendering for very small HUD controls.
         *
         * Unlike configure(), this permits a two-cell-wide button and allows
         * content wider than the normal interior to use the border row.  That
         * makes tiny attached launchers and short status strings possible
         * without weakening the normal control contract for existing menus.
         */
        void configure_compact( const catacurses::window &parent, point pos, point size,
                                ui_action_entry action, std::string icon,
                                const ui_icon_button_style &style = ui_icon_button_style() ) {
            configure_impl( parent, pos, size, std::move( action ), std::move( icon ),
                            style, true );
        }

        bool is_configured() const {
            const point minimum = compact_ ? point( 2, 3 ) : point( 3, 3 );
            return action_.has_value() && size_.x >= minimum.x && size_.y >= minimum.y;
        }

        std::optional<inclusive_rectangle<point>> bounds() const {
            if( !is_configured() ) {
                return std::nullopt;
            }
            return inclusive_rectangle<point>( pos_, pos_ + size_ - point( 1, 1 ) );
        }

        bool contains( const point &parent_pos ) const {
            const auto area = bounds();
            return area && area->contains( parent_pos );
        }

        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos && contains( *parent_pos );
        }

        ui_action_result handle_input( const std::string &action,
                                       const std::optional<point> &parent_pos ) {
            if( !is_configured() ) {
                return {};
            }
            if( action == "MOUSE_MOVE" ) {
                update_hover( parent_pos );
                return { hovered_ ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action != "SELECT" && action != "CONFIRM" ) {
                return {};
            }
            if( action == "SELECT" && ( !parent_pos || !contains( *parent_pos ) ) ) {
                return {};
            }
            return { action_->enabled ? ui_action_result_type::activated :
                     ui_action_result_type::disabled, *action_ };
        }

        void draw( const catacurses::window &parent ) {
            if( !is_configured() ) {
                overlay_.close();
                return;
            }
            overlay_.configure( parent, pos_, size_.x, size_.y );
            catacurses::window &window = overlay_.begin_draw( parent );
            if( !window ) {
                return;
            }

            nc_color border = style_.border;
            nc_color fill = style_.fill;
            nc_color icon_color = style_.icon;
            if( !action_->enabled ) {
                border = style_.disabled_border;
                fill = style_.disabled_fill;
                icon_color = style_.disabled_icon;
            } else if( hovered_ ) {
                border = style_.hover_border;
                fill = style_.hover_fill;
                icon_color = style_.hover_icon;
            } else if( action_->selected ) {
                border = style_.selected_border;
                fill = style_.selected_fill;
                icon_color = style_.selected_icon;
            }

            draw_border( window, border );
            const int interior_width = std::max( 0, size_.x - 2 );
            if( interior_width > 0 ) {
                const std::string fill_row( interior_width, ' ' );
                for( int y = 1; y < size_.y - 1; ++y ) {
                    trim_and_print( window, point( 1, y ), interior_width, fill, fill_row );
                }
            }

            const int icon_w = std::max( 1, utf8_width( icon_ ) );
            int icon_x = std::max( 1, ( size_.x - icon_w ) / 2 );
            int icon_width = std::max( 1, size_.x - icon_x - 1 );
            if( compact_ && icon_w > interior_width ) {
                icon_x = std::max( 0, ( size_.x - icon_w ) / 2 );
                icon_width = std::max( 1, size_.x - icon_x );
            }
            const int icon_y = std::clamp( size_.y / 2, 1, size_.y - 2 );
            trim_and_print( window, point( icon_x, icon_y ),
                            icon_width, icon_color, icon_ );
            overlay_.refresh();
        }

    private:
        void configure_impl( const catacurses::window &parent, point pos, point size,
                             ui_action_entry action, std::string icon,
                             const ui_icon_button_style &style, const bool compact ) {
            const point minimum = compact ? point( 2, 3 ) : point( 3, 3 );
            const int parent_w = getmaxx( parent );
            const int parent_h = getmaxy( parent );
            if( parent_w < minimum.x || parent_h < minimum.y ||
                size.x < minimum.x || size.y < minimum.y || icon.empty() ) {
                close();
                return;
            }
            size.x = std::min( size.x, parent_w );
            size.y = std::min( size.y, parent_h );
            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_w - size.x ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_h - size.y ) );
            pos_ = pos;
            size_ = size;
            action_ = std::move( action );
            icon_ = std::move( icon );
            style_ = style;
            compact_ = compact;
            overlay_.configure( parent, pos_, size_.x, size_.y );
        }

        ui_overlay overlay_;
        std::optional<ui_action_entry> action_;
        std::string icon_;
        ui_icon_button_style style_;
        point pos_ = point::zero;
        point size_ = point::zero;
        bool hovered_ = false;
        bool compact_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_ICON_BUTTON_H
