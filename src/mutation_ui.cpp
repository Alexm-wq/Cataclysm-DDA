#include "character.h" // IWYU pragma: associated

#include <algorithm>
#include <array>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "color.h"
#include "cursesdef.h"
#include "input.h"
#include "input_context.h"
#include "magic.h"
#include "mutation.h"
#include "output.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/key_field.h"
#include "ui_helpers/controls/scroll_view.h"
#include "ui_helpers/controls/selection_list.h"
#include "ui_manager.h"

// '!' and '=' are used as default bindings in the menu.
static const invlet_wrapper
mutation_chars( "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\"#&()*+./:;@[\\]^_{|}" );

namespace
{

struct mutation_inspector_line {
    std::string text;
    nc_color color = c_light_gray;
    bool shortcut = false;
};

class mutations_window
{
    public:
        explicit mutations_window( avatar &player ) : p( player ), ctxt( "MUTATIONS", keyboard_mode::keychar ) {
            ctxt.register_updown();
            for( const char *action : {
                     "ANY_INPUT", "TOGGLE_EXAMINE", "TOGGLE_SPRITE", "REASSIGN", "NEXT_TAB",
                     "PREV_TAB", "CONFIRM", "HELP_KEYBINDINGS", "QUIT", "MOUSE_MOVE", "SELECT",
                     "CLICK_AND_DRAG", "SCROLL_UP", "SCROLL_DOWN", "PAGE_UP", "PAGE_DOWN", "HOME", "END"
                 } ) {
                ctxt.register_action( action );
            }
            for( tab_state &state : tabs ) {
                state.list.hover_previews( false );
            }
            rebuild();
            ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
                resize( adaptor );
            } );
            ui.on_redraw( [&]( const ui_adaptor & ) {
                draw();
            } );
            ui.mark_resize();
        }

        void run();

    private:
        struct tab_state {
            std::vector<trait_id> rows;
            std::optional<trait_id> selected;
            ui_selection_list list;
        };

        avatar &p;
        input_context ctxt;
        std::array<tab_state, 2> tabs;
        int tab = 0;
        ui_adaptor ui;
        catacurses::window window;
        ui_action_strip toolbar;
        ui_action_strip settings;
        ui_action_strip primary;
        ui_key_field shortcut;
        ui_scroll_view inspector;
        std::vector<mutation_inspector_line> lines;
        std::string status;
        bool done = false;
        bool details_focus = false;
        bool single_pane = false;
        bool stacked = false;
        bool show_list = true;
        bool show_inspector = true;
        point list_origin = point::zero;
        point detail_origin = point::zero;
        int list_width = 0;
        int list_height = 0;
        int detail_width = 0;
        int detail_height = 0;
        int divider_y = 0;
        int shortcut_line = -1;

        trait_id selected() const;
        void rebuild();
        void select( const trait_id &id );
        void resize( ui_adaptor &adaptor );
        void configure_toolbar();
        void build_inspector( int width );
        void draw();
        void dispatch( const std::string &action, std::optional<trait_id> id = std::nullopt );
        bool can_activate( const trait_id &id ) const;
        std::string activation_failure( const trait_id &id ) const;
        void activate_or_deactivate( const trait_id &id );
        void assign_shortcut( const trait_id &id, int key );
};

trait_id mutations_window::selected() const
{
    if( tabs[tab].selected ) {
        return *tabs[tab].selected;
    }
    return trait_id();
}

bool mutations_window::can_activate( const trait_id &id ) const
{
    if( id.is_null() || !id->activated ) {
        return false;
    }
    if( p.cached_mutations.at( id ).powered ) {
        return true;
    }
    return ( !id->hunger || p.get_kcal_percent() >= 0.8f ) &&
           ( !id->thirst || p.get_thirst() <= 400 ) &&
           ( !id->sleepiness || p.get_sleepiness() <= 400 ) &&
           ( !id->mana || p.magic->available_mana() >= id->cost );
}

std::string mutations_window::activation_failure( const trait_id &id ) const
{
    if( id.is_null() ) {
        return _( "Select a mutation first." );
    }
    if( !id->activated ) {
        return _( "This mutation is passive." );
    }
    if( p.cached_mutations.at( id ).powered ) {
        return std::string();
    }
    if( id->hunger && p.get_kcal_percent() < 0.8f ) {
        return _( "Not enough stored calories to activate this mutation." );
    }
    if( id->thirst && p.get_thirst() > 400 ) {
        return _( "You are too thirsty to activate this mutation." );
    }
    if( id->sleepiness && p.get_sleepiness() > 400 ) {
        return _( "You are too tired to activate this mutation." );
    }
    if( id->mana && p.magic->available_mana() < id->cost ) {
        return _( "Not enough mana to activate this mutation." );
    }
    return std::string();
}

void mutations_window::rebuild()
{
    std::array<int, 2> old_cursor = { tabs[0].list.cursor(), tabs[1].list.cursor() };
    std::array<int, 2> old_scroll = { tabs[0].list.scroll_model().viewport_pos(),
                                     tabs[1].list.scroll_model().viewport_pos() };
    for( tab_state &state : tabs ) {
        state.rows.clear();
    }

    for( std::pair<const trait_id, Character::trait_data> &mut : p.cached_mutations ) {
        if( mut.second.corrupted > 0 || !mut.first->player_display ) {
            continue;
        }
        if( mut.second.key == ' ' && mut.first->activated ) {
            for( const char letter : mutation_chars ) {
                if( p.trait_by_invlet( letter ).is_null() ) {
                    mut.second.key = letter;
                    break;
                }
            }
        }
        tabs[mut.first->activated ? 0 : 1].rows.push_back( mut.first );
    }

    for( int t = 0; t < 2; ++t ) {
        tab_state &state = tabs[t];
        std::sort( state.rows.begin(), state.rows.end(), [&]( const trait_id & lhs, const trait_id & rhs ) {
            return p.mutation_name( lhs ) < p.mutation_name( rhs );
        } );
        if( state.selected && std::find( state.rows.begin(), state.rows.end(), *state.selected ) == state.rows.end() ) {
            state.selected.reset();
        }
        if( !state.selected && !state.rows.empty() ) {
            state.selected = state.rows[std::clamp( old_cursor[t], 0,
                static_cast<int>( state.rows.size() ) - 1 )];
        }

        std::vector<ui_action_entry> entries;
        std::vector<std::vector<ui_row_accessory>> accessories;
        for( const trait_id &id : state.rows ) {
            const Character::trait_data &data = p.cached_mutations.at( id );
            std::string label;
            if( id->activated ) {
                label = string_format( "%c  %s", data.key == ' ' ? '-' : data.key, p.mutation_name( id ) );
                if( data.powered ) {
                    label += _( "  · Active" );
                }
            } else {
                label = p.mutation_name( id );
            }
            entries.emplace_back( label, id.str() );
            std::vector<ui_row_accessory> row;
            row.push_back( { ui_action_entry( _( "Sprite" ), "SPRITE:" + id.str(), true,
                                              false, std::string(), data.show_sprite ) } );
            accessories.push_back( std::move( row ) );
        }
        state.list.set_entries( std::move( entries ), false );
        state.list.set_row_accessories( std::move( accessories ) );
        if( state.selected ) {
            const auto it = std::find( state.rows.begin(), state.rows.end(), *state.selected );
            state.list.select_only( static_cast<int>( it - state.rows.begin() ) );
        } else {
            state.list.clear_selection();
        }
        state.list.scroll_model().set_viewport_pos( old_scroll[t] );
    }

    if( tabs[tab].rows.empty() && !tabs[1 - tab].rows.empty() ) {
        tab = 1 - tab;
    }
}

void mutations_window::select( const trait_id &id )
{
    tab_state &state = tabs[tab];
    const auto it = std::find( state.rows.begin(), state.rows.end(), id );
    if( it == state.rows.end() ) {
        return;
    }
    if( state.selected != id ) {
        shortcut.cancel();
        inspector.model().scroll_to_start();
        status.clear();
    }
    state.selected = id;
    state.list.select_only( static_cast<int>( it - state.rows.begin() ) );
}

void mutations_window::configure_toolbar()
{
    std::vector<ui_action_strip_item> actions = {
        { ui_action_entry( string_format( _( "Active (%d)" ), tabs[0].rows.size() ),
                           "ACTIVE_TAB", true, tab == 0 ) },
        { ui_action_entry( string_format( _( "Passive (%d)" ), tabs[1].rows.size() ),
                           "PASSIVE_TAB", true, tab == 1 ) },
        { ui_action_entry( single_pane && details_focus ? _( "Back to list" ) : _( "Back" ),
                           "BACK" ), 2, ui_action_alignment::right }
    };
    toolbar.configure( window, point( 1, 1 ), std::move( actions ), getmaxx( window ) - 2,
                       std::min( 3, std::max( 1, getmaxy( window ) - 6 ) ) );
}

void mutations_window::resize( ui_adaptor &adaptor )
{
    for( tab_state &state : tabs ) {
        state.list.invalidate_geometry();
    }
    shortcut.cancel();
    shortcut.hide();
    inspector.hide();
    toolbar.clear();
    settings.clear();
    primary.clear();

    int names = 24;
    for( const tab_state &state : tabs ) {
        for( const trait_id &id : state.rows ) {
            names = std::max( names, utf8_width( p.mutation_name( id ) ) );
        }
    }
    const int preferred_list = std::clamp( names + 18, 52, 62 );
    const int preferred_detail = 52;
    const int width = std::min( TERMX, preferred_list + preferred_detail + 3 );
    const int height = std::min( TERMY, 28 );
    window = catacurses::newwin( height, width, point( ( TERMX - width ) / 2, ( TERMY - height ) / 2 ) );
    configure_toolbar();

    divider_y = 2 + toolbar.rows_used();
    const int top = divider_y + 1;
    const int body_height = std::max( 0, height - top - 2 );
    stacked = width < 104 && body_height >= 13;
    single_pane = width < 104 && !stacked;
    show_list = !single_pane || !details_focus;
    show_inspector = !single_pane || details_focus;

    list_origin = point( 1, top + 1 );
    detail_origin = point( 1, top );
    list_width = width - 2;
    list_height = body_height - 1;
    detail_width = width - 2;
    detail_height = body_height - 1;

    if( !single_pane && !stacked ) {
        const int pane_width = width - 3;
        list_width = std::min( preferred_list, std::max( 1, pane_width - 48 ) );
        detail_origin = point( list_width + 2, top );
        detail_width = width - detail_origin.x - 1;
    } else if( stacked ) {
        list_height = std::clamp( static_cast<int>( tabs[tab].rows.size() ), 3,
                                  std::max( 3, body_height / 3 ) );
        detail_origin = point( 1, top + list_height + 1 );
        detail_height = body_height - list_height - 1;
    }
    detail_height = std::max( 0, detail_height - 1 );
    adaptor.position_from_window( window );
}

void mutations_window::build_inspector( int width )
{
    lines.clear();
    shortcut_line = -1;
    const auto add = [&]( const std::string &text, nc_color color = c_light_gray ) {
        const std::vector<std::string> folded = foldstring( text, std::max( 1, width ) );
        if( folded.empty() ) {
            lines.push_back( { "", color, false } );
        } else {
            for( const std::string &line : folded ) {
                lines.push_back( { line, color, false } );
            }
        }
    };

    const trait_id id = selected();
    if( id.is_null() ) {
        add( _( "Select a mutation to see its details." ) );
        return;
    }
    const Character::trait_data &data = p.cached_mutations.at( id );
    add( p.mutation_name( id ), c_white );
    if( id->activated ) {
        add( data.powered ? _( "ACTIVE" ) : _( "INACTIVE" ), data.powered ? c_light_green : c_light_cyan );
        const std::string failure = activation_failure( id );
        if( !failure.empty() ) {
            add( failure, c_light_red );
        }
    } else {
        add( _( "PASSIVE" ), c_light_cyan );
    }

    add( "" );
    if( id->activated ) {
        add( _( "Activation" ), c_light_cyan );
        std::vector<std::string> resources;
        if( id->hunger ) {
            resources.emplace_back( _( "calories" ) );
        }
        if( id->thirst ) {
            resources.emplace_back( _( "thirst" ) );
        }
        if( id->sleepiness ) {
            resources.emplace_back( _( "sleepiness" ) );
        }
        if( id->mana ) {
            resources.emplace_back( _( "mana" ) );
        }
        if( id->cost > 0 && !resources.empty() ) {
            add( string_format( _( "Cost: %d %s" ), id->cost,
                                enumerate_as_string( resources, enumeration_conjunction::none ) ) );
        } else if( id->cost > 0 ) {
            add( string_format( _( "Cost: %d" ), id->cost ) );
        } else {
            add( _( "No activation cost." ) );
        }
        if( id->cooldown > 0_turns ) {
            add( string_format( _( "Cooldown: %s" ), to_string_clipped( id->cooldown ) ) );
        }
        add( "" );
    }

    add( p.mutation_desc( id ), c_light_blue );
    if( !p.purifiable( id ) ) {
        add( "" );
        add( _( "This trait is intrinsic and cannot be removed by purifier." ), c_yellow );
    }
    add( "" );
    add( _( "Settings" ), c_light_cyan );
    shortcut_line = static_cast<int>( lines.size() );
    lines.push_back( { "", c_light_gray, true } );
    lines.push_back( { "", c_light_gray, false } );
}

void mutations_window::draw()
{
    if( !window ) {
        return;
    }
    werase( window );
    draw_border( window, BORDER_COLOR, _( " Mutations " ) );
    configure_toolbar();
    toolbar.draw( window );
    mvwhline( window, point( 1, divider_y ), LINE_OXOX, getmaxx( window ) - 2 );

    if( !single_pane && !stacked ) {
        mvwvline( window, point( detail_origin.x - 1, list_origin.y - 1 ), LINE_XOXO, list_height + 1 );
    } else if( stacked ) {
        mvwhline( window, point( 1, detail_origin.y - 1 ), LINE_OXOX, getmaxx( window ) - 2 );
    }

    settings.begin_layout();
    if( show_list ) {
        if( single_pane ) {
            primary.configure( window, list_origin - point( 0, 1 ),
            { ui_action_entry( _( "Details" ), "DETAILS", !selected().is_null() ) }, list_width );
            primary.draw( window );
        } else {
            trim_and_print( window, list_origin - point( 0, 1 ), list_width - 1, c_light_cyan,
                            tab == 0 ? _( "Shortcut / Mutation / State / Sprite" ) : _( "Mutation / Sprite" ) );
        }
        tabs[tab].list.draw( window, list_origin, list_width, list_height );
        if( tabs[tab].rows.empty() ) {
            trim_and_print( window, list_origin, list_width - 1, c_light_gray,
                            tab == 0 ? _( "No activatable mutations." ) : _( "No passive mutations." ) );
        }
    }

    if( show_inspector ) {
        build_inspector( detail_width - 1 );
        inspector.configure( detail_origin, detail_width, detail_height, static_cast<int>( lines.size() ) );
        for( int i = 0; i < static_cast<int>( lines.size() ); ++i ) {
            const std::optional<point> pos = inspector.position( i );
            if( !pos ) {
                continue;
            }
            if( lines[i].shortcut ) {
                const trait_id id = selected();
                if( !id.is_null() ) {
                    const char key = p.cached_mutations.at( id ).key;
                    shortcut.configure( window, *pos, detail_width - 1, _( "Shortcut" ),
                                        key == ' ' ? _( "None" ) : std::string( 1, key ), _( "Press a key…" ) );
                    shortcut.draw( window );
                }
            } else {
                trim_and_print( window, *pos, detail_width - 1, lines[i].color, lines[i].text );
            }
        }
        if( shortcut_line < 0 || !inspector.position( shortcut_line ) ) {
            shortcut.hide();
        }

        const trait_id id = selected();
        if( !id.is_null() ) {
            if( const std::optional<point> pos = inspector.position( shortcut_line + 1 ) ) {
                settings.add_row( window, *pos,
                                  ui_action_entry( p.cached_mutations.at( id ).show_sprite ?
                                                   _( "Sprite: Shown" ) : _( "Sprite: Hidden" ),
                                                   "SPRITE", true, false, std::string(),
                                                   p.cached_mutations.at( id ).show_sprite ), detail_width - 1 );
            }
            settings.draw( window );
        }
        inspector.draw_scrollbar( window );

        std::vector<ui_action_strip_item> actions;
        if( !id.is_null() && id->activated ) {
            const bool powered = p.cached_mutations.at( id ).powered;
            actions.push_back( { ui_action_entry( powered ? _( "Deactivate" ) : _( "Activate" ),
                                                  "POWER", can_activate( id ), powered,
                                                  activation_failure( id ) ) } );
        }
        primary.configure( window, detail_origin + point( 0, detail_height ),
                           std::move( actions ), detail_width - 1 );
        primary.draw( window );
    } else {
        shortcut.hide();
    }

    const std::string hint = !status.empty() ? status : shortcut.armed() ?
                             _( "Press a shortcut; Space clears, Esc cancels." ) : details_focus ?
                             string_format( _( "Details: arrows / wheel scroll.  %s returns to list." ),
                                            ctxt.get_desc( "TOGGLE_EXAMINE" ) ) :
                             string_format( _( "Select a mutation to inspect it.  %s activates.  %s focuses details." ),
                                            ctxt.get_desc( "CONFIRM" ), ctxt.get_desc( "TOGGLE_EXAMINE" ) );
    trim_and_print( window, point( 1, getmaxy( window ) - 2 ), getmaxx( window ) - 2,
                    shortcut.armed() ? c_yellow : c_light_gray, hint );
    wnoutrefresh( window );
}

void mutations_window::assign_shortcut( const trait_id &id, int key )
{
    if( id.is_null() ) {
        return;
    }
    if( key == ' ' ) {
        p.cached_mutations[id].key = ' ';
        return;
    }
    const trait_id other = p.trait_by_invlet( key );
    if( !other.is_null() && other != id ) {
        std::swap( p.cached_mutations[id].key, p.cached_mutations[other].key );
    } else {
        p.cached_mutations[id].key = key;
    }
}

void mutations_window::activate_or_deactivate( const trait_id &id )
{
    if( id.is_null() || !id->activated ) {
        status = activation_failure( id );
        return;
    }
    Character::trait_data &data = p.cached_mutations[id];
    if( data.powered ) {
        p.add_msg_if_player( m_neutral, _( "You stop using your %s." ), p.mutation_name( id ) );
        ui.reset();
        p.deactivate_mutation( id );
        done = true;
        return;
    }
    if( !can_activate( id ) ) {
        status = activation_failure( id );
        return;
    }
    p.add_msg_if_player( m_neutral, string_format( id->activation_msg, p.mutation_name( id ) ) );
    ui.reset();
    p.activate_mutation( id );
    done = true;
}

void mutations_window::dispatch( const std::string &action, std::optional<trait_id> id )
{
    if( action == "BACK" ) {
        if( single_pane && details_focus ) {
            details_focus = false;
            shortcut.cancel();
            ui.mark_resize();
        } else {
            done = true;
        }
        return;
    }
    if( action == "ACTIVE_TAB" || action == "PASSIVE_TAB" ) {
        const int next = action == "ACTIVE_TAB" ? 0 : 1;
        if( next != tab ) {
            tab = next;
            details_focus = false;
            shortcut.cancel();
            inspector.model().scroll_to_start();
            status.clear();
            ui.mark_resize();
        }
        return;
    }
    if( action == "LIST" || action == "DETAILS" ) {
        details_focus = action == "DETAILS";
        shortcut.cancel();
        if( single_pane ) {
            ui.mark_resize();
        }
        return;
    }
    if( !id ) {
        id = selected();
    }
    if( !id || id->is_null() ) {
        status = _( "Select a mutation first." );
        return;
    }
    if( action == "SELECT_MUTATION" ) {
        select( *id );
        details_focus = false;
    } else if( action == "POWER" ) {
        activate_or_deactivate( *id );
    } else if( action == "SPRITE" ) {
        p.cached_mutations[*id].show_sprite = !p.cached_mutations[*id].show_sprite;
        rebuild();
    } else if( action == "SHORTCUT" ) {
        if( single_pane && !details_focus ) {
            details_focus = true;
            ui.mark_resize();
            ui_manager::redraw();
        }
        build_inspector( detail_width - 1 );
        inspector.model().ensure_visible( shortcut_line );
        ui.invalidate_ui();
        ui_manager::redraw_invalidated();
        shortcut.arm();
        status.clear();
    }
}

void mutations_window::run()
{
    while( !done ) {
        ui_manager::redraw();
        if( shortcut.armed() ) {
            const ui_key_field_result result = shortcut.read( [&]( int key ) {
                return mutation_chars.valid( key );
            } );
            if( result.type == ui_key_field_result_type::assigned ||
                result.type == ui_key_field_result_type::cleared ) {
                assign_shortcut( selected(), result.type == ui_key_field_result_type::cleared ? ' ' : result.key );
                rebuild();
                status.clear();
            } else if( result.type == ui_key_field_result_type::invalid ) {
                status = _( "Invalid shortcut.  Use a mutation letter, Space to clear, or Esc to cancel." );
            } else if( result.type == ui_key_field_result_type::cancelled ) {
                status.clear();
            }
            continue;
        }

        const std::string action = ctxt.handle_input();
        const std::optional<point> pos = ctxt.get_coordinates_text( window );

        if( show_list && tabs[tab].list.has_capture() &&
            tabs[tab].list.handle_input( action, ctxt, pos ).consumed() ) {
            continue;
        }
        if( show_inspector && inspector.has_capture() && inspector.handle_input( action, ctxt, pos ) ) {
            continue;
        }

        const auto route = [&]( const ui_action_result &result ) {
            if( result.type == ui_action_result_type::disabled && result.entry ) {
                status = result.entry->disabled_reason;
            } else if( result.type == ui_action_result_type::activated && result.entry ) {
                const std::string &id = result.entry->id;
                if( id.rfind( "SPRITE:", 0 ) == 0 ) {
                    dispatch( "SPRITE", trait_id( id.substr( 7 ) ) );
                } else {
                    dispatch( id );
                }
            }
            return result.consumed();
        };

        if( action == "MOUSE_MOVE" ) {
            toolbar.handle_pointer_input( action, pos );
            primary.handle_pointer_input( action, pos );
            settings.handle_pointer_input( action, pos );
            shortcut.handle_pointer_input( action, pos );
            if( show_list ) {
                tabs[tab].list.handle_input( action, ctxt, pos );
            }
            if( show_inspector ) {
                inspector.handle_input( action, ctxt, pos );
            }
            continue;
        }

        if( action == "SELECT" && show_inspector && inspector.contains( pos ) ) {
            details_focus = true;
        }
        if( show_inspector && inspector.handle_input( action, ctxt, pos, details_focus ) ) {
            continue;
        }
        if( show_list && action != "CONFIRM" ) {
            ui_selection_list &list = tabs[tab].list;
            const ui_action_result result = list.handle_input( action, ctxt, pos );
            if( result.entry ) {
                const std::string &entry_id = result.entry->id;
                if( entry_id.rfind( "SPRITE:", 0 ) == 0 ) {
                    route( result );
                } else {
                    dispatch( "SELECT_MUTATION", trait_id( entry_id ) );
                }
            } else if( result.consumed() && ( action == "UP" || action == "DOWN" ||
                                              action == "PAGE_UP" || action == "PAGE_DOWN" ||
                                              action == "HOME" || action == "END" ) && !tabs[tab].rows.empty() ) {
                select( tabs[tab].rows[list.cursor()] );
            }
            if( result.consumed() ) {
                continue;
            }
        }

        if( route( toolbar.handle_pointer_input( action, pos ) ) ||
            route( primary.handle_pointer_input( action, pos ) ) ||
            route( settings.handle_pointer_input( action, pos ) ) ) {
            continue;
        }
        if( shortcut.handle_pointer_input( action, pos ).consumed() ) {
            dispatch( "SHORTCUT" );
            continue;
        }

        if( action == "QUIT" ) {
            dispatch( "BACK" );
        } else if( action == "NEXT_TAB" || action == "PREV_TAB" ) {
            dispatch( tab == 0 ? "PASSIVE_TAB" : "ACTIVE_TAB" );
        } else if( action == "TOGGLE_EXAMINE" ) {
            dispatch( details_focus ? "LIST" : "DETAILS" );
        } else if( action == "REASSIGN" ) {
            dispatch( "SHORTCUT" );
        } else if( action == "TOGGLE_SPRITE" ) {
            dispatch( "SPRITE" );
        } else if( action == "CONFIRM" ) {
            dispatch( "POWER" );
        } else if( action == "ANY_INPUT" && ctxt.get_raw_input().type == input_event_t::keyboard_char ) {
            const int key = ctxt.get_raw_input().get_first_input();
            if( key != ' ' ) {
                const trait_id id = p.trait_by_invlet( key );
                if( !id.is_null() ) {
                    const int target_tab = id->activated ? 0 : 1;
                    if( target_tab != tab ) {
                        dispatch( target_tab == 0 ? "ACTIVE_TAB" : "PASSIVE_TAB" );
                    }
                    select( id );
                    if( id->activated ) {
                        dispatch( "POWER", id );
                    }
                }
            }
        }
    }
}

} // namespace

void avatar::power_mutations()
{
    extern void show_character_hub_mutations( Character & );
    show_character_hub_mutations( *this );
}
