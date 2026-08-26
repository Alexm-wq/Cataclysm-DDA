from pathlib import Path
import re

hpp = Path('src/veh_interact.h')
cpp = Path('src/veh_interact.cpp')
sdl_h = Path('src/sdltiles.h')
sdl_cpp = Path('src/sdltiles.cpp')

htext = hpp.read_text()
ctext = cpp.read_text()
shtext = sdl_h.read_text()
sctext = sdl_cpp.read_text()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one match, got {count}')
    return text.replace(old, new, 1)

# ---- Generic SDL auxiliary map-preview hook ---------------------------------
shtext = replace_once(
    shtext,
'''window_dimensions get_window_dimensions( const point &pos, const point &size );

const SDL_Renderer_Ptr &get_sdl_renderer();
''',
'''window_dimensions get_window_dimensions( const point &pos, const point &size );

// Register one auxiliary catacurses window to be rendered by the normal map
// tiles renderer.  This is intentionally generic: callers provide only the
// layout window and map center, while the SDL backend owns the actual drawing.
void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center );
void clear_map_preview_window();

const SDL_Renderer_Ptr &get_sdl_renderer();
''',
    'sdl preview declarations',
)

sctext = replace_once(
    sctext,
'''static bool draw_window( Font_Ptr &font, const catacurses::window &w )
{
    cata_cursesport::WINDOW *const win = w.get<cata_cursesport::WINDOW>();
    // Use global font sizes here to make this independent of the
    // font used for this window.
    return draw_window( font, w, point( win->pos.x * ::fontwidth, win->pos.y * ::fontheight ) );
}

void cata_cursesport::curses_drawwindow( const catacurses::window &w )
''',
'''static bool draw_window( Font_Ptr &font, const catacurses::window &w )
{
    cata_cursesport::WINDOW *const win = w.get<cata_cursesport::WINDOW>();
    // Use global font sizes here to make this independent of the
    // font used for this window.
    return draw_window( font, w, point( win->pos.x * ::fontwidth, win->pos.y * ::fontheight ) );
}

namespace
{
cata_cursesport::WINDOW *map_preview_window = nullptr;
std::optional<tripoint_bub_ms> map_preview_center;
} // namespace

void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center )
{
    map_preview_window = win ? win.get<cata_cursesport::WINDOW>() : nullptr;
    map_preview_center = map_preview_window != nullptr ? std::optional<tripoint_bub_ms>( center ) : std::nullopt;
}

void clear_map_preview_window()
{
    map_preview_window = nullptr;
    map_preview_center.reset();
}

void cata_cursesport::curses_drawwindow( const catacurses::window &w )
''',
    'sdl preview state',
)

sctext = replace_once(
    sctext,
'''    WINDOW *const win = w.get<WINDOW>();
    bool update = false;
    if( g && w == g->w_terrain && use_tiles ) {
''',
'''    WINDOW *const win = w.get<WINDOW>();
    bool update = false;
    const bool draw_terrain_tiles = g && use_tiles && w == g->w_terrain;
    const bool draw_preview_tiles = g && use_tiles && map_preview_window == win &&
                                    map_preview_center.has_value();
    if( draw_terrain_tiles || draw_preview_tiles ) {
''',
    'tiles window selection',
)

sctext = replace_once(
    sctext,
'''        // game::w_terrain can be drawn by the tilecontext.
        // skip the normal drawing code for it.
        tilecontext->draw(
            point( win->pos.x * fontwidth, win->pos.y * fontheight ),
            g->ter_view_p,
            TERRAIN_WINDOW_TERM_WIDTH * font->width,
            TERRAIN_WINDOW_TERM_HEIGHT * font->height,
            overlay_strings,
            color_blocks );
''',
'''        // The main terrain window and registered auxiliary previews use the
        // exact same tiles renderer.  Only their center and destination size differ.
        const point tile_draw_pos( win->pos.x * fontwidth, win->pos.y * fontheight );
        const tripoint_bub_ms tile_draw_center = draw_terrain_tiles ? g->ter_view_p : *map_preview_center;
        const int tile_draw_width = draw_terrain_tiles ?
                                    TERRAIN_WINDOW_TERM_WIDTH * font->width : win->width * font->width;
        const int tile_draw_height = draw_terrain_tiles ?
                                     TERRAIN_WINDOW_TERM_HEIGHT * font->height : win->height * font->height;
        tilecontext->draw( tile_draw_pos, tile_draw_center, tile_draw_width, tile_draw_height,
                           overlay_strings, color_blocks );
''',
    'tiles draw geometry',
)

sctext = replace_once(
    sctext,
'''                // Clip to window bounds.
                if( p.x < p0.x || p.x > p0.x + ( TERRAIN_WINDOW_TERM_WIDTH - 1 ) * font->width
                    || p.y < p0.y || p.y > p0.y + ( TERRAIN_WINDOW_TERM_HEIGHT - 1 ) * font->height ) {
                    continue;
                }
''',
'''                // Clip overlays to whichever tiles-backed window is being drawn.
                if( p.x < p0.x || p.x >= p0.x + tile_draw_width ||
                    p.y < p0.y || p.y >= p0.y + tile_draw_height ) {
                    continue;
                }
''',
    'tiles overlay clipping',
)

# ---- Vehicle editor state/layout --------------------------------------------
htext = replace_once(
    htext,
'''        catacurses::window w_msg;
        catacurses::window w_disp;
        catacurses::window w_parts;
''',
'''        catacurses::window w_msg;
        catacurses::window w_disp;
        catacurses::window w_live_preview_full;
        catacurses::window w_live_preview_split;
        catacurses::window w_parts;
''',
    'preview windows',
)

htext = replace_once(
    htext,
'''        point_rel_ms selected_mount() const;
        point viewport_cell_size() const;
        int editor_viewport_top() const;
        point mount_to_viewport( const point_rel_ms &mount ) const;
''',
'''        point_rel_ms selected_mount() const;
        point viewport_cell_size() const;
        int editor_viewport_top() const;
        int editor_schematic_width() const;
        bool point_in_editor_schematic( const point &screen ) const;
        point mount_to_viewport( const point_rel_ms &mount ) const;
''',
    'schematic geometry declarations',
)

htext = replace_once(
    htext,
'''        void display_grid();
        void display_veh( map &here );
        void display_part_inspector();
''',
'''        void display_grid();
        void display_veh( map &here );
        void display_live_preview( map &here );
        void display_part_inspector();
''',
    'live preview declaration',
)

ctext = replace_once(
    ctext,
'''#if defined(TILES)
#include "sdl_utils.h"
#endif
''',
'''#if defined(TILES)
#include "sdl_utils.h"
#include "sdltiles.h"
#endif
''',
    'sdltiles include',
)

ctext = replace_once(
    ctext,
'''static constexpr bool vehicle_editor_test_mode_visible = true;
static bool vehicle_editor_test_mode_latched = false;
''',
'''static constexpr bool vehicle_editor_test_mode_visible = true;
static bool vehicle_editor_test_mode_latched = false;
// Keep the selected viewport through ACT_VEHICLE handoffs/re-entry during this
// game session, just like the editor test-mode latch.
static int vehicle_editor_view_mode_latched = 0;
''',
    'view mode latch',
)

ctext = replace_once(
    ctext,
'''    editor_test_mode = vehicle_editor_test_mode_visible && vehicle_editor_test_mode_latched;
    if( !vehicle_editor_test_mode_visible ) {
        vehicle_editor_test_mode_latched = false;
    }

    count_durability();
''',
'''    editor_test_mode = vehicle_editor_test_mode_visible && vehicle_editor_test_mode_latched;
    if( !vehicle_editor_test_mode_visible ) {
        vehicle_editor_test_mode_latched = false;
    }
    active_editor_view_mode = static_cast<editor_view_mode>(
                                  std::clamp( vehicle_editor_view_mode_latched, 0, 2 ) );

    count_durability();
''',
    'restore view mode',
)

ctext = replace_once(
    ctext,
'''veh_interact::~veh_interact()
{
#if defined(TILES)
    set_sdl_mouse_capture( false );
#endif
}
''',
'''veh_interact::~veh_interact()
{
#if defined(TILES)
    clear_map_preview_window();
    set_sdl_mouse_capture( false );
#endif
}
''',
    'clear preview on destruction',
)

ctext = replace_once(
    ctext,
'''void veh_interact::allocate_windows()
{
    const point grid( point::south_east );
''',
'''void veh_interact::allocate_windows()
{
#if defined(TILES)
    // Window objects are replaced below; never leave the SDL preview registry
    // pointing at an old curses window across a resize.
    clear_map_preview_window();
#endif
    const point grid( point::south_east );
''',
    'clear preview on resize',
)

ctext = replace_once(
    ctext,
'''    w_mode = catacurses::newwin( mode_h, grid_w, grid );
    w_disp = catacurses::newwin( page_size, disp_w, point( grid.x, pane_y ) );

    // Base editor inspector.  Command modes reuse the same two right-side regions.
''',
'''    w_mode = catacurses::newwin( mode_h, grid_w, grid );
    w_disp = catacurses::newwin( page_size, disp_w, point( grid.x, pane_y ) );
#if defined(TILES)
    const int content_top = editor_viewport_top();
    const int preview_h = std::max( 1, page_size - content_top );
    const int split_left_w = std::max( 1, ( disp_w - 1 ) / 2 );
    const int split_preview_x = split_left_w + 1;
    const int split_preview_w = std::max( 1, disp_w - split_preview_x );
    w_live_preview_full = catacurses::newwin( preview_h, disp_w,
                          point( grid.x, pane_y + content_top ) );
    w_live_preview_split = catacurses::newwin( preview_h, split_preview_w,
                           point( grid.x + split_preview_x, pane_y + content_top ) );
#endif

    // Base editor inspector.  Command modes reuse the same two right-side regions.
''',
    'allocate preview windows',
)

ctext = replace_once(
    ctext,
'''int veh_interact::editor_viewport_top() const
{
    // Header, layer tabs, and system/condition controls occupy the top rows.
    return std::min( 3, std::max( 1, getmaxy( w_disp ) - 1 ) );
}

point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const
''',
'''int veh_interact::editor_viewport_top() const
{
    // Header, layer tabs, and system/condition controls occupy the top rows.
    return std::min( 3, std::max( 1, getmaxy( w_disp ) - 1 ) );
}

int veh_interact::editor_schematic_width() const
{
    const int width = getmaxx( w_disp );
    switch( active_editor_view_mode ) {
        case editor_view_mode::live:
            return 0;
        case editor_view_mode::split:
            return std::max( 1, ( width - 1 ) / 2 );
        case editor_view_mode::editor:
        default:
            return width;
    }
}

bool veh_interact::point_in_editor_schematic( const point &screen ) const
{
    const int schematic_width = editor_schematic_width();
    return schematic_width > 0 && screen.x >= 0 && screen.x < schematic_width &&
           screen.y >= editor_viewport_top() && screen.y < getmaxy( w_disp );
}

point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const
''',
    'schematic geometry helpers',
)

ctext = replace_once(
    ctext,
'''    const int content_height = std::max( 1, getmaxy( w_disp ) - content_top );
    const point center( getmaxx( w_disp ) / 2, content_top + content_height / 2 );
''',
'''    const int content_height = std::max( 1, getmaxy( w_disp ) - content_top );
    const int schematic_width = std::max( 1, editor_schematic_width() );
    const point center( schematic_width / 2, content_top + content_height / 2 );
''',
    'schematic mount center',
)

ctext = replace_once(
    ctext,
'''    if( screen.x < 0 || screen.y < editor_viewport_top() || screen.x >= getmaxx( w_disp ) ||
        screen.y >= getmaxy( w_disp ) ) {
''',
'''    if( !point_in_editor_schematic( screen ) ) {
''',
    'schematic hit test',
)

ctext = replace_once(
    ctext,
'''void veh_interact::clamp_viewport_pan()
{
    if( getmaxx( w_disp ) <= 0 || getmaxy( w_disp ) <= editor_viewport_top() ) {
        return;
    }
''',
'''void veh_interact::clamp_viewport_pan()
{
    const int schematic_width = editor_schematic_width();
    if( schematic_width <= 0 || getmaxy( w_disp ) <= editor_viewport_top() ) {
        return;
    }
''',
    'schematic pan guard',
)

ctext = replace_once(
    ctext,
'''    const point view_size( getmaxx( w_disp ), content_height );
''',
'''    const point view_size( schematic_width, content_height );
''',
    'schematic pan width',
)

ctext = replace_once(
    ctext,
'''void veh_interact::ensure_selected_mount_visible()
{
    const point cell = viewport_cell_size();
    const point p = mount_to_viewport( selected_mount() );
    const int left = cell.x;
    const int right = getmaxx( w_disp ) - cell.x - 1;
''',
'''void veh_interact::ensure_selected_mount_visible()
{
    const int schematic_width = editor_schematic_width();
    if( schematic_width <= 0 ) {
        return;
    }
    const point cell = viewport_cell_size();
    const point p = mount_to_viewport( selected_mount() );
    const int left = cell.x;
    const int right = schematic_width - cell.x - 1;
''',
    'schematic visibility width',
)

ctext = replace_once(
    ctext,
'''                active_editor_view_mode = view.first;
                open_editor_dropdown = editor_dropdown::none;
                close_editor_context_menu();
                viewport_dragging = false;
                return true;
''',
'''                active_editor_view_mode = view.first;
                vehicle_editor_view_mode_latched = static_cast<int>( active_editor_view_mode );
                open_editor_dropdown = editor_dropdown::none;
                close_editor_context_menu();
                viewport_dragging = false;
                if( active_editor_view_mode != editor_view_mode::live ) {
                    ensure_selected_mount_visible();
                }
                return true;
''',
    'viewport button state',
)

# Mouse interaction uses the exact same existing VEH_INTERACT actions, but only
# the schematic portion may resolve editor mounts.
if 'over_viewport_content' not in ctext:
    raise RuntimeError('mouse schematic variable: source marker missing')
ctext = ctext.replace(
    'const bool over_viewport_content = viewport_pos && viewport_pos->y >= editor_viewport_top();',
    'const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );',
    1,
)
ctext = ctext.replace('over_viewport_content', 'over_schematic_content')

# Render callback must refresh the live preview last so no later curses refresh
# can paint normal cells over the tiles-backed preview window.
ctext = replace_once(
    ctext,
'''            display_editor_context_menu();
            display_mode( here );
        } );
''',
'''            display_editor_context_menu();
            display_mode( here );
            display_live_preview( here );
        } );
''',
    'preview redraw order',
)

# Replace the viewport renderer as a unit so all width/selection checks agree on
# the left schematic region in Split and become empty in Live.
start = ctext.index('/**\n * Draws the primary vehicle editor viewport.\n */\nvoid veh_interact::display_veh( map &here )')
end = ctext.index('\nvoid veh_interact::display_part_inspector()', start)
new_display = r'''/**
 * Draws the primary vehicle editor viewport.
 */
void veh_interact::display_veh( map &here )
{
    werase( w_disp );
    if( !viewport_initialized ) {
        center_viewport_on_vehicle();
    }
    clamp_viewport_pan();

    const int schematic_width = editor_schematic_width();
    const point cell = viewport_cell_size();
    const int content_top = editor_viewport_top();
    constexpr int editor_margin = 4;
    const bounding_box bounds = veh->get_bounding_box( false, true );

    if( schematic_width > 0 ) {
        for( int x = bounds.p1.x() - editor_margin; x <= bounds.p2.x() + editor_margin; ++x ) {
            for( int y = bounds.p1.y() - editor_margin; y <= bounds.p2.y() + editor_margin; ++y ) {
                const point_rel_ms mount( x, y );
                const point screen = mount_to_viewport( mount );
                if( screen.x >= 0 && screen.y >= content_top && screen.x < schematic_width &&
                    screen.y < getmaxy( w_disp ) ) {
                    mvwputch( w_disp, screen, c_dark_gray, '.' );
                    if( const std::optional<std::pair<int, nc_color>> shown = editor_mount_display( mount ) ) {
                        mvwputch( w_disp, screen, shown->second, shown->first );
                    }
                }
            }
        }

        if( debug_mode ) {
            const point_rel_ms &pivot = veh->pivot_point( here );
            const point_rel_ms &com = veh->local_center_of_mass( here );
            const point com_s = mount_to_viewport( com );
            const point pivot_s = mount_to_viewport( pivot );
            if( com_s.x >= 0 && com_s.y >= content_top && com_s.x < schematic_width &&
                com_s.y < getmaxy( w_disp ) ) {
                mvwputch( w_disp, com_s, c_green, 'C' );
            }
            if( pivot_s.x >= 0 && pivot_s.y >= content_top && pivot_s.x < schematic_width &&
                pivot_s.y < getmaxy( w_disp ) ) {
                mvwputch( w_disp, pivot_s, c_red, 'P' );
            }
        }

        const point selected_screen = mount_to_viewport( selected_mount() );
        if( selected_screen.x >= 0 && selected_screen.y >= content_top &&
            selected_screen.x < schematic_width && selected_screen.y < getmaxy( w_disp ) ) {
            int sym = '.';
            nc_color col = c_dark_gray;
            if( const std::optional<std::pair<int, nc_color>> shown = editor_mount_display( selected_mount() ) ) {
                sym = shown->first;
                col = shown->second;
            }

            const tripoint_bub_ms world_pos = veh->pos_bub( here ) + veh->coord_translate( selected_mount() );
            const optional_vpart_position ovp = here.veh_at( world_pos );
            col = hilite( col );
            if( here.impassable_ter_furn( world_pos ) || ( ovp && &ovp->vehicle() != veh ) ) {
                col = red_background( col );
            }

            mvwputch( w_disp, selected_screen, col, sym );
            if( selected_screen.x > 0 ) {
                mvwputch( w_disp, point( selected_screen.x - 1, selected_screen.y ), c_yellow, '[' );
            }
            if( selected_screen.x + 1 < schematic_width ) {
                mvwputch( w_disp, point( selected_screen.x + 1, selected_screen.y ), c_yellow, ']' );
            }
            if( cell.y >= 2 && selected_screen.y > content_top ) {
                mvwputch( w_disp, point( selected_screen.x, selected_screen.y - 1 ), c_yellow, '^' );
            }
            if( cell.y >= 2 && selected_screen.y + 1 < getmaxy( w_disp ) ) {
                mvwputch( w_disp, point( selected_screen.x, selected_screen.y + 1 ), c_yellow, 'v' );
            }
        }
    }

    if( active_editor_view_mode == editor_view_mode::split && schematic_width > 0 &&
        schematic_width < getmaxx( w_disp ) ) {
        wattron( w_disp, c_dark_gray );
        mvwvline( w_disp, point( schematic_width, content_top ), LINE_XOXO,
                  std::max( 0, getmaxy( w_disp ) - content_top ) );
        wattroff( w_disp, c_dark_gray );
    }

    if( install_info ) {
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%  <color_light_cyan>INSTALL MODE</color>" ),
                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50 );
    } else {
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%" ),
                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50 );
    }
    display_editor_controls();
#if !defined(TILES)
    if( active_editor_view_mode != editor_view_mode::editor ) {
        const int x = active_editor_view_mode == editor_view_mode::split ? schematic_width + 2 : 2;
        trim_and_print( w_disp, point( x, content_top + 1 ),
                        std::max( 1, getmaxx( w_disp ) - x - 1 ), c_dark_gray,
                        _( "Live vehicle preview requires the tiles build." ) );
    }
#endif
    wnoutrefresh( w_disp );
}

void veh_interact::display_live_preview( map &here )
{
#if defined(TILES)
    if( active_editor_view_mode == editor_view_mode::editor ) {
        clear_map_preview_window();
        return;
    }

    catacurses::window &preview = active_editor_view_mode == editor_view_mode::live ?
                                  w_live_preview_full : w_live_preview_split;
    if( !preview ) {
        clear_map_preview_window();
        return;
    }

    // Center on the vehicle's current geometric extent in world space.  The
    // underlying map and vehicle are not copied, so every editor/activity update
    // is visible on the next normal UI redraw.
    const bounding_box bounds = veh->get_bounding_box( false, true );
    const point_rel_ms center_mount( ( bounds.p1.x() + bounds.p2.x() ) / 2,
                                     ( bounds.p1.y() + bounds.p2.y() ) / 2 );
    const tripoint_bub_ms world_center = veh->pos_bub( here ) + veh->coord_translate( center_mount );

    set_map_preview_window( preview, world_center );
    werase( preview );
    wnoutrefresh( preview );
#else
    ( void )here;
#endif
}
'''
ctext = ctext[:start] + new_display + ctext[end:]

hpp.write_text(htext)
cpp.write_text(ctext)
sdl_h.write_text(shtext)
sdl_cpp.write_text(sctext)
