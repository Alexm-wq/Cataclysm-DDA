from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)

cata_h = Path("src/cata_tiles.h")
cata_cpp = Path("src/cata_tiles.cpp")
sdl_h = Path("src/sdltiles.h")
sdl_cpp = Path("src/sdltiles.cpp")
veh_cpp = Path("src/veh_interact.cpp")

h = cata_h.read_text()
c = cata_cpp.read_text()
sh = sdl_h.read_text()
sc = sdl_cpp.read_text()
vc = veh_cpp.read_text()

h = replace_once(
    h,
'''        int get_draw_scale() const {
            return draw_scale;
        }
        // Current viewport size in renderer tile-grid coordinates.  Weather uses
''',
'''        int get_draw_scale() const {
            return draw_scale;
        }
        // Resolve a pixel coordinate inside an arbitrary map-render window to the
        // corresponding map square using this tileset's real projection.
        point_bub_ms screen_to_map( const point &scr_pos, const point &win_size,
                                    const point_bub_ms &center ) const;
        // Current viewport size in renderer tile-grid coordinates.  Weather uses
''',
    "cata tiles public screen transform",
)

c = replace_once(
    c,
'''point_bub_ms cata_tiles::screen_to_player(
''',
'''point_bub_ms cata_tiles::screen_to_map( const point &scr_pos, const point &win_size,
        const point_bub_ms &center ) const
{
    return screen_to_player( scr_pos, point( tile_width, tile_height ), win_size, center,
                             is_isometric() );
}

point_bub_ms cata_tiles::screen_to_player(
''',
    "cata tiles screen transform implementation",
)

sh = replace_once(
    sh,
'''void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center,
                             int draw_scale = 16 );
void clear_map_preview_window();
''',
'''void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center,
                             int draw_scale = 16 );
void clear_map_preview_window();
// Resolve a terminal-cell position inside an auxiliary preview window to the
// map square rendered there at the supplied center/scale.
std::optional<tripoint_bub_ms> map_preview_cell_to_map( const catacurses::window &win,
        const point &cell, const tripoint_bub_ms &center, int draw_scale );
''',
    "sdl preview transform declaration",
)

sc = replace_once(
    sc,
'''void clear_map_preview_window()
{
    map_preview_window = nullptr;
    map_preview_center.reset();
    map_preview_draw_scale = 16;
}
''',
'''void clear_map_preview_window()
{
    map_preview_window = nullptr;
    map_preview_center.reset();
    map_preview_draw_scale = 16;
}

std::optional<tripoint_bub_ms> map_preview_cell_to_map( const catacurses::window &win,
        const point &cell, const tripoint_bub_ms &center, const int draw_scale )
{
    if( !win ) {
        return std::nullopt;
    }
    std::shared_ptr<cata_tiles> draw_tiles = closetilecontext ? closetilecontext : tilecontext;
    if( !draw_tiles ) {
        return std::nullopt;
    }

    const window_dimensions dim = get_window_dimensions( win );
    if( cell.x < 0 || cell.y < 0 || cell.x >= dim.window_size_cell.x ||
        cell.y >= dim.window_size_cell.y ) {
        return std::nullopt;
    }

    // Input coordinates are terminal cells while cata_tiles works in pixels.
    // Use the cell center so the transform is stable and still follows the same
    // isometric/non-isometric projection used for the actual preview draw.
    const point pixel( cell.x * dim.scaled_font_size.x + dim.scaled_font_size.x / 2,
                       cell.y * dim.scaled_font_size.y + dim.scaled_font_size.y / 2 );
    const int previous_draw_scale = draw_tiles->get_draw_scale();
    if( previous_draw_scale != draw_scale ) {
        draw_tiles->set_draw_scale( draw_scale );
    }
    const point_bub_ms mapped = draw_tiles->screen_to_map( pixel, dim.window_size_pixel, center.xy() );
    if( draw_tiles->get_draw_scale() != previous_draw_scale ) {
        draw_tiles->set_draw_scale( previous_draw_scale );
    }
    return tripoint_bub_ms( mapped, center.z() );
}
''',
    "sdl preview transform implementation",
)

vc = replace_once(
    vc,
'''    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );
''',
'''    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );
#if defined(TILES)
    const std::optional<point> live_preview_pos = active_editor_view_mode == editor_view_mode::live ?
            mouse_pos_in( w_live_preview_full ) :
            active_editor_view_mode == editor_view_mode::split ? mouse_pos_in( w_live_preview_split ) :
            std::nullopt;
#endif
''',
    "vehicle preview local mouse position",
)

vc = replace_once(
    vc,
'''        if( over_live_preview ) {
            // Live preview deliberately has the same finite editor range and
            // never cycles into the normal game's extreme zoom-out levels.
            live_preview_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );
            return true;
        }
''',
'''        if( over_live_preview ) {
            // Live preview deliberately has the same finite editor range and
            // never cycles into the normal game's extreme zoom-out levels.  Keep
            // the rendered map square under the mouse fixed while changing scale,
            // matching normal map/editor cursor-relative zoom behavior.
#if defined(TILES)
            catacurses::window &preview = active_editor_view_mode == editor_view_mode::live ?
                                          w_live_preview_full : w_live_preview_split;
            const int old_zoom = live_preview_zoom;
            const int new_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );
            if( new_zoom != old_zoom && live_preview_pos ) {
                const tripoint_bub_ms vehicle_center = live_preview_vehicle_center( here );
                const tripoint_bub_ms current_center = vehicle_center +
                        tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );
                const std::optional<tripoint_bub_ms> before = map_preview_cell_to_map(
                            preview, *live_preview_pos, current_center, old_zoom * 8 );
                live_preview_zoom = new_zoom;
                const std::optional<tripoint_bub_ms> after = map_preview_cell_to_map(
                            preview, *live_preview_pos, current_center, new_zoom * 8 );
                if( before && after ) {
                    live_preview_pan += ( *before - *after ).xy().raw();
                }
            } else {
                live_preview_zoom = new_zoom;
            }
#else
            live_preview_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );
#endif
            return true;
        }
''',
    "vehicle live zoom anchoring",
)

cata_h.write_text(h)
cata_cpp.write_text(c)
sdl_h.write_text(sh)
sdl_cpp.write_text(sc)
veh_cpp.write_text(vc)
