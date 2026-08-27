from pathlib import Path

cpp_path = Path('src/veh_interact.cpp')
h_path = Path('src/veh_interact.h')
helper_path = Path('src/ui_dropdown.h')
cpp = cpp_path.read_text()
h = h_path.read_text()


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    return text.replace(old, new, 1)


def replace_function(text, signature, replacement, label):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'{label}: signature not found')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'{label}: opening brace not found')
    depth = 0
    in_string = False
    in_char = False
    escape = False
    i = brace
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
                    return text[:start] + replacement.rstrip() + text[i + 1:]
        i += 1
    raise SystemExit(f'{label}: unterminated function')

helper = r'''#pragma once
#ifndef CATA_SRC_UI_DROPDOWN_H
#define CATA_SRC_UI_DROPDOWN_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "output.h"
#include "point.h"

/** A single row in a lightweight dropdown/context menu. */
struct ui_dropdown_entry {
    std::string label;
    std::string id;
    bool enabled = true;
    bool selected = false;
    std::string disabled_reason;
};

/** Visual policy for ui_dropdown.  Callers may override any color independently. */
struct ui_dropdown_style {
    nc_color border = c_light_cyan;
    nc_color text = c_light_gray;
    nc_color disabled = c_dark_gray;
    nc_color highlight = h_green;
};

/**
 * Reusable mouse-first dropdown/context-menu overlay.
 *
 * Coordinates are relative to a caller-owned parent window, but the menu renders
 * through its own tiny curses window.  That lets it safely sit above SDL-backed
 * Live/Split previews without refreshing an opaque full-screen parent window.
 */
class ui_dropdown
{
    public:
        void close() {
            entries_.clear();
            hovered_ = -1;
            pos_ = point::zero;
            width_ = 0;
            height_ = 0;
            window_ = catacurses::window();
        }

        bool is_open() const {
            return !entries_.empty() && width_ >= 3 && height_ >= 3;
        }

        void configure( const catacurses::window &parent, point pos,
                        std::vector<ui_dropdown_entry> entries,
                        int requested_width = 0,
                        const ui_dropdown_style &style = ui_dropdown_style() ) {
            std::string hovered_id;
            if( hovered_ >= 0 && hovered_ < static_cast<int>( entries_.size() ) ) {
                hovered_id = entries_[hovered_].id;
            }

            style_ = style;
            entries_ = std::move( entries );
            if( entries_.empty() || getmaxx( parent ) < 3 || getmaxy( parent ) < 3 ) {
                close();
                return;
            }

            int widest = 0;
            for( const ui_dropdown_entry &entry : entries_ ) {
                widest = std::max( widest, utf8_width( entry.label ) );
            }
            const int parent_width = getmaxx( parent );
            const int parent_height = getmaxy( parent );
            width_ = requested_width > 0 ? requested_width : widest + 4;
            width_ = std::clamp( width_, 3, parent_width );
            height_ = std::min( static_cast<int>( entries_.size() ) + 2, parent_height );
            if( height_ < 3 ) {
                close();
                return;
            }
            if( static_cast<int>( entries_.size() ) > height_ - 2 ) {
                entries_.resize( height_ - 2 );
            }

            pos.x = std::clamp( pos.x, 0, std::max( 0, parent_width - width_ ) );
            pos.y = std::clamp( pos.y, 0, std::max( 0, parent_height - height_ ) );
            pos_ = pos;

            hovered_ = -1;
            if( !hovered_id.empty() ) {
                for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                    if( entries_[i].id == hovered_id ) {
                        hovered_ = i;
                        break;
                    }
                }
            }
        }

        bool contains( const point &parent_pos ) const {
            return is_open() && parent_pos.x >= pos_.x && parent_pos.x < pos_.x + width_ &&
                   parent_pos.y >= pos_.y && parent_pos.y < pos_.y + height_;
        }

        std::optional<int> hit_test( const point &parent_pos ) const {
            if( !contains( parent_pos ) || parent_pos.x <= pos_.x ||
                parent_pos.x >= pos_.x + width_ - 1 ) {
                return std::nullopt;
            }
            const int row = parent_pos.y - pos_.y - 1;
            if( row < 0 || row >= static_cast<int>( entries_.size() ) ) {
                return std::nullopt;
            }
            return row;
        }

        void update_hover( const std::optional<point> &parent_pos ) {
            hovered_ = parent_pos ? hit_test( *parent_pos ).value_or( -1 ) : -1;
        }

        int hovered_index() const {
            return hovered_;
        }

        const ui_dropdown_entry *entry( const int index ) const {
            return index >= 0 && index < static_cast<int>( entries_.size() ) ? &entries_[index] : nullptr;
        }

        point pos() const {
            return pos_;
        }

        int width() const {
            return width_;
        }

        int height() const {
            return height_;
        }

        void draw( const catacurses::window &parent ) {
            if( !is_open() ) {
                window_ = catacurses::window();
                return;
            }

            const point screen_pos( getbegx( parent ) + pos_.x, getbegy( parent ) + pos_.y );
            const bool needs_window = !window_ || getmaxx( window_ ) != width_ ||
                                      getmaxy( window_ ) != height_ ||
                                      getbegx( window_ ) != screen_pos.x ||
                                      getbegy( window_ ) != screen_pos.y;
            if( needs_window ) {
                window_ = catacurses::newwin( height_, width_, screen_pos );
            }

            werase( window_ );
            draw_border( window_, style_.border );
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                const ui_dropdown_entry &row = entries_[i];
                const bool highlighted = i == hovered_ || row.selected;
                const nc_color color = !row.enabled ? style_.disabled :
                                       highlighted ? style_.highlight : style_.text;
                trim_and_print( window_, point( 1, i + 1 ), std::max( 1, width_ - 2 ), color,
                                row.label );
            }
            wnoutrefresh( window_ );
        }

    private:
        catacurses::window window_;
        std::vector<ui_dropdown_entry> entries_;
        ui_dropdown_style style_;
        point pos_ = point::zero;
        int width_ = 0;
        int height_ = 0;
        int hovered_ = -1;
};

#endif // CATA_SRC_UI_DROPDOWN_H
'''
helper_path.write_text(helper)

h = replace_once(h, '#include "type_id.h"\n', '#include "type_id.h"\n#include "ui_dropdown.h"\n',
                 'include ui_dropdown')
h = replace_once(
    h,
    '''        catacurses::window w_refuel_overlay;\n        // Small transient overlay for Modify/More.  This must not reuse w_border:\n        // refreshing the full-screen border after the SDL map preview masks Live/Split.\n        catacurses::window w_toolbar_dropdown;\n''',
    '''        catacurses::window w_refuel_overlay;\n        // Shared transient-menu renderer.  Every vehicle-editor dropdown/context\n        // menu uses the same highlighting, hit testing, and SDL-safe overlay path.\n        ui_dropdown editor_filter_dropdown_menu;\n        ui_dropdown editor_context_dropdown_menu;\n        ui_dropdown editor_toolbar_dropdown_menu;\n''',
    'replace toolbar window with helpers')
h = replace_once(h, '        void display_editor_controls();\n',
                 '        void display_editor_controls();\n        void display_editor_filter_dropdown();\n',
                 'declare filter dropdown display')

cpp = replace_once(
    cpp,
    '''    // Any transient toolbar window references the old terminal geometry.\n    // Recreate it lazily on the next dropdown redraw after a resize.\n    w_toolbar_dropdown = catacurses::window();\n    w_border = catacurses::newwin( TERMY, TERMX, point::zero );\n''',
    '''    // Transient dropdown windows reference terminal geometry; their helpers\n    // recreate tiny overlay windows lazily after this resize.\n    editor_filter_dropdown_menu.close();\n    editor_context_dropdown_menu.close();\n    editor_toolbar_dropdown_menu.close();\n    w_border = catacurses::newwin( TERMY, TERMX, point::zero );\n''',
    'reset shared dropdowns on resize')

controls = r'''void veh_interact::display_editor_controls()
{
    const int width = getmaxx( w_disp );
    if( width <= 2 ) {
        return;
    }

    // View-mode tabs remain first-class in every editor mode, including reshape.
    {
        const std::array<std::pair<editor_view_mode, std::string>, 3> views = {{
                { editor_view_mode::editor, _( "Editor" ) },
                { editor_view_mode::live, _( "Live" ) },
                { editor_view_mode::split, _( "Split" ) }
            }};
        int view_total_width = 0;
        for( const auto &view : views ) {
            view_total_width += utf8_width( string_format( "[ %s ]", view.second ) ) + 1;
        }
        int view_x = std::max( 1, width - view_total_width );
        for( const auto &view : views ) {
            const std::string label = string_format( "[ %s ]", view.second );
            const int label_width = utf8_width( label );
            if( view_x < width - 1 ) {
                trim_and_print( w_disp, point( view_x, 0 ), std::max( 1, width - view_x - 1 ),
                                view.first == active_editor_view_mode ? h_light_cyan : c_light_cyan,
                                label );
            }
            view_x += label_width + 1;
        }
    }

    if( reshape_info ) {
        trim_and_print( w_disp, point( 1, 1 ), std::max( 1, width - 2 ), c_light_gray,
                        _( "Filter: reshapeable parts only" ) );
        return;
    }

    mvwprintz( w_disp, point( 1, 1 ), c_light_gray, _( "Layer: " ) );
    int layer_x = utf8_width( _( "Layer: " ) ) + 1;
    for( int i = 0; i <= static_cast<int>( editor_layer::roof ); ++i ) {
        const editor_layer layer = static_cast<editor_layer>( i );
        const std::string label = string_format( "[ %s ]", editor_layer_name( layer ) );
        const nc_color color = layer == active_editor_layer ? h_light_cyan : c_light_cyan;
        const int label_width = utf8_width( label );
        if( layer_x < width - 1 ) {
            trim_and_print( w_disp, point( layer_x, 1 ), std::max( 1, width - layer_x - 1 ), color, label );
        }
        layer_x += label_width + 1;
    }

    mvwprintz( w_disp, point( 1, 2 ), c_light_gray, _( "System: " ) );
    int system_x = 0;
    int system_width = 0;
    editor_filter_button_geometry( editor_dropdown::system, system_x, system_width );
    const std::string system_button = string_format( "[ %s ▼ ]",
                                      editor_system_name( active_system_filter ) );
    if( system_x < width - 1 ) {
        trim_and_print( w_disp, point( system_x, 2 ), std::max( 1, width - system_x - 1 ),
                        open_editor_dropdown == editor_dropdown::system ? h_light_cyan : c_light_cyan,
                        system_button );
    }

    const int condition_label_x = system_x + system_width + 2;
    if( condition_label_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_label_x, 2 ), std::max( 1, width - condition_label_x - 1 ),
                        c_light_gray, _( "Condition: " ) );
    }
    int condition_x = 0;
    int condition_width = 0;
    editor_filter_button_geometry( editor_dropdown::condition, condition_x, condition_width );
    const std::string condition_button = string_format( "[ %s ▼ ]",
                                         editor_condition_name( active_condition_filter ) );
    if( condition_x < width - 1 ) {
        trim_and_print( w_disp, point( condition_x, 2 ), std::max( 1, width - condition_x - 1 ),
                        open_editor_dropdown == editor_dropdown::condition ? h_light_cyan : c_light_cyan,
                        condition_button );
    }

    if( vehicle_editor_test_mode_visible ) {
        const int test_x = condition_x + condition_width + 2;
        const std::string test_label = editor_test_mode ? _( "[x] Test" ) : _( "[ ] Test" );
        if( test_x < width - 1 ) {
            trim_and_print( w_disp, point( test_x, 2 ), std::max( 1, width - test_x - 1 ),
                            editor_test_mode ? h_light_red : c_light_gray, test_label );
        }
    }
}

void veh_interact::display_editor_filter_dropdown()
{
    if( reshape_info || open_editor_dropdown == editor_dropdown::none ) {
        editor_filter_dropdown_menu.close();
        return;
    }

    int x = 0;
    int y = 0;
    int dropdown_width = 0;
    int dropdown_height = 0;
    editor_dropdown_geometry( open_editor_dropdown, x, y, dropdown_width, dropdown_height );
    const int max_height = std::max( 0, getmaxy( w_disp ) - y );
    dropdown_height = std::min( dropdown_height, max_height );
    if( dropdown_height < 3 ) {
        editor_filter_dropdown_menu.close();
        return;
    }

    std::vector<ui_dropdown_entry> entries;
    const int option_count = dropdown_height - 2;
    for( int i = 0; i < option_count; ++i ) {
        ui_dropdown_entry entry;
        entry.id = std::to_string( i );
        if( open_editor_dropdown == editor_dropdown::system ) {
            const editor_system_filter filter = static_cast<editor_system_filter>( i );
            entry.label = editor_system_name( filter );
            entry.selected = filter == active_system_filter;
        } else {
            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );
            entry.label = editor_condition_name( filter );
            entry.selected = filter == active_condition_filter;
        }
        entries.push_back( std::move( entry ) );
    }

    editor_filter_dropdown_menu.configure( w_disp, point( x, y ), std::move( entries ), dropdown_width );
    editor_filter_dropdown_menu.draw( w_disp );
}'''
cpp = replace_function(cpp, 'void veh_interact::display_editor_controls()', controls,
                       'replace editor controls/dropdown renderer')

cpp = replace_once(
    cpp,
    '''                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;\n                close_editor_context_menu();\n                return true;\n''',
    '''                open_editor_dropdown = open_editor_dropdown == which ? editor_dropdown::none : which;\n                close_editor_context_menu();\n                close_editor_toolbar_dropdown();\n                return true;\n''',
    'filter toggle exclusivity')

old_filter_click = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        int x = 0;\n        int y = 0;\n        int width = 0;\n        int height = 0;\n        editor_dropdown_geometry( open_editor_dropdown, x, y, width, height );\n        if( pos.x >= x && pos.x < x + width && pos.y >= y && pos.y < y + height ) {\n            const int option = pos.y - y - 1;\n            if( option >= 0 && option < height - 2 ) {\n                if( open_editor_dropdown == editor_dropdown::system ) {\n                    active_system_filter = static_cast<editor_system_filter>( option );\n                    if( install_info ) {\n                        install_info->dirty = true;\n                    }\n                } else {\n                    active_condition_filter = static_cast<editor_condition_filter>( option );\n                }\n                open_editor_dropdown = editor_dropdown::none;\n                reset_part_selection();\n            }\n            return true;\n        }\n        // Clicking outside the dropdown dismisses it, but do not consume the\n        // click here.  The normal mouse router still needs the same click so a\n        // schematic tile can be selected immediately instead of requiring a\n        // second click.\n        open_editor_dropdown = editor_dropdown::none;\n        return false;\n    }\n'''
new_filter_click = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        if( const std::optional<int> option = editor_filter_dropdown_menu.hit_test( pos ) ) {\n            if( open_editor_dropdown == editor_dropdown::system ) {\n                active_system_filter = static_cast<editor_system_filter>( *option );\n                if( install_info ) {\n                    install_info->dirty = true;\n                }\n            } else {\n                active_condition_filter = static_cast<editor_condition_filter>( *option );\n            }\n            open_editor_dropdown = editor_dropdown::none;\n            editor_filter_dropdown_menu.close();\n            reset_part_selection();\n            return true;\n        }\n        if( editor_filter_dropdown_menu.contains( pos ) ) {\n            return true;\n        }\n        // Outside clicks dismiss with click-through semantics.\n        open_editor_dropdown = editor_dropdown::none;\n        editor_filter_dropdown_menu.close();\n        return false;\n    }\n'''
cpp = replace_once(cpp, old_filter_click, new_filter_click, 'filter helper hit testing')

cpp = replace_once(
    cpp,
    '''    editor_context_buttons.clear();\n    editor_context_width = 0;\n    editor_context_height = 0;\n}\n\nvoid veh_interact::open_editor_context_menu''',
    '''    editor_context_buttons.clear();\n    editor_context_width = 0;\n    editor_context_height = 0;\n    editor_context_dropdown_menu.close();\n}\n\nvoid veh_interact::open_editor_context_menu''',
    'close context helper')

context_hover = r'''void veh_interact::update_editor_context_hover( map &here )
{
    if( !editor_context_open ) {
        return;
    }

    editor_context_dropdown_menu.update_hover( editor_mouse_pos );
    const int hovered_index = editor_context_dropdown_menu.hovered_index();
    const editor_context_button *hovered = hovered_index >= 0 &&
                                           hovered_index < static_cast<int>( editor_context_buttons.size() ) ?
                                           &editor_context_buttons[hovered_index] : nullptr;

    const std::string new_action = hovered != nullptr ? hovered->action : std::string();
    if( new_action == editor_context_hover_action ) {
        return;
    }

    const bool had_preview = !editor_context_hover_action.empty();
    editor_context_hover_action = new_action;
    w_msg_scroll_offset = 0;

    if( hovered == nullptr || ( hovered->action != "EDITOR_REMOVE" &&
                                hovered->action != "EDITOR_REPAIR" ) ) {
        if( had_preview ) {
            msg.reset();
        }
        return;
    }

    if( selected_part < 0 || selected_part >= veh->part_count() ) {
        msg = _( "No part selected." );
        return;
    }
    vehicle_part &part = veh->part( selected_part );
    if( part.removed || part.mount != selected_mount() ) {
        msg = _( "No part selected." );
        return;
    }

    if( hovered->action == "EDITOR_REPAIR" ) {
        set_editor_repair_requirements( here, part );
        return;
    }

    const vehicle_part *old_sel_vehicle_part = sel_vehicle_part;
    const vpart_info *old_sel_vpart_info = sel_vpart_info;
    can_remove_part( here, selected_part, get_avatar() );
    sel_vehicle_part = old_sel_vehicle_part;
    sel_vpart_info = old_sel_vpart_info;
}'''
cpp = replace_function(cpp, 'void veh_interact::update_editor_context_hover( map &here )', context_hover,
                       'context hover helper')

context_click = r'''bool veh_interact::handle_editor_context_click( map &here, const point &pos )
{
    if( !editor_context_open ) {
        return false;
    }
    if( const std::optional<int> hit = editor_context_dropdown_menu.hit_test( pos ) ) {
        if( *hit >= 0 && *hit < static_cast<int>( editor_context_buttons.size() ) ) {
            const editor_context_button &button = editor_context_buttons[*hit];
            if( !button.enabled ) {
                msg = button.disabled_reason.empty() ? _( "That action is not available." ) : button.disabled_reason;
                return true;
            }
            return run_editor_context_action( here, button.action );
        }
    }
    close_editor_context_menu();
    return true;
}'''
cpp = replace_function(cpp, 'bool veh_interact::handle_editor_context_click( map &here, const point &pos )',
                       context_click, 'context click helper')

context_display = r'''void veh_interact::display_editor_context_menu()
{
    if( !editor_context_open || editor_context_target == editor_context_surface::none ||
        editor_context_width <= 0 || editor_context_height < 3 ) {
        editor_context_dropdown_menu.close();
        return;
    }

    catacurses::window &target = editor_context_target == editor_context_surface::parts ? w_parts : w_disp;
    std::vector<ui_dropdown_entry> entries;
    entries.reserve( editor_context_buttons.size() );
    for( const editor_context_button &button : editor_context_buttons ) {
        entries.push_back( { button.label, button.action, button.enabled, false, button.disabled_reason } );
    }

    ui_dropdown_style style;
    style.border = c_light_gray; // keep the existing right-click visual language
    style.text = c_light_green;
    editor_context_dropdown_menu.configure( target, editor_context_pos, std::move( entries ),
                                            editor_context_width, style );
    editor_context_dropdown_menu.update_hover( editor_mouse_pos );
    editor_context_dropdown_menu.draw( target );
}'''
cpp = replace_function(cpp, 'void veh_interact::display_editor_context_menu()', context_display,
                       'context display helper')

toolbar_open = r'''void veh_interact::open_editor_toolbar_menu( const map &here, const std::string &which )
{
    struct toolbar_menu_entry {
        std::string label;
        std::string action;
    };
    std::vector<toolbar_menu_entry> entries;

    const auto has_direct = [&]( const std::string &action ) {
        return std::any_of( editor_toolbar_buttons.begin(), editor_toolbar_buttons.end(),
        [&]( const editor_toolbar_button &button ) {
            return !button.action.starts_with( "TOOLBAR_MENU_" ) && button.action == action;
        } );
    };
    const auto add = [&]( const std::string &label, const std::string &action ) {
        entries.push_back( { label, action } );
    };

    if( which == "TOOLBAR_MENU_MODIFY" ) {
        add( _( "Mend faults…" ), "MEND" );
        add( _( "Change shape…" ), "CHANGE_SHAPE" );
        add( _( "Relabel…" ), "RELABEL" );
    } else if( which == "TOOLBAR_MENU_MORE" ) {
        if( !has_direct( "ASSIGN_CREW" ) ) {
            add( _( "Crew…" ), "ASSIGN_CREW" );
        }
        if( !has_direct( "RENAME" ) ) {
            add( _( "Rename vehicle…" ), "RENAME" );
        }
        add( _( "Siphon liquid…" ), "SIPHON" );
        add( _( "Unload fuel…" ), "UNLOAD" );
    } else if( which == "TOOLBAR_MENU_ACTIONS" ) {
        if( !has_direct( "INSTALL" ) ) {
            add( _( "Install…" ), "INSTALL" );
        }
        if( !has_direct( "REPAIR" ) ) {
            add( _( "Repair…" ), "REPAIR" );
        }
        if( !has_direct( "REMOVE" ) ) {
            add( _( "Remove…" ), "REMOVE" );
        }
        if( !has_direct( "REFILL" ) ) {
            add( _( "Refuel…" ), "REFILL" );
        }
        add( _( "Mend faults…" ), "MEND" );
        add( _( "Change shape…" ), "CHANGE_SHAPE" );
        add( _( "Relabel…" ), "RELABEL" );
        add( _( "Crew…" ), "ASSIGN_CREW" );
        add( _( "Rename vehicle…" ), "RENAME" );
        add( _( "Siphon liquid…" ), "SIPHON" );
        add( _( "Unload fuel…" ), "UNLOAD" );
    } else {
        return;
    }

    if( entries.empty() ) {
        return;
    }
    if( open_editor_toolbar_dropdown == which ) {
        close_editor_toolbar_dropdown();
        return;
    }

    close_editor_context_menu();
    open_editor_dropdown = editor_dropdown::none;
    editor_filter_dropdown_menu.close();
    open_editor_toolbar_dropdown = which;
    editor_toolbar_dropdown_buttons.clear();

    int widest = 0;
    for( const toolbar_menu_entry &entry : entries ) {
        widest = std::max( widest, utf8_width( entry.label ) );
        editor_toolbar_dropdown_buttons.push_back( {
            entry.label, point::zero, 0, entry.action, std::string(),
            editor_toolbar_action_enabled( here, entry.action )
        } );
    }
    editor_toolbar_dropdown_width = std::clamp( widest + 4, 14,
                                    std::max( 14, getmaxx( w_border ) - 2 ) );
    editor_toolbar_dropdown_height = static_cast<int>( editor_toolbar_dropdown_buttons.size() ) + 2;

    int anchor_x = 1;
    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {
        if( button.action == which ) {
            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );
            break;
        }
    }
    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );
    const int x = std::clamp( anchor_x, 1, max_x );
    const int desired_y = getbegy( w_disp ) - getbegy( w_border );
    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );
    const int y = std::clamp( desired_y, 1, max_y );
    editor_toolbar_dropdown_pos = point( x, y );
}'''
cpp = replace_function(cpp, 'void veh_interact::open_editor_toolbar_menu( const map &here, const std::string &which )',
                       toolbar_open, 'toolbar open helper')

toolbar_close = r'''void veh_interact::close_editor_toolbar_dropdown()
{
    open_editor_toolbar_dropdown.clear();
    editor_toolbar_dropdown_buttons.clear();
    editor_toolbar_dropdown_width = 0;
    editor_toolbar_dropdown_height = 0;
    editor_toolbar_dropdown_pos = point::zero;
    editor_toolbar_dropdown_menu.close();
}'''
cpp = replace_function(cpp, 'void veh_interact::close_editor_toolbar_dropdown()', toolbar_close,
                       'toolbar close helper')

toolbar_mouse = r'''bool veh_interact::handle_editor_toolbar_dropdown_mouse( const std::string &action )
{
    if( open_editor_toolbar_dropdown.empty() || !editor_toolbar_dropdown_menu.is_open() ) {
        return false;
    }
    const std::optional<point> pos = main_context.get_coordinates_text( w_border );
    if( !pos ) {
        return false;
    }

    editor_toolbar_dropdown_menu.update_hover( pos );
    const bool inside = editor_toolbar_dropdown_menu.contains( *pos );
    if( action == "MOUSE_MOVE" ) {
        return inside;
    }
    if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
        return true;
    }
    if( action == "SEC_SELECT" ) {
        close_editor_toolbar_dropdown();
        return false;
    }
    if( action != "SELECT" ) {
        return false;
    }

    if( const std::optional<int> hit = editor_toolbar_dropdown_menu.hit_test( *pos ) ) {
        if( *hit >= 0 && *hit < static_cast<int>( editor_toolbar_dropdown_buttons.size() ) ) {
            const editor_context_button &button = editor_toolbar_dropdown_buttons[*hit];
            if( !button.enabled ) {
                msg = _( "That action is not available for the current selection." );
                return true;
            }
            pending_editor_action = button.action;
            close_editor_toolbar_dropdown();
            return false;
        }
    }
    if( inside ) {
        return true;
    }

    close_editor_toolbar_dropdown();
    return false;
}'''
cpp = replace_function(cpp, 'bool veh_interact::handle_editor_toolbar_dropdown_mouse( const std::string &action )',
                       toolbar_mouse, 'toolbar mouse helper')

toolbar_display = r'''void veh_interact::display_editor_toolbar_dropdown()
{
    if( open_editor_toolbar_dropdown.empty() || editor_toolbar_dropdown_buttons.empty() ) {
        editor_toolbar_dropdown_menu.close();
        return;
    }

    int anchor_x = editor_toolbar_dropdown_pos.x;
    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {
        if( button.action == open_editor_toolbar_dropdown ) {
            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );
            break;
        }
    }
    const int max_x = std::max( 1, getmaxx( w_border ) - editor_toolbar_dropdown_width - 1 );
    editor_toolbar_dropdown_pos.x = std::clamp( anchor_x, 1, max_x );
    const int desired_y = getbegy( w_disp ) - getbegy( w_border );
    const int max_y = std::max( 1, getmaxy( w_border ) - editor_toolbar_dropdown_height - 1 );
    editor_toolbar_dropdown_pos.y = std::clamp( desired_y, 1, max_y );

    std::vector<ui_dropdown_entry> entries;
    entries.reserve( editor_toolbar_dropdown_buttons.size() );
    for( const editor_context_button &button : editor_toolbar_dropdown_buttons ) {
        entries.push_back( { button.label, button.action, button.enabled, false, button.disabled_reason } );
    }
    editor_toolbar_dropdown_menu.configure( w_border, editor_toolbar_dropdown_pos, std::move( entries ),
                                            editor_toolbar_dropdown_width );
    editor_toolbar_dropdown_menu.draw( w_border );
}'''
cpp = replace_function(cpp, 'void veh_interact::display_editor_toolbar_dropdown()', toolbar_display,
                       'toolbar display helper')

# Feed filter hover through the shared helper while it is open.
needle = '''    if( !open_editor_toolbar_dropdown.empty() ) {\n        const bool dropdown_handled = handle_editor_toolbar_dropdown_mouse( action );\n        if( !pending_editor_action.empty() ) {\n            return false;\n        }\n        if( dropdown_handled ) {\n            return true;\n        }\n    }\n\n    if( refuel_info ) {\n'''
replacement = '''    if( !open_editor_toolbar_dropdown.empty() ) {\n        const bool dropdown_handled = handle_editor_toolbar_dropdown_mouse( action );\n        if( !pending_editor_action.empty() ) {\n            return false;\n        }\n        if( dropdown_handled ) {\n            return true;\n        }\n    }\n\n    if( open_editor_dropdown != editor_dropdown::none && viewport_pos ) {\n        editor_filter_dropdown_menu.update_hover( viewport_pos );\n        if( action == "MOUSE_MOVE" && editor_filter_dropdown_menu.contains( *viewport_pos ) ) {\n            return true;\n        }\n    }\n\n    if( refuel_info ) {\n'''
cpp = replace_once(cpp, needle, replacement, 'filter hover routing')

# Draw SDL-backed content first, then all tiny overlay dropdowns.  Dedicated windows
# mean this no longer paints a black backing rectangle over Live/Split.
old_order = '''            display_editor_context_menu();\n            // Register/draw the SDL-backed Live/Split preview before refreshing the\n            // toolbar overlay.  The toolbar dropdown is painted into w_border, so\n            // refreshing it last keeps the inline menu above the live renderer\n            // without disabling or resizing the preview camera.\n            display_live_preview( here );\n            display_mode( here );\n'''
new_order = '''            // SDL-backed Live/Split renders first.  Every dropdown/context menu now\n            // owns a tiny ui_dropdown window and can safely overlay it afterwards.\n            display_live_preview( here );\n            display_editor_filter_dropdown();\n            display_editor_context_menu();\n            display_mode( here );\n'''
cpp = replace_once(cpp, old_order, new_order, 'shared dropdown overlay draw order')

# No vehicle dropdown should retain a one-off curses backing window or manual modal uilist.
assert 'w_toolbar_dropdown' not in cpp
assert 'w_toolbar_dropdown' not in h
assert 'ui_dropdown editor_filter_dropdown_menu' in h
assert 'style.border = c_light_gray' in cpp
assert 'display_editor_filter_dropdown();\n            display_editor_context_menu();' in cpp
assert 'if( which == "TOOLBAR_MENU_ACTIONS" ) {\n        uilist menu;' not in cpp

cpp_path.write_text(cpp)
h_path.write_text(h)
print('vehicle dropdowns migrated to shared ui_dropdown helper')
