from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/cata_tiles.h",
    '''        void init_draw_highlight( const tripoint_bub_ms &p );\n        void draw_highlight();\n        void void_highlight();\n''',
    '''        void init_draw_highlight( const tripoint_bub_ms &p );\n        /** Draw a thin green selection outline around a world tile for contextual UI. */\n        void init_draw_ui_context_outline( const tripoint_bub_ms &p );\n        void draw_highlight();\n        void void_highlight();\n'''
)

replace_once(
    "src/cata_tiles.h",
    '''        std::vector<tripoint_bub_ms> cursors;\n        std::vector<tripoint_bub_ms> highlights;\n        std::vector<tripoint_bub_ms> ui_removal_overlays;\n''',
    '''        std::vector<tripoint_bub_ms> cursors;\n        std::vector<tripoint_bub_ms> highlights;\n        std::vector<tripoint_bub_ms> ui_context_outlines;\n        std::vector<tripoint_bub_ms> ui_removal_overlays;\n'''
)

replace_once(
    "src/cata_tiles.cpp",
    '''void cata_tiles::init_draw_highlight( const tripoint_bub_ms &p )\n{\n    do_draw_highlight = true;\n    highlights.emplace_back( p );\n}\nvoid cata_tiles::init_draw_ui_removal_overlay( const tripoint_bub_ms &p )\n''',
    '''void cata_tiles::init_draw_highlight( const tripoint_bub_ms &p )\n{\n    do_draw_highlight = true;\n    highlights.emplace_back( p );\n}\nvoid cata_tiles::init_draw_ui_context_outline( const tripoint_bub_ms &p )\n{\n    // Share the normal transient-highlight draw cycle, but keep the visual\n    // independent from the tileset-provided highlight sprite.\n    do_draw_highlight = true;\n    ui_context_outlines.emplace_back( p );\n}\nvoid cata_tiles::init_draw_ui_removal_overlay( const tripoint_bub_ms &p )\n'''
)

replace_once(
    "src/cata_tiles.cpp",
    '''void cata_tiles::void_highlight()\n{\n    do_draw_highlight = false;\n    highlights.clear();\n}\nvoid cata_tiles::void_ui_removal_overlays()\n''',
    '''void cata_tiles::void_highlight()\n{\n    do_draw_highlight = false;\n    highlights.clear();\n    ui_context_outlines.clear();\n}\nvoid cata_tiles::void_ui_removal_overlays()\n'''
)

replace_once(
    "src/cata_tiles.cpp",
    '''void cata_tiles::draw_highlight()\n{\n    for( const tripoint_bub_ms &p : highlights ) {\n        draw_from_id_string( "highlight", p, 0, 0, lit_level::LIT, false );\n    }\n}\nvoid cata_tiles::draw_ui_removal_overlays()\n''',
    '''void cata_tiles::draw_highlight()\n{\n    for( const tripoint_bub_ms &p : highlights ) {\n        draw_from_id_string( "highlight", p, 0, 0, lit_level::LIT, false );\n    }\n\n    if( ui_context_outlines.empty() ) {\n        return;\n    }\n\n    // Context selection should be visible without tinting or obscuring the tile.\n    // Keep the line deliberately thin and slightly inset from the tile edge.\n    constexpr SDL_Color context_green{ 72, 224, 104, 232 };\n    SDL_BlendMode previous_blend_mode;\n    GetRenderDrawBlendMode( renderer, previous_blend_mode );\n    SetRenderDrawBlendMode( renderer, SDL_BLENDMODE_BLEND );\n    SetRenderDrawColor( renderer, context_green.r, context_green.g,\n                        context_green.b, context_green.a );\n\n    for( const tripoint_bub_ms &p : ui_context_outlines ) {\n        const point tile = player_to_screen( p.xy() );\n        if( is_isometric() ) {\n            const int left = tile.x + 1;\n            const int right = tile.x + std::max( 1, tile_width - 2 );\n            const int top = tile.y + 1;\n            const int bottom = tile.y + std::max( 1, tile_height - 2 );\n            const int center_x = tile.x + tile_width / 2;\n            const int center_y = tile.y + tile_height / 2;\n            const SDL_Point diamond[] = {\n                { center_x, top }, { right, center_y }, { center_x, bottom },\n                { left, center_y }, { center_x, top }\n            };\n            SDL_RenderDrawLines( renderer.get(), diamond, 5 );\n        } else {\n            const SDL_Rect outline{\n                tile.x + 1, tile.y + 1,\n                std::max( 1, tile_width - 2 ), std::max( 1, tile_height - 2 )\n            };\n            SDL_RenderDrawRect( renderer.get(), &outline );\n        }\n    }\n    SetRenderDrawBlendMode( renderer, previous_blend_mode );\n}\nvoid cata_tiles::draw_ui_removal_overlays()\n'''
)

replace_once(
    "src/game.cpp",
    '''    if( entries.empty() ) {\n        add_msg( _( "Nothing relevant here." ) );\n        return false;\n    }\n\n    // ui_dropdown is the shared mouse-first context-menu helper.  The gameplay input\n''',
    '''    if( entries.empty() ) {\n        add_msg( _( "Nothing relevant here." ) );\n        return false;\n    }\n\n#if defined(TILES)\n    // Paint the selected world tile once before the modal freezes the gameplay\n    // viewport underneath it.  The renderer clears this transient layer after\n    // that frame, so closing the menu cannot leave a stale selection behind.\n    if( use_tiles && tilecontext ) {\n        tilecontext->init_draw_ui_context_outline( mouse_target );\n        invalidate_main_ui_adaptor();\n        ui_manager::redraw_invalidated();\n    }\n#endif\n\n    // ui_dropdown is the shared mouse-first context-menu helper.  The gameplay input\n'''
)

print("right-click context tile outline patched")
