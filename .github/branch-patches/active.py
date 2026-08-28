from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Pixel overlays are drawn as part of their parent's render pass, but their mere
# existence must not mark that parent dirty. The parent's own curses/tile update
# or an explicit overlay-state change is what should schedule presentation.
replace_once(
    "src/sdltiles.cpp",
    '''    if( draw_ui_pixel_icon_buttons( win ) ) {\n        update = true;\n    }\n    if( update ) {\n        needupdate = true;\n    }\n''',
    '''    draw_ui_pixel_icon_buttons( win );\n    if( update ) {\n        needupdate = true;\n    }\n'''
)

# Hover updates should expose whether the visual state actually changed. Existing
# callers can ignore the return value, so this is source-compatible with all other
# menus using ui_icon_button.
replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void update_hover( const std::optional<point> &parent_pos ) {\n            hovered_ = parent_pos && contains( *parent_pos );\n        }\n''',
    '''        bool update_hover( const std::optional<point> &parent_pos ) {\n            const bool next_hovered = parent_pos && contains( *parent_pos );\n            if( next_hovered == hovered_ ) {\n                return false;\n            }\n            hovered_ = next_hovered;\n            return true;\n        }\n'''
)
replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void update_hover_pixel( const std::optional<point> &screen_pixel ) {\n            hovered_ = screen_pixel && contains_pixel( *screen_pixel );\n        }\n''',
    '''        bool update_hover_pixel( const std::optional<point> &screen_pixel ) {\n            const bool next_hovered = screen_pixel && contains_pixel( *screen_pixel );\n            if( next_hovered == hovered_ ) {\n                return false;\n            }\n            hovered_ = next_hovered;\n            return true;\n        }\n'''
)

# Safemode HUD hover redraws are now edge-triggered: moving within the same button
# no longer invalidates anything. Only entering/leaving a button or changing the
# delayed tooltip visibility causes a UI redraw.
replace_once(
    "src/game.cpp",
    '''    bool tooltip_changed = false;\n\n    if( action == "TIMEOUT" ) {\n        tooltip_changed = safemode_corner_tooltip.tick();\n#if defined(TILES)\n    } else if( pixel_mouse_pos ) {\n        safemode_corner_launcher.handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );\n        if( safemode_corner_expanded ) {\n            for( ui_icon_button &button : safemode_corner_buttons ) {\n                button.handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );\n            }\n            for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n                button->handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );\n            }\n            tooltip_changed = mouse_pos ? safemode_corner_tooltip.update_pointer( mouse_pos ) :\n                              safemode_corner_tooltip.clear_pointer();\n        } else {\n            tooltip_changed = safemode_corner_tooltip.clear_pointer();\n        }\n#else\n    } else if( mouse_pos ) {\n        safemode_corner_launcher.handle_input( "MOUSE_MOVE", mouse_pos );\n        if( safemode_corner_expanded ) {\n            for( ui_icon_button &button : safemode_corner_buttons ) {\n                button.handle_input( "MOUSE_MOVE", mouse_pos );\n            }\n            for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n                button->handle_input( "MOUSE_MOVE", mouse_pos );\n            }\n            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );\n        } else {\n            tooltip_changed = safemode_corner_tooltip.clear_pointer();\n        }\n#endif\n    } else if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ) {\n#if defined(TILES)\n        safemode_corner_launcher.update_hover_pixel( std::nullopt );\n        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.update_hover_pixel( std::nullopt );\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            button->update_hover_pixel( std::nullopt );\n        }\n#else\n        safemode_corner_launcher.update_hover( std::nullopt );\n        for( ui_icon_button &button : safemode_corner_buttons ) {\n            button.update_hover( std::nullopt );\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            button->update_hover( std::nullopt );\n        }\n#endif\n        tooltip_changed = safemode_corner_tooltip.clear_pointer();\n    }\n\n    if( tooltip_changed ) {\n        invalidate_main_ui_adaptor();\n        if( action == "TIMEOUT" ) {\n            ui_manager::redraw();\n        }\n    }\n''',
    '''    bool tooltip_changed = false;\n    bool hover_changed = false;\n\n    if( action == "TIMEOUT" ) {\n        tooltip_changed = safemode_corner_tooltip.tick();\n#if defined(TILES)\n    } else if( pixel_mouse_pos ) {\n        hover_changed |= safemode_corner_launcher.update_hover_pixel( pixel_mouse_pos );\n        if( safemode_corner_expanded ) {\n            for( ui_icon_button &button : safemode_corner_buttons ) {\n                hover_changed |= button.update_hover_pixel( pixel_mouse_pos );\n            }\n            for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n                hover_changed |= button->update_hover_pixel( pixel_mouse_pos );\n            }\n            tooltip_changed = mouse_pos ? safemode_corner_tooltip.update_pointer( mouse_pos ) :\n                              safemode_corner_tooltip.clear_pointer();\n        } else {\n            tooltip_changed = safemode_corner_tooltip.clear_pointer();\n        }\n#else\n    } else if( mouse_pos ) {\n        hover_changed |= safemode_corner_launcher.update_hover( mouse_pos );\n        if( safemode_corner_expanded ) {\n            for( ui_icon_button &button : safemode_corner_buttons ) {\n                hover_changed |= button.update_hover( mouse_pos );\n            }\n            for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n                hover_changed |= button->update_hover( mouse_pos );\n            }\n            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );\n        } else {\n            tooltip_changed = safemode_corner_tooltip.clear_pointer();\n        }\n#endif\n    } else if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ) {\n#if defined(TILES)\n        hover_changed |= safemode_corner_launcher.update_hover_pixel( std::nullopt );\n        for( ui_icon_button &button : safemode_corner_buttons ) {\n            hover_changed |= button.update_hover_pixel( std::nullopt );\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            hover_changed |= button->update_hover_pixel( std::nullopt );\n        }\n#else\n        hover_changed |= safemode_corner_launcher.update_hover( std::nullopt );\n        for( ui_icon_button &button : safemode_corner_buttons ) {\n            hover_changed |= button.update_hover( std::nullopt );\n        }\n        for( const std::unique_ptr<ui_icon_button> &button : safemode_corner_extra_buttons ) {\n            hover_changed |= button->update_hover( std::nullopt );\n        }\n#endif\n        tooltip_changed = safemode_corner_tooltip.clear_pointer();\n    }\n\n    if( hover_changed || tooltip_changed ) {\n        invalidate_main_ui_adaptor();\n        if( action == "TIMEOUT" ) {\n            ui_manager::redraw();\n        }\n    }\n'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Stop pixel HUD redraw feedback loop\n", encoding="utf-8"
)
