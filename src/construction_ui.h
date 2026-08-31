#pragma once
#ifndef CATA_SRC_CONSTRUCTION_UI_H
#define CATA_SRC_CONSTRUCTION_UI_H

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
/** Keep the retained workspace when cancellation was caused by an editor interaction. */
bool preserve_persistent_editor_on_activity_cancel();

} // namespace construction_ui

#endif // CATA_SRC_CONSTRUCTION_UI_H
