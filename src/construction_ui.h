#pragma once
#ifndef CATA_SRC_CONSTRUCTION_UI_H
#define CATA_SRC_CONSTRUCTION_UI_H

#include <string>

namespace construction_ui
{

/** Opens the modern immediate-construction workspace.
 * Returns false only when the terminal is too small and the legacy picker
 * should be used as a compatibility fallback. */
bool run();

/** Drop any Construction editor retained across a walk/build handoff. */
void discard_persistent_editor();
/** Temporarily hide a retained Construction editor while a distraction query owns the screen. */
void suspend_persistent_editor_for_query();
/** Restore the exact retained Construction frame when the distraction is ignored. */
void restore_persistent_editor_after_query();
/** Re-enter the retained Construction editor after its walk/build handoff ends. */
void resume_persistent_editor_after_activity();
/** True while a retained Construction workspace owns auto-walk or ACT_BUILD. */
bool persistent_editor_activity_active();
/** Poll one nonblocking Construction input while the world handoff owns the turn loop. */
bool handle_persistent_editor_activity_input();
/** Repaint a retained handoff only when its world position, phase, or progress changed. */
void redraw_persistent_editor_if_needed();
/** Keep a retained workspace when its current walk/build handoff is canceled. */
bool preserve_persistent_editor_on_activity_cancel();
/** Show an activity failure in the retained editor when it resumes. */
void set_persistent_editor_activity_failure( const std::string &reason );

} // namespace construction_ui

#endif // CATA_SRC_CONSTRUCTION_UI_H
