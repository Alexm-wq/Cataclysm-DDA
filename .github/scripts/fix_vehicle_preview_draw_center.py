from pathlib import Path

path = Path("src/sdltiles.cpp")
text = path.read_text()
old = '''        const point tile_draw_pos( win->pos.x * fontwidth, win->pos.y * fontheight );
        const tripoint_bub_ms tile_draw_center = draw_terrain_tiles ? g->ter_view_p : *map_preview_center;
        const int tile_draw_width = draw_terrain_tiles ?
                                    TERRAIN_WINDOW_TERM_WIDTH * font->width : win->width * font->width;
        const int tile_draw_height = draw_terrain_tiles ?
                                     TERRAIN_WINDOW_TERM_HEIGHT * font->height : win->height * font->height;
'''
new = '''        const point tile_draw_pos( win->pos.x * fontwidth, win->pos.y * fontheight );
        const int tile_draw_width = draw_terrain_tiles ?
                                    TERRAIN_WINDOW_TERM_WIDTH * font->width : win->width * font->width;
        const int tile_draw_height = draw_terrain_tiles ?
                                     TERRAIN_WINDOW_TERM_HEIGHT * font->height : win->height * font->height;
        const tripoint_bub_ms logical_tile_draw_center = draw_terrain_tiles ?
                g->ter_view_p : *map_preview_center;
        tripoint_bub_ms tile_draw_center = logical_tile_draw_center;

        // cata_tiles::draw() predates arbitrary auxiliary map viewports.  In
        // orthographic mode it interprets its center parameter relative to the
        // normal terrain constants POSX/POSY rather than relative to the supplied
        // destination width/height.  That is correct for w_terrain, but it makes
        // a smaller Live/Split preview visibly off-center and makes its apparent
        // camera shift whenever scale or preview width changes.
        //
        // Translate the requested logical preview center into the legacy center
        // expected by draw(), so its resulting map origin is exactly the same one
        // used by cata_tiles::screen_to_player(..., win_size, logical_center).
        if( draw_preview_tiles && !draw_tiles->is_isometric() &&
            draw_tiles->get_tile_width() > 0 && draw_tiles->get_tile_height() > 0 ) {
            const point preview_half_tiles(
                tile_draw_width / draw_tiles->get_tile_width() / 2,
                tile_draw_height / draw_tiles->get_tile_height() / 2 );
            const point_rel_ms legacy_center_compensation(
                POSX - preview_half_tiles.x, POSY - preview_half_tiles.y );
            tile_draw_center += tripoint_rel_ms( legacy_center_compensation, 0 );
        }
'''
if text.count(old) != 1:
    raise SystemExit(f"draw geometry block expected once, found {text.count(old)}")
text = text.replace(old, new, 1)
old_log = '''                DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_RENDER] draw center=("
                                          << tile_draw_center.x() << "," << tile_draw_center.y() << ","
                                          << tile_draw_center.z() << ") scale=" << map_preview_draw_scale
                                          << " pos=(" << tile_draw_pos.x << "," << tile_draw_pos.y << ")"
                                          << " size=(" << tile_draw_width << "," << tile_draw_height << ")"
                                          << " tile_size=(" << draw_tiles->get_tile_width() << ","
                                          << draw_tiles->get_tile_height() << ")";
'''
new_log = '''                DebugLog( D_INFO, D_MAIN ) << "[VEH_LIVE_RENDER] draw logical_center=("
                                          << logical_tile_draw_center.x() << ","
                                          << logical_tile_draw_center.y() << ","
                                          << logical_tile_draw_center.z() << ") renderer_center=("
                                          << tile_draw_center.x() << "," << tile_draw_center.y() << ","
                                          << tile_draw_center.z() << ") scale=" << map_preview_draw_scale
                                          << " pos=(" << tile_draw_pos.x << "," << tile_draw_pos.y << ")"
                                          << " size=(" << tile_draw_width << "," << tile_draw_height << ")"
                                          << " tile_size=(" << draw_tiles->get_tile_width() << ","
                                          << draw_tiles->get_tile_height() << ")";
'''
if text.count(old_log) != 1:
    raise SystemExit(f"render diagnostic block expected once, found {text.count(old_log)}")
text = text.replace(old_log, new_log, 1)
path.write_text(text)
