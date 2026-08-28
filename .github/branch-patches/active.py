from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Add an opt-in compact path. Existing callers keep using configure(), whose
# size checks, icon placement, and rendering semantics remain unchanged.
replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        void close() {
            overlay_.close();
            action_.reset();
            icon_.clear();
            pos_ = point::zero;
            size_ = point::zero;
            hovered_ = false;
        }

        void configure( const catacurses::window &parent, point pos, point size,
                        ui_action_entry action, std::string icon,
                        const ui_icon_button_style &style = ui_icon_button_style() ) {
            const int parent_w = getmaxx( parent );
            const int parent_h = getmaxy( parent );
            if( parent_w < 3 || parent_h < 3 || size.x < 3 || size.y < 3 || icon.empty() ) {
                close();
                return;
            }
            size.x = std::min( size.x, parent_w );
            size.y = std::min( size.y, parent_h );
            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_w - size.x ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_h - size.y ) );
            pos_ = pos;
            size_ = size;
            action_ = std::move( action );
            icon_ = std::move( icon );
            style_ = style;
            overlay_.configure( parent, pos_, size_.x, size_.y );
        }

        bool is_configured() const {
            return action_.has_value() && size_.x >= 3 && size_.y >= 3;
        }
''',
    '''        void close() {
            overlay_.close();
            action_.reset();
            icon_.clear();
            pos_ = point::zero;
            size_ = point::zero;
            hovered_ = false;
            compact_ = false;
        }

        void configure( const catacurses::window &parent, point pos, point size,
                        ui_action_entry action, std::string icon,
                        const ui_icon_button_style &style = ui_icon_button_style() ) {
            configure_impl( parent, pos, size, std::move( action ), std::move( icon ),
                            style, false );
        }

        /**
         * Opt-in compact rendering for very small HUD controls.
         *
         * Unlike configure(), this permits a two-cell-wide button and allows
         * content wider than the normal interior to use the border row.  That
         * makes tiny attached launchers and short status strings possible
         * without weakening the normal control contract for existing menus.
         */
        void configure_compact( const catacurses::window &parent, point pos, point size,
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
    "icon button compact API",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''            draw_border( window, border );
            const std::string fill_row( std::max( 0, size_.x - 2 ), ' ' );
            for( int y = 1; y < size_.y - 1; ++y ) {
                trim_and_print( window, point( 1, y ), size_.x - 2, fill, fill_row );
            }
            const int icon_w = std::max( 1, utf8_width( icon_ ) );
            const int icon_x = std::max( 1, ( size_.x - icon_w ) / 2 );
            const int icon_y = std::clamp( size_.y / 2, 1, size_.y - 2 );
            trim_and_print( window, point( icon_x, icon_y ),
                            std::max( 1, size_.x - icon_x - 1 ), icon_color, icon_ );
            overlay_.refresh();
        }

    private:
        ui_overlay overlay_;
''',
    '''            draw_border( window, border );
            const int interior_width = std::max( 0, size_.x - 2 );
            if( interior_width > 0 ) {
                const std::string fill_row( interior_width, ' ' );
                for( int y = 1; y < size_.y - 1; ++y ) {
                    trim_and_print( window, point( 1, y ), interior_width, fill, fill_row );
                }
            }

            const int icon_w = std::max( 1, utf8_width( icon_ ) );
            int icon_x = std::max( 1, ( size_.x - icon_w ) / 2 );
            int icon_width = std::max( 1, size_.x - icon_x - 1 );
            if( compact_ && icon_w > interior_width ) {
                icon_x = std::max( 0, ( size_.x - icon_w ) / 2 );
                icon_width = std::max( 1, size_.x - icon_x );
            }
            const int icon_y = std::clamp( size_.y / 2, 1, size_.y - 2 );
            trim_and_print( window, point( icon_x, icon_y ),
                            icon_width, icon_color, icon_ );
            overlay_.refresh();
        }

    private:
        void configure_impl( const catacurses::window &parent, point pos, point size,
                             ui_action_entry action, std::string icon,
                             const ui_icon_button_style &style, const bool compact ) {
            const point minimum = compact ? point( 2, 3 ) : point( 3, 3 );
            const int parent_w = getmaxx( parent );
            const int parent_h = getmaxy( parent );
            if( parent_w < minimum.x || parent_h < minimum.y ||
                size.x < minimum.x || size.y < minimum.y || icon.empty() ) {
                close();
                return;
            }
            size.x = std::min( size.x, parent_w );
            size.y = std::min( size.y, parent_h );
            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_w - size.x ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_h - size.y ) );
            pos_ = pos;
            size_ = size;
            action_ = std::move( action );
            icon_ = std::move( icon );
            style_ = style;
            compact_ = compact;
            overlay_.configure( parent, pos_, size_.x, size_.y );
        }

        ui_overlay overlay_;
''',
    "icon button compact draw",
)

replace_once(
    "src/ui_helpers/controls/icon_button.h",
    '''        point pos_ = point::zero;
        point size_ = point::zero;
        bool hovered_ = false;
};
''',
    '''        point pos_ = point::zero;
        point size_ = point::zero;
        bool hovered_ = false;
        bool compact_ = false;
};
''',
    "icon button compact state",
)

# Use the compact helper only for this HUD. Screen code still owns placement and
# exact cell geometry; helper code owns rendering and interaction.
replace_once(
    "src/game.cpp",
    '''static constexpr int safemode_corner_button_count = 5;
static constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;
static const point safemode_corner_icon_pixels( 6, 6 );

static point safemode_corner_button_size()
{
    return ui_icon_button::square_size_for_icon( catacurses::stdscr,
            safemode_corner_icon_pixels );
}

// The pixel minimap is only the anchor.  All controls render against stdscr so
// the expanded column is free to sit immediately outside the panel's left edge.
static point safemode_corner_launcher_size()
{
    const point button_size = safemode_corner_button_size();
    return point( std::max( 3, ( button_size.x + 1 ) / 2 ), button_size.y );
}
''',
    '''static constexpr int safemode_corner_button_count = 5;
static constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;

// The standard icon-button sizing intentionally keeps normal menu controls roomy.
// This HUD opts into a much denser 3x4-cell control, with a two-cell-wide launcher.
static const point safemode_corner_button_cells( 3, 4 );
static const point safemode_corner_launcher_cells( 2, 4 );

static point safemode_corner_button_size()
{
    return safemode_corner_button_cells;
}

// The pixel minimap is only the anchor.  All controls render against stdscr so
// the expanded column is free to sit immediately outside the panel's left edge.
static point safemode_corner_launcher_size()
{
    return safemode_corner_launcher_cells;
}
''',
    "safemode compact cell geometry",
)

replace_once(
    "src/game.cpp",
    '''static point safemode_corner_launcher_pos( const catacurses::window &panel )
{
    const point size = safemode_corner_button_size();
    // Share the launcher's left border with the bottom palette cell's right border.
    return point( getbegx( panel ) - 1,
                  getbegy( panel ) + getmaxy( panel ) - size.y );
}
''',
    '''static point safemode_corner_launcher_pos( const catacurses::window &panel )
{
    const point size = safemode_corner_button_size();
    return point( getbegx( panel ),
                  getbegy( panel ) + getmaxy( panel ) - size.y );
}
''',
    "safemode compact launcher position",
)

replace_once(
    "src/game.cpp",
    '''    ui_icon_button_style launcher_style;
    launcher_style.border = c_light_gray;
    launcher_style.fill = i_dark_gray;
    launcher_style.icon = c_light_gray;
    launcher_style.hover_border = c_white;
    launcher_style.hover_fill = i_light_gray;
    launcher_style.hover_icon = c_white;
    safemode_corner_launcher.configure( catacurses::stdscr, launcher_pos, launcher_size,
                                        ui_action_entry( "", "SAFE_CORNER_EXPAND" ),
                                        "<", launcher_style );
''',
    '''    ui_icon_button_style launcher_style;
    launcher_style.border = c_light_gray;
    launcher_style.fill = c_black;
    launcher_style.icon = c_light_gray;
    launcher_style.hover_border = c_white;
    launcher_style.hover_fill = c_black;
    launcher_style.hover_icon = c_white;
    launcher_style.selected_fill = c_black;
    launcher_style.disabled_fill = c_black;
    safemode_corner_launcher.configure_compact(
        catacurses::stdscr, launcher_pos, launcher_size,
        ui_action_entry( "", "SAFE_CORNER_EXPAND" ), "<", launcher_style );
''',
    "safemode compact launcher helper",
)

replace_once(
    "src/game.cpp",
    '''            ui_icon_button_style style;
            ui_action_entry action( "", is_safe ? "SAFE_MODE_TOGGLE" :
                                    string_format( "SAFE_RESERVED_%d", i ), is_safe );
            std::string icon = is_safe ? "[!]" : "■";

            style.border = c_light_gray;
            style.fill = i_dark_gray;
            style.hover_border = c_white;
            style.hover_fill = i_light_gray;
            if( is_safe ) {
                const nc_color state_color = enabled ? c_light_green : c_light_red;
                style.icon = state_color;
                style.hover_icon = state_color;
                style.selected_icon = state_color;
            } else {
                // Reserved cells stay disabled, but remain visually present as grey tiles.
                style.disabled_border = c_light_gray;
                style.disabled_fill = i_dark_gray;
                style.disabled_icon = c_dark_gray;
            }

            safemode_corner_buttons[i].configure(
                catacurses::stdscr,
                safemode_corner_palette_pos( w_pixel_minimap, i ),
                button_size, std::move( action ), std::move( icon ), style );
''',
    '''            ui_icon_button_style style;
            ui_action_entry action( "", is_safe ? "SAFE_MODE_TOGGLE" :
                                    string_format( "SAFE_RESERVED_%d", i ), is_safe );
            std::string icon = is_safe ? "[!]" : "█";

            style.border = c_light_gray;
            style.fill = c_black;
            style.hover_border = c_white;
            style.hover_fill = c_black;
            style.selected_fill = c_black;
            style.disabled_fill = c_black;
            if( is_safe ) {
                const nc_color state_color = enabled ? c_light_green : c_light_red;
                style.icon = state_color;
                style.hover_icon = state_color;
                style.selected_icon = state_color;
            } else {
                // Reserved cells stay disabled, but remain visually present as one grey tile.
                style.disabled_border = c_light_gray;
                style.disabled_icon = c_dark_gray;
            }

            safemode_corner_buttons[i].configure_compact(
                catacurses::stdscr,
                safemode_corner_palette_pos( w_pixel_minimap, i ),
                button_size, std::move( action ), std::move( icon ), style );
''',
    "safemode compact cell rendering",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Make safemode palette truly compact\n", encoding="utf-8"
)
