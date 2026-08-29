#include "construction_ui.h"

#include <algorithm>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "cata_scope_helpers.h"
#include "catacharset.h"
#include "character.h"
#include "color.h"
#include "construction.h"
#include "construction_category.h"
#include "construction_group.h"
#include "construction_target.h"
#include "crafting.h"
#include "cursesdef.h"
#include "game.h"
#include "input_context.h"
#include "inventory.h"
#include "line.h"
#include "map.h"
#include "mapdata.h"
#include "memory_fast.h"
#include "messages.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "requirements.h"
#include "ret_val.h"
#include "skill.h"
#include "string_formatter.h"
#include "translations.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/dropdown.h"
#include "ui_helpers/controls/scroll_view.h"
#include "ui_helpers/controls/selection_list.h"
#include "ui_helpers/controls/text_field.h"
#include "ui_helpers/controls/text_input_dialog.h"
#include "ui_helpers/controls/world_viewport.h"
#include "ui_manager.h"
#include "uistate.h"

#if defined(TILES)
#include "cata_tiles.h"
#include "sdl_utils.h"
#include "sdltiles.h"
#endif

namespace
{

static const construction_category_id construction_category_ALL( "ALL" );
static const construction_category_id construction_category_FILTER( "FILTER" );

enum class workspace_focus : int {
    palette,
    viewport,
    inspector
};

struct construction_build_order {
    construction_id id = construction_id( -1 );
    tripoint_bub_ms target;
};

static std::string construction_result_name( const construction &con )
{
    if( con.post_terrain.empty() ) {
        return _( "Special construction operation" );
    }
    return con.post_is_furniture ? furn_str_id( con.post_terrain )->name() :
           ter_str_id( con.post_terrain )->name();
}

static std::string construction_result_description( const construction &con )
{
    if( con.post_terrain.empty() ) {
        return con.pre_note.empty() ? std::string() : con.pre_note.translated();
    }
    return con.post_is_furniture ? furn_str_id( con.post_terrain )->description.translated() :
           ter_str_id( con.post_terrain )->description.translated();
}

class construction_workspace
{
    public:
        construction_workspace();
        bool run();

    private:
        void create_layout( ui_adaptor &ui );
        void draw( ui_adaptor &ui );
        void draw_header();
        void draw_palette();
        void draw_inspector();
        void draw_footer();
        void draw_world_overlay() const;
        void rebuild_palette();
        void rebuild_inspector();
        void refresh_active_target();
        void set_focus( workspace_focus next, ui_adaptor &ui );
        void edit_search();
        void open_category_menu();
        void open_context_menu( const point &anchor, const tripoint_bub_ms &target );
        bool execute_context_action( const std::string &id );
        bool request_build( const tripoint_bub_ms &target );
        bool handle_input( const std::string &action, input_context &context, ui_adaptor &ui );
        bool handle_pointer( const std::string &action, input_context &context, ui_adaptor &ui );
        void zoom_view( int direction, const input_context *context = nullptr,
                        const std::optional<tripoint_bub_ms> &anchor = std::nullopt );
        bool target_is_adjacent( const tripoint_bub_ms &target ) const;
        std::optional<tripoint_bub_ms> pointer_world( const input_context &context,
                const std::optional<point> &screen_pos ) const;
        std::optional<tripoint_bub_ms> displayed_target() const;
        const construction *resolved_construction() const;
        std::string category_label() const;
        std::string footer_status() const;

        avatar &you;
        map &here;
        const int original_zoom;

        catacurses::window header;
        catacurses::window palette_window;
        catacurses::window inspector_window;
        catacurses::window footer;

        ui_action_strip header_actions;
        ui_action_strip palette_actions;
        ui_action_strip primary_action;
        ui_text_field search_field;
        ui_selection_list palette;
        ui_scroll_view inspector;
        ui_dropdown category_menu;
        ui_dropdown context_menu;
        ui_world_viewport viewport;

        workspace_focus focus = workspace_focus::palette;
        construction_category_id category = construction_category_ALL;
        construction_group_str_id selected_group = construction_group_str_id::NULL_ID();
        std::vector<construction_group_str_id> visible_groups;
        std::string search;
        std::string transient_status;
        bool show_unavailable = true;
        bool compact = false;
        bool palette_visible = true;
        bool inspector_visible = true;
        bool exit_requested = false;
        bool blink = true;

        int palette_width = 0;
        int inspector_width = 0;
        int content_top = 3;
        int content_bottom = 0;

        std::optional<tripoint_bub_ms> hovered_target;
        std::optional<tripoint_bub_ms> selected_target;
        std::optional<tripoint_bub_ms> context_target;
        std::optional<tripoint_bub_ms> pan_anchor;
        construction_target_resolution resolution;
        std::vector<std::string> inspector_lines;
        std::optional<construction_build_order> build_order;
};

construction_workspace::construction_workspace() :
    you( get_avatar() ), here( get_map() ), original_zoom( g->get_zoom() )
{
    search = uistate.construction_filter;
    if( uistate.construction_tab.is_valid() &&
        uistate.construction_tab != construction_category_FILTER ) {
        category = uistate.construction_tab;
    }
    if( uistate.last_construction.is_valid() ) {
        selected_group = uistate.last_construction;
    }
    palette.hover_previews( false );
    rebuild_palette();
    refresh_active_target();
}

bool construction_workspace::target_is_adjacent( const tripoint_bub_ms &target ) const
{
    return target.z() == you.pos_bub().z() && target != you.pos_bub() &&
           square_dist( target.raw(), you.pos_bub().raw() ) <= 1;
}

std::optional<tripoint_bub_ms> construction_workspace::displayed_target() const
{
    return hovered_target ? hovered_target : selected_target;
}

const construction *construction_workspace::resolved_construction() const
{
    return resolution.id.is_valid() ? &resolution.id.obj() : nullptr;
}

std::string construction_workspace::category_label() const
{
    return category.is_valid() ? category->name() : _( "All" );
}

void construction_workspace::rebuild_palette()
{
    visible_groups.clear();
    std::set<construction_group_str_id> seen;
    std::map<construction_group_str_id, bool> currently_available;
    for( const construction &con : get_constructions() ) {
        if( !con.on_display || !seen.insert( con.group ).second ) {
            continue;
        }
        bool available = false;
        for( const construction *candidate : constructions_by_group( con.group ) ) {
            if( candidate && player_can_build( you, you.crafting_inventory(), *candidate, true ) ) {
                available = true;
                break;
            }
        }
        currently_available[con.group] = available;
        if( !show_unavailable && !available ) {
            continue;
        }
        const std::vector<construction *> variants = constructions_by_group( con.group );
        const construction &representative = *variants.front();
        const std::string category_name = representative.category.is_valid() ?
                                          representative.category->name() : std::string();
        const bool category_matches = category == construction_category_ALL ||
                                      representative.category == category;
        const bool result_matches = std::any_of( variants.begin(), variants.end(),
        [&]( const construction * variant ) {
            return variant != nullptr && lcmatch( construction_result_name( *variant ), search );
        } );
        const bool search_matches = search.empty() || lcmatch( con.group->name(), search ) ||
                                    lcmatch( category_name, search ) || result_matches;
        if( category_matches && search_matches ) {
            visible_groups.push_back( con.group );
        }
    }

    std::vector<ui_action_entry> entries;
    entries.reserve( visible_groups.size() );
    for( const construction_group_str_id &group : visible_groups ) {
        ui_action_entry entry( group->name(), group.str(), true, group == selected_group );
        if( currently_available[group] ) {
            entry.tone = ui_action_tone::positive;
        }
        entries.push_back( std::move( entry ) );
    }
    palette.set_entries( std::move( entries ), false );
    const auto selected = std::find( visible_groups.begin(), visible_groups.end(), selected_group );
    if( selected != visible_groups.end() ) {
        palette.select_only( static_cast<int>( selected - visible_groups.begin() ) );
    } else {
        palette.clear_selection();
    }
}

void construction_workspace::refresh_active_target()
{
    const std::optional<tripoint_bub_ms> target = displayed_target();
    resolution = target ? resolve_construction_target( you, you.crafting_inventory(), selected_group,
        *target ) : construction_target_resolution();
    rebuild_inspector();
}

void construction_workspace::rebuild_inspector()
{
    inspector_lines.clear();
    const int wrap_width = std::max( 8, inspector_width - 4 );
    const auto add = [&]( const std::string & line ) {
        const std::vector<std::string> folded = foldstring( line, wrap_width );
        inspector_lines.insert( inspector_lines.end(), folded.begin(), folded.end() );
    };
    const auto blank = [&]() {
        inspector_lines.emplace_back();
    };

    if( selected_group.is_null() ) {
        add( colorize( _( "Select a construction" ), c_light_green ) );
        blank();
        add( _( "Choose the desired result from the palette, then inspect a tile in the world viewport." ) );
        inspector.model().scroll_to_start();
        return;
    }

    add( colorize( selected_group->name(), c_light_green ) );
    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        blank();
        add( colorize( _( "Target" ), c_light_gray ) );
        add( _( "Hover or select a world tile." ) );
        inspector.model().scroll_to_start();
        return;
    }

    blank();
    add( colorize( _( "Target" ), c_light_gray ) );
    const std::string existing = here.has_furn( *target ) ? here.furn( *target )->name() :
                                 here.ter( *target )->name();
    add( string_format( "%s  (%d, %d, %d)", existing, target->x(), target->y(), target->z() ) );

    const nc_color status_color = resolution.status == construction_target_status::ready ?
                                  c_light_green :
                                  resolution.status == construction_target_status::unavailable_requirements ?
                                  c_yellow : resolution.status == construction_target_status::in_progress ?
                                  c_light_blue : c_light_red;
    blank();
    add( colorize( _( "Status" ), c_light_gray ) );
    add( colorize( resolution.reason, status_color ) );

    const construction *con = resolved_construction();
    if( con == nullptr ) {
        inspector.model().scroll_to_start();
        return;
    }

    blank();
    add( colorize( _( "Result" ), c_light_gray ) );
    add( construction_result_name( *con ) );
    const std::string description = construction_result_description( *con );
    if( !description.empty() ) {
        add( description );
    }

    blank();
    const std::vector<std::string> time = con->get_folded_time_string( wrap_width );
    inspector_lines.insert( inspector_lines.end(), time.begin(), time.end() );

    blank();
    add( colorize( _( "Skills" ), c_light_gray ) );
    if( con->required_skills.empty() ) {
        add( _( "None" ) );
    } else {
        for( const std::pair<const skill_id, int> &skill : con->required_skills ) {
            const int have = you.get_skill_level( skill.first );
            const nc_color color = have >= skill.second ? c_light_green : c_light_red;
            add( colorize( string_format( "%s  %d / %d", skill.first->name(), have, skill.second ), color ) );
        }
    }

    con->requirements->can_make_with_inventory( you.crafting_inventory(), is_crafting_component, 1,
            craft_flags::none, false );
    blank();
    const std::vector<std::string> tools = con->requirements->get_folded_tools_list(
            wrap_width, c_light_gray, you.crafting_inventory() );
    inspector_lines.insert( inspector_lines.end(), tools.begin(), tools.end() );
    blank();
    const std::vector<std::string> components = con->requirements->get_folded_components_list(
            wrap_width, c_light_gray, you.crafting_inventory(), is_crafting_component );
    inspector_lines.insert( inspector_lines.end(), components.begin(), components.end() );
    inspector.model().set_content_size( static_cast<int>( inspector_lines.size() ) );
}

void construction_workspace::create_layout( ui_adaptor &ui )
{
    const int width = TERMX;
    const int height = TERMY;
    content_bottom = std::max( content_top, height - 4 );
    compact = width < 104;
    palette_visible = !compact || focus == workspace_focus::palette;
    inspector_visible = !compact || focus == workspace_focus::inspector;

    palette_width = palette_visible ? std::min( compact ? 34 : 38,
        std::max( 24, width / 4 ) ) : 0;
    inspector_width = inspector_visible ? std::min( compact ? 40 : 46,
        std::max( 28, width / 4 ) ) : 0;
    const int content_height = std::max( 1, content_bottom - content_top + 1 );

    header = catacurses::newwin( 3, width, point::zero );
    footer = catacurses::newwin( 3, width, point( 0, std::max( 0, height - 3 ) ) );
    palette_window = palette_visible ? catacurses::newwin( content_height, palette_width,
        point( 0, content_top ) ) : catacurses::window();
    inspector_window = inspector_visible ? catacurses::newwin( content_height, inspector_width,
        point( std::max( 0, width - inspector_width ), content_top ) ) : catacurses::window();

    const int viewport_left = palette_width;
    const int viewport_right = std::max( viewport_left, width - inspector_width - 1 );
    viewport.configure( inclusive_rectangle<point>( point( viewport_left, content_top ),
            point( viewport_right, content_bottom ) ) );
    ui.position_from_window( catacurses::stdscr );
    rebuild_inspector();
}

void construction_workspace::draw_header()
{
    werase( header );
    draw_border( header, c_light_gray );
    trim_and_print( header, point( 2, 1 ), 14, c_light_green, _( "Construction" ) );

    std::vector<ui_action_strip_item> actions = {
        {
            ui_action_entry( _( "Build" ), "MODE_BUILD", true, true ), 0,
            ui_action_alignment::left
        },
        {
            ui_action_entry( _( "Plan" ), "MODE_PLAN", false, false,
                             _( "Persistent construction plans are not implemented in this UI pass." ) ), 0,
            ui_action_alignment::left
        },
        {
            ui_action_entry( _( "Plans" ), "MODE_PLANS", false, false,
                             _( "Plan management requires the construction-plan backend." ) ), 0,
            ui_action_alignment::left
        }
    };
    if( compact ) {
        actions.push_back( { ui_action_entry( _( "Palette" ), "FOCUS_PALETTE", true,
                                              focus == workspace_focus::palette ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Map" ), "FOCUS_VIEWPORT", true,
                                              focus == workspace_focus::viewport ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Inspector" ), "FOCUS_INSPECTOR", true,
                                              focus == workspace_focus::inspector ), 1,
                             ui_action_alignment::left } );
    }
    actions.push_back( { ui_action_entry( _( "Back" ), "BACK" ), 2,
                         ui_action_alignment::right } );
    header_actions.configure( header, point( 17, 1 ), std::move( actions ),
                              std::max( 1, getmaxx( header ) - 19 ), 1 );
    header_actions.draw( header );
    const int viewport_left = palette_width;
    const int viewport_width = TERMX - palette_width - inspector_width;
    if( viewport_width > 12 ) {
        trim_and_print( header, point( viewport_left + 2, 2 ), viewport_width - 4,
                        focus == workspace_focus::viewport ? c_light_cyan : c_dark_gray,
                        _( " World viewport " ) );
    }
    wnoutrefresh( header );
}

void construction_workspace::draw_palette()
{
    if( !palette_window ) {
        palette.invalidate_geometry();
        return;
    }
    werase( palette_window );
    draw_border( palette_window, focus == workspace_focus::palette ? c_light_cyan : c_light_gray );
    trim_and_print( palette_window, point( 2, 0 ), std::max( 1, palette_width - 4 ),
                    c_light_green, _( " Constructions " ) );
    search_field.configure( palette_window, point( 2, 2 ), palette_width - 4,
                            _( "Search: " ), search, _( "name or result" ), true );
    search_field.draw( palette_window );

    palette_actions.configure( palette_window, point( 2, 4 ), {
        ui_action_entry( string_format( _( "Category: %s" ), category_label() ),
                         "CATEGORY", true, category_menu.is_open(), std::string(), std::nullopt, true ),
        ui_action_entry( _( "Unavailable" ), "SHOW_UNAVAILABLE", true, false,
                         std::string(), show_unavailable )
    }, palette_width - 4, 2 );
    palette_actions.draw( palette_window );
    const int list_y = 7;
    palette.draw( palette_window, point( 2, list_y ), palette_width - 4,
                  std::max( 1, getmaxy( palette_window ) - list_y - 2 ) );
    if( visible_groups.empty() ) {
        trim_and_print( palette_window, point( 2, list_y ), palette_width - 4, c_dark_gray,
                        _( "No constructions match." ) );
    }
    wnoutrefresh( palette_window );
}

void construction_workspace::draw_inspector()
{
    if( !inspector_window ) {
        inspector.hide();
        return;
    }
    werase( inspector_window );
    draw_border( inspector_window, focus == workspace_focus::inspector ? c_light_cyan : c_light_gray );
    trim_and_print( inspector_window, point( 2, 0 ), std::max( 1, inspector_width - 4 ),
                    c_light_green, _( " Inspector " ) );

    const int action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int content_height = std::max( 1, action_y - 2 );
    inspector.configure( point( 2, 1 ), std::max( 2, inspector_width - 4 ), content_height,
                         static_cast<int>( inspector_lines.size() ) );
    for( int line = 0; line < static_cast<int>( inspector_lines.size() ); ++line ) {
        const std::optional<point> pos = inspector.position( line );
        if( pos ) {
            nc_color current = c_light_gray;
            print_colored_text( inspector_window, *pos, current, c_light_gray, inspector_lines[line] );
        }
    }
    inspector.draw_scrollbar( inspector_window );

    ui_action_entry build( _( "Select a target" ), "BUILD", false, false,
                           _( "Select a construction and a world tile first." ) );
    if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
        if( resolution.status == construction_target_status::in_progress ) {
            build.label = _( "Continue" );
            build.disabled_reason = _( "Continue unfinished construction by examining it in the world." );
        } else if( !target_is_adjacent( *target ) ) {
            build.label = _( "Go there and build" );
            build.disabled_reason = _( "Distant build orders are planned for the next construction pass." );
        } else {
            build.label = _( "Build here" );
            build.enabled = resolution.ready();
            build.disabled_reason = resolution.reason;
        }
    }
    build.tone = ui_action_tone::positive;
    primary_action.configure( inspector_window, point( 2, action_y ), { build },
                              inspector_width - 4, 1 );
    primary_action.draw( inspector_window );
    wnoutrefresh( inspector_window );
}

std::string construction_workspace::footer_status() const
{
    if( !transient_status.empty() ) {
        return transient_status;
    }
    if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
        return string_format( _( "Target: %d, %d  •  %s" ), target->x(), target->y(),
                              resolution.reason );
    }
    return _( "LMB select  •  MMB drag/pan  •  Wheel zoom  •  RMB context  •  Tab change focus" );
}

void construction_workspace::draw_footer()
{
    werase( footer );
    draw_border( footer, c_light_gray );
    trim_and_print( footer, point( 2, 1 ), std::max( 1, getmaxx( footer ) - 16 ),
                    transient_status.empty() ? c_light_gray : c_yellow, footer_status() );
    trim_and_print( footer, point( std::max( 2, getmaxx( footer ) - 13 ), 1 ), 11, c_light_cyan,
                    string_format( _( "Zoom %d%%" ), g->get_zoom() * 100 / DEFAULT_TILESET_ZOOM ) );
    wnoutrefresh( footer );
}

void construction_workspace::draw_world_overlay() const
{
    const std::optional<tripoint_bub_ms> target = displayed_target();
    if( !target ) {
        return;
    }
    const construction *con = resolved_construction();
    if( con && !con->post_terrain.empty() && blink ) {
        if( con->post_is_furniture ) {
            g->draw_furniture_override( *target, furn_str_id( con->post_terrain ) );
        } else {
            g->draw_terrain_override( *target, ter_str_id( con->post_terrain ) );
        }
    }
#if defined(TILES)
    g->draw_highlight( *target );
#else
    here.drawsq( g->w_terrain, *target,
                 drawsq_params().highlight( true ).show_items( true )
                 .center( you.pos_bub() + you.view_offset ) );
#endif
    if( selected_target ) {
        g->draw_cursor_unobscuring( *selected_target );
    }
}

void construction_workspace::draw( ui_adaptor &ui )
{
    draw_header();
    draw_palette();
    draw_inspector();
    draw_footer();
    ui.disable_cursor();
    if( category_menu.is_open() && palette_window ) {
        category_menu.draw( palette_window );
    }
    if( context_menu.is_open() ) {
        context_menu.draw( catacurses::stdscr );
    }
}

void construction_workspace::set_focus( const workspace_focus next, ui_adaptor &ui )
{
    if( focus == next ) {
        return;
    }
    focus = next;
    transient_status.clear();
    if( compact ) {
        ui.mark_resize();
    }
}

void construction_workspace::edit_search()
{
    const std::optional<std::string> edited = ui_query_text_input_dialog(
            _( "Search constructions" ), _( "Search" ), search, 30, 100 );
    if( edited ) {
        search = *edited;
        uistate.construction_filter = search;
        rebuild_palette();
    }
}

void construction_workspace::open_category_menu()
{
    if( !palette_window ) {
        return;
    }
    std::vector<ui_dropdown_entry> entries;
    entries.emplace_back( _( "All categories" ), construction_category_ALL.str(), true,
                          category == construction_category_ALL );
    for( const construction_category &candidate : construction_categories::get_all() ) {
        if( candidate.id == construction_category_ALL || candidate.id == construction_category_FILTER ) {
            continue;
        }
        entries.emplace_back( candidate.name(), candidate.id.str(), true, candidate.id == category );
    }
    category_menu.configure( palette_window, point( 2, 6 ), std::move( entries ),
                             std::max( 16, palette_width - 4 ) );
    category_menu.focus_selected();
}

void construction_workspace::open_context_menu( const point &anchor,
        const tripoint_bub_ms &target )
{
    context_target = target;
    const construction_target_resolution target_resolution = resolve_construction_target(
            you, you.crafting_inventory(), selected_group, target );
    const bool adjacent = target_is_adjacent( target );
    const bool buildable = target_resolution.ready() && adjacent;
    std::string build_reason = target_resolution.reason;
    std::string build_label = _( "Build here" );
    if( !adjacent ) {
        build_label = _( "Go there and build" );
        build_reason = _( "Distant build orders are not implemented yet." );
    }
    std::vector<ui_dropdown_entry> entries = {
        ui_dropdown_entry( _( "Select tile" ), "SELECT_TILE" ),
        ui_dropdown_entry( build_label, "BUILD", buildable, false, build_reason ),
        ui_dropdown_entry( _( "Center view here" ), "CENTER" ),
        ui_dropdown_entry( _( "Clear selection" ), "CLEAR", selected_target.has_value() )
    };
    context_menu.configure( catacurses::stdscr, anchor, std::move( entries ) );
}

bool construction_workspace::execute_context_action( const std::string &id )
{
    if( !context_target ) {
        return false;
    }
    if( id == "SELECT_TILE" ) {
        selected_target = context_target;
        hovered_target.reset();
        refresh_active_target();
    } else if( id == "BUILD" ) {
        return request_build( *context_target );
    } else if( id == "CENTER" ) {
        you.view_offset = *context_target - you.pos_bub();
        g->normalize_map_camera();
        g->invalidate_main_ui_adaptor();
    } else if( id == "CLEAR" ) {
        selected_target.reset();
        refresh_active_target();
    }
    return false;
}

bool construction_workspace::request_build( const tripoint_bub_ms &target )
{
    const construction_target_resolution current = resolve_construction_target(
            you, you.crafting_inventory(), selected_group, target );
    if( !target_is_adjacent( target ) ) {
        transient_status = _( "Distant build orders are not implemented yet." );
        return false;
    }
    if( !current.ready() ) {
        transient_status = current.reason;
        return false;
    }
    if( !g->warn_player_maybe_anger_local_faction( true ) ) {
        transient_status = _( "Construction canceled." );
        return false;
    }
    build_order = construction_build_order{ current.id, target };
    exit_requested = true;
    return true;
}

std::optional<tripoint_bub_ms> construction_workspace::pointer_world(
    const input_context &context, const std::optional<point> &screen_pos ) const
{
    if( !viewport.contains( screen_pos ) ) {
        return std::nullopt;
    }
    const std::optional<tripoint_bub_ms> world = context.get_coordinates(
            g->w_terrain, g->ter_view_p.raw().xy(), true );
    return world && world->z() == you.pos_bub().z() ? world : std::nullopt;
}

void construction_workspace::zoom_view( const int direction, const input_context *context,
                                        const std::optional<tripoint_bub_ms> &anchor )
{
    const int old_zoom = g->get_zoom();
    const int next = std::clamp( direction > 0 ? old_zoom * 2 : old_zoom / 2,
                                 MINIMUM_TILESET_ZOOM, MAXIMUM_TILESET_ZOOM );
    g->set_zoom( next );
    if( context != nullptr && anchor && next != old_zoom ) {
        const std::optional<tripoint_bub_ms> after = context->get_coordinates(
                g->w_terrain, g->ter_view_p.raw().xy(), true );
        if( after ) {
            you.view_offset += *anchor - *after;
            g->normalize_map_camera();
        }
    }
    g->invalidate_main_ui_adaptor();
}

bool construction_workspace::handle_pointer( const std::string &action,
        input_context &context, ui_adaptor &ui )
{
    const std::optional<point> screen_pos = context.get_coordinates_text( catacurses::stdscr );
    const std::optional<point> header_pos = header ? context.get_coordinates_text(
            header ) : std::nullopt;
    const std::optional<point> palette_pos = palette_window ?
        context.get_coordinates_text( palette_window ) : std::nullopt;
    const std::optional<point> inspector_pos = inspector_window ?
        context.get_coordinates_text( inspector_window ) : std::nullopt;

    // Hover is transient preview state.  Crossing into a panel immediately
    // restores the explicitly selected target instead of leaving a stale map
    // tile active beneath buttons or list rows.
    if( action == "MOUSE_MOVE" && !viewport.contains( screen_pos ) && hovered_target ) {
        hovered_target.reset();
        refresh_active_target();
    }

    // A captured map drag owns every pointer event through release, even when
    // the pointer crosses a panel.  Route it before dropdowns and controls so
    // releasing or clicking over another surface cannot activate that surface.
    if( viewport.has_capture() ) {
        const ui_world_viewport_action captured_action = viewport.handle_input( action, screen_pos );
        const std::optional<tripoint_bub_ms> world = context.get_coordinates(
                g->w_terrain, g->ter_view_p.raw().xy(), true );
        if( captured_action.type == ui_world_viewport_action_type::pan_move ) {
            if( pan_anchor && world ) {
                you.view_offset += *pan_anchor - *world;
                g->normalize_map_camera();
                g->invalidate_main_ui_adaptor();
                pan_anchor = context.get_coordinates( g->w_terrain, g->ter_view_p.raw().xy(), true );
            }
        } else if( captured_action.type == ui_world_viewport_action_type::pan_end ) {
            pan_anchor.reset();
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
        }
        return captured_action.consumed();
    }

    if( category_menu.is_open() ) {
        std::optional<inclusive_rectangle<point>> trigger;
        if( const auto bounds = palette_actions.bounds_for_id( "CATEGORY" ) ) {
            trigger.emplace( bounds->p_min, bounds->p_max );
        }
        const ui_action_result result = category_menu.handle_input(
                                            action, palette_pos, true,
                                            ui_outside_click_policy::passthrough, trigger, &context );
        if( result.type == ui_action_result_type::activated && result.entry ) {
            category = construction_category_id( result.entry->id );
            uistate.construction_tab = category;
            rebuild_palette();
            transient_status.clear();
            return true;
        }
        if( result.type == ui_action_result_type::disabled && result.entry ) {
            transient_status = result.entry->disabled_reason;
        }
        if( result.consumed() ) {
            return true;
        }
    }

    if( context_menu.is_open() ) {
        const ui_action_result result = context_menu.handle_input(
                                            action, screen_pos, true,
                                            ui_outside_click_policy::passthrough, std::nullopt, &context );
        if( result.type == ui_action_result_type::activated && result.entry ) {
            execute_context_action( result.entry->id );
            return true;
        }
        if( result.type == ui_action_result_type::disabled && result.entry ) {
            transient_status = result.entry->disabled_reason;
            return true;
        }
        if( result.consumed() ) {
            return true;
        }
    }

    if( palette.has_capture() ) {
        return palette.handle_input( action, context, palette_pos ).consumed();
    }
    if( inspector.has_capture() && inspector.handle_input( action, context, inspector_pos ) ) {
        return true;
    }

    const ui_action_result header_result = header_actions.handle_pointer_input( action, header_pos );
    if( header_result.type == ui_action_result_type::disabled && header_result.entry ) {
        transient_status = header_result.entry->disabled_reason;
        return true;
    }
    if( header_result.type == ui_action_result_type::activated && header_result.entry ) {
        const std::string &id = header_result.entry->id;
        if( id == "BACK" ) {
            exit_requested = true;
        } else if( id == "FOCUS_PALETTE" ) {
            set_focus( workspace_focus::palette, ui );
        } else if( id == "FOCUS_VIEWPORT" ) {
            set_focus( workspace_focus::viewport, ui );
        } else if( id == "FOCUS_INSPECTOR" ) {
            set_focus( workspace_focus::inspector, ui );
        }
        return true;
    }

    if( palette_window ) {
        const ui_action_result palette_action = palette_actions.handle_pointer_input( action, palette_pos );
        if( palette_action.type == ui_action_result_type::activated && palette_action.entry ) {
            if( palette_action.entry->id == "CATEGORY" ) {
                open_category_menu();
            } else if( palette_action.entry->id == "SHOW_UNAVAILABLE" ) {
                show_unavailable = !show_unavailable;
                rebuild_palette();
            }
            set_focus( workspace_focus::palette, ui );
            return true;
        }
        if( action == "SELECT" && palette_pos ) {
            const ui_text_field_hit hit = search_field.hit_test( *palette_pos );
            if( hit == ui_text_field_hit::clear ) {
                search.clear();
                uistate.construction_filter.clear();
                rebuild_palette();
                return true;
            }
            if( hit == ui_text_field_hit::edit ) {
                edit_search();
                return true;
            }
        }
        const ui_action_result list_result = palette.handle_input( action, context, palette_pos );
        if( list_result.entry && ( list_result.type == ui_action_result_type::handled ||
                                   list_result.type == ui_action_result_type::activated ) ) {
            selected_group = construction_group_str_id( list_result.entry->id );
            uistate.last_construction = selected_group;
            refresh_active_target();
            set_focus( workspace_focus::palette, ui );
            return true;
        }
        if( list_result.consumed() ) {
            return true;
        }
    }

    if( inspector_window ) {
        const ui_action_result build_result = primary_action.handle_pointer_input( action, inspector_pos );
        if( build_result.type == ui_action_result_type::disabled && build_result.entry ) {
            transient_status = build_result.entry->disabled_reason;
            return true;
        }
        if( build_result.type == ui_action_result_type::activated ) {
            if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
                request_build( *target );
            }
            return true;
        }
        if( inspector.handle_input( action, context, inspector_pos ) ) {
            set_focus( workspace_focus::inspector, ui );
            return true;
        }
    }

    const ui_world_viewport_action viewport_action = viewport.handle_input( action, screen_pos );
    const std::optional<tripoint_bub_ms> world = viewport.has_capture() ?
        context.get_coordinates( g->w_terrain, g->ter_view_p.raw().xy(), true ) :
        pointer_world( context, screen_pos );
    switch( viewport_action.type ) {
        case ui_world_viewport_action_type::hover:
            hovered_target = world;
            refresh_active_target();
            return true;
        case ui_world_viewport_action_type::select:
            if( world ) {
                selected_target = world;
                hovered_target.reset();
                refresh_active_target();
                set_focus( workspace_focus::viewport, ui );
            }
            return true;
        case ui_world_viewport_action_type::context:
            if( world && screen_pos ) {
                open_context_menu( *screen_pos, *world );
                set_focus( workspace_focus::viewport, ui );
            }
            return true;
        case ui_world_viewport_action_type::pan_start:
            pan_anchor = world;
#if defined(TILES)
            set_sdl_mouse_capture( pan_anchor.has_value() );
#endif
            return true;
        case ui_world_viewport_action_type::pan_move:
            if( pan_anchor && world ) {
                you.view_offset += *pan_anchor - *world;
                g->normalize_map_camera();
                g->invalidate_main_ui_adaptor();
                pan_anchor = context.get_coordinates( g->w_terrain, g->ter_view_p.raw().xy(), true );
            }
            return true;
        case ui_world_viewport_action_type::pan_end:
            pan_anchor.reset();
#if defined(TILES)
            set_sdl_mouse_capture( false );
#endif
            return true;
        case ui_world_viewport_action_type::zoom_in:
            zoom_view( 1, &context, world );
            return true;
        case ui_world_viewport_action_type::zoom_out:
            zoom_view( -1, &context, world );
            return true;
        case ui_world_viewport_action_type::handled:
            return true;
        default:
            break;
    }
    return false;
}

bool construction_workspace::handle_input( const std::string &action,
        input_context &context, ui_adaptor &ui )
{
    transient_status.clear();
    if( action == "TIMEOUT" ) {
        blink = !blink;
        g->invalidate_main_ui_adaptor();
        return true;
    }
    blink = true;
    if( action == "MOUSE_MOVE" || action == "SELECT" || action == "SEC_SELECT" ||
        action == "SCROLL_UP" || action == "SCROLL_DOWN" ||
        action == "CLICK_AND_DRAG" || action == "CAMERA_PAN_START" ||
        action == "CAMERA_PAN_END" ) {
        return handle_pointer( action, context, ui );
    }
    if( action == "QUIT" ) {
        if( category_menu.is_open() ) {
            category_menu.close();
        } else if( context_menu.is_open() ) {
            context_menu.close();
        } else {
            exit_requested = true;
        }
        return true;
    }
    if( action == "NEXT_TAB" || action == "PREV_TAB" ) {
        const int direction = action == "NEXT_TAB" ? 1 : -1;
        const int next = ( static_cast<int>( focus ) + direction + 3 ) % 3;
        set_focus( static_cast<workspace_focus>( next ), ui );
        return true;
    }
    if( action == "FILTER" ) {
        edit_search();
        return true;
    }
    if( action == "TOGGLE_UNAVAILABLE_CONSTRUCTIONS" ) {
        show_unavailable = !show_unavailable;
        rebuild_palette();
        return true;
    }
    if( action == "CONSTRUCTION_CENTER" ) {
        you.view_offset = tripoint_rel_ms::zero;
        selected_target = you.pos_bub() + tripoint_rel_ms::east;
        refresh_active_target();
        g->invalidate_main_ui_adaptor();
        return true;
    }
    if( action == "CONSTRUCTION_BUILD" ) {
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            request_build( *target );
        } else {
            transient_status = _( "Select a target first." );
        }
        return true;
    }
    if( action == "zoom_in" || action == "zoom_out" ) {
        zoom_view( action == "zoom_in" ? 1 : -1 );
        return true;
    }

    if( focus == workspace_focus::palette && palette_window ) {
        const ui_action_result result = palette.handle_input( action, context, std::nullopt );
        if( result.entry && ( result.type == ui_action_result_type::handled ||
                              result.type == ui_action_result_type::activated ) ) {
            selected_group = construction_group_str_id( result.entry->id );
            uistate.last_construction = selected_group;
            refresh_active_target();
        }
        return result.consumed();
    }
    if( focus == workspace_focus::inspector && inspector_window &&
        inspector.handle_input( action, context, std::nullopt, true ) ) {
        return true;
    }
    if( focus == workspace_focus::viewport ) {
        const std::optional<tripoint_rel_ms> direction = context.get_direction_rel_ms( action );
        if( direction ) {
            you.view_offset += *direction;
            g->normalize_map_camera();
            selected_target = you.pos_bub() + you.view_offset;
            hovered_target.reset();
            refresh_active_target();
            g->invalidate_main_ui_adaptor();
            return true;
        }
        if( action == "CONFIRM" ) {
            selected_target = you.pos_bub() + you.view_offset;
            hovered_target.reset();
            refresh_active_target();
            return true;
        }
    }
    return false;
}

bool construction_workspace::run()
{
    std::optional<construction_build_order> final_order;
    {
        restore_on_out_of_scope<tripoint_rel_ms> restore_view( you.view_offset );
        on_out_of_scope restore_zoom( [this]() {
            g->set_zoom( original_zoom );
        } );
        on_out_of_scope restore_ui( []() {
#if defined(TILES)
            set_sdl_mouse_capture( false );
            tilecontext->set_disable_occlusion( false );
#endif
            g->invalidate_main_ui_adaptor();
        } );
#if defined(TILES)
        tilecontext->set_disable_occlusion( true );
#endif
        g->invalidate_main_ui_adaptor();

        input_context context( "CONSTRUCTION" );
        context.register_navigate_ui_list();
        context.register_directions();
        for( const char *action : {
                 "NEXT_TAB", "PREV_TAB", "CONFIRM", "QUIT",
                 "HELP_KEYBINDINGS", "FILTER", "TOGGLE_UNAVAILABLE_CONSTRUCTIONS",
                 "CONSTRUCTION_BUILD", "CONSTRUCTION_CENTER", "zoom_in", "zoom_out",
                 "SELECT", "SEC_SELECT", "MOUSE_MOVE", "CLICK_AND_DRAG",
                 "SCROLL_UP", "SCROLL_DOWN", "CAMERA_PAN_START", "CAMERA_PAN_END"
             } ) {
            context.register_action( action );
        }
        context.set_timeout( get_option<int>( "BLINK_SPEED" ) );

        ui_adaptor ui;
        ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
            create_layout( adaptor );
        } );
        ui.mark_resize();
        ui.on_redraw( [&]( ui_adaptor & adaptor ) {
            draw( adaptor );
        } );

        shared_ptr_fast<game::draw_callback_t> overlay =
        make_shared_fast<game::draw_callback_t>( [this]() {
            draw_world_overlay();
        } );
        g->add_draw_callback( overlay );

        while( !exit_requested ) {
            g->invalidate_main_ui_adaptor();
            ui_manager::redraw();
            const std::string action = context.handle_input();
            handle_input( action, context, ui );
        }
        overlay.reset();
        ui.reset();
        final_order = build_order;
    }

    uistate.construction_filter = search;
    uistate.construction_tab = category;
    if( !selected_group.is_null() ) {
        uistate.last_construction = selected_group;
    }
    if( final_order && final_order->id.is_valid() ) {
        const ret_val<void> started = start_construction_at( you, final_order->id.obj(),
            final_order->target );
        if( !started.success() ) {
            add_msg( m_info, started.str() );
        }
    }
    return true;
}

} // namespace

namespace construction_ui
{

bool run()
{
    if( TERMX < 60 || TERMY < 16 ) {
        return false;
    }
    construction_workspace workspace;
    return workspace.run();
}

} // namespace construction_ui
