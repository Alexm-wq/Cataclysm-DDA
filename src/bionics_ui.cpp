#include <algorithm>
#include <array>
#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "bionics.h"
#include "bionics_ui_model.h"
#include "bodypart.h"
#include "calendar.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "character.h"
#include "color.h"
#include "cursesdef.h"
#include "game.h"
#include "input.h"
#include "input_context.h"
#include "item.h"
#include "item_location.h"
#include "map.h"
#include "options.h"
#include "output.h"
#include "pimpl.h"
#include "point.h"
#include "ret_val.h"
#include "string_formatter.h"
#include "translations.h"
#include "type_id.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/dropdown.h"
#include "ui_helpers/controls/key_field.h"
#include "ui_helpers/controls/scroll_view.h"
#include "ui_helpers/controls/selection_list.h"
#include "ui_manager.h"
#include "uilist.h"
#include "uistate.h"
#include "units.h"
#include "vehicle.h"

static const itype_id itype_battery( "battery" );
static const json_character_flag json_flag_BIONIC_FAULTY( "BIONIC_FAULTY" );
static const json_character_flag json_flag_BIONIC_GUN( "BIONIC_GUN" );
static const std::string bionic_ui_test_tag = "UI_TEST_FIXTURE";

namespace io
{
template<>
std::string enum_to_string<bionic_ui_sort_mode>( bionic_ui_sort_mode mode )
{
    switch( mode ) {
        case bionic_ui_sort_mode::nsort:
        case bionic_ui_sort_mode::NONE:
            return "none";
        case bionic_ui_sort_mode::POWER:
            return "power";
        case bionic_ui_sort_mode::NAME:
            return "name";
        case bionic_ui_sort_mode::INVLET:
            return "invlet";
    }
    return "error";
}
} // namespace io

bionic *avatar::bionic_by_invlet( const int ch )
{
    if( ch != ' ' ) {
        for( bionic &bio : *my_bionics ) {
            if( bio.invlet == ch ) {
                return &bio;
            }
        }
    }
    return nullptr;
}

char get_free_invlet( Character &p )
{
    if( !p.is_npc() ) {
        for( const char key : bionics_ui::shortcut_characters ) {
            if( p.as_avatar()->bionic_by_invlet( key ) == nullptr ) {
                return key;
            }
        }
    }
    return ' ';
}

namespace
{
using bio_uid = bionic::bionic_uid;

std::string sort_label( bionic_ui_sort_mode mode )
{
    switch( mode ) {
        case bionic_ui_sort_mode::POWER:
            return _( "Power usage" );
        case bionic_ui_sort_mode::NAME:
            return _( "Name" );
        case bionic_ui_sort_mode::INVLET:
            return _( "Manual (shortcut)" );
        default:
            return _( "Installation order" );
    }
}

std::string fuel_label( float threshold )
{
    return threshold < 0 ? _( "Disabled" ) :
           string_format( _( "%d %%" ), static_cast<int>( threshold * 100 + 0.5f ) );
}

std::string row_power( const bionic &bio )
{
    const bionic_data &data = bio.info();
    if( data.has_flag( json_flag_BIONIC_GUN ) && bio.has_weapon() ) {
        return units::display( bio.get_weapon().get_gun_bionic_drain() );
    }
    if( data.power_over_time > 0_J && data.charge_time > 0_turns ) {
        return data.charge_time == 1_turns ?
               string_format( _( "%s/turn" ), units::display( data.power_over_time ) ) :
               string_format( _( "%s/%d turns" ), units::display( data.power_over_time ),
                              to_turns<int>( data.charge_time ) );
    }
    return data.power_activate > 0_J ? units::display( data.power_activate ) : std::string();
}

struct inspector_line {
    std::string text;
    nc_color color = c_light_gray;
    std::string control;
};

/** Layout and CBM semantics live here; controls own all pointer geometry,
 * selection, capture, scrolling and overlay behavior. No borrowed bionic
 * pointer survives a gameplay handoff or a list rebuild. */
class bionics_window
{
    public:
        explicit bionics_window( avatar &player ) : p( player ), ctxt( "BIONICS", keyboard_mode::keychar ) {
            ctxt.register_updown();
            for( const char *action : {
                     "ANY_INPUT", "TOGGLE_EXAMINE", "REASSIGN", "NEXT_TAB",
                     "PREV_TAB", "CONFIRM", "QUIT", "HELP_KEYBINDINGS", "TOGGLE_SAFE_FUEL",
                     "TOGGLE_SPRITE", "SORT", "BIONICS_WEAPON", "MOUSE_MOVE", "SELECT",
                     "SEC_SELECT", "CLICK_AND_DRAG", "SCROLL_UP", "SCROLL_DOWN", "PAGE_UP",
                     "PAGE_DOWN", "HOME", "END"
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
            std::vector<bio_uid> rows;
            std::optional<bio_uid> selected;
            ui_selection_list list;
        };
        avatar &p;
        input_context ctxt;
        std::array<tab_state, 2> tabs;
        int tab = 0;
        ui_adaptor ui;
        catacurses::window window;
        ui_action_strip toolbar;
        ui_action_strip primary;
        ui_action_strip settings;
        ui_key_field shortcut;
        ui_scroll_view inspector;
        ui_dropdown dropdown;
        std::string dropdown_kind;
        std::optional<inclusive_rectangle<point>> dropdown_trigger;
        std::optional<bio_uid> dropdown_bionic;
        std::vector<inspector_line> lines;
        std::map<std::string, std::pair<std::string, bio_uid>> row_actions;
        std::string status;
        bool hidden = false;
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
        int status_y = 0;
        int divider_y = 0;
        int shortcut_line = 0;
        int fuel_line = 0;

        bionic *find( bio_uid uid ) {
            return p.find_bionic_by_uid( uid ).value_or( nullptr );
        }
        bionic *selected() {
            return tabs[tab].selected ? find( *tabs[tab].selected ) : nullptr;
        }
        void close_transients() {
            dropdown.close();
            dropdown_kind.clear();
            dropdown_trigger.reset();
            dropdown_bionic.reset();
            shortcut.cancel();
        }
        void rebuild();
        void select( bio_uid uid );
        void resize( ui_adaptor &adaptor );
        void configure_toolbar();
        void build_inspector( int width );
        void draw();
        std::string global_status();
        ui_action_entry power_action( bionic &bio, bool compact = false );
        void open_dropdown( const std::string &kind );
        void apply_test_fixture( const std::string &fixture );
        void dispatch( const std::string &action, std::optional<bio_uid> uid = std::nullopt );
        void handoff( bio_uid uid, bool weapon_management );
};

ui_action_entry bionics_window::power_action( bionic &bio, bool compact )
{
    if( !bio.info().activated ) {
        return ui_action_entry( _( "Passive" ), "POWER", false, false,
                                _( "This is a passive bionic." ) );
    }
    const bool install = !bio.powered && bio.can_install_weapon() && !bio.has_weapon();
    const std::string label = install ? _( "Install weapon" ) :
                              compact ? ( bio.powered ? _( "On" ) : _( "Off" ) ) :
                              bio.powered ? _( "Deactivate" ) : _( "Activate" );
    // Installing a weapon does not activate the CBM and must remain possible
    // without power, just as in the old CBM-owned weapon menu.
    const ret_val<void> eligible = install ? ret_val<void>::make_success() : bio.powered ?
                                   p.can_deactivate_bionic( bio ) : p.can_activate_bionic( bio );
    return ui_action_entry( compact && !eligible.success() ? "! " + label : label,
                            "POWER", eligible.success(), bio.powered, eligible.str() );
}

void bionics_window::rebuild()
{
    row_actions.clear();
    for( int t = 0; t < 2; ++t ) {
        tab_state &state = tabs[t];
        const int old_cursor = state.list.cursor();
        const int old_scroll = state.list.scroll_model().viewport_pos();
        state.rows = bionics_ui::sorted_bionics( *p.my_bionics, t == 0, uistate.bionic_sort_mode );
        if( state.selected && std::find( state.rows.begin(), state.rows.end(), *state.selected ) ==
            state.rows.end() ) {
            state.selected = state.rows.empty() ? std::nullopt :
                             std::optional<bio_uid>( state.rows[std::clamp( old_cursor, 0,
                                 static_cast<int>( state.rows.size() ) - 1 )] );
            if( t == tab ) {
                inspector.model().scroll_to_start();
            }
        }
        std::vector<ui_action_entry> entries;
        std::vector<std::vector<ui_row_accessory>> accessories;
        for( const bio_uid uid : state.rows ) {
            bionic &bio = *find( uid );
            const auto action_id = [&]( const std::string & semantic ) {
                const std::string id = semantic + ":" + std::to_string( uid );
                row_actions.emplace( id, std::make_pair( semantic, uid ) );
                return id;
            };
            entries.emplace_back( string_format( "%c %s", bio.invlet, bio.info().name.translated() ),
                                  action_id( "SELECT_BIONIC" ) );
            std::vector<ui_row_accessory> row;
            if( bio.info().activated ) {
                ui_action_entry power = power_action( bio, true );
                power.id = action_id( "POWER" );
                // Installation is explicit in the inspector; keep the row compact.
                if( !bio.has_weapon() && bio.can_install_weapon() ) {
                    power.label = "+";
                }
                row.push_back( { power, ui_row_accessory_side::leading } );
            }
            row.push_back( { ui_action_entry( _( "Sprite" ), action_id( "SPRITE" ), true,
                                              false, std::string(), bio.show_sprite ) } );
            const std::string power = row_power( bio );
            if( !power.empty() ) {
                row.push_back( { ui_action_entry( power, "" ), ui_row_accessory_side::trailing, false, 14 } );
            }
            accessories.push_back( std::move( row ) );
        }
        state.list.set_entries( std::move( entries ), false );
        state.list.set_row_accessories( std::move( accessories ) );
        if( state.selected ) {
            state.list.select_only( static_cast<int>( std::find( state.rows.begin(), state.rows.end(),
                    *state.selected ) - state.rows.begin() ) );
        } else {
            state.list.clear_selection();
        }
        state.list.scroll_model().set_viewport_pos( old_scroll );
    }
}

void bionics_window::select( bio_uid uid )
{
    tab_state &state = tabs[tab];
    const auto it = std::find( state.rows.begin(), state.rows.end(), uid );
    if( it == state.rows.end() ) {
        return;
    }
    if( state.selected != uid ) {
        close_transients();
        inspector.model().scroll_to_start();
        status.clear();
    }
    state.selected = uid;
    state.list.select_only( static_cast<int>( it - state.rows.begin() ) );
}

void bionics_window::configure_toolbar()
{
    std::vector<ui_action_strip_item> actions = {
        {
            ui_action_entry( string_format( _( "Activatable (%d)" ), tabs[0].rows.size() ),
                             "ACTIVE_TAB", true, tab == 0 )
        },
        {
            ui_action_entry( string_format( _( "Passive (%d)" ), tabs[1].rows.size() ),
                             "PASSIVE_TAB", true, tab == 1 )
        },
        {
            ui_action_entry( string_format( _( "Sort: %s" ), sort_label( uistate.bionic_sort_mode ) ),
                             "SORT", true, false, std::string(), std::nullopt, true ), 1
        }
    };
    if( get_option<bool>( "UI_TEST_MODE" ) ) {
        actions.push_back( { ui_action_entry( _( "Test" ), "TEST", true, false,
                                              std::string(), std::nullopt, true ), 1 } );
    }
    actions.push_back( {
        ui_action_entry( single_pane && details_focus ? _( "Back to list" ) : _( "Back" ),
                         "BACK" ), 2, ui_action_alignment::right
    } );
    toolbar.configure( window, point( 1, 1 ), std::move( actions ),
                       getmaxx( window ) - 2, std::min( 4, std::max( 1, getmaxy( window ) - 6 ) ) );
}

void bionics_window::resize( ui_adaptor &adaptor )
{
    close_transients();
    for( tab_state &state : tabs ) {
        state.list.invalidate_geometry();
    }
    inspector.hide();
    shortcut.hide();
    settings.clear();
    primary.clear();
    toolbar.clear();
    if( hidden ) {
        adaptor.position( point::zero, point::zero );
        return;
    }
    int names = 22;
    for( const bionic &bio : *p.my_bionics ) {
        names = std::max( names, utf8_width( bio.info().name.translated() ) );
    }
    const bool empty = tabs[tab].rows.empty();
    const int preferred_list = std::clamp( names + 25, 44, 56 );
    const int width = std::min( TERMX, empty ? 86 : preferred_list + 51 );
    // Measure the actual wrapping toolbar before deciding the content height.
    window = catacurses::newwin( std::min( TERMY, 30 ), width, point::zero );
    configure_toolbar();
    const int toolbar_rows = toolbar.rows_used();
    int content = 4;
    if( !empty ) {
        content = 12;
        for( const bionic &bio : *p.my_bionics ) {
            const int detail_lines = 8 + static_cast<int>( foldstring( bio.info().description.translated(),
                std::max( 20, width >= 88 ? 46 : width - 4 ) ).size() ) +
                                     ( bio.supports_safe_fuel() ? 1 : 0 ) +
                                     ( get_option<bool>( "CBM_SLOTS_ENABLED" ) ?
                                       static_cast<int>( bio.info().occupied_bodyparts.size() ) + 2 : 0 );
            content = std::max( content, std::min( 21, detail_lines ) );
        }
        content = std::max( content, std::min( 21, static_cast<int>( std::max( tabs[0].rows.size(),
            tabs[1].rows.size() ) ) ) );
    }
    const int height = std::min( TERMY, std::min( 30, content + toolbar_rows + 6 ) );
    window = catacurses::newwin( height, width, point( ( TERMX - width ) / 2,
        ( TERMY - height ) / 2 ) );
    single_pane = width < 88 && height - toolbar_rows - 5 < 13;
    configure_toolbar();
    status_y = 1 + toolbar.rows_used();
    divider_y = status_y + 1;
    const int top = divider_y + 1;
    const int body_height = std::max( 0, height - top - 2 );
    stacked = width < 88 && body_height >= 13;
    single_pane = width < 88 && !stacked;
    show_list = !single_pane || !details_focus;
    show_inspector = !single_pane || details_focus;
    list_origin = point( 1, top );
    list_width = std::max( 0, width - 2 );
    list_height = body_height;
    detail_origin = list_origin;
    detail_width = list_width;
    detail_height = body_height;
    if( !single_pane && !stacked ) {
        list_width = std::min( preferred_list, ( width - 3 ) / 2 );
        detail_origin.x = list_width + 2;
        detail_width = std::max( 0, width - detail_origin.x - 1 );
    } else if( stacked ) {
        list_height = std::clamp( static_cast<int>( std::max( tabs[0].rows.size(), tabs[1].rows.size() ) ),
                                  3, std::max( 3, body_height / 3 ) );
        detail_origin.y = top + list_height + 1;
        detail_height = body_height - list_height - 1;
    }
    // One row above the list describes its controls and offers Details on
    // constrained terminals; one row below the inspector is its primary action.
    list_origin.y++;
    list_height = std::max( 0, list_height - 1 );
    detail_height = std::max( 0, detail_height - 1 );
    adaptor.position_from_window( window );
}

void bionics_window::build_inspector( int width )
{
    lines.clear();
    shortcut_line = fuel_line = -1;
    const auto add = [&]( const std::string & text, nc_color color = c_light_gray ) {
        for( const std::string &line : foldstring( text, std::max( 1, width ) ) ) {
            lines.push_back( { line, color, "" } );
        }
    };
    bionic *bio = selected();
    if( !bio ) {
        add( _( "Select a bionic to see its details." ) );
        return;
    }
    const bionic_data &data = bio->info();
    add( data.name.translated(), c_white );
    add( bio->incapacitated_time > 0_turns ? _( "INCAPACITATED" ) :
         !data.activated ? _( "PASSIVE" ) : bio->powered ? _( "ACTIVE" ) : _( "INACTIVE" ),
         bio->incapacitated_time > 0_turns ? c_light_red : bio->powered ? c_light_green : c_light_cyan );
    const ui_action_entry action = power_action( *bio );
    if( !action.enabled && data.activated ) {
        add( action.disabled_reason, c_light_red );
    }
    add( "" );
    add( _( "Power" ), c_light_cyan );
    if( data.power_activate > 0_J ) {
        add( string_format( _( "Activation: %s" ), units::display( data.power_activate ) ) );
    }
    if( data.has_flag( json_flag_BIONIC_GUN ) && bio->has_weapon() ) {
        add( string_format( _( "Firing: %s" ),
                            units::display( bio->get_weapon().get_gun_bionic_drain() ) ) );
    }
    if( data.power_deactivate > 0_J ) {
        add( string_format( _( "Deactivation: %s" ), units::display( data.power_deactivate ) ) );
    }
    if( data.power_trigger > 0_J ) {
        add( string_format( _( "Trigger: %s" ), units::display( data.power_trigger ) ) );
    }
    if( data.charge_time > 0_turns && data.power_over_time > 0_J ) {
        add( data.charge_time == 1_turns ?
             string_format( _( "Running: %s / turn" ), units::display( data.power_over_time ) ) :
             string_format( _( "Running: %s / %d turns" ), units::display( data.power_over_time ),
                            to_turns<int>( data.charge_time ) ) );
    }
    if( data.power_activate == 0_J && data.power_over_time == 0_J && data.power_trigger == 0_J &&
        data.power_deactivate == 0_J && !data.has_flag( json_flag_BIONIC_GUN ) ) {
        add( _( "No power cost." ) );
    }
    if( bio->is_safe_fuel_on() && bio->powered &&
        bio->get_safe_fuel_thresh() * p.get_max_power_level() - 1_kJ <= p.get_power_level() ) {
        add( _( "Fuel saving: generation paused at the reserve threshold." ), c_yellow );
    }
    add( "" );
    add( data.description.translated(), c_light_blue );
    if( bio->has_weapon() ) {
        add( string_format( _( "Installed weapon: %s" ), bio->get_weapon().tname() ) );
    }
    add( "" );
    add( _( "Settings" ), c_light_cyan );
    shortcut_line = static_cast<int>( lines.size() );
    lines.push_back( { "", c_light_gray, "SHORTCUT" } );
    if( bio->supports_safe_fuel() ) {
        fuel_line = static_cast<int>( lines.size() );
        lines.push_back( { "", c_light_gray, "FUEL" } );
    }
    if( bio->can_install_weapon() ) {
        lines.push_back( { "", c_light_gray, "WEAPON" } );
    }
    if( get_option<bool>( "CBM_SLOTS_ENABLED" ) ) {
        add( "" );
        add( _( "Body slots" ), c_light_cyan );
        if( data.occupied_bodyparts.empty() ) {
            add( _( "No body slots occupied." ) );
        }
        for( const auto &part : data.occupied_bodyparts ) {
            const bodypart_id bp = part.first.id();
            const int total = p.get_total_bionics_slots( bp );
            add( string_format( _( "%s: this CBM %d; total %d / %d" ),
                                body_part_name_as_heading( bp, 1 ), part.second,
                                total - p.get_free_bionics_slots( bp ), total ) );
        }
    }
}

std::string bionics_window::global_status()
{
    std::vector<std::string> fuel;
    std::set<const item *> seen;
    const auto append = [&]( const item * source ) {
        if( !source || !seen.insert( source ).second ) {
            return;
        }
        const item *content = nullptr;
        if( source->ammo_remaining() > 0 ) {
            content = &source->first_ammo();
        } else {
            const auto contents = source->all_items_top();
            if( !contents.empty() ) {
                content = contents.front();
            }
        }
        if( content ) {
            fuel.push_back( string_format( "%s: %d", content->tname(), content->charges ) );
        }
    };
    for( const bionic &bio : *p.my_bionics ) {
        for( const item *source : p.get_bionic_fuels( bio.id ) ) {
            append( source );
        }
    }
    for( const item *ups : p.get_cable_ups() ) {
        append( ups );
    }
    for( vehicle *veh : p.get_cable_vehicle() ) {
        const int64_t charges = veh->connected_battery_power_level( get_map() ).first;
        if( charges > 0 ) {
            fuel.push_back( string_format( "%s: %d", item( itype_battery ).tname(), charges ) );
        }
    }
    std::string result = string_format( _( "Power %s / %s" ), units::display( p.get_power_level() ),
                                        units::display( p.get_max_power_level() ) );
    if( !fuel.empty() ) {
        result += "   " + string_format( _( "Fuel: %s" ),
                                         enumerate_as_string( fuel, enumeration_conjunction::none ) );
    }
    return result;
}

void bionics_window::draw()
{
    if( hidden || !window ) {
        return;
    }
    werase( window );
    draw_border( window, BORDER_COLOR, _( " Bionics " ) );
    configure_toolbar();
    toolbar.draw( window );
    trim_and_print( window, point( 1, status_y ), getmaxx( window ) - 2, c_light_gray,
                    global_status() );
    mvwhline( window, point( 1, divider_y ), LINE_OXOX, getmaxx( window ) - 2 );
    if( !single_pane && !stacked ) {
        mvwvline( window, point( detail_origin.x - 1, list_origin.y - 1 ), LINE_XOXO,
                  list_height + 1 );
    } else if( stacked ) {
        mvwhline( window, point( 1, detail_origin.y - 1 ), LINE_OXOX, getmaxx( window ) - 2 );
    }
    settings.begin_layout();
    if( !show_inspector ) {
        shortcut.hide();
    }
    if( show_list ) {
        tabs[tab].list.draw( window, list_origin, list_width, list_height );
        if( tabs[tab].rows.empty() ) {
            trim_and_print( window, list_origin, list_width - 1, c_light_gray,
                            tab == 0 ? _( "No activatable bionics installed." ) : _( "No passive bionics installed." ) );
        }
        if( single_pane ) {
            primary.configure( window, list_origin - point( 0, 1 ),
            { ui_action_entry( _( "Details" ), "DETAILS", selected() != nullptr ) }, list_width );
            primary.draw( window );
        } else {
            trim_and_print( window, list_origin - point( 0, 1 ), list_width - 1, c_light_cyan,
                            tab == 0 ? _( "State / Bionic / Power / Sprite" ) : _( "Bionic / Sprite" ) );
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
            const inspector_line &line = lines[i];
            if( line.control.empty() ) {
                trim_and_print( window, *pos, detail_width - 1, line.color, line.text );
            } else if( line.control == "SHORTCUT" ) {
                bionic &bio = *selected();
                shortcut.configure( window, *pos, detail_width - 1, _( "Shortcut" ),
                                    bio.invlet == ' ' ? _( "None" ) : std::string( 1, bio.invlet ), _( "Press a key…" ) );
                shortcut.draw( window );
            }
        }
        if( !inspector.position( shortcut_line ) ) {
            shortcut.hide();
        }
        // Fuel and weapon settings are consecutive rows. A vertical action
        // strip owns their individual regions, including clipped-away rows.
        bionic *bio = selected();
        if( bio ) {
            for( int i = 0; i < static_cast<int>( lines.size() ); ++i ) {
                if( lines[i].control != "FUEL" && lines[i].control != "WEAPON" ) {
                    continue;
                }
                if( const auto pos = inspector.position( i ) ) {
                    ui_action_entry action = lines[i].control == "FUEL" ?
                                             ui_action_entry( string_format( _( "Fuel reserve: %s" ),
                                                 fuel_label( bio->get_safe_fuel_thresh() ) ),
                                                 "FUEL", true, false, std::string(), std::nullopt, true ) :
                                             ui_action_entry( bio->has_weapon() ? _( "Uninstall weapon" ) : _( "Install weapon" ),
                                                 "WEAPON", !bio->powered, false, _( "Deactivate this bionic first." ) );
                    settings.add_row( window, *pos, std::move( action ), detail_width - 1 );
                }
            }
            settings.draw( window );
        }
        inspector.draw_scrollbar( window );
        std::vector<ui_action_strip_item> actions;
        if( bio ) {
            actions.push_back( { power_action( *bio ) } );
        }
        primary.configure( window, detail_origin + point( 0, detail_height ), std::move( actions ),
                           detail_width - 1 );
        primary.draw( window );
    }
    const std::string hint = !status.empty() ? status : shortcut.armed() ?
                             _( "Press a shortcut; Space clears, Esc cancels." ) :
                             details_focus ?
                             string_format( _( "Details: arrows / wheel scroll.  %s returns to list." ),
                                            ctxt.get_desc( "TOGGLE_EXAMINE" ) ) :
                             string_format( _( "Select to inspect; %s activates.  %s focuses details." ),
                                            ctxt.get_desc( "CONFIRM" ), ctxt.get_desc( "TOGGLE_EXAMINE" ) );
    trim_and_print( window, point( 1, getmaxy( window ) - 2 ), getmaxx( window ) - 2,
                    shortcut.armed() ? c_yellow : c_light_gray, hint );
    wnoutrefresh( window );
    dropdown.draw( window );
}

void bionics_window::open_dropdown( const std::string &kind )
{
    close_transients();
    std::vector<ui_dropdown_entry> choices;
    if( kind == "SORT" ) {
        for( const bionic_ui_sort_mode mode : {
                 bionic_ui_sort_mode::POWER, bionic_ui_sort_mode::NAME,
                 bionic_ui_sort_mode::INVLET, bionic_ui_sort_mode::NONE
             } ) {
            choices.emplace_back( sort_label( mode ), io::enum_to_string( mode ), true,
                                  uistate.bionic_sort_mode == mode );
        }
        dropdown_trigger = toolbar.bounds_for_id( "SORT" );
    } else if( kind == "TEST" && get_option<bool>( "UI_TEST_MODE" ) ) {
        choices.emplace_back( _( "Grant bionics test suite" ), "GRANT_SUITE" );
        choices.emplace_back( _( "Add 500 battery charges" ), "ADD_BATTERY" );
        choices.emplace_back( _( "Set full power" ), "POWER_FULL" );
        choices.emplace_back( _( "Set low power (10%)" ), "POWER_LOW" );
        choices.emplace_back( _( "Set empty power" ), "POWER_EMPTY" );
        choices.emplace_back( _( "Apply mixed active / sprite / fuel states" ), "MIXED_STATES" );
        choices.emplace_back( _( "Incapacitate selected bionic" ), "INCAPACITATE_SELECTED" );
        choices.emplace_back( _( "Clear selected incapacitation" ), "CLEAR_INCAPACITATION" );
        choices.emplace_back( _( "Clear test bionics" ), "CLEAR_SUITE" );
        dropdown_trigger = toolbar.bounds_for_id( "TEST" );
    } else if( bionic *bio = selected(); bio && bio->supports_safe_fuel() ) {
        dropdown_bionic = bio->get_uid();
        for( int i = 0; i < static_cast<int>( bionics_ui::fuel_thresholds.size() ); ++i ) {
            const float value = bionics_ui::fuel_thresholds[i];
            choices.emplace_back( fuel_label( value ), std::to_string( i ), true,
                                  bio->get_safe_fuel_thresh() == value );
        }
        dropdown_trigger = settings.bounds_for_id( "FUEL" );
    }
    if( choices.empty() ) {
        return;
    }
    dropdown_kind = kind;
    const point anchor = dropdown_trigger ?
                         point( dropdown_trigger->p_min.x, dropdown_trigger->p_max.y + 1 ) : point( 1, divider_y );
    dropdown.configure( window, anchor, std::move( choices ) );
    dropdown.focus_selected();
}

void bionics_window::apply_test_fixture( const std::string &fixture )
{
    if( !get_option<bool>( "UI_TEST_MODE" ) ) {
        return;
    }

    const auto test_bionics = [&]() {
        std::vector<bionic *> result;
        for( bionic &bio : *p.my_bionics ) {
            if( bio.has_flag( bionic_ui_test_tag ) ) {
                result.push_back( &bio );
            }
        }
        return result;
    };

    if( fixture == "GRANT_SUITE" ) {
        std::set<bio_uid> existing;
        for( const bionic &bio : *p.my_bionics ) {
            existing.insert( bio.get_uid() );
        }

        std::vector<bionic_id> chosen;
        const auto eligible = [&]( const bionic_data & data ) {
            return !data.included && !data.activated_on_install && !data.cant_remove_reason &&
                   !data.has_flag( json_flag_BIONIC_FAULTY ) && !p.has_bionic( data.id ) &&
                   std::find( chosen.begin(), chosen.end(), data.id ) == chosen.end();
        };
        const auto add_matching = [&]( auto predicate, int limit ) {
            int added = 0;
            for( const bionic_data &data : bionic_data::get_all() ) {
                if( added >= limit ) {
                    break;
                }
                if( eligible( data ) && predicate( data ) ) {
                    chosen.push_back( data.id );
                    ++added;
                }
            }
        };

        // Cover the important UI shapes first, then fill out the list so scrolling,
        // sorting and clipping can be tested without depending on a specific character.
        add_matching( []( const bionic_data & d ) { return d.activated; }, 6 );
        add_matching( []( const bionic_data & d ) { return !d.activated; }, 6 );
        add_matching( []( const bionic_data & d ) {
            return !d.fuel_opts.empty() || d.is_remote_fueled;
        }, 4 );
        add_matching( []( const bionic_data & d ) {
            return d.has_flag( json_flag_BIONIC_GUN ) || !d.fake_weapon.is_empty() ||
                   !d.installable_weapon_flags.empty();
        }, 4 );
        add_matching( []( const bionic_data & d ) {
            return d.power_over_time > 0_J || d.power_trigger > 0_J || d.power_deactivate > 0_J;
        }, 4 );
        add_matching( []( const bionic_data & ) { return true; },
                      std::max( 0, 30 - static_cast<int>( chosen.size() ) ) );

        for( const bionic_id &id : chosen ) {
            p.add_bionic( id, 0, true );
        }

        int added = 0;
        for( bionic &bio : *p.my_bionics ) {
            if( existing.count( bio.get_uid() ) == 0 ) {
                bio.set_flag( bionic_ui_test_tag );
                ++added;
            }
        }

        p.update_bionic_power_capacity();
        if( p.get_max_power_level() < 1000_kJ ) {
            p.set_max_power_level( 1000_kJ );
        }
        p.set_power_level( p.get_max_power_level() );

        int active_index = 0;
        int sprite_index = 0;
        int fuel_index = 0;
        bool incapacitated = false;
        for( bionic *bio : test_bionics() ) {
            bio->show_sprite = ( sprite_index++ % 3 ) != 1;
            if( bio->info().activated ) {
                bio->powered = ( active_index++ % 3 ) == 1;
                bio->incapacitated_time = 0_turns;
                if( !incapacitated && !bio->powered ) {
                    bio->incapacitated_time = 10_minutes;
                    incapacitated = true;
                }
            }
            if( bio->supports_safe_fuel() ) {
                bio->set_safe_fuel_thresh(
                    bionics_ui::fuel_thresholds[fuel_index++ % bionics_ui::fuel_thresholds.size()] );
            }
        }
        status = string_format( _( "Added %d UI-test bionics and prepared mixed states." ), added );
    } else if( fixture == "ADD_BATTERY" ) {
        item battery( itype_battery, calendar::turn, 500 );
        p.i_add_or_drop( battery );
        status = _( "Added 500 battery charges." );
    } else if( fixture == "POWER_FULL" ) {
        if( p.get_max_power_level() <= 0_J ) {
            p.set_max_power_level( 1000_kJ );
        }
        p.set_power_level( p.get_max_power_level() );
        status = _( "Bionic power set to full." );
    } else if( fixture == "POWER_LOW" ) {
        if( p.get_max_power_level() <= 0_J ) {
            p.set_max_power_level( 1000_kJ );
        }
        p.set_power_level( p.get_max_power_level() / 10 );
        status = _( "Bionic power set to 10%." );
    } else if( fixture == "POWER_EMPTY" ) {
        p.set_power_level( 0_J );
        status = _( "Bionic power emptied." );
    } else if( fixture == "MIXED_STATES" ) {
        int active_index = 0;
        int sprite_index = 0;
        int fuel_index = 0;
        bool incapacitated = false;
        for( bionic *bio : test_bionics() ) {
            bio->show_sprite = ( sprite_index++ % 3 ) != 1;
            bio->incapacitated_time = 0_turns;
            if( bio->info().activated ) {
                bio->powered = ( active_index++ % 3 ) == 1;
                if( !incapacitated && !bio->powered ) {
                    bio->incapacitated_time = 10_minutes;
                    incapacitated = true;
                }
            }
            if( bio->supports_safe_fuel() ) {
                bio->set_safe_fuel_thresh(
                    bionics_ui::fuel_thresholds[fuel_index++ % bionics_ui::fuel_thresholds.size()] );
            }
        }
        status = _( "Applied mixed states to UI-test bionics." );
    } else if( fixture == "INCAPACITATE_SELECTED" ) {
        if( bionic *bio = selected() ) {
            bio->incapacitated_time = 10_minutes;
            status = _( "Selected bionic incapacitated for 10 minutes." );
        } else {
            status = _( "Select a bionic first." );
        }
    } else if( fixture == "CLEAR_INCAPACITATION" ) {
        if( bionic *bio = selected() ) {
            bio->incapacitated_time = 0_turns;
            status = _( "Selected bionic incapacitation cleared." );
        } else {
            status = _( "Select a bionic first." );
        }
    } else if( fixture == "CLEAR_SUITE" ) {
        std::vector<bio_uid> remove;
        for( const bionic &bio : *p.my_bionics ) {
            if( bio.has_flag( bionic_ui_test_tag ) ) {
                remove.push_back( bio.get_uid() );
            }
        }
        int removed = 0;
        for( const bio_uid uid : remove ) {
            if( const std::optional<bionic *> current = p.find_bionic_by_uid( uid ) ) {
                ( *current )->powered = false;
                p.remove_bionic( **current );
                ++removed;
            }
        }
        p.update_bionic_power_capacity();
        if( p.get_power_level() > p.get_max_power_level() ) {
            p.set_power_level( p.get_max_power_level() );
        }
        status = string_format( _( "Removed %d UI-test bionics." ), removed );
    }

    p.invalidate_pseudo_items();
    p.recalculate_enchantment_cache();
    rebuild();
    ui.mark_resize();
    g->invalidate_main_ui_adaptor();
}

void bionics_window::handoff( bio_uid uid, bool weapon_management )
{
    bionic *bio = find( uid );
    if( !bio ) {
        return;
    }
    const ui_action_entry eligible = power_action( *bio );
    if( !weapon_management && !eligible.enabled ) {
        status = eligible.disabled_reason;
        return;
    }
    if( weapon_management && ( !bio->can_install_weapon() || bio->powered ) ) {
        status = _( "Deactivate this bionic first." );
        return;
    }
    const bool was_powered = bio->powered;
    const bool closes_activate = bio->info().activated_close_ui;
    const bool closes_deactivate = bio->info().deactivated_close_ui;
    const bool install = !bio->powered && bio->can_install_weapon() && !bio->has_weapon();
    close_transients();
    hidden = true;
    ui.mark_resize();
    g->invalidate_main_ui_adaptor();
    ui_manager::redraw();
    // All CBM-owned item/world/target queries now run above the underlying game,
    // without retaining a visible Bionics surface or a dropdown.
    if( weapon_management || install ) {
        if( bio->has_weapon() ) {
            if( std::optional<item> weapon = bio->uninstall_weapon() ) {
                p.i_add_or_drop( *weapon );
            }
        } else {
            uilist menu;
            menu.title = _( "Select weapon to install" );
            std::vector<item *> weapons = p.items_with( [bio]( const item & it ) {
                return it.has_any_flag( bio->info().installable_weapon_flags );
            } );
            for( int i = 0; i < static_cast<int>( weapons.size() ); ++i ) {
                menu.addentry( i, true, MENU_AUTOASSIGN, weapons[i]->tname() );
            }
            if( weapons.empty() ) {
                status = _( "You don't have any items you can install in this bionic." );
            } else {
                menu.query();
                if( menu.ret >= 0 && menu.ret < static_cast<int>( weapons.size() ) ) {
                    item &weapon = *weapons[menu.ret];
                    if( bio->can_install_weapon( weapon ) && bio->install_weapon( weapon ) ) {
                        item_location( p, &weapon ).remove_item();
                    } else {
                        status = string_format( _( "Unable to install %s" ), weapon.tname() );
                    }
                }
            }
        }
    } else if( was_powered ) {
        p.deactivate_bionic( *bio );
        done = closes_deactivate;
    } else {
        bool close_ui = false;
        if( closes_activate ) {
            ui.reset();
        }
        p.activate_bionic( *bio, false, &close_ui );
        // Never dereference bio after gameplay: EOCs may alter the collection.
        bionic *after = find( uid );
        done = closes_activate || ( close_ui && after && after->has_weapon() &&
                                    after->get_weapon().shots_remaining( get_map(), &p ) > 0 );
    }
    done = done || p.get_moves() < 0;
    if( done ) {
        return; // Do not flash a stale Bionics frame on the way out.
    }
    hidden = false;
    rebuild();
    ui.mark_resize();
    g->invalidate_main_ui_adaptor();
}

void bionics_window::dispatch( const std::string &action, std::optional<bio_uid> uid )
{
    if( action == "BACK" ) {
        if( single_pane && details_focus ) {
            dispatch( "LIST" );
        } else {
            done = true;
        }
        return;
    }
    if( action == "ACTIVE_TAB" || action == "PASSIVE_TAB" ) {
        close_transients();
        tab = action == "ACTIVE_TAB" ? 0 : 1;
        details_focus = false;
        inspector.model().scroll_to_start();
        status.clear();
        ui.mark_resize();
        return;
    }
    if( action == "SORT" ) {
        open_dropdown( "SORT" );
        return;
    }
    if( action == "TEST" ) {
        open_dropdown( "TEST" );
        return;
    }
    if( action == "LIST" || action == "DETAILS" ) {
        close_transients();
        details_focus = action == "DETAILS";
        if( single_pane ) {
            ui.mark_resize();
        }
        return;
    }
    if( !uid ) {
        uid = tabs[tab].selected;
    }
    bionic *bio = uid ? find( *uid ) : nullptr;
    if( !bio ) {
        status = _( "Select a bionic first." );
        return;
    }
    if( action == "SELECT_BIONIC" ) {
        select( *uid );
        details_focus = false;
    } else if( action == "SPRITE" ) {
        bio->show_sprite = !bio->show_sprite;
        rebuild();
        g->invalidate_main_ui_adaptor();
    } else if( action == "POWER" || action == "WEAPON" ) {
        handoff( *uid, action == "WEAPON" );
    } else if( action == "SHORTCUT" || action == "FUEL" ) {
        if( action == "FUEL" && !bio->supports_safe_fuel() ) {
            return;
        }
        close_transients();
        if( single_pane && !details_focus ) {
            details_focus = true;
            ui.mark_resize();
            ui_manager::redraw();
        }
        build_inspector( detail_width - 1 );
        inspector.model().ensure_visible( action == "SHORTCUT" ? shortcut_line : fuel_line );
        ui.invalidate_ui();
        ui_manager::redraw_invalidated();
        status.clear();
        if( action == "SHORTCUT" ) {
            shortcut.arm();
        } else {
            open_dropdown( "FUEL" );
        }
    }
}

void bionics_window::run()
{
    while( !done ) {
        ui_manager::redraw();
        if( shortcut.armed() ) {
            const ui_key_field_result result = shortcut.read( bionics_ui::valid_shortcut );
            if( result.type == ui_key_field_result_type::assigned ||
                result.type == ui_key_field_result_type::cleared ) {
                if( tabs[tab].selected ) {
                    bionics_ui::assign_shortcut( *p.my_bionics, *tabs[tab].selected, result.key );
                    rebuild();
                    tabs[tab].list.scroll_model().ensure_visible( tabs[tab].list.cursor() );
                }
                status.clear();
            } else if( result.type == ui_key_field_result_type::invalid ) {
                status = _( "Invalid shortcut.  Use a bionic letter, Space to clear, or Esc to cancel." );
            } else if( result.type == ui_key_field_result_type::cancelled ) {
                status.clear();
            }
            continue;
        }
        const std::string action = ctxt.handle_input();
        const std::optional<point> pos = ctxt.get_coordinates_text( window );
        if( dropdown.is_open() ) {
            const std::string kind = dropdown_kind;
            const std::optional<bio_uid> owner = dropdown_bionic;
            const ui_action_result result = dropdown.handle_input( action, pos, true,
                ui_outside_click_policy::passthrough, dropdown_trigger, &ctxt );
            if( result.type == ui_action_result_type::activated && result.entry ) {
                if( kind == "SORT" ) {
                    const std::string &id = result.entry->id;
                    uistate.bionic_sort_mode = id == "power" ? bionic_ui_sort_mode::POWER :
                                               id == "name" ? bionic_ui_sort_mode::NAME : id == "invlet" ?
                                               bionic_ui_sort_mode::INVLET : bionic_ui_sort_mode::NONE;
                    rebuild();
                    for( tab_state &state : tabs ) {
                        state.list.scroll_model().ensure_visible( state.list.cursor() );
                    }
                    // Translated sort labels can change the toolbar's wrap.
                    ui.mark_resize();
                } else if( kind == "TEST" ) {
                    apply_test_fixture( result.entry->id );
                } else if( owner ) {
                    if( bionic *bio = find( *owner ); bio && bio->supports_safe_fuel() ) {
                        bio->set_safe_fuel_thresh( bionics_ui::fuel_thresholds[std::stoi( result.entry->id )] );
                        g->invalidate_main_ui_adaptor();
                    }
                }
            }
            if( !dropdown.is_open() ) {
                close_transients();
            }
            if( result.consumed() ) {
                continue;
            }
        }
        // A captured scrollbar owns its release even over the other pane's
        // scrollbar or a button. The controls expose capture; the screen only
        // orders them, without implementing drag behavior.
        if( show_list && tabs[tab].list.has_capture() &&
            tabs[tab].list.handle_input( action, ctxt, pos ).consumed() ) {
            continue;
        }
        if( show_inspector && inspector.has_capture() &&
            inspector.handle_input( action, ctxt, pos ) ) {
            continue;
        }
        const auto route = [&]( const ui_action_result & result ) {
            if( result.type == ui_action_result_type::disabled && result.entry ) {
                status = result.entry->disabled_reason;
            } else if( result.type == ui_action_result_type::activated && result.entry ) {
                const auto row = row_actions.find( result.entry->id );
                if( row != row_actions.end() ) {
                    dispatch( row->second.first, row->second.second );
                } else {
                    dispatch( result.entry->id );
                }
            }
            return result.consumed();
        };
        // Broadcast hover to all visible controls, so leaving one never leaves
        // stale emphasis there. Keyboard Confirm uses selection, never hover.
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
                const auto row = row_actions.find( result.entry->id );
                if( row != row_actions.end() && row->second.first == "SELECT_BIONIC" ) {
                    // Even double clicking a label only inspects it.
                    dispatch( "SELECT_BIONIC", row->second.second );
                } else {
                    route( result );
                }
            } else if( result.consumed() && ( action == "UP" || action == "DOWN" ||
                                              action == "PAGE_UP" || action == "PAGE_DOWN" || action == "HOME" || action == "END" ) &&
                       !tabs[tab].rows.empty() ) {
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
            close_transients();
            shortcut.arm();
            status.clear();
            continue;
        }
        if( action == "QUIT" ) {
            dispatch( "BACK" );
        } else if( action == "NEXT_TAB" || action == "PREV_TAB" ) {
            dispatch( tab == 0 ? "PASSIVE_TAB" : "ACTIVE_TAB" );
        } else if( action == "TOGGLE_EXAMINE" ) {
            dispatch( details_focus ? "LIST" : "DETAILS" );
        } else if( action == "SORT" ) {
            dispatch( "SORT" );
        } else if( action == "REASSIGN" ) {
            dispatch( "SHORTCUT" );
        } else if( action == "TOGGLE_SAFE_FUEL" ) {
            dispatch( "FUEL" );
        } else if( action == "TOGGLE_SPRITE" ) {
            dispatch( "SPRITE" );
        } else if( action == "BIONICS_WEAPON" ) {
            dispatch( "WEAPON" );
        } else if( action == "CONFIRM" ) {
            dispatch( "POWER" );
        } else if( action == "ANY_INPUT" && ctxt.get_raw_input().type == input_event_t::keyboard_char ) {
            if( bionic *bio = p.bionic_by_invlet( ctxt.get_raw_input().get_first_input() ) ) {
                const bio_uid uid = bio->get_uid();
                const int target_tab = bio->info().activated ? 0 : 1;
                if( target_tab != tab ) {
                    dispatch( target_tab == 0 ? "ACTIVE_TAB" : "PASSIVE_TAB" );
                }
                select( uid );
                if( bio->info().activated ) {
                    dispatch( "POWER", uid );
                }
            }
        }
    }
}
} // namespace

void avatar::power_bionics()
{
    bionics_window( *this ).run();
}
