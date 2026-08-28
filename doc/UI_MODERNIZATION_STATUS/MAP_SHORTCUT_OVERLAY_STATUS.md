# Map shortcut overlay

Branch: `mouse-inventory-0-i-test`

## Tooltip and assignment fixes — 2026-08-28

- Assigned shortcut buttons display a small tooltip after one second of stationary hover, including extra columns. Labels use the current key binding and translated menu name, for example `(i) Inventory`; unbound actions show only the name.
- The launcher, empty assignment slots and Safe mode button also have tooltips. Safe mode retains its colored ON/OFF status.
- Button hover and tooltip targets use the same exact pixel bounds in TILES and text-cell bounds in curses. Tooltip placement remains in text cells and is clamped by the shared overlay.
- `ui_tooltip` uses the shared `ui_hover_dwell` model for timing. Idle ticks can reveal the tooltip without another mouse event. Repeated redraws preserve dwell; changing targets, moving the pointer, clicking, keyboard input or losing mouse focus resets it.
- The assignment popup keeps already-assigned menus visible, gray and disabled, with a red `already assigned` hint supplied through `ui_selection_list`. All saved slots count, including currently off-screen slots. The assignment function also rejects duplicates; existing saved assignments are not rewritten.
- The screen still owns placement and action labels. Shared helpers own hit testing, hover, dwell timing, disabled-row rendering and the tooltip surface.

## Verification

The renderer-independent helper subset passes 14 test cases with 169 assertions. Targeted hover-model tests cover the one-second threshold, repeated idle redraws, pointer motion and exit, dismissal, target/content changes and exact pixel boundaries. Non-TILES syntax checks cover the game input/drawing code and helper tests. Desktop/TILES visual checks remain necessary; no in-game validation is claimed here.

Manual checks: hover Inventory without moving for one second; test another bound menu, a remapped key, an unbound menu, an extra-column button, an empty slot, Safe mode and the launcher. Move away and open a menu to check tooltip cleanup. Open an empty slot and verify assigned menus are gray with the red hint and cannot be chosen by mouse or Enter. Repeat after resizing and with animations disabled.
