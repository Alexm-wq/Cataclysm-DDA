#pragma once
#ifndef CATA_SRC_CRAFTING_DESTINATION_UI_H
#define CATA_SRC_CRAFTING_DESTINATION_UI_H

#include <array>
#include <optional>
#include <string>
#include <vector>

#include "crafting_destination.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/compass_grid.h"

class Character;
class item;
class recipe;

/** Crafting-specific data and layout around shared spatial/list controls. */
class crafting_destination_picker
{
    public:
        void refresh( Character &crafter, const recipe *rec, int batch );
        void draw( const catacurses::window &window, const point &origin, int width );
        ui_action_result handle_input( const std::string &action, const std::optional<point> &pos );
        /** A tile action opens its storage list; no action opens the full picker. */
        bool query( const std::string &tile_action = std::string() );
        bool available() const;
        std::string unavailable_reason() const;
        crafting_destination destination() const;

    private:
        Character *crafter_ = nullptr;
        const recipe *recipe_ = nullptr;
        int batch_ = 0;
        bool explicit_selection_ = false;
        crafting_destination destination_;
        std::array<crafting_destination_tile, 9> tiles_;
        std::vector<item> results_;
        ui_compass_grid compass_;
        ui_action_strip summary_;

        std::optional<int> selected_tile() const;
        std::array<ui_compass_entry, 9> compass_entries( std::optional<int> selected ) const;
        std::string summary() const;
};

#endif // CATA_SRC_CRAFTING_DESTINATION_UI_H
