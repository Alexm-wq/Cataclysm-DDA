# Bionics UI modernization status

**Branch:** `mouse-inventory-0-i-test`
**Implementation base:** `455594673906616bbafeb84fa70f6631a3563e3e` (fast-forwarded from `08afcb7` through `3c3513b`; vehicle history refinements and clipped-text updates preserved)
**Status:** full implementation; in-game acceptance pending
**Plan:** [Bionics implementation plan](../UI_MODERNIZATION_PLANS/BIONICS_UI_IMPLEMENTATION_PLAN.md)

## Implemented

- Centered, content-sized window with two panes, stacked panes on narrow terminals, and a list/details switch when space is particularly constrained. Empty tabs remain compact and switchable. The desktop window does not grow to fill an ultrawide display.
- Cyan shared action-strip controls for Activatable/Passive counts, Sort, and right-aligned Back. There is no initial implicit selection.
- Persistent selected-bionic inspector: explicit state, separate activation/firing/deactivation/trigger/running costs, fuel-saving pause state, full wrapped description, installed weapon, and optional body-slot occupancy/capacity.
- Independent list selection, wheel scrolling and scrollbar capture. Row labels only select, including double clicks. Row power controls dispatch the same operation as the inspector action; `[x] Sprite` controls operate independently without selecting or activating the row. Unavailable quick actions carry an explicit `!` marker as well as disabled styling.
- Shared Sort and fuel-reserve dropdowns, with outside-click pass-through to rows, buttons and scrollbars. Exact reserve values remain 100/90/70/50/30/10 percent and Disabled. Inapplicable CBMs do not show the fuel control.
- Inline shortcut capture: valid characters, Space to clear, Escape to cancel, conflict swapping, inline invalid-key feedback, and no captured-key fall-through to screen commands or Help.
- UID-based selection across sorting, tab changes and activation. Stable sorting preserves duplicate/equal-key bionics and installation order.
- Existing activation/deactivation, move costs, close-on-use flags, targeting, queries and item selection remain gameplay-owned. The Bionics surface is suspended and the game redrawn before a handoff. Post-action lookups use the UID rather than a potentially invalidated vector pointer.
- Direct install/uninstall weapon setting replaces the old intermediate action menu; the actual weapon item picker remains a gameplay handoff.
- Shared clipped-text rendering retains the existing mouse-position/color-preserving hover expansion.

## Shared helpers

`ui_row_accessories` owns leading/trailing controls, checkbox/dropdown rendering, disabled reasons, clipping, accessory hit regions and redraw invalidation. `ui_selection_list` integrates it ahead of base-row actions and exposes capture ownership for multi-pane routing.

`ui_key_field` owns inline arming, raw key capture, clear/cancel/validation results and event consumption. `ui_scroll_view` owns a separate scroll model, wheel/keyboard navigation, content-to-screen clipping and scrollbar behavior for inspector content.

`ui_action_strip` supports composing individually positioned visible settings rows and pointer-only routing without stale-hover keyboard confirmation. Its wrapping path now moves an oversized first left-hand control below a right-aligned Back button. Dropdowns can focus their current choice and accept the shared draggable scrollbar input path.

Screens still own geometry and feature semantics. No Bionics-specific mouse rectangles, dropdown state machine or scrollbar implementation were added.

## Keyboard operation

Existing bindings remain; the following are their defaults:

| Input | Operation |
| --- | --- |
| Up/Down, Page Up/Down, Home/End | Navigate the list, or scroll details when details have focus |
| Tab/previous-tab binding | Switch Activatable/Passive |
| Enter | Selected bionic's primary action |
| Bionic shortcut | Select and invoke the bionic, switching tabs if needed |
| `!` | Focus details/list; it is no longer an Examine mode |
| `s` | Shared Sort dropdown |
| `S` | Selected bionic's fuel-reserve dropdown, if applicable |
| `H` | Selected bionic's sprite toggle |
| `=` | Inline shortcut capture |
| `-` | Install/uninstall selected CBM's weapon |
| Escape | Close a transient control, return from constrained details to list, or exit |

## Validation

- Passed: 25 shared-helper test cases, 1,252 assertions, in a standalone harness. This exercises the actual control/layout/model code with platform color lookup, input plumbing and logging stubbed; it is not an interactive game run.
- Passed: `g++ -std=c++17 -fsyntax-only` in both TILES and non-TILES configurations for `bionics_ui.cpp`, `bionics.cpp`, `veh_interact.cpp`, `crafting_gui.cpp`, `ui_helpers_test.cpp`, and `bionics_test.cpp`, after fast-forwarding to `4555946`. TILES validation used local upstream SDL2/SDL_image/SDL_ttf headers. Shared scrollbar TILES syntax was also checked.
- Passed: keybinding JSON parsing and retained legacy action mappings; `git diff --check`.
- Added four Bionics regression cases covering shortcut swap/clear/invalid input, duplicate-safe sorting and installation order, fuel thresholds/applicability, and side-effect-free activation eligibility. They were syntax checked but not executed: running them requires the complete game test binary and loaded game data.
- Not run: full game linking, the complete Bionics/game test suite, Windows/MSVC compilation, or interactive TILES/curses acceptance. The checklist below remains open.

No balance values, activation costs or save-data formats were changed. The new `Character` declaration will cause dependent translation units to rebuild on the next normal game build.

## In-game acceptance checklist

- [ ] Zero bionics; empty active tab with populated passive tab; one bionic; dozens of bionics.
- [ ] Normal desktop, 80-column stacked layout, short/narrow list/details layout, ultrawide, and runtime resize.
- [ ] German/long localized names: no overlapping controls; clipped text expands at the mouse with its original colors.
- [ ] Label click/double click only selects; quick power action does not activate a different selected bionic; sprite toggle does not select or activate.
- [ ] List and inspector wheel scrolling are independent; thumb drags retain capture when released over another pane or button.
- [ ] Dismiss Sort/fuel onto a row, button or scrollbar: the original click/drag reaches its target. Escape only dismisses the open dropdown.
- [ ] Shortcut capture handles assign/swap/clear/invalid/Escape and consumes keys otherwise bound to screen commands. Re-sorting preserves the chosen UID.
- [ ] All fuel thresholds, remote fuel, unavailable fuel, multiple sources, and non-fueled CBMs.
- [ ] Ordinary toggle; insufficient power; incapacitated CBM; timed bionic that cannot deactivate manually.
- [ ] Query/item/world/targeting activation; cancellation; `activated_close_ui`; `deactivated_close_ui`; firing with remaining shots; action ending the turn. Check for stale Bionics frames during handoff.
- [ ] Install/uninstall integrated weapon; no eligible item; cancellation; powered weapon management disabled.
- [ ] Body slots enabled/disabled, several occupied parts, long body-part names, long modded descriptions.
- [ ] Mouse-only, keyboard-only and mixed input, including Enter after hovering an unrelated button.
