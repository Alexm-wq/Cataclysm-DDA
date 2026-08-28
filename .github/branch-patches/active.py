from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Add a pixel-space renderer API for icon buttons. This is opt-in; the normal
# curses-cell icon-button path remains unchanged for existing menus.
replace_once(
    "src/sdltiles.h",
    '''const SDL_Renderer_Ptr &get_sdl_renderer();\n''',
    '''struct ui_pixel_icon_button_overlay {
    const void *owner = nullptr;
    point pos_pixels = point::zero;
    point size_pixels = point::zero;
    int border_color_pair = 0;
    int fill_color_pair = 0;
    int icon_color_pair = 0;
    std::string icon;
};
void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay );
void clear_ui_pixel_icon_button( const void *owner );

const SDL_Renderer_Ptr &get_sdl_renderer();
''',
    "pixel icon-button API",
)

replace_once(
    "src/sdltiles.cpp",
    '''static bool needupdate = false;
static bool need_invalidate_framebuffers = false;
palette_array windowsPalette;
''',
    '''static bool needupdate = false;
static bool need_invalidate_framebuffers = false;
palette_array windowsPalette;
static std::vector<ui_pixel_icon_button_overlay> ui_pixel_icon_buttons;

void set_ui_pixel_icon_button( const ui_pixel_icon_button_overlay &overlay )
{
    if( overlay.owner == nullptr ) {
        return;
    }
    const auto found = std::find_if( ui_pixel_icon_buttons.begin(), ui_pixel_icon_buttons.end(),
    [&]( const ui_pixel_icon_button_overlay & existing ) {
        return existing.owner == overlay.owner;
    } );
    if( found == ui_pixel_icon_buttons.end() ) {
        ui_pixel_icon_buttons.push_back( overlay );
    } else {
        *found = overlay;
    }
    needupdate = true;
}

void clear_ui_pixel_icon_button( const void *owner )
{
    if( owner == nullptr ) {
        return;
    }
    const auto new_end = std::remove_if( ui_pixel_icon_buttons.begin(), ui_pixel_icon_buttons.end(),
    [&]( const ui_pixel_icon_button_overlay & existing ) {
        return existing.owner == owner;
    } );
    if( new_end != ui_pixel_icon_buttons.end() ) {
        ui_pixel_icon_buttons.erase( new_end, ui_pixel_icon_buttons.end() );
        needupdate = true;
    }
}
''',
    "pixel icon-button registry",
)

replace_once(
    "src/sdltiles.cpp",
    '''void refresh_display()
{
''',
    r'''static SDL_Color ui_pixel_button_color( const int pair_index )
{
    const int clamped_pair = std::clamp(
                                 pair_index, 0,
                                 static_cast<int>( cata_cursesport::colorpairs.size() ) - 1 );
    return color_as_sdl( static_cast<unsigned char>(
                             cata_cursesport::colorpairs[clamped_pair].FG ) );
}

static void draw_ui_pixel_button_bitmap( const ui_pixel_icon_button_overlay &button,
        const SDL_Color &color )
{
    const int inner_w = std::max( 0, button.size_pixels.x - 4 );
    const int inner_h = std::max( 0, button.size_pixels.y - 4 );
    if( inner_w <= 0 || inner_h <= 0 ) {
        return;
    }

    SetRenderDrawColor( renderer, color.r, color.g, color.b, 255 );

    if( button.icon == "■" || button.icon == "█" || button.icon == "tile" ) {
        const int tile_side = std::max( 3, std::min( { 6, inner_w, inner_h } ) );
        SDL_Rect tile = {
            button.pos_pixels.x + ( button.size_pixels.x - tile_side ) / 2,
            button.pos_pixels.y + ( button.size_pixels.y - tile_side ) / 2,
            tile_side, tile_side
        };
        RenderFillRect( renderer, &tile );
        return;
    }

    const std::array<unsigned char, 5> glyph_left = { 7, 4, 4, 4, 7 };
    const std::array<unsigned char, 5> glyph_right = { 7, 1, 1, 1, 7 };
    const std::array<unsigned char, 5> glyph_bang = { 2, 2, 2, 0, 2 };
    const std::array<unsigned char, 5> glyph_chevron_left = { 1, 2, 4, 2, 1 };

    const auto draw_glyph = [&]( const std::array<unsigned char, 5> &rows,
                                 const int origin_x, const int origin_y,
                                 const int scale ) {
        for( int y = 0; y < 5; ++y ) {
            for( int x = 0; x < 3; ++x ) {
                if( ( rows[y] & ( 1 << ( 2 - x ) ) ) == 0 ) {
                    continue;
                }
                SDL_Rect pixel = { origin_x + x * scale, origin_y + y * scale, scale, scale };
                RenderFillRect( renderer, &pixel );
            }
        }
    };

    if( button.icon == "[!]" ) {
        const int scale = std::max( 1, std::min( inner_w / 11, inner_h / 5 ) );
        const int total_w = 11 * scale;
        const int total_h = 5 * scale;
        const int left = button.pos_pixels.x + ( button.size_pixels.x - total_w ) / 2;
        const int top = button.pos_pixels.y + ( button.size_pixels.y - total_h ) / 2;
        draw_glyph( glyph_left, left, top, scale );
        draw_glyph( glyph_bang, left + 4 * scale, top, scale );
        draw_glyph( glyph_right, left + 8 * scale, top, scale );
    } else if( button.icon == "<" ) {
        const int scale = std::max( 1, std::min( inner_w / 3, inner_h / 5 ) );
        const int total_w = 3 * scale;
        const int total_h = 5 * scale;
        const int left = button.pos_pixels.x + ( button.size_pixels.x - total_w ) / 2;
        const int top = button.pos_pixels.y + ( button.size_pixels.y - total_h ) / 2;
        draw_glyph( glyph_chevron_left, left, top, scale );
    }
}

static void draw_ui_pixel_icon_buttons()
{
    for( const ui_pixel_icon_button_overlay &button : ui_pixel_icon_buttons ) {
        if( button.owner == nullptr || button.size_pixels.x < 3 || button.size_pixels.y < 3 ) {
            continue;
        }

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
}

void refresh_display()
{
''',
    "pixel icon-button renderer",
)

replace_once(
    "src/sdltiles.cpp",
    '''#else
    RenderCopy( renderer, display_buffer, nullptr, nullptr );
#endif

#if defined(__ANDROID__)
''',
    '''#else
    RenderCopy( renderer, display_buffer, nullptr, nullptr );
#endif

    // Pixel-space HUD controls are composited after the terminal framebuffer so
    // their geometry is not quantized to character-cell aspect ratios.
    draw_ui_pixel_icon_buttons();

#if defined(__ANDROID__)
''',
    "pixel icon-button composite",
)

# Add an explicit pixel-mode to the icon helper. Existing configure() and
# configure_compact() behavior is preserved.
replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void close() {
            overlay_.close();
            action_.reset();
            icon_.clear();
            pos_ = point::zero;
            size_ = point::zero;
            hovered_ = false;
            compact_ = false;
        }
''',
    '''        void close() {
#if defined(TILES)
            clear_ui_pixel_icon_button( this );
#endif
            overlay_.close();
            action_.reset();
            icon_.clear();
            pos_ = point::zero;
            size_ = point::zero;
#if defined(TILES)
            pixel_pos_ = point::zero;
            pixel_size_ = point::zero;
            pixel_mode_ = false;
#endif
            hovered_ = false;
            compact_ = false;
        }
''',
    "icon-button close pixel state",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void configure_compact( const catacurses::window &parent, point pos, point size,
                                ui_action_entry action, std::string icon,
                                const ui_icon_button_style &style = ui_icon_button_style() ) {
            configure_impl( parent, pos, size, std::move( action ), std::move( icon ),
                            style, true );
        }

        bool is_configured() const {
            const point minimum = compact_ ? point( 2, 3 ) : point( 3, 3 );
            return action_.has_value() && size_.x >= minimum.x && size_.y >= minimum.y;
        }
''',
    '''        void configure_compact( const catacurses::window &parent, point pos, point size,
                                ui_action_entry action, std::string icon,
                                const ui_icon_button_style &style = ui_icon_button_style() ) {
            configure_impl( parent, pos, size, std::move( action ), std::move( icon ),
                            style, true );
        }

#if defined(TILES)
        /**
         * Opt-in exact pixel rendering for tiny SDL HUD controls. Pixel geometry
         * is screen-relative and is intentionally independent of terminal-cell
         * aspect ratio. Normal menus continue to use configure().
         */
        void configure_pixel( const catacurses::window &parent, point pixel_pos, point pixel_size,
                              ui_action_entry action, std::string icon,
                              const ui_icon_button_style &style = ui_icon_button_style() ) {
            clear_ui_pixel_icon_button( this );
            overlay_.close();
            if( !parent || pixel_size.x < 3 || pixel_size.y < 3 || icon.empty() ) {
                close();
                return;
            }

            const window_dimensions screen_dim = get_window_dimensions( catacurses::stdscr );
            const int cell_w = std::max( 1, screen_dim.scaled_font_size.x );
            const int cell_h = std::max( 1, screen_dim.scaled_font_size.y );
            const point pixel_max = pixel_pos + pixel_size - point( 1, 1 );

            pixel_pos_ = pixel_pos;
            pixel_size_ = pixel_size;
            pos_ = point( pixel_pos.x / cell_w, pixel_pos.y / cell_h );
            size_ = point( std::max( 1, pixel_max.x / cell_w - pos_.x + 1 ),
                           std::max( 1, pixel_max.y / cell_h - pos_.y + 1 ) );
            action_ = std::move( action );
            icon_ = std::move( icon );
            style_ = style;
            compact_ = false;
            pixel_mode_ = true;
        }
#endif

        bool is_configured() const {
#if defined(TILES)
            if( pixel_mode_ ) {
                return action_.has_value() && pixel_size_.x >= 3 && pixel_size_.y >= 3;
            }
#endif
            const point minimum = compact_ ? point( 2, 3 ) : point( 3, 3 );
            return action_.has_value() && size_.x >= minimum.x && size_.y >= minimum.y;
        }
''',
    "icon-button pixel configure",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos && contains( *parent_pos );
        }

        ui_action_result handle_input( const std::string &action,
''',
    '''        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos && contains( *parent_pos );
        }

#if defined(TILES)
        bool contains_pixel( const point &screen_pixel ) const {
            if( !pixel_mode_ || !is_configured() ) {
                return false;
            }
            return inclusive_rectangle<point>( pixel_pos_,
                                                pixel_pos_ + pixel_size_ - point( 1, 1 ) ).contains(
                       screen_pixel );
        }

        void update_hover_pixel( const std::optional<point> &screen_pixel ) {
            hovered_ = screen_pixel && contains_pixel( *screen_pixel );
        }

        ui_action_result handle_pixel_input( const std::string &action,
                                             const std::optional<point> &screen_pixel ) {
            if( !pixel_mode_ || !is_configured() ) {
                return {};
            }
            if( action == "MOUSE_MOVE" ) {
                update_hover_pixel( screen_pixel );
                return { hovered_ ? ui_action_result_type::handled : ui_action_result_type::ignored,
                         std::nullopt };
            }
            if( action != "SELECT" && action != "CONFIRM" ) {
                return {};
            }
            if( action == "SELECT" && ( !screen_pixel || !contains_pixel( *screen_pixel ) ) ) {
                return {};
            }
            return { action_->enabled ? ui_action_result_type::activated :
                     ui_action_result_type::disabled, *action_ };
        }
#endif

        ui_action_result handle_input( const std::string &action,
''',
    "icon-button pixel input",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void draw( const catacurses::window &parent ) {
            if( !is_configured() ) {
                overlay_.close();
                return;
            }
            overlay_.configure( parent, pos_, size_.x, size_.y );
''',
    '''        void draw( const catacurses::window &parent ) {
            if( !is_configured() ) {
#if defined(TILES)
                clear_ui_pixel_icon_button( this );
#endif
                overlay_.close();
                return;
            }
#if defined(TILES)
            if( pixel_mode_ ) {
                nc_color border = style_.border;
                nc_color fill = style_.fill;
                nc_color icon_color = style_.icon;
                if( !action_->enabled ) {
                    border = style_.disabled_border;
                    fill = style_.disabled_fill;
                    icon_color = style_.disabled_icon;
                } else if( hovered_ ) {
                    border = style_.hover_border;
                    fill = style_.hover_fill;
                    icon_color = style_.hover_icon;
                } else if( action_->selected ) {
                    border = style_.selected_border;
                    fill = style_.selected_fill;
                    icon_color = style_.selected_icon;
                }

                ui_pixel_icon_button_overlay render;
                render.owner = this;
                render.pos_pixels = pixel_pos_;
                render.size_pixels = pixel_size_;
                render.border_color_pair = border.to_color_pair_index();
                render.fill_color_pair = fill.to_color_pair_index();
                render.icon_color_pair = icon_color.to_color_pair_index();
                render.icon = icon_;
                set_ui_pixel_icon_button( render );
                return;
            }
#endif
            overlay_.configure( parent, pos_, size_.x, size_.y );
''',
    "icon-button pixel draw",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void configure_impl( const catacurses::window &parent, point pos, point size,
                             ui_action_entry action, std::string icon,
                             const ui_icon_button_style &style, const bool compact ) {
            const point minimum = compact ? point( 2, 3 ) : point( 3, 3 );
''',
    '''        void configure_impl( const catacurses::window &parent, point pos, point size,
                             ui_action_entry action, std::string icon,
                             const ui_icon_button_style &style, const bool compact ) {
#if defined(TILES)
            clear_ui_pixel_icon_button( this );
            pixel_mode_ = false;
            pixel_pos_ = point::zero;
            pixel_size_ = point::zero;
#endif
            const point minimum = compact ? point( 2, 3 ) : point( 3, 3 );
''',
    "icon-button normal mode clears pixel",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        point pos_ = point::zero;
        point size_ = point::zero;
        bool hovered_ = false;
        bool compact_ = false;
''',
    '''        point pos_ = point::zero;
        point size_ = point::zero;
#if defined(TILES)
        point pixel_pos_ = point::zero;
        point pixel_size_ = point::zero;
        bool pixel_mode_ = false;
#endif
        bool hovered_ = false;
        bool compact_ = false;
''',
    "icon-button pixel fields",
)

# The desired palette has five reserved squares plus the safemode square.
replace_once(
    "src/game.h",
    '''        std::array<ui_icon_button, 5> safemode_corner_buttons; // NOLINT(cata-serialize)
''',
    '''        std::array<ui_icon_button, 6> safemode_corner_buttons; // NOLINT(cata-serialize)
''',
    "safemode six-button storage",
)

replace_once(
    "src/game.h",
    '''        action_id get_safemode_mouse_action( const point &p );
''',
    '''        action_id get_safemode_mouse_action( const point &p,
                const std::optional<point> &pixel_p = std::nullopt );
''',
    "safemode pixel click declaration",
)

# Replace the cell-quantized HUD geometry with exact SDL pixel geometry while
# retaining the current curses fallback for non-TILES builds.
p = Path("src/game.cpp")
text = p.read_text(encoding="utf-8")
start_marker = "static constexpr int safemode_corner_button_count = 5;"
end_marker = "void game::draw_safemode_mouse_controls()"
if text.count(start_marker) != 1:
    raise SystemExit(f"safemode geometry start: expected 1 anchor, found {text.count(start_marker)}")
if text.count(end_marker) != 1:
    raise SystemExit(f"safemode geometry end: expected 1 anchor, found {text.count(end_marker)}")
start = text.index(start_marker)
end = text.index(end_marker, start)
new_geometry = r'''static constexpr int safemode_corner_button_count = 6;
static constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;

#if defined(TILES)
static constexpr int safemode_corner_button_base_pixels = 16;
static constexpr int safemode_corner_launcher_base_pixels = 8;

static int safemode_corner_ui_scale()
{
    return std::max( 1, get_scaling_factor() );
}

static point safemode_corner_button_pixel_size()
{
    const int side = safemode_corner_button_base_pixels * safemode_corner_ui_scale();
    return point( side, side );
}

static point safemode_corner_launcher_pixel_size()
{
    const int scale = safemode_corner_ui_scale();
    return point( safemode_corner_launcher_base_pixels * scale,
                  safemode_corner_button_base_pixels * scale );
}

static point safemode_corner_palette_pixel_pos( const catacurses::window &panel, const int index )
{
    const window_dimensions panel_dim = get_window_dimensions( panel );
    const point size = safemode_corner_button_pixel_size();
    const int overlap = safemode_corner_ui_scale();
    const point safe_pos( panel_dim.window_pos_pixel.x - size.x,
                          panel_dim.window_pos_pixel.y + panel_dim.window_size_pixel.y - size.y );
    const int rows_above_bottom = safemode_corner_safe_index - index;
    return point( safe_pos.x, safe_pos.y - rows_above_bottom * ( size.y - overlap ) );
}

static point safemode_corner_launcher_pixel_pos( const catacurses::window &panel )
{
    const point safe_pos = safemode_corner_palette_pixel_pos( panel, safemode_corner_safe_index );
    const point size = safemode_corner_button_pixel_size();
    return point( safe_pos.x + size.x - safemode_corner_ui_scale(), safe_pos.y );
}
#else
static const point safemode_corner_button_cells( 3, 4 );
static const point safemode_corner_launcher_cells( 2, 4 );

static point safemode_corner_button_size()
{
    return safemode_corner_button_cells;
}

static point safemode_corner_launcher_size()
{
    return safemode_corner_launcher_cells;
}

static point safemode_corner_launcher_pos( const catacurses::window &panel )
{
    const point size = safemode_corner_button_size();
    return point( getbegx( panel ),
                  getbegy( panel ) + getmaxy( panel ) - size.y );
}

static point safemode_corner_palette_pos( const catacurses::window &panel, const int index )
{
    const point size = safemode_corner_button_size();
    const point launcher = safemode_corner_launcher_pos( panel );
    const int rows_above_bottom = safemode_corner_safe_index - index;
    return point( getbegx( panel ) - size.x,
                  launcher.y - rows_above_bottom * ( size.y - 1 ) );
}
#endif

static bool safemode_corner_controls_fit( const catacurses::window &panel )
{
    if( !panel || !catacurses::stdscr ) {
        return false;
    }
#if defined(TILES)
    const window_dimensions screen_dim = get_window_dimensions( catacurses::stdscr );
    const point top_button = safemode_corner_palette_pixel_pos( panel, 0 );
    const point launcher = safemode_corner_launcher_pixel_pos( panel );
    const point launcher_size = safemode_corner_launcher_pixel_size();
    return top_button.x >= 0 && top_button.y >= 0 &&
           launcher.x >= 0 && launcher.y >= 0 &&
           launcher.x + launcher_size.x <= screen_dim.window_size_pixel.x &&
           launcher.y + launcher_size.y <= screen_dim.window_size_pixel.y;
#else
    const point size = safemode_corner_button_size();
    const point launcher_size = safemode_corner_launcher_size();
    if( getmaxx( panel ) < launcher_size.x || getmaxy( panel ) < size.y ) {
        return false;
    }
    const point launcher = safemode_corner_launcher_pos( panel );
    const point top_button = safemode_corner_palette_pos( panel, 0 );
    return launcher.x >= 0 && launcher.y >= 0 &&
           launcher.x + launcher_size.x <= getmaxx( catacurses::stdscr ) &&
           launcher.y + launcher_size.y <= getmaxy( catacurses::stdscr ) &&
           top_button.x >= 0 && top_button.y >= 0;
#endif
}

'''
p.write_text(text[:start] + new_geometry + text[end:], encoding="utf-8")

replace_once(
    "src/game.cpp",
    '''    const point button_size = safemode_corner_button_size();
    const point launcher_size = safemode_corner_launcher_size();
    const point launcher_pos = safemode_corner_launcher_pos( w_pixel_minimap );

    ui_icon_button_style launcher_style;
''',
    '''#if defined(TILES)
    const point button_size = safemode_corner_button_pixel_size();
    const point launcher_size = safemode_corner_launcher_pixel_size();
    const point launcher_pos = safemode_corner_launcher_pixel_pos( w_pixel_minimap );
#else
    const point button_size = safemode_corner_button_size();
    const point launcher_size = safemode_corner_launcher_size();
    const point launcher_pos = safemode_corner_launcher_pos( w_pixel_minimap );
#endif

    ui_icon_button_style launcher_style;
''',
    "safemode draw geometry",
)

replace_once(
    "src/game.cpp",
    '''    safemode_corner_launcher.configure_compact(
        catacurses::stdscr, launcher_pos, launcher_size,
        ui_action_entry( "", "SAFE_CORNER_EXPAND" ), "<", launcher_style );
''',
    '''#if defined(TILES)
    safemode_corner_launcher.configure_pixel(
        catacurses::stdscr, launcher_pos, launcher_size,
        ui_action_entry( "", "SAFE_CORNER_EXPAND" ), "<", launcher_style );
#else
    safemode_corner_launcher.configure_compact(
        catacurses::stdscr, launcher_pos, launcher_size,
        ui_action_entry( "", "SAFE_CORNER_EXPAND" ), "<", launcher_style );
#endif
''',
    "safemode pixel launcher",
)

replace_once(
    "src/game.cpp",
    '''            std::string icon = is_safe ? "[!]" : "█";
''',
    '''            std::string icon = is_safe ? "[!]" : "■";
''',
    "safemode single grey tile icon",
)

replace_once(
    "src/game.cpp",
    '''                style.disabled_border = c_light_gray;
                style.disabled_icon = c_dark_gray;
''',
    '''                style.disabled_border = c_light_gray;
                style.disabled_icon = c_light_gray;
''',
    "safemode grey tile color",
)

replace_once(
    "src/game.cpp",
    '''            safemode_corner_buttons[i].configure_compact(
                catacurses::stdscr,
                safemode_corner_palette_pos( w_pixel_minimap, i ),
                button_size, std::move( action ), std::move( icon ), style );
''',
    '''#if defined(TILES)
            safemode_corner_buttons[i].configure_pixel(
                catacurses::stdscr,
                safemode_corner_palette_pixel_pos( w_pixel_minimap, i ),
                button_size, std::move( action ), std::move( icon ), style );
#else
            safemode_corner_buttons[i].configure_compact(
                catacurses::stdscr,
                safemode_corner_palette_pos( w_pixel_minimap, i ),
                button_size, std::move( action ), std::move( icon ), style );
#endif
''',
    "safemode pixel palette buttons",
)

replace_once(
    "src/game.cpp",
    '''            const point safe_pos = safemode_corner_palette_pos(
                                       w_pixel_minimap, safemode_corner_safe_index );
            const point tooltip_pos( std::max( 0, safe_pos.x - tooltip_width - 1 ),
                                     std::max( 0, safe_pos.y - 1 ) );
''',
    '''            const point safe_pos = safe_bounds->p_min;
            const point tooltip_pos( std::max( 0, safe_pos.x - tooltip_width - 1 ),
                                     std::max( 0, safe_pos.y - 1 ) );
''',
    "safemode tooltip cell approximation",
)

replace_once(
    "src/game.cpp",
    '''    const std::optional<point> mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );
    bool tooltip_changed = false;

    if( action == "TIMEOUT" ) {
        tooltip_changed = safemode_corner_tooltip.tick();
    } else if( mouse_pos ) {
        safemode_corner_launcher.handle_input( "MOUSE_MOVE", mouse_pos );
        if( safemode_corner_expanded ) {
            for( ui_icon_button &button : safemode_corner_buttons ) {
                button.handle_input( "MOUSE_MOVE", mouse_pos );
            }
            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );
        } else {
            tooltip_changed = safemode_corner_tooltip.clear_pointer();
        }
    } else if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ) {
        safemode_corner_launcher.update_hover( std::nullopt );
        for( ui_icon_button &button : safemode_corner_buttons ) {
            button.update_hover( std::nullopt );
        }
        tooltip_changed = safemode_corner_tooltip.clear_pointer();
    }
''',
    '''    const std::optional<point> mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );
#if defined(TILES)
    const std::optional<point> pixel_mouse_pos = ctxt.get_coordinates_pixel();
#endif
    bool tooltip_changed = false;

    if( action == "TIMEOUT" ) {
        tooltip_changed = safemode_corner_tooltip.tick();
#if defined(TILES)
    } else if( pixel_mouse_pos ) {
        safemode_corner_launcher.handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );
        if( safemode_corner_expanded ) {
            for( ui_icon_button &button : safemode_corner_buttons ) {
                button.handle_pixel_input( "MOUSE_MOVE", pixel_mouse_pos );
            }
            tooltip_changed = mouse_pos ? safemode_corner_tooltip.update_pointer( mouse_pos ) :
                              safemode_corner_tooltip.clear_pointer();
        } else {
            tooltip_changed = safemode_corner_tooltip.clear_pointer();
        }
#else
    } else if( mouse_pos ) {
        safemode_corner_launcher.handle_input( "MOUSE_MOVE", mouse_pos );
        if( safemode_corner_expanded ) {
            for( ui_icon_button &button : safemode_corner_buttons ) {
                button.handle_input( "MOUSE_MOVE", mouse_pos );
            }
            tooltip_changed = safemode_corner_tooltip.update_pointer( mouse_pos );
        } else {
            tooltip_changed = safemode_corner_tooltip.clear_pointer();
        }
#endif
    } else if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ) {
#if defined(TILES)
        safemode_corner_launcher.update_hover_pixel( std::nullopt );
        for( ui_icon_button &button : safemode_corner_buttons ) {
            button.update_hover_pixel( std::nullopt );
        }
#else
        safemode_corner_launcher.update_hover( std::nullopt );
        for( ui_icon_button &button : safemode_corner_buttons ) {
            button.update_hover( std::nullopt );
        }
#endif
        tooltip_changed = safemode_corner_tooltip.clear_pointer();
    }
''',
    "safemode pixel hover",
)

replace_once(
    "src/game.cpp",
    '''action_id game::get_safemode_mouse_action( const point &p )
{
''',
    '''action_id game::get_safemode_mouse_action( const point &p,
        const std::optional<point> &pixel_p )
{
''',
    "safemode pixel click definition",
)

replace_once(
    "src/game.cpp",
    '''    if( safemode_corner_controls_fit( w_pixel_minimap ) ) {
        const ui_action_result launcher_result = safemode_corner_launcher.handle_input( "SELECT", p );
''',
    '''    if( safemode_corner_controls_fit( w_pixel_minimap ) ) {
#if defined(TILES)
        const ui_action_result launcher_result = safemode_corner_launcher.handle_pixel_input( "SELECT",
                pixel_p );
#else
        const ui_action_result launcher_result = safemode_corner_launcher.handle_input( "SELECT", p );
#endif
''',
    "safemode launcher pixel click",
)

replace_once(
    "src/game.cpp",
    '''            for( int i = 0; i < safemode_corner_button_count; ++i ) {
                const ui_action_result result = safemode_corner_buttons[i].handle_input( "SELECT", p );
''',
    '''            for( int i = 0; i < safemode_corner_button_count; ++i ) {
#if defined(TILES)
                const ui_action_result result = safemode_corner_buttons[i].handle_pixel_input( "SELECT",
                                                pixel_p );
#else
                const ui_action_result result = safemode_corner_buttons[i].handle_input( "SELECT", p );
#endif
''',
    "safemode palette pixel click",
)

replace_once(
    "src/handle_action.cpp",
    '''            const std::optional<point> ui_mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );
            if( ui_mouse_pos ) {
                const action_id safemode_action = get_safemode_mouse_action( *ui_mouse_pos );
                if( safemode_action != ACTION_NULL ) {
                    act = safemode_action;
                }
            }
''',
    '''            const std::optional<point> ui_mouse_pos = ctxt.get_coordinates_text( catacurses::stdscr );
#if defined(TILES)
            const std::optional<point> ui_mouse_pixel = ctxt.get_coordinates_pixel();
#else
            const std::optional<point> ui_mouse_pixel = std::nullopt;
#endif
            if( ui_mouse_pos ) {
                const action_id safemode_action = get_safemode_mouse_action( *ui_mouse_pos,
                                                  ui_mouse_pixel );
                if( safemode_action != ACTION_NULL ) {
                    act = safemode_action;
                }
            }
''',
    "safemode raw pixel click plumbing",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Render compact safemode palette in pixels\n", encoding="utf-8"
)
