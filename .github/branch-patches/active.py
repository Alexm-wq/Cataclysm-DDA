from pathlib import Path


def replace_exact(path: Path, label: str, old: str, new: str, expected: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} match(es), found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


crafting = Path("src/crafting_gui.cpp")
replace_exact(
    crafting,
    "remaining inspector scroll integer assignments",
    "            state.inspector_scroll = 0;",
    "            state.inspector_scroll.scroll_to_start();",
    expected=2,
)

vehicle = Path("src/veh_interact.cpp")
replace_exact(
    vehicle,
    "reopen refuel overlay",
    """    refuel_info = std::make_unique<refuel_info_t>();
    for( const vpart_reference &ref : veh->get_all_parts() ) {""",
    """    refuel_info = std::make_unique<refuel_info_t>();

    // close_refuel_mode() closes the overlay window itself.  Window geometry is
    // normally established during editor layout, so reopening the modal without
    // a resize would otherwise leave refuel_info alive while display_refuel_pane()
    // rejects the closed overlay.  Re-establish the modal geometry every time the
    // refuel workflow is opened.
    const int refuel_overlay_w = std::min( grid_w, std::clamp( grid_w * 55 / 100, 36, 64 ) );
    const int refuel_overlay_h = std::min( page_size, std::clamp( page_size - 2, 12, 20 ) );
    refuel_overlay.configure( w_border,
                              point( grid.x + std::max( 0, ( grid_w - refuel_overlay_w ) / 2 ),
                                     pane_y + std::max( 0, ( page_size - refuel_overlay_h ) / 2 ) ),
                              refuel_overlay_w, refuel_overlay_h );

    for( const vpart_reference &ref : veh->get_all_parts() ) {""",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix crafting scroll migration and refuel reopen\n", encoding="utf-8"
)
