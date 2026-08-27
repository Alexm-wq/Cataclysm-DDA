from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


icon_button = Path("src/ui_helpers/controls/icon_button.h")
if icon_button.exists():
    raise SystemExit("icon button helper already exists; refusing to overwrite")
icon_button.write_text(r'''#pragma once
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

/** Visual policy for a compact bordered icon/tile button. */
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
 * Compact icon/tile button rendered through a helper-owned overlay.
 *
 * Geometry remains caller-owned, but square_size_for_icon() derives a visually
 * square terminal-cell rectangle from a desired pixel icon size and the active
 * SDL font scaling.  That keeps toolbars ready for 16x16 (or other) bitmap icons
 * without hardcoding a particular terminal font aspect ratio into a screen.
 */
class ui_icon_button
{
    public:
        static point square_size_for_icon( const catacurses::window &parent,
                                           const point &icon_pixels,
                                           const int border_cells = 1 ) {
#if defined(TILES)
            const window_dimensions dims = get_window_dimensions( parent );
            const int cell_width = std::max( 1, dims.scaled_font_size.x );
            const int cell_height = std::max( 1, dims.scaled_font_size.y );
            const int border = std::max( 1, border_cells );
            const auto ceil_div = []( const int value, const int divisor ) {
                return ( std::max( 1, value ) + divisor - 1 ) / divisor;
            };

            int width_cells = ceil_div( icon_pixels.x, cell_width ) + border * 2;
            int height_cells = ceil_div( icon_pixels.y, cell_height ) + border * 2;
            const int target_side_pixels = std::max( width_cells * cell_width,
                                           height_cells * cell_height );
            width_cells = std::max( width_cells, ceil_div( target_side_pixels, cell_width ) );
            height_cells = std::max( height_cells, ceil_div( target_side_pixels, cell_height ) );
            return point( std::max( 3, width_cells ), std::max( 3, height_cells ) );
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
            width_ = 0;
            height_ = 0;
            hovered_ = false;
        }

        void configure( const catacurses::window &parent, point pos, const point &size,
                        ui_action_entry action, std::string icon,
                        const ui_icon_button_style &style = ui_icon_button_style() ) {
            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            if( parent_width < 3 || parent_height < 3 || size.x < 3 || size.y < 3 || icon.empty() ) {
                close();
                return;
            }

            width_ = std::min( size.x, parent_width );
            height_ = std::min( size.y, parent_height );
            if( width_ < 3 || height_ < 3 ) {
                close();
                return;
            }
            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_width - width_ ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height - height_ ) );
            pos_ = pos;
            action_ = std::move( action );
            icon_ = std::move( icon );
            style_ = style;
            overlay_.configure( parent, pos_, width_, height_ );
        }

        bool is_configured() const {
            return action_.has_value() && width_ >= 3 && height_ >= 3;
        }

        std::optional<inclusive_rectangle<point>> bounds() const {
            if( !is_configured() ) {
                return std::nullopt;
            }
            return inclusive_rectangle<point>( pos_,
                                                point( pos_.x + width_ - 1,
                                                       pos_.y + height_ - 1 ) );
        }

        bool contains( const point &parent_pos ) const {
            const std::optional<inclusive_rectangle<point>> area = bounds();
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
                return { hovered_ ? ui_action_result_type::handled :
                         ui_action_result_type::ignored, std::nullopt };
            }
            if( action != "SELECT" && action != "CONFIRM" ) {
                return {};
            }
            if( action == "SELECT" && ( !parent_pos || !contains( *parent_pos ) ) ) {
                return {};
            }
            if( !action_->enabled ) {
                return { ui_action_result_type::disabled, *action_ };
            }
            return { ui_action_result_type::activated, *action_ };
        }

        void draw( const catacurses::window &parent ) {
            if( !is_configured() ) {
                overlay_.close();
                return;
            }

            overlay_.configure( parent, pos_, width_, height_ );
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
            const std::string fill_row( std::max( 0, width_ - 2 ), ' ' );
            for( int y = 1; y < height_ - 1; ++y ) {
                trim_and_print( window, point( 1, y ), width_ - 2, fill, fill_row );
            }

            const int icon_width = std::max( 1, utf8_width( icon_ ) );
            const int icon_x = std::max( 1, ( width_ - icon_width ) / 2 );
            const int icon_y = std::clamp( height_ / 2, 1, height_ - 2 );
            trim_and_print( window, point( icon_x, icon_y ),
                            std::max( 1, width_ - icon_x - 1 ), icon_color, icon_ );
            overlay_.refresh();
        }

    private:
        ui_overlay overlay_;
        std::optional<ui_action_entry> action_;
        std::string icon_;
        ui_icon_button_style style_;
        point pos_ = point::zero;
        int width_ = 0;
        int height_ = 0;
        bool hovered_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_ICON_BUTTON_H
''', encoding="utf-8")

replace_once(
    "src/game.h",
    '#include "ui_helpers/controls/dropdown.h"\n',
    '#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/controls/icon_button.h"\n',
    "game icon helper include",
)
replace_once(
    "src/game.h",
    '''        ui_overlay safemode_corner_button_overlay; // NOLINT(cata-serialize)\n        ui_action_strip safemode_corner_button; // NOLINT(cata-serialize)\n''',
    '''        ui_icon_button safemode_corner_button; // NOLINT(cata-serialize)\n''',
    "game icon helper member",
)

replace_once(
    "src/game.cpp",
    '''static constexpr int safemode_corner_button_width = 5;\nstatic constexpr int safemode_corner_menu_width = 22;\nstatic constexpr int safemode_corner_menu_rows = 5;\n\nstatic point safemode_corner_button_pos( const catacurses::window &window )\n{\n    return point( std::max( 0, getmaxx( window ) - safemode_corner_button_width - 1 ),\n                  std::max( 0, getmaxy( window ) - 2 ) );\n}\n\nstatic inclusive_rectangle<point> safemode_corner_button_bounds( const catacurses::window &window )\n{\n    const point pos = safemode_corner_button_pos( window );\n    return inclusive_rectangle<point>( pos,\n                                       point( pos.x + safemode_corner_button_width - 1, pos.y ) );\n}\n''',
    '''static constexpr int safemode_corner_menu_width = 22;\nstatic constexpr int safemode_corner_menu_rows = 5;\nstatic const point safemode_corner_icon_pixels( 16, 16 );\n\nstatic point safemode_corner_button_size( const catacurses::window &window )\n{\n    return ui_icon_button::square_size_for_icon( window, safemode_corner_icon_pixels );\n}\n\nstatic point safemode_corner_button_pos( const catacurses::window &window )\n{\n    const point size = safemode_corner_button_size( window );\n    return point( std::max( 0, getmaxx( window ) - size.x - 1 ),\n                  std::max( 0, getmaxy( window ) - size.y - 1 ) );\n}\n\nstatic inclusive_rectangle<point> safemode_corner_button_bounds( const catacurses::window &window )\n{\n    const point pos = safemode_corner_button_pos( window );\n    const point size = safemode_corner_button_size( window );\n    return inclusive_rectangle<point>( pos,\n                                       point( pos.x + size.x - 1, pos.y + size.y - 1 ) );\n}\n\nstatic bool safemode_corner_button_fits( const catacurses::window &window )\n{\n    if( !window ) {\n        return false;\n    }\n    const point size = safemode_corner_button_size( window );\n    return getmaxx( window ) >= size.x + 2 && getmaxy( window ) >= size.y + 2;\n}\n''',
    "scaled safemode button geometry",
)

replace_once(
    "src/game.cpp",
    '''void game::configure_safemode_corner_menu()\n{\n    if( !w_pixel_minimap || getmaxx( w_pixel_minimap ) < safemode_corner_button_width + 3 ||\n        getmaxy( w_pixel_minimap ) < 3 ) {\n        safemode_corner_menu.close();\n        return;\n    }\n\n    const point button_pos = safemode_corner_button_pos( w_pixel_minimap );\n    const int available_left = std::max( 3, button_pos.x - 1 );\n    const int menu_width = std::min( safemode_corner_menu_width, available_left );\n    const int menu_height = safemode_corner_menu_rows + 2;\n    const point menu_pos( std::max( 0, button_pos.x - menu_width - 1 ),\n                          std::max( 0, button_pos.y - menu_height + 1 ) );\n    safemode_corner_menu.configure( w_pixel_minimap, menu_pos,\n                                    safemode_corner_entries( safe_mode != SAFE_MODE_OFF ),\n                                    menu_width );\n}\n''',
    '''void game::configure_safemode_corner_menu()\n{\n    if( !safemode_corner_button_fits( w_pixel_minimap ) ) {\n        safemode_corner_menu.close();\n        return;\n    }\n\n    const point button_pos = safemode_corner_button_pos( w_pixel_minimap );\n    const point button_size = safemode_corner_button_size( w_pixel_minimap );\n    const int available_left = std::max( 3, button_pos.x - 1 );\n    const int menu_width = std::min( safemode_corner_menu_width, available_left );\n    const int menu_height = safemode_corner_menu_rows + 2;\n    const point menu_pos( std::max( 0, button_pos.x - menu_width - 1 ),\n                          std::max( 0, button_pos.y + button_size.y - menu_height ) );\n    safemode_corner_menu.configure( w_pixel_minimap, menu_pos,\n                                    safemode_corner_entries( safe_mode != SAFE_MODE_OFF ),\n                                    menu_width );\n}\n''',
    "scaled safemode menu anchor",
)

replace_once(
    "src/game.cpp",
    '''        safemode_corner_button_overlay.close();\n        safemode_corner_button.clear();\n''',
    '''        safemode_corner_button.close();\n''',
    "safemode early close",
)
replace_once(
    "src/game.cpp",
    '''    if( w_pixel_minimap && getmaxx( w_pixel_minimap ) >= safemode_corner_button_width + 3 &&\n        getmaxy( w_pixel_minimap ) >= 3 ) {\n        const bool enabled = safe_mode != SAFE_MODE_OFF;\n        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );\n        const inclusive_rectangle<point> button_bounds =\n            safemode_corner_button_bounds( w_pixel_minimap );\n\n        safemode_corner_button_overlay.configure( w_pixel_minimap, button_pos,\n                safemode_corner_button_width, 1 );\n        catacurses::window &button_window = safemode_corner_button_overlay.begin_draw( w_pixel_minimap );\n        if( button_window ) {\n            ui_action_strip_style button_style;\n            const nc_color state_color = enabled ? c_light_green : c_light_red;\n            button_style.text = state_color;\n            button_style.highlight = state_color;\n            button_style.selected = state_color;\n            button_style.gap = 0;\n            button_style.group_gap = 0;\n            safemode_corner_button.configure( button_window, point::zero,\n            { ui_action_entry( "!", "SAFE_CORNER_MENU", true,\n                               safemode_corner_menu.is_open() ) },\n            safemode_corner_button_width, 1, button_style );\n            safemode_corner_button.draw( button_window );\n            safemode_corner_button_overlay.refresh();\n        }\n''',
    '''    if( safemode_corner_button_fits( w_pixel_minimap ) ) {\n        const bool enabled = safe_mode != SAFE_MODE_OFF;\n        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );\n        const point button_size = safemode_corner_button_size( w_pixel_minimap );\n        const inclusive_rectangle<point> button_bounds =\n            safemode_corner_button_bounds( w_pixel_minimap );\n        const nc_color state_color = enabled ? c_light_green : c_light_red;\n        ui_icon_button_style button_style;\n        button_style.icon = state_color;\n        button_style.hover_icon = state_color;\n        button_style.selected_border = state_color;\n        button_style.selected_icon = state_color;\n        safemode_corner_button.configure( w_pixel_minimap, button_pos, button_size,\n                ui_action_entry( "", "SAFE_CORNER_MENU", true,\n                                 safemode_corner_menu.is_open() ),\n                "!", button_style );\n        safemode_corner_button.draw( w_pixel_minimap );\n''',
    "square safemode button draw",
)
replace_once(
    "src/game.cpp",
    '''        safemode_corner_button_overlay.close();\n        safemode_corner_button.clear();\n        safemode_corner_menu.close();\n''',
    '''        safemode_corner_button.close();\n        safemode_corner_menu.close();\n''',
    "safemode fallback close",
)
replace_once(
    "src/game.cpp",
    '''        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );\n        const point button_local = *parent_pos - button_pos;\n        safemode_corner_button.handle_input( "MOUSE_MOVE", button_local );\n''',
    '''        safemode_corner_button.handle_input( "MOUSE_MOVE", parent_pos );\n''',
    "safemode hover parent geometry",
)
replace_once(
    "src/game.cpp",
    '''    if( w_pixel_minimap && getmaxx( w_pixel_minimap ) >= safemode_corner_button_width + 3 &&\n        getmaxy( w_pixel_minimap ) >= 3 ) {\n''',
    '''    if( safemode_corner_button_fits( w_pixel_minimap ) ) {\n''',
    "safemode click fit",
)
replace_once(
    "src/game.cpp",
    '''        const point button_pos = safemode_corner_button_pos( w_pixel_minimap );\n        const ui_action_result button_result = safemode_corner_button.handle_input(\n                "SELECT", parent_pos - button_pos );\n''',
    '''        const ui_action_result button_result = safemode_corner_button.handle_input(\n                "SELECT", parent_pos );\n''',
    "safemode click parent geometry",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Use scalable square icon button for safemode\n", encoding="utf-8"
)
