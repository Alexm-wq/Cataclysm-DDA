from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:180]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path_str: str, start: str, end: str, replacement: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    i = text.find(start)
    if i < 0:
        raise SystemExit(f"start anchor not found in {path_str}: {start!r}")
    j = text.find(end, i)
    if j < 0:
        raise SystemExit(f"end anchor not found in {path_str}: {end!r}")
    path.write_text(text[:i] + replacement + text[j:], encoding="utf-8")


# The WINDOW-owned experiment cannot work for the minimap HUD because that
# backing WINDOW is ephemeral.  Remove the temporary per-window icon storage;
# pixel icon buttons return to a backend registry, but their z-layer is keyed by
# stable parent geometry rather than raw WINDOW* identity.
replace_once(
    "src/cursesport.h",
    '''\n// Pixel-space icon/button overlay drawn as part of its owning curses window.\n// Keeping this on WINDOW gives it the same lifetime and z-order semantics as\n// the existing pixel scrollbar overlay, without relying on WINDOW* identity.\nstruct pixel_icon_button_overlay {\n    const void *owner = nullptr;\n    point pos_pixels = point::zero;\n    point size_pixels = point::zero;\n    int border_color_pair = 0;\n    int fill_color_pair = 0;\n    int icon_color_pair = 0;\n    std::string icon;\n};\n''',
    ''
)
replace_once(
    "src/cursesport.h",
    '''    std::vector<pixel_scrollbar_overlay> pixel_scrollbars;\n    std::vector<pixel_icon_button_overlay> pixel_icon_buttons;\n''',
    '''    std::vector<pixel_scrollbar_overlay> pixel_scrollbars;\n'''
)

# The public overlay describes only the control itself.  Layer geometry is
# derived by the SDL backend from the parent supplied to set_ui_pixel_icon_button().
replace_once(
    "src/sdltiles.h",
    '''struct ui_pixel_icon_button_overlay {\n    const void *owner = nullptr;\n    const void *parent = nullptr;\n''',
    '''struct ui_pixel_icon_button_overlay {\n    const void *owner = nullptr;\n'''
)

# No weak-parent tracking is needed anymore.
replace_once( "src/sdltiles.cpp", "#include <unordered_map>\n", "" )

replace_between(
    "src/sdltiles.cpp",
    "static std::unordered_map<const void *, std::weak_ptr<void>> ui_pixel_icon_button_parents;\n",
    "static std::ofstream &pixel_hud_debug_stream()\n",
    '''struct ui_pixel_icon_button_layered_overlay {\n    ui_pixel_icon_button_overlay button;\n    point parent_pos_cell = point::zero;\n    point parent_size_cell = point::zero;\n};\n\nstatic std::vector<ui_pixel_icon_button_layered_overlay> ui_pixel_icon_buttons;\n\nstruct ui_pixel_button_debug_stats {\n    uint64_t set_calls = 0;\n    uint64_t registrations = 0;\n    uint64_t layer_updates = 0;\n    uint64_t visual_updates = 0;\n    uint64_t clear_calls = 0;\n    uint64_t clear_removed = 0;\n    uint64_t draw_calls = 0;\n    uint64_t matched_draw_calls = 0;\n    uint64_t drawn_buttons = 0;\n    uint64_t summary_sequence = 0;\n    uint32_t last_summary_tick = 0;\n};\n\nstatic ui_pixel_button_debug_stats ui_pixel_button_debug;\n\n'''
)

# Replace the summary implementation so the retained diagnostics report stable
# geometry matching rather than now-removed parent pointer switching.
replace_between(
    "src/sdltiles.cpp",
    "static void maybe_log_ui_pixel_button_summary( const char *site )\n",
    "static Font_Ptr font;\n",
    r'''static void maybe_log_ui_pixel_button_summary( const char *site )
{
    const uint32_t now = SDL_GetTicks();
    if( ui_pixel_button_debug.last_summary_tick == 0 ) {
        ui_pixel_button_debug.last_summary_tick = now;
        return;
    }
    if( now - ui_pixel_button_debug.last_summary_tick < 1000 ) {
        return;
    }
    ++ui_pixel_button_debug.summary_sequence;
    std::ofstream &stream = pixel_hud_debug_stream();
    if( stream ) {
        stream << now << " [pixel-hud] summary #" << ui_pixel_button_debug.summary_sequence
               << " site=" << site
               << " registry=" << ui_pixel_icon_buttons.size()
               << " set=" << ui_pixel_button_debug.set_calls
               << " register=" << ui_pixel_button_debug.registrations
               << " layer_update=" << ui_pixel_button_debug.layer_updates
               << " visual_update=" << ui_pixel_button_debug.visual_updates
               << " clear=" << ui_pixel_button_debug.clear_calls
               << " removed=" << ui_pixel_button_debug.clear_removed
               << " draw_calls=" << ui_pixel_button_debug.draw_calls
               << " matched_draw=" << ui_pixel_button_debug.matched_draw_calls
               << " drawn_buttons=" << ui_pixel_button_debug.drawn_buttons << '\n';
        stream.flush();
    }
    ui_pixel_button_debug.set_calls = 0;
    ui_pixel_button_debug.registrations = 0;
    ui_pixel_button_debug.layer_updates = 0;
    ui_pixel_button_debug.visual_updates = 0;
    ui_pixel_button_debug.clear_calls = 0;
    ui_pixel_button_debug.clear_removed = 0;
    ui_pixel_button_debug.draw_calls = 0;
    ui_pixel_button_debug.matched_draw_calls = 0;
    ui_pixel_button_debug.drawn_buttons = 0;
    ui_pixel_button_debug.last_summary_tick = now;
}

void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay,
                               const catacurses::window &parent )
{
    ++ui_pixel_button_debug.set_calls;
    if( overlay.owner == nullptr || !parent ) {
        maybe_log_ui_pixel_button_summary( "set-rejected" );
        return;
    }
    const cata_cursesport::WINDOW *const win = parent.get<cata_cursesport::WINDOW>();
    if( win == nullptr ) {
        maybe_log_ui_pixel_button_summary( "set-no-window" );
        return;
    }

    const point parent_pos = win->pos;
    const point parent_size( win->width, win->height );
    const auto found = std::find_if( ui_pixel_icon_buttons.begin(), ui_pixel_icon_buttons.end(),
    [&]( const ui_pixel_icon_button_layered_overlay & existing ) {
        return existing.button.owner == overlay.owner;
    } );

    if( found == ui_pixel_icon_buttons.end() ) {
        ui_pixel_icon_buttons.push_back( { overlay, parent_pos, parent_size } );
        ++ui_pixel_button_debug.registrations;
        maybe_log_ui_pixel_button_summary( "set-register" );
        return;
    }

    const bool layer_unchanged = found->parent_pos_cell == parent_pos &&
                                 found->parent_size_cell == parent_size;
    const bool visual_unchanged = found->button.pos_pixels == overlay.pos_pixels &&
                                  found->button.size_pixels == overlay.size_pixels &&
                                  found->button.border_color_pair == overlay.border_color_pair &&
                                  found->button.fill_color_pair == overlay.fill_color_pair &&
                                  found->button.icon_color_pair == overlay.icon_color_pair &&
                                  found->button.icon == overlay.icon;
    if( !layer_unchanged ) {
        found->parent_pos_cell = parent_pos;
        found->parent_size_cell = parent_size;
        ++ui_pixel_button_debug.layer_updates;
    }
    if( !visual_unchanged ) {
        found->button = overlay;
        ++ui_pixel_button_debug.visual_updates;
    }
    maybe_log_ui_pixel_button_summary( layer_unchanged && visual_unchanged ?
                                       "set-unchanged" : "set-update" );
}

void clear_ui_pixel_icon_button( const void *owner )
{
    ++ui_pixel_button_debug.clear_calls;
    if( owner == nullptr ) {
        maybe_log_ui_pixel_button_summary( "clear-null" );
        return;
    }
    const size_t before = ui_pixel_icon_buttons.size();
    const auto new_end = std::remove_if( ui_pixel_icon_buttons.begin(), ui_pixel_icon_buttons.end(),
    [&]( const ui_pixel_icon_button_layered_overlay & existing ) {
        return existing.button.owner == owner;
    } );
    ui_pixel_icon_buttons.erase( new_end, ui_pixel_icon_buttons.end() );
    ui_pixel_button_debug.clear_removed += before - ui_pixel_icon_buttons.size();
    maybe_log_ui_pixel_button_summary( before == ui_pixel_icon_buttons.size() ?
                                       "clear-miss" : "clear-removed" );
}

static Font_Ptr font;
'''
)

# Geometry-layer draw: whichever ephemeral curses WINDOW currently represents
# the same logical parent rectangle gets the overlay.  Later menu windows still
# render afterward and cover the HUD naturally.
replace_between(
    "src/sdltiles.cpp",
    "static bool draw_ui_pixel_icon_buttons( const cata_cursesport::WINDOW *parent )\n",
    "void refresh_display()\n",
    r'''static bool draw_ui_pixel_icon_buttons( const cata_cursesport::WINDOW *parent )
{
    ++ui_pixel_button_debug.draw_calls;
    if( parent == nullptr ) {
        maybe_log_ui_pixel_button_summary( "draw-null" );
        return false;
    }

    const point parent_pos = parent->pos;
    const point parent_size( parent->width, parent->height );
    bool drew = false;
    size_t matched = 0;
    for( const ui_pixel_icon_button_layered_overlay &layered : ui_pixel_icon_buttons ) {
        if( layered.parent_pos_cell != parent_pos || layered.parent_size_cell != parent_size ) {
            continue;
        }
        const ui_pixel_icon_button_overlay &button = layered.button;
        if( button.owner == nullptr || button.size_pixels.x < 3 || button.size_pixels.y < 3 ) {
            continue;
        }
        drew = true;
        ++matched;

        const SDL_Color border = ui_pixel_button_color( button.border_color_pair );
        const SDL_Color fill = ui_pixel_button_color( button.fill_color_pair );
        const SDL_Color icon = ui_pixel_button_color( button.icon_color_pair );
        const int border_width = std::max( 1, std::min( button.size_pixels.x,
                                      button.size_pixels.y ) / 16 );

        SDL_Rect outer = { button.pos_pixels.x, button.pos_pixels.y,
                           button.size_pixels.x, button.size_pixels.y };
        SetRenderDrawColor( renderer, border.r, border.g, border.b, 255 );
        RenderFillRect( renderer, &outer );

        if( button.size_pixels.x > border_width * 2 &&
            button.size_pixels.y > border_width * 2 ) {
            SDL_Rect inner = { button.pos_pixels.x + border_width,
                               button.pos_pixels.y + border_width,
                               button.size_pixels.x - border_width * 2,
                               button.size_pixels.y - border_width * 2 };
            SetRenderDrawColor( renderer, fill.r, fill.g, fill.b, 255 );
            RenderFillRect( renderer, &inner );
        }

        draw_ui_pixel_button_bitmap( button, icon );
    }
    if( matched > 0 ) {
        ++ui_pixel_button_debug.matched_draw_calls;
        ui_pixel_button_debug.drawn_buttons += matched;
    }
    maybe_log_ui_pixel_button_summary( drew ? "draw-matched" : "draw-empty" );
    return drew;
}

void refresh_display()
'''
)

# Update the diagnostic banner so a submitted log clearly identifies this build.
replace_once(
    "src/sdltiles.cpp",
    'stream << "pixel HUD diagnostics started (window-owned overlays)\\n";',
    'stream << "pixel HUD diagnostics started (geometry-layer overlays)\\n";'
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Use stable geometry layers for pixel HUD overlays\n", encoding="utf-8"
)
