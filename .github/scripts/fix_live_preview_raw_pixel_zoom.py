from pathlib import Path


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1))


h = Path("src/sdltiles.h")
replace_exact(
    h,
    """// Resolve a terminal-cell position inside an auxiliary preview window to the
// map square rendered there at the supplied center/scale.
std::optional<tripoint_bub_ms> map_preview_cell_to_map( const catacurses::window &win,
        const point &cell, const tripoint_bub_ms &center, int draw_scale );
""",
    """// Resolve a raw pixel offset from an auxiliary preview window's origin to the
// map square rendered there at the supplied center/scale.  This intentionally
// matches the pixel-space path used by input_context::get_coordinates().
std::optional<tripoint_bub_ms> map_preview_pixel_to_map( const catacurses::window &win,
        const point &pixel, const tripoint_bub_ms &center, int draw_scale );
""",
    "sdltiles.h helper declaration",
)

cpp = Path("src/sdltiles.cpp")
text = cpp.read_text()
start_marker = "std::optional<tripoint_bub_ms> map_preview_cell_to_map( const catacurses::window &win,\n"
end_marker = "\nvoid cata_cursesport::curses_drawwindow( const catacurses::window &w )"
if text.count(start_marker) != 1:
    raise SystemExit(f"sdltiles.cpp old helper count={text.count(start_marker)}")
start = text.index(start_marker)
end = text.index(end_marker, start)
replacement = """std::optional<tripoint_bub_ms> map_preview_pixel_to_map( const catacurses::window &win,
        const point &pixel, const tripoint_bub_ms &center, const int draw_scale )
{
    if( !win ) {
        return std::nullopt;
    }
    std::shared_ptr<cata_tiles> draw_tiles = closetilecontext ? closetilecontext : tilecontext;
    if( !draw_tiles ) {
        return std::nullopt;
    }

    const window_dimensions dim = get_window_dimensions( win );
    const half_open_rectangle<point> pixel_bounds( point::zero, dim.window_size_pixel );
    if( !pixel_bounds.contains( pixel ) ) {
        return std::nullopt;
    }

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
"""
cpp.write_text(text[:start] + replacement + text[end:])

v = Path("src/veh_interact.cpp")
replace_exact(
    v,
    """            std::optional<tripoint_bub_ms> zoom_anchor;
            const tripoint_bub_ms old_center = live_preview_vehicle_center( here ) +
                    tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );
            if( action == \"SCROLL_UP\" && new_zoom > old_zoom && live_preview_pos ) {
                zoom_anchor = map_preview_cell_to_map( preview, *live_preview_pos, old_center,
                                                       old_zoom * 8 );
            }
""",
    """            std::optional<tripoint_bub_ms> zoom_anchor;
            const tripoint_bub_ms old_center = live_preview_vehicle_center( here ) +
                    tripoint_rel_ms( point_rel_ms( live_preview_pan ), 0 );
            if( action == \"SCROLL_UP\" && new_zoom > old_zoom ) {
                // Normal gameplay zoom anchors from the raw SDL mouse pixel, not
                // from a quantized curses cell.  Preserve the existing pane
                // routing above, then convert that same raw coordinate into this
                // preview window's local pixel space.
                const input_event raw_input = main_context.get_raw_input();
                if( raw_input.type == input_event_t::mouse ) {
                    const window_dimensions dim = get_window_dimensions( preview );
                    const point local_pixel = raw_input.mouse_pos - dim.window_pos_pixel;
                    zoom_anchor = map_preview_pixel_to_map( preview, local_pixel, old_center,
                                                           old_zoom * 8 );
                }
            }
""",
    "veh_interact zoom anchor",
)

replace_exact(
    v,
    """#if defined(TILES)
    const std::optional<point> live_preview_pos = active_editor_view_mode == editor_view_mode::live ?
            mouse_pos_in( w_live_preview_full ) :
            active_editor_view_mode == editor_view_mode::split ? mouse_pos_in( w_live_preview_split ) :
            std::nullopt;
#endif
""",
    "",
    "veh_interact obsolete live_preview_pos",
)
