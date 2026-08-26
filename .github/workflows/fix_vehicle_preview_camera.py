from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)

veh_h = Path("src/veh_interact.h")
veh_cpp = Path("src/veh_interact.cpp")
sdl_h = Path("src/sdltiles.h")
sdl_cpp = Path("src/sdltiles.cpp")
tiles_h = Path("src/cata_tiles.h")
tiles_cpp = Path("src/cata_tiles.cpp")

h = veh_h.read_text()
c = veh_cpp.read_text()
sh = sdl_h.read_text()
sc = sdl_cpp.read_text()
th = tiles_h.read_text()
tc = tiles_cpp.read_text()

# Track the renderer scale explicitly so an auxiliary preview can temporarily
# render at its own scale and restore the normal gameplay tiles immediately.
th = replace_once(
    th,
'''        int get_tile_width() const {
            return tile_width;
        }
        // Current viewport size in renderer tile-grid coordinates.  Weather uses
''',
'''        int get_tile_width() const {
            return tile_width;
        }
        int get_draw_scale() const {
            return draw_scale;
        }
        // Current viewport size in renderer tile-grid coordinates.  Weather uses
''',
    "cata tiles scale getter",
)

th = replace_once(
    th,
'''        int tile_height = 0;
        int tile_width = 0;
        // The scaled maximum extent of loaded sprites.
''',
'''        int tile_height = 0;
        int tile_width = 0;
        int draw_scale = 16;
        // The scaled maximum extent of loaded sprites.
''',
    "cata tiles scale member",
)

tc = replace_once(
    tc,
'''void cata_tiles::set_draw_scale( int scale )
{
    cata_assert( tileset_ptr );
    const int mult = tileset_ptr->get_tile_pixelscale() * scale;
''',
'''void cata_tiles::set_draw_scale( int scale )
{
    cata_assert( tileset_ptr );
    draw_scale = scale;
    const int mult = tileset_ptr->get_tile_pixelscale() * scale;
''',
    "record cata tiles scale",
)

# Auxiliary map previews accept their own scale.  16 is the renderer's 100%
# scale; the vehicle editor passes 8/16/24 for its 50/100/150% steps.
sh = replace_once(
    sh,
'''void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center );
void clear_map_preview_window();
''',
'''void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center,
                             int draw_scale = 16 );
void clear_map_preview_window();
''',
    "preview scale declaration",
)

sc = replace_once(
    sc,
'''cata_cursesport::WINDOW *map_preview_window = nullptr;
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
''',
'''cata_cursesport::WINDOW *map_preview_window = nullptr;
std::optional<tripoint_bub_ms> map_preview_center;
int map_preview_draw_scale = 16;
} // namespace

void set_map_preview_window( const catacurses::window &win, const tripoint_bub_ms &center,
                             const int draw_scale )
{
    map_preview_window = win ? win.get<cata_cursesport::WINDOW>() : nullptr;
    map_preview_center = map_preview_window != nullptr ? std::optional<tripoint_bub_ms>( center ) : std::nullopt;
    map_preview_draw_scale = std::max( 1, draw_scale );
}

void clear_map_preview_window()
{
    map_preview_window = nullptr;
    map_preview_center.reset();
    map_preview_draw_scale = 16;
}
''',
    "preview scale state",
)

sc = replace_once(
    sc,
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
'''        // The main terrain window and registered auxiliary previews use the
        // same map renderer.  Preview rendering deliberately uses the close
        // tileset and temporarily applies its own scale so it cannot change the
        // player's normal-game zoom or fall into the far-tileset zoom range.
        std::shared_ptr<cata_tiles> draw_tiles = draw_preview_tiles && closetilecontext ?
                                                closetilecontext : tilecontext;
        const int previous_draw_scale = draw_tiles->get_draw_scale();
        if( draw_preview_tiles && previous_draw_scale != map_preview_draw_scale ) {
            draw_tiles->set_draw_scale( map_preview_draw_scale );
        }

        const point tile_draw_pos( win->pos.x * fontwidth, win->pos.y * fontheight );
        const tripoint_bub_ms tile_draw_center = draw_terrain_tiles ? g->ter_view_p : *map_preview_center;
        const int tile_draw_width = draw_terrain_tiles ?
                                    TERRAIN_WINDOW_TERM_WIDTH * font->width : win->width * font->width;
        const int tile_draw_height = draw_terrain_tiles ?
                                     TERRAIN_WINDOW_TERM_HEIGHT * font->height : win->height * font->height;
        draw_tiles->draw( tile_draw_pos, tile_draw_center, tile_draw_width, tile_draw_height,
                          overlay_strings, color_blocks );
''',
    "preview draw context",
)

sc = replace_once(
    sc,
'''                geometry->rect( renderer, e.first, tilecontext->get_tile_width(),
                                tilecontext->get_tile_height(), e.second );
''',
'''                geometry->rect( renderer, e.first, draw_tiles->get_tile_width(),
                                draw_tiles->get_tile_height(), e.second );
''',
    "preview color block scale",
)

sc = replace_once(
    sc,
'''            prev_coord = coord;
            x_offset = width;
        }

        update = true;
''',
'''            prev_coord = coord;
            x_offset = width;
        }

        if( draw_preview_tiles && draw_tiles->get_draw_scale() != previous_draw_scale ) {
            draw_tiles->set_draw_scale( previous_draw_scale );
        }
        update = true;
''',
    "restore preview scale",
)

# Independent live-preview camera state.  Pan is stored in map tiles relative
# to the vehicle's automatically recomputed visual center.
h = replace_once(
    h,
'''        point viewport_drag_pan_origin = point::zero;
        int viewport_zoom = 2;
        int selected_part = -1;
''',
'''        point viewport_drag_pan_origin = point::zero;
        int viewport_zoom = 2;
        point live_preview_pan = point::zero;
        point live_preview_drag_anchor = point::zero;
        point live_preview_drag_pan_origin = point::zero;
        int live_preview_zoom = 2;
        bool live_preview_dragging = false;
        int selected_part = -1;
''',
    "live preview camera state",
)

h = replace_once(
    h,
'''        int editor_schematic_width() const;
        bool point_in_editor_schematic( const point &screen ) const;
        point mount_to_viewport( const point_rel_ms &mount ) const;
''',
'''        int editor_schematic_width() const;
        bool point_in_editor_schematic( const point &screen ) const;
        bool point_in_live_preview( const point &screen ) const;
        point live_preview_cell_size() const;
        tripoint_bub_ms live_preview_vehicle_center( map &here ) const;
        point mount_to_viewport( const point_rel_ms &mount ) const;
''',
    "live preview camera declarations",
)

# Geometry helpers and a visual center based on the actual transformed world
# positions of installed parts, rather than the vehicle pivot/origin.
c = replace_once(
    c,
'''bool veh_interact::point_in_editor_schematic( const point &screen ) const
{
    const int schematic_width = editor_schematic_width();
    return schematic_width > 0 && screen.x >= 0 && screen.x < schematic_width &&
           screen.y >= editor_viewport_top() && screen.y < getmaxy( w_disp );
}

point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const
''',
'''bool veh_interact::point_in_editor_schematic( const point &screen ) const
{
    const int schematic_width = editor_schematic_width();
    return schematic_width > 0 && screen.x >= 0 && screen.x < schematic_width &&
           screen.y >= editor_viewport_top() && screen.y < getmaxy( w_disp );
}

bool veh_interact::point_in_live_preview( const point &screen ) const
{
    if( screen.y < editor_viewport_top() || screen.y >= getmaxy( w_disp ) ||
        screen.x < 0 || screen.x >= getmaxx( w_disp ) ) {
        return false;
    }
    if( active_editor_view_mode == editor_view_mode::live ) {
        return true;
    }
    return active_editor_view_mode == editor_view_mode::split &&
           screen.x > editor_schematic_width();
}

point veh_interact::live_preview_cell_size() const
{
    // Match the editor's three zoom levels: 50%, 100%, and 150%.
    return point( live_preview_zoom * 2, live_preview_zoom );
}

tripoint_bub_ms veh_interact::live_preview_vehicle_center( map &here ) const
{
    int min_x = INT_MAX;
    int max_x = INT_MIN;
    int min_y = INT_MAX;
    int max_y = INT_MIN;
    bool found = false;

    for( const vpart_reference &vpr : veh->get_all_parts() ) {
        if( vpr.part().removed ) {
            continue;
        }
        const tripoint_bub_ms pos = vpr.pos_bub( here );
        min_x = std::min( min_x, pos.x() );
        max_x = std::max( max_x, pos.x() );
        min_y = std::min( min_y, pos.y() );
        max_y = std::max( max_y, pos.y() );
        found = true;
    }

    if( !found ) {
        return veh->pos_bub( here );
    }
    const point center_xy( ( min_x + max_x ) / 2, ( min_y + max_y ) / 2 );
    return tripoint_bub_ms( point_bub_ms( center_xy ), veh->pos_bub( here ).z() );
}

point veh_interact::mount_to_viewport( const point_rel_ms &mount ) const
''',
    "live preview helpers",
)

# View-mode changes stop either camera drag.  Camera pan/zoom otherwise persists
# while moving between Editor/Live/Split.
c = replace_once(
    c,
'''                close_editor_context_menu();
                viewport_dragging = false;
                if( active_editor_view_mode != editor_view_mode::live ) {
''',
'''                close_editor_context_menu();
                viewport_dragging = false;
                live_preview_dragging = false;
#if defined(TILES)
                set_sdl_mouse_capture( false );
#endif
                if( active_editor_view_mode != editor_view_mode::live ) {
''',
    "stop both camera drags on view switch",
)

# Mouse routing: reuse the existing camera actions.  The two halves in Split are
# mutually exclusive input regions; no second input context is introduced.
c = replace_once(
    c,
'''    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
''',
'''    const std::optional<point> details_pos = mouse_pos_in( w_msg );
    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );
    const bool over_live_preview = viewport_pos && point_in_live_preview( *viewport_pos );
''',
    "live preview hit test",
)

c = replace_once(
    c,
'''    if( viewport_dragging && ( !middle_mouse_down || !mouse_focused ) ) {
        viewport_dragging = false;
        set_sdl_mouse_capture( false );
    }
    if( action == "MOUSE_MOVE" && !viewport_dragging && middle_mouse_down && mouse_focused &&
        over_schematic_content && open_editor_dropdown == editor_dropdown::none && !editor_context_open ) {
        viewport_dragging = true;
        viewport_drag_anchor = *viewport_pos;
        viewport_drag_pan_origin = viewport_pan;
        set_sdl_mouse_capture( true );
        return true;
    }
''',
'''    if( ( viewport_dragging || live_preview_dragging ) && ( !middle_mouse_down || !mouse_focused ) ) {
        viewport_dragging = false;
        live_preview_dragging = false;
        set_sdl_mouse_capture( false );
    }
    if( action == "MOUSE_MOVE" && !viewport_dragging && !live_preview_dragging &&
        middle_mouse_down && mouse_focused && open_editor_dropdown == editor_dropdown::none &&
        !editor_context_open ) {
        if( over_live_preview ) {
            live_preview_dragging = true;
            live_preview_drag_anchor = *viewport_pos;
            live_preview_drag_pan_origin = live_preview_pan;
            set_sdl_mouse_capture( true );
            return true;
        }
        if( over_schematic_content ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
            set_sdl_mouse_capture( true );
            return true;
        }
    }
''',
    "auto middle drag routing",
)

c = replace_once(
    c,
'''    if( action == "CAMERA_PAN_START" ) {
        if( over_schematic_content && open_editor_dropdown == editor_dropdown::none && !editor_context_open ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        return false;
    }
    if( action == "CAMERA_PAN_END" ) {
        if( viewport_dragging ) {
            viewport_dragging = false;
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            return true;
        }
#if defined(TILES)
        set_sdl_mouse_capture( false );
#endif
        return false;
    }
    if( action == "MOUSE_MOVE" && viewport_dragging ) {
        if( viewport_pos ) {
            viewport_pan = viewport_drag_pan_origin + ( *viewport_pos - viewport_drag_anchor );
            clamp_viewport_pan();
        }
        return true;
    }
''',
'''    if( action == "CAMERA_PAN_START" ) {
        if( open_editor_dropdown != editor_dropdown::none || editor_context_open || !viewport_pos ) {
            return false;
        }
        if( over_live_preview ) {
            live_preview_dragging = true;
            live_preview_drag_anchor = *viewport_pos;
            live_preview_drag_pan_origin = live_preview_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        if( over_schematic_content ) {
            viewport_dragging = true;
            viewport_drag_anchor = *viewport_pos;
            viewport_drag_pan_origin = viewport_pan;
#if defined(TILES)
            set_sdl_mouse_capture( true );
#endif
            return true;
        }
        return false;
    }
    if( action == "CAMERA_PAN_END" ) {
        if( viewport_dragging || live_preview_dragging ) {
            viewport_dragging = false;
            live_preview_dragging = false;
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            return true;
        }
#if defined(TILES)
        set_sdl_mouse_capture( false );
#endif
        return false;
    }
    if( action == "MOUSE_MOVE" && live_preview_dragging ) {
        if( viewport_pos ) {
            const point delta = *viewport_pos - live_preview_drag_anchor;
            const point cell = live_preview_cell_size();
            const auto rounded_div = []( const int value, const int divisor ) {
                if( value >= 0 ) {
                    return ( value + divisor / 2 ) / divisor;
                }
                return -( ( -value + divisor / 2 ) / divisor );
            };
            live_preview_pan = live_preview_drag_pan_origin -
                               point( rounded_div( delta.x, std::max( 1, cell.x ) ),
                                      rounded_div( delta.y, std::max( 1, cell.y ) ) );
        }
        return true;
    }
    if( action == "MOUSE_MOVE" && viewport_dragging ) {
        if( viewport_pos ) {
            viewport_pan = viewport_drag_pan_origin + ( *viewport_pos - viewport_drag_anchor );
            clamp_viewport_pan();
        }
        return true;
    }
''',
    "camera pan action routing",
)

c = replace_once(
    c,
'''        if( over_schematic_content ) {
            const std::optional<point_rel_ms> anchor = viewport_to_mount( *viewport_pos );
            const int old_zoom = viewport_zoom;
            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 3 );
            if( viewport_zoom != old_zoom && anchor ) {
                const point after = mount_to_viewport( *anchor );
                viewport_pan += *viewport_pos - after;
                clamp_viewport_pan();
            }
            return true;
        }
''',
'''        if( over_live_preview ) {
            // Live preview deliberately has the same finite editor range and
            // never cycles into the normal game's extreme zoom-out levels.
            live_preview_zoom = std::clamp( live_preview_zoom - direction, 1, 3 );
            return true;
        }
        if( over_schematic_content ) {
            const std::optional<point_rel_ms> anchor = viewport_to_mount( *viewport_pos );
            const int old_zoom = viewport_zoom;
            viewport_zoom = std::clamp( viewport_zoom - direction, 1, 3 );
            if( viewport_zoom != old_zoom && anchor ) {
                const point after = mount_to_viewport( *anchor );
                viewport_pan += *viewport_pos - after;
                clamp_viewport_pan();
            }
            return true;
        }
''',
    "live preview wheel zoom",
)

# Header reports whichever camera zoom is actually being manipulated.
c = replace_once(
    c,
'''    if( install_info ) {
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%  <color_light_cyan>INSTALL MODE</color>" ),
                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50 );
    } else {
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%" ),
                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50 );
    }
''',
'''    if( active_editor_view_mode == editor_view_mode::split ) {
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   install_info ?
                   _( "Vehicle editor  Mount (%+d,%+d)  Editor %d%% / Live %d%%  <color_light_cyan>INSTALL MODE</color>" ) :
                   _( "Vehicle editor  Mount (%+d,%+d)  Editor %d%% / Live %d%%" ),
                   selected_mount().x(), selected_mount().y(), viewport_zoom * 50,
                   live_preview_zoom * 50 );
    } else {
        const int shown_zoom = active_editor_view_mode == editor_view_mode::live ?
                               live_preview_zoom : viewport_zoom;
        mvwprintz( w_disp, point( 1, 0 ), c_light_gray,
                   install_info ?
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%  <color_light_cyan>INSTALL MODE</color>" ) :
                   _( "Vehicle editor  Mount (%+d,%+d)  Zoom %d%%" ),
                   selected_mount().x(), selected_mount().y(), shown_zoom * 50 );
    }
''',
    "camera zoom header",
)

# Render from the actual occupied world-space bounds and add camera pan.  Pass
# 8/16/24 directly to the generic preview hook for 50/100/150%.
c = replace_once(
    c,
'''    // Center on the vehicle's current geometric extent in world space.  The
    // underlying map and vehicle are not copied, so every editor/activity update
    // is visible on the next normal UI redraw.
    const bounding_box bounds = veh->get_bounding_box( false, true );
    const point_rel_ms center_mount( ( bounds.p1.x() + bounds.p2.x() ) / 2,
                                     ( bounds.p1.y() + bounds.p2.y() ) / 2 );
    const tripoint_bub_ms world_center = veh->pos_bub( here ) + veh->coord_translate( center_mount );

    set_map_preview_window( preview, world_center );
''',
'''    // Use the real transformed positions of all installed parts.  Vehicle
    // mount-space bounding boxes can be far from the visual center when a large
    // vehicle has an offset pivot or asymmetric construction.
    const tripoint_bub_ms vehicle_center = live_preview_vehicle_center( here );
    const tripoint_bub_ms world_center = vehicle_center + tripoint_rel_ms( live_preview_pan, 0 );

    set_map_preview_window( preview, world_center, live_preview_zoom * 8 );
''',
    "live preview center zoom pan",
)

veh_h.write_text(h)
veh_cpp.write_text(c)
sdl_h.write_text(sh)
sdl_cpp.write_text(sc)
tiles_h.write_text(th)
tiles_cpp.write_text(tc)
