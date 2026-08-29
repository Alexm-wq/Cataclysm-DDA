#pragma once
#ifndef CATA_SRC_CONSTRUCTION_UI_H
#define CATA_SRC_CONSTRUCTION_UI_H

namespace construction_ui
{

/** Opens the modern immediate-construction workspace.
 * Returns false only when the terminal is too small and the legacy picker
 * should be used as a compatibility fallback. */
bool run();

} // namespace construction_ui

#endif // CATA_SRC_CONSTRUCTION_UI_H
