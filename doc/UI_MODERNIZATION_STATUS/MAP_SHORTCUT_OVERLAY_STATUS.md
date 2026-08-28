# Map shortcut overlay

Branch: `mouse-inventory-0-i-test`

## Tooltip and assignment fixes — 2026-08-28

- Assigned shortcut buttons display a small tooltip after one second of stationary hover, including extra columns. Labels use the current key binding and translated menu name, for example `(i) Inventory`; unbound actions show only the name.
- The launcher, empty assignment slots and Safe mode button also have tooltips. Safe mode retains its colored ON/OFF status.
- Button hover and tooltip targets use the same exact pixel bounds in TILES and text-cell bounds in curses. Tooltip placement remains in text cells and is clamped by the shared overlay.
- `ui_tooltip` uses the shared `ui_hover_dwell` model for timing. Idle ticks can reveal the tooltip without another mouse event. Repeated redraws preserve dwell; changing targets, moving the pointer, clicking, keyboard input or losing mouse focus resets it.
- The assignment popup keeps already-assigned menus visible, gray and disabled, with a red `already assigned` hint supplied through `ui_selection_list`. All saved slots count, including currently off-screen slots. The assignment function also rejects duplicates; existing saved assignments are not rewritten.
- The screen still owns placement and action labels. Shared helpers own hit testing, hover, dwell timing, disabled-row rendering and the tooltip surface.

## Presentation and category filters — 2026-08-28

- Tooltips request a tight frame through `ui_overlay`. In TILES, the window background is clipped to a thin native outline at the border-cell centers, removing the black half-cell surround. The SDL clip is restored afterward; ordinary windows and curses borders are unchanged. Erasing a window clears its frame request.
- The assignment list opts into a reserved right column for disabled hints. Its width uses all matching entries, including rows outside the viewport, so `already assigned` stays aligned while scrolling. Long labels are trimmed before the column; narrow windows preserve label space and the scrollbar. Other lists keep their existing inline hints.
- Categories use the same `ui_tree_dropdown` and `ui_multiselect_filter` as crafting, with checkbox selection, an All/None/partial state, and immediate filtering without closing the dropdown. Search and category filters apply together; an empty result has an explicit message. Escape/right-click dismisses the dropdown before leaving the picker.
- Category identifiers are independent of translated labels. Every menu is mapped as follows:

| Category | Menus |
| --- | --- |
| Inventory | Inventory, Item actions |
| Crafting | Crafting, Construction |
| World | Map, Zone manager, Nearby items |
| Character | Bionics, Mutations, Character info, Medical, Body status, Morale |
| Information | Missions, Factions, Messages, Diary |
| General | Action menu, Movement mode |

## Verification

The renderer-independent helper subset passes 15 test cases with 199 assertions. Targeted tests cover hover timing/retargeting, hint-column geometry at normal and narrow widths, and All/None/combined category selection. Non-TILES syntax checks cover `game.cpp`, `handle_action.cpp`, `crafting_gui.cpp`, `veh_interact.cpp` and the helper tests; `cursesport.cpp` also passes with `TILES` defined. SDL build dependencies are unavailable in this environment, so `sdltiles.cpp` has not been compiled or visually tested here.

Manual checks: hover Inventory without moving for one second; test another bound menu, a remapped key, an unbound menu, an extra-column button, an empty slot, Safe mode and the launcher. Move away and open a menu to check tooltip cleanup. Open an empty slot and verify assigned menus are gray with the red hint and cannot be chosen by mouse or Enter. Repeat after resizing and with animations disabled.

Presentation checks: verify the map remains visible immediately outside each tooltip outline at different UI scales/font sizes, and that later windows are not clipped. Scroll the assignment list and check the warning column. Toggle All off, select Character and confirm Bionics/Mutations appear; combine categories, search within them, then restore All. Check General includes both its menus, dropdown dismissal does not assign a shortcut, and no-match filters cannot activate a stale row.
