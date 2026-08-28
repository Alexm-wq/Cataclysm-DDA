#include "crafting_destination_ui.h"

#include <algorithm>
#include <utility>

#include "character.h"
#include "input_context.h"
#include "item.h"
#include "map.h"
#include "output.h"
#include "recipe.h"
#include "ret_val.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui_helpers/controls/selection_panel.h"
#include "ui_manager.h"

static const std::array<std::string, 9> tile_actions = {
    "OUTPUT_NW", "OUTPUT_N", "OUTPUT_NE", "OUTPUT_W", "OUTPUT_CE", "OUTPUT_E",
    "OUTPUT_SW", "OUTPUT_S", "OUTPUT_SE"
};

static std::array<std::string, 9> tile_labels()
{
    return { _( "NW" ), _( "N" ), _( "NE" ), _( "W" ), _( "You" ), _( "E" ),
             _( "SW" ), _( "S" ), _( "SE" ) };
}

void crafting_destination_picker::refresh( Character &crafter, const recipe *rec, const int batch )
{
    if( crafter_ == &crafter && recipe_ == rec && batch_ == batch ) {
        return;
    }
    if( crafter_ != &crafter ) {
        explicit_selection_ = false;
    }
    crafter_ = &crafter;
    recipe_ = rec;
    batch_ = batch;
    results_.clear();
    if( rec && !rec->is_nested() && !rec->is_practice() && !rec->result().is_null() ) {
        results_ = rec->create_results( batch );
    }
    for( int i = 0; i < 9; ++i ) {
        tiles_[i] = crafting_destinations_at( crafter, get_player_character().pos_bub() +
                                             tripoint( ui_compass_grid::offset( i ), 0 ), results_ );
    }
    if( !explicit_selection_ ) {
        destination_ = crafting_destination();
    }
}

bool crafting_destination_picker::available() const
{
    return !results_.empty();
}

std::string crafting_destination_picker::unavailable_reason() const
{
    if( !available() || destination_.kind == crafting_destination_kind::automatic ) {
        return std::string();
    }
    std::string reason;
    for( const item &result : results_ ) {
        const ret_val<void> fit = crafting_destination_can_accept( *crafter_, destination_, result );
        if( fit.success() ) {
            return std::string();
        }
        if( reason.empty() ) {
            reason = fit.str();
        }
    }
    return reason;
}

crafting_destination crafting_destination_picker::destination() const
{
    return available() ? destination_ : crafting_destination();
}

std::optional<int> crafting_destination_picker::selected_tile() const
{
    if( destination_.kind != crafting_destination_kind::automatic ) {
        const item_location target = destination_.target();
        const tripoint_abs_ms pos = target ? target.pos_abs() : destination_.position;
        for( int i = 0; i < 9; ++i ) {
            if( tiles_[i].position == pos ) {
                return i;
            }
        }
    }
    return std::nullopt;
}

std::array<ui_compass_entry, 9> crafting_destination_picker::compass_entries(
    const std::optional<int> selected ) const
{
    std::array<ui_compass_entry, 9> entries;
    const std::array<std::string, 9> labels = tile_labels();
    for( int i = 0; i < 9; ++i ) {
        const crafting_destination_tile &tile = tiles_[i];
        entries[i] = { ui_action_entry( labels[i], tile_actions[i], !tile.blocked,
                                       selected && *selected == i, _( "There is no accessible storage on this tile." ) ),
                       tile.blocked, tile.dangerous, tile.has_items, tile.has_vehicle_storage };
    }
    return entries;
}

std::string crafting_destination_picker::summary() const
{
    if( const std::optional<int> index = selected_tile() ) {
        for( const crafting_destination_option &option : tiles_[*index].options ) {
            if( !option.inventory_root && option.destination == destination_ ) {
                std::string path = option.name;
                for( int parent = option.parent; parent >= 0;
                     parent = tiles_[*index].options[parent].parent ) {
                    path = tiles_[*index].options[parent].name + " > " + path;
                }
                return string_format( "%s: %s", tile_labels()[*index], path );
            }
        }
        return _( "Destination unavailable" );
    }
    return destination_.kind == crafting_destination_kind::automatic ? _( "Usual placement" ) :
           _( "Destination unavailable" );
}

void crafting_destination_picker::draw( const catacurses::window &window, const point &origin,
                                       const int width )
{
    compass_.set_entries( compass_entries( selected_tile() ) );
    compass_.draw( window, origin, width );
    const int text_offset = compass_.width() + 2;
    const point text_pos = origin + point( text_offset, 0 );
    const int text_width = width - text_offset;
    if( text_width < 1 ) {
        summary_.clear();
        return;
    }
    trim_and_print( window, text_pos, text_width, c_light_gray, _( "Place result:" ) );
    ui_action_strip_style style;
    style.text = c_light_gray;
    style.highlight = h_white;
    summary_.configure( window, text_pos + point( 0, 1 ),
                        { ui_action_entry( summary(), "CHOOSE_OUTPUT", true, false, "", std::nullopt, true ) },
                        text_width, 1, style );
    summary_.draw( window );
    trim_and_print( window, text_pos + point( 0, 2 ), text_width, c_dark_gray,
                    _( "Click a tile to choose storage" ) );
}

ui_action_result crafting_destination_picker::handle_input( const std::string &action,
        const std::optional<point> &pos )
{
    const ui_action_result tile = compass_.handle_input( action, pos );
    const ui_action_result button = summary_.handle_input( action, pos );
    return tile.consumed() ? tile : button;
}

bool crafting_destination_picker::query( const std::string &tile_action )
{
    if( !available() ) {
        return false;
    }
    int tile_index = selected_tile().value_or( 4 );
    const auto clicked = std::find( tile_actions.begin(), tile_actions.end(), tile_action );
    if( clicked != tile_actions.end() ) {
        tile_index = static_cast<int>( clicked - tile_actions.begin() );
    }
    std::array<ui_selection_panel, 9> panels;
    std::array<bool, 9> initialized{};
    ui_compass_grid compass;
    std::string status;
    const auto rebuild_list = [&]() {
        status.clear();
        if( initialized[tile_index] ) {
            return;
        }
        ui_selection_list &list = panels[tile_index].list;
        std::vector<ui_action_entry> entries;
        std::vector<ui_tree_node> nodes;
        const std::vector<crafting_destination_option> &options = tiles_[tile_index].options;
        for( size_t i = 0; i < options.size(); ++i ) {
            const crafting_destination_option &option = options[i];
            ui_action_entry entry( option.name, std::to_string( i ),
                                   option.enabled || option.inventory_root,
                                   !option.inventory_root && option.destination == destination_,
                                   option.reason );
            // Inventory groups show occupancy; actual destinations show whether the result fits.
            const bool positive = option.inventory_root ? option.has_items : option.enabled;
            entry.tone = positive ? ui_action_tone::positive : ui_action_tone::normal;
            if( !entry.enabled ) {
                entry.disabled_hint = option.too_small ? _( "too small!" ) : option.reason;
            }
            entries.push_back( std::move( entry ) );
            nodes.push_back( { option.parent, !option.inventory_root } );
        }
        list.set_tree_entries( std::move( entries ), std::move( nodes ) );
        initialized[tile_index] = true;
    };
    rebuild_list();

    input_context context( "CRAFTING_DESTINATION" );
    for( const char *action : { "UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "QUIT", "SELECT", "MOUSE_MOVE",
                              "SCROLL_UP", "SCROLL_DOWN",
                              "PAGE_UP", "PAGE_DOWN", "HOME", "END", "HELP_KEYBINDINGS" } ) {
        context.register_action( action );
    }
    for( const std::string &action : tile_actions ) {
        context.register_action( action );
    }

    catacurses::window window;
    ui_adaptor ui;
    ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
        const int width = std::min( TERMX, 76 );
        const int height = std::min( TERMY, 24 );
        window = catacurses::newwin( height, width, point( ( TERMX - width ) / 2, ( TERMY - height ) / 2 ) );
        adaptor.position_from_window( window );
    } );
    ui.mark_resize();
    ui.on_redraw( [&]( const ui_adaptor & ) {
        werase( window );
        ui_selection_panel &panel = panels[tile_index];
        const std::vector<int> selected = panel.list.selected_indices();
        ui_selection_panel_content content;
        content.title = _( "Crafting output" );
        content.heading = string_format( _( "%s — Choose destination" ), tile_labels()[tile_index] );
        content.status = status.empty() ? _( "1–9: tiles.  Left/Right: expand.  Double-click or Enter: choose." ) :
                         status;
        content.status_is_error = !status.empty();
        content.primary = { _( "Use selected" ), "USE", !selected.empty(), false,
                            _( "Select a destination first." ) };
        content.secondary = { { _( "Usual placement" ), "AUTOMATIC" } };
        content.back = { _( "Back" ), "BACK" };
        ui_selection_panel_layout layout;
        layout.heading_y = 6;
        layout.list_y = 8;
        layout.secondary_rows = 1;
        ui_selection_panel_style style;
        style.list.cursor = h_light_gray;
        style.list.positive_cursor = hilite( c_light_green );
        style.list.positive_selected = hilite( c_light_green );
        style.list.allow_label_colors = false;
        panel.draw( window, content, style, layout );
        compass.set_entries( compass_entries( tile_index ) );
        compass.draw( window, point( 2, 2 ), getmaxx( window ) - 4 );
        const int legend_x = compass.width() + 4;
        const int legend_width = getmaxx( window ) - legend_x - 2;
        trim_and_print( window, point( legend_x, 2 ), legend_width, c_light_green,
                        _( "Green: contains items" ) );
        trim_and_print( window, point( legend_x, 3 ), legend_width, c_light_red,
                        _( "Red: danger" ) );
        trim_and_print( window, point( legend_x, 4 ), legend_width, c_light_gray,
                        _( "Solid tile: blocked" ) );
        wnoutrefresh( window );
    } );
    while( true ) {
        ui_manager::redraw();
        const std::string action = context.handle_input();
        const std::optional<point> pos = context.get_coordinates_text( window );
        const ui_action_result tile = compass.handle_input( action, pos );
        if( tile.type == ui_action_result_type::disabled && tile.entry ) {
            status = tile.entry->disabled_reason;
            continue;
        }
        if( tile.type == ui_action_result_type::activated && tile.entry ) {
            const auto found = std::find( tile_actions.begin(), tile_actions.end(), tile.entry->id );
            tile_index = static_cast<int>( found - tile_actions.begin() );
            rebuild_list();
            continue;
        }
        ui_selection_panel &panel = panels[tile_index];
        const ui_selection_panel_result response = panel.handle_input( action, context, pos );
        if( !response.action.entry ) {
            continue;
        }
        if( response.action.type == ui_action_result_type::disabled ) {
            status = response.action.entry->disabled_reason;
            continue;
        }
        if( response.action.type != ui_action_result_type::activated ) {
            if( response.action.type == ui_action_result_type::handled && response.action.entry->enabled ) {
                status.clear();
            }
            continue;
        }
        if( response.action.entry->id == "BACK" ) {
            return false;
        }
        if( response.action.entry->id == "AUTOMATIC" ) {
            destination_ = crafting_destination();
            explicit_selection_ = true;
            return true;
        }
        const std::vector<int> selected = panel.list.selected_indices();
        if( !selected.empty() ) {
            destination_ = tiles_[tile_index].options[selected.front()].destination;
            explicit_selection_ = true;
            return true;
        }
    }
}
