#include <array>
#include <chrono>
#include <string>

#include "cata_catch.h"
#include "point.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/compass_grid.h"
#include "ui_helpers/controls/selection_panel.h"
#include "ui_helpers/models/double_click_tracker.h"
#include "ui_helpers/models/hit_map.h"
#include "ui_helpers/models/list_selection.h"
#include "ui_helpers/models/multiselect_filter.h"
#include "ui_helpers/models/scroll_model.h"
#include "ui_helpers/models/tree_model.h"

namespace
{
enum class test_filter : int {
    first,
    second,
    third,
    unsupported
};
} // namespace

TEST_CASE( "ui_scroll_model_keeps_selection_independent", "[ui][ui_helpers]" )
{
    ui_scroll_model scroll( 20, 5 );

    scroll.scroll_by( 7 );
    CHECK( scroll.viewport_pos() == 7 );

    scroll.ensure_visible( 2 );
    CHECK( scroll.viewport_pos() == 2 );

    scroll.ensure_visible( 10 );
    CHECK( scroll.viewport_pos() == 6 );

    scroll.scroll_to_end().scroll_by( 20 );
    CHECK( scroll.viewport_pos() == 15 );
}

TEST_CASE( "ui_selection_panel_keeps_back_separate_from_list_confirmation", "[ui][ui_helpers]" )
{
    ui_selection_panel panel;
    input_context context( "TEST_SELECTION_PANEL" );
    panel.list.set_entries( { ui_action_entry( "First", "FIRST", true, true ),
                             ui_action_entry( "Second", "SECOND", true, true ),
                             ui_action_entry( "Unavailable", "DISABLED", false ) } );
    panel.list.set_cursor( 1 );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 0, 1 } );
    const ui_selection_panel_result confirm = panel.handle_input( "CONFIRM", context, std::nullopt );
    CHECK( confirm.from_list );
    CHECK( confirm.action.type == ui_action_result_type::activated );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 0, 1 } );

    const ui_selection_panel_result back = panel.handle_input( "QUIT", context, std::nullopt );
    CHECK_FALSE( back.from_list );
    REQUIRE( back.action.entry );
    CHECK( back.action.entry->id == "BACK" );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 0, 1 } );

    panel.list.set_cursor( 99 );
    CHECK( panel.list.cursor() == 2 );
    CHECK( panel.handle_input( "CONFIRM", context, std::nullopt ).action.type ==
           ui_action_result_type::disabled );
    panel.list.set_entries( {}, false );
    panel.list.set_cursor( -1 );
    CHECK( panel.list.cursor() == 0 );
    CHECK( panel.handle_input( "CONFIRM", context, std::nullopt ).action.type ==
           ui_action_result_type::handled );
    CHECK( panel.handle_input( "QUIT", context, std::nullopt ).action.entry->id == "BACK" );

    panel.list.set_entries( { ui_action_entry( "Old selection", "OLD", true, true ),
                             ui_action_entry( "Focused", "NEW" ) }, false );
    panel.list.set_cursor( 1 );
    CHECK( panel.handle_input( "CONFIRM", context, std::nullopt ).action.entry->id == "NEW" );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 1 } );

    // Group activation expands without committing the previously selected ground.
    panel.list.set_tree_entries( { ui_action_entry( "Ground", "GROUND", true, true ),
                                  ui_action_entry( "You", "YOU" ),
                                  ui_action_entry( "Backpack", "PACK", false ),
                                  ui_action_entry( "Bottle", "BOTTLE" ) },
                                { { -1 }, { -1, false }, { 1 }, { 2 } } );
    panel.list.set_cursor( 1 );
    CHECK( panel.handle_input( "CONFIRM", context, std::nullopt ).action.type ==
           ui_action_result_type::handled );
    CHECK( panel.list.expanded( 1 ) );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 0 } );
    panel.handle_input( "RIGHT", context, std::nullopt );
    CHECK( panel.list.cursor() == 2 );
    panel.handle_input( "RIGHT", context, std::nullopt );
    CHECK( panel.list.expanded( 2 ) );
    panel.handle_input( "DOWN", context, std::nullopt );
    CHECK( panel.list.cursor() == 3 );
    CHECK( panel.handle_input( "CONFIRM", context, std::nullopt ).action.entry->id == "BOTTLE" );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 3 } );
    panel.handle_input( "LEFT", context, std::nullopt );
    panel.handle_input( "LEFT", context, std::nullopt );
    CHECK_FALSE( panel.list.expanded( 2 ) );
    CHECK( panel.list.selected_indices() == std::vector<int>{ 3 } );
}

TEST_CASE( "ui_single_selection_has_one_highlight_with_hover_or_keyboard_focus", "[ui][ui_helpers]" )
{
    // Moving over another row must not steal the clicked row's highlight.
    CHECK( ui_list_highlight( 0, 0, 1, true, false ) == ui_list_row_highlight::selected );
    CHECK( ui_list_highlight( 1, 0, 1, false, false ) == ui_list_row_highlight::none );
    CHECK( ui_list_highlight( 2, 0, 1, false, false ) == ui_list_row_highlight::none );

    // A new click owns the highlight even before the old hover is cleared.
    CHECK( ui_list_highlight( 1, 2, 1, false, false ) == ui_list_row_highlight::none );
    CHECK( ui_list_highlight( 2, 2, 1, true, false ) == ui_list_row_highlight::selected );

    // Keyboard navigation focuses the new row without two highlights.
    CHECK( ui_list_highlight( 1, 2, -1, false, false ) == ui_list_row_highlight::none );
    CHECK( ui_list_highlight( 2, 2, -1, true, false ) == ui_list_row_highlight::selected );
    CHECK( ui_list_highlight( 0, 0, -1, false, false ) == ui_list_row_highlight::focused );
    CHECK( ui_list_highlight( 2, 0, -1, true, false ) == ui_list_row_highlight::none );

    // Multiple deliberate selections (e.g. refuel sources) remain visible.
    CHECK( ui_list_highlight( 0, 0, 1, true, true ) == ui_list_row_highlight::selected );
    CHECK( ui_list_highlight( 1, 0, 1, false, true ) == ui_list_row_highlight::focused );
    CHECK( ui_list_highlight( 2, 0, 1, true, true ) == ui_list_row_highlight::selected );
    CHECK( ui_list_highlight( 0, 0, 1, false, true ) == ui_list_row_highlight::none );
}

TEST_CASE( "ui_tree_model_preserves_nested_branches_and_stable_row_indices", "[ui][ui_helpers]" )
{
    ui_tree_model tree;
    // Ground is an independent leaf; You and the crate are separate roots.
    tree.reset( { { -1 }, { -1, false }, { 1 }, { 2 }, { 3 }, { 1 }, { -1 } } );
    CHECK( tree.visible_indices() == std::vector<int>{ 0, 1, 6 } );
    CHECK_FALSE( tree.expandable( 0 ) );
    CHECK_FALSE( tree.selectable( 1 ) );
    CHECK( tree.depth( 4 ) == 3 );
    CHECK( tree.set_expanded( 1, true ) );
    CHECK( tree.visible_indices() == std::vector<int>{ 0, 1, 2, 5, 6 } );
    tree.set_expanded( 2, true );
    tree.set_expanded( 3, true );
    CHECK( tree.visible_position( 4 ) == 4 );
    tree.set_expanded( 1, false );
    CHECK( tree.visible_position( 4 ) == -1 );
    CHECK( tree.visible_ancestor( 4 ) == 1 );
    CHECK( tree.expanded( 2 ) );
    tree.reveal( 4 );
    CHECK( tree.visible_indices() == std::vector<int>{ 0, 1, 2, 3, 4, 5, 6 } );
    CHECK( tree.index_at( 4 ) == 4 );

    SECTION( "invalid parents cannot create cycles" ) {
        tree.reset( { { 1 }, { 1 }, { 99 }, { -2 } } );
        CHECK( tree.visible_indices() == std::vector<int>{ 0, 1, 2, 3 } );
        CHECK( tree.parent( 0 ) == -1 );
        CHECK( tree.parent( 1 ) == -1 );
        CHECK_FALSE( tree.set_expanded( -1, true ) );
        CHECK( tree.index_at( 99 ) == -1 );
    }
    SECTION( "deep nesting does not impose a UI depth limit" ) {
        std::vector<ui_tree_node> nodes( 100 );
        for( int i = 1; i < 100; ++i ) {
            nodes[i].parent = i - 1;
        }
        tree.reset( nodes );
        tree.reveal( 99 );
        CHECK( tree.visible_indices().size() == 100 );
        CHECK( tree.depth( 99 ) == 99 );
        tree.set_expanded( 0, false );
        CHECK( tree.visible_indices() == std::vector<int>{ 0 } );
        tree.set_expanded( 0, true );
        CHECK( tree.visible_position( 99 ) == 99 );
    }
}

TEST_CASE( "ui_selection_list_tree_expansion_does_not_change_destination", "[ui][ui_helpers]" )
{
    ui_selection_list list;
    list.set_tree_entries( { ui_action_entry( "Ground", "GROUND" ),
                            ui_action_entry( "You", "YOU" ),
                            ui_action_entry( "Backpack", "PACK", false ),
                            ui_action_entry( "Bottle", "BOTTLE", true, true ),
                            ui_action_entry( "Crate", "CRATE" ) },
                          { { -1 }, { -1, false }, { 1 }, { 2 }, { -1 } } );
    CHECK( list.visible_indices() == std::vector<int>{ 0, 1, 2, 3, 4 } );
    CHECK( list.selected_indices() == std::vector<int>{ 3 } );
    CHECK( list.cursor() == 3 );
    list.set_expanded( 1, false );
    CHECK( list.visible_indices() == std::vector<int>{ 0, 1, 4 } );
    CHECK( list.selected_indices() == std::vector<int>{ 3 } );
    CHECK( list.cursor() == 1 );
    list.set_selected( 1, true );
    list.set_selected( 2, true );
    CHECK( list.selected_indices() == std::vector<int>{ 3 } );
    list.set_expanded( 1, true );
    CHECK( list.expanded( 2 ) );
    CHECK( list.selected_indices() == std::vector<int>{ 3 } );
    list.select_only( 4 );
    CHECK( list.selected_indices() == std::vector<int>{ 4 } );

    // Reusing the helper for a flat picker clears all hierarchy state.
    list.set_entries( { ui_action_entry( "First", "FIRST" ), ui_action_entry( "Second", "SECOND" ) } );
    CHECK( list.visible_indices() == std::vector<int>{ 0, 1 } );
    CHECK( list.selected_indices().empty() );
    CHECK_FALSE( list.expanded( 1 ) );
    list.select_all();
    CHECK( list.selected_indices() == std::vector<int>{ 0, 1 } );
}

TEST_CASE( "ui_compass_grid_routes_spatial_actions_and_blocks_obstacles", "[ui][ui_helpers]" )
{
    ui_compass_grid grid;
    std::array<ui_compass_entry, 9> entries;
    for( int i = 0; i < 9; ++i ) {
        entries[i].action = ui_action_entry( "tile", std::to_string( i ) );
    }
    entries[0].blocked = true;
    entries[2].action.enabled = false;
    entries[5].dangerous = true;
    grid.set_entries( entries );

    CHECK( ui_compass_grid::offset( 0 ).x == -1 );
    CHECK( ui_compass_grid::offset( 0 ).y == -1 );
    CHECK( ui_compass_grid::offset( 4 ).x == 0 );
    CHECK( ui_compass_grid::offset( 4 ).y == 0 );
    CHECK( ui_compass_grid::offset( 5 ).x == 1 );
    CHECK( ui_compass_grid::offset( 5 ).y == 0 );
    CHECK( ui_compass_grid::offset( 8 ).x == 1 );
    CHECK( ui_compass_grid::offset( 8 ).y == 1 );
    CHECK( grid.handle_input( "0", std::nullopt ).type == ui_action_result_type::disabled );
    CHECK( grid.handle_input( "2", std::nullopt ).type == ui_action_result_type::disabled );
    CHECK( grid.handle_input( "5", std::nullopt ).type == ui_action_result_type::activated );
    CHECK( grid.handle_input( "CONFIRM", std::nullopt ).type == ui_action_result_type::ignored );
    grid.clear();
    CHECK( grid.handle_input( "5", std::nullopt ).type == ui_action_result_type::ignored );
}

TEST_CASE( "ui_list_selection_preserves_batch_on_double_click", "[ui][ui_helpers]" )
{
    using namespace std::chrono_literals;
    ui_list_selection selection;
    std::vector<bool> selected( 4, false );
    const auto enabled = []( int ) { return true; };
    const ui_list_selection::time_point now;
    CHECK_FALSE( selection.click( selected, 0, enabled, false, false, now ) );
    CHECK_FALSE( selection.click( selected, 2, enabled, true, false, now + 100ms ) );
    CHECK_FALSE( selection.click( selected, 0, enabled, false, false, now + 200ms ) );
    CHECK( selection.click( selected, 0, enabled, false, false, now + 300ms ) );
    CHECK( selected == std::vector<bool>{ true, false, true, false } );
    // A modifier click never forms half of a double-click.
    CHECK_FALSE( selection.click( selected, 0, enabled, true, false, now + 400ms ) );
    CHECK_FALSE( selection.click( selected, 0, enabled, false, false, now + 500ms ) );
}

TEST_CASE( "ui_list_selection_requires_two_clicks_on_the_same_destination", "[ui][ui_helpers]" )
{
    using namespace std::chrono_literals;
    ui_list_selection selection;
    std::vector<bool> selected( 2, false );
    const auto enabled = []( int ) { return true; };
    const ui_list_selection::time_point now;
    // Hover previews without selecting; a click then keeps its own highlight.
    CHECK( ui_list_cursor_after_hover( 0, 1, selected, false ) == 1 );
    CHECK( selected == std::vector<bool>{ false, false } );
    CHECK_FALSE( selection.click( selected, 0, enabled, false, false, now ) );
    CHECK( selected == std::vector<bool>{ true, false } );
    int cursor = ui_list_cursor_after_hover( 0, 1, selected, false );
    CHECK( cursor == 0 );
    CHECK( ui_list_highlight( 0, cursor, 1, selected[0], false ) ==
           ui_list_row_highlight::selected );
    CHECK( ui_list_highlight( 1, cursor, 1, selected[1], false ) == ui_list_row_highlight::none );

    CHECK_FALSE( selection.click( selected, 1, enabled, false, false, now + 100ms ) );
    CHECK( selected == std::vector<bool>{ false, true } );
    cursor = ui_list_cursor_after_hover( 1, 0, selected, false );
    CHECK( cursor == 1 );
    CHECK( ui_list_highlight( 0, cursor, 0, selected[0], false ) == ui_list_row_highlight::none );
    CHECK( ui_list_highlight( 1, cursor, 0, selected[1], false ) ==
           ui_list_row_highlight::selected );
    // Leaving the list for Use selected preserves the same candidate and focus.
    CHECK( ui_list_cursor_after_hover( cursor, -1, selected, false ) == cursor );
    CHECK( selected == std::vector<bool>{ false, true } );
    CHECK( selection.click( selected, 1, enabled, false, false, now + 200ms ) );

    // An explicit keyboard cursor also survives later mouse motion.
    cursor = ui_list_cursor_after_hover( 0, 1, selected, false );
    CHECK( cursor == 0 );
    CHECK( ui_list_highlight( 0, cursor, 1, selected[0], false ) ==
           ui_list_row_highlight::focused );
    CHECK( ui_list_highlight( 1, cursor, 1, selected[1], false ) == ui_list_row_highlight::none );

    // Multi-select hover stays separate from its keyboard cursor and selections.
    CHECK( ui_list_cursor_after_hover( 0, 1, selected, true ) == 0 );
    CHECK( selected == std::vector<bool>{ false, true } );
}

TEST_CASE( "ui_list_selection_ranges_skip_disabled_rows_and_reset_on_rebuild", "[ui][ui_helpers]" )
{
    ui_list_selection selection;
    std::vector<bool> selected( 5, false );
    const auto enabled = []( int index ) { return index != 2; };
    selection.click( selected, 1, enabled, false, false );
    selection.click( selected, 4, enabled, false, true );
    CHECK( selected == std::vector<bool>{ false, true, false, true, true } );
    CHECK_FALSE( selection.click( selected, 2, enabled, false, false ) );
    selection.click( selected, 0, enabled, true, true );
    CHECK( selected == std::vector<bool>{ true, true, false, true, true } );
    selection.reset();
    selected.assign( 2, false );
    selection.click( selected, 0, enabled, false, true );
    CHECK( selected == std::vector<bool>{ true, false } );
    CHECK_FALSE( selection.click( selected, 9, enabled, false, false ) );
}

TEST_CASE( "ui_scroll_model_maps_visible_rows_to_content", "[ui][ui_helpers]" )
{
    ui_scroll_model scroll( 20, 5, 7 );

    CHECK( scroll.is_visible( 7 ) );
    CHECK( scroll.is_visible( 11 ) );
    CHECK_FALSE( scroll.is_visible( 6 ) );
    CHECK_FALSE( scroll.is_visible( 12 ) );

    CHECK( scroll.index_at_viewport_row( 0 ) == 7 );
    CHECK( scroll.index_at_viewport_row( 4 ) == 11 );
    CHECK_FALSE( scroll.index_at_viewport_row( -1 ).has_value() );
    CHECK_FALSE( scroll.index_at_viewport_row( 5 ).has_value() );

    scroll.set_viewport_pos( 17 );
    CHECK( scroll.viewport_pos() == 15 );
    CHECK( scroll.index_at_viewport_row( 4 ) == 19 );
}

TEST_CASE( "ui_transient_control_can_close_with_pointer_passthrough", "[ui][ui_helpers]" )
{
    const ui_action_result consumed_close{ ui_action_result_type::closed, std::nullopt };
    const ui_action_result passthrough_close{ ui_action_result_type::closed, std::nullopt, true };

    CHECK( consumed_close.consumed() );
    CHECK_FALSE( consumed_close.passes_through() );
    CHECK_FALSE( passthrough_close.consumed() );
    CHECK( passthrough_close.passes_through() );

    CHECK_FALSE( ui_outside_pointer_passthrough( ui_outside_click_policy::consume, false ) );
    CHECK_FALSE( ui_outside_pointer_passthrough( ui_outside_click_policy::passthrough, true ) );
    CHECK( ui_outside_pointer_passthrough( ui_outside_click_policy::passthrough, false ) );
}

TEST_CASE( "ui_action_strip_owns_dropdown_affordance", "[ui][ui_helpers]" )
{
    const ui_action_entry plain( "Filter", "FILTER" );
    const ui_action_entry dropdown( "Filter", "FILTER", true, false, std::string(),
                                    std::nullopt, true );

    CHECK( ui_action_strip::format_label( plain ) == "[ Filter ]" );
    CHECK( ui_action_strip::format_label( dropdown ) == "[ Filter ▼ ]" );
    CHECK( ui_action_strip::format_label( ui_action_entry( "Materials", "MATERIALS", true, false,
            std::string(), true ) ) == "[x] Materials" );
}

TEST_CASE( "ui_multiselect_filter_supports_explicit_restore", "[ui][ui_helpers]" )
{
    ui_multiselect_filter<test_filter> filters {
        test_filter::first, test_filter::second, test_filter::third
    };

    filters.clear();
    filters.set( test_filter::first, true );
    filters.set( test_filter::third, true );
    filters.set( test_filter::unsupported, true );

    CHECK( filters.contains( test_filter::first ) );
    CHECK_FALSE( filters.contains( test_filter::second ) );
    CHECK( filters.contains( test_filter::third ) );
    CHECK_FALSE( filters.contains( test_filter::unsupported ) );
    CHECK( filters.selected_count() == 2 );
}

TEST_CASE( "ui_hit_map_returns_topmost_semantic_target", "[ui][ui_helpers]" )
{
    ui_hit_map<std::string> hits;
    hits.add( inclusive_rectangle<point>( point::zero, point( 4, 4 ) ), "base" );
    hits.add( inclusive_rectangle<point>( point( 2, 2 ), point( 3, 3 ) ), "overlay" );

    CHECK( hits.hit( point( 1, 1 ) ) == "base" );
    CHECK( hits.hit( point( 2, 2 ) ) == "overlay" );
    CHECK_FALSE( hits.hit( point( 5, 5 ) ).has_value() );

    hits.clear();
    CHECK( hits.empty() );
}

TEST_CASE( "ui_double_click_tracker_is_target_aware", "[ui][ui_helpers]" )
{
    using namespace std::chrono_literals;
    ui_double_click_tracker<int> clicks( 500ms );
    const ui_double_click_tracker<int>::time_point start;

    CHECK_FALSE( clicks.click( 1, start ) );
    CHECK_FALSE( clicks.click( 2, start + 100ms ) );
    CHECK( clicks.click( 2, start + 500ms ) );

    // A completed double-click resets instead of turning a triple-click into
    // two activations.
    CHECK_FALSE( clicks.click( 2, start + 600ms ) );
    CHECK_FALSE( clicks.click( 2, start + 1200ms ) );
}
