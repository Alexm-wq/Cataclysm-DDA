from pathlib import Path


def once(text, old, new, label):
    if text.count(old) != 1:
        raise SystemExit(f"{label}: {text.count(old)} anchors")
    return text.replace(old, new, 1)

h = Path("src/ui_helpers/primitive/scrollbar.h")
t = h.read_text()
t = once(t,
'''        bool dragging = false;\n        inclusive_rectangle<point> scrollbar_area;\n''',
'''        bool dragging = false;\n        int drag_grab_offset = 0;\n        inclusive_rectangle<point> scrollbar_area;\n        std::optional<inclusive_rectangle<point>> thumb_area;\n''', "scrollbar state")
h.write_text(t)

cpp = Path("src/ui_helpers/primitive/scrollbar.cpp")
t = cpp.read_text()
a = t.index("void scrollbar::apply")
b = t.index("bool scrollbar::handle_dragging", a)
apply = r'''void scrollbar::apply( const catacurses::window &window, const bool draw_unneeded )
{
    const int absolute_x = getbegx( window ) + offset_x_v;
    const int absolute_y = getbegy( window ) + offset_y_v;
    const int drawn_height = std::max( 1, viewport_size_v );
    scrollbar_area = inclusive_rectangle<point>( point( absolute_x, absolute_y ),
                     point( absolute_x, absolute_y + drawn_height - 1 ) );
    thumb_area.reset();

    if( viewport_size_v >= content_size_v || content_size_v <= 0 || viewport_size_v < 3 ) {
        dragging = false;
        if( draw_unneeded && viewport_size_v > 0 ) {
            mvwvline( window, point( offset_x_v, offset_y_v ), border_color_v, LINE_XOXO,
                      viewport_size_v );
        }
        return;
    }

    mvwputch( window, point( offset_x_v, offset_y_v ), arrow_color_v, '^' );
    mvwputch( window, point( offset_x_v, offset_y_v + viewport_size_v - 1 ), arrow_color_v, 'v' );

    const int slot_size = viewport_size_v - 2;
    const int bar_size = std::clamp(
                             static_cast<int>( std::lround( static_cast<double>( slot_size ) *
                                     static_cast<double>( viewport_size_v ) /
                                     static_cast<double>( content_size_v ) ) ), 1, slot_size );
    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :
                             std::max( 0, content_size_v - viewport_size_v );
    const int travel = std::max( 0, slot_size - bar_size );
    const int clamped_position = clamp( viewport_pos_v, 0, max_position );
    const int bar_start = max_position > 0 && travel > 0 ?
                          static_cast<int>( std::lround( static_cast<double>( clamped_position ) *
                                  static_cast<double>( travel ) /
                                  static_cast<double>( max_position ) ) ) : 0;
    const int bar_end = bar_start + bar_size;
    thumb_area = inclusive_rectangle<point>( point( absolute_x, absolute_y + 1 + bar_start ),
                 point( absolute_x, absolute_y + bar_end ) );

    const nc_color current_bar_color = dragging ? c_magenta_magenta : bar_color_v;
    mvwvline( window, point( offset_x_v, offset_y_v + 1 ), slot_color_v, LINE_XOXO, bar_start );
    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_start ), current_bar_color, LINE_XOXO,
              bar_size );
    mvwvline( window, point( offset_x_v, offset_y_v + 1 + bar_end ), slot_color_v, LINE_XOXO,
              slot_size - bar_end );
}

'''
t = t[:a] + apply + t[b:]
b = t.index("bool scrollbar::handle_dragging")
drag = r'''bool scrollbar::handle_dragging( const std::string &action, const std::optional<point> &coord,
                                 int &position )
{
    if( !thumb_area ) {
        dragging = false;
        return false;
    }

    const int max_position = scroll_to_last_v ? std::max( 0, content_size_v - 1 ) :
                             std::max( 0, content_size_v - viewport_size_v );
    const int track_min = scrollbar_area.p_min.y + 1;
    const int track_max = scrollbar_area.p_max.y - 1;
    const int thumb_size = thumb_area->p_max.y - thumb_area->p_min.y + 1;
    const int travel = std::max( 0, track_max - track_min + 1 - thumb_size );

    const auto publish = [&]( const int requested ) {
        viewport_pos_v = clamp( requested, 0, max_position );
        position = viewport_pos_v;
    };
    const auto drag_to = [&]( const int cursor_y ) {
        const int thumb_start = clamp( cursor_y - drag_grab_offset, track_min,
                                      track_min + travel );
        const int thumb_offset = thumb_start - track_min;
        const int requested = travel > 0 && max_position > 0 ?
                              static_cast<int>( std::lround( static_cast<double>( thumb_offset ) *
                                      static_cast<double>( max_position ) /
                                      static_cast<double>( travel ) ) ) : 0;
        publish( requested );
    };

    if( dragging && action == "SELECT" ) {
        dragging = false;
        drag_grab_offset = 0;
        return true;
    }
    if( dragging ) {
        if( ( action == "MOUSE_MOVE" || action == "CLICK_AND_DRAG" ) && coord ) {
            drag_to( coord->y );
            return true;
        }
        if( action != "MOUSE_MOVE" && action != "CLICK_AND_DRAG" ) {
            dragging = false;
            drag_grab_offset = 0;
        }
        return false;
    }
    if( action == "CLICK_AND_DRAG" && coord && thumb_area->contains( *coord ) ) {
        dragging = true;
        drag_grab_offset = clamp( coord->y - thumb_area->p_min.y, 0, thumb_size - 1 );
        return true;
    }
    if( action == "SELECT" && coord && scrollbar_area.contains( *coord ) ) {
        if( coord->y == scrollbar_area.p_min.y ) {
            publish( position - 1 );
        } else if( coord->y == scrollbar_area.p_max.y ) {
            publish( position + 1 );
        } else if( coord->y < thumb_area->p_min.y ) {
            publish( position - std::max( 1, viewport_size_v ) );
        } else if( coord->y > thumb_area->p_max.y ) {
            publish( position + std::max( 1, viewport_size_v ) );
        }
        return true;
    }
    return false;
}
'''
t = (t[:b] + drag).rstrip() + "\n"
cpp.write_text(t)

vh = Path("src/veh_interact.h")
t = vh.read_text()
t = once(t,
'''#include "ui_helpers/models/scroll_model.h"\n#include "ui_helpers/primitive/overlay.h"\n''',
'''#include "ui_helpers/models/scroll_model.h"\n#include "ui_helpers/primitive/overlay.h"\n#include "ui_helpers/primitive/scrollbar.h"\n''', "vehicle include")
t = once(t,
'''        ui_scroll_model part_scroll;\n        ui_scroll_model part_detail_scroll;\n        bool viewport_dragging = false;\n''',
'''        ui_scroll_model part_scroll;\n        ui_scroll_model part_detail_scroll;\n        scrollbar part_scrollbar;\n        scrollbar part_detail_scrollbar;\n        scrollbar reshape_scrollbar;\n        bool viewport_dragging = false;\n''', "vehicle scrollbar members")
vh.write_text(t)

vcpp = Path("src/veh_interact.cpp")
t = vcpp.read_text()
t = once(t,
'''    main_context.register_action( "FILTER" );\n    main_context.register_action( "SELECT" );\n    main_context.register_action( "SEC_SELECT" );\n    main_context.register_action( "MOUSE_MOVE" );\n''',
'''    main_context.register_action( "FILTER" );\n    part_scrollbar.set_draggable( main_context );\n    main_context.register_action( "SEC_SELECT" );\n''', "vehicle drag action")
t = once(t,
'''    if( part_scroll.can_scroll() ) {\n        scrollbar().offset_x( width - 1 ).offset_y( first_row )\n        .model( part_scroll ).apply( w_parts );\n    }\n''',
'''    part_scrollbar.offset_x( width - 1 ).offset_y( first_row )\n    .model( part_scroll ).apply( w_parts );\n''', "part scrollbar")
t = once(t,
'''        if( static_cast<int>( reshape_info->variants.size() ) > visible && visible > 0 ) {\n            scrollbar().offset_x( width - 1 ).offset_y( first_row )\n            .model( reshape_info->variant_scroll ).apply( w_msg );\n        }\n''',
'''        reshape_scrollbar.offset_x( width - 1 ).offset_y( first_row )\n        .model( reshape_info->variant_scroll ).apply( w_msg );\n''', "reshape scrollbar")
t = once(t,
'''    if( part_detail_scroll.can_scroll() ) {\n        scrollbar().offset_x( width - 1 ).offset_y( line )\n        .model( part_detail_scroll ).apply( w_msg );\n    }\n''',
'''    part_detail_scrollbar.offset_x( width - 1 ).offset_y( line )\n    .model( part_detail_scroll ).apply( w_msg );\n''', "detail scrollbar")
t = once(t,
'''    const std::optional<point> details_pos = mouse_pos_in( w_msg );\n    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );\n''',
'''    const std::optional<point> details_pos = mouse_pos_in( w_msg );\n    const std::optional<point> screen_pos = main_context.get_coordinates_text( catacurses::stdscr );\n    const bool over_schematic_content = viewport_pos && point_in_editor_schematic( *viewport_pos );\n''', "screen pos")
t = once(t,
'''    if( action == "MOUSE_MOVE" ) {\n        // Each strip must see the cursor leave as well as enter.  Passing nullopt\n''',
'''    if( !install_info && !remove_info ) {\n        if( part_scrollbar.handle_dragging( action, screen_pos, part_scroll ) ) {\n            return true;\n        }\n        if( reshape_info ) {\n            if( reshape_scrollbar.handle_dragging( action, screen_pos, reshape_info->variant_scroll ) ) {\n                return true;\n            }\n        } else if( !msg.has_value() &&\n                   part_detail_scrollbar.handle_dragging( action, screen_pos, part_detail_scroll ) ) {\n            return true;\n        }\n    }\n\n    if( action == "MOUSE_MOVE" ) {\n        // Each strip must see the cursor leave as well as enter.  Passing nullopt\n''', "scrollbar routing")
vcpp.write_text(t)

Path("/tmp/branch_patch_commit_message").write_text("Add browser-like draggable shared scrollbars\n")
