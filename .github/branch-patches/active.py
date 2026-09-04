from pathlib import Path

cpp_path = Path("src/inventory_ui.cpp")
h_path = Path("src/inventory_ui.h")
helper_path = Path("src/ui_helpers/controls/grab_indicator.h")

cpp = cpp_path.read_text(encoding="utf-8")
hdr = h_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


cpp = replace_once(
    cpp,
    '#include "ui_iteminfo.h"\n#include "ui_manager.h"\n',
    '#include "ui_iteminfo.h"\n#include "ui_helpers/controls/grab_indicator.h"\n#include "ui_manager.h"\n',
    "grab indicator include",
)

hdr = replace_once(
    hdr,
    '''        /**\n         * The input context for navigation, already contains some actions for movement.\n         */\n        input_context ctxt;\n''',
    '''        /**\n         * The input context for navigation, already contains some actions for movement.\n         */\n        input_context ctxt;\n\n        // Pointer-following feedback for the item currently owned by a drag.\n        // Kept on the selector rather than inferred from row highlight so a\n        // held item remains visually stable while the pointer crosses rows.\n        item_location grabbed_item;\n        void draw_grab_indicator();\n        void clear_grab_indicator();\n''',
    "selector grab state",
)

cpp = replace_once(
    cpp,
    '''shared_ptr_fast<ui_adaptor> inventory_selector::create_or_get_ui_adaptor()\n{\n''',
    '''void inventory_selector::draw_grab_indicator()\n{\n    draw_ui_grab_item_indicator( w_inv, ctxt.get_coordinates_text( w_inv ), grabbed_item );\n}\n\nvoid inventory_selector::clear_grab_indicator()\n{\n    const bool was_active = static_cast<bool>( grabbed_item );\n    grabbed_item = item_location();\n    if( was_active ) {\n        clear_ui_grab_item_indicator();\n    }\n}\n\nshared_ptr_fast<ui_adaptor> inventory_selector::create_or_get_ui_adaptor()\n{\n''',
    "grab indicator methods",
)

cpp = replace_once(
    cpp,
    '''        current_ui->on_redraw( [this]( const ui_adaptor & ) {\n            refresh_window();\n        } );\n''',
    '''        current_ui->on_redraw( [this]( const ui_adaptor & ) {\n            refresh_window();\n            draw_grab_indicator();\n        } );\n''',
    "draw grab indicator after inventory",
)

start_drag = '''                if( input.entry->is_item() ) {\n                    dragActive = true;\n                    startDragItem = input.entry->locations.front();\n                }\n'''
start_drag_new = '''                if( input.entry->is_item() ) {\n                    dragActive = true;\n                    startDragItem = input.entry->locations.front();\n                    grabbed_item = startDragItem;\n                }\n'''
if cpp.count(start_drag) != 2:
    raise RuntimeError(f"drag start blocks: expected two matches, found {cpp.count(start_drag)}")
cpp = cpp.replace(start_drag, start_drag_new)

finish_drag = '''                dragActive = false;\n                item_location startDragItemCpy = startDragItem;\n                startDragItem = item_location();\n'''
finish_drag_new = '''                dragActive = false;\n                item_location startDragItemCpy = startDragItem;\n                startDragItem = item_location();\n                clear_grab_indicator();\n'''
if cpp.count(finish_drag) != 2:
    raise RuntimeError(f"drag finish blocks: expected two matches, found {cpp.count(finish_drag)}")
cpp = cpp.replace(finish_drag, finish_drag_new)

cpp = replace_once(
    cpp,
    '''inventory_selector::~inventory_selector()\n{\n    item_name_cache_users--;\n''',
    '''inventory_selector::~inventory_selector()\n{\n    clear_grab_indicator();\n    item_name_cache_users--;\n''',
    "clear grab indicator on selector teardown",
)

helper = r'''#pragma once
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
'''

if helper_path.exists():
    raise RuntimeError("grab_indicator.h already exists; refusing to overwrite")
helper_path.write_text(helper, encoding="utf-8")
cpp_path.write_text(cpp, encoding="utf-8")
h_path.write_text(hdr, encoding="utf-8")

# Static invariants only; no compile/build is run by this patch.
assert cpp.count('grabbed_item = startDragItem;') == 2
assert cpp.count('clear_grab_indicator();') >= 3
assert 'draw_ui_grab_item_indicator' in cpp
assert 'ui_tile_preview_type::item' in helper

Path("/tmp/branch_patch_commit_message").write_text(
    "Add grabbed-item cursor indicator\n", encoding="utf-8"
)
