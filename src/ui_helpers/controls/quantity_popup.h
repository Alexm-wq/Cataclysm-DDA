#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_QUANTITY_POPUP_H
#define CATA_SRC_UI_HELPERS_CONTROLS_QUANTITY_POPUP_H

#include <algorithm>
#include <optional>
#include <string>

#include "../../string_formatter.h"
#include "../../string_input_popup.h"
#include "../../translations.h"

/** Bounded quantity prompt backed by the standard input control. Cancel is
 * distinct from zero; invalid/out-of-range input never silently chooses all.
 */
inline std::optional<int> ui_query_quantity( const std::string &title,
        const std::string &description, int maximum, int initial = 1 )
{
    if( maximum < 1 ) {
        return std::nullopt;
    }
    string_input_popup input;
    input.title( title ).description( description + "\n" +
                                     string_format( _( "Enter a quantity from 1 to %d." ), maximum ) )
    .width( 20 ).text( std::to_string( std::clamp( initial, 1, maximum ) ) ).only_digits( true );
    while( true ) {
        const std::optional<int> amount = input.query_int();
        if( input.canceled() ) {
            return std::nullopt;
        }
        if( amount && *amount >= 1 && *amount <= maximum ) {
            return amount;
        }
    }
}

#endif // CATA_SRC_UI_HELPERS_CONTROLS_QUANTITY_POPUP_H
