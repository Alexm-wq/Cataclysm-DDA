from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''    u.mod_moves( -u.get_speed() * 2 );
    const tripoint_bub_ms prev = u.pos_bub();
    u.setpos( here, p, false );
    const bool is_same_pos = u.pos_bub() == prev;
    const bool is_standup_peek = is_same_pos && u.is_crouching();
    tripoint_bub_ms center = p;
''',
    '''    u.mod_moves( -u.get_speed() * 2 );
    const tripoint_bub_ms prev = u.pos_bub();
    const tripoint_rel_ms entry_view_offset = u.view_offset;
    u.setpos( here, p, false );
    const bool is_same_pos = u.pos_bub() == prev;
    const bool is_standup_peek = is_same_pos && u.is_crouching();

    // Peeking changes the visibility origin, not the camera.  Preserve the exact
    // world-space camera center the player had before the temporary position shift.
    tripoint_bub_ms center = prev + entry_view_offset;
    center.z() = p.z();
''',
    "preserve pre-peek camera center",
)

text = replace_once(
    text,
    '''    } else {                // Else is normal peek
        result = look_around( looka_params );
        u.setpos( here, prev, false );
    }

    if( result.peek_action ) {
''',
    '''    } else {                // Else is normal peek
        result = look_around( looka_params );
        u.setpos( here, prev, false );
    }

    // `center` is the final world-space camera center chosen while peeking.  Convert
    // it back to an offset from the real avatar position so middle-drag/zoom camera
    // changes survive leaving peek just as they do in normal gameplay.
    tripoint_rel_ms restored_view_offset = center - u.pos_bub();
    restored_view_offset.z() = entry_view_offset.z();
    u.view_offset = restored_view_offset;
#if defined(TILES)
    normalize_map_camera();
#endif

    if( result.peek_action ) {
''',
    "persist peek camera changes",
)

text = replace_once(
    text,
    '''    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "CENTER" );
''',
    '''    ctxt.register_action( "MOUSE_MOVE" );
#if defined(TILES)
    if( peeking ) {
        // Peek is a visibility mode, not a separate camera mode.  Accept the same
        // wheel zoom and middle-button drag actions as normal gameplay.
        ctxt.register_action( "SCROLL_UP" );
        ctxt.register_action( "SCROLL_DOWN" );
        ctxt.register_action( "CAMERA_PAN_START" );
        ctxt.register_action( "CAMERA_PAN_END" );
    }
#endif
    ctxt.register_action( "CENTER" );
''',
    "register normal camera actions while peeking",
)

text = replace_once(
    text,
    '''        const tripoint_rel_ms edge_scroll = mouse_edge_scrolling_terrain( ctxt );
        const int scroll_timeout = get_option<int>( "EDGE_SCROLL" );
        const bool edge_scrolling = edge_scroll != tripoint_rel_ms::zero && scroll_timeout >= 0;
''',
    '''        // Legacy look-around edge scrolling fights the mouse camera controls and
        // makes peek pan just because the pointer approaches/leaves the viewport.  Peek
        // deliberately uses the normal gameplay camera model instead.
        const tripoint_rel_ms edge_scroll = peeking ? tripoint_rel_ms::zero :
                                              mouse_edge_scrolling_terrain( ctxt );
        const int scroll_timeout = get_option<int>( "EDGE_SCROLL" );
        const bool edge_scrolling = !peeking && edge_scroll != tripoint_rel_ms::zero &&
                                    scroll_timeout >= 0;
''',
    "disable legacy edge panning during peek",
)

old_input = '''        if( edge_scrolling ) {
            action = ctxt.handle_input( scroll_timeout );
        } else {
            action = ctxt.handle_input();
        }
        if( ( action == "LEVEL_UP" || action == "LEVEL_DOWN" || action == "MOUSE_MOVE" ||
'''
new_input = '''        if( edge_scrolling ) {
            action = ctxt.handle_input( scroll_timeout );
        } else {
            action = ctxt.handle_input();
        }

#if defined(TILES)
        if( peeking ) {
            const bool middle_mouse_down = is_middle_mouse_button_down();
            const bool mouse_focused = has_sdl_mouse_focus();
            if( camera_pan_active && ( !middle_mouse_down || !mouse_focused ) ) {
                camera_pan_active = false;
                camera_pan_anchor.reset();
                set_sdl_mouse_capture( false );
            }

            // Match normal gameplay's permissive middle-drag startup: some SDL paths
            // report motion while the button is held before a dedicated start action.
            if( action == "MOUSE_MOVE" && !camera_pan_active && middle_mouse_down && mouse_focused ) {
                camera_pan_anchor = ctxt.get_coordinates( w_terrain, ter_view_p.raw().xy(), true );
                camera_pan_active = camera_pan_anchor.has_value();
                if( camera_pan_active ) {
                    set_sdl_mouse_capture( true );
                    continue;
                }
            }

            if( action == "CAMERA_PAN_START" ) {
                camera_pan_anchor = ctxt.get_coordinates( w_terrain, ter_view_p.raw().xy(), true );
                camera_pan_active = camera_pan_anchor.has_value();
                set_sdl_mouse_capture( camera_pan_active );
                continue;
            }
            if( action == "CAMERA_PAN_END" ) {
                camera_pan_active = false;
                camera_pan_anchor.reset();
                set_sdl_mouse_capture( false );
                continue;
            }
            if( action == "MOUSE_MOVE" && camera_pan_active && camera_pan_anchor ) {
                const std::optional<tripoint_bub_ms> mouse_pos = ctxt.get_coordinates(
                            w_terrain, ter_view_p.raw().xy(), true );
                if( mouse_pos ) {
                    center += *camera_pan_anchor - *mouse_pos;
                    u.view_offset = center - u.pos_bub();
                    normalize_map_camera();
                    center = u.pos_bub() + u.view_offset;
                    invalidate_main_ui_adaptor();
                }
                continue;
            }

            if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
                const int old_zoom = get_zoom();
                const tripoint_bub_ms old_center = center;
                std::optional<tripoint_bub_ms> zoom_anchor;
                if( action == "SCROLL_UP" && old_zoom < MAXIMUM_TILESET_ZOOM ) {
                    zoom_anchor = ctxt.get_coordinates( w_terrain, ter_view_p.raw().xy(), true );
                    zoom_in();
                } else if( action == "SCROLL_DOWN" && old_zoom > MINIMUM_TILESET_ZOOM ) {
                    zoom_out();
                } else {
                    continue;
                }

                mark_main_ui_adaptor_resize();
                if( action == "SCROLL_UP" && zoom_anchor && get_zoom() > old_zoom ) {
                    // Same cursor-anchored zoom-in transform used by normal gameplay.
                    const double camera_fraction = 1.0 - static_cast<double>( old_zoom ) /
                                                   static_cast<double>( get_zoom() );
                    center.x() += static_cast<int>( std::lround(
                                      ( zoom_anchor->x() - old_center.x() ) * camera_fraction ) );
                    center.y() += static_cast<int>( std::lround(
                                      ( zoom_anchor->y() - old_center.y() ) * camera_fraction ) );
                }
                u.view_offset = center - u.pos_bub();
                normalize_map_camera();
                center = u.pos_bub() + u.view_offset;
                invalidate_main_ui_adaptor();
                continue;
            }
        }
#endif

        if( ( action == "LEVEL_UP" || action == "LEVEL_DOWN" || action == "MOUSE_MOVE" ||
'''
text = replace_once(text, old_input, new_input, "route normal mouse camera controls in peek")

text = replace_once(
    text,
    '''    ctxt.reset_timeout();
    u.view_offset = prev_offset;
    zone_cb = nullptr;
''',
    '''    ctxt.reset_timeout();
#if defined(TILES)
    if( peeking ) {
        camera_pan_active = false;
        camera_pan_anchor.reset();
        set_sdl_mouse_capture( false );
    }
#endif
    u.view_offset = prev_offset;
    zone_cb = nullptr;
''',
    "release peek camera capture",
)

path.write_text(text, encoding="utf-8")

assert "const tripoint_rel_ms entry_view_offset = u.view_offset;" in text
assert "const tripoint_rel_ms edge_scroll = peeking ? tripoint_rel_ms::zero" in text
assert 'ctxt.register_action( "CAMERA_PAN_START" );' in text
assert "Same cursor-anchored zoom-in transform used by normal gameplay." in text
assert "restored_view_offset = center - u.pos_bub()" in text

Path("/tmp/branch_patch_commit_message").write_text(
    "Keep normal camera controls while peeking\n", encoding="utf-8"
)
