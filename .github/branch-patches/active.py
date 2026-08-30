from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:140]!r}")
    p.write_text(text.replace(old, new, 1))


# Public hooks used by the main turn loop while a Construction-owned ACT_BUILD
# is advancing behind the retained workspace.
replace_once(
    "src/construction_ui.h",
    """/** Re-enter the retained Construction editor after its ACT_BUILD completes. */
void resume_persistent_editor_after_activity();

} // namespace construction_ui
""",
    """/** Re-enter the retained Construction editor after its ACT_BUILD completes. */
void resume_persistent_editor_after_activity();
/** True only while a retained Construction workspace currently owns ACT_BUILD. */
bool persistent_editor_activity_active();
/** Poll one nonblocking Construction input while ACT_BUILD owns the turn loop. */
bool handle_persistent_editor_activity_input();
/** Keep the retained workspace when cancellation was caused by an editor interaction. */
bool preserve_persistent_editor_on_activity_cancel();

} // namespace construction_ui
""",
)

path = "src/construction_ui.cpp"
p = Path(path)
text = p.read_text()

old = """        void suspend_for_query();
        void restore_after_query();

    private:
"""
new = """        void suspend_for_query();
        void restore_after_query();
        bool poll_activity_input();
        bool preserve_on_activity_cancel() const;

    private:
"""
if text.count(old) != 1:
    raise RuntimeError("construction_ui.cpp: public handoff block changed")
text = text.replace(old, new, 1)

old = """        bool activity_handoff = false;
        bool ui_hidden = false;
        bool handoff_repaint_pending = false;
"""
new = """        bool activity_handoff = false;
        bool ui_hidden = false;
        bool handoff_repaint_pending = false;
        bool interactive_activity_interrupt = false;
"""
if text.count(old) != 1:
    raise RuntimeError("construction_ui.cpp: handoff bool block changed")
text = text.replace(old, new, 1)

anchor = """void construction_workspace::restore_after_query()
{
    if( !activity_handoff || !ui_hidden || !ui ) {
        return;
    }
    ui_hidden = false;
    // The popup overwrote the editor, so this is one of the few redraws that
    // must be allowed while ACT_BUILD is still running.
    handoff_repaint_pending = true;
#if defined(TILES)
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( true );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( true );
    }
    ui->set_disable_uis_below( true );
#else
    if( !overlay ) {
        overlay = make_shared_fast<game::draw_callback_t>( [this]() {
            draw_world_overlay();
        } );
        g->add_draw_callback( overlay );
    }
#endif
    ui->mark_resize();
    ui->invalidate_ui();
    ui_manager::redraw_invalidated();
    g->invalidate_main_ui_adaptor();
}

"""
if text.count(anchor) != 1:
    raise RuntimeError("construction_ui.cpp: restore_after_query body changed")
addition = anchor + r'''bool construction_workspace::preserve_on_activity_cancel() const
{
    return interactive_activity_interrupt;
}

bool construction_workspace::poll_activity_input()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return false;
    }

    // ACT_BUILD normally uses the gameplay activity input context, which means
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

    const std::string action = context.handle_input( 0 );
    if( action.empty() || action == "TIMEOUT" || action == "ERROR" ||
        action == "MOUSE_MOVE" ) {
        return false;
    }

    interactive_activity_interrupt = true;
    you.cancel_activity();
    interactive_activity_interrupt = false;

    // Direct Construction actions leave an unfinished partial_con behind.  If
    // cancellation handed control to some other activity, do not open a modal
    // editor on top of it; the normal activity lifecycle will resolve that case.
    if( you.activity ) {
        return true;
    }

    g->wait_popup_reset();
    resume_activity_handoff();
    transient_status = _( "Construction paused.  The unfinished work can be continued from this tile." );
    if( ui ) {
        ui->invalidate_ui();
    }
    return true;
}

'''
text = text.replace(anchor, addition, 1)

old = """void resume_persistent_editor_after_activity()
{
    if( persistent_workspace == nullptr ||
        !persistent_workspace->activity_handoff_active() ) {
        return;
    }
    if( TERMX < 60 || TERMY < 16 ) {
        discard_persistent_editor();
        return;
    }
    run();
}

bool run()
"""
new = """void resume_persistent_editor_after_activity()
{
    if( persistent_workspace == nullptr ||
        !persistent_workspace->activity_handoff_active() ) {
        return;
    }
    if( TERMX < 60 || TERMY < 16 ) {
        discard_persistent_editor();
        return;
    }
    run();
}

bool persistent_editor_activity_active()
{
    return persistent_workspace != nullptr &&
           persistent_workspace->activity_handoff_active();
}

bool preserve_persistent_editor_on_activity_cancel()
{
    return persistent_workspace != nullptr &&
           persistent_workspace->preserve_on_activity_cancel();
}

bool handle_persistent_editor_activity_input()
{
    if( persistent_workspace == nullptr ||
        !persistent_workspace->activity_handoff_active() ) {
        return false;
    }

    construction_workspace *const editor = persistent_workspace;
    if( !editor->poll_activity_input() ) {
        return false;
    }

    // A deliberate editor interaction paused ACT_BUILD.  Re-enter the exact
    // workspace now, rather than waiting for the rest of the old activity to
    // finish.  The input that caused the pause is intentionally consumed; the
    // next input operates normally on the live editor.
    if( persistent_workspace == editor &&
        !editor->activity_handoff_active() ) {
        editor->run();
        if( persistent_workspace == editor &&
            !editor->activity_handoff_active() ) {
            discard_persistent_editor();
        }
    }
    return true;
}

bool run()
"""
if text.count(old) != 1:
    raise RuntimeError("construction_ui.cpp: namespace lifecycle block changed")
text = text.replace(old, new, 1)
p.write_text(text)

# A UI-driven pause must not destroy the retained editor from the generic
# player_activity cancellation hook.
replace_once(
    "src/player_activity.cpp",
    """    if( id() == ACT_BUILD && !auto_resume ) {
        // A stopped construction has no completion callback to re-enter the
        // workspace.  Auto-resume pauses retain it until ACT_BUILD continues.
        construction_ui::discard_persistent_editor();
    }
""",
    """    if( id() == ACT_BUILD && !auto_resume &&
        !construction_ui::preserve_persistent_editor_on_activity_cancel() ) {
        // A stopped construction has no completion callback to re-enter the
        // workspace.  Auto-resume and an intentional editor interaction retain
        // it so unfinished work can continue in the same Construction frame.
        construction_ui::discard_persistent_editor();
    }
""",
)

# Route activity polling to the visible Construction editor instead of the
# gameplay context, and make its progress indicator visibly advance instead of
# sitting on one percentage for five in-game minutes.
replace_once(
    "src/do_turn.cpp",
    '#include "coordinates.h"\n',
    '#include "coordinates.h"\n#include "construction_ui.h"\n',
)
replace_once(
    "src/do_turn.cpp",
    """            if( ( now - start ).count() > 100 ) {
                handle_key_blocking_activity();
                start = now;
            }
""",
    """            if( ( now - start ).count() > 100 ) {
                if( construction_ui::persistent_editor_activity_active() ) {
                    construction_ui::handle_persistent_editor_activity_input();
                } else {
                    handle_key_blocking_activity();
                }
                start = now;
            }
""",
)
replace_once(
    "src/do_turn.cpp",
    """        if( u.activity.is_interruptible() && u.activity.interruptable_with_kb ) {
            wait_message += string_format( _( "\\n%s to interrupt" ), press_x( ACTION_PAUSE ) );
        }
        if( u.activity.id() == ACT_AUTODRIVE ) {
            wait_refresh_rate = 1_turns;
        } else if( u.activity.id() == ACT_FIRSTAID ) {
            wait_refresh_rate = 5_turns;
        } else {
            wait_refresh_rate = 5_minutes;
        }
""",
    """        const bool construction_editor_activity =
            construction_ui::persistent_editor_activity_active();
        if( u.activity.is_interruptible() && u.activity.interruptable_with_kb ) {
            wait_message += construction_editor_activity ?
                            string_format( _( "\\nClick the editor or %s to pause and edit" ),
                                           press_x( ACTION_PAUSE ) ) :
                            string_format( _( "\\n%s to interrupt" ), press_x( ACTION_PAUSE ) );
        }
        if( construction_editor_activity ) {
            wait_refresh_rate = 30_seconds;
        } else if( u.activity.id() == ACT_AUTODRIVE ) {
            wait_refresh_rate = 1_turns;
        } else if( u.activity.id() == ACT_FIRSTAID ) {
            wait_refresh_rate = 5_turns;
        } else {
            wait_refresh_rate = 5_minutes;
        }
""",
)

# Source-only contracts.  User does local compilation/testing.
checks = {
    "src/construction_ui.h": [
        "persistent_editor_activity_active",
        "handle_persistent_editor_activity_input",
        "preserve_persistent_editor_on_activity_cancel",
    ],
    "src/construction_ui.cpp": [
        "bool construction_workspace::poll_activity_input()",
        'context.handle_input( 0 )',
        'action == "MOUSE_MOVE"',
        "interactive_activity_interrupt = true;",
        "Construction paused.",
    ],
    "src/player_activity.cpp": [
        "!construction_ui::preserve_persistent_editor_on_activity_cancel()",
    ],
    "src/do_turn.cpp": [
        "construction_ui::handle_persistent_editor_activity_input();",
        "wait_refresh_rate = 30_seconds;",
        "Click the editor or %s to pause and edit",
    ],
}
for filename, needles in checks.items():
    source = Path(filename).read_text()
    for needle in needles:
        if needle not in source:
            raise RuntimeError(f"{filename}: missing contract {needle!r}")

Path("/tmp/branch_patch_commit_message").write_text(
    "Make retained Construction activities responsive [skip ci]\n"
)
print("Responsive retained Construction activity input staged")
