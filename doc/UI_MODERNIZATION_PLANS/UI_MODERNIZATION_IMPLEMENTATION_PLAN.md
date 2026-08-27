# UI Modernization Implementation Plan

Status: long-term implementation plan for `mouse-inventory-0-i-test`

Baseline reviewed: `cf7ab459a441b344e4a06d55225e2f21f11574b9` on 2026-08-27

Related plans/status:

- `doc/UI_MODERNIZATION_PLANS/VEHICLE_EDITOR_VIEWPORT_IMPLEMENTATION_PLAN.md`
- `doc/UI_MODERNIZATION_PLANS/CRAFTING_OVERHAUL_IMPLEMENTATION_PLAN.md`
- `doc/UI_MODERNIZATION_STATUS/INVENTORY_OVERHAUL_STATUS.md`
- `doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md`
- `doc/UI_MODERNIZATION_STATUS/CRAFTING_OVERHAUL_STATUS.md`

## Goal

Modernize Cataclysm-DDA's remaining keyboard-first interfaces around a small set of reusable mouse-capable UI systems instead of building dozens of unrelated one-off screens.

The intent is not to remove keyboard control or change gameplay rules. The new interfaces should expose the same underlying mechanics more clearly, make state and unavailable actions understandable, and allow mouse and keyboard interaction to coexist without maintaining two separate behavioral models.

The inventory, vehicle-editor, and crafting work should now be treated as the foundation. The next work should deliberately reuse their interaction patterns, viewport behavior, selection semantics, scroll handling, action helpers, context actions, and persistent UI state.

## Current foundation state

The roadmap is no longer starting from scratch:

- **Vehicle editor:** approximately 97% complete; remaining work is mainly stabilization, edge cases, and parity.
- **Unified inventory:** approximately 90% complete; the new interaction model is established and remaining work is primarily stabilization and unfinished edge cases.
- **Crafting browser:** approximately 90% complete; the full browser architecture is implemented and manual in-game validation/stabilization remains. Dependency planning remains a later follow-on.
- **Reusable interaction helpers:** action strips, semantic hit maps, scrolling, dropdown/input handling, persisted filters, and click tracking should be preferred over new screen-local equivalents.

These foundation screens should continue receiving fixes, but they no longer need to block starting the next cross-cutting UI work.

## Scope classification

The backlog uses four practical levels of change:

- **FULL** — the interaction model itself is obsolete enough that the screen should be redesigned around a new workflow rather than cosmetically patched.
- **MAJOR** — substantial layout and interaction changes, but much of the current underlying flow can remain.
- **MEDIUM** — focused modernization around a clearer shared browser, inspector, or selection component.
- **LIGHT / SHARED** — do not build a bespoke replacement. Improve a reusable primitive and migrate the existing caller onto it.
- **LOW** — deliberately defer until player-facing systems and shared components are mature.

These labels describe UI scope, not gameplay scope. Unless a feature explicitly requires a mechanics change, the first implementation should preserve existing rules, move costs, activities, requirements, and save behavior.

## Core architectural rule: build six UI families, not dozens of bespoke interfaces

Most of the backlog falls into six reusable families.

### 1. Inventory / list-detail

A scalable item or object list with:

- search and filtering;
- selection and multi-selection where appropriate;
- sortable/groupable rows;
- mouse wheel and draggable scrollbar;
- a persistent detail/inspector panel;
- context actions tied to the selected object;
- explicit disabled/unavailable reasons;
- keyboard focus synchronized with mouse selection rather than competing with it.

The unified inventory is the first major implementation of this family. Trade, item examine, reload selection, repair/disassembly, pickup/drop selectors, and many generic item-choice screens should reuse it or smaller components extracted from it.

### 2. Map viewport / editor

A shared mouse-aware map interaction layer with:

- screen coordinate -> map coordinate conversion;
- pan/zoom without altering gameplay selection;
- hover and selected-tile state;
- selectable/highlighted valid and invalid tiles;
- click, drag, rectangle, and paint selection modes;
- ghost preview overlays;
- right-click contextual actions;
- clear confirmation/cancel semantics;
- keyboard equivalents operating on the same authoritative selection state.

The vehicle editor proves viewport/selection separation at vehicle-mount scale. Construction and Zones should turn the same concept into a reusable map-area editing primitive. Farming, hauling, dismantling, chopping, mining, and similar activities should then adopt that primitive rather than creating their own area selectors.

### 3. Body / equipment

A reusable body-centric interface where body parts are first-class selectable objects and the inspector can show:

- clothing layers and ordering;
- coverage;
- warmth;
- encumbrance;
- protection;
- injuries and effects;
- medical state;
- body-slot conflicts and usage.

Character/armor/encumbrance, wear/equipment, medical interaction, and parts of bionics should share this model.

### 4. Management dashboard

A reusable dashboard pattern for systems with several related resources, actors, queues, and status groups:

- category/sidebar navigation;
- summary/status strip;
- searchable or filterable main list;
- master/detail inspector;
- actions adjacent to the state they affect;
- warnings and unavailable reasons inline;
- persistent selection while data refreshes.

Bionics and faction camps are the clearest examples. Vehicle driving controls can reuse parts of the same status-widget language.

### 5. Generic searchable selector

A replacement for repeated primitive keyboard selectors where the actual domain differs but the interaction does not:

- searchable command/object list;
- categories and filters;
- disabled entries with explanations;
- mouse hover/click;
- wheel scrolling and scrollbar;
- predictable keyboard focus;
- optional detail/preview pane;
- reusable action/result callbacks.

This family should eventually feed `uilist` modernization, keybindings, options, help/command search, skills, martial arts, spells, mod selection, and other long-tail menus.

### 6. Gameplay action dock / command surface

A persistent, compact mouse-facing command surface for ordinary gameplay actions:

- collapsed by default as a small control anchored to the **bottom-right of the gameplay viewport**;
- expands upward/leftward into a compact action panel without replacing the game screen;
- provides a useful curated default set of common actions;
- allows the player to add, remove, pin, and reorder the actions they personally use;
- dispatches registered game **action IDs directly** through the normal action/input path rather than simulating key presses or reproducing multi-key/multi-menu click paths;
- uses the existing shared action/dropdown/hit-test/scroll helpers instead of implementing another button system;
- keeps unavailable actions visible when useful and exposes a reason rather than silently failing;
- persists the player's chosen layout through existing UI/user configuration state;
- keeps keyboard shortcuts authoritative and fully functional.

This is deliberately a cross-cutting feature. It should make already-modernized screens easier to reach while also reducing friction in still-keyboard-heavy parts of the game.

## Priority backlog

Crafting is no longer treated as the next untouched project. Its core browser is implemented and belongs in stabilization while new work proceeds.

| Priority | UI | Scope | Implementation direction |
| ---: | --- | --- | --- |
| **1** | **Gameplay Quick-Action Dock / Expandable Action Menu** | **MAJOR / SHARED — HIGH PRIORITY** | Add a compact expandable button dock at the bottom-right of the game viewport. Ship useful default actions, let players add/remove/reorder their own buttons, and execute the underlying registered action directly instead of forcing key sequences or awkward click paths. Reuse shared UI helpers and persist configuration. |
| **2** | **Bionics / CBMs** | **FULL** | Dashboard-style interface. Installed CBMs grouped by body/system, power usage, current state, activation controls, faults, body-slot usage, filtering/search, and a clearer distinction between passive and active systems. |
| **3** | **Construction** | **FULL** | Construction browser plus map interaction. Select construction -> valid map tiles highlight -> click/paint placement. Add ghost preview, missing-material/tool reasons, and estimated time. Eventually support blueprinting multiple constructions before execution. |
| **4** | **Trade** | **MAJOR / probably cheap** | Reuse the new inventory UX. Replace the two half-screen inventory-selector panes with drag/drop player <-> trader inventory, an explicit selected trade basket, per-item prices, and balance preview. |
| **5** | **Zones / Zone Manager** | **FULL** | Turn it into a map editor. Draw rectangles, click zones, resize/move, right-click properties, show a sidebar of zones, and render color-coded overlays. Reuse the camera/mouse layer. |
| **6** | **Mutations** | **FULL** | Proper visual browser with categories/tree, active/passive state, activation cost, prerequisites/conflicts, mutation lineage, search and filtering. Mutation dependencies can later be shown graphically. |
| **7** | **Character / Armor / Encumbrance** | **MAJOR-FULL** | Replace giant tables with a body-centric UI. Click head/torso/arms/legs and show worn clothing layers, coverage, warmth, encumbrance, protection, injuries, and effects. Use this to unify currently separate character-information concepts where practical. |
| **8** | **Faction camp / Base management** | **FULL** | Build a genuine management dashboard: NPCs, jobs, food, resources, expansion projects, missions, work queues, and map/zone view. Preserve camp mechanics while replacing the menu-heavy interaction model. |
| **9** | **Overmap** | **MAJOR** | Mouse-first map browsing, hover information, right-click contextual actions, route planning, selectable overlays, waypoints, notes, mission targets, and better z-level handling. Reuse map camera infrastructure. |
| **10** | **Targeting / Aiming** | **MAJOR** | Mouse target selection, hover enemy information, trajectory/LOS visualization, firing-mode controls, aim level, estimated hit chance, and obstruction information directly around the cursor. |
| **11** | **NPC Dialogue** | **MAJOR** | Clickable dialogue choices, proper conversation history, optional NPC portrait/info panel, scrollable responses, clearer consequences/skill checks, with keyboard control retained. |
| **12** | **Missions / Quest Log** | **MAJOR** | Master/detail layout, categories and filtering, clickable objectives, jump-to-overmap, completed/failed history, and dependency/mission-chain display. |
| **13** | **Diary** | **MEDIUM** | Master/detail treatment with date navigation, search, filters, clickable locations/events, and cleaner statistics presentation. |
| **14** | **Vehicle Controls / Driving UI** | **MAJOR** | Separate from the builder: an actual dashboard while driving. Speed, heading, cruise control, engine/fuel/battery state, reverse, wheel state, warnings, and clickable vehicle systems. |
| **15** | **Item Examine / Item Info** | **MEDIUM** | Standardized reusable information panel with sections/tabs, collapsible details, mouse scrolling, compare-to-equipped, container contents, and contextual actions. |
| **16** | **Reload / Ammo selection** | **MEDIUM** | Finish the inventory-side work with visual weapon -> magazine -> ammunition relationships, compatible-only filters, and clear time-cost preview. |
| **17** | **Wear / Equipment management** | **MAJOR** | Let the inventory absorb generic item movement, but provide a dedicated equipment/body view for clothing order, pockets, encumbrance, coverage, and conflicts. |
| **18** | **Pickup / Drop / Consume / Read / Unload selectors** | **LIGHT / SHARED** | Do not redesign these independently. Route them through unified inventory/item-selection components so improvements propagate everywhere. |
| **19** | **Disassembly / Repair selectors** | **MEDIUM / SHARED** | Use a shared item browser with availability/requirements and result preview instead of another independent keyboard selector. |
| **20** | **Butchery / corpse processing** | **MEDIUM** | Select a corpse, then show a graphical/action list of available processes, required tools, time, expected yields, and environmental constraints. |
| **21** | **Medical interaction** | **MEDIUM** | Use a body-part selector when applying bandages, disinfectant, splints, etc. Show injury severity and expected result instead of repeatedly invoking generic menus. |
| **22** | **Spell / Magic menus** | **MAJOR** | Particularly relevant with mods: searchable abilities, categories, costs, cooldowns, targeting mode, and favorites/hotbar support. |
| **23** | **Martial arts / combat style** | **MEDIUM** | Style browser showing requirements, buffs, techniques, and weapon compatibility. |
| **24** | **Skills / Proficiencies** | **MEDIUM** | Proper progress browser with filtering, progress bars, dependencies, learning sources, and related recipes/actions. |
| **25** | **Map editor-like activities** | **FULL as a shared framework** | Farming, chopping, mining, dismantling, hauling, construction, and zones should eventually share a generic **select action -> paint/select map area -> preview -> confirm** interaction system. |
| **26** | **Keybindings** | **MAJOR** | Searchable command list. Click an action -> press the desired key or mouse button. Show conflicts, categories, and reset-per-action. This also provides the searchable action catalog used to configure the quick-action dock. |
| **27** | **Options** | **MEDIUM** | Search, category sidebar, actual checkboxes/sliders/dropdowns, tooltips, and "changed from default" indicators. |
| **28** | **Mod manager** | **MAJOR** | Available/active columns, drag reorder, dependency/conflict display, search, and mod information panel. |
| **29** | **World creation** | **MEDIUM-MAJOR** | Wizard/tabbed workflow rather than long option screens. Integrate mod selection, world settings, character creation, and final summary. |
| **30** | **Character creation** | **MAJOR** | Profession/scenario/stat/trait/skill selection with persistent summary, search/filter, point impact, and conflict explanations. |
| **31** | **Message log** | **MEDIUM** | Search/filter, categories, clickable coordinates/entities where possible, severity distinction, and persistent history. |
| **32** | **Help / command listing** | **MEDIUM** | Searchable command palette rather than a static key reference. A future `Ctrl+P`-style action search could make practically every CDDA action discoverable and feed the quick-action dock's customization picker. |
| **33** | **Generic `uilist` menus** | **LIGHT but very high leverage** | Proper mouse hover, clicking, wheel scrolling, scrollbar, disabled-state explanation, and keyboard/mouse coexistence. Improving the primitive upgrades dozens of minor menus automatically. |
| **34** | **Generic text viewers/popups** | **LIGHT / SHARED** | Mouse wheel, draggable scrollbar, selectable links/actions, consistent close/back behavior, and resizing. |
| **35** | **Debug menus** | **LOW** | Eventually modernize them through the same reusable widgets, but defer because they are not player-facing enough to justify early bespoke work. |

## Priority 1 detailed plan — Gameplay Quick-Action Dock

### User-facing behavior

The normal game screen gets one compact launcher in the bottom-right corner. It must remain unobtrusive when collapsed.

Conceptually:

```text
                                            [ Actions ]
```

Expanded:

```text
                                +-----------------------+
                                | Inventory   Examine   |
                                | Pick up     Reload    |
                                | Craft       Construct |
                                | Wait        Sleep     |
                                | Map         More...   |
                                |      [ Customize ]    |
                                +-----------------------+
```

The exact default set can be tuned in playtesting. The important behavior is that a common action becomes one direct click rather than a remembered hotkey, simulated key sequence, or chain through unrelated menus.

### Action model

The dock must not become a second gameplay command system.

Each button stores a stable registered action/command identity. Activating the button routes to the same canonical action handling used by keyboard input. If that action opens a direction picker, item selector, targeting UI, crafting browser, construction browser, or other child UI, the normal authoritative implementation opens from there.

Do **not** implement dock buttons as:

- synthetic keyboard events;
- hard-coded key characters;
- scripted click paths through menus;
- duplicated gameplay validation;
- screen-specific callbacks when an existing action ID already expresses the command.

This preserves rebinding, gameplay rules, activity costs, target validation, and keyboard parity.

### Defaults and customization

Phase 1 should ship with a restrained default group of high-frequency actions such as:

- Inventory;
- Examine / Interact;
- Pick up;
- Reload;
- Craft;
- Construction;
- Wait;
- Sleep;
- Overmap / Map.

The player must be able to customize the dock without editing JSON or keybindings:

- add an action from a searchable action list;
- remove an action;
- reorder buttons;
- restore defaults;
- optionally choose whether labels, compact labels, or icons are shown if the presentation layer later supports that cleanly.

Configuration should persist through the existing UI/user configuration path. Do not create an unrelated ad-hoc save file for it.

### Context and disabled states

The initial dock does not need an AI-like dynamic action system. Stable user-selected buttons are more predictable.

Where the game can cheaply determine that an action cannot currently start, keep the action visible but disabled and expose the concrete reason through the same disabled-reason conventions used by the modernized UIs. Avoid aggressive hiding that causes the dock to constantly reorder itself.

A later optional layer may surface a small contextual section for actions such as opening a nearby door or interacting with a vehicle, but contextual suggestions must remain separate from the player's pinned layout.

### Shared helpers

The implementation should build on the helper layer already introduced for the modernized UIs:

- `ui_action_strip` for button layout, wrapping, hover, enabled/disabled state, and activation;
- `ui_dropdown` / overlay handling where an overflow or secondary menu is appropriate;
- `ui_hit_map` for semantic hit targets where required;
- `ui_scroll_model` if the expanded action catalog can overflow;
- the existing input/action registry for command identities and execution.

If customization needs a searchable action picker, make that picker the first practical caller of the **generic searchable selector** family so Keybindings and Help/command search can later reuse it.

### Layout rules

- Anchor to the gameplay viewport, not an arbitrary terminal coordinate that collides with sidebars after resize.
- Expand upward/leftward from the bottom-right anchor so the launch button remains spatially stable.
- Never reserve a large permanent rectangle while collapsed.
- Clamp/reflow on small windows instead of drawing off-screen.
- Outside clicks may collapse the panel but must not also trigger the underlying world click.
- Escape closes the expanded panel before affecting gameplay.
- Opening/closing the dock must not reset camera, selection, drag state, or other retained gameplay UI state.

### Implementation phases

**Phase 1 — functional dock**

- persistent bottom-right launcher;
- expandable action panel;
- curated default actions;
- direct action-ID dispatch;
- shared helper usage;
- resize/reflow and click-consumption correctness.

**Phase 2 — player customization**

- searchable action catalog;
- add/remove/reorder;
- persisted layout;
- reset defaults;
- disabled-state explanations where available.

**Phase 3 — optional contextual layer**

- context-sensitive suggestions kept separate from pinned buttons;
- optional action grouping/profiles if real use demonstrates a need;
- presentation polish without changing the canonical action model.

### Acceptance criteria

The quick-action dock is ready for normal use when:

- the collapsed control is consistently reachable at the bottom-right of the gameplay viewport;
- expanding/collapsing does not move or mutate world selection;
- common actions are reachable in one or two clicks;
- every dock button invokes the normal registered gameplay action rather than emulating a key press;
- actions that require further choices enter the normal authoritative picker/targeting flow;
- the player can add, remove, and reorder buttons;
- customization persists across restarts;
- unavailable actions cannot silently fail when a reason can be exposed;
- mouse and keyboard remain interchangeable rather than maintaining separate action state;
- resize and small-window layouts cannot leave invisible/off-screen clickable buttons;
- the implementation reuses shared action/hit/overlay/scroll helpers rather than adding another bespoke interaction layer.

## Recommended implementation sequence from the current state

The backlog priority is not identical to implementation order. Dependencies and reuse matter more than simply completing rows in sequence.

Recommended order now that inventory, vehicle editing, and crafting have crossed their main architectural barriers:

1. **Gameplay Quick-Action Dock** — high-leverage cross-game feature; it immediately reduces keyboard/path friction and exercises the shared action helpers on the live gameplay screen.
2. **Trade** — probably the cheapest major remaining win because it can inherit the unified inventory transfer model.
3. **Bionics / CBMs** — first isolated management-dashboard redesign; aggressive UI changes are possible without coupling to map rendering.
4. **Construction** — combine a searchable action browser with a reusable map-selection/preview primitive.
5. **Zones** — harden that map primitive with rectangle drawing, editing, overlays, persistent objects, and properties.
6. **Character / equipment** — establish the reusable body/equipment model and migrate armor/encumbrance/wear concepts into it.
7. **Mutations** — reuse searchable browser/tree concepts and, where useful, body/system presentation patterns.
8. **Targeting / Aiming** — apply the mature mouse/world selection model to one of the most gameplay-critical remaining keyboard-heavy paths.
9. **Overmap** — extend mouse-first viewport principles to strategic map navigation, overlays, routing, and context actions.
10. **Faction camp** — combine the mature dashboard, list/detail, map, queue, and zone components into the most complex management screen.

In parallel, continue stabilization of Inventory, Vehicle Editor, and Crafting when manual testing exposes regressions. Those fixes should not reset the roadmap back to treating the three foundation screens as the only active work.

### Why this order

**Quick-Action Dock** is now the strongest immediate addition because it benefits almost every play session and directly attacks one of the remaining global usability problems: common commands being technically available but hidden behind memorized keys or indirect click paths. It is also small enough to validate the shared action helpers in the main gameplay surface before another full-screen redesign.

**Trade** remains the strongest cheap screen-level win. Its interaction is structurally close to inventory transfer, so the inventory work should replace a large amount of bespoke selector behavior instead of creating another parallel UI system.

**Bionics** is the strongest next isolated full redesign because it benefits from an aggressive dashboard layout without requiring map-renderer or world-interaction changes.

**Construction + Zones** are where the camera/mouse infrastructure starts paying off outside traditional menus. They should not invent independent map interaction systems. Construction should establish the first reusable selection/preview path; Zones should expand it into editable areas and overlays.

## Shared dependency path

The broad dependency graph should be treated roughly as:

```text
Unified mouse/input conventions
        |
        +--> Shared action controls + canonical action IDs
        |       +--> Gameplay Quick-Action Dock
        |       +--> Searchable action catalog
        |               +--> Keybindings
        |               +--> Help / command palette
        |
        +--> Inventory / list-detail primitives
        |       +--> Trade
        |       +--> Item info
        |       +--> Reload / selectors
        |       +--> Repair / disassembly
        |
        +--> Searchable browser / selector primitives
        |       +--> Crafting
        |       +--> Bionics
        |       +--> Mutations
        |       +--> Skills / spells / martial arts
        |       +--> Keybindings / options / help
        |
        +--> Viewport + authoritative selection
        |       +--> Vehicle editor
        |       +--> Map editor primitive
        |               +--> Construction
        |               +--> Zones
        |               +--> Farming / hauling / dismantling / mining / chopping
        |               +--> Overmap interaction patterns
        |
        +--> Body / equipment primitive
        |       +--> Character / armor / encumbrance
        |       +--> Wear / equipment
        |       +--> Medical interaction
        |       +--> parts of Bionics
        |
        +--> Management dashboard primitives
                +--> Bionics
                +--> Vehicle driving UI
                +--> Faction camp
```

Shared primitives should be extracted when at least two real callers need them. Avoid prematurely building a generic widget framework with no concrete screen driving its requirements.

## Cross-cutting interaction requirements

Every modernization should follow these rules unless the screen has a specific reason not to.

### One authoritative selection state

Do not maintain separate mouse and keyboard selections. Mouse hit testing and keyboard navigation must resolve to the same underlying selected object/tile/action.

Temporary hover state may be separate, but actions should never need to guess which selection model is authoritative.

### Keyboard remains first-class

A mouse-first redesign is not a mouse-only redesign.

- Existing keyboard actions should continue to work where practical.
- New widgets need predictable focus order and directional navigation.
- Mouse clicking should update keyboard focus coherently.
- Keyboard navigation should update visible selection coherently.
- Scroll position should follow the active selection only when necessary, not continuously recenter the view.
- A mouse shortcut surface must invoke canonical actions, not replace or shadow their keybindings.

### Explain unavailable actions

Greyed-out rows alone are insufficient. Screens dealing with requirements, tools, power, conflicts, body slots, materials, targeting, permissions, or context-sensitive commands should expose the concrete reason an option cannot currently be used.

This is especially important for the action dock, Crafting, Construction, Bionics, Mutations, equipment, and selectors.

### Persistent context, not screen rebuilds

Where possible, opening a detail, modal action, or child selector should not destroy and reconstruct the parent UI state.

Preserve:

- current selection;
- scroll position;
- search/filter state;
- expanded/collapsed nodes;
- viewport origin/zoom;
- active tab/category;
- multi-selection where applicable;
- quick-action dock configuration and ordinary expanded/collapsed behavior without perturbing world state.

This is both a usability requirement and a way to avoid the redraw/flicker problems already encountered during inventory modernization.

### Responsive layout

Do not hard-code a single desktop resolution into the new screens.

Prefer layouts that can degrade from sidebar + list + inspector into narrower arrangements while retaining usable scrolling. Any pane that can contain unbounded data needs explicit scroll behavior and, where appropriate, a visible scrollbar.

Persistent gameplay overlays such as the quick-action dock must anchor to the current gameplay viewport and reflow around the usable screen instead of assuming fixed sidebar dimensions.

### Gameplay semantics stay behind the UI

The first UI migration for each screen should call existing mechanics and validation wherever possible.

Do not duplicate game rules in rendering or mouse code. The UI may cache presentation data, but authoritative answers such as "can craft," "can wear," "can install," "valid target," "trade value," "required activity time," or "can execute this action now" should come from the same mechanics used by keyboard actions/gameplay.

## Phased roadmap

### Phase A — finish foundational interaction systems + action access

- Continue stabilization of the vehicle editor, unified inventory, and crafting browser.
- Implement the Gameplay Quick-Action Dock Phase 1 and Phase 2.
- Use the dock customization picker to prove a reusable searchable action catalog if practical.
- Continue extracting shared list/detail, scrollbar, context-menu, action-strip, hit-test, and search pieces only where real callers justify them.
- Maintain consistent disabled-state explanation and tooltip/help conventions.

Exit condition: ordinary gameplay and the three foundation UIs no longer require screen-specific workarounds for basic mouse selection, scrolling, focus, viewport state, or access to common commands.

### Phase B — transfer and dashboard proof

- Implement Trade by reusing inventory transfer components.
- Implement Bionics as the first mature management dashboard.
- Extract only the shared components proven by those real screens.

Exit condition: inventory transfer, list/detail, search/filter, requirements/explanation, action access, and dashboard patterns are reusable without forcing unrelated screens into one monolithic widget.

### Phase C — map editing framework

- Implement Construction selection + valid-tile visualization + placement preview.
- Generalize the tile/area selection state enough for Zones.
- Implement Zone drawing, selection, move/resize, overlays, and properties.
- Define shared selection modes: point, rectangle, paint/brush, and existing-area edit.

Exit condition: another area activity can adopt the map editor primitive without copying Construction or Zone Manager input code.

### Phase D — body/equipment framework

- Implement Character / Armor / Encumbrance around selectable body regions.
- Integrate Wear / Equipment management.
- Reuse body selection for Medical interaction.
- Feed compatible body-slot information into Bionics where useful.

Exit condition: body-related screens share one vocabulary for body-part selection, layers, coverage, conflicts, and condition display.

### Phase E — strategic and complex systems

- Implement Mutations using mature search/tree/detail patterns.
- Modernize Targeting/Aiming using proven world selection and action controls.
- Modernize Overmap interaction using proven viewport/context-action patterns.
- Implement Faction camp as the composite management screen that can use dashboards, lists, queues, zones, and map views together.

### Phase F — broad migration through shared primitives

Migrate the long tail rather than redesigning it piecemeal:

- reload/ammo selectors;
- pickup/drop/consume/read/unload selectors;
- repair/disassembly;
- butchery;
- spells;
- martial arts;
- skills/proficiencies;
- keybindings;
- options;
- mod manager;
- world/character creation;
- message log;
- help/command listing;
- generic `uilist` callers;
- generic text viewers/popups;
- debug screens last.

## Acceptance criteria for each migrated screen

A modernization should not be considered complete merely because mouse clicks work. For the relevant screen, verify:

- the primary workflow is discoverable without memorizing hotkeys;
- all primary rows/actions can be reached by mouse and keyboard;
- keyboard and mouse operate on one authoritative selection;
- wheel scrolling does not accidentally mutate selection unless the screen explicitly defines wheel navigation;
- scrollbars are visible/draggable where content can overflow;
- disabled actions expose a reason where the game can provide one;
- search/filter state is stable across ordinary redraws;
- nested/detail actions do not unnecessarily tear down the parent UI;
- resize/reflow does not lose selection or corrupt hit testing;
- actions still route through existing mechanics/activities rather than bypassing rules;
- no duplicate selector or action system is introduced when a shared component already covers the use case;
- shared component changes are validated against their existing callers, not only the newest screen.

## Non-goals

This plan is not a mandate to rewrite every menu immediately, remove curses/terminal support, or replace every current UI implementation with a universal framework.

It also does not require graphical art assets, portraits, or animation as prerequisites. Those can be layered on later. The first objective is interaction quality, information architecture, shared state, and discoverability.

The quick-action dock is not intended to automate gameplay, bypass input validation, or replace keybindings. It is a direct mouse-access surface for the same commands the game already exposes.

Debug-only interfaces remain deliberately low priority until the player-facing reusable systems are mature.
