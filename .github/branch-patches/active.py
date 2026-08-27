from pathlib import Path


def replace_exact(path: Path, label: str, old: str, new: str, expected: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} match(es), found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


overlay = Path("src/ui_helpers/primitive/overlay.h")
replace_exact(
    overlay,
    "overlay visibility lifecycle",
    """        void close() {
            window_ = catacurses::window();
            pos_ = point::zero;
            width_ = 0;
            height_ = 0;
        }

        bool is_open() const {
            return width_ > 0 && height_ > 0;
        }
""",
    """        void close() {
            window_ = catacurses::window();
            pos_ = point::zero;
            width_ = 0;
            height_ = 0;
            visible_ = false;
        }

        /** Hide the overlay while retaining its configured geometry for reuse. */
        void hide() {
            window_ = catacurses::window();
            visible_ = false;
        }

        /** Re-show a previously configured overlay without duplicating layout math. */
        void show() {
            visible_ = width_ > 0 && height_ > 0;
        }

        bool is_open() const {
            return visible_ && width_ > 0 && height_ > 0;
        }
""",
)
replace_exact(
    overlay,
    "configure marks overlay visible",
    """            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height - height_ ) );
            pos_ = pos;
        }
""",
    """            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height - height_ ) );
            pos_ = pos;
            visible_ = true;
        }
""",
)
replace_exact(
    overlay,
    "overlay visible member",
    """        int width_ = 0;
        int height_ = 0;
};
""",
    """        int width_ = 0;
        int height_ = 0;
        bool visible_ = false;
};
""",
)

vehicle = Path("src/veh_interact.cpp")
replace_exact(
    vehicle,
    "remove duplicated refuel overlay geometry",
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

    for( const vpart_reference &ref : veh->get_all_parts() ) {
""",
    """    refuel_info = std::make_unique<refuel_info_t>();
    refuel_overlay.show();

    for( const vpart_reference &ref : veh->get_all_parts() ) {
""",
)
replace_exact(
    vehicle,
    "hide refuel overlay on modal close",
    """void veh_interact::close_refuel_mode()
{
    refuel_info.reset();
    refuel_overlay.close();
    msg.reset();
}
""",
    """void veh_interact::close_refuel_mode()
{
    refuel_info.reset();
    refuel_overlay.hide();
    msg.reset();
}
""",
)
replace_exact(
    vehicle,
    "hide refuel overlay across activity handoff",
    """    refuel_info.reset();
    refuel_overlay.close();
    refill_target = item_location();
""",
    """    refuel_info.reset();
    refuel_overlay.hide();
    refill_target = item_location();
""",
)

crafting = Path("src/crafting_gui.cpp")
text = crafting.read_text(encoding="utf-8")
for forbidden in (
    "state.inspector_scroll =",
    "state.recipe_scroll =",
    "state.category_scroll =",
):
    if forbidden in text:
        raise SystemExit(f"stale ui_scroll_model assignment remains: {forbidden}")

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix reusable overlay reopen lifecycle\n", encoding="utf-8"
)
