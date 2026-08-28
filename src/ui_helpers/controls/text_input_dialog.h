#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_TEXT_INPUT_DIALOG_H
#define CATA_SRC_UI_HELPERS_CONTROLS_TEXT_INPUT_DIALOG_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cursesdef.h"
#include "../../input_context.h"
#include "../../input_enums.h"
#include "../../output.h"
#include "../../point.h"
#include "../../string_input_popup.h"
#include "../../translations.h"
#include "../../ui_manager.h"
#include "action_strip.h"
#include "text_field.h"

struct ui_text_input_dialog_style {
    nc_color border = c_light_gray;
    nc_color title = c_light_green;
    ui_text_field_style field;
    ui_action_strip_style actions;
    ui_action_strip_style close;

    ui_text_input_dialog_style() {
        field.label = c_light_gray;
        field.border = c_light_gray;
        field.text = c_white;
        field.placeholder = c_dark_gray;
        actions.text = c_light_gray;
        actions.disabled = c_dark_gray;
        actions.highlight = hilite( c_white );
        actions.selected = hilite( c_white );
        close = actions;
        close.text = c_light_red;
    }
};

/**
 * Shared modal text editor for screen-owned rename/relabel operations.
 *
 * The helper owns the modal interaction contract: text editing, Enter/Escape,
 * mouse hover/click routing, a top-right close control, and OK/Cancel actions.
 * The caller owns only the semantic title/label/value and applies the returned
 * string when present.  Cancel is distinct from confirming an empty string.
 */
inline std::optional<std::string> ui_query_text_input_dialog(
    const std::string &title, const std::string &label, const std::string &initial,
    const int requested_input_width = 20, const int max_length = -1,
    const ui_text_input_dialog_style &style = ui_text_input_dialog_style() )
{
    const int screen_width = getmaxx( catacurses::stdscr );
    const int screen_height = getmaxy( catacurses::stdscr );
    if( screen_width < 18 || screen_height < 7 ) {
        return std::nullopt;
    }

    const int label_width = utf8_width( label ) + ( label.empty() ? 0 : 2 );
    const int desired_width = std::max( { 32, requested_input_width + label_width + 6,
                                         utf8_width( title ) + 12 } );
    const int dialog_width = std::clamp( desired_width, 18, screen_width - 2 );
    constexpr int dialog_height = 7;

    catacurses::window window;
    ui_adaptor ui;
    ui_text_field field;
    ui_action_strip close_button;
    ui_action_strip actions;

    string_input_popup input;
    input.text( initial )
    .string_color( c_white )
    .cursor_color( h_light_gray )
    .underscore_color( c_dark_gray );
    if( max_length > 0 ) {
        input.max_length( max_length );
    }

    input_context context( "STRING_INPUT", keyboard_mode::keychar );
    context.register_action( "TEXT.QUIT" );
    context.register_action( "TEXT.CONFIRM" );
    context.register_action( "TEXT.LEFT" );
    context.register_action( "TEXT.RIGHT" );
    context.register_action( "TEXT.CLEAR" );
    context.register_action( "TEXT.BACKSPACE" );
    context.register_action( "TEXT.HOME" );
    context.register_action( "TEXT.END" );
    context.register_action( "TEXT.DELETE" );
#if defined(TILES)
    context.register_action( "TEXT.PASTE" );
#endif
    context.register_action( "TEXT.INPUT_FROM_FILE" );
    context.register_action( "HELP_KEYBINDINGS" );
    context.register_action( "ANY_INPUT" );
    context.register_action( "SELECT" );
    context.register_action( "MOUSE_MOVE" );
    input.context( context );

    bool accept_requested = false;
    bool cancel_requested = false;

    const auto create_window = [&]() {
        const int current_width = getmaxx( catacurses::stdscr );
        const int current_height = getmaxy( catacurses::stdscr );
        const int width = std::min( dialog_width, std::max( 1, current_width ) );
        const int height = std::min( dialog_height, std::max( 1, current_height ) );
        window = catacurses::newwin( height, width,
                                     point( std::max( 0, ( current_width - width ) / 2 ),
                                            std::max( 0, ( current_height - height ) / 2 ) ) );
        ui.position_from_window( window );
    };

    create_window();
    ui.set_disable_uis_below( true );
    ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
        create_window();
        adaptor.position_from_window( window );
    } );
    ui.on_redraw( [&]( ui_adaptor & ) {
        werase( window );
        draw_border( window, style.border );
        const int width = getmaxx( window );
        const int height = getmaxy( window );
        const int content_width = std::max( 0, width - 4 );

        trim_and_print( window, point( 2, 1 ), content_width, style.title, title );
        close_button.configure( window, point( 2, 1 ),
        { { ui_action_entry( "X", "CLOSE" ), 0, ui_action_alignment::right } },
        content_width, 1, style.close );
        close_button.draw( window );

        const std::string field_label = label.empty() ? std::string() : label + ": ";
        field.configure( window, point( 2, 3 ), content_width, field_label,
                         input.text(), std::string(), false, style.field );
        field.draw( window );

        actions.configure( window, point( 2, std::max( 1, height - 2 ) ), {
            { ui_action_entry( _( "OK" ), "ACCEPT" ), 0, ui_action_alignment::left },
            { ui_action_entry( _( "Cancel" ), "CANCEL" ), 1, ui_action_alignment::right }
        }, content_width, 1, style.actions );
        actions.draw( window );

        input.window( window, field.edit_start(), field.edit_end_x() + 1 );
        input.query_string( false, true );
        wnoutrefresh( window );
    } );

    const auto handle_pointer = [&]( const std::string &action ) {
        const std::optional<point> pos = context.get_coordinates_text( window );
        const ui_action_result close_result = close_button.handle_input( action, pos );
        if( close_result.type == ui_action_result_type::activated ) {
            cancel_requested = true;
        }
        const ui_action_result action_result = actions.handle_input( action, pos );
        if( action_result.type == ui_action_result_type::activated && action_result.entry ) {
            if( action_result.entry->id == "ACCEPT" ) {
                accept_requested = true;
                input.confirm();
            } else if( action_result.entry->id == "CANCEL" ) {
                cancel_requested = true;
            }
        }
        ui.invalidate_ui();
        return true;
    };

    input.add_callback( "MOUSE_MOVE", [&]() {
        return handle_pointer( "MOUSE_MOVE" );
    } );
    input.add_callback( "SELECT", [&]() {
        return handle_pointer( "SELECT" );
    } );

    while( true ) {
        ui_manager::redraw();
        input.query_string( false );
        if( cancel_requested || input.canceled() ) {
            return std::nullopt;
        }
        if( accept_requested || input.confirmed() ) {
            return input.text();
        }
        ui.invalidate_ui();
    }
}

#endif // CATA_SRC_UI_HELPERS_CONTROLS_TEXT_INPUT_DIALOG_H
