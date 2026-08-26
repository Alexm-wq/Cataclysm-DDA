# Crafting Overhaul — Implementation Plan

Status: **implemented on `crafting-browser-overhaul` — manual validation pending**

Completion estimate: **approximately 90%**. The complete core browser implementation is present on the PR branch; the remaining gate is broad in-game mouse/keyboard/resize validation before the branch can be marked 100%.

Branch: `mouse-inventory-0-i-test`

Planning baseline: `4b82fdd75a354a660681e25f18e3f8fe1571bc42` (`Implement persistent vehicle refueling`)

Created: 2026-08-26

Related roadmap: `UI_MODERNIZATION_IMPLEMENTATION_PLAN.md`

Related living status documents:

- `../UI_MODERNIZATION_STATUS/INVENTORY_OVERHAUL_STATUS.md`
- `../UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md`

## Goal

Replace the current keyboard-first crafting recipe screen with a first-class **recipe browser + persistent recipe inspector** while preserving Cataclysm's existing crafting rules, recipe availability logic, requirement solving, move/time costs, batch behavior, crafter selection, and keyboard controls.

The redesign should make crafting understandable through direct inspection rather than requiring the player to decode tabs, hotkeys, modal screens, and terse requirement text.

The central design principle is the same one used successfully in the vehicle editor overhaul:

> The new UI owns selection, navigation, presentation, and mouse interaction. Existing game systems remain authoritative for what is craftable and what actually happens when crafting starts.

## Current UI problems

The current crafting screen is functional but structurally still a keyboard recipe selector.

Observed problems in the existing layout:

- The horizontal category tab strip scales poorly as category count grows.
- Favorites/recent/hidden state occupies a second horizontal strip and competes with the main category navigation.
- The center of the screen can contain a very large amount of unused space.
- Recipe information is not presented as a persistent, structured inspector.
- Requirement failures are difficult to scan quickly.
- Basic actions are discoverable primarily through the long hotkey legend at the bottom.
- Search/filter state is not presented as a first-class browser control.
- Batch quantity is treated more like a mode than a normal property of the current crafting operation.
- Much of the normal character sidebar is irrelevant while the player is actively browsing recipes.
- Mouse support should become structural rather than being added as isolated click handlers to the existing keyboard layout.

## Target layout

The preferred desktop layout is a three-pane browser:

```text
┌───────────────────────────────────────────────────────────────────────────────┐
│ CRAFTING                                      [ Search recipes...           ] │
├───────────────┬──────────────────────────────────────┬────────────────────────┤
│ CATEGORIES    │ RECIPES                              │ RECIPE                  │
│               │                                      │                        │
│ ★ Favorites   │ ★ Survivor telescope                │ Survivor telescope     │
│ Recent        │   Makeshift crowbar                  │ ─────────────────────  │
│               │   Wooden spear                       │ [item/result details]  │
│ Weapons       │   Combat knife                       │                        │
│ Ammo          │   ...                                │ Difficulty       3     │
│ Food          │                                      │ Time          25 min   │
│ Clothing      │                                      │ Batch       [-] 1 [+] │
│ Electronics   │                                      │                        │
│ Chemistry     │                                      │ SKILLS                 │
│ Vehicles      │                                      │ Fabrication  3 / 2 ✓   │
│ Other         │                                      │                        │
│               │                                      │ REQUIREMENTS           │
│ Filters       │                                      │ Tools                  │
│ ☑ Craftable   │                                      │ ✓ hammer               │
│ ☐ Known       │                                      │ ✓ cutting 2            │
│ ☐ Hidden      │                                      │ Components             │
│ ☐ Nearby only │                                      │ ✓ plank       4 / 4    │
│               │                                      │ ✗ nails      18 / 20   │
│               │                                      │                        │
│               │                                      │ Missing: 2 nails       │
├───────────────┴──────────────────────────────────────┴────────────────────────┤
│ [Craft] [Batch...] [Favorite] [Hide] [Examine]              Crafter: Alex   │
└───────────────────────────────────────────────────────────────────────────────┘
```

The exact proportions should be responsive, but on normal desktop widths the recipe list should be the largest list surface and the inspector should be wide enough to display structured requirements without constant wrapping.

## Authoritative UI state

The new browser should have one explicit source of truth for each piece of UI state.

Conceptually:

```cpp
struct crafting_browser_state {
    const recipe *selected_recipe = nullptr;
    std::string selected_category;
    std::string selected_subcategory;

    std::string search_query;
    crafting_filter_state filters;

    int recipe_scroll = 0;
    int category_scroll = 0;
    int inspector_scroll = 0;
    int batch_size = 1;

    crafting_pane focused_pane = crafting_pane::recipes;
};
```

The exact types should follow existing CDDA conventions rather than introducing unnecessary new IDs or wrappers.

Critical rule:

**Do not maintain separate mouse recipe selection, keyboard recipe selection, batch recipe selection, and inspector recipe selection.**

The recipe browser owns the selected recipe. Every action and every presentation surface reads from that same selection.

## Existing mechanics that must remain authoritative

The first implementation should deliberately avoid rewriting crafting mechanics.

Reuse existing systems for:

- recipe discovery/knowledge;
- `recipe_subset` filtering and availability;
- component alternatives;
- tool requirements;
- qualities;
- proficiencies;
- skill requirements;
- nearby inventory/source access;
- crafter selection;
- batch calculations;
- crafting time;
- charges and result quantities;
- recipe hiding/favorites/known state;
- actual craft command/activity creation;
- failure reasons that already exist in the crafting system.

The browser may organize and explain those results differently, but it must not become a parallel implementation of crafting eligibility.

## Primary expected code surface

The current crafting UI is centered in `src/crafting_gui.cpp`; it already includes crafting, recipe, requirement, input, UI-state, item-info, popup, and `uilist` infrastructure.

Expected primary touch points:

| File | Expected role |
| --- | --- |
| `src/crafting_gui.cpp` | Main browser layout, selection, input routing, recipe list, inspector, search/filter interaction, batch controls, action bar. |
| `src/crafting_gui.h` | Browser state and helper declarations if state needs to be split out of the current implementation. |
| `src/uistate.*` | Persisted crafting browser context if existing crafting UI state is not sufficient. |

Potential supporting touch points should only be modified when the UI exposes a real missing API:

| Area | Rule |
| --- | --- |
| `crafting.*` | Add/query helpers only if existing crafting APIs cannot expose information cleanly. Do not move browser logic into mechanics code. |
| `recipe.*` | Prefer existing recipe metadata. Add read-only helpers only when required by structured presentation. |
| `requirements.*` | Reuse existing requirement solving. Any new API should expose structured requirement results rather than duplicating solving rules in the UI. |
| generic UI helpers | Extract only after the crafting browser has a concrete working need; avoid speculative framework work in Phase 1. |

## Phase 1 — Browser shell and authoritative selection

**Target after Phase 1: approximately 25%.**

This is the equivalent of the vehicle editor's first-class viewport patch: change the structure before changing mechanics.

### Layout

- [ ] Replace the horizontal category-strip-dominated layout with a three-pane desktop browser.
- [ ] Add left category/sidebar region.
- [ ] Add large central recipe list.
- [ ] Add persistent right recipe inspector.
- [ ] Add compact bottom action/status bar.
- [ ] Stop dedicating a large permanent region to the ordinary character HUD while the crafting browser owns the screen.
- [ ] Retain a compact crafting-context status area where useful.

### Selection

- [ ] Introduce one authoritative selected-recipe state.
- [ ] Preserve selection when changing focus between panes.
- [ ] Keep keyboard cursor and visual selection synchronized.
- [ ] Mouse click on a recipe selects that recipe.
- [ ] Mouse click on a category changes category without creating a second recipe-selection model.
- [ ] Preserve selected recipe by identity where possible after list refreshes.

### Initial inspector

- [ ] Show recipe/result name.
- [ ] Show description/item information using existing item-info facilities where practical.
- [ ] Show difficulty.
- [ ] Show primary skill/skill requirement.
- [ ] Show base crafting time.
- [ ] Show current craftability state.
- [ ] Show current batch amount even before richer batch controls are implemented.

### Keyboard parity

- [ ] Existing keyboard category navigation remains functional.
- [ ] Existing recipe up/down navigation remains functional.
- [ ] Confirm/Craft remains keyboard-accessible.
- [ ] Existing escape/back behavior remains predictable.

### Phase 1 non-goals

Do not yet implement:

- dependency planning;
- automatic prerequisite crafting;
- graphical recipe trees;
- major requirement-solving changes;
- shared UI framework extraction;
- broad changes to crafting mechanics.

## Phase 2 — Structured requirements and unavailable reasons

**Target after Phase 2: approximately 50%.**

The inspector becomes the main explanation surface for crafting.

### Requirement tree

- [ ] Present tools, qualities, components, skills, and proficiencies as structured sections.
- [ ] Preserve alternative groups such as "one of" requirements instead of flattening them into misleading independent rows.
- [ ] Show owned/required counts where meaningful.
- [ ] Show satisfied requirements clearly.
- [ ] Show missing requirements clearly.
- [ ] Support scrolling the inspector independently from the recipe list.
- [ ] Keep requirement presentation stable when the selected recipe does not change.

Example:

```text
Components
├─ ✓ Rag                     3 / 3
├─ ✗ Thread                 80 / 120
└─ One of:
   ├─ ✓ Sewing kit
   └─ ✗ Bone needle
```

### Diagnostic summary

- [ ] Put the most actionable blocking reason near the top of the inspector.
- [ ] Prefer concrete explanations such as `Missing 40 thread` over a generic `Cannot craft` state.
- [ ] Where multiple blockers exist, show a concise summary followed by the full structured tree.
- [ ] Explain unavailable/disabled actions instead of silently preventing them.

### Availability integration

- [ ] Ensure nearby components/tools are represented according to the existing crafting inventory rules.
- [ ] Ensure alternate requirement paths use the same solver as actual crafting.
- [ ] Ensure batch changes re-evaluate requirements rather than multiplying UI numbers naively.

## Phase 3 — Search, filters, mouse actions, and batch controls

**Target after Phase 3: approximately 75%.**

### Search

- [ ] Add a persistent search field at the top of the browser.
- [ ] `/` or an appropriate existing shortcut focuses search.
- [ ] Typing into search must not accidentally fire crafting actions.
- [ ] Search recipe/result names first.
- [ ] Preserve the current selection by identity when a query changes and the recipe remains visible.
- [ ] Decide separately whether component/skill/description search is worth adding after name search is stable.

### Filters

Expose current crafting filtering in visible controls rather than relying only on cryptic hotkeys.

Candidate filter controls:

- [ ] Craftable now.
- [ ] Known/available recipes.
- [ ] Favorites.
- [ ] Recent.
- [ ] Hidden.
- [ ] Unread/new state where existing semantics support it.
- [ ] Nearby/source restrictions where they map cleanly to actual crafting behavior.

Filters should be clickable but retain keyboard shortcuts.

### Recipe list rows

- [ ] Give each recipe row enough compact metadata to scan usefully.
- [ ] Candidate metadata: skill/difficulty, time, craftable indicator, missing-count summary, favorite state.
- [ ] Avoid turning each row into a multi-line card; recipe density is important.
- [ ] Highlight selected recipe distinctly from mouse hover.

### Mouse actions

- [ ] Left-click recipe: select.
- [ ] Double-click craftable recipe: craft one, unless testing shows accidental activation is too easy.
- [ ] Mouse wheel scrolls the pane under the cursor.
- [ ] Scrollbars are visible where content exceeds the pane.
- [ ] Scrollbars are draggable if the shared curses UI infrastructure can support it cleanly.
- [ ] Right-click recipe opens a compact context menu.

Candidate context actions:

```text
Craft
Craft batch…
Favorite / Unfavorite
Hide / Unhide
Examine
Choose crafter…
```

Unavailable actions should remain visible when useful and include a reason rather than simply disappearing.

### Batch controls

- [ ] Put batch size in the inspector/action area rather than treating batch as an opaque separate mode.
- [ ] `[-]`, numeric value, `[+]`, and `[Max]` should be mouse-accessible.
- [ ] Direct numeric input remains possible.
- [ ] Changing batch size updates total time.
- [ ] Changing batch size updates component/tool availability using the real crafting calculations.
- [ ] Changing batch size updates result quantity and other relevant totals.
- [ ] Existing keyboard batch workflow remains available.

## Phase 4 — Persistence, responsive layout, and polish

**Target after Phase 4: approximately 90%.**

### Persistent context

The browser should not lose the player's place when a child UI closes or an action refreshes recipe state.

Preserve where appropriate:

- [ ] selected category;
- [ ] selected subcategory;
- [ ] selected recipe identity;
- [ ] recipe scroll position;
- [ ] category scroll position;
- [ ] inspector scroll position;
- [ ] search query;
- [ ] filter state;
- [ ] batch amount;
- [ ] focused pane.

Audit persistence after:

- [ ] Examine/item-info popup.
- [ ] Choose-crafter UI.
- [ ] Favorite/hide operation.
- [ ] Successful craft start/return.
- [ ] Failed craft attempt.
- [ ] Requirement-affecting inventory change.
- [ ] Window resize.

### Responsive behavior

- [ ] Normal desktop width uses three panes.
- [ ] Narrow windows degrade deliberately rather than producing unusably narrow panes.
- [ ] Define a minimum useful category width.
- [ ] Define a minimum useful recipe-list width.
- [ ] Define a minimum useful inspector width.
- [ ] If necessary, collapse category/inspector regions into switchable views below a width threshold rather than crushing all three panes.

### Crafting-context status

Replace the ordinary full game sidebar with a compact context block where useful.

Candidate information:

```text
Crafter: <name>
Focus: 100
Primary skill: Fabrication 5
Light: Good
Workbench: Table
Power available: 143 W
```

Only show values that genuinely affect or help explain the current craft. Do not recreate the entire gameplay HUD inside crafting.

### Visual polish

- [ ] Consistent selected/hover/disabled colors.
- [ ] Strong visual distinction between satisfied and missing requirements.
- [ ] Clear pane focus without making mouse hover look like selection.
- [ ] Compact hotkey hints integrated into visible actions.
- [ ] Remove obsolete status/header text that became redundant after the redesign.
- [ ] Reduce the bottom-wall-of-hotkeys effect; retain keyboard discoverability through labels/tooltips/help.

## Phase 5 — Stabilization and 100% gate

**Target after Phase 5: 100% for the core crafting browser overhaul.**

- [ ] Manual test with very small and very large recipe sets.
- [ ] Test all major crafting categories and subcategories.
- [ ] Test no-known-recipes and no-craftable-recipes states.
- [ ] Test favorites, recent, hidden, unread/new, and existing recipe-state features.
- [ ] Test multiple crafters.
- [ ] Test recipes with complicated alternative requirements.
- [ ] Test recipes with qualities, proficiencies, charges, and component counts.
- [ ] Test recipes consuming nearby map/vehicle/container resources.
- [ ] Test batch values from 1 through practical maximums.
- [ ] Test keyboard-only operation end to end.
- [ ] Test mouse-only operation end to end.
- [ ] Test mixed mouse/keyboard use without duplicate selection or focus desynchronization.
- [ ] Test resize/reflow without losing state or breaking hitboxes.
- [ ] Remove obsolete layout code only after parity has been manually verified.
- [ ] Add targeted regression tests where the state/filter/selection logic is practical to test outside curses rendering.

The core overhaul can be marked **100%** when the browser/inspector UI is stable, mouse-first, keyboard-compatible, explains recipe availability clearly, preserves context correctly, and still delegates crafting semantics to the existing game systems.

## Phase 6 — Crafting plans and dependencies (follow-on, not part of the core 100% gate)

Dependency planning is intentionally deferred until the base browser is stable.

This prevents the first redesign from simultaneously changing layout, selection, requirement presentation, and crafting automation.

Once the requirement tree has proven stable, it can support a second feature:

```text
Missing: 2 electronic circuits

[Add prerequisites to plan]

Crafting plan
├─ 4 copper wire
├─ 2 circuit boards
└─ Survivor telescope
```

Possible follow-on work:

- [ ] Build a dependency graph from existing recipe/requirement APIs.
- [ ] Show craftable intermediate components.
- [ ] Detect cycles and impossible prerequisite chains.
- [ ] Allow adding prerequisite crafts to an explicit plan.
- [ ] Show total materials/time for a plan.
- [ ] Never silently auto-craft prerequisites without explicit player confirmation.
- [ ] Preserve normal crafting availability, source, activity, and move/time-cost semantics for every step.

This phase should receive its own design pass before implementation.

## Input model

The intended interaction model is:

### Left sidebar

- click category -> select category;
- wheel -> scroll categories;
- keyboard left/right or existing category actions -> switch category without breaking recipe selection logic.

### Recipe list

- click -> select recipe;
- double-click -> Craft when valid;
- wheel -> scroll recipes;
- arrow keys -> move the same selected recipe;
- Enter -> Craft;
- right-click -> recipe context menu.

### Inspector

- wheel -> scroll recipe details/requirements;
- click batch controls -> change batch;
- click visible actions -> invoke the same action paths as keyboard commands.

### Search

- click or shortcut -> focus search field;
- Escape -> leave search focus without closing the whole crafting browser unless already unfocused;
- query changes filter the existing recipe model, not a second copy of recipes.

## Selection and refresh rules

These rules are important enough to be explicit before implementation:

1. Recipe identity is more important than row index.
2. When filtering or refreshing, keep the selected recipe if it remains visible.
3. If the selected recipe disappears, choose the nearest sensible remaining recipe once.
4. Do not let mouse hover mutate selected recipe.
5. Do not let inspector scrolling mutate recipe-list selection.
6. Changing category intentionally changes the visible recipe set but should not arbitrarily reset unrelated filter/search state.
7. Returning from a child dialog should restore the exact browser context whenever possible.
8. A successful craft or inventory mutation may refresh availability, but it should not rebuild the entire interface from zero.

## Requirement presentation rules

- Use existing crafting calculations as the source of truth.
- Do not claim a component is sufficient based only on a naive owned-count calculation.
- Preserve alternative requirements.
- Preserve charge/count semantics.
- Preserve nearby-source rules.
- Preserve tools that are required but not consumed.
- Preserve qualities separately from concrete tool items.
- Explain the most useful blocker first, then expose the complete requirement structure.
- If a precise reason cannot be derived safely, fall back to existing game wording rather than inventing a potentially incorrect explanation.

## Action availability rules

Every visible action should be in one of three states:

1. **Available** — normal action.
2. **Unavailable with reason** — visible but disabled, with a meaningful explanation.
3. **Irrelevant** — omitted when the action has no semantic meaning in the current context.

Example:

```text
Craft                 disabled — Missing 2 nails
Craft batch…          available
Favorite              available
Hide                  available
Examine               available
```

This model should later be reusable by Trade, Construction, Bionics, and other modernization work.

## Non-goals

The core crafting-browser overhaul should not:

- rewrite crafting mechanics;
- change recipe balance;
- change material consumption rules;
- change which nearby inventories are legally accessible;
- change crafting time or move costs;
- change proficiency mechanics;
- remove keyboard control;
- require tiles mode to function;
- create a second recipe database/cache that can diverge from existing crafting data;
- implement dependency automation before the base browser is stable;
- extract a generic application framework before there is a proven second caller.

## Recommended first implementation patch

The first code patch should be deliberately narrow:

1. Reallocate the crafting screen into category sidebar + recipe list + inspector.
2. Introduce one authoritative selected-recipe state.
3. Route mouse click selection into that state.
4. Keep existing recipe filtering/category mechanics behind the new layout.
5. Populate the inspector with basic recipe name, description, difficulty, skill, time, craftability, and existing requirement text.
6. Keep the current Craft/Batch/Favorite/Hide/etc. command implementations intact.
7. Keep existing keyboard actions intact.
8. Do not add dependency planning yet.

That patch should prove that the crafting browser feels structurally correct before requirement-tree rendering or more advanced mouse behavior is added.

## Living progress checklist

Update this section as implementation lands.

- [x] Phase 1 — Browser shell and authoritative selection.
- [x] Phase 2 — Structured requirements and unavailable reasons.
- [x] Phase 3 — Search, filters, mouse actions, and batch controls.
- [x] Phase 4 — Persistence, responsive layout, and polish.
- [ ] Phase 5 — Stabilization and core 100% gate.
- [ ] Phase 6 — Crafting plans/dependencies follow-on design.

**Current core crafting overhaul completion: approximately 90%; manual stabilization gate pending.**
