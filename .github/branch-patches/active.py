from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:160]!r}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/construction_ui.cpp",
    '#include "input_context.h"\n',
    '#include "input.h"\n#include "input_context.h"\n',
)

old = r'''    // ACT_BUILD normally uses the gameplay activity input context, which means
    // clicks on this still-visible editor are discarded until the activity
    // finishes.  Poll the editor context nonblocking instead.  Mere mouse motion
    // is ignored so looking at the progress frame never stops work; a deliberate
    // interaction pauses the partial construction and returns control here.
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
    // Keep the normal activity interruption key useful while this context owns
    // polling, even though it is not otherwise part of the Construction UI.
    context.register_action( "pause" );

    const auto poll_started = std::chrono::steady_clock::now();
    const std::string action = context.handle_input( 0 );
    const long long poll_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                                  std::chrono::steady_clock::now() - poll_started ).count();
    if( action.empty() || action == "TIMEOUT" || action == "ERROR" ||
        action == "MOUSE_MOVE" ) {
        if( poll_ms >= 20 ) {
            construction_ui::performance_trace( string_format(
                    "INPUT_POLL_IDLE ms=%lld action=%s", poll_ms, action ) );
        }
        return false;
    }

    construction_ui::performance_trace( string_format(
            "INPUT_ACTION action=%s poll_ms=%lld", action, poll_ms ) );
'''
new = r'''    // This poll runs while ACT_BUILD owns the turn loop.  Do not route it
    // through input_context::handle_input(): that path also updates the global
    // clipped-text hover helper and may synchronously redraw the UI for every
    // queued MOUSE_MOVE.  The performance trace showed those harmless mouse
    // moves taking hundreds of milliseconds and starving the click behind them.
    // Here we only need to distinguish passive pointer motion from an intentional
    // input that should pause work and return control to the editor.
    const int previous_timeout = inp_mngr.get_timeout();
    inp_mngr.set_timeout( 0 );
    const auto poll_started = std::chrono::steady_clock::now();
    const input_event raw_input = inp_mngr.get_input_event( keyboard_mode::keycode );
    const long long poll_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                                  std::chrono::steady_clock::now() - poll_started ).count();
    inp_mngr.set_timeout( previous_timeout );

    if( raw_input.type == input_event_t::timeout || raw_input.type == input_event_t::error ) {
        if( poll_ms >= 20 ) {
            construction_ui::performance_trace( string_format(
                    "RAW_INPUT_IDLE ms=%lld type=%d", poll_ms,
                    static_cast<int>( raw_input.type ) ) );
        }
        return false;
    }

    const bool passive_mouse_move = raw_input.type == input_event_t::mouse &&
                                    raw_input.get_first_input() ==
                                    static_cast<int>( MouseInput::Move );
    if( passive_mouse_move ) {
        if( poll_ms >= 20 ) {
            construction_ui::performance_trace( string_format(
                    "RAW_INPUT_MOVE ms=%lld", poll_ms ) );
        }
        return false;
    }

    construction_ui::performance_trace( string_format(
            "RAW_INPUT_ACTION type=%d code=%d poll_ms=%lld",
            static_cast<int>( raw_input.type ), raw_input.get_first_input(), poll_ms ) );
'''
replace_once( "src/construction_ui.cpp", old, new )

source = Path("src/construction_ui.cpp").read_text()
for needle in [
    '#include "input.h"',
    "inp_mngr.get_input_event( keyboard_mode::keycode )",
    "RAW_INPUT_MOVE",
    "RAW_INPUT_ACTION",
    "interactive_activity_interrupt = true;",
]:
    if needle not in source:
        raise RuntimeError(f"missing source contract: {needle}")
if "context.handle_input( 0 )" in source:
    raise RuntimeError("old activity-side input_context polling is still present")

Path("/tmp/branch_patch_commit_message").write_text(
    "Avoid hover redraws in Construction activity polling [skip ci]\n"
)
print("Raw Construction activity input polling staged")
