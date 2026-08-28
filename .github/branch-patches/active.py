from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one block in {path_str}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Pixel icon controls belong to the curses WINDOW that owns their layer, just
# like pixel scrollbars.  A WINDOW may be recreated frequently; keeping the
# overlay inside it makes that churn irrelevant to rendering and z-order.
replace_once(
    "src/cursesport.h",
    '''struct pixel_scrollbar_overlay {\n    const void *owner = nullptr;\n    int x_cell = 0;\n    int track_top_px = 0;\n    int track_height_px = 0;\n    int thumb_top_px = 0;\n    int thumb_height_px = 0;\n    bool dragging = false;\n};\n''',
    '''struct pixel_scrollbar_overlay {\n    const void *owner = nullptr;\n    int x_cell = 0;\n    int track_top_px = 0;\n    int track_height_px = 0;\n    int thumb_top_px = 0;\n    int thumb_height_px = 0;\n    bool dragging = false;\n};\n\n// Pixel-space icon/button overlay drawn as part of its owning curses window.\n// Keeping this on WINDOW gives it the same lifetime and z-order semantics as\n// the existing pixel scrollbar overlay, without relying on WINDOW* identity.\nstruct pixel_icon_button_overlay {\n    const void *owner = nullptr;\n    point pos_pixels = point::zero;\n    point size_pixels = point::zero;\n    int border_color_pair = 0;\n    int fill_color_pair = 0;\n    int icon_color_pair = 0;\n    std::string icon;\n};\n'''
)

replace_once(
    "src/cursesport.h",
    '''    std::vector<curseline> line;\n    std::vector<pixel_scrollbar_overlay> pixel_scrollbars;\n};\n''',
    '''    std::vector<curseline> line;\n    std::vector<pixel_scrollbar_overlay> pixel_scrollbars;\n    std::vector<pixel_icon_button_overlay> pixel_icon_buttons;\n};\n'''
)

# The SDL backend now stores only a weak cleanup association by owner. Rendering
# reads the overlays directly from each WINDOW, so changing backing pointers can
# never make a globally registered control hop between layers.
path = Path("src/sdltiles.cpp")
text = path.read_text(encoding="utf-8")
text = text.replace('#include <type_traits>\n#include <vector>\n',
                    '#include <type_traits>\n#include <unordered_map>\n#include <vector>\n', 1)
start = text.find('static std::vector<ui_pixel_icon_button_overlay> ui_pixel_icon_buttons;')
end = text.find('static Font_Ptr font;', start)
if start < 0 or end < 0 or end <= start:
    raise SystemExit('could not locate pixel HUD registry/debug block in sdltiles.cpp')
replacement = r'''static std::unordered_map<const void *, std::weak_ptr<void>> ui_pixel_icon_button_parents;

struct ui_pixel_button_debug_stats {
    uint64_t set_calls = 0;
    uint64_t parent_switches = 0;
    uint64_t registrations = 0;
    uint64_t visual_updates = 0;
    uint64_t clear_calls = 0;
    uint64_t clear_removed = 0;
    uint64_t draw_calls = 0;
    uint64_t drawn_buttons = 0;
    uint64_t summary_sequence = 0;
    uint32_t last_summary_tick = 0;
};

static ui_pixel_button_debug_stats ui_pixel_button_debug;

static std::ofstream &pixel_hud_debug_stream()
{
    static std::ofstream stream;
    static bool initialized = false;
    if( !initialized ) {
        initialized = true;
        std::string directory = PATH_INFO::config_dir();
        if( !directory.empty() && directory.back() != '/' && directory.back() != '\\' ) {
            directory.push_back( '/' );
        }
        stream.open( directory + "pixel_hud_debug.log", std::ios::out | std::ios::trunc );
        if( !stream ) {
            stream.clear();
            stream.open( "pixel_hud_debug.log", std::ios::out | std::ios::trunc );
        }
        if( stream ) {
            stream << "pixel HUD diagnostics started (window-owned overlays)\n";
            stream.flush();
        }
    }
    return stream;
}

static void maybe_log_ui_pixel_button_summary( const char *site )
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
               << " tracked_owners=" << ui_pixel_icon_button_parents.size()
               << " set=" << ui_pixel_button_debug.set_calls
               << " parent_switch=" << ui_pixel_button_debug.parent_switches
               << " register=" << ui_pixel_button_debug.registrations
               << " visual_update=" << ui_pixel_button_debug.visual_updates
               << " clear=" << ui_pixel_button_debug.clear_calls
               << " removed=" << ui_pixel_button_debug.clear_removed
               << " draw_calls=" << ui_pixel_button_debug.draw_calls
               << " drawn_buttons=" << ui_pixel_button_debug.drawn_buttons << '\n';
        stream.flush();
    }
    ui_pixel_button_debug.set_calls = 0;
    ui_pixel_button_debug.parent_switches = 0;
    ui_pixel_button_debug.registrations = 0;
    ui_pixel_button_debug.visual_updates = 0;
    ui_pixel_button_debug.clear_calls = 0;
    ui_pixel_button_debug.clear_removed = 0;
    ui_pixel_button_debug.draw_calls = 0;
    ui_pixel_button_debug.drawn_buttons = 0;
    ui_pixel_button_debug.last_summary_tick = now;
}

static void erase_pixel_icon_button_from_window( cata_cursesport::WINDOW *win, const void *owner )
{
    if( win == nullptr || owner == nullptr ) {
        return;
    }
    const auto new_end = std::remove_if( win->pixel_icon_buttons.begin(), win->pixel_icon_buttons.end(),
    [&]( const cata_cursesport::pixel_icon_button_overlay & existing ) {
        return existing.owner == owner;
    } );
    if( new_end != win->pixel_icon_buttons.end() ) {
        win->pixel_icon_buttons.erase( new_end, win->pixel_icon_buttons.end() );
        ++ui_pixel_button_debug.clear_removed;
    }
}

void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay,
                               const catacurses::window &parent )
{
    ++ui_pixel_button_debug.set_calls;
    if( overlay.owner == nullptr || !parent ) {
        maybe_log_ui_pixel_button_summary( "set-rejected" );
        return;
    }

    cata_cursesport::WINDOW *const win = parent.get<cata_cursesport::WINDOW>();
    if( win == nullptr ) {
        maybe_log_ui_pixel_button_summary( "set-no-window" );
        return;
    }

    auto tracked = ui_pixel_icon_button_parents.find( overlay.owner );
    if( tracked != ui_pixel_icon_button_parents.end() ) {
        if( const std::shared_ptr<void> old_parent = tracked->second.lock() ) {
            cata_cursesport::WINDOW *const old_win =
                static_cast<cata_cursesport::WINDOW *>( old_parent.get() );
            if( old_win != win ) {
                ++ui_pixel_button_debug.parent_switches;
                erase_pixel_icon_button_from_window( old_win, overlay.owner );
            }
        }
    }
    ui_pixel_icon_button_parents[overlay.owner] = parent.weak_ptr();

    cata_cursesport::pixel_icon_button_overlay layered;
    layered.owner = overlay.owner;
    layered.pos_pixels = overlay.pos_pixels;
    layered.size_pixels = overlay.size_pixels;
    layered.border_color_pair = overlay.border_color_pair;
    layered.fill_color_pair = overlay.fill_color_pair;
    layered.icon_color_pair = overlay.icon_color_pair;
    layered.icon = overlay.icon;

    const auto found = std::find_if( win->pixel_icon_buttons.begin(), win->pixel_icon_buttons.end(),
    [&]( const cata_cursesport::pixel_icon_button_overlay & existing ) {
        return existing.owner == layered.owner;
    } );
    if( found == win->pixel_icon_buttons.end() ) {
        win->pixel_icon_buttons.push_back( std::move( layered ) );
        ++ui_pixel_button_debug.registrations;
        maybe_log_ui_pixel_button_summary( "set-register" );
        return;
    }

    const bool unchanged = found->pos_pixels == layered.pos_pixels &&
                           found->size_pixels == layered.size_pixels &&
                           found->border_color_pair == layered.border_color_pair &&
                           found->fill_color_pair == layered.fill_color_pair &&
                           found->icon_color_pair == layered.icon_color_pair &&
                           found->icon == layered.icon;
    if( !unchanged ) {
        *found = std::move( layered );
        ++ui_pixel_button_debug.visual_updates;
    }
    maybe_log_ui_pixel_button_summary( unchanged ? "set-unchanged" : "set-visual" );
}

void clear_ui_pixel_icon_button( const void *owner )
{
    ++ui_pixel_button_debug.clear_calls;
    if( owner == nullptr ) {
        maybe_log_ui_pixel_button_summary( "clear-null" );
        return;
    }
    const auto tracked = ui_pixel_icon_button_parents.find( owner );
    if( tracked != ui_pixel_icon_button_parents.end() ) {
        if( const std::shared_ptr<void> parent = tracked->second.lock() ) {
            erase_pixel_icon_button_from_window(
                static_cast<cata_cursesport::WINDOW *>( parent.get() ), owner );
        }
        ui_pixel_icon_button_parents.erase( tracked );
    }
    maybe_log_ui_pixel_button_summary( "clear" );
}

'''
text = text[:start] + replacement + text[end:]

# Draw directly from the WINDOW-owned overlay list.  No global parent comparison.
text = text.replace(
    'static void draw_ui_pixel_button_bitmap( const ui_pixel_icon_button_overlay &button,\n',
    'static void draw_ui_pixel_button_bitmap( const cata_cursesport::pixel_icon_button_overlay &button,\n',
    1
)
old_draw = '''static bool draw_ui_pixel_icon_buttons( const cata_cursesport::WINDOW *parent )\n{\n    ++ui_pixel_button_debug.draw_calls;\n    bool drew = false;\n    size_t matched = 0;\n    for( const ui_pixel_icon_button_overlay &button : ui_pixel_icon_buttons ) {\n        if( button.owner == nullptr || button.parent != parent ||\n            button.size_pixels.x < 3 || button.size_pixels.y < 3 ) {\n            continue;\n        }\n        drew = true;\n        ++matched;\n'''
new_draw = '''static bool draw_ui_pixel_icon_buttons( const cata_cursesport::WINDOW *parent )\n{\n    ++ui_pixel_button_debug.draw_calls;\n    if( parent == nullptr ) {\n        maybe_log_ui_pixel_button_summary( "draw-null" );\n        return false;\n    }\n    bool drew = false;\n    size_t matched = 0;\n    for( const cata_cursesport::pixel_icon_button_overlay &button : parent->pixel_icon_buttons ) {\n        if( button.owner == nullptr || button.size_pixels.x < 3 || button.size_pixels.y < 3 ) {\n            continue;\n        }\n        drew = true;\n        ++matched;\n'''
if old_draw not in text:
    raise SystemExit('pixel icon draw loop anchor not found')
text = text.replace(old_draw, new_draw, 1)
text = text.replace(
    '''    if( matched > 0 ) {\n        ++ui_pixel_button_debug.nonempty_draw_calls;\n        ui_pixel_button_debug.drawn_buttons += matched;\n    }\n    maybe_log_ui_pixel_button_summary( drew ? "draw-nonempty" : "draw-empty" );\n    return drew;\n}\n\nvoid refresh_display()\n{\n    ++ui_pixel_button_debug.refresh_calls;\n    if( !needupdate ) {\n        ++ui_pixel_button_debug.refresh_without_needupdate;\n    }\n    maybe_log_ui_pixel_button_summary( "refresh" );\n    needupdate = false;\n''',
    '''    if( matched > 0 ) {\n        ui_pixel_button_debug.drawn_buttons += matched;\n    }\n    maybe_log_ui_pixel_button_summary( drew ? "draw-nonempty" : "draw-empty" );\n    return drew;\n}\n\nvoid refresh_display()\n{\n    needupdate = false;\n''',
    1
)
text = text.replace(
    '''static void try_sdl_update()\n{\n    ++ui_pixel_button_debug.try_update_calls;\n    uint32_t now = SDL_GetTicks();\n    if( now - lastupdate >= interval ) {\n        refresh_display();\n    } else {\n        ++ui_pixel_button_debug.deferred_updates;\n        needupdate = true;\n    }\n    maybe_log_ui_pixel_button_summary( "try-update" );\n}\n''',
    '''static void try_sdl_update()\n{\n    uint32_t now = SDL_GetTicks();\n    if( now - lastupdate >= interval ) {\n        refresh_display();\n    } else {\n        needupdate = true;\n    }\n}\n''',
    1
)
path.write_text(text, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Own pixel HUD overlays by curses window\n", encoding="utf-8"
)
