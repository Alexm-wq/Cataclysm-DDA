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
#if defined(TILES)
            clear_ui_pixel_icon_button( this );
#endif
            overlay_.close();
            action_.reset();
            icon_.clear();
            pos_ = point::zero;
            size_ = point::zero;
#if defined(TILES)
            pixel_pos_ = point::zero;
            pixel_size_ = point::zero;
            pixel_mode_ = false;
#endif
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

#if defined(TILES)
        /**
         * Opt-in exact pixel rendering for tiny SDL HUD controls. Pixel geometry
         * is screen-relative and is intentionally independent of terminal-cell
         * aspect ratio. Normal menus continue to use configure().
         */
        void configure_pixel( const catacurses::window &parent, point pixel_pos, point pixel_size,
                              ui_action_entry action, std::string icon,
                              const ui_icon_button_style &style = ui_icon_button_style() ) {
            clear_ui_pixel_icon_button( this );
            overlay_.close();
            if( !parent || pixel_size.x < 3 || pixel_size.y < 3 || icon.empty() ) {
                close();
                return;
            }

            const window_dimensions screen_dim = get_window_dimensions( catacurses::stdscr );
            const int cell_w = std::max( 1, screen_dim.scaled_font_size.x );
            const int cell_h = std::max( 1, screen_dim.scaled_font_size.y );
            const point pixel_max = pixel_pos + pixel_size - point( 1, 1 );

            pixel_pos_ = pixel_pos;
            pixel_size_ = pixel_size;
            pos_ = point( pixel_pos.x / cell_w, pixel_pos.y / cell_h );
            size_ = point( std::max( 1, pixel_max.x / cell_w - pos_.x + 1 ),
                           std::max( 1, pixel_max.y / cell_h - pos_.y + 1 ) );
            action_ = std::move( action );
            icon_ = std::move( icon );
            style_ = style;
            compact_ = false;
            pixel_mode_ = true;
        }
#endif

        bool is_configured() const {
#if defined(TILES)
            if( pixel_mode_ ) {
                return action_.has_value() && pixel_size_.x >= 3 && pixel_size_.y >= 3;
            }
#endif
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

#if defined(TILES)
        bool contains_pixel( const point &screen_pixel ) const {
            if( !pixel_mode_ || !is_configured() ) {
                return false;
            }
            return inclusive_rectangle<point>( pixel_pos_,
                                                pixel_pos_ + pixel_size_ - point( 1, 1 ) ).contains(
                       screen_pixel );
        }

        void update_hover_pixel( const std::optional<point> &screen_pixel ) {
            hovered_ = screen_pixel && contains_pixel( *screen_pixel );
        }

        ui_action_result handle_pixel_input( const std::string &action,
                                             const std::optional<point> &screen_pixel ) {
            if( !pixel_mode_ || !is_configured() ) {
                return {};
            }
            if( action == "MOUSE_MOVE" ) {
                update_hover_pixel( screen_pixel );
                return { hovered_ ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action != "SELECT" && action != "CONFIRM" ) {
                return {};
            }
            if( action == "SELECT" && ( !screen_pixel || !contains_pixel( *screen_pixel ) ) ) {
                return {};
            }
            return { action_->enabled ? ui_action_result_type::activated :
                     ui_action_result_type::disabled, *action_ };
        }
#endif

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
#if defined(TILES)
                clear_ui_pixel_icon_button( this );
#endif
                overlay_.close();
                return;
            }
#if defined(TILES)
            if( pixel_mode_ ) {
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

                ui_pixel_icon_button_overlay render;
                render.owner = this;
                render.pos_pixels = pixel_pos_;
                render.size_pixels = pixel_size_;
                render.border_color_pair = border.to_color_pair_index();
                render.fill_color_pair = fill.to_color_pair_index();
                render.icon_color_pair = icon_color.to_color_pair_index();
                render.icon = icon_;
                set_ui_pixel_icon_button( render );
                return;
            }
#endif
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
#if defined(TILES)
            clear_ui_pixel_icon_button( this );
            pixel_mode_ = false;
            pixel_pos_ = point::zero;
            pixel_size_ = point::zero;
#endif
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
#if defined(TILES)
        point pixel_pos_ = point::zero;
        point pixel_size_ = point::zero;
        bool pixel_mode_ = false;
#endif
        bool hovered_ = false;
        bool compact_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_ICON_BUTTON_H
