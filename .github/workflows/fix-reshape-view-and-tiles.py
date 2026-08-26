from pathlib import Path

CPP = Path('src/veh_interact.cpp')
SDL_H = Path('src/sdltiles.h')
SDL_CPP = Path('src/sdltiles.cpp')
TILES_H = Path('src/cata_tiles.h')
TILES_CPP = Path('src/cata_tiles.cpp')

cpp = CPP.read_text()
sdl_h = SDL_H.read_text()
sdl_cpp = SDL_CPP.read_text()
tiles_h = TILES_H.read_text()
tiles_cpp = TILES_CPP.read_text()


def rep(text, old, new, label, count=1):
    found = text.count(old)
    if found != count:
        raise SystemExit(f'{label}: expected {count} match(es), got {found}')
    return text.replace(old, new, count)


def replace_function(text, signature, replacement, label):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'{label}: signature not found')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'{label}: opening brace not found')
    depth = 0
    i = brace
    in_string = False
    in_char = False
    escape = False
    while i < len(text):
        ch = text[i]
        if escape:
            escape = False
        elif ch == '\\' and (in_string or in_char):
            escape = True
        elif ch == '"' and not in_char:
            in_string = not in_string
        elif ch == "'" and not in_string:
            in_char = not in_char
        elif not in_string and not in_char:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    return text[:start] + replacement.rstrip() + text[end:]
        i += 1
    raise SystemExit(f'{label}: unterminated function')


# -----------------------------------------------------------------------------
# SDL auxiliary vehicle-part thumbnails.  This deliberately lives beside the
# existing auxiliary map-preview bridge: curses owns layout, SDL owns tile data.
# -----------------------------------------------------------------------------
sdl_h = rep(
    sdl_h,
    '#include <optional>\n#include <string>\n',
    '#include <optional>\n#include <string>\n#include <vector>\n',
    'sdltiles vector include'
)

sdl_h = rep(
    sdl_h,
    '''std::optional<tripoint_bub_ms> map_preview_pixel_to_map( const catacurses::window &win,\n        const point &pixel, const tripoint_bub_ms &center, int draw_scale );\n\nconst SDL_Renderer_Ptr &get_sdl_renderer();\n''',
    '''std::optional<tripoint_bub_ms> map_preview_pixel_to_map( const catacurses::window &win,\n        const point &pixel, const tripoint_bub_ms &center, int draw_scale );\n\n// Small tileset-backed vehicle-part thumbnails for curses-owned auxiliary panes.\n// `pos` and `size` are relative to the supplied window in terminal cells.\nstruct vehicle_part_preview_tile {\n    point pos = point::zero;\n    point size = point::zero;\n    std::string part_id;\n    std::string variant;\n    int rotation = 0;\n};\nvoid set_vehicle_part_preview_tiles( const catacurses::window &win,\n                                     const std::vector<vehicle_part_preview_tile> &previews );\nvoid clear_vehicle_part_preview_tiles();\nbool has_vehicle_part_preview_tile( const std::string &part_id, const std::string &variant );\n\nconst SDL_Renderer_Ptr &get_sdl_renderer();\n''',
    'sdltiles thumbnail API'
)

sdl_cpp = rep(
    sdl_cpp,
    '''cata_cursesport::WINDOW *map_preview_window = nullptr;\nstd::optional<tripoint_bub_ms> map_preview_center;\nint map_preview_draw_scale = 16;\n} // namespace\n''',
    '''cata_cursesport::WINDOW *map_preview_window = nullptr;\nstd::optional<tripoint_bub_ms> map_preview_center;\nint map_preview_draw_scale = 16;\ncata_cursesport::WINDOW *vehicle_part_preview_window = nullptr;\nstd::vector<vehicle_part_preview_tile> vehicle_part_preview_tiles;\n} // namespace\n''',
    'thumbnail global state'
)

sdl_cpp = rep(
    sdl_cpp,
    '''void clear_map_preview_window()\n{\n    map_preview_window = nullptr;\n    map_preview_center.reset();\n    map_preview_draw_scale = 16;\n}\n\nstd::optional<tripoint_bub_ms> map_preview_pixel_to_map( const catacurses::window &win,\n''',
    '''void clear_map_preview_window()\n{\n    map_preview_window = nullptr;\n    map_preview_center.reset();\n    map_preview_draw_scale = 16;\n}\n\nvoid set_vehicle_part_preview_tiles( const catacurses::window &win,\n                                     const std::vector<vehicle_part_preview_tile> &previews )\n{\n    vehicle_part_preview_window = win ? win.get<cata_cursesport::WINDOW>() : nullptr;\n    vehicle_part_preview_tiles = previews;\n}\n\nvoid clear_vehicle_part_preview_tiles()\n{\n    vehicle_part_preview_window = nullptr;\n    vehicle_part_preview_tiles.clear();\n}\n\nbool has_vehicle_part_preview_tile( const std::string &part_id, const std::string &variant )\n{\n    if( !use_tiles ) {\n        return false;\n    }\n    const std::shared_ptr<cata_tiles> draw_tiles = closetilecontext ? closetilecontext : tilecontext;\n    return draw_tiles && draw_tiles->has_vehicle_part_preview_tile( part_id, variant );\n}\n\nstd::optional<tripoint_bub_ms> map_preview_pixel_to_map( const catacurses::window &win,\n''',
    'thumbnail registration functions'
)

sdl_cpp = rep(
    sdl_cpp,
    '''    } else {\n        // Either not using tiles (tilecontext) or not the w_terrain window.\n        update = draw_window( font, w );\n    }\n    if( update ) {\n''',
    '''    } else {\n        // Either not using tiles (tilecontext) or not the w_terrain window.\n        update = draw_window( font, w );\n\n        // A reshape palette is a normal curses window with small tileset-backed\n        // previews composited over reserved icon cells.  Drawing them here keeps\n        // layout/input in curses while using the exact same tileset lookup as a\n        // live vehicle part.\n        if( g && use_tiles && vehicle_part_preview_window == win &&\n            !vehicle_part_preview_tiles.empty() ) {\n            const std::shared_ptr<cata_tiles> draw_tiles = closetilecontext ? closetilecontext : tilecontext;\n            if( draw_tiles ) {\n                for( const vehicle_part_preview_tile &preview : vehicle_part_preview_tiles ) {\n                    const point dest( ( win->pos.x + preview.pos.x ) * fontwidth,\n                                      ( win->pos.y + preview.pos.y ) * fontheight );\n                    const point size( preview.size.x * fontwidth, preview.size.y * fontheight );\n                    draw_tiles->draw_vehicle_part_preview( dest, size, preview.part_id,\n                                                           preview.variant, preview.rotation );\n                }\n                update = true;\n            }\n        }\n    }\n    if( update ) {\n''',
    'thumbnail window compositing'
)

# -----------------------------------------------------------------------------
# Tiles renderer: resolve and draw exactly the same vp_<id> + variant tile path
# used by draw_vpart(), but into an arbitrary small pixel rectangle.
# -----------------------------------------------------------------------------
tiles_h = rep(
    tiles_h,
    '''        /** Draw to screen */\n        void draw( const point &dest, const tripoint_bub_ms &center, int width, int height,\n                   std::multimap<point, formatted_text> &overlay_strings,\n                   color_block_overlay_container &color_blocks );\n        void draw_om( const point &dest, const tripoint_abs_omt &center_abs_omt, bool blink );\n\n        /** Minimap functionality */\n''',
    '''        /** Draw to screen */\n        void draw( const point &dest, const tripoint_bub_ms &center, int width, int height,\n                   std::multimap<point, formatted_text> &overlay_strings,\n                   color_block_overlay_container &color_blocks );\n        void draw_om( const point &dest, const tripoint_abs_omt &center_abs_omt, bool blink );\n\n        /** Draw one vehicle-part variant into a small UI thumbnail rectangle. */\n        bool has_vehicle_part_preview_tile( const std::string &part_id,\n                                            const std::string &variant ) const;\n        bool draw_vehicle_part_preview( const point &dest, const point &size,\n                                        const std::string &part_id, const std::string &variant,\n                                        int rotation );\n\n        /** Minimap functionality */\n''',
    'cata_tiles thumbnail declarations'
)

preview_impl = r'''
bool cata_tiles::has_vehicle_part_preview_tile( const std::string &part_id,
        const std::string &variant ) const
{
    if( !tileset_ptr || part_id.empty() ) {
        return false;
    }
    return find_tile_looks_like( "vp_" + part_id, TILE_CATEGORY::VEHICLE_PART, variant ).has_value();
}

bool cata_tiles::draw_vehicle_part_preview( const point &dest, const point &size,
        const std::string &part_id, const std::string &variant, const int rotation )
{
    if( !tileset_ptr || size.x <= 0 || size.y <= 0 || part_id.empty() ) {
        return false;
    }
    std::optional<tile_lookup_res> resolved =
        find_tile_looks_like( "vp_" + part_id, TILE_CATEGORY::VEHICLE_PART, variant );
    if( !resolved ) {
        return false;
    }

    const int base_width = tileset_ptr->get_tile_width();
    const int base_height = tileset_ptr->get_tile_height();
    if( base_width <= 0 || base_height <= 0 ) {
        return false;
    }

    int preview_width = size.x;
    int preview_height = std::max( 1, preview_width * base_height / base_width );
    if( preview_height > size.y ) {
        preview_height = size.y;
        preview_width = std::max( 1, preview_height * base_width / base_height );
    }

    const int saved_tile_width = tile_width;
    const int saved_tile_height = tile_height;
    const bool clip_was_enabled = SDL_RenderIsClipEnabled( renderer.get() ) == SDL_TRUE;
    SDL_Rect saved_clip = { 0, 0, 0, 0 };
    if( clip_was_enabled ) {
        SDL_RenderGetClipRect( renderer.get(), &saved_clip );
    }

    tile_width = preview_width;
    tile_height = preview_height;
    SDL_Rect clip = { dest.x, dest.y, size.x, size.y };
    SDL_RenderSetClipRect( renderer.get(), &clip );

    const point draw_pos = dest + point( ( size.x - preview_width ) / 2,
                                         ( size.y - preview_height ) / 2 );
    int height_3d = 0;
    draw_tile_at( resolved->tile(), draw_pos, 0u, rotation, lit_level::LIT,
                  false, 0, height_3d, point::zero );

    tile_width = saved_tile_width;
    tile_height = saved_tile_height;
    SDL_RenderSetClipRect( renderer.get(), clip_was_enabled ? &saved_clip : nullptr );
    return true;
}

'''
tiles_cpp = rep(
    tiles_cpp,
    '''void cata_tiles::draw_minimap( const point &dest, const tripoint_bub_ms &center, int width,\n                               int height )\n''',
    preview_impl + '''void cata_tiles::draw_minimap( const point &dest, const tripoint_bub_ms &center, int width,\n                               int height )\n''',
    'cata_tiles thumbnail implementation'
)

# -----------------------------------------------------------------------------
# Reshape editor behavior.
# -----------------------------------------------------------------------------
cpp = rep(
    cpp,
    '''#if defined(TILES)\n    clear_map_preview_window();\n    set_sdl_mouse_capture( false );\n#endif\n''',
    '''#if defined(TILES)\n    clear_map_preview_window();\n    clear_vehicle_part_preview_tiles();\n    set_sdl_mouse_capture( false );\n#endif\n''',
    'destructor thumbnail cleanup'
)

open_reshape = r'''void veh_interact::open_reshape_mode()
{
    if( reshape_info ) {
        return;
    }

    // Enter against the exact currently selected stacked part.  Unsupported
    // selections intentionally become an empty selection rather than silently
    // jumping to another reshapeable part on the same mount.
    bool selected_is_reshapeable = false;
    if( selected_part >= 0 && selected_part < veh->part_count() ) {
        const vehicle_part &part = veh->part( selected_part );
        selected_is_reshapeable = !part.removed && part.mount == selected_mount() &&
                                  part.info().variants.size() > 1;
    }
    if( !selected_is_reshapeable ) {
        selected_part = -1;
    }

    reshape_info = std::make_unique<reshape_info_t>();
    // Force the first synchronization even when the intentional selection is -1.
    reshape_info->target_part = -2;
    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    viewport_dragging = false;
    live_preview_dragging = false;
#if defined(TILES)
    set_sdl_mouse_capture( false );
    clear_vehicle_part_preview_tiles();
#endif
    live_preview_last_draw_mode.reset();
    msg.reset();
    sync_reshape_selection();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}'''
cpp = replace_function(cpp, 'void veh_interact::open_reshape_mode()', open_reshape, 'open reshape')

close_reshape = r'''void veh_interact::close_reshape_mode()
{
    if( !reshape_info ) {
        return;
    }
    const int target = reshape_info->target_part;
    if( target >= 0 && target < veh->part_count() ) {
        vehicle_part &part = veh->part( target );
        if( !part.removed ) {
            part.variant = reshape_info->committed_variant;
        }
    }
#if defined(TILES)
    clear_vehicle_part_preview_tiles();
#endif
    reshape_info.reset();
    msg.reset();
    live_preview_last_draw_mode.reset();
    clamp_viewport_pan();
    if( active_editor_view_mode != editor_view_mode::live ) {
        ensure_selected_mount_visible();
    }
}'''
cpp = replace_function(cpp, 'void veh_interact::close_reshape_mode()', close_reshape, 'close reshape')

schematic_width = r'''int veh_interact::editor_schematic_width() const
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
}'''
cpp = replace_function(cpp, 'int veh_interact::editor_schematic_width() const', schematic_width,
                       'normal schematic width in reshape')

live_hit = r'''bool veh_interact::point_in_live_preview( const point &screen ) const
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
}'''
cpp = replace_function(cpp, 'bool veh_interact::point_in_live_preview( const point &screen ) const',
                       live_hit, 'normal live hit testing in reshape')

cpp = rep(
    cpp,
    '''    if( !reshape_info && active_editor_view_mode == editor_view_mode::split && schematic_width > 0 &&\n        schematic_width < getmaxx( w_disp ) ) {\n''',
    '''    if( active_editor_view_mode == editor_view_mode::split && schematic_width > 0 &&\n        schematic_width < getmaxx( w_disp ) ) {\n''',
    'restore split divider'
)

cpp = rep(
    cpp,
    '''    if( pos.y == 0 ) {\n        if( reshape_info ) {\n            return true;\n        }\n        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{\n''',
    '''    if( pos.y == 0 ) {\n        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{\n''',
    'reshape view tab click-through'
)

cpp = rep(
    cpp,
    '''    // View-mode tabs live at the top-right of the editor pane. Reshape temporarily\n    // owns the complete schematic width, while preserving the player's normal view mode.\n    if( !reshape_info ) {\n''',
    '''    // View-mode tabs remain first-class in every editor mode, including reshape.\n    {\n''',
    'reshape view tab display'
)

cpp = rep(
    cpp,
    '''    // Layer tabs: persistent and directly clickable because there are only four.\n''',
    '''    if( reshape_info ) {\n        // Reshapeability itself is the active part filter.  Keep rows 1/2 reserved\n        // so switching into reshape does not move the viewport/camera rectangle.\n        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,\n                        _( "Filter: reshapeable parts only" ) );\n        return;\n    }\n\n    // Layer tabs: persistent and directly clickable because there are only four.\n''',
    'hide normal filters in reshape'
)

# Rows 1/2 are still reserved but must not invoke hidden normal filter controls.
cpp = rep(
    cpp,
    '''        return true;\n    }\n\n    if( pos.y == 1 ) {\n''',
    '''        return true;\n    }\n\n    if( reshape_info && ( pos.y == 1 || pos.y == 2 ) ) {\n        return true;\n    }\n\n    if( pos.y == 1 ) {\n''',
    'consume hidden reshape filter rows'
)

inspector = r'''std::vector<int> veh_interact::inspector_parts() const
{
    std::vector<int> result;
    for( const int idx : veh->parts_at_relative( selected_mount(), true, false ) ) {
        const vehicle_part &vp = veh->part( idx );
        if( reshape_info ) {
            // Reshape is its own filter mode: ignore the normal layer/system/
            // condition filters and expose only independently reshapeable parts.
            if( !vp.removed && vp.info().variants.size() > 1 ) {
                result.push_back( idx );
            }
        } else if( part_matches_layer( vp ) && part_matches_system( vp ) &&
                   part_matches_condition( vp ) ) {
            result.push_back( idx );
        }
    }
    return result;
}'''
cpp = replace_function(cpp, 'std::vector<int> veh_interact::inspector_parts() const', inspector,
                       'reshape inspector filter')

cpp = rep(
    cpp,
    '''    mvwprintz( w_parts, point( 1, 0 ), c_light_green, _( "Mount (%+d,%+d)" ), mount.x(), mount.y() );\n    if( parts.size() == all_parts.size() ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d" ),\n                   static_cast<int>( parts.size() ) );\n    } else {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d/%d" ),\n                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );\n    }\n''',
    '''    mvwprintz( w_parts, point( 1, 0 ), c_light_green, _( "Mount (%+d,%+d)" ), mount.x(), mount.y() );\n    if( reshape_info ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Reshapeable parts: %d/%d" ),\n                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );\n    } else if( parts.size() == all_parts.size() ) {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d" ),\n                   static_cast<int>( parts.size() ) );\n    } else {\n        mvwprintz( w_parts, point( 1, 1 ), c_light_gray, _( "Installed parts: %d/%d" ),\n                   static_cast<int>( parts.size() ), static_cast<int>( all_parts.size() ) );\n    }\n''',
    'reshape inspector count'
)

reshape_display = r'''void veh_interact::display_reshape_pane()
{
    werase( w_msg );
    const int width = getmaxx( w_msg );
    const int height = getmaxy( w_msg );
#if defined(TILES)
    std::vector<vehicle_part_preview_tile> tile_previews;
#endif
    if( !reshape_info ) {
#if defined(TILES)
        clear_vehicle_part_preview_tiles();
#endif
        wnoutrefresh( w_msg );
        return;
    }

    trim_and_print( w_msg, point( 1, 0 ), std::max( 1, width - 2 ), c_light_green,
                    _( "Shapes / orientation" ) );

    if( reshape_info->target_part < 0 || reshape_info->target_part >= veh->part_count() ) {
        trim_and_print( w_msg, point( 1, 1 ), std::max( 1, width - 2 ), c_dark_gray,
                        _( "Select a reshapeable part above." ) );
    } else {
        const vehicle_part &part = veh->part( reshape_info->target_part );
        trim_and_print( w_msg, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray, part.name() );
    }

    if( height > 2 ) {
        wattron( w_msg, c_dark_gray );
        mvwhline( w_msg, point( 1, 2 ), LINE_OXOX, std::max( 0, width - 2 ) );
        wattroff( w_msg, c_dark_gray );
    }

    constexpr int first_row = 3;
    constexpr int entry_height = 2;
    constexpr int icon_width = 4;
    const int footer_y = std::max( first_row, height - 2 );
    const int visible = std::max( 0, ( footer_y - first_row ) / entry_height );

    if( reshape_info->variants.empty() ) {
        if( first_row < footer_y ) {
            trim_and_print( w_msg, point( 2, first_row ), std::max( 1, width - 4 ), c_dark_gray,
                            reshape_info->target_part < 0 ?
                            _( "No reshapeable part selected." ) :
                            _( "This selected part has no alternate shapes." ) );
        }
    } else {
        const int max_scroll = std::max( 0, static_cast<int>( reshape_info->variants.size() ) - visible );
        reshape_info->variant_scroll = std::clamp( reshape_info->variant_scroll, 0, max_scroll );
        if( reshape_info->variant_pos < reshape_info->variant_scroll ) {
            reshape_info->variant_scroll = reshape_info->variant_pos;
        } else if( visible > 0 && reshape_info->variant_pos >= reshape_info->variant_scroll + visible ) {
            reshape_info->variant_scroll = reshape_info->variant_pos - visible + 1;
        }

        const vehicle_part &part = veh->part( reshape_info->target_part );
        const vpart_info &vpi = part.info();
        const units::angle display_dir = 270_degrees - veh->face.dir();
        const int tile_rotation = angle_to_dir4( display_dir );
        for( int row = 0; row < visible; ++row ) {
            const int index = reshape_info->variant_scroll + row;
            if( index >= static_cast<int>( reshape_info->variants.size() ) ) {
                break;
            }
            const int y = first_row + row * entry_height;
            const std::string &id = reshape_info->variants[index];
            const vpart_variant &variant = vpi.variants.at( id );
            const bool selected = index == reshape_info->variant_pos;
            const bool committed = id == reshape_info->committed_variant;
            const std::string label = variant.get_label().empty() ? _( "Default" ) : variant.get_label();

            if( selected ) {
                const std::string blank( std::max( 0, width - 2 ), ' ' );
                trim_and_print( w_msg, point( 1, y ), std::max( 0, width - 2 ), h_dark_gray, blank );
                if( y + 1 < footer_y ) {
                    trim_and_print( w_msg, point( 1, y + 1 ), std::max( 0, width - 2 ), h_dark_gray, blank );
                }
            }

#if defined(TILES)
            if( has_vehicle_part_preview_tile( vpi.id.str(), id ) ) {
                tile_previews.push_back( vehicle_part_preview_tile{ point( 2, y ), point( icon_width, entry_height ),
                                         vpi.id.str(), id, tile_rotation } );
            } else {
                trim_and_print( w_msg, point( 2, y ), icon_width, c_light_red, _( "[?]" ) );
            }
#else
            const int symbol = variant.get_symbol_curses( display_dir, false );
            mvwputch( w_msg, point( 3, y ), selected ? hilite( vpi.color ) : vpi.color, symbol );
#endif
            trim_and_print( w_msg, point( 2 + icon_width + 1, y ),
                            std::max( 1, width - icon_width - 5 ),
                            selected ? h_light_cyan : c_light_gray, label );
            if( committed && y + 1 < footer_y ) {
                trim_and_print( w_msg, point( 2 + icon_width + 1, y + 1 ),
                                std::max( 1, width - icon_width - 5 ), c_dark_gray, _( "Current" ) );
            }
        }
        if( static_cast<int>( reshape_info->variants.size() ) > visible && visible > 0 ) {
            scrollbar().offset_x( width - 1 ).offset_y( first_row )
            .content_size( static_cast<int>( reshape_info->variants.size() ) )
            .viewport_pos( reshape_info->variant_scroll ).viewport_size( visible ).apply( w_msg );
        }
    }

    if( footer_y < height ) {
        const std::string apply_label = _( "[ Apply ]" );
        const std::string back_label = _( "[ Back ]" );
        trim_and_print( w_msg, point( 1, footer_y ), utf8_width( apply_label ),
                        reshape_info->variants.empty() ? c_dark_gray : c_light_green, apply_label );
        const int back_x = std::max( 1, width - utf8_width( back_label ) - 1 );
        trim_and_print( w_msg, point( back_x, footer_y ), utf8_width( back_label ), c_light_gray, back_label );
    }
    if( footer_y + 1 < height ) {
        trim_and_print( w_msg, point( 1, footer_y + 1 ), std::max( 1, width - 2 ), c_dark_gray,
                        _( "Click = preview   Double-click / Apply = save" ) );
    }
#if defined(TILES)
    set_vehicle_part_preview_tiles( w_msg, tile_previews );
#endif
    wnoutrefresh( w_msg );
}'''
cpp = replace_function(cpp, 'void veh_interact::display_reshape_pane()', reshape_display,
                       'reshape tile palette')

reshape_mouse = r'''bool veh_interact::handle_reshape_mouse( const std::string &action )
{
    if( !reshape_info ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_msg );
    if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( w_msg ) ||
        pos->y >= getmaxy( w_msg ) ) {
        return false;
    }

    const int height = getmaxy( w_msg );
    constexpr int first_row = 3;
    constexpr int entry_height = 2;
    const int footer_y = std::max( first_row, height - 2 );
    const int visible = std::max( 0, ( footer_y - first_row ) / entry_height );

    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        const int direction = action == "SCROLL_UP" ? -1 : 1;
        const int max_scroll = std::max( 0, static_cast<int>( reshape_info->variants.size() ) - visible );
        reshape_info->variant_scroll = std::clamp( reshape_info->variant_scroll + direction, 0, max_scroll );
        return true;
    }

    if( action != "SELECT" ) {
        return action == "SEC_SELECT";
    }

    if( pos->y >= first_row && pos->y < footer_y && visible > 0 ) {
        const int index = reshape_info->variant_scroll + ( pos->y - first_row ) / entry_height;
        if( index >= 0 && index < static_cast<int>( reshape_info->variants.size() ) ) {
            const auto now = std::chrono::steady_clock::now();
            const bool double_click = reshape_info->last_clicked_variant == index &&
                                      reshape_info->last_click_time &&
                                      now - *reshape_info->last_click_time <= std::chrono::milliseconds( 500 );
            preview_reshape_variant( index );
            if( double_click ) {
                apply_reshape_variant();
            } else {
                reshape_info->last_clicked_variant = index;
                reshape_info->last_click_time = now;
            }
        }
        return true;
    }

    if( pos->y == footer_y ) {
        const std::string apply_label = _( "[ Apply ]" );
        const std::string close_label = _( "[ Back ]" );
        const int close_x = std::max( 1, getmaxx( w_msg ) - utf8_width( close_label ) - 1 );
        if( pos->x >= 1 && pos->x < 1 + utf8_width( apply_label ) ) {
            apply_reshape_variant();
        } else if( pos->x >= close_x && pos->x < close_x + utf8_width( close_label ) ) {
            close_reshape_mode();
        }
        return true;
    }
    return true;
}'''
cpp = replace_function(cpp, 'bool veh_interact::handle_reshape_mouse( const std::string &action )',
                       reshape_mouse, 'reshape two-row mouse hitboxes')

# Defensive cleanup if reshape disappears through another state transition.
cpp = rep(
    cpp,
    '''            display_grid();\n            display_name();\n            display_stats( here );\n            display_veh( here );\n            if( refuel_info ) {\n''',
    '''            display_grid();\n            display_name();\n            display_stats( here );\n            display_veh( here );\n#if defined(TILES)\n            if( !reshape_info ) {\n                clear_vehicle_part_preview_tiles();\n            }\n#endif\n            if( refuel_info ) {\n''',
    'clear stale reshape previews outside mode'
)

# Structural assertions: reshape must no longer override normal viewport routing,
# and the ordinary filters must not participate in reshape mode.
assert 'if( reshape_info ) {\n        return width;' not in cpp
assert 'if( reshape_info ) {\n        return false;' not in cpp
assert '!reshape_info && active_editor_view_mode == editor_view_mode::split' not in cpp
assert 'Filter: reshapeable parts only' in cpp
assert 'Reshapeable parts: %d/%d' in cpp
assert 'vp.info().variants.size() > 1' in cpp
assert 'set_vehicle_part_preview_tiles( w_msg, tile_previews )' in cpp
assert 'point( icon_width, entry_height )' in cpp
assert 'find_tile_looks_like( "vp_" + part_id, TILE_CATEGORY::VEHICLE_PART, variant )' in tiles_cpp
assert 'vehicle_part_preview_window == win' in sdl_cpp

CPP.write_text(cpp)
SDL_H.write_text(sdl_h)
SDL_CPP.write_text(sdl_cpp)
TILES_H.write_text(tiles_h)
TILES_CPP.write_text(tiles_cpp)
print('reshape live/split + reshape filter + tileset thumbnails patch applied')
