#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_PANEL_H
#define CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_PANEL_H

#include <algorithm>
#include <optional>
#include <string>
#include <vector>

#include "action_strip.h"
#include "selection_list.h"

/** Content and semantic actions supplied by the owning screen. */
struct ui_selection_panel_content {
    std::string title;
    std::string heading;
    std::string status;
    bool status_is_error = true;
    ui_action_entry primary;
    std::vector<ui_action_entry> secondary;
    ui_action_entry back;
};

/** Defaults shared by staged selectors; screens may override their geometry. */
struct ui_selection_panel_layout {
    int margin = 2;
    int title_y = 0;
    int back_y = 1;
    int heading_y = 2;
    int list_y = 4;
    int primary_rows = 1;
    int secondary_rows = 2;
};

struct ui_selection_panel_style {
    nc_color border = c_light_gray;
    nc_color title = c_light_green;
    nc_color text = c_light_gray;
    nc_color error = c_light_red;
    ui_selection_list_style list;
    ui_action_strip_style primary;
    ui_action_strip_style secondary;

    ui_selection_panel_style() {
        list.selected = hilite( c_white );
        secondary.text = c_light_gray;
        secondary.highlight = hilite( c_white );
        secondary.selected = hilite( c_white );
        primary = secondary;
        primary.text = c_light_green;
    }
};

struct ui_selection_panel_result {
    ui_action_result action;
    bool from_list = false;
};

/** Shared staged-selector surface. The owner supplies its window, content and
 * optional geometry/style; the helper owns drawing and control input routing.
 * A list activation is reported separately so the owner can validate the new
 * selection before continuing. Enter never activates a stale hovered button.
 */
class ui_selection_panel
{
    public:
        ui_selection_list list;

        void draw( const catacurses::window &window, const ui_selection_panel_content &content,
                   const ui_selection_panel_style &style = ui_selection_panel_style(),
                   const ui_selection_panel_layout &layout = ui_selection_panel_layout() ) {
            back_ = content.back;
            const int width = getmaxx( window ) - 2 * layout.margin;
            const int height = getmaxy( window );
            if( width <= 0 || height < 4 ) {
                primary_.clear();
                secondary_.clear();
                navigation_.clear();
                return;
            }
            const int secondary_y = height - 1 - layout.secondary_rows;
            const int primary_y = secondary_y - layout.primary_rows;
            const int status_y = primary_y - 1;
            draw_border( window, style.border );
            trim_and_print( window, point( layout.margin, layout.title_y ), width, style.title,
                            content.title );
            trim_and_print( window, point( layout.margin, layout.heading_y ), width, style.text,
                            content.heading );
            list.draw( window, point( layout.margin, layout.list_y ), width,
                       std::max( 0, status_y - layout.list_y ), style.list );
            primary_.configure( window, point( layout.margin, primary_y ), { content.primary },
                                width, layout.primary_rows, style.primary );
            primary_.draw( window );
            secondary_.configure( window, point( layout.margin, secondary_y ), content.secondary,
                                  width, layout.secondary_rows, style.secondary );
            secondary_.draw( window );
            const std::vector<ui_action_strip_item> navigation = {
                { content.back, 0, ui_action_alignment::right }
            };
            navigation_.configure( window, point( layout.margin, layout.back_y ), navigation,
                                   width, 1, style.secondary );
            navigation_.draw( window );
            if( !content.status.empty() && status_y >= layout.list_y ) {
                trim_and_print( window, point( layout.margin, status_y ), width,
                                content.status_is_error ? style.error : style.text, content.status );
            }
        }

        ui_selection_panel_result handle_input( const std::string &action, input_context &context,
                const std::optional<point> &pos ) {
            if( action == "QUIT" ) {
                return { { ui_action_result_type::activated, back_ }, false };
            }
            if( action != "CONFIRM" ) {
                for( ui_action_strip *strip : { &navigation_, &primary_, &secondary_ } ) {
                    const ui_action_result result = strip->handle_input( action, pos );
                    if( result.type == ui_action_result_type::activated ||
                        result.type == ui_action_result_type::disabled ) {
                        return { result, false };
                    }
                }
            }
            return { list.handle_input( action, context, pos ), true };
        }

    private:
        ui_action_entry back_{ "", "BACK" };
        ui_action_strip primary_;
        ui_action_strip secondary_;
        ui_action_strip navigation_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_SELECTION_PANEL_H
