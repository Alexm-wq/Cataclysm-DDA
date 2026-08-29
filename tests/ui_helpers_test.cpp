#include <array>
#include <chrono>
#include <string>

#include "cata_catch.h"
#include "point.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/compass_grid.h"
#include "ui_helpers/controls/key_field.h"
#include "ui_helpers/controls/row_accessories.h"
#include "ui_helpers/controls/scroll_view.h"
#include "ui_helpers/controls/selection_panel.h"
#include "ui_helpers/controls/world_viewport.h"
#include "ui_helpers/models/double_click_tracker.h"
#include "ui_helpers/models/hit_map.h"
#include "ui_helpers/models/hover_dwell.h"
#include "ui_helpers/models/list_layout.h"
#include "ui_helpers/models/list_selection.h"
#include "ui_helpers/models/multiselect_filter.h"
#include "ui_helpers/models/scroll_model.h"
#include "ui_helpers/models/text_overflow.h"
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

TEST_CASE( "ui_clipped_text_only_targets_visible_truncated_labels", "[ui][ui_helpers]" )
{
    int window;
    int popup;
    ui_text_overflow_model model;
    const inclusive_rectangle<point> area( point::zero, point( 79, 23 ) );
    const inclusive_rectangle<point> row( point( 2, 4 ), point( 11, 4 ) );
    const point hover( 5, 4 );
    const std::string full = "A long container name and its location";
    model.record( &window, row, full, 38, 10 );
    model.present( &window, area );
    REQUIRE( model.hit( hover ) );
    CHECK( model.hit( hover )->text == full );
    CHECK_FALSE( model.hit( point( 12, 4 ) ) );
    CHECK_FALSE( model.hit( point( 5, 5 ) ) );

    SECTION( "fitting and exactly fitting labels never show an expansion" ) {
        model.record( &window, row, "Fits", 4, 10 );
        CHECK_FALSE( model.hit( hover ) );
        model.record( &window, row, "Exact fit!", 10, 10 );
        CHECK_FALSE( model.hit( hover ) );
        CHECK_FALSE( ui_text_overflow_model::clipped( 38, 0 ) );
    }
    SECTION( "display columns determine truncation, not UTF-8 byte counts" ) {
        model.record( &window, row, "箱箱", 4, 4 );
        CHECK_FALSE( model.hit( hover ) );
        model.record( &window, row, "箱箱", 4, 3 );
        REQUIRE( model.hit( hover ) );
        CHECK( model.hit( hover )->text == "箱箱" );
    }
    SECTION( "popup text retains base and inline colors without counting tags as columns" ) {
        const std::string colored =
            "<color_green>Tank <color_red>12 L</color> remaining</color>";
        model.record( &window, row, colored, 19, 10 );
        REQUIRE( model.hit( hover ) );
        CHECK( model.hit( hover )->text == colored );
        model.record( &window, row, colored, 19, 19 );
        CHECK_FALSE( model.hit( hover ) );
    }
    SECTION( "a blank popup blocks a covered label from the window below" ) {
        model.present( &popup, area );
        CHECK_FALSE( model.hit( hover ) );
        model.record( &popup, row, "Another long label", 18, 10 );
        REQUIRE( model.hit( hover ) );
        CHECK( model.hit( hover )->text == "Another long label" );
    }
    SECTION( "erasing and rebuilding a window removes its stale text" ) {
        model.erase_window( &window );
        CHECK_FALSE( model.hit( hover ) );
        model.record( &window, row, "Replacement long label", 22, 10 );
        REQUIRE( model.hit( hover ) );
        CHECK( model.hit( hover )->text == "Replacement long label" );
        model.clear();
        CHECK_FALSE( model.hit( hover ) );
    }
    SECTION( "text is not hoverable until its window has been presented" ) {
        model.clear();
        model.record( &window, row, full, 38, 10 );
        CHECK_FALSE( model.hit( hover ) );
        model.present( &window, area );
        REQUIRE( model.hit( hover ) );
    }
}

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

TEST_CASE( "ui_hover_dwell_appears_after_one_second_without_new_input", "[ui][ui_helpers]" )
{
    using namespace std::chrono_literals;
    ui_hover_dwell dwell;
    const ui_hover_dwell::clock::time_point now;
    const inclusive_rectangle<point> bounds( point( 100, 100 ), point( 123, 123 ) );
    dwell.configure( bounds, 1000ms, "inventory" );
    CHECK_FALSE( dwell.update_pointer( point( 112, 112 ), now ) );

    SECTION( "idle redraws preserve the pending timer and visible tooltip" ) {
        for( int elapsed = 125; elapsed < 1000; elapsed += 125 ) {
            dwell.configure( bounds, 1000ms, "inventory" );
            CHECK_FALSE( dwell.tick( now + std::chrono::milliseconds( elapsed ) ) );
        }
        CHECK_FALSE( dwell.tick( now + 999ms ) );
        CHECK( dwell.tick( now + 1000ms ) );
        CHECK( dwell.visible() );
        dwell.configure( bounds, 1000ms, "inventory" );
        CHECK( dwell.visible() );
        CHECK_FALSE( dwell.tick( now + 2000ms ) );
    }
    SECTION( "pointer motion restarts dwell and leaving clears it" ) {
        CHECK_FALSE( dwell.update_pointer( point( 113, 112 ), now + 750ms ) );
        CHECK_FALSE( dwell.tick( now + 1749ms ) );
        CHECK( dwell.tick( now + 1750ms ) );
        CHECK( dwell.update_pointer( point( 124, 112 ), now + 1751ms ) );
        CHECK_FALSE( dwell.visible() );
        CHECK_FALSE( dwell.tick( now + 5000ms ) );
        CHECK_FALSE( dwell.update_pointer( point( 112, 112 ), now + 5001ms ) );
        CHECK( dwell.tick( now + 6001ms ) );
        CHECK( dwell.update_pointer( std::nullopt, now + 6002ms ) );
        CHECK_FALSE( dwell.tick( now + 8000ms ) );
    }
    SECTION( "click dismissal and resetting cannot leave a stale tooltip" ) {
        CHECK( dwell.tick( now + 1000ms ) );
        CHECK( dwell.clear_pointer() );
        CHECK_FALSE( dwell.tick( now + 2000ms ) );
        CHECK_FALSE( dwell.update_pointer( point( 112, 112 ), now + 2001ms ) );
        dwell.reset();
        CHECK_FALSE( dwell.update_pointer( point( 112, 112 ), now + 4000ms ) );
        CHECK_FALSE( dwell.tick( now + 6000ms ) );
    }
}

TEST_CASE( "ui_hover_dwell_retargets_exact_pixel_bounds_and_content", "[ui][ui_helpers]" )
{
    using namespace std::chrono_literals;
    ui_hover_dwell dwell;
    const ui_hover_dwell::clock::time_point now;
    const inclusive_rectangle<point> first( point( 100, 100 ), point( 123, 123 ) );
    const inclusive_rectangle<point> second( point( 123, 100 ), point( 146, 123 ) );
    const point shared_border( 123, 112 );
    dwell.configure( first, 1000ms, "inventory" );
    dwell.update_pointer( shared_border, now );
    REQUIRE( dwell.tick( now + 1000ms ) );

    // Even overlapping pixel buttons cannot inherit the previous target's timer.
    dwell.configure( second, 1000ms, "crafting" );
    CHECK_FALSE( dwell.visible() );
    CHECK_FALSE( dwell.tick( now + 2000ms ) );
    CHECK_FALSE( dwell.update_pointer( shared_border, now + 2001ms ) );
    CHECK_FALSE( dwell.tick( now + 3000ms ) );
    CHECK( dwell.tick( now + 3001ms ) );

    // Reassigning a button or changing its hotkey resets the same rectangle too.
    dwell.configure( second, 1000ms, "map" );
    CHECK_FALSE( dwell.visible() );
    dwell.update_pointer( shared_border, now + 4000ms );
    CHECK_FALSE( dwell.tick( now + 4999ms ) );
    CHECK( dwell.tick( now + 5000ms ) );

    dwell.configure( second, 0ms, "map" );
    CHECK_FALSE( dwell.visible() );
    CHECK( dwell.update_pointer( shared_border, now + 6000ms ) );
    CHECK( dwell.visible() );
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

TEST_CASE( "ui_list_columns_keep_hints_separate_from_names_and_scrollbar", "[ui][ui_helpers]" )
{
    const ui_list_columns columns = ui_list_columns_for_width( 64, 16 );
    CHECK( columns.label_width == 46 );
    CHECK( columns.hint_x == 47 );
    CHECK( columns.hint_width == 16 );

    SECTION( "a long translated hint leaves room for the label at narrow widths" ) {
        const ui_list_columns narrow = ui_list_columns_for_width( 28, 40 );
        CHECK( narrow.label_width == 13 );
        CHECK( narrow.hint_x == 14 );
        CHECK( narrow.hint_width == 13 );
        CHECK( narrow.hint_x + narrow.hint_width == 27 );
    }
    SECTION( "lists without hints retain the full label area" ) {
        const ui_list_columns plain = ui_list_columns_for_width( 64, 0 );
        CHECK( plain.label_width == 63 );
        CHECK( plain.hint_width == 0 );
    }
    SECTION( "tiny windows never produce negative column widths" ) {
        for( int width = 0; width <= 3; ++width ) {
            const ui_list_columns tiny = ui_list_columns_for_width( width, 16 );
            CHECK( tiny.label_width == std::max( 0, width - 1 ) );
            CHECK( tiny.hint_width == 0 );
        }
    }
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

    // A partial category filter can restore All, clear All, and combine categories.
    filters.toggle_all();
    CHECK( filters.all_selected() );
    CHECK( filters.selected_count() == 3 );
    filters.toggle_all();
    CHECK( filters.none_selected() );
    filters.toggle( test_filter::second );
    filters.toggle( test_filter::third );
    filters.toggle( test_filter::unsupported );
    CHECK_FALSE( filters.contains( test_filter::first ) );
    CHECK( filters.contains( test_filter::second ) );
    CHECK( filters.contains( test_filter::third ) );
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

TEST_CASE( "ui_row_accessories_own_independent_hit_regions", "[ui][ui_helpers]" )
{
    ui_row_accessories controls;
    const std::vector<ui_row_accessory> items = {
        { ui_action_entry( "On", "POWER" ), ui_row_accessory_side::leading },
        { ui_action_entry( "Sprite", "SPRITE", true, false, "", true ) },
        { ui_action_entry( "15 kJ/turn", "VALUE" ), ui_row_accessory_side::trailing, false }
    };
    const ui_row_label_area label = controls.layout( point( 0, 2 ), 50, items );
    CHECK( label.width >= 6 );
    CHECK( controls.handle_input( "SELECT", point( 1, 2 ) ).entry->id == "POWER" );
    CHECK( controls.handle_input( "SELECT", point( 49, 2 ) ).entry->id == "SPRITE" );
    CHECK( controls.handle_input( "SELECT", point( 49, 2 ) ).entry->checked == true );
    CHECK_FALSE( controls.handle_input( "SELECT", label.origin ).consumed() );
    CHECK_FALSE( controls.handle_input( "SELECT", point( 50, 2 ) ).consumed() );
    CHECK_FALSE( controls.handle_input( "SELECT", point( 1, 3 ) ).consumed() );
    CHECK_FALSE( controls.handle_input( "SCROLL_DOWN", point( 1, 2 ) ).consumed() );
    controls.handle_input( "MOUSE_MOVE", point( 49, 2 ) );
    CHECK_FALSE( controls.handle_input( "CONFIRM", point( 49, 2 ) ).consumed() );
    for( int x = label.origin.x; x < 39; ++x ) {
        // The label, its padding and the read-only power value are not buttons.
        CHECK_FALSE( controls.handle_input( "SELECT", point( x, 2 ) ).consumed() );
    }

    SECTION( "disabled controls retain their reason without becoming row clicks" ) {
        controls.begin_layout();
        controls.layout( point::zero, 30, {
            {
                ui_action_entry( "Off", "POWER", false, false, "No power" ),
                ui_row_accessory_side::leading
            }
        } );
        const ui_action_result result = controls.handle_input( "SELECT", point( 1, 0 ) );
        CHECK( result.consumed() );
        CHECK( result.type == ui_action_result_type::disabled );
        REQUIRE( result.entry );
        CHECK( result.entry->disabled_reason == "No power" );
        CHECK_FALSE( controls.handle_input( "SELECT", point( 49, 2 ) ).consumed() );
    }
    SECTION( "scrolling rebuilding and hiding discard offscreen regions" ) {
        controls.begin_layout();
        controls.layout( point( 0, 3 ), 40, items );
        CHECK_FALSE( controls.handle_input( "SELECT", point( 1, 2 ) ).consumed() );
        CHECK( controls.handle_input( "SELECT", point( 1, 3 ) ).consumed() );
        controls.clear();
        CHECK_FALSE( controls.handle_input( "SELECT", point( 1, 3 ) ).consumed() );
    }
    SECTION( "narrow rows and wide translated characters cannot overlap controls" ) {
        for( int width = 0; width < 60; ++width ) {
            controls.begin_layout();
            const auto area = controls.layout( point::zero, width, items );
            CHECK( area.width >= 0 );
            CHECK( area.origin.x + area.width <= width );
            for( int x = area.origin.x; x < area.origin.x + area.width; ++x ) {
                CHECK_FALSE( controls.handle_input( "SELECT", point( x, 0 ) ).consumed() );
            }
            CHECK_FALSE( controls.handle_input( "SELECT", point( width, 0 ) ).consumed() );
        }
        controls.begin_layout();
        const auto area = controls.layout( point::zero, 20,
        { { ui_action_entry( "箱箱", "WIDE" ), ui_row_accessory_side::leading } } );
        CHECK( area.origin.x == 9 ); // two double-width glyphs, decoration and gap
    }
}

TEST_CASE( "ui_key_field_captures_raw_keys_without_action_fallthrough", "[ui][ui_helpers]" )
{
    ui_key_field field;
    const auto valid = []( int key ) {
        return key == 's' || key == '!';
    };
    const auto key = []( int ch ) {
        return input_event( ch, input_event_t::keyboard_char );
    };
    CHECK_FALSE( field.capture( key( 's' ), valid ).consumed() );
    field.arm();
    CHECK( field.armed() );
    CHECK( field.capture( key( '4' ), valid ).type == ui_key_field_result_type::invalid );
    CHECK( field.armed() );
    CHECK( field.capture( input_event( MouseInput::Move, input_event_t::mouse ), valid ).consumed() );
    CHECK( field.armed() );
    const auto assigned = field.capture( key( 's' ), valid );
    CHECK( assigned.type == ui_key_field_result_type::assigned );
    CHECK( assigned.key == 's' );
    CHECK( assigned.consumed() );
    CHECK_FALSE( field.armed() );
    CHECK_FALSE( field.capture( key( 's' ), valid ).consumed() );
    field.arm();
    CHECK( field.capture( key( ' ' ), valid ).type == ui_key_field_result_type::cleared );
    CHECK_FALSE( field.armed() );
    field.arm();
    CHECK( field.capture( key( KEY_ESCAPE ), valid ).type == ui_key_field_result_type::cancelled );
    CHECK_FALSE( field.armed() );
    field.arm();
    input_event multiple = key( 's' );
    multiple.add_input( '!' );
    CHECK( field.capture( multiple, valid ).type == ui_key_field_result_type::invalid );
    CHECK( field.armed() );
    field.cancel();
    CHECK_FALSE( field.armed() );
}

TEST_CASE( "ui_toolbar_wraps_around_back_and_ignores_stale_hover_confirm", "[ui][ui_helpers]" )
{
    ui_action_strip toolbar;
    const std::vector<ui_action_strip_item> actions = {
        { ui_action_entry( "Aktivierbar (12)", "TAB" ) },
        { ui_action_entry( "Sortierung", "SORT", true, false, "", std::nullopt, true ) },
        { ui_action_entry( "Zurück", "BACK" ), 1, ui_action_alignment::right }
    };
    toolbar.configure( point( 30, 10 ), point::zero, actions, 30, 4 );
    REQUIRE( toolbar.bounds_for_id( "TAB" ) );
    REQUIRE( toolbar.bounds_for_id( "SORT" ) );
    REQUIRE( toolbar.bounds_for_id( "BACK" ) );
    CHECK( toolbar.bounds_for_id( "TAB" )->p_min.y == 1 );
    CHECK( toolbar.bounds_for_id( "BACK" )->p_max.x == 29 );
    CHECK( toolbar.bounds_for_id( "BACK" )->p_min.y == 0 );
    toolbar.handle_pointer_input( "MOUSE_MOVE", toolbar.bounds_for_id( "BACK" )->p_min );
    CHECK_FALSE( toolbar.handle_pointer_input( "CONFIRM", std::nullopt ).consumed() );
    const auto clicked = toolbar.handle_pointer_input( "SELECT",
        toolbar.bounds_for_id( "BACK" )->p_min );
    REQUIRE( clicked.entry );
    CHECK( clicked.entry->id == "BACK" );
    toolbar.configure( point( 20, 1 ), point::zero, {}, 20, 1 );
    CHECK_FALSE( toolbar.handle_pointer_input( "SELECT", point( 29, 0 ) ).consumed() );
}

TEST_CASE( "ui_selection_list_accessories_do_not_change_selection_model", "[ui][ui_helpers]" )
{
    ui_selection_list list;
    list.set_entries( { ui_action_entry( "First", "FIRST" ), ui_action_entry( "Second", "SECOND" ) },
                      false );
    list.hover_previews( false );
    list.clear_selection();
    CHECK( list.cursor() == -1 );
    CHECK( list.selected_indices().empty() );
    list.select_only( 1 );
    list.set_row_accessories( { {}, { { ui_action_entry( "Sprite", "SPRITE" ) } } } );
    CHECK( list.cursor() == 1 );
    CHECK( list.selected_indices() == std::vector<int> { 1 } );
    list.invalidate_geometry();
    CHECK( list.selected_indices() == std::vector<int> { 1 } );
}

TEST_CASE( "ui_inline_settings_drop_hidden_hit_regions", "[ui][ui_helpers]" )
{
    const point size( 40, 10 );
    ui_action_strip settings;
    settings.begin_layout();
    settings.add_row( size, point( 2, 3 ), ui_action_entry( "Fuel", "FUEL" ), 30 );
    settings.add_row( size, point( 2, 4 ), ui_action_entry( "Weapon", "WEAPON" ), 30 );
    REQUIRE( settings.bounds_for_id( "FUEL" ) );
    REQUIRE( settings.bounds_for_id( "WEAPON" ) );
    settings.handle_pointer_input( "MOUSE_MOVE", point( 3, 3 ) );
    settings.begin_layout();
    settings.add_row( size, point( 2, 3 ), ui_action_entry( "Weapon", "WEAPON" ), 30 );
    CHECK_FALSE( settings.bounds_for_id( "FUEL" ) );
    CHECK_FALSE( settings.handle_pointer_input( "SELECT", point( 3, 4 ) ).consumed() );
    CHECK( settings.handle_pointer_input( "SELECT", point( 3, 3 ) ).entry->id == "WEAPON" );
    CHECK_FALSE( settings.handle_pointer_input( "CONFIRM", std::nullopt ).consumed() );

    ui_key_field field;
    field.configure( size, point( 2, 6 ), 30, "Shortcut", "a", "Press a key" );
    CHECK( field.handle_pointer_input( "SELECT", point( 3, 6 ) ).consumed() );
    CHECK( field.armed() );
    field.hide();
    CHECK_FALSE( field.handle_pointer_input( "SELECT", point( 3, 6 ) ).consumed() );
    field.cancel();
    CHECK_FALSE( field.armed() );
}

TEST_CASE( "ui_inspector_scroll_view_is_independent_and_clips_controls", "[ui][ui_helpers]" )
{
    ui_scroll_view view;
    ui_scroll_model other( 30, 5, 3 );
    input_context context( "UI_SCROLL_VIEW_TEST" );
    view.configure( point( 10, 2 ), 30, 5, 20 );
    CHECK_FALSE( view.position( 5 ) );
    CHECK( view.position( 0 )->y == 2 );
    CHECK_FALSE( view.handle_input( "SCROLL_DOWN", context, point( 9, 3 ) ) );
    CHECK( view.handle_input( "SCROLL_DOWN", context, point( 12, 3 ) ) );
    CHECK_FALSE( view.position( 0 ) );
    CHECK( view.position( 5 )->y == 6 );
    CHECK( other.viewport_pos() == 3 );
    CHECK_FALSE( view.handle_input( "PAGE_DOWN", context, std::nullopt ) );
    CHECK( view.handle_input( "END", context, std::nullopt, true ) );
    CHECK( view.model().viewport_pos() == 15 );
    view.configure( point( 10, 2 ), 30, 5, 2 );
    CHECK( view.model().viewport_pos() == 0 );
    view.hide();
    CHECK_FALSE( view.position( 0 ) );
    CHECK_FALSE( view.handle_input( "SCROLL_DOWN", context, point( 12, 3 ) ) );
}

TEST_CASE( "ui_world_viewport_clips_actions_and_owns_pan_capture", "[ui][ui_helpers]" )
{
    ui_world_viewport viewport;
    viewport.configure( inclusive_rectangle<point>( point( 20, 3 ), point( 79, 21 ) ) );

    CHECK_FALSE( viewport.handle_input( "SELECT", point( 10, 10 ) ).consumed() );
    CHECK( viewport.handle_input( "SELECT", point( 30, 10 ) ).type ==
           ui_world_viewport_action_type::select );
    CHECK( viewport.handle_input( "SEC_SELECT", point( 30, 10 ) ).type ==
           ui_world_viewport_action_type::context );
    CHECK( viewport.handle_input( "SCROLL_UP", point( 30, 10 ) ).type ==
           ui_world_viewport_action_type::zoom_in );
    CHECK_FALSE( viewport.handle_input( "SCROLL_UP", point( 90, 10 ) ).consumed() );

    CHECK( viewport.handle_input( "CAMERA_PAN_START", point( 30, 10 ) ).type ==
           ui_world_viewport_action_type::pan_start );
    CHECK( viewport.has_capture() );
    CHECK( viewport.handle_input( "MOUSE_MOVE", point( 90, 10 ) ).type ==
           ui_world_viewport_action_type::pan_move );
    CHECK( viewport.handle_input( "SELECT", point( 10, 10 ) ).type ==
           ui_world_viewport_action_type::handled );
    CHECK( viewport.has_capture() );
    CHECK( viewport.handle_input( "CAMERA_PAN_END", point( 10, 10 ) ).type ==
           ui_world_viewport_action_type::pan_end );
    CHECK_FALSE( viewport.has_capture() );
    CHECK_FALSE( viewport.handle_input( "SELECT", point( 10, 10 ) ).consumed() );

    viewport.hide();
    CHECK_FALSE( viewport.handle_input( "SELECT", point( 30, 10 ) ).consumed() );
}
