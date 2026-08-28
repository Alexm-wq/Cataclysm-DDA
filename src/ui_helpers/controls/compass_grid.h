#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_COMPASS_GRID_H
#define CATA_SRC_UI_HELPERS_CONTROLS_COMPASS_GRID_H

#include <algorithm>
#include <array>
#include <optional>
#include <string>
#include <utility>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../output.h"
#include "../../point.h"
#include "../models/action_entry.h"
#include "../models/hit_map.h"

/** Cells are in compass order: NW, N, NE, W, center, E, SW, S, SE.
 * The caller supplies translated labels, semantic actions and world state.
 */
struct ui_compass_entry {
    ui_action_entry action;
    bool blocked = false;
    bool dangerous = false;
    bool occupied = false;
    bool vehicle = false;
};

struct ui_compass_grid_style {
    nc_color empty = c_light_gray;
    nc_color occupied = c_light_green;
    nc_color dangerous = c_light_red;
    nc_color blocked = c_dark_gray;
    int column_gap = 1;
};

/** Shared inventory-style spatial picker. Owns rendering, pointer hit tests,
 * hover and activation. Geometry is relative to the caller-owned window.
 */
class ui_compass_grid
{
    public:
        static point offset( const int index ) {
            return point( index % 3 - 1, index / 3 - 1 );
        }

        void clear() {
            entries_ = {};
            hits_.clear();
            hovered_ = -1;
        }

        void set_entries( std::array<ui_compass_entry, 9> entries ) {
            entries_ = std::move( entries );
        }

        int width( const int column_gap = 1 ) const {
            int label_width = 2;
            for( const ui_compass_entry &entry : entries_ ) {
                label_width = std::max( label_width, utf8_width( entry.action.label ) );
            }
            return ( label_width + 2 ) * 3 + column_gap * 2;
        }

        void draw( const catacurses::window &window, const point &origin, const int width,
                   const ui_compass_grid_style &style = ui_compass_grid_style() ) {
            hits_.clear();
            const int needed_width = this->width( style.column_gap );
            const int cell_width = ( needed_width - style.column_gap * 2 ) / 3;
            const int label_width = cell_width - 2;
            if( origin.x < 0 || origin.y < 0 || needed_width > width ||
                origin.x + needed_width > getmaxx( window ) || origin.y + 3 > getmaxy( window ) ) {
                return;
            }
            for( int i = 0; i < 9; ++i ) {
                const ui_compass_entry &entry = entries_[i];
                const point pos = origin + point( ( i % 3 ) * ( cell_width + style.column_gap ), i / 3 );
                hits_.add( inclusive_rectangle<point>( pos, pos + point( cell_width - 1, 0 ) ), i );
                if( entry.blocked ) {
                    for( int x = 0; x < cell_width; ++x ) {
                        mvwprintz( window, pos + point( x, 0 ), style.blocked, "█" );
                    }
                    continue;
                }
                nc_color color = entry.dangerous ? style.dangerous :
                                 entry.occupied ? style.occupied : style.empty;
                if( entry.action.selected || i == hovered_ ) {
                    color = hilite( color );
                }
                const std::string padding( label_width - utf8_width( entry.action.label ), ' ' );
                const std::string label = ( entry.vehicle ? "<" : "[" ) + entry.action.label + padding +
                                          ( entry.vehicle ? ">" : "]" );
                mvwprintz( window, pos, color, "%s", label );
            }
        }

        ui_action_result handle_input( const std::string &action, const std::optional<point> &pos ) {
            if( action == "MOUSE_MOVE" ) {
                hovered_ = pos ? hits_.hit( *pos ).value_or( -1 ) : -1;
                return { hovered_ >= 0 ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            std::optional<int> index;
            if( action == "SELECT" ) {
                index = pos ? hits_.hit( *pos ) : std::nullopt;
            } else {
                for( int i = 0; i < 9; ++i ) {
                    if( !entries_[i].action.id.empty() && entries_[i].action.id == action ) {
                        index = i;
                        break;
                    }
                }
            }
            if( !index ) {
                return {};
            }
            const ui_compass_entry &entry = entries_[*index];
            return { !entry.blocked && entry.action.enabled ? ui_action_result_type::activated :
                     ui_action_result_type::disabled, entry.action };
        }

    private:
        std::array<ui_compass_entry, 9> entries_;
        ui_hit_map<int> hits_;
        int hovered_ = -1;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_COMPASS_GRID_H
