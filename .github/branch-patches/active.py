from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new, 1))


# Public lifecycle hooks used by the activity/distraction layers.
replace_once(
    "src/construction_ui.h",
    "bool run();\n\n} // namespace construction_ui\n",
    """bool run();

/** Drop any Construction editor retained across an ACT_BUILD handoff. */
void discard_persistent_editor();
/** Temporarily hide a retained Construction editor while a distraction query owns the screen. */
void suspend_persistent_editor_for_query();
/** Restore the exact retained Construction frame when the distraction is ignored. */
void restore_persistent_editor_after_query();
/** Re-enter the retained Construction editor after its ACT_BUILD completes. */
void resume_persistent_editor_after_activity();

} // namespace construction_ui
""",
)

# Construction workspace: keep the same object and ui_adaptor alive across ACT_BUILD.
p = Path("src/construction_ui.cpp")
text = p.read_text()
text = text.replace(
    """    public:
        construction_workspace();
        bool run();

    private:
        void create_layout( ui_adaptor &ui );
""",
    """    public:
        construction_workspace();
        ~construction_workspace();
        bool run();
        bool activity_handoff_active() const;
        void begin_activity_handoff();
        void resume_activity_handoff();
        void suspend_for_query();
        void restore_after_query();

    private:
        shared_ptr_fast<ui_adaptor> create_or_get_ui_adaptor();
        void create_layout( ui_adaptor &ui );
""",
    1,
)
text = text.replace(
    """        ui_dropdown category_menu;
        ui_dropdown context_menu;
        ui_world_viewport viewport;

        workspace_focus focus = workspace_focus::palette;
""",
    """        ui_dropdown category_menu;
        ui_dropdown context_menu;
        ui_world_viewport viewport;
        shared_ptr_fast<ui_adaptor> ui;
#if !defined(TILES)
        shared_ptr_fast<game::draw_callback_t> overlay;
#endif

        workspace_focus focus = workspace_focus::palette;
""",
    1,
)
text = text.replace(
    """        bool inspector_visible = true;
        bool exit_requested = false;
        bool blink = true;
""",
    """        bool inspector_visible = true;
        bool exit_requested = false;
        bool blink = true;
        bool activity_handoff = false;
        bool ui_hidden = false;
""",
    1,
)
class_end = """        std::optional<construction_build_order> build_order;
};

construction_workspace::construction_workspace() :
"""
if text.count(class_end) != 1:
    raise RuntimeError("construction_ui.cpp: workspace class end changed")
text = text.replace(
    class_end,
    """        std::optional<construction_build_order> build_order;
};

construction_workspace *persistent_workspace = nullptr;

construction_workspace::construction_workspace() :
""",
    1,
)
constructor_end = """    rebuild_palette();
    refresh_active_target();
}

bool construction_workspace::target_is_adjacent( const tripoint_bub_ms &target ) const
"""
if text.count(constructor_end) != 1:
    raise RuntimeError("construction_ui.cpp: constructor tail changed")
lifecycle_impl = """    rebuild_palette();
    refresh_active_target();
}

construction_workspace::~construction_workspace()
{
    viewport.cancel_map_capture();
#if defined(TILES)
    viewport.detach_map_preview();
    clear_ui_tile_previews();
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( false );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( false );
    }
#else
    overlay.reset();
#endif
    if( ui ) {
        ui->set_disable_uis_below( false );
        ui.reset();
    }
    g->invalidate_main_ui_adaptor();
}

shared_ptr_fast<ui_adaptor> construction_workspace::create_or_get_ui_adaptor()
{
    shared_ptr_fast<ui_adaptor> current_ui = ui;
    if( !current_ui ) {
#if defined(TILES)
        ui = current_ui = make_shared_fast<ui_adaptor>( ui_adaptor::disable_uis_below{} );
#else
        ui = current_ui = make_shared_fast<ui_adaptor>();
#endif
        current_ui->on_screen_resize( [this]( ui_adaptor & adaptor ) {
            if( ui_hidden ) {
                adaptor.position( point::zero, point::zero );
                return;
            }
            create_layout( adaptor );
        } );
        current_ui->on_redraw( [this]( ui_adaptor & adaptor ) {
            if( !ui_hidden ) {
                draw( adaptor );
            }
        } );
    }
    return current_ui;
}

bool construction_workspace::activity_handoff_active() const
{
    return activity_handoff;
}

void construction_workspace::begin_activity_handoff()
{
    // ACT_BUILD advances outside this modal input loop.  Keep both this state
    // object and its adaptor registered so gameplay never replaces the editor
    // frame while the construction activity is running.
    activity_handoff = ui != nullptr;
}

void construction_workspace::resume_activity_handoff()
{
    activity_handoff = false;
    ui_hidden = false;
    exit_requested = false;
    build_order.reset();
    category_menu.close();
    context_menu.close();
    transient_status.clear();
    rebuild_palette();
    refresh_active_target();
#if defined(TILES)
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( true );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( true );
    }
#endif
    if( ui ) {
#if defined(TILES)
        ui->set_disable_uis_below( true );
#endif
        ui->mark_resize();
        ui->invalidate_ui();
    }
}

void construction_workspace::suspend_for_query()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return;
    }
    // Distraction warnings should own a clean game frame, exactly like the
    // persistent Vehicle Editor.  Only presentation is suspended; selection,
    // camera, filters, scroll state, and the ACT_BUILD handoff remain intact.
    ui_hidden = true;
    viewport.cancel_map_capture();
#if defined(TILES)
    viewport.detach_map_preview();
    clear_ui_tile_previews();
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( false );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( false );
    }
#else
    overlay.reset();
#endif
    ui->set_disable_uis_below( false );
    ui->mark_resize();
    ui->invalidate_ui();
    g->invalidate_main_ui_adaptor();
    ui_manager::redraw_invalidated();
}

void construction_workspace::restore_after_query()
{
    if( !activity_handoff || !ui_hidden || !ui ) {
        return;
    }
    ui_hidden = false;
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

bool construction_workspace::target_is_adjacent( const tripoint_bub_ms &target ) const
"""
text = text.replace(constructor_end, lifecycle_impl, 1)

# Replace the modal one-shot run with a persistent activity handoff loop.
run_start = text.index("bool construction_workspace::run()\n{")
run_end_marker = "\n}\n\n} // namespace\n"
run_end = text.index(run_end_marker, run_start) + 2
new_run = r'''bool construction_workspace::run()
{
    restore_on_out_of_scope<tripoint_rel_ms> restore_view( you.view_offset );
    on_out_of_scope restore_zoom( [this]() {
        g->set_zoom( original_zoom );
        g->mark_main_ui_adaptor_resize();
    } );

#if defined(TILES)
    if( tilecontext ) {
        tilecontext->set_disable_occlusion( true );
    }
    if( closetilecontext ) {
        closetilecontext->set_disable_occlusion( true );
    }
#else
    g->invalidate_main_ui_adaptor();
#endif

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

    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor();
    ui_hidden = false;
#if defined(TILES)
    current_ui->set_disable_uis_below( true );
#endif
    current_ui->mark_resize();

#if !defined(TILES)
    if( !overlay ) {
        overlay = make_shared_fast<game::draw_callback_t>( [this]() {
            draw_world_overlay();
        } );
        g->add_draw_callback( overlay );
    }
#endif

    while( true ) {
        exit_requested = false;
        build_order.reset();
        while( !exit_requested ) {
#if !defined(TILES)
            g->invalidate_main_ui_adaptor();
#endif
            ui_manager::redraw();
            const std::string action = context.handle_input();
            handle_input( action, context, *current_ui );
        }

        uistate.construction_filter = search;
        if( operation == construction_operation::build && !selected_group.is_null() ) {
            uistate.last_construction = selected_group;
        }

        if( !build_order || !build_order->id.is_valid() ) {
            return true;
        }

        const construction_build_order order = *build_order;
        build_order.reset();
        const ret_val<void> started = order.resume ?
                                      resume_construction_at( you, order.target ) :
                                      start_construction_at( you, order.id.obj(), order.target,
                                                             order.carried_source_only );
        if( !started.success() ) {
            transient_status = started.str();
            rebuild_palette();
            refresh_active_target();
            current_ui->invalidate_ui();
            continue;
        }

        // Starting ACT_BUILD creates/updates the partial construction immediately.
        // Paint that new state before yielding turns to the activity system, then
        // retain this exact editor and adaptor until completion or cancellation.
        refresh_active_target();
        begin_activity_handoff();
        current_ui->invalidate_ui();
        ui_manager::redraw_invalidated();
        return true;
    }
}'''
text = text[:run_start] + new_run + text[run_end:]

# Replace the stack-local wrapper with the same persistent handoff contract as Vehicle Editor.
old_wrapper = """namespace construction_ui
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
"""
new_wrapper = """namespace construction_ui
{

void discard_persistent_editor()
{
    if( persistent_workspace != nullptr ) {
        delete persistent_workspace;
        persistent_workspace = nullptr;
    }
}

void suspend_persistent_editor_for_query()
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->suspend_for_query();
    }
}

void restore_persistent_editor_after_query()
{
    if( persistent_workspace != nullptr ) {
        persistent_workspace->restore_after_query();
    }
}

void resume_persistent_editor_after_activity()
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
{
    if( TERMX < 60 || TERMY < 16 ) {
        discard_persistent_editor();
        return false;
    }

    // Reuse only the editor explicitly retained by its own ACT_BUILD handoff.
    // Any unrelated entry starts from a clean Construction workspace.
    if( persistent_workspace != nullptr &&
        !persistent_workspace->activity_handoff_active() ) {
        discard_persistent_editor();
    }
    if( persistent_workspace == nullptr ) {
        persistent_workspace = new construction_workspace();
    } else {
        persistent_workspace->resume_activity_handoff();
    }

    construction_workspace *const editor = persistent_workspace;
    const bool result = editor->run();
    if( editor->activity_handoff_active() ) {
        return result;
    }

    discard_persistent_editor();
    return result;
}

} // namespace construction_ui
"""
if text.count(old_wrapper) != 1:
    raise RuntimeError("construction_ui.cpp: namespace wrapper changed")
text = text.replace(old_wrapper, new_wrapper, 1)
p.write_text(text)

# Successful ACT_BUILD completion re-enters the retained workspace unless a
# post-special or multiple-construction activity has taken ownership.
replace_once(
    "src/construction.cpp",
    """    if( you->is_avatar() && !you->backlog.empty() &&
        you->backlog.front().id() == ACT_MULTIPLE_CONSTRUCTION ) {
        you->backlog.clear();
        you->assign_activity( ACT_MULTIPLE_CONSTRUCTION );
    }
}
""",
    """    if( you->is_avatar() && !you->backlog.empty() &&
        you->backlog.front().id() == ACT_MULTIPLE_CONSTRUCTION ) {
        you->backlog.clear();
        you->assign_activity( ACT_MULTIPLE_CONSTRUCTION );
    }
    if( you->is_avatar() ) {
        if( you->activity ) {
            // A post-special or queued multi-activity owns the next UI flow.
            construction_ui::discard_persistent_editor();
        } else {
            construction_ui::resume_persistent_editor_after_activity();
        }
    }
}
""",
)

# Explicit activity cancellation has no completion re-entry.  Keep a retained
# Construction editor only for auto-resume pauses such as stamina recovery.
replace_once(
    "src/player_activity.cpp",
    '#include "construction.h"\n',
    '#include "construction.h"\n#include "construction_ui.h"\n',
)
replace_once(
    "src/player_activity.cpp",
    """    if( id() == ACT_VEHICLE ) {
        // Cancellation has no vehicle_finish()/exam_vehicle() re-entry. Drop
        // the retained editor adaptor immediately so it cannot stay over the map.
        veh_interact::discard_persistent_editor();
    }
""",
    """    if( id() == ACT_VEHICLE ) {
        // Cancellation has no vehicle_finish()/exam_vehicle() re-entry. Drop
        // the retained editor adaptor immediately so it cannot stay over the map.
        veh_interact::discard_persistent_editor();
    }
    if( id() == ACT_BUILD && !auto_resume ) {
        // A stopped construction has no completion callback to re-enter the
        // workspace.  Auto-resume pauses retain it until ACT_BUILD continues.
        construction_ui::discard_persistent_editor();
    }
""",
)

# The global activity-distraction popup temporarily owns the screen.  Hide the
# retained Construction editor exactly as the Vehicle Editor already does.
replace_once(
    "src/game.cpp",
    '#include "construction.h"\n#include "construction_group.h"\n',
    '#include "construction.h"\n#include "construction_group.h"\n#include "construction_ui.h"\n',
)
replace_once(
    "src/game.cpp",
    """    veh_interact::suspend_persistent_editor_for_query();
    on_out_of_scope restore_vehicle_editor_after_query( []() {
        veh_interact::restore_persistent_editor_after_query();
    } );

    const std::string &action = query_popup()
""",
    """    veh_interact::suspend_persistent_editor_for_query();
    construction_ui::suspend_persistent_editor_for_query();
    on_out_of_scope restore_vehicle_editor_after_query( []() {
        veh_interact::restore_persistent_editor_after_query();
    } );
    on_out_of_scope restore_construction_editor_after_query( []() {
        construction_ui::restore_persistent_editor_after_query();
    } );

    const std::string &action = query_popup()
""",
)

# Source-contract audit.  This is intentionally not a build/test step.
checks = {
    "src/construction_ui.cpp": [
        "construction_workspace *persistent_workspace = nullptr;",
        "make_shared_fast<ui_adaptor>( ui_adaptor::disable_uis_below{} )",
        "begin_activity_handoff();",
        "construction_ui::resume_persistent_editor_after_activity",
    ],
    "src/construction.cpp": ["construction_ui::resume_persistent_editor_after_activity();"],
    "src/player_activity.cpp": ["id() == ACT_BUILD && !auto_resume"],
    "src/game.cpp": ["construction_ui::suspend_persistent_editor_for_query();"],
}
for path, needles in checks.items():
    data = Path(path).read_text()
    for needle in needles:
        if needle not in data:
            raise RuntimeError(f"{path}: missing source contract {needle!r}")

Path("/tmp/branch_patch_commit_message").write_text(
    "Keep Construction editor active during builds [skip ci]\n"
)
print("Persistent Construction ACT_BUILD handoff staged")
