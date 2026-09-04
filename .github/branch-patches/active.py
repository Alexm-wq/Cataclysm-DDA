from pathlib import Path

path = Path("src/construction_ui.cpp")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    '''    const std::optional<point> inspector_pos = input_event_window_position(
                raw_input, inspector_window );
    if( !inspector_pos ) {
        return false;
    }
    const std::optional<int> hit = primary_action.hit_test( *inspector_pos );
    const ui_action_entry *entry = hit ? primary_action.entry( *hit ) : nullptr;
    if( entry == nullptr || entry->id != "PAUSE" ) {
        return false;
    }
''',
    '''    bool pause_requested = false;
    if( inspector_window ) {
        const std::optional<point> inspector_pos = input_event_window_position(
                    raw_input, inspector_window );
        if( inspector_pos ) {
            const std::optional<int> hit = primary_action.hit_test( *inspector_pos );
            const ui_action_entry *entry = hit ? primary_action.entry( *hit ) : nullptr;
            pause_requested = entry != nullptr && entry->id == "PAUSE";
        }
    }
    if( !pause_requested && compact && header ) {
        const std::optional<point> header_pos = input_event_window_position( raw_input, header );
        if( header_pos ) {
            const std::optional<int> hit = header_actions.hit_test( *header_pos );
            const ui_action_entry *entry = hit ? header_actions.entry( *hit ) : nullptr;
            pause_requested = entry != nullptr && entry->id == "PAUSE";
        }
    }
    if( !pause_requested ) {
        return false;
    }
''',
    "recognize compact header pause",
)

replace_once(
    '''    }
    actions.push_back( { ui_action_entry( _( "Back" ), "BACK" ), 2,
                         ui_action_alignment::right } );
''',
    '''    }
    if( compact && activity_handoff ) {
        actions.push_back( { ui_action_entry( _( "Pause" ), "PAUSE" ), 2,
                             ui_action_alignment::right } );
    }
    actions.push_back( { ui_action_entry( _( "Back" ), "BACK" ), 2,
                         ui_action_alignment::right } );
''',
    "compact header pause button",
)

replace_once(
    '''                build.disabled_reason = can_walk ?
                                        resolution.reason :
                                        operation == construction_operation::markers ?
                                        _( "Distant marker orders are not implemented yet." ) :
                                        _( "Distant build orders are planned for the next construction pass." );
''',
    '''                build.disabled_reason = resolution.reason;
''',
    "remove stale distant marker fallback",
)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Keep Pause reachable in compact construction UI\n", encoding="utf-8"
)
