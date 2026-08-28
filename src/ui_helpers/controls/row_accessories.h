#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_ROW_ACCESSORIES_H
#define CATA_SRC_UI_HELPERS_CONTROLS_ROW_ACCESSORIES_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "action_strip.h"

enum class ui_row_accessory_side {
    leading,
    trailing
};

/** A local action/toggle/dropdown or read-only value. IDs belong to the caller;
 * checked/dropdown state and styling use the same contract as action strips. */
struct ui_row_accessory {
    ui_action_entry action;
    ui_row_accessory_side side = ui_row_accessory_side::trailing;
    bool interactive = true;
    int max_width = 0;
};

struct ui_row_label_area {
    point origin = point::zero;
    int width = 0;
};

/** Composable row controls. The caller supplies row geometry, never accessory
 * hitboxes. begin_layout() drops all stale/offscreen regions on every redraw.
 * Scrollbar space is supplied by the owning list, outside this content width. */
class ui_row_accessories
{
    public:
        void begin_layout() {
            regions_.clear();
        }

        void clear() {
            begin_layout();
            hovered_id_.clear();
        }

        ui_row_label_area layout( const point &origin, int width,
                                  const std::vector<ui_row_accessory> &items ) {
            width = std::max( 0, width );
            int left = origin.x;
            int right = origin.x + width;
            const int label_min = std::min( 6, width / 3 );
            // Controls have priority over optional values on narrow rows.
            for( const bool interactive : {
                     true, false
                 } ) {
                for( const ui_row_accessory &item : items ) {
                    if( item.interactive != interactive ) {
                        continue;
                    }
                    const std::string label = interactive ?
                                              ui_action_strip::format_label( item.action ) : item.action.label;
                    const int natural = utf8_width( remove_color_tags( label ) );
                    const int requested = item.max_width > 0 ? std::min( natural, item.max_width ) : natural;
                    const int available = std::max( 0, right - left - label_min - 1 );
                    const int actual = std::min( requested, available );
                    if( actual <= 0 ) {
                        continue;
                    }
                    const bool leading = item.side == ui_row_accessory_side::leading;
                    const int x = leading ? left : right - actual;
                    regions_.push_back( { inclusive_rectangle<point>( point( x, origin.y ),
                            point( x + actual - 1, origin.y ) ), item.action, label, interactive } );
                    if( leading ) {
                        left += actual + 1;
                    } else {
                        right -= actual + 1;
                    }
                }
            }
            return { point( left, origin.y ), std::max( 0, right - left ) };
        }

        ui_action_result handle_input( const std::string &action,
                                       const std::optional<point> &pos ) {
            const region *hit = nullptr;
            if( pos ) {
                for( const region &r : regions_ ) {
                    if( r.interactive && r.bounds.contains( *pos ) ) {
                        hit = &r;
                        break;
                    }
                }
            }
            if( action == "MOUSE_MOVE" ) {
                hovered_id_ = hit ? hit->action.id : std::string();
                return { hit ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         hit ? std::optional<ui_action_entry>( hit->action ) : std::nullopt };
            }
            // Keyboard commands belong to explicit focus/semantic bindings,
            // never to the last accessory the mouse happened to cross.
            if( action != "SELECT" || !hit ) {
                return {};
            }
            return { hit->action.enabled ? ui_action_result_type::activated :
                     ui_action_result_type::disabled, hit->action };
        }

        void draw( const catacurses::window &window,
                   const ui_action_strip_style &style = ui_action_strip_style() ) const {
            for( const region &r : regions_ ) {
                const nc_color color = !r.interactive ? c_light_gray : !r.action.enabled ?
                                       style.disabled : r.action.id == hovered_id_ ? style.highlight :
                                       r.action.selected ? style.selected : style.text;
                trim_and_print( window, r.bounds.p_min, r.bounds.p_max.x - r.bounds.p_min.x + 1,
                                color, r.label );
            }
        }

    private:
        struct region {
            inclusive_rectangle<point> bounds;
            ui_action_entry action;
            std::string label;
            bool interactive;
        };
        std::vector<region> regions_;
        std::string hovered_id_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_ROW_ACCESSORIES_H
