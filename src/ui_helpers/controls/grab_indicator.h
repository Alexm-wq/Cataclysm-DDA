#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_GRAB_INDICATOR_H
#define CATA_SRC_UI_HELPERS_CONTROLS_GRAB_INDICATOR_H

#include <algorithm>
#include <optional>
#include <string>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cursesdef.h"
#include "../../item.h"
#include "../../item_location.h"
#include "../../output.h"
#include "../../point.h"
#if defined(TILES)
#include "../../sdltiles.h"
#endif

/**
 * Draw the item currently owned by a pointer drag next to the pointer.
 *
 * TILES uses the real item tile as the leading icon; curses uses the item's
 * normal symbol/color.  The small [::] grip is deliberately renderer-neutral
 * so the state remains recognizable even when the tileset has no item sprite.
 * This helper owns only transient visual state and never changes the item.
 */
inline void clear_ui_grab_item_indicator()
{
#if defined(TILES)
    clear_ui_tile_previews();
#endif
}

inline void draw_ui_grab_item_indicator( const catacurses::window &parent,
        const std::optional<point> &cursor, const item_location &held )
{
    if( !parent || !cursor || !held ) {
        clear_ui_grab_item_indicator();
        return;
    }

    const int width = getmaxx( parent );
    const int height = getmaxy( parent );
    if( width <= 0 || height <= 0 ) {
        clear_ui_grab_item_indicator();
        return;
    }

    constexpr int max_name_width = 22;
    constexpr int tile_width = 2;
    constexpr int label_gap = 1;
    constexpr int grip_width = 4; // [::]
    const int desired_width = tile_width + label_gap + grip_width + 1 + max_name_width;

    point origin( cursor->x + 1, cursor->y + 1 );
    if( origin.x + desired_width > width ) {
        origin.x = std::max( 0, cursor->x - desired_width );
    }
    if( origin.y + 2 > height ) {
        origin.y = std::max( 0, cursor->y - 2 );
    }
    origin.x = std::clamp( origin.x, 0, std::max( 0, width - 1 ) );
    origin.y = std::clamp( origin.y, 0, std::max( 0, height - 1 ) );

    int label_x = origin.x;
#if defined(TILES)
    ui_tile_preview preview;
    preview.pos = origin;
    preview.size = point( tile_width, std::min( 2, height - origin.y ) );
    preview.type = ui_tile_preview_type::item;
    preview.id = held->typeId().str();
    preview.variant = held->has_itype_variant() ? held->itype_variant().id : std::string();
    set_ui_tile_previews( parent, { preview } );
    label_x += tile_width + label_gap;
#else
    mvwputch( parent, origin, held->color(), held->symbol() );
    label_x += 2;
#endif

    if( label_x >= width ) {
        return;
    }
    trim_and_print( parent, point( label_x, origin.y ),
                    std::min( grip_width, width - label_x ), c_light_cyan, "[::]" );

    const int name_x = label_x + grip_width + 1;
    if( name_x < width ) {
        const std::string name = remove_color_tags( held->tname() );
        trim_and_print( parent, point( name_x, origin.y ),
                        std::min( max_name_width, width - name_x ), c_light_gray, name );
    }
}

#endif // CATA_SRC_UI_HELPERS_CONTROLS_GRAB_INDICATOR_H
