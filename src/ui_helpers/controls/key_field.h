#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_KEY_FIELD_H
#define CATA_SRC_UI_HELPERS_CONTROLS_KEY_FIELD_H

#include <functional>
#include <optional>
#include <string>

#include "action_strip.h"
#include "../../input.h"

enum class ui_key_field_result_type {
    ignored,
    handled,
    assigned,
    cleared,
    cancelled,
    invalid
};

struct ui_key_field_result {
    ui_key_field_result_type type = ui_key_field_result_type::ignored;
    int key = 0;
    bool consumed() const {
        return type != ui_key_field_result_type::ignored;
    }
};

/** One-key inline editor. The caller owns validation and conflict resolution.
 * Capture receives RAW input before the screen's action context processes it;
 * even keys bound to Help/Quit must not escape into unrelated commands.
 * Resize/selection changes should call cancel(); hiding only clears geometry. */
class ui_key_field
{
    public:
        void arm() {
            armed_ = true;
        }
        void cancel() {
            armed_ = false;
        }
        bool armed() const {
            return armed_;
        }
        void hide() {
            strip_.clear();
        }
        void configure( const catacurses::window &window, const point &pos, int width,
                        const std::string &label, const std::string &value,
                        const std::string &waiting ) {
            configure( point( getmaxx( window ), getmaxy( window ) ), pos, width, label, value, waiting );
        }
        void configure( const point &parent_size, const point &pos, int width,
                        const std::string &label, const std::string &value,
                        const std::string &waiting ) {
            strip_.configure( parent_size, pos, {
                {
                    ui_action_entry( label + " " + ( armed_ ? waiting : value ),
                                     "KEY_FIELD", true, armed_ )
                }
            }, width );
        }
        void draw( const catacurses::window &window ) const {
            strip_.draw( window );
        }
        ui_action_result handle_pointer_input( const std::string &action,
                                               const std::optional<point> &pos ) {
            const ui_action_result result = strip_.handle_pointer_input( action, pos );
            if( result.type == ui_action_result_type::activated ) {
                arm();
            }
            return result;
        }
        ui_key_field_result capture( const input_event &event,
                                     const std::function<bool( int )> &valid,
                                     const int clear_key = ' ', const int cancel_key = KEY_ESCAPE ) {
            if( !armed_ ) {
                return {};
            }
            if( event.type != input_event_t::keyboard_char ) {
                return { ui_key_field_result_type::handled };
            }
            const int key = event.get_first_input();
            if( event.sequence.size() != 1 ) {
                return { ui_key_field_result_type::invalid, key };
            }
            if( key == cancel_key ) {
                cancel();
                return { ui_key_field_result_type::cancelled, key };
            }
            if( key == clear_key ) {
                cancel();
                return { ui_key_field_result_type::cleared, key };
            }
            if( !valid( key ) ) {
                return { ui_key_field_result_type::invalid, key };
            }
            cancel();
            return { ui_key_field_result_type::assigned, key };
        }

        ui_key_field_result read( const std::function<bool( int )> &valid ) {
            return capture( inp_mngr.get_input_event( keyboard_mode::keychar ), valid );
        }

    private:
        ui_action_strip strip_;
        bool armed_ = false;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_KEY_FIELD_H
