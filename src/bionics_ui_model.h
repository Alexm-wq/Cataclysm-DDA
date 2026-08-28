#pragma once
#ifndef CATA_SRC_BIONICS_UI_MODEL_H
#define CATA_SRC_BIONICS_UI_MODEL_H

#include <algorithm>
#include <array>
#include <string_view>
#include <vector>

#include "bionics.h"
#include "localized_comparator.h"
#include "uistate.h"

/** Presentation-independent transformations shared by Bionics and its tests. */
namespace bionics_ui
{
inline constexpr std::string_view shortcut_characters =
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\"#&()*+./:;@[\\]^_{|}";
inline constexpr std::array<float, 7> fuel_thresholds = {
    1.0f, 0.90f, 0.70f, 0.50f, 0.30f, 0.10f, -1.0f
};

inline bool valid_shortcut( int key )
{
    return key > 0 && key < 128 && shortcut_characters.find( static_cast<char>( key ) ) !=
           std::string_view::npos;
}

inline bool assign_shortcut( bionic_collection &all, bionic::bionic_uid uid, int key )
{
    if( key != ' ' && !valid_shortcut( key ) ) {
        return false;
    }
    const auto target = std::find_if( all.begin(), all.end(), [uid]( const bionic & bio ) {
        return bio.get_uid() == uid;
    } );
    if( target == all.end() ) {
        return false;
    }
    if( key != ' ' ) {
        for( bionic &other : all ) {
            if( other.get_uid() != uid && other.invlet == key ) {
                other.invlet = target->invlet;
                break;
            }
        }
    }
    target->invlet = static_cast<char>( key );
    return true;
}

inline std::vector<bionic::bionic_uid> sorted_bionics( bionic_collection &all,
        bool activatable, bionic_ui_sort_mode mode )
{
    std::vector<const bionic *> rows;
    for( const bionic &bio : all ) {
        if( bio.info().activated == activatable ) {
            rows.push_back( &bio );
        }
    }
    // Installation order is already correct. Never use an always-true
    // comparator: it violates strict weak ordering and can lose duplicate CBMs.
    if( mode != bionic_ui_sort_mode::NONE && mode != bionic_ui_sort_mode::nsort ) {
        std::stable_sort( rows.begin(), rows.end(), [mode]( const bionic * lhs, const bionic * rhs ) {
            if( mode == bionic_ui_sort_mode::INVLET ) {
                return lhs->invlet < rhs->invlet;
            }
            const auto power = []( const bionic & bio ) {
                return bio.supports_safe_fuel() ? units::energy( -1_kJ * bio.info().fuel_efficiency ) :
                       bio.info().power_activate + bio.info().power_over_time;
            };
            if( mode == bionic_ui_sort_mode::POWER && power( *lhs ) != power( *rhs ) ) {
                return power( *lhs ) < power( *rhs );
            }
            return localized_compare( lhs->info().name.translated(), rhs->info().name.translated() );
        } );
    }
    std::vector<bionic::bionic_uid> result;
    for( const bionic *bio : rows ) {
        result.push_back( bio->get_uid() );
    }
    return result;
}
} // namespace bionics_ui

#endif // CATA_SRC_BIONICS_UI_MODEL_H
