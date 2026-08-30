from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


# Contextual actions should communicate the actual chosen backend cost without
# exposing recipe variants.  This is particularly useful for Cut grass where
# the resolver may choose basic or advanced equipment automatically.
replace_once(
    "src/construction_ui.cpp",
    '''        for( const construction_context_action &action : context_actions ) {
            const nc_color action_color = action.resolution.ready() ? c_light_green : c_yellow;
            add( colorize( string_format( _( "%s  •  %s" ),
                                          contextual_action_label( action ),
                                          action.resolution.reason ), action_color ) );
        }
''',
    '''        for( const construction_context_action &action : context_actions ) {
            const nc_color action_color = action.resolution.ready() ? c_light_green : c_yellow;
            std::string summary = contextual_action_label( action );
            if( action.resolution.id.is_valid() ) {
                summary += "  •  " + to_string( time_duration::from_moves(
                                                   action.resolution.id.obj().adjusted_time() ) );
            }
            if( action.resolution.alternative_ids.size() > 1 ) {
                summary += string_format( n_gettext( "  •  %d method", "  •  %d methods",
                                                       action.resolution.alternative_ids.size() ),
                                          action.resolution.alternative_ids.size() );
            }
            summary += "  •  " + action.resolution.reason;
            add( colorize( summary, action_color ) );
        }
'''
)

# In unarmed Inspect & work mode, contextual actions are the primary controls.
# Do not waste the bottom row on a disabled instruction button.
replace_once(
    "src/construction_ui.cpp",
    '''    const bool show_context_actions = operation == construction_operation::build &&
                                      selected_target && !context_actions.empty();
    const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int contextual_action_y = show_context_actions ?
                                    std::max( 2, primary_action_y - 3 ) : primary_action_y;
    const int content_height = std::max( 1, contextual_action_y - 2 );
''',
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();
    const bool show_context_actions = operation == construction_operation::build &&
                                      selected_target && !context_actions.empty();
    const int primary_action_y = std::max( 2, getmaxy( inspector_window ) - 3 );
    const int contextual_action_y = show_context_actions ?
                                    std::max( 2, primary_action_y - ( inspect_mode ? 1 : 3 ) ) :
                                    primary_action_y;
    const int content_height = std::max( 1, contextual_action_y - 2 );
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    const bool inspect_mode = operation == construction_operation::build && selected_group.is_null();
    ui_action_entry build( inspect_mode ? _( "Choose a build result" ) : _( "Select a target" ),
                           "APPLY", false, false,
                           operation == construction_operation::remove ?
                           _( "Select a world tile first." ) :
                           inspect_mode ? _( "Choose a result from the catalog to place new construction." ) :
                           _( "Select a construction and a world tile first." ) );
    if( !inspect_mode ) {
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            if( !selected_target ) {
            build.label = _( "Select this tile first" );
            build.disabled_reason = _( "Click the world tile to commit this target." );
        } else if( resolution.status == construction_target_status::in_progress ) {
            build.label = _( "Continue" );
            build.enabled = target_is_adjacent( *target );
            build.disabled_reason = build.enabled ? std::string() :
                                    _( "Move adjacent to continue this construction." );
        } else if( !target_is_adjacent( *target ) ) {
            build.label = operation == construction_operation::remove ?
                          _( "Go there and remove" ) : _( "Go there and build" );
            build.disabled_reason = operation == construction_operation::remove ?
                                    _( "Distant removal orders are not implemented yet." ) :
                                    _( "Distant build orders are planned for the next construction pass." );
        } else {
            build.label = operation == construction_operation::remove && resolved_construction() ?
                          string_format( _( "Remove %s" ), resolved_construction()->group->name() ) :
                          _( "Build here" );
                build.enabled = resolution.ready();
                build.disabled_reason = resolution.reason;
            }
        }
    }
''',
    '''    ui_action_entry build( _( "Select a target" ), "APPLY", false, false,
                           operation == construction_operation::remove ?
                           _( "Select a world tile first." ) :
                           _( "Select a construction and a world tile first." ) );
    if( !inspect_mode ) {
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            if( !selected_target ) {
                build.label = _( "Select this tile first" );
                build.disabled_reason = _( "Click the world tile to commit this target." );
            } else if( resolution.status == construction_target_status::in_progress ) {
                build.label = _( "Continue" );
                build.enabled = target_is_adjacent( *target );
                build.disabled_reason = build.enabled ? std::string() :
                                        _( "Move adjacent to continue this construction." );
            } else if( !target_is_adjacent( *target ) ) {
                build.label = operation == construction_operation::remove ?
                              _( "Go there and remove" ) : _( "Go there and build" );
                build.disabled_reason = operation == construction_operation::remove ?
                                        _( "Distant removal orders are not implemented yet." ) :
                                        _( "Distant build orders are planned for the next construction pass." );
            } else {
                build.label = operation == construction_operation::remove && resolved_construction() ?
                              string_format( _( "Remove %s" ), resolved_construction()->group->name() ) :
                              _( "Build here" );
                build.enabled = resolution.ready();
                build.disabled_reason = resolution.reason;
            }
        }
    }
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    build.tone = operation == construction_operation::build ?
                 ui_action_tone::positive : ui_action_tone::destructive;
    primary_action.configure( inspector_window, point( 2, primary_action_y ), { build },
                              inspector_width - 4, 1 );
    primary_action.draw( inspector_window );
    wnoutrefresh( inspector_window );
''',
    '''    if( inspect_mode ) {
        primary_action.clear();
    } else {
        build.tone = operation == construction_operation::build ?
                     ui_action_tone::positive : ui_action_tone::destructive;
        primary_action.configure( inspector_window, point( 2, primary_action_y ), { build },
                                  inspector_width - 4, 1 );
        primary_action.draw( inspector_window );
    }
    wnoutrefresh( inspector_window );
'''
)

replace_once(
    "src/construction_ui.cpp",
    '''    return _( "LMB select  •  MMB drag/pan  •  Wheel zoom  •  RMB context  •  Tab change focus" );
''',
    '''    return _( "LMB select  •  MMB drag/pan  •  Wheel zoom  •  RMB context  •  Esc clear/back  •  Tab focus" );
'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Polish contextual construction inspection [skip ci]\n"
)
