from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:140]!r}")
    p.write_text(text.replace(old, new, 1))


# Public diagnostics API.  Kept deliberately tiny so do_turn can report the
# expensive phase without knowing anything about the workspace implementation.
replace_once(
    "src/construction_ui.h",
    "#define CATA_SRC_CONSTRUCTION_UI_H\n\nnamespace construction_ui\n",
    "#define CATA_SRC_CONSTRUCTION_UI_H\n\n#include <string>\n\nnamespace construction_ui\n",
)
replace_once(
    "src/construction_ui.h",
    """/** Keep the retained workspace when cancellation was caused by an editor interaction. */
bool preserve_persistent_editor_on_activity_cancel();

} // namespace construction_ui
""",
    """/** Keep the retained workspace when cancellation was caused by an editor interaction. */
bool preserve_persistent_editor_on_activity_cancel();
/** True while detailed Construction timing should be collected. */
bool performance_trace_active();
/** Append one timestamped record to config/construction_ui_perf.log. */
void performance_trace( const std::string &message );

} // namespace construction_ui
""",
)

# Dedicated trace sink and workspace-level timings.
replace_once(
    "src/construction_ui.cpp",
    "#include <algorithm>\n#include <map>\n",
    "#include <algorithm>\n#include <chrono>\n#include <fstream>\n#include <map>\n",
)
replace_once(
    "src/construction_ui.cpp",
    '#include "output.h"\n#include "point.h"\n',
    '#include "output.h"\n#include "path_info.h"\n#include "point.h"\n',
)
replace_once(
    "src/construction_ui.cpp",
    """        bool handoff_repaint_pending = false;
        bool interactive_activity_interrupt = false;

        int palette_width = 0;
""",
    """        bool handoff_repaint_pending = false;
        bool interactive_activity_interrupt = false;
        int skipped_handoff_redraws = 0;

        int palette_width = 0;
""",
)
replace_once(
    "src/construction_ui.cpp",
    """            if( activity_handoff && !handoff_repaint_pending ) {
                return;
            }
            draw( adaptor );
            handoff_repaint_pending = false;
""",
    """            if( activity_handoff && !handoff_repaint_pending ) {
                ++skipped_handoff_redraws;
                return;
            }
            const auto redraw_started = std::chrono::steady_clock::now();
            draw( adaptor );
            const long long redraw_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                                            std::chrono::steady_clock::now() - redraw_started ).count();
            construction_ui::performance_trace( string_format(
                    "UI_REDRAW ms=%lld handoff=%d hidden=%d skipped_since_resume=%d",
                    redraw_ms, activity_handoff ? 1 : 0, ui_hidden ? 1 : 0,
                    skipped_handoff_redraws ) );
            handoff_repaint_pending = false;
""",
)
replace_once(
    "src/construction_ui.cpp",
    """void construction_workspace::begin_activity_handoff()
{
    // Keep this exact workspace and adaptor registered while ACT_BUILD advances.
    // Paint the newly-created partial construction once, then let the frame stay
    // dormant until a query restore or completion actually changes UI state.
    activity_handoff = ui != nullptr;
    handoff_repaint_pending = activity_handoff;
}
""",
    """void construction_workspace::begin_activity_handoff()
{
    // Keep this exact workspace and adaptor registered while ACT_BUILD advances.
    // Paint the newly-created partial construction once, then let the frame stay
    // dormant until a query restore or completion actually changes UI state.
    activity_handoff = ui != nullptr;
    handoff_repaint_pending = activity_handoff;
    skipped_handoff_redraws = 0;
    construction_ui::performance_trace( string_format(
            "HANDOFF_BEGIN activity=%s target=%s group=%s",
            you.activity.id().str(), selected_target ? selected_target->to_string() : "none",
            selected_group.is_null() ? "none" : selected_group.str() ) );
}
""",
)
replace_once(
    "src/construction_ui.cpp",
    """    transient_status.clear();
    rebuild_palette();
    refresh_active_target();
#if defined(TILES)
""",
    """    transient_status.clear();
    const auto resume_started = std::chrono::steady_clock::now();
    rebuild_palette();
    const auto palette_done = std::chrono::steady_clock::now();
    refresh_active_target();
    const auto target_done = std::chrono::steady_clock::now();
    construction_ui::performance_trace( string_format(
            "HANDOFF_RESUME palette_ms=%lld target_ms=%lld total_ms=%lld skipped_redraws=%d",
            std::chrono::duration_cast<std::chrono::milliseconds>( palette_done - resume_started ).count(),
            std::chrono::duration_cast<std::chrono::milliseconds>( target_done - palette_done ).count(),
            std::chrono::duration_cast<std::chrono::milliseconds>( target_done - resume_started ).count(),
            skipped_handoff_redraws ) );
    skipped_handoff_redraws = 0;
#if defined(TILES)
""",
)
replace_once(
    "src/construction_ui.cpp",
    """void construction_workspace::suspend_for_query()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return;
    }
""",
    """void construction_workspace::suspend_for_query()
{
    if( !activity_handoff || ui_hidden || !ui ) {
        return;
    }
    const auto suspend_started = std::chrono::steady_clock::now();
    construction_ui::performance_trace( string_format(
            "QUERY_SUSPEND_BEGIN skipped_redraws=%d", skipped_handoff_redraws ) );
""",
)
replace_once(
    "src/construction_ui.cpp",
    """    g->invalidate_main_ui_adaptor();
    ui_manager::redraw_invalidated();
}

void construction_workspace::restore_after_query()
""",
    """    g->invalidate_main_ui_adaptor();
    ui_manager::redraw_invalidated();
    construction_ui::performance_trace( string_format(
            "QUERY_SUSPEND_END ms=%lld",
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - suspend_started ).count() ) );
}

void construction_workspace::restore_after_query()
""",
)
replace_once(
    "src/construction_ui.cpp",
    """void construction_workspace::restore_after_query()
{
    if( !activity_handoff || !ui_hidden || !ui ) {
        return;
    }
    ui_hidden = false;
""",
    """void construction_workspace::restore_after_query()
{
    if( !activity_handoff || !ui_hidden || !ui ) {
        return;
    }
    const auto restore_started = std::chrono::steady_clock::now();
    construction_ui::performance_trace( "QUERY_RESTORE_BEGIN" );
    ui_hidden = false;
""",
)
replace_once(
    "src/construction_ui.cpp",
    """    ui_manager::redraw_invalidated();
    g->invalidate_main_ui_adaptor();
}

bool construction_workspace::preserve_on_activity_cancel() const
""",
    """    ui_manager::redraw_invalidated();
    g->invalidate_main_ui_adaptor();
    construction_ui::performance_trace( string_format(
            "QUERY_RESTORE_END ms=%lld",
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - restore_started ).count() ) );
}

bool construction_workspace::preserve_on_activity_cancel() const
""",
)
replace_once(
    "src/construction_ui.cpp",
    """    const std::string action = context.handle_input( 0 );
    if( action.empty() || action == "TIMEOUT" || action == "ERROR" ||
        action == "MOUSE_MOVE" ) {
        return false;
    }

    interactive_activity_interrupt = true;
    you.cancel_activity();
    interactive_activity_interrupt = false;
""",
    """    const auto poll_started = std::chrono::steady_clock::now();
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
    const auto cancel_started = std::chrono::steady_clock::now();
    interactive_activity_interrupt = true;
    you.cancel_activity();
    interactive_activity_interrupt = false;
    construction_ui::performance_trace( string_format(
            "INPUT_CANCEL_ACTIVITY ms=%lld remaining_activity=%s",
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - cancel_started ).count(),
            you.activity ? you.activity.id().str() : "none" ) );
""",
)
replace_once(
    "src/construction_ui.cpp",
    """    g->wait_popup_reset();
    resume_activity_handoff();
    transient_status = _( "Construction paused.  The unfinished work can be continued from this tile." );
""",
    """    g->wait_popup_reset();
    const auto editor_resume_started = std::chrono::steady_clock::now();
    resume_activity_handoff();
    construction_ui::performance_trace( string_format(
            "INPUT_EDITOR_RESUME ms=%lld",
            std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - editor_resume_started ).count() ) );
    transient_status = _( "Construction paused.  The unfinished work can be continued from this tile." );
""",
)

# Trace implementation and lifecycle events live at the public namespace boundary.
replace_once(
    "src/construction_ui.cpp",
    """namespace construction_ui
{

void discard_persistent_editor()
""",
    """namespace construction_ui
{

namespace
{
std::ofstream &performance_trace_stream()
{
    static std::ofstream stream;
    static bool initialized = false;
    if( !initialized ) {
        initialized = true;
        std::string directory = PATH_INFO::config_dir();
        if( !directory.empty() && directory.back() != '/' && directory.back() != '\\\\' ) {
            directory.push_back( '/' );
        }
        stream.open( directory + "construction_ui_perf.log", std::ios::out | std::ios::trunc );
        if( !stream ) {
            stream.clear();
            stream.open( "construction_ui_perf.log", std::ios::out | std::ios::trunc );
        }
        if( stream ) {
            stream << "# Construction UI performance trace\\n";
            stream.flush();
        }
    }
    return stream;
}
} // namespace

bool performance_trace_active()
{
    return persistent_workspace != nullptr && persistent_workspace->activity_handoff_active();
}

void performance_trace( const std::string &message )
{
    static const auto origin = std::chrono::steady_clock::now();
    static unsigned long long sequence = 0;
    std::ofstream &stream = performance_trace_stream();
    if( !stream ) {
        return;
    }
    const long long elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                                     std::chrono::steady_clock::now() - origin ).count();
    stream << elapsed_ms << "ms #" << ++sequence << ' ' << message << '\\n';
    stream.flush();
}

void discard_persistent_editor()
""",
)
replace_once(
    "src/construction_ui.cpp",
    """void discard_persistent_editor()
{
    if( persistent_workspace != nullptr ) {
        delete persistent_workspace;
        persistent_workspace = nullptr;
    }
}
""",
    """void discard_persistent_editor()
{
    if( persistent_workspace != nullptr ) {
        performance_trace( "WORKSPACE_DISCARD" );
        delete persistent_workspace;
        persistent_workspace = nullptr;
    }
}
""",
)

# Turn-loop phase timings.  These are emitted only while the retained editor owns ACT_BUILD.
replace_once(
    "src/do_turn.cpp",
    """    avatar &u = get_avatar();
    map &m = get_map();
    // If controlling a vehicle that is owned by someone else
""",
    """    avatar &u = get_avatar();
    map &m = get_map();
    const bool construction_perf = construction_ui::performance_trace_active();
    const auto construction_turn_started = std::chrono::steady_clock::now();
    if( construction_perf ) {
        construction_ui::performance_trace( string_format(
                "TURN_BEGIN moves=%d activity=%s", u.get_moves(), u.activity.id().str() ) );
    }
    // If controlling a vehicle that is owned by someone else
""",
)
replace_once(
    "src/do_turn.cpp",
    """    g->perhaps_add_random_npc( /* ignore_spawn_timers_and_rates = */ false );
    while( u.get_moves() > 0 && u.activity ) {
        u.activity.do_turn( u );
    }

    // Process NPC sound events before they move or they hear themselves talking
""",
    """    g->perhaps_add_random_npc( /* ignore_spawn_timers_and_rates = */ false );
    const auto activity_phase_started = std::chrono::steady_clock::now();
    int activity_iterations = 0;
    while( u.get_moves() > 0 && u.activity ) {
        ++activity_iterations;
        u.activity.do_turn( u );
    }
    if( construction_perf ) {
        construction_ui::performance_trace( string_format(
                "ACTIVITY_PHASE ms=%lld iterations=%d moves_after=%d activity_after=%s",
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - activity_phase_started ).count(),
                activity_iterations, u.get_moves(), u.activity ? u.activity.id().str() : "none" ) );
    }

    // Process NPC sound events before they move or they hear themselves talking
""",
)
replace_once(
    "src/do_turn.cpp",
    """                if( construction_ui::persistent_editor_activity_active() ) {
                    construction_ui::handle_persistent_editor_activity_input();
                } else {
""",
    """                if( construction_ui::persistent_editor_activity_active() ) {
                    const auto input_started = std::chrono::steady_clock::now();
                    const bool handled = construction_ui::handle_persistent_editor_activity_input();
                    if( construction_perf || handled ) {
                        construction_ui::performance_trace( string_format(
                                "TURN_INPUT_POLL ms=%lld handled=%d activity_after=%s",
                                std::chrono::duration_cast<std::chrono::milliseconds>(
                                    std::chrono::steady_clock::now() - input_started ).count(),
                                handled ? 1 : 0,
                                u.activity ? u.activity.id().str() : "none" ) );
                    }
                } else {
""",
)
replace_once(
    "src/do_turn.cpp",
    """    resolve_crafting_destinations();
    m.process_falling();
    m.vehmove();
    m.process_fields();
    m.process_items();
    explosion_handler::process_explosions();
    m.creature_in_field( u );

    // Apply sounds from previous turn to monster and NPC AI.
    sounds::process_sounds();
    const int levz = m.get_abs_sub().z();
    // Update vision caches for monsters. If this turns out to be expensive,
    // consider a stripped down cache just for monsters.
    m.build_map_cache( levz, true );
    monmove();
""",
    """    resolve_crafting_destinations();
    const auto world_started = std::chrono::steady_clock::now();
    m.process_falling();
    const auto falling_done = std::chrono::steady_clock::now();
    m.vehmove();
    const auto vehicles_done = std::chrono::steady_clock::now();
    m.process_fields();
    const auto fields_done = std::chrono::steady_clock::now();
    m.process_items();
    const auto items_done = std::chrono::steady_clock::now();
    explosion_handler::process_explosions();
    const auto explosions_done = std::chrono::steady_clock::now();
    m.creature_in_field( u );

    // Apply sounds from previous turn to monster and NPC AI.
    sounds::process_sounds();
    const auto sounds_done = std::chrono::steady_clock::now();
    const int levz = m.get_abs_sub().z();
    // Update vision caches for monsters. If this turns out to be expensive,
    // consider a stripped down cache just for monsters.
    m.build_map_cache( levz, true );
    const auto cache_done = std::chrono::steady_clock::now();
    monmove();
    const auto monsters_done = std::chrono::steady_clock::now();
""",
)
replace_once(
    "src/do_turn.cpp",
    """    g->mon_info_update();
    u.process_turn();
    if( u.get_moves() < 0 && get_option<bool>( "FORCE_REDRAW" ) ) {
""",
    """    g->mon_info_update();
    const auto mon_info_done = std::chrono::steady_clock::now();
    u.process_turn();
    const auto player_done = std::chrono::steady_clock::now();
    if( construction_perf ) {
        const auto ms = []( const auto &a, const auto &b ) {
            return std::chrono::duration_cast<std::chrono::milliseconds>( b - a ).count();
        };
        construction_ui::performance_trace( string_format(
                "WORLD_PHASE total=%lld falling=%lld vehicles=%lld fields=%lld items=%lld explosions=%lld sounds=%lld map_cache=%lld monsters=%lld post_monsters=%lld player=%lld",
                ms( world_started, player_done ), ms( world_started, falling_done ),
                ms( falling_done, vehicles_done ), ms( vehicles_done, fields_done ),
                ms( fields_done, items_done ), ms( items_done, explosions_done ),
                ms( explosions_done, sounds_done ), ms( sounds_done, cache_done ),
                ms( cache_done, monsters_done ), ms( monsters_done, mon_info_done ),
                ms( mon_info_done, player_done ) ) );
    }
    if( u.get_moves() < 0 && get_option<bool>( "FORCE_REDRAW" ) ) {
""",
)
replace_once(
    "src/do_turn.cpp",
    """    if( wait_redraw ) {
        if( g->first_redraw_since_waiting_started ||
""",
    """    const auto wait_render_started = std::chrono::steady_clock::now();
    bool wait_rendered = false;
    if( wait_redraw ) {
        if( g->first_redraw_since_waiting_started ||
""",
)
replace_once(
    "src/do_turn.cpp",
    """            refresh_display();
            g->first_redraw_since_waiting_started = false;
""",
    """            refresh_display();
            wait_rendered = true;
            g->first_redraw_since_waiting_started = false;
""",
)
replace_once(
    "src/do_turn.cpp",
    """        g->first_redraw_since_waiting_started = true;
    }

    m.invalidate_visibility_cache();
""",
    """        g->first_redraw_since_waiting_started = true;
    }
    if( construction_perf ) {
        construction_ui::performance_trace( string_format(
                "WAIT_RENDER ms=%lld rendered=%d wait_redraw=%d",
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - wait_render_started ).count(),
                wait_rendered ? 1 : 0, wait_redraw ? 1 : 0 ) );
    }

    m.invalidate_visibility_cache();
""",
)
replace_once(
    "src/do_turn.cpp",
    """#endif

    return false;
}
""",
    """#endif

    if( construction_perf ) {
        construction_ui::performance_trace( string_format(
                "TURN_END total_ms=%lld moves=%d activity=%s",
                std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - construction_turn_started ).count(),
                u.get_moves(), u.activity ? u.activity.id().str() : "none" ) );
    }
    return false;
}
""",
)

# Source-only contracts; no compile/build/test.
checks = {
    "src/construction_ui.h": [
        "performance_trace_active",
        "performance_trace( const std::string &message )",
    ],
    "src/construction_ui.cpp": [
        "construction_ui_perf.log",
        "UI_REDRAW ms=",
        "HANDOFF_BEGIN",
        "QUERY_SUSPEND_BEGIN",
        "QUERY_RESTORE_END",
        "INPUT_ACTION action=",
        "INPUT_CANCEL_ACTIVITY",
    ],
    "src/do_turn.cpp": [
        "TURN_BEGIN moves=",
        "ACTIVITY_PHASE ms=",
        "WORLD_PHASE total=",
        "TURN_INPUT_POLL ms=",
        "WAIT_RENDER ms=",
        "TURN_END total_ms=",
    ],
}
for filename, needles in checks.items():
    source = Path(filename).read_text()
    for needle in needles:
        if needle not in source:
            raise RuntimeError(f"{filename}: missing trace contract {needle!r}")

Path("/tmp/branch_patch_commit_message").write_text(
    "Add detailed Construction performance logging [skip ci]\n"
)
print("Detailed Construction performance trace staged")
