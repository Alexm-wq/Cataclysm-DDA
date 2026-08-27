# Crafting Overhaul — Living Implementation Status

Status: **implemented — approximately 90% complete; manual validation pending**

Completion estimate: maintainer estimate, not a percentage calculated from commit count.

Base branch: `mouse-inventory-0-i-test`

Implementation branch: `crafting-browser-overhaul`

Implementation baseline: `b71aef5756c2c0e91d9bd6583cfd2683ffd35886`

Last audited: 2026-08-26

Related plan: `../UI_MODERNIZATION_PLANS/CRAFTING_OVERHAUL_IMPLEMENTATION_PLAN.md`

## Current state

The keyboard recipe selector has been replaced by a first-class crafting browser on the implementation branch. The core implementation is complete: desktop layouts use a three-pane category/list/inspector workspace, smaller supported layouts collapse those panes into explicit switchable views, mouse input is structural, and every crafting action still delegates to the existing crafting and activity systems.

The remaining 10% is the Phase 5 manual stabilization gate. The branch needs in-game verification with real characters, large modded recipe sets, alternate requirements, multiple crafters, nearby map/vehicle resources, and repeated resize/mouse/keyboard transitions before the status can honestly be raised to 100%.

Dependency planning and automatic prerequisite queues remain the explicitly deferred Phase 6 follow-on. They are not part of the core browser completion gate.

## Implemented functionality

### Browser shell and authoritative selection

- [x] Full-width crafting workspace that blocks lower world redraws while it owns the screen.
- [x] Three-pane desktop layout: category/filter sidebar, dense recipe list, and persistent recipe inspector.
- [x] Compact layout below the desktop threshold with directly switchable Categories, Recipes, and Inspector views.
- [x] The ordinary gameplay sidebar is no longer reserved inside the crafting screen.
- [x] One selected recipe drives list highlight, inspector, batch calculation, toolbar actions, context actions, and returned craft result.
- [x] Selection is preserved by recipe identity after filters, category changes, favorite/hide changes, crafter changes, and list rebuilds.
- [x] When a selected recipe disappears, the nearest surviving row is selected once.
- [x] Mouse hover is presentation-only and never mutates selection.
- [x] Keyboard cursor and visible selection use the same recipe state.

### Category browser and visible filters

- [x] Favorites, Recent, Hidden, and Nested groups are first-class sidebar destinations.
- [x] Crafting categories are vertical and selected category subcategories expand beneath them.
- [x] Craftable-now, Memorized, and Unread filters are visible, persistent, and clickable.
- [x] Unread filtering is disabled cleanly when unread highlighting is disabled in options.
- [x] Existing advanced recipe-search prefixes remain supported through the native recipe filter implementation.
- [x] Hidden recipe counts are surfaced in the recipe-list scope line.
- [x] Existing unread-first sorting remains keyboard-accessible and persistent.

### Recipe list interaction

- [x] Dense one-line recipe rows with favorite/unread markers, nested-group affordance, difficulty, and native availability colors.
- [x] Strong selected-row treatment distinct from hover.
- [x] Left click selects without firing the recipe.
- [x] Double click invokes the same craft path as keyboard Confirm.
- [x] Mouse wheel scrolls the list without creating a second selection or changing the selected recipe.
- [x] Keyboard Up/Down, Page Up/Down, Home, and End move the same selected recipe and keep it visible.
- [x] Visible scrollbars for the category, recipe, and inspector panes.
- [x] Right click opens an anchored in-pane context menu instead of replacing the workspace.

### Persistent inspector and availability explanation

- [x] Persistent result name and immediate Craftable/blocked status.
- [x] Difficulty, result quantity, current batch, crafter, skills, proficiencies, failure chances, time, activity level, byproducts, recipe-source information, and description.
- [x] Native structured Tools and Components sections with the game's existing alternative-group presentation and owned/required counts.
- [x] Batch-sensitive requirements are recalculated through `availability` and normal requirement APIs.
- [x] The most actionable blocker is kept above the scrollable detail area.
- [x] Missing requirements, theoretical knowledge, proficiencies, overlapping component use, NPC restrictions, light, and crafting-speed blockers have explicit explanations.
- [x] Inspector scrolling is independent from recipe-list selection and scrolling.
- [x] Examine still opens the native detailed result item-info view.

### Batch and action controls

- [x] Batch amount is a persistent property of the selected crafting operation instead of a replacement recipe-list mode.
- [x] Inspector controls provide `[-]`, direct numeric input, `[+]`, and `[Max]`.
- [x] Batch values remain within the existing 1–50 crafting UI range.
- [x] `[Max]` checks every candidate size with the real availability path rather than multiplying component counts naively.
- [x] Changing batch updates time, result quantity, requirements, craftability, toolbar state, and context actions.
- [x] Bottom toolbar exposes Craft, Batch, Favorite, Hide, Examine, Crafter, Related, Compare, and Back.
- [x] Disabled actions stay visible and carry an explanation.
- [x] Context-menu and toolbar actions route into the same backend actions used by keyboard commands.

### Persistence and flicker prevention

- [x] Category, subcategory, recipe identity, search query, visible filters, unread-first state, pane scroll positions, batch amount, and focused compact pane are serialized in `uistate`.
- [x] Child item-info, crafter, related-recipe, compare, search, and quantity UIs do not destroy and recreate the crafting workspace.
- [x] The browser owns one `ui_adaptor` for its lifetime and uses the lower-UI redraw barrier already proven by the inventory and vehicle editor work.
- [x] Inline search edits directly in the persistent header window.
- [x] Normal return from a child UI invalidates/repaints the retained browser state instead of rebuilding it from defaults.
- [x] Recipe refreshes replace list data while preserving identity/scroll state; they do not tear down the curses windows.
- [x] Extremely small terminals retain the legacy selector as a compatibility fallback below `72x20` rather than crushing the new browser beyond usability.

### Keyboard compatibility

- [x] Confirm/Craft, search/reset, favorite, hide/show, choose crafter, batch, examine, related recipes, compare, unread actions, category navigation, subcategory navigation, and inspector scrolling remain registered in the `CRAFTING` input context.
- [x] Mouse actions use global `SELECT`, `SEC_SELECT`, `MOUSE_MOVE`, and wheel bindings; no tiles-only crafting rules were introduced.
- [x] Escape closes an open context menu first and otherwise exits the browser normally.

## Implementation sequence

1. Added explicit browser state and persisted presentation fields without changing crafting mechanics.
2. Added the responsive window layout and a single recipe-selection model.
3. Reused the existing `recipe_subset`, `availability`, `requirement_data`, crafter, item-info, and craft-start paths behind the new surfaces.
4. Added the vertical category/filter browser and identity-preserving recipe rebuilds.
5. Added the fixed inspector summary, structured scrollable details, and batch-sensitive availability diagnostics.
6. Added pane-aware mouse routing, hover, click, double-click, wheel scrolling, toolbar controls, and the anchored context menu.
7. Added persistent search and batch editing while keeping the parent browser adaptor alive.
8. Added serialization for browser context and retained the legacy selector only as the very-small-terminal fallback.

## Primary edited code surface

| File | Role |
| --- | --- |
| `src/crafting_gui.cpp` | Browser state, layout, recipe-list rebuilds, mouse/keyboard routing, inspector, action toolbar, right-click menu, batch controls, availability explanations, and legacy small-terminal fallback. |
| `src/uistate.h` | Persisted crafting-browser presentation fields. |
| `src/inventory_ui.cpp` | Serialization/deserialization of the new `uistate` fields. |
| `doc/UI_MODERNIZATION_PLANS/CRAFTING_OVERHAUL_IMPLEMENTATION_PLAN.md` | Updated phase/completion record. |
| `doc/UI_MODERNIZATION_STATUS/CRAFTING_OVERHAUL_STATUS.md` | This living implementation and validation record. |

No crafting balance, material-consumption, nearby-source, move/time-cost, proficiency, or activity code was replaced.

## Validation completed on the implementation branch

- [x] `src/crafting_gui.cpp` compiles as the non-tiles object with the project's release warning set and `-Werror`.
- [x] `src/inventory_ui.cpp` passes a direct release `-Werror` syntax compile; its Make object also compiles when the environment-only precompiled-header unused-macro warning is demoted.
- [x] `git diff --check` passes.
- [x] Search, batch, selection, availability, and action handling share existing mechanics rather than a parallel rule implementation.
- [ ] Tiles object compile in this environment: blocked because the container does not provide SDL headers or `pkg-config`; there is no tiles-conditional crafting-browser code.
- [ ] In-game visual/manual verification on the Windows tiles build.

## Manual Phase 5 validation still required

- [ ] Open the browser at normal desktop size and verify the screenshot-aligned proportions/colors.
- [ ] Verify mouse-only crafting, including disabled Craft explanations and eligible-container confirmation.
- [ ] Verify keyboard-only crafting and mixed mouse/keyboard selection without duplicate highlights.
- [ ] Verify Favorites, Recent, Hidden, Nested, Memorized, Craftable, Unread, unread-first, search, and reset interactions.
- [ ] Verify single click, double click, right click, hover, and wheel behavior in every pane.
- [ ] Verify simple and complex alternative requirements, qualities, charges, proficiencies, byproducts, and overlapping requirements.
- [ ] Verify batches 1, intermediate values, 50, and Max against nearby player/map/vehicle/container resources.
- [ ] Verify multiple crafters and camp crafting with the correct inventory override.
- [ ] Verify Examine, Related, Compare, search entry, numeric batch entry, and crafter selection return to the exact browser context without a one-frame world flash.
- [ ] Resize across the three-pane/compact threshold repeatedly and confirm hitboxes and scroll positions remain coherent.
- [ ] Test an extremely small terminal and confirm the compatibility fallback remains usable.
- [ ] Test large modded recipe sets and slow advanced searches.

The core overhaul should be marked **100%** only after those manual checks pass and any resulting stabilization fixes have landed.

## Explicitly deferred follow-on

Crafting dependency plans, prerequisite graphs, aggregate material/time planning, and explicit prerequisite queues remain Phase 6. The new structured inspector is intended to support that work later, but the current implementation never silently auto-crafts prerequisites.
