from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# SDL curses windows own their pixel scrollbar overlays.  Keeping the overlay
# on WINDOW itself gives it the correct lifetime and avoids any global registry
# that could retain stale window pointers.
# ---------------------------------------------------------------------------
p = Path("src/cursesport.h")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''struct curseline {\n    bool touched;\n    std::vector<cursecell> chars;\n};\n\n// The curses window struct\n''',
    '''struct curseline {\n    bool touched;\n    std::vector<cursecell> chars;\n};\n\n// Pixel-space visual overlay for a scrollbar drawn by the SDL curses backend.\n// Geometry is relative to the owning window in logical renderer pixels.\nstruct pixel_scrollbar_overlay {\n    const void *owner = nullptr;\n    int x_cell = 0;\n    int track_top_px = 0;\n    int track_height_px = 0;\n    int thumb_top_px = 0;\n    int thumb_height_px = 0;\n    bool dragging = false;\n};\n\n// The curses window struct\n''',
    "pixel scrollbar overlay struct",
)
text = replace_once(
    text,
    '''    point cursor;\n    std::vector<curseline> line;\n};\n''',
    '''    point cursor;\n    std::vector<curseline> line;\n    std::vector<pixel_scrollbar_overlay> pixel_scrollbars;\n};\n''',
    "window pixel scrollbar storage",
)
p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Expose the already-stored raw mouse pixel coordinate.  Existing text/map
# coordinate APIs remain unchanged; pixel-aware UI primitives can opt in.
# ---------------------------------------------------------------------------
p = Path("src/input_context.h")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        std::optional<point> get_coordinates_text( const catacurses::window &capture_win ) const;\n\n        /**\n         * Get the human-readable name for an action.\n''',
    '''        std::optional<point> get_coordinates_text( const catacurses::window &capture_win ) const;\n\n        /** Return the raw screen pixel coordinate from the latest coordinate input. */\n        std::optional<point> get_coordinates_pixel() const {\n            return coordinate_input_received ? std::optional<point>( coordinate ) : std::nullopt;\n        }\n\n        /**\n         * Get the human-readable name for an action.\n''',
    "raw pixel coordinate accessor",
)
p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Shared scrollbar API: viewport_size remains semantic entry count; height()
# independently controls visual track height.  handle_input() centralizes the
# pixel-aware TILES path while preserving the old coordinate overloads.
# ---------------------------------------------------------------------------
p = Path("src/ui_helpers/primitive/scrollbar.h")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        // number of lines shown\n        scrollbar &viewport_size( int vsize );\n        // window border color\n''',
    '''        // number of entries shown\n        scrollbar &viewport_size( int vsize );\n        // visual scrollbar height in terminal rows; defaults to viewport_size\n        scrollbar &height( int rows );\n        // window border color\n''',
    "scrollbar height API",
)
text = replace_once(
    text,
    '''        bool handle_dragging( const std::string &action, const std::optional<point> &coord,\n                              int &position );\n\n        /** Copy renderer-independent scroll state into this visual scrollbar. */\n''',
    '''        bool handle_dragging( const std::string &action, const std::optional<point> &coord,\n                              int &position );\n\n        /** Handle scrollbar input using pixel coordinates on TILES and text cells elsewhere. */\n        bool handle_input( const std::string &action, const input_context &ctxt,\n                           ui_scroll_model &state );\n\n        /** Copy renderer-independent scroll state into this visual scrollbar. */\n''',
    "scrollbar centralized input API",
)
text = replace_once(
    text,
    '''        int offset_x_v, offset_y_v;\n        int content_size_v, viewport_pos_v, viewport_size_v;\n        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;\n''',
    '''        int offset_x_v, offset_y_v;\n        int content_size_v, viewport_pos_v, viewport_size_v, drawn_height_v;\n        nc_color border_color_v, arrow_color_v, slot_color_v, bar_color_v;\n''',
    "scrollbar visual height member",
)
text = replace_once(
    text,
    '''        int drag_grab_offset = 0;\n        inclusive_rectangle<point> scrollbar_area;\n        std::optional<inclusive_rectangle<point>> thumb_area;\n''',
    '''        int drag_grab_offset = 0;\n        inclusive_rectangle<point> scrollbar_area;\n        std::optional<inclusive_rectangle<point>> thumb_area;\n#if defined(TILES)\n        int pixel_drag_grab_offset = 0;\n        inclusive_rectangle<point> pixel_scrollbar_area;\n        std::optional<inclusive_rectangle<point>> pixel_thumb_area;\n        bool handle_pixel_dragging( const std::string &action, const std::optional<point> &coord,\n                                    int &position );\n#endif\n''',
    "scrollbar pixel interaction state",
)
p.write_text(text, encoding="utf-8")


p = Path("src/ui_helpers/primitive/scrollbar.cpp")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''#include "../../input_context.h"\n#include "../../output.h"\n''',
    '''#include "../../input_context.h"\n#include "../../output.h"\n#if defined(TILES)\n#include "../../cursesport.h"\n#include "../../sdltiles.h"\n#endif\n''',
    "scrollbar SDL includes",
)
text = replace_once(
    text,
    '''    : offset_x_v( 0 ), offset_y_v( 0 ), content_size_v( 0 ),\n      viewport_pos_v( 0 ), viewport_size_v( 0 ),\n''',
    '''    : offset_x_v( 0 ), offset_y_v( 0 ), content_size_v( 0 ),\n      viewport_pos_v( 0 ), viewport_size_v( 0 ), drawn_height_v( 0 ),\n''',
    "scrollbar visual height initialization",
)
text = replace_once(
    text,
    '''scrollbar &scrollbar::viewport_size( int vsize )\n{\n    viewport_size_v = vsize;\n    return *this;\n}\n\n''',
    '''scrollbar &scrollbar::viewport_size( int vsize )\n{\n    viewport_size_v = vsize;\n    return *this;\n}\n\nscrollbar &scrollbar::height( int rows )\n{\n    drawn_height_v = std::max( 0, rows );\n    return *this;\n}\n\n''',
    "scrollbar visual height setter",
)

old_apply = '''void scrollbar::apply( const catacurses::window &window, const bool draw_unneeded )\n{\n    const int absolute_x = getbegx( window ) + offset_x_v;\n    const int absolute_y = getbegy( window ) + offset_y_v;\n    const int drawn_height = std::max( 1, viewport_size_v );\n    scrollbar_area = inclusive_rectangle<point>( point( absolute_x, absolute_y ),\n                     point( absolute_x, absolute_y + drawn_height - 1 ) );\n    thumb_area.reset();\n\n    if( viewport_size_v >= content_size_v || content_size_v <= 0 || viewport_size_v < 3 ) {\n        dragging = false;\n        if( draw_unneeded && viewport_size_v > 0 ) {\n            mvwvline( window, point( offset_x_v, offset_y_v ), border_color_v, LINE_XOXO,\n                      viewport_size_v );\n        }\n        return;\n    }\n\n    mvwputch( window, point( offset_x_v, offset_y_v ), arrow_color_v, '^' );\n    mvwputch( window, point( offset_x_v, offset_y_v + viewport_size_v - 1 ), arrow_color_v, 'v' );\n\n    const int slot_size = viewport_size_v - 2;\n    const int bar_size = std::clamp(\n                             static_cast<int>( std::lround( static_cast<double>( slot_size ) *\n                                     static_cast<double>( viewport_size_v ) /\n                                     static_cast<double>( content_size_v ) ) ), 1, slot_size );\n    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :\n                             std::max( 0, content_size_v - viewport_size_v );\n    const int travel = std::max( 0, slot_size - bar_size );\n    const int clamped_position = clamp( viewport_pos_v, 0, max_position );\n    // viewport_pos_v is an entry index.  Map that exact entry position across\n    // the available thumb travel; rendering is quantized only by terminal rows.\n    const int bar_start = max_position > 0 && travel > 0 ?\n                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *\n                                  static_cast<double>( travel ) /\n                                  static_cast<double>( max_position ) ) ) : 0;\n    const int bar_end = bar_start + bar_size;\n    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),\n                 point( absolute_x, absolute_y + bar_end ) );\n\n    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,\n              bar_size );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,\n              slot_size - bar_end );\n}\n'''
new_apply = '''void scrollbar::apply( const catacurses::window &window, const bool draw_unneeded )\n{\n    const int absolute_x = getbegx( window ) + offset_x_v;\n    const int absolute_y = getbegy( window ) + offset_y_v;\n    const int drawn_height = std::max( 1, drawn_height_v > 0 ? drawn_height_v : viewport_size_v );\n    scrollbar_area = inclusive_rectangle<point>( point( absolute_x, absolute_y ),\n                     point( absolute_x, absolute_y + drawn_height - 1 ) );\n    thumb_area.reset();\n\n#if defined(TILES)\n    cata_cursesport::WINDOW *const raw_window = window.get<cata_cursesport::WINDOW>();\n    const auto overlay_for_this = [&]() {\n        return std::find_if( raw_window->pixel_scrollbars.begin(), raw_window->pixel_scrollbars.end(),\n        [&]( const cata_cursesport::pixel_scrollbar_overlay & overlay ) {\n            return overlay.owner == this;\n        } );\n    };\n    const auto clear_pixel_overlay = [&]() {\n        const auto found = overlay_for_this();\n        if( found != raw_window->pixel_scrollbars.end() ) {\n            raw_window->pixel_scrollbars.erase( found );\n            raw_window->draw = true;\n        }\n        pixel_thumb_area.reset();\n    };\n#endif\n\n    if( viewport_size_v >= content_size_v || content_size_v <= 0 || drawn_height < 3 ) {\n        dragging = false;\n#if defined(TILES)\n        clear_pixel_overlay();\n#endif\n        if( draw_unneeded && drawn_height > 0 ) {\n            mvwvline( window, point( offset_x_v, offset_y_v ), border_color_v, LINE_XOXO,\n                      drawn_height );\n        }\n        return;\n    }\n\n    mvwputch( window, point( offset_x_v, offset_y_v ), arrow_color_v, '^' );\n    mvwputch( window, point( offset_x_v, offset_y_v + drawn_height - 1 ), arrow_color_v, 'v' );\n\n    const int slot_size = drawn_height - 2;\n    const int bar_size = std::clamp(\n                             static_cast<int>( std::lround( static_cast<double>( slot_size ) *\n                                     static_cast<double>( viewport_size_v ) /\n                                     static_cast<double>( content_size_v ) ) ), 1, slot_size );\n    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :\n                             std::max( 0, content_size_v - viewport_size_v );\n    const int travel = std::max( 0, slot_size - bar_size );\n    const int clamped_position = clamp( viewport_pos_v, 0, max_position );\n    const int bar_start = max_position > 0 && travel > 0 ?\n                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *\n                                  static_cast<double>( travel ) /\n                                  static_cast<double>( max_position ) ) ) : 0;\n    const int bar_end = bar_start + bar_size;\n    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),\n                 point( absolute_x, absolute_y + bar_end ) );\n\n#if defined(TILES)\n    // SDL can represent positions between terminal rows.  Keep text arrows and a\n    // neutral cell track for compatibility, then composite the thumb in pixels.\n    const int pixel_track_top_abs = ( absolute_y + 1 ) * fontheight;\n    const int pixel_track_height = slot_size * fontheight;\n    const int minimum_thumb = std::min( pixel_track_height, std::max( 4, fontheight / 3 ) );\n    const int pixel_bar_size = std::clamp(\n                                   static_cast<int>( std::lround( static_cast<double>( pixel_track_height ) *\n                                           static_cast<double>( viewport_size_v ) /\n                                           static_cast<double>( content_size_v ) ) ),\n                                   minimum_thumb, pixel_track_height );\n    const int pixel_travel = std::max( 0, pixel_track_height - pixel_bar_size );\n    const int pixel_bar_start = max_position > 0 && pixel_travel > 0 ?\n                                static_cast<int>( std::lround( static_cast<double>( clamped_position ) *\n                                        static_cast<double>( pixel_travel ) /\n                                        static_cast<double>( max_position ) ) ) : 0;\n    const int pixel_x_min = absolute_x * fontwidth;\n    const int pixel_y_min = absolute_y * fontheight;\n    pixel_scrollbar_area = inclusive_rectangle<point>(\n                               point( pixel_x_min, pixel_y_min ),\n                               point( pixel_x_min + fontwidth - 1, pixel_y_min + drawn_height * fontheight - 1 ) );\n    pixel_thumb_area = inclusive_rectangle<point>(\n                           point( pixel_x_min, pixel_track_top_abs + pixel_bar_start ),\n                           point( pixel_x_min + fontwidth - 1,\n                                  pixel_track_top_abs + pixel_bar_start + pixel_bar_size - 1 ) );\n\n    cata_cursesport::pixel_scrollbar_overlay overlay;\n    overlay.owner = this;\n    overlay.x_cell = offset_x_v;\n    overlay.track_top_px = ( offset_y_v + 1 ) * fontheight;\n    overlay.track_height_px = pixel_track_height;\n    overlay.thumb_top_px = overlay.track_top_px + pixel_bar_start;\n    overlay.thumb_height_px = pixel_bar_size;\n    overlay.dragging = dragging;\n    const auto found = overlay_for_this();\n    if( found == raw_window->pixel_scrollbars.end() ) {\n        raw_window->pixel_scrollbars.push_back( overlay );\n    } else {\n        *found = overlay;\n    }\n    raw_window->draw = true;\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, slot_size );\n#else\n    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,\n              bar_size );\n    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,\n              slot_size - bar_end );\n#endif\n}\n'''
text = replace_once(text, old_apply, new_apply, "pixel-aware scrollbar apply")

# Add the pixel input path immediately before the existing cell handler.
anchor = '''bool scrollbar::handle_dragging( const std::string &action, const std::optional<point> &coord,\n                                 int &position )\n{\n'''
pixel_handler = '''#if defined(TILES)\nbool scrollbar::handle_pixel_dragging( const std::string &action, const std::optional<point> &coord,\n                                       int &position )\n{\n    if( !pixel_thumb_area ) {\n        dragging = false;\n        return false;\n    }\n\n    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :\n                             std::max( 0, content_size_v - viewport_size_v );\n    const int track_min = pixel_scrollbar_area.p_min.y + fontheight;\n    const int track_max = pixel_scrollbar_area.p_max.y - fontheight;\n    const int thumb_size = pixel_thumb_area->p_max.y - pixel_thumb_area->p_min.y + 1;\n    const int travel = std::max( 0, track_max - track_min + 1 - thumb_size );\n\n    const auto publish = [&]( const int requested ) {\n        viewport_pos_v = clamp( requested, 0, max_position );\n        position = viewport_pos_v;\n    };\n    const auto drag_to = [&]( const int cursor_y ) {\n        const int thumb_start = clamp( cursor_y - pixel_drag_grab_offset, track_min,\n                                      track_min + travel );\n        const int thumb_offset = thumb_start - track_min;\n        const int requested = travel > 0 && max_position > 0 ?\n                              static_cast<int>( std::lround( static_cast<double>( thumb_offset ) *\n                                      static_cast<double>( max_position ) /\n                                      static_cast<double>( travel ) ) ) : 0;\n        publish( requested );\n    };\n\n    if( dragging && action == "SELECT" ) {\n        dragging = false;\n        pixel_drag_grab_offset = 0;\n        return true;\n    }\n    if( dragging ) {\n        if( ( action == "MOUSE_MOVE" || action == "CLICK_AND_DRAG" ) && coord ) {\n            drag_to( coord->y );\n            return true;\n        }\n        if( action != "MOUSE_MOVE" && action != "CLICK_AND_DRAG" ) {\n            dragging = false;\n            pixel_drag_grab_offset = 0;\n        }\n        return false;\n    }\n    if( action == "CLICK_AND_DRAG" && coord && pixel_thumb_area->contains( *coord ) ) {\n        dragging = true;\n        pixel_drag_grab_offset = clamp( coord->y - pixel_thumb_area->p_min.y, 0, thumb_size - 1 );\n        return true;\n    }\n    if( action == "SELECT" && coord && pixel_scrollbar_area.contains( *coord ) ) {\n        if( coord->y < track_min ) {\n            publish( position - 1 );\n        } else if( coord->y > track_max ) {\n            publish( position + 1 );\n        } else if( coord->y < pixel_thumb_area->p_min.y ) {\n            publish( position - std::max( 1, viewport_size_v ) );\n        } else if( coord->y > pixel_thumb_area->p_max.y ) {\n            publish( position + std::max( 1, viewport_size_v ) );\n        }\n        return true;\n    }\n    return false;\n}\n#endif\n\nbool scrollbar::handle_input( const std::string &action, const input_context &ctxt,\n                              ui_scroll_model &state )\n{\n    int position = state.viewport_pos();\n#if defined(TILES)\n    if( pixel_thumb_area ) {\n        const bool handled = handle_pixel_dragging( action, ctxt.get_coordinates_pixel(), position );\n        if( handled ) {\n            state.set_viewport_pos( position );\n        }\n        return handled;\n    }\n#endif\n    const bool handled = handle_dragging( action, ctxt.get_coordinates_text( catacurses::stdscr ),\n                                          position );\n    if( handled ) {\n        state.set_viewport_pos( position );\n    }\n    return handled;\n}\n\n'''
text = replace_once(text, anchor, pixel_handler + anchor, "pixel scrollbar input handler")
p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# SDL backend: draw a narrow track and a pixel-positioned thumb after the
# curses window cells.  This is real pixel movement, not Unicode block tricks.
# ---------------------------------------------------------------------------
p = Path("src/sdltiles.cpp")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        update = draw_window( font, w );\n\n        // A reshape palette is a normal curses window with small tileset-backed\n''',
    '''        update = draw_window( font, w );\n\n        if( !win->pixel_scrollbars.empty() ) {\n            const SDL_Color &track_color = color_as_sdl(\n                    static_cast<unsigned char>( catacurses::dark_gray ) );\n            const SDL_Color &thumb_color = color_as_sdl(\n                    static_cast<unsigned char>( catacurses::cyan ) );\n            const SDL_Color &drag_color = color_as_sdl(\n                    static_cast<unsigned char>( catacurses::magenta ) );\n            const int track_width = std::max( 2, fontwidth / 5 );\n            const int thumb_width = std::max( track_width + 2, fontwidth / 2 );\n            for( const cata_cursesport::pixel_scrollbar_overlay &scroll : win->pixel_scrollbars ) {\n                const int cell_left = ( win->pos.x + scroll.x_cell ) * fontwidth;\n                const int center_x = cell_left + fontwidth / 2;\n                SDL_Rect track_rect = { center_x - track_width / 2,\n                                        win->pos.y * fontheight + scroll.track_top_px,\n                                        track_width, scroll.track_height_px };\n                SetRenderDrawColor( renderer, track_color.r, track_color.g, track_color.b, 255 );\n                RenderFillRect( renderer, &track_rect );\n\n                const SDL_Color &bar = scroll.dragging ? drag_color : thumb_color;\n                SDL_Rect thumb_rect = { center_x - thumb_width / 2,\n                                        win->pos.y * fontheight + scroll.thumb_top_px,\n                                        thumb_width, scroll.thumb_height_px };\n                SetRenderDrawColor( renderer, bar.r, bar.g, bar.b, 255 );\n                RenderFillRect( renderer, &thumb_rect );\n            }\n            update = true;\n        }\n\n        // A reshape palette is a normal curses window with small tileset-backed\n''',
    "SDL pixel scrollbar compositor",
)
p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Callers: use centralized pixel-aware input.  The reshape palette also tells
# the helper its actual 2-row-per-entry visual height instead of pretending its
# height equals the number of visible entries.
# ---------------------------------------------------------------------------
p = Path("src/crafting_gui.cpp")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''        if( recipes_visible &&\n            recipe_scrollbar.handle_dragging( action, screen_pos, state.recipe_scroll ) ) {\n            continue;\n        }\n        if( inspector_visible &&\n            inspector_scrollbar.handle_dragging( action, screen_pos, state.inspector_scroll ) ) {\n            continue;\n        }\n''',
    '''        if( recipes_visible && recipe_scrollbar.handle_input( action, ctxt, state.recipe_scroll ) ) {\n            continue;\n        }\n        if( inspector_visible && inspector_scrollbar.handle_input( action, ctxt, state.inspector_scroll ) ) {\n            continue;\n        }\n''',
    "crafting pixel scrollbar input",
)
p.write_text(text, encoding="utf-8")

p = Path("src/veh_interact.cpp")
text = p.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_dragging( action, screen_pos, part_scroll ) ) {\n            return true;\n        }\n        if( reshape_info ) {\n            if( reshape_scrollbar.handle_dragging( action, screen_pos, reshape_info->variant_scroll ) ) {\n                return true;\n            }\n        } else if( !msg.has_value() &&\n                   part_detail_scrollbar.handle_dragging( action, screen_pos, part_detail_scroll ) ) {\n            return true;\n        }\n    }\n''',
    '''    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_input( action, main_context, part_scroll ) ) {\n            return true;\n        }\n        if( reshape_info ) {\n            if( reshape_scrollbar.handle_input( action, main_context, reshape_info->variant_scroll ) ) {\n                return true;\n            }\n        } else if( !msg.has_value() &&\n                   part_detail_scrollbar.handle_input( action, main_context, part_detail_scroll ) ) {\n            return true;\n        }\n    }\n''',
    "vehicle pixel scrollbar input",
)
text = replace_once(
    text,
    '''        reshape_scrollbar.offset_x( width - 1 ).offset_y( first_row )\n        .model( reshape_info->variant_scroll ).apply( w_msg );\n''',
    '''        reshape_scrollbar.offset_x( width - 1 ).offset_y( first_row )\n        .height( std::max( 3, footer_y - first_row ) )\n        .model( reshape_info->variant_scroll ).apply( w_msg );\n''',
    "reshape actual visual scrollbar height",
)
p.write_text(text, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Add pixel-accurate shared scrollbar movement\n", encoding="utf-8"
)
