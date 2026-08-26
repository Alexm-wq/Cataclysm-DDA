from pathlib import Path


def replace_exact(path: Path, old: str, new: str, label: str, expected: int = 1) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: {label}: expected {expected} match(es), got {count}")
    path.write_text(text.replace(old, new, expected))


header = Path("src/veh_interact.h")
replace_exact(
    header,
    '''        static player_activity run( map &here,  vehicle &veh, const point_rel_ms &p );\n\n        /** Prompt for a part matching the selector function */\n''',
    '''        static player_activity run( map &here,  vehicle &veh, const point_rel_ms &p );\n        /** Drop any editor frame retained for an interrupted/aborted ACT_VEHICLE handoff. */\n        static void discard_persistent_editor();\n\n        /** Prompt for a part matching the selector function */\n''',
    "public discard hook",
)
replace_exact(
    header,
    '''        weak_ptr_fast<ui_adaptor> ui;\n\n        std::optional<std::string> title;\n''',
    '''        // Keep the adaptor alive while ACT_VEHICLE runs so the editor frame is never\n        // torn down to the world view between an action and automatic editor re-entry.\n        shared_ptr_fast<ui_adaptor> ui;\n        bool activity_handoff = false;\n        bool first_frame_after_handoff = false;\n\n        std::optional<std::string> title;\n''',
    "strong persistent adaptor",
)
replace_exact(
    header,
    '''        vehicle *veh;\n        const inventory *crafting_inv;\n        input_context main_context;\n''',
    '''        static veh_interact *persistent_editor;\n        void begin_activity_handoff();\n        void resume_activity_handoff( map &here );\n\n        vehicle *veh;\n        const inventory *crafting_inv;\n        input_context main_context;\n''',
    "handoff declarations",
)

cpp = Path("src/veh_interact.cpp")
replace_exact(
    cpp,
    '''static int vehicle_editor_view_mode_latched = 0;\n\nplayer_activity veh_interact::serialize_activity( map &here )\n''',
    '''static int vehicle_editor_view_mode_latched = 0;\n\nveh_interact *veh_interact::persistent_editor = nullptr;\n\nplayer_activity veh_interact::serialize_activity( map &here )\n''',
    "persistent editor definition",
)
replace_exact(
    cpp,
    '''player_activity veh_interact::run( map &here, vehicle &veh, const point_rel_ms &p )\n{\n    veh_interact vehint( here, veh, p );\n    vehint.do_main_loop( here );\n    return vehint.serialize_activity( here );\n}\n''',
    '''void veh_interact::discard_persistent_editor()\n{\n    if( persistent_editor != nullptr ) {\n        delete persistent_editor;\n        persistent_editor = nullptr;\n    }\n}\n\nvoid veh_interact::begin_activity_handoff()\n{\n    // ACT_VEHICLE completes outside this input loop and then re-enters through\n    // game::exam_vehicle().  Keep this editor and its ui_adaptor alive so the\n    // map can never become the visible frame between those two calls.\n    activity_handoff = ui != nullptr;\n    first_frame_after_handoff = false;\n}\n\nvoid veh_interact::resume_activity_handoff( map &here )\n{\n    // The vehicle may have gained, lost, or replaced parts at activity completion.\n    // Preserve camera/mount state, but throw away every command-side pointer/list\n    // that could refer to the pre-activity part array before the first fresh draw.\n    sel_cmd = ' ';\n    sel_vehicle_part = nullptr;\n    sel_vpart_info = nullptr;\n    install_info.reset();\n    remove_info.reset();\n    refuel_info.reset();\n    refill_target = item_location();\n    refill_part_indices.clear();\n    refill_targets.clear();\n    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n    pending_editor_action.clear();\n    msg.reset();\n    w_msg_scroll_offset = 0;\n    ui_hidden = false;\n\n    count_durability();\n    cache_tool_availability();\n    move_cursor( here, point_rel_ms::zero );\n    reset_part_selection();\n\n    // Keep activity_handoff armed until do_main_loop is ready to present the\n    // rebuilt frame.  That first frame gets the same temporary lower-UI redraw\n    // barrier used by the persistent inventory workspace.\n    first_frame_after_handoff = true;\n}\n\nplayer_activity veh_interact::run( map &here, vehicle &veh, const point_rel_ms &p )\n{\n    // Reuse an editor only for the exact ACT_VEHICLE handoff that retained it.\n    // Any unrelated/open-different-vehicle entry starts from a clean workspace.\n    if( persistent_editor != nullptr &&\n        ( persistent_editor->veh != &veh || !persistent_editor->activity_handoff ) ) {\n        discard_persistent_editor();\n    }\n\n    if( persistent_editor == nullptr ) {\n        persistent_editor = new veh_interact( here, veh, p );\n    } else {\n        persistent_editor->resume_activity_handoff( here );\n    }\n\n    veh_interact *const editor = persistent_editor;\n    editor->do_main_loop( here );\n    player_activity result = editor->serialize_activity( here );\n\n    if( result && result.id() == ACT_VEHICLE ) {\n        editor->begin_activity_handoff();\n        return result;\n    }\n\n    discard_persistent_editor();\n    return result;\n}\n''',
    "persistent run lifecycle",
)
replace_exact(
    cpp,
    '''shared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor( map &here )\n{\n    shared_ptr_fast<ui_adaptor> current_ui = ui.lock();\n    if( !current_ui ) {\n        ui = current_ui = make_shared_fast<ui_adaptor>();\n''',
    '''shared_ptr_fast<ui_adaptor> veh_interact::create_or_get_ui_adaptor( map &here )\n{\n    shared_ptr_fast<ui_adaptor> current_ui = ui;\n    if( !current_ui ) {\n        ui = current_ui = make_shared_fast<ui_adaptor>();\n''',
    "strong adaptor access",
)
replace_exact(
    cpp,
    '''    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );\n\n    while( !finish ) {\n        calc_overview( here );\n        if( install_info ) {\n            refresh_install_candidates();\n            sync_install_selection( here );\n        }\n        ui_manager::redraw();\n''',
    '''    shared_ptr_fast<ui_adaptor> current_ui = create_or_get_ui_adaptor( here );\n\n    if( first_frame_after_handoff ) {\n        // The activity has completed and resume_activity_handoff() has rebuilt all\n        // pointer-bearing editor state.  Release the handoff only when we are\n        // immediately ready to paint the replacement editor frame.\n        activity_handoff = false;\n    }\n\n    while( !finish ) {\n        calc_overview( here );\n        if( install_info ) {\n            refresh_install_candidates();\n            sync_install_selection( here );\n        }\n        if( first_frame_after_handoff ) {\n            // Do not invalidate/redraw the world underneath the retained editor\n            // before its first post-activity frame is ready.  This mirrors the\n            // persistent inventory handoff fix and removes the one-frame map flash.\n            current_ui->set_disable_uis_below( true );\n            current_ui->invalidate_ui();\n            ui_manager::redraw_invalidated();\n            current_ui->set_disable_uis_below( false );\n            g->invalidate_main_ui_adaptor();\n            first_frame_after_handoff = false;\n        } else {\n            ui_manager::redraw();\n        }\n''',
    "first post-activity redraw barrier",
)
replace_exact(
    cpp,
    '''        if( refuel_info ) {\n''',
    '''        // Escape dismisses transient editor menus before it is allowed to\n        // close a mode or the vehicle editor itself.\n        if( action == "QUIT" && editor_context_open ) {\n            close_editor_context_menu();\n            continue;\n        }\n        if( action == "QUIT" && open_editor_dropdown != editor_dropdown::none ) {\n            open_editor_dropdown = editor_dropdown::none;\n            continue;\n        }\n\n        if( refuel_info ) {\n''',
    "escape menu priority",
)
replace_exact(
    cpp,
    '''void veh_interact::open_editor_context_menu( map &here, const point &pos,\n        const editor_context_surface surface )\n{\n    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n    editor_context_target = surface;\n''',
    '''void veh_interact::open_editor_context_menu( map &here, const point &pos,\n        const editor_context_surface surface )\n{\n    // Context menus are mutually exclusive across the schematic, inspector, and\n    // filter dropdowns.  Redraw once with the old transient UI removed before\n    // placing a menu on another surface so cached curses contents cannot leave\n    // two menus visible at the same time.\n    const bool had_transient_menu = editor_context_open ||\n                                    open_editor_dropdown != editor_dropdown::none;\n    close_editor_context_menu();\n    open_editor_dropdown = editor_dropdown::none;\n    if( had_transient_menu && ui ) {\n        ui->invalidate_ui();\n        ui_manager::redraw_invalidated();\n    }\n    editor_context_target = surface;\n''',
    "exclusive context surfaces",
)
replace_exact(
    cpp,
    '''    sel_vehicle_part = &veh->part( refill_part_indices.front() );\n    sel_vpart_info = &sel_vehicle_part->info();\n    sel_cmd = 'f';\n    close_refuel_mode();\n    return true;\n''',
    '''    sel_vehicle_part = &veh->part( refill_part_indices.front() );\n    sel_vpart_info = &sel_vehicle_part->info();\n    sel_cmd = 'f';\n    // Keep the already-rendered transactional overlay intact through the\n    // activity handoff.  resume_activity_handoff() closes it only after the\n    // refill has completed and the refreshed editor frame is ready.\n    return true;\n''',
    "keep refuel frame through handoff",
)

activity = Path("src/activity_handlers.cpp")
text = activity.read_text()
old = '''    if( act->is_null() ) {\n        if( npc *guy = dynamic_cast<npc *>( you ) ) {\n'''
new = '''    if( act->is_null() ) {\n        veh_interact::discard_persistent_editor();\n        if( npc *guy = dynamic_cast<npc *>( you ) ) {\n'''
if text.count(old) != 1:
    raise SystemExit(f"{activity}: null vehicle completion cleanup: expected 1 match, got {text.count(old)}")
text = text.replace(old, new, 1)

old = '''                if( !resume_for_multi_activities( *you ) ) {\n                    point_rel_ms int_p( act->values[ 2 ], act->values[ 3 ] );\n                    if( vp->vehicle().is_appliance() ) {\n                        g->exam_appliance( vp->vehicle(), int_p );\n                    } else {\n                        g->exam_vehicle( vp->vehicle(), int_p );\n                    }\n                }\n                return;\n'''
new = '''                if( !resume_for_multi_activities( *you ) ) {\n                    point_rel_ms int_p( act->values[ 2 ], act->values[ 3 ] );\n                    if( vp->vehicle().is_appliance() ) {\n                        g->exam_appliance( vp->vehicle(), int_p );\n                    } else {\n                        g->exam_vehicle( vp->vehicle(), int_p );\n                    }\n                } else {\n                    // Another queued activity won ownership of the UI flow, so the\n                    // retained editor must not remain registered underneath it.\n                    veh_interact::discard_persistent_editor();\n                }\n                return;\n'''
if text.count(old) != 1:
    raise SystemExit(f"{activity}: resumed multi-activity cleanup: expected 1 match, got {text.count(old)}")
text = text.replace(old, new, 1)

old = '''            } else {\n                dbg( D_ERROR ) << "game:process_activity: ACT_VEHICLE: vehicle not found";\n'''
new = '''            } else {\n                veh_interact::discard_persistent_editor();\n                dbg( D_ERROR ) << "game:process_activity: ACT_VEHICLE: vehicle not found";\n'''
if text.count(old) != 1:
    raise SystemExit(f"{activity}: missing vehicle cleanup: expected 1 match, got {text.count(old)}")
text = text.replace(old, new, 1)
activity.write_text(text)

player_activity = Path("src/player_activity.cpp")
replace_exact(
    player_activity,
    '''#include "uilist.h"\n#include "uistate.h"\n#include "units.h"\n''',
    '''#include "uilist.h"\n#include "uistate.h"\n#include "units.h"\n#include "veh_interact.h"\n''',
    "player activity vehicle editor cleanup include",
)
replace_exact(
    player_activity,
    '''void player_activity::canceled( Character &who )\n{\n    if( *this && actor ) {\n''',
    '''void player_activity::canceled( Character &who )\n{\n    if( id() == ACT_VEHICLE ) {\n        // Cancellation has no vehicle_finish()/exam_vehicle() re-entry.  Drop\n        // the retained editor adaptor immediately so it cannot stay over the map.\n        veh_interact::discard_persistent_editor();\n    }\n    if( *this && actor ) {\n''',
    "cancelled ACT_VEHICLE cleanup",
)

status = Path("doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md")
replace_exact(
    status,
    '''### Context actions\n\n- [x] Vehicle editor context actions implemented.\n''',
    '''### Context actions\n\n- [x] Vehicle editor context actions implemented.\n- [x] Context/dropdown exclusivity hardened: Esc dismisses an open right-click/filter menu before closing the editor, and opening a context menu on another editor surface clears/redraws the previous transient menu first.\n''',
    "context usability status",
)
replace_exact(
    status,
    '''### Live install pane\n''',
    '''### Activity handoff and redraw stability\n\n- [x] `ACT_VEHICLE` install/repair/remove/refuel handoffs retain the existing vehicle editor object and `ui_adaptor` instead of tearing the editor down to the world view and reconstructing it afterward.\n- [x] The first post-activity editor frame uses the same temporary lower-UI redraw barrier pattern proven by the persistent inventory workspace, preventing a one-frame map flash while preserving normal activity timing and completion mechanics.\n- [x] Part/pointer-bearing command state is rebuilt after vehicle mutation before that first fresh frame; cancellation, complete dismantling, missing vehicles, and queued multi-activity handoffs explicitly discard the retained editor.\n\n### Live install pane\n''',
    "handoff status section",
)

print("vehicle editor handoff patch applied")
