#pragma once
#ifndef CATA_SRC_CONSTRUCTION_UI_H
#define CATA_SRC_CONSTRUCTION_UI_H

namespace construction_ui
{

/** Opens the modern immediate-construction workspace.
 * Returns false only when the terminal is too small and the legacy picker
 * should be used as a compatibility fallback. */
bool run();

/** Drop any Construction editor retained across an ACT_BUILD handoff. */
void discard_persistent_editor();
/** Temporarily hide a retained Construction editor while a distraction query owns the screen. */
void suspend_persistent_editor_for_query();
/** Restore the exact retained Construction frame when the distraction is ignored. */
void restore_persistent_editor_after_query();
/** Re-enter the retained Construction editor after its ACT_BUILD completes. */
void resume_persistent_editor_after_activity();

} // namespace construction_ui

#endif // CATA_SRC_CONSTRUCTION_UI_H
