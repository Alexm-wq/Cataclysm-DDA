#include <chrono>
#include <string>

#include "cata_catch.h"
#include "point.h"
#include "ui_helpers/models/double_click_tracker.h"
#include "ui_helpers/models/hit_map.h"
#include "ui_helpers/models/multiselect_filter.h"
#include "ui_helpers/models/scroll_model.h"

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
