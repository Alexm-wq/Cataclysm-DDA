# Bionics UI Modernization — Implementation Plan

**Status:** implementation plan  
**Target branch:** `mouse-inventory-0-i-test`  
**Primary implementation:** `src/bionics_ui.cpp`  
**Related model logic:** `src/bionics.cpp`, `src/bionics.h`  
**UI reference:** modernized vehicle editor in `src/veh_interact.cpp` / `src/veh_interact.h`  
**Architecture rule:** screens own placement and game semantics; `ui_helpers` own reusable UI behavior.

## 1. Purpose

Replace the current keyboard-first Bionics screen with a mouse-first, responsive, content-sized interface that follows the interaction language established by the modernized vehicle editor and crafting UI without copying their full-screen geometry.

The current Bionics screen is visually much larger and operationally more modal than its real complexity requires. Its size is partly caused by legacy layout policy: the window is forced to at least `FULL_SCREEN_HEIGHT`, while the width grows from `FULL_SCREEN_WIDTH` toward the terminal width. Its interaction model also uses `ACTIVATING`, `EXAMINING`, and `REASSIGNING` modes primarily to expose information or commands that can instead be represented directly in the interface.

The redesign should remove those artificial modes, keep the selected bionic's information visible at all times, expose common actions directly, and reserve transient windows only for interactions that genuinely require them.

This is not intended as a quick reskin. The implementation should improve the shared helper layer where reusable behavior is missing so Bionics does not become another screen containing bespoke hit-testing, hover logic, dropdown behavior, scroll handling, or keyboard/mouse state machines.

---

## 2. Design goals

### 2.1 Same design language as the vehicle editor

Bionics should use the same broad interaction conventions as the vehicle editor:

- cyan/neutral inline action controls;
- explicit selected, hovered, disabled, and active states;
- shared dropdown affordances;
- right-aligned `[ Back ]` navigation;
- shared scrollbar behavior;
- mouse and keyboard operating the same control models;
- transient overlays rendered through the shared overlay/dropdown path;
- clipped text exposing its full value through the shared clipped-text hover system;
- screen code declaring semantics and geometry instead of manually implementing widget behavior.

The vehicle editor is the architectural and visual reference, not a size reference. Bionics has substantially less simultaneous information and should therefore occupy substantially less screen space.

### 2.2 Content-sized by default

The Bionics window must not fill the screen merely because space exists.

The preferred geometry should be calculated from:

- toolbar/status requirements;
- useful list width;
- useful inspector width;
- number of installed bionics;
- amount of inspector content;
- available terminal dimensions.

A character with zero or three installed bionics should receive a compact centered dialog. A character with dozens of bionics should receive a larger dialog with scrolling, not an indefinitely growing window.

### 2.3 Always-on inspector

Selecting a bionic should always show its details. The old `EXAMINING` visual mode should disappear.

The right pane should be the canonical location for:

- bionic name;
- powered/active status;
- activation/deactivation cost;
- periodic power cost;
- trigger/deactivation costs where applicable;
- description;
- shortcut assignment;
- sprite visibility;
- fuel reserve setting where applicable;
- body-slot information when enabled;
- contextual primary action.

### 2.4 Direct controls for direct state

Simple boolean state must not require a global command or popup.

The strongest example is sprite visibility. The existing operation is simply:

```cpp
bio.show_sprite = !bio.show_sprite;
```

Therefore sprite visibility should be a small toggle directly on each bionic row. It should not open a window and should not require selecting the row and invoking a separate toolbar command.

The same principle applies wherever an operation is truly local and immediate.

### 2.5 Preserve complex game semantics

Modernizing the launcher must not rewrite the behavior of individual CBMs.

Some bionics legitimately:

- open queries;
- request targeting;
- select items;
- interact with the map;
- close the Bionics UI on activation/deactivation;
- temporarily require the Bionics UI to disappear so another game surface owns the screen.

Those handoffs must remain correct. The redesign should make common Bionics operations direct while preserving CBM-owned interaction flows.

---

## 3. Non-goals

This work should **not**:

- change bionic balance, costs, or activation rules;
- change the semantics of `activated_close_ui` or `deactivated_close_ui`;
- replace CBM-specific targeting or gameplay dialogs with Bionics-specific substitutes;
- make Bionics permanently full-screen to mimic the vehicle editor;
- add screen-specific manual mouse rectangles where a reusable control can own them;
- make mouse controls a second system layered over the old keyboard state machine;
- make color the only indicator of selection, powered state, or enabled/disabled state;
- remove keyboard operation;
- force sprite visibility, fuel reserve, shortcut assignment, or sort selection into generic `uilist` popups if the information can be edited in place or through a shared dropdown.

---

## 4. Current behavior that must be preserved

Before UI changes, establish regression coverage for these behaviors.

### 4.1 Active/passive partition

The current screen separates bionics into:

- activatable bionics;
- passive bionics.

The new tabs should retain this distinction and show counts.

### 4.2 Sort modes

Current sort modes are:

- Power usage;
- Name;
- Manual / shortcut;
- None / installation order.

The same modes should remain available. Only their presentation changes from a `uilist` to a shared toolbar dropdown.

### 4.3 Shortcut assignment

Current reassignment behavior permits:

- assigning a valid bionic shortcut;
- clearing the shortcut with Space;
- cancelling;
- swapping shortcuts when the requested shortcut belongs to another bionic;
- rejecting invalid characters.

The new inline key-capture field must preserve all of these semantics.

### 4.4 Fuel reserve

Fuel-capable and remotely fueled bionics can currently select a safe-fuel threshold of:

- 100%;
- 90%;
- 70%;
- 50%;
- 30%;
- 10%;
- Disabled.

The inspector dropdown must map exactly to the existing stored threshold behavior.

Non-fueled bionics should not present this control at all rather than exposing a control that can only produce an error popup.

### 4.5 Sprite visibility

`show_sprite` must continue to be independently stored per bionic and immediately reflected by the game renderer.

### 4.6 Activation/deactivation

The new UI must preserve:

- normal activate/deactivate eligibility;
- powered state;
- bionics that open secondary UI or targeting;
- bionics that close Bionics after use;
- movement/turn consequences;
- restoration of the Bionics screen when the action returns normally;
- clean rendering during external queries or world interactions.

### 4.7 Body-slot information

When `CBM_SLOTS_ENABLED` is active, body-slot occupancy and capacity information must remain available. The exact connector-line visualization does not need to be preserved if a clearer compact inspector representation replaces it.

---

## 5. Target interface

### 5.1 Normal two-pane layout

Conceptual layout:

```text
┌─ Bionics ────────────────────────────────────────────────────────────────────┐
│ [ Activatable (6) ] [ Passive (11) ]   [ Sort: Name ▼ ]          [ Back ] │
│ Power 824 / 1200 kJ      Fuel: gasoline 72%                                │
├──────────────────────────────────┬────────────────────────────────────────────┤
│ ACTIVATABLE                     │ Night Vision CBM                           │
│                                 │────────────────────────────────────────────│
│ ○ Night Vision        2 kJ  [S] │ ACTIVE                                     │
│ ● Enhanced Hearing          [S] │                                            │
│ ○ Hydraulic Muscles  10 kJ  [S]│ Power                                      │
│ ○ Integrated Toolset  5 kJ  [S]│ Activation:   5 kJ                         │
│ ...                             │ Running:     15 kJ / turn                  │
│                                 │                                            │
│                                 │ Provides enhanced low-light vision...      │
│                                 │                                            │
│                                 │ Settings                                   │
│                                 │ Shortcut       [ n ]                       │
│                                 │ Sprite         [x]                         │
│                                 │ Fuel reserve   [ 70% ▼ ]                   │
│                                 │                                            │
│                                 │ Body slots                                 │
│                                 │ Eyes              2 / 4                    │
│                                 │                                            │
│                                 │ [ Deactivate ]                             │
└──────────────────────────────────┴────────────────────────────────────────────┘
```

`[S]` above denotes the conceptual inline sprite control; the final glyph/icon may differ. The implementation should favor a clear small control whose state is visually explicit in both TILES and curses builds.

### 5.2 Row semantics

Each row should have distinct interaction regions:

1. **State/activation control** — quick activation/deactivation when meaningful.
2. **Bionic label** — selects the row and updates the inspector.
3. **Power summary** — read-only trailing value.
4. **Sprite visibility toggle** — independent inline toggle.

A click on one accessory must not accidentally trigger another row action.

Selecting a row must never activate the bionic.

### 5.3 Empty state

With no bionics in the selected tab, show a compact empty panel instead of a large blank screen:

```text
┌─ Bionics ────────────────────────────────────────────────────────┐
│ [ Activatable (0) ] [ Passive (0) ] [ Sort: Name ▼ ] [ Back ] │
│ Power 0 mJ / 0 kJ                                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│               No activatable bionics installed.                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

When the selected tab is empty but the other tab is not, the current tab remains explicit and switchable.

---

## 6. Responsive sizing and layout

### 6.1 Preferred size

Do not use the current `FULL_SCREEN_HEIGHT` minimum.

Calculate a preferred modal size using content and useful readability rather than terminal percentage. A reasonable initial target for a typical two-pane layout is approximately:

- **width:** 100–115 terminal columns;
- **height:** 20–30 rows.

These are preferred ranges, not hard constants.

### 6.2 Width calculation

Preferred width should derive from:

```text
outer borders
+ left pane preferred width
+ divider
+ right inspector preferred width
```

The left pane needs enough width for:

- state control;
- localized bionic name;
- compact power value;
- trailing row accessories;
- scrollbar.

The inspector needs enough width for normal translated descriptions without becoming excessively wide.

Clamp preferred width to the available terminal, with a defined minimum below which the layout changes mode.

### 6.3 Height calculation

Preferred height should derive from:

- border;
- toolbar;
- global status line;
- a useful number of list rows;
- a useful inspector viewport;
- bottom border.

For a small bionic collection, the dialog may shrink. For a large collection, list and inspector scroll rather than continuously increasing the dialog.

### 6.4 Narrow-terminal fallback

Use deterministic responsive modes rather than letting controls overlap or disappear unpredictably.

Recommended order:

1. **Two-pane mode** when both panes can meet their minimum useful width.
2. **Stacked mode** when width is insufficient but height can support list above inspector.
3. **Single-pane switch mode** only on very constrained terminals: list first, inspector entered for the selected bionic with an explicit Back-to-list action.

The same model state should drive all three layouts. Responsive layout must not fork game semantics.

### 6.5 Ultra-wide terminals

Do not stretch the modal indefinitely. Center it at its maximum useful preferred width. Empty space should remain world/background space rather than turning descriptions into extremely long single lines.

---

## 7. Interaction model

### 7.1 Tabs

Use `ui_action_strip` for `Activatable` and `Passive`.

Requirements:

- counts in labels;
- selected-state rendering;
- mouse click;
- keyboard `NEXT_TAB` / `PREV_TAB` compatibility;
- preserve or restore sensible selection per tab;
- tab switching resets only state that logically belongs to the previous tab (for example an open row-local dropdown).

### 7.2 Row selection

Use `ui_selection_list` or a helper built on the same list model.

Requirements:

- single selection;
- mouse hover;
- wheel scrolling without selection changes;
- keyboard navigation;
- scrollbar capture;
- stable selection where possible after sort/rebuild;
- selected item identified by stable bionic identity/pointer relationship rather than only row number.

### 7.3 Activation/deactivation

Provide both:

- a compact row-level quick action;
- a clearly labeled primary action in the inspector.

Both must dispatch through the same semantic handler.

The row state icon must distinguish at least:

- inactive but activatable;
- powered/active;
- unavailable/disabled where appropriate.

Do not use color alone.

Disabled activation should surface the existing reason through an inline status/disabled-reason path where available. Do not create a new popup for every disabled click.

### 7.4 Sprite visibility

Sprite visibility is a direct inline toggle on every bionic row.

Requirements:

- checked/unchecked state is explicit;
- toggling does not activate the bionic;
- toggling does not require a secondary popup;
- row selection may remain unchanged when the accessory is clicked;
- keyboard access remains possible through either the selected row's accessory focus/action or the existing action binding mapped to the same semantic operation;
- optional inspector mirroring is allowed, but the row control is canonical and should always be available.

### 7.5 Sort

Toolbar action:

```text
[ Sort: Name ▼ ]
```

opens a shared `ui_dropdown` with:

- Power usage;
- Name;
- Manual (shortcut);
- Installation order.

Requirements:

- current mode selected;
- outside click follows the shared dropdown contract;
- clicking through to another valid control after dismissal follows the established helper behavior;
- selection remains on the same bionic when possible after resorting;
- no legacy `uilist` remains for this operation.

### 7.6 Fuel reserve

Only present in the inspector for bionics for which the existing code permits safe-fuel mode.

Example:

```text
Fuel reserve   [ 70% ▼ ]
```

Use `ui_dropdown` with the existing thresholds.

Requirements:

- exact mapping to current values;
- current value shown in the closed control;
- no control at all for non-fueled CBMs;
- no error popup merely because the user selected an ordinary non-fueled bionic.

### 7.7 Shortcut reassignment

Replace global `REASSIGNING` mode plus `popup_getkey()` with an inline key-capture field in the inspector:

```text
Shortcut       [ n ]
```

Clicking or keyboard-activating the field arms capture. The field should visibly change state while waiting for input.

Preserve existing behavior:

- valid shortcut assigns;
- Space clears;
- Escape cancels;
- assigning an occupied shortcut swaps assignments;
- invalid input remains rejected and provides an inline error/status;
- opening capture should not cause unrelated actions to fire from the same input event.

This should be implemented as a reusable helper rather than bespoke Bionics key handling.

### 7.8 Inspector scrolling

Long descriptions and modded bionic metadata may exceed available height. Use a dedicated `ui_scroll_model` and shared scrollbar for the inspector.

Scrolling the inspector must not move the bionic list. Scrolling the list must not move the inspector unless a new row is selected and the inspector intentionally resets to its start.

### 7.9 Keyboard parity

Existing keyboard bindings remain useful, but they should target the same control/semantic state as mouse input.

Examples:

- Up/Down changes list selection;
- Tab actions switch tabs;
- Confirm invokes the selected bionic's primary activation/deactivation action;
- Sort binding opens or cycles through the same sort control rather than entering a separate code path;
- sprite binding toggles the selected row's same sprite action;
- shortcut reassignment enters the same key field;
- Quit activates the same Back semantic action.

---

## 8. Popup and transient-window policy

Use an explicit policy so legacy `uilist`/popup behavior does not creep back in piecemeal.

| Operation | New presentation | Reason |
|---|---|---|
| Sprite visibility | Inline row toggle | Pure boolean state |
| Activate/deactivate | Inline/inspector action; preserve CBM-owned downstream UI | Direct action with potentially complex game handoff |
| Sort | Shared dropdown | Small fixed choice set |
| Fuel reserve | Inspector dropdown | Small fixed choice set tied to selected CBM |
| Shortcut assignment | Inline key-capture field | One-key edit, no need for modal screen |
| Description | Persistent inspector | Information, not a mode |
| Body slots | Persistent inspector section | Information, not a mode |
| Disabled reason | Inline status / helper disabled reason | Avoid nuisance popups |
| CBM targeting/query/item/world interaction | Existing external UI | Genuine gameplay interaction |

Transient overlays must route through shared overlay/dropdown helpers so they behave correctly above SDL/TILES content.

---

## 9. Shared helper architecture

The implementation should prefer extending reusable helpers over introducing Bionics-specific UI machinery.

### 9.1 Reuse existing helpers

Use the existing helpers wherever they already own the needed behavior:

- `ui_action_strip`
  - tabs;
  - Sort trigger;
  - Back;
  - inspector primary action;
  - other compact contextual actions.
- `ui_dropdown`
  - Sort menu;
  - fuel reserve menu;
  - future fixed-choice Bionics settings.
- `ui_selection_list`
  - bionic list selection/navigation/scrolling.
- `ui_scroll_model`
  - list and inspector scrolling.
- shared `scrollbar`
  - visible list and inspector scrollbars.
- `ui_overlay`
  - transient surfaces only where required.
- `ui_clipped_text`
  - bionic names, power summaries, translated labels, and other genuinely clipped text.
- `ui_action_entry`
  - semantic action metadata, enabled/disabled state, selected/checked state, and disabled reasons.

### 9.2 Add generic row accessories / inline controls

The current list helper handles rows well but Bionics needs multiple independently clickable controls inside a row. Do not solve this with hardcoded `x` offsets in `bionics_ui.cpp`.

Add a reusable abstraction, either integrated into `ui_selection_list` or implemented as a composable helper, for trailing/leading row accessories.

Conceptual API capabilities:

```cpp
enum class ui_row_accessory_kind {
    action,
    toggle,
    dropdown,
    value
};

struct ui_row_accessory {
    ui_action_entry action;
    ui_row_accessory_kind kind;
    std::string display;
    // Optional width/alignment policy, not absolute screen coordinates.
};
```

The exact API should be designed around existing helper conventions, not this sketch.

Helper ownership must include:

- layout within a caller-supplied row width;
- leading/trailing alignment;
- independent hit regions;
- hover state;
- selected/checked state;
- disabled state and reason;
- clipping;
- interaction results identifying the accessory semantic ID;
- scrollbar exclusion;
- mouse capture rules;
- preventing an accessory click from also selecting/activating the base row;
- keyboard focus/activation policy where applicable.

Bionics should supply data such as:

```text
SPRITE_VISIBLE checked=true
POWER_SUMMARY "15 kJ/t"
TOGGLE_POWER selected=true
```

and should not know the pixel/cell hit rectangles created for them.

The first production consumer is Bionics, but the helper should be general enough for future inventory, crafting, settings, or status-list rows.

### 9.3 Add generic key-capture field

Introduce a reusable helper, tentatively `ui_key_field`, for one-key shortcut editing.

It should own:

- idle/armed state;
- field drawing;
- hover/click behavior;
- current value display;
- clear/cancel handling;
- capture of one raw key event;
- validation callback/result plumbing;
- error display hook/status result;
- prevention of the captured key from falling through into unrelated UI actions.

The caller owns semantics such as swapping two bionic invlets after a conflict.

Do not hardcode the bionic character set into the helper.

### 9.4 Optional responsive modal helper

Only add a generalized responsive modal/layout helper if the abstraction is clearly reusable by more than Bionics.

It would be reasonable for Bionics itself to own:

- desired pane widths;
- divider location;
- preferred/minimum dimensions;
- decision between two-pane/stacked/single-pane modes.

Layout policy is screen-specific. Interaction behavior is not.

---

## 10. Bionics UI state refactor

The current UI state should be simplified before layering new controls over it.

### 10.1 Remove visual modes

Eliminate `EXAMINING` as a screen mode. The inspector is always visible.

Eliminate `REASSIGNING` as a screen mode. Key capture becomes a small transient field state.

`ACTIVATING` no longer needs to exist as a visual mode if it means only the ordinary list/inspector state.

### 10.2 Explicit state

The modernized screen should have explicit state roughly equivalent to:

```cpp
struct bionics_ui_state {
    bionic_tab_mode tab;
    bionic *selected;

    ui_selection_list list;
    ui_scroll_model inspector_scroll;

    ui_action_strip toolbar;
    ui_action_strip inspector_actions;

    ui_dropdown sort_dropdown;
    ui_dropdown fuel_dropdown;
    ui_key_field shortcut_field;

    // Responsive layout mode and transient status.
};
```

This is conceptual. Use safe identities/lifetimes appropriate to the existing bionic collection.

### 10.3 Stable selection

Rebuilding the sorted list must attempt to keep the same selected bionic.

Do not treat `cursor` row number as identity across:

- sort changes;
- tab rebuilds;
- activation side effects;
- bionic collection changes.

If the selected bionic disappears, choose the nearest valid row or the first row and reset inspector scroll.

### 10.4 Transient state

Only genuinely transient controls should add transient state:

- open Sort dropdown;
- open fuel dropdown;
- armed shortcut field;
- disabled/status message;
- activation handoff.

Avoid general-purpose screen modes for individual controls.

---

## 11. Input-routing order

Define input precedence explicitly to prevent the class of bugs already encountered in other modernized screens.

Recommended order for pointer/input routing:

1. active external/retained handoff state;
2. open dropdown/overlay;
3. armed key-capture field;
4. row accessories under the pointer;
5. toolbar controls;
6. base list row selection/navigation;
7. inspector controls and inspector scrollbar;
8. global keyboard actions;
9. Back/Quit.

Rules:

- an activated accessory consumes that click;
- a dropdown dismissed by clicking elsewhere follows the shared passthrough policy;
- clicking a recipe/bionic/list row while dismissing a dropdown should behave according to the shared dropdown contract, not a Bionics-specific workaround;
- scrollbar drag capture must win over row selection;
- mouse wheel scrolling must never activate/select a different row merely because it moved under the pointer;
- Enter/Confirm must not activate a stale hovered control from a previous frame;
- hidden or clipped-away controls must not retain active hit regions;
- resize/rebuild must invalidate stale overlay geometry.

---

## 12. Activation handoff semantics

This is the highest-risk behavioral part of the rewrite.

The current screen deliberately hides itself while calling bionic activation/deactivation because the invoked bionic may open another UI or use the world screen. Preserve this behavior with a clearer handoff mechanism.

### 12.1 Before activation/deactivation

- store stable selected-bionic identity and tab;
- close Bionics-owned transient dropdowns;
- disarm shortcut capture;
- suspend/hide the Bionics drawing surface before handing control to gameplay code;
- ensure the underlying game UI receives a clean redraw when required.

### 12.2 During the action

Call existing activation/deactivation logic without changing its gameplay contract.

Respect:

- `activated_close_ui`;
- `deactivated_close_ui`;
- explicit close requests returned by activation logic;
- moves/turn state;
- targeting/query UI ownership.

### 12.3 Returning normally

If the Bionics UI should remain open:

- restore its UI adaptor/window;
- rebuild bionic collections if activation changed relevant state;
- restore the previously selected bionic when it still exists;
- preserve list scroll position where valid;
- redraw power/fuel/active state;
- return inspector scroll to a sensible location only if its selected content changed.

### 12.4 Action closes UI

If gameplay semantics request closure, destroy the Bionics UI normally and do not flash a stale modal frame during transition.

### 12.5 Tests

At least one regression test/manual fixture should cover each category:

- direct toggle bionic;
- bionic that opens a query;
- bionic that enters targeting/world selection;
- bionic with `activated_close_ui`;
- bionic with `deactivated_close_ui`;
- activation that fails/cancels and returns.

---

## 13. Inspector design

### 13.1 Header

Show:

- localized bionic name;
- explicit state label such as `ACTIVE`, `INACTIVE`, `PASSIVE`, `INCAPACITATED` where appropriate;
- optional compact flags/statuses only when useful.

### 13.2 Power section

Do not bury all power information in the list name.

Show structured values where applicable:

```text
Power
Activation:     5 kJ
Deactivation:   2 kJ
Running:        15 kJ / turn
Trigger:        1 kJ
```

Only render rows relevant to the selected bionic.

The list itself gets only a compact summary useful for comparison/sorting.

### 13.3 Description

Render the full translated description in the inspector with wrapping and inspector scrolling.

### 13.4 Settings

Conditional rows:

```text
Settings
Shortcut       [ n ]
Sprite         [x]
Fuel reserve   [ 70% ▼ ]
```

Do not reserve blank rows for controls that do not apply.

### 13.5 Body slots

When slot limits are enabled, show only relevant body parts for the selected bionic by default:

```text
Body slots
Eyes             2 / 4
Head             1 / 6
```

If useful, distinguish:

- slots occupied by this CBM;
- total occupied slots;
- total capacity.

A compact explicit table is preferable to drawing long connector lines across the list because it works better in a content-sized modal and in narrow layouts.

### 13.6 Weapons/pseudo-items/other metadata

Preserve information currently emitted by `draw_description()`. Refactor the content generation so the new inspector does not accidentally lose niche bionic metadata.

---

## 14. Global status line

Replace the old titlebar instruction paragraph with useful state.

Suggested content:

```text
Power 824 / 1200 kJ      Fuel: gasoline 72%
```

Rules:

- current/max power always shown;
- available external/internal fuel summary shown only when non-empty;
- long fuel lists may be clipped with shared hover expansion or summarized with a compact count/primary value;
- controls belong in the toolbar, not embedded as keyboard instructions in this line.

Keyboard shortcuts remain discoverable through normal help/keybinding UI and optional helper tooltips rather than permanent instruction text.

---

## 15. Visual-state rules

Use explicit, consistent states across TILES and curses.

### 15.1 Selection vs powered state

These are different concepts and must look different.

- **selected row:** list selection/highlight;
- **powered bionic:** active-state icon/toggle/text;
- **sprite visible:** independent checkbox/icon state.

Never use a single highlight color to encode all three.

### 15.2 Disabled state

Disabled actions should:

- render with shared disabled styling;
- remain identifiable;
- provide a reason through `disabled_reason`/status where possible;
- not respond as successful actions.

### 15.3 Hover

Hover should be transient and helper-owned. Moving over an accessory should highlight the accessory, not unpredictably move list selection unless the base list's established hover policy calls for it.

### 15.4 Clipped text

Use the shared clipped-text recording path for any `trim_and_print` output likely to truncate, especially:

- bionic names;
- power summaries;
- fuel summaries;
- long settings values;
- disabled reasons.

Only genuinely clipped strings receive the full-text hover popup.

---

## 16. Localization and terminal constraints

The implementation must be designed around translated text from the start.

Requirements:

- use UTF-8 display width, never byte length, for geometry;
- allow toolbar controls to wrap or reduce gracefully according to helper policy;
- do not hardcode English label widths;
- keep important controls visible when translations expand;
- rely on clipping + hover expansion only after allocating sensible width;
- test German or another known longer localization;
- keep all semantics available with keyboard-only input;
- support TILES and curses builds;
- avoid assumptions about square terminal cells;
- ensure exact-pixel icon controls, if used, remain optional TILES enhancements with a curses representation.

---

## 17. Concrete file impact

Expected files; adjust only where implementation proves necessary.

### `src/bionics_ui.cpp`

Major rewrite of presentation and input state:

- responsive modal allocation;
- toolbar and tabs;
- selection list population;
- inspector rendering;
- activation handoff orchestration;
- semantic action dispatch;
- removal of old title instruction rendering;
- removal of `EXAMINING` and `REASSIGNING` visual state;
- removal of old Sort `uilist` path;
- replacement of old sprite command presentation with row accessory;
- integration of fuel dropdown and key field.

### `src/bionics.cpp`

Refactor safe-fuel configuration so UI choice and model mutation are separable.

Do not require `bionic::toggle_safe_fuel_mod()` to own a `uilist` for the new screen. Prefer model-facing operations such as setting/querying threshold while retaining any compatibility path still used elsewhere.

### `src/bionics.h`

Only add/expose model-level API necessary to avoid UI code reaching through internal state incorrectly.

### `src/ui_helpers/controls/selection_list.h`

Potential extension for row accessories if that produces the cleanest reusable model.

Alternatively add a new focused helper rather than overloading selection-list responsibilities.

### New shared helper, tentative

`src/ui_helpers/controls/row_accessories.h`

or an equivalently named helper consistent with the existing hierarchy.

### New shared helper, tentative

`src/ui_helpers/controls/key_field.h`

### Helper tests

Add model/control tests alongside the existing UI helper tests for:

- independent row accessory hit testing;
- toggle state;
- accessory vs row click precedence;
- hidden/offscreen accessory invalidation;
- scrollbar exclusion;
- key-field capture/cancel/clear;
- invalid key result;
- event consumption.

### Bionics-focused tests

Add tests for state/model transformations where practical rather than relying entirely on visual integration tests.

---

## 18. Phased implementation

### Phase 0 — Behavior inventory and regression baseline

Before changing layout:

1. enumerate every action registered by the current `BIONICS` input context;
2. enumerate every current menu mode branch;
3. enumerate all data emitted by `draw_description()` and row rendering;
4. enumerate activation/deactivation exit and handoff paths;
5. add focused tests for sort ordering, safe-fuel thresholds, invlet swap/clear behavior, and any pure helpers that can be isolated;
6. record representative screenshots for empty, small, and populated Bionics states.

**Exit condition:** no current behavior is being removed accidentally because it was hidden in legacy rendering code.

### Phase 1 — Shared row-accessory helper

Implement reusable inline row controls.

Required first tests:

- value accessory draws but is not actionable;
- action accessory returns its own semantic ID;
- toggle accessory returns activation without selecting the row;
- disabled accessory returns disabled state/reason;
- clicks in the base label still select the row;
- wheel scroll does not activate accessories;
- scrollbar interactions do not fall through;
- offscreen rows have no active regions;
- rebuild/resize removes stale hit regions;
- hover state resets correctly.

**Exit condition:** Bionics can declare a row containing a label, power value, and sprite toggle without hand-built hit boxes.

### Phase 2 — Shared key-capture field

Implement `ui_key_field` or equivalent.

Test:

- arm by mouse;
- arm by keyboard;
- capture valid key;
- Space/clear behavior as configured;
- Escape cancel;
- invalid key result;
- captured event does not trigger another action;
- resize/rebuild preserves or safely cancels armed state according to documented contract.

**Exit condition:** Bionics only supplies allowed-key validation and assignment semantics.

### Phase 3 — Explicit Bionics state/model extraction

Refactor the current loop so selected bionic, active tab, sort mode, list model, and transient controls are explicit.

Do not change the entire visual design in the same step if that makes behavior difficult to verify.

**Exit condition:** current behavior can be driven through an explicit state object without `EXAMINING`/`REASSIGNING` being required as the fundamental architecture.

### Phase 4 — Responsive shell and top toolbar

Implement:

- centered content-sized outer window;
- responsive sizing;
- two-pane layout;
- tabs via `ui_action_strip`;
- Sort trigger via action strip;
- right-aligned Back;
- compact power/fuel status;
- compact empty state.

Keep list contents simple during this phase if necessary.

**Exit condition:** the Bionics window no longer inherits legacy fullscreen-like sizing.

### Phase 5 — Modern bionic list and row accessories

Move the bionic list to shared selection/list behavior and add:

- powered-state control;
- name;
- compact power summary;
- inline sprite toggle;
- shared scrollbar;
- clipped-text hover behavior.

**Exit condition:** all primary list interactions are mouse-operable without screen-local hit-test code.

### Phase 6 — Always-on inspector

Replace Examine mode with permanent inspector content:

- name/state;
- structured power data;
- description;
- settings section;
- contextual primary action;
- independent inspector scrolling.

Audit every branch of old `draw_description()` before deleting it.

**Exit condition:** no information requires entering an Examine mode.

### Phase 7 — Sort/fuel dropdowns and inline shortcut capture

- replace Sort `uilist` with `ui_dropdown`;
- refactor safe-fuel model API and use inspector dropdown;
- replace `popup_getkey()` reassignment with key field;
- preserve invlet swapping/clearing/validation.

**Exit condition:** the old UI-owned Sort, fuel, and reassignment transient menus are gone.

### Phase 8 — Activation/deactivation handoff hardening

Route row quick action and inspector action through a single semantic activation function.

Verify clean suspend/restore around CBM-owned external UI.

**Exit condition:** no screen flashing, stale UI, lost selection, or broken close semantics across representative bionic activation classes.

### Phase 9 — Body slots, narrow layouts, and polish

- replace connector visualization with compact inspector body-slot presentation;
- implement stacked and constrained layout fallbacks;
- localization stress test;
- long-name/clipped-text test;
- hover/tooltip polish;
- ensure control spacing matches vehicle/crafting design language.

### Phase 10 — Cleanup

Delete obsolete code only after all behavior is covered:

- old title instruction soup;
- Examine visual mode;
- Reassign visual mode;
- old Sort `uilist`;
- Bionics UI path that launches safe-fuel `uilist`;
- obsolete windows and geometry;
- connector-line drawing if fully replaced;
- redundant manual cursor/scroll logic now owned by helpers;
- duplicate mouse hit testing.

---

## 19. Testing matrix

### Collection sizes

- zero total bionics;
- selected tab empty, other tab populated;
- one bionic;
- a few bionics;
- enough bionics to scroll;
- very large modded collection.

### Bionic classes/states

- passive;
- activatable, currently off;
- activatable, currently on;
- incapacitated;
- bionic weapon/gun;
- bionic with trigger cost;
- bionic with periodic cost;
- bionic with deactivation cost;
- bionic with no power cost;
- hidden sprite;
- visible sprite.

### Fuel

- non-fuel bionic;
- fuel-option bionic;
- remote-fueled bionic;
- every reserve threshold;
- Disabled reserve;
- no available fuel;
- one fuel type;
- multiple available fuel sources.

### Shortcut assignment

- existing shortcut displayed;
- no shortcut;
- assign unused valid key;
- assign occupied key and swap;
- clear with Space;
- invalid key;
- Escape cancel;
- capture while another dropdown had been open;
- sort-by-shortcut after assignment.

### Sort

- Power;
- Name;
- Manual;
- Installation order;
- selection stable after sort;
- top scroll position remains sensible;
- selected item remains visible.

### Activation handoff

- ordinary toggle;
- activation cancelled;
- activation opens popup/query;
- activation opens item selector;
- activation opens targeting/world interaction;
- `activated_close_ui`;
- `deactivated_close_ui`;
- action changes moves below zero/ends normal flow;
- selected bionic still present after return;
- selected bionic removed/changed after return if such an action is possible.

### Body slots

- `CBM_SLOTS_ENABLED` off;
- on with one occupied body part;
- on with several occupied body parts;
- long localized body-part names.

### Geometry

- minimum supported terminal;
- narrow terminal;
- normal 80-ish baseline where possible;
- preferred desktop size;
- ultrawide terminal;
- short-height terminal;
- runtime resize in every responsive layout mode.

### Input

- mouse only;
- keyboard only;
- mixed mouse/keyboard;
- wheel over list;
- wheel over inspector;
- wheel over dropdown;
- scrollbar drag;
- click dropdown then click through to row/control;
- hover accessory then keyboard Confirm;
- stale hover after resize/rebuild.

### Rendering

- TILES;
- curses/non-TILES;
- long localization;
- clipped bionic name;
- clipped power value;
- tooltip at mouse location only for clipped text;
- overlays above active UI without stale background corruption.

---

## 20. Definition of Done

The Bionics modernization is complete when all of the following are true:

1. The default Bionics window is centered and sized to useful content instead of being forced to a fullscreen-like minimum.
2. Activatable/Passive tabs, Sort, and Back use shared action-strip behavior.
3. The bionic list uses shared list/scroll/hover behavior.
4. Selecting a bionic always shows its inspector; there is no Examine visual mode.
5. Sprite visibility is an inline toggle directly beside each bionic.
6. Sprite toggling cannot accidentally activate the bionic or trigger the base row action.
7. Sort uses a shared dropdown and no longer opens its legacy `uilist`.
8. Fuel reserve uses a selected-bionic inspector dropdown and is absent for inapplicable bionics.
9. Shortcut reassignment is inline key capture and preserves clear/cancel/conflict-swap semantics.
10. Activation/deactivation can be invoked by mouse and keyboard through the same semantic handler.
11. CBM-owned targeting, queries, and close-UI behavior still work correctly.
12. Body-slot information remains available when slot limits are enabled.
13. Long inspector content and large bionic lists scroll independently.
14. Long/clipped text uses the shared clipped-text hover behavior.
15. There is no new Bionics-specific implementation of dropdown behavior, scrollbar dragging, generic hover state, or manual accessory hit-testing.
16. Mouse and keyboard behavior use the same state models rather than parallel implementations.
17. Narrow and short terminal layouts degrade intentionally and remain usable.
18. Helper regression tests cover newly added reusable control behavior.
19. Targeted Bionics behavior tests pass.
20. TILES and non-TILES syntax/build validation passes, followed by in-game validation of representative CBM interactions.

---

## 21. Recommended architectural decisions

These decisions should be treated as the default implementation direction unless real code constraints discovered during implementation justify changing them.

### 21.1 Keep screen-specific geometry in Bionics

Bionics decides:

- modal preferred/minimum dimensions;
- left/right pane sizes;
- which layout mode is active;
- placement of toolbar, list, inspector, and status sections.

Helpers decide:

- how a supplied control is rendered;
- hover/selected/disabled behavior;
- hit testing;
- click/keyboard handling;
- dropdown behavior;
- scroll/drag behavior;
- inline accessory behavior;
- key-field capture behavior.

### 21.2 Keep feature semantics in Bionics/model code

Bionics/model code decides:

- what activating a CBM does;
- whether a CBM can be activated;
- what safe-fuel threshold means;
- how invlet conflicts are resolved;
- what `show_sprite` changes;
- what data belongs in the inspector.

Helpers should never know what a bionic is.

### 21.3 Inline sprite control is mandatory

Do not regress this into an inspector-only control or toolbar command. It is cheap, local state and should stay visible beside its bionic.

### 21.4 Fuel reserve belongs in the inspector

Unlike sprite visibility, safe-fuel reserve has seven values and only applies to some bionics. A row dropdown would add unnecessary clutter. The inspector is the correct scope.

### 21.5 Activation gets both quick and explicit access

The row-level control makes repeated use efficient. The inspector primary action makes the selected bionic's current action unmistakable. Both must share implementation.

### 21.6 Do not preserve legacy modes for implementation convenience

If the new UI is implemented by keeping `ACTIVATING`, `EXAMINING`, and `REASSIGNING` underneath and merely adding mouse controls on top, the modernization has failed architecturally. Replace the visual-mode state machine with explicit control state.

---

## 22. Final expected result

The finished screen should feel like it belongs to the same UI system as the modernized vehicle editor and crafting screen while being visibly simpler because its task is simpler.

The user should be able to open Bionics and immediately understand:

- what bionics are installed;
- which are active;
- how much power they use;
- which are visually shown on the character;
- what the selected bionic does;
- how to activate/deactivate it;
- how to change its shortcut;
- whether and how it conserves fuel;
- how it occupies body slots.

None of that should require entering an Examine mode, remembering a dedicated sprite-visibility key, opening a full-screen reassignment state, or navigating generic text `uilist` dialogs for simple fixed choices.

The implementation should leave the shared helper layer better than it found it, so the next UI modernization can reuse the row-control and key-capture work rather than repeating it.