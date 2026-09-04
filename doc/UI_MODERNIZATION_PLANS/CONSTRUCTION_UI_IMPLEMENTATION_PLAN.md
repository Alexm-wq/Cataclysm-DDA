# Construction UI Modernization — Implementation Plan

**Status:** Phases 1–4 implemented; multi-tile planning and in-game acceptance pending
**Target branch:** `mouse-inventory-0-i-test`  
**Primary implementation:** new Construction Workspace UI, with minimal construction/activity changes where required  
**Existing mechanics:** `src/construction.cpp`, `src/clzones.cpp`, `src/activity_item_handling.cpp`  
**UI references:** modernized vehicle editor, crafting UI, bionics UI  
**Architecture rule:** screens own placement and game semantics; `ui_helpers` own reusable UI behavior; existing construction/activity systems remain authoritative.

## 1. Purpose

Replace the current keyboard-first construction browser plus adjacent-tile prompt with a full-screen, map-centric **Construction Workspace**.

Construction is fundamentally spatial: the player is choosing a desired world-state change at a location. The current UI reverses that relationship by showing a large textual recipe browser first and only asking for a world location after confirmation. The redesign should make the actual map the primary interaction surface.

The target interaction model is closer to an RTS / colony-sim construction planner, while preserving Cataclysm-DDA's simulation rules. The UI may let the player inspect distant tiles, plan future work, and explicitly order the character to travel to a work site, but the character must still physically move, satisfy normal requirements, spend construction time, be interrupted normally, and only change terrain/furniture when construction actually completes.

The key model is:

```text
Construction Workspace
        ↓
what the player wants + where
        ↓
existing construction validation
        ↓
existing pathfinding / fetching / activities
        ↓
partial_con / ACT_BUILD
        ↓
actual terrain or furniture change on completion
```

This is a UI and orchestration redesign, not a replacement construction engine.

---

## 2. Existing mechanics to build on

The game already contains most of the mechanics needed for the proposed workflow.

### 2.1 Immediate construction

Normal construction already follows this broad flow:

```text
chosen construction group
        ↓
resolve valid construction variant for target tile
        ↓
validate tile + requirements
        ↓
consume / commit components
        ↓
create partial_con
        ↓
ACT_BUILD
        ↓
complete_construction()
        ↓
terrain / furniture changes
```

The new UI must preserve this flow rather than directly mutating map tiles.

### 2.2 Construction blueprints already exist

CDDA already has a `CONSTRUCTION_BLUEPRINT` zone type. `blueprint_options` stores the selected construction and resolves construction chains to the desired final result.

The Construction Workspace should expose this capability directly as **Plan** mode instead of requiring the player to understand Zone Manager internals.

### 2.3 Multiple construction already exists

`ACT_MULTIPLE_CONSTRUCTION` already treats construction blueprint zones and unfinished `partial_con` entries as work targets.

The generic multi-activity system can already:

- find construction targets;
- route the character toward an adjacent work position;
- resume the activity after movement;
- evaluate construction requirements;
- enter existing requirement-fetching behavior;
- continue unfinished construction;
- execute normal construction activities.

The workspace should surface this as **Execute plans**, not duplicate it with a second scheduler.

---

## 3. Core product model

The redesign should make three concepts explicit.

### 3.1 Construction

The desired player-facing operation, such as:

- Wooden Wall;
- Wooden Door;
- Floor;
- Appliance;
- Remove Empty Window Frame;
- Deconstruct Furniture.

The player chooses a construction **group / desired result**, not an implementation-specific internal variant.

### 3.2 Plan

Persistent construction intent at one or more world locations.

A plan does not instantly build anything and does not consume materials merely because it was placed.

### 3.3 Execution

The physical character work required to fulfill a construction or plan:

- path to a valid work position;
- obtain/fetch requirements where existing mechanics permit;
- create/continue `partial_con`;
- spend construction time;
- respect interruptions and hazards;
- complete using normal construction code.

The screen must not blur these concepts together.

### 3.4 Build and Remove operations

Immediate work is separated by intent at the workspace level:

- **Build** presents the categorized construction catalog and previews the resulting terrain or furniture beside each row.
- **Remove** is a map tool and never presents a list of removal recipes. The selected terrain or furniture determines the applicable removal/deconstruction action and the requirements shown in the inspector.

Removal resolution must prefer a specific applicable recipe over generic deconstruction so generic requirements cannot bypass the requirements authored for the selected feature.

---

## 4. Architecture boundary

### 4.1 Construction screen owns

- panel placement and dimensions;
- full-screen workspace composition;
- toolbar placement;
- palette organization;
- inspector organization;
- construction-specific screen state;
- selected construction group;
- selected/hovered construction target;
- construction overlay semantics;
- invoking construction and activity APIs;
- construction-specific status/reason presentation.

### 4.2 Shared UI helpers own

- buttons;
- tabs;
- search fields;
- dropdowns;
- lists and list rows;
- scrollbars;
- hover states;
- clipped-text tooltips;
- context menus;
- pointer capture;
- click/release semantics;
- drag ownership;
- generic map viewport input where reusable;
- generic line/rectangle/paint selection geometry where reusable.

Construction must not grow bespoke button, dropdown, scrollbar, drag, or context-menu implementations.

### 4.3 Existing game systems remain authoritative

- `can_construct()` and construction prerequisite checks;
- construction variant/group data;
- skills;
- tools;
- components;
- crafting inventory;
- terrain/furniture validity;
- `partial_con`;
- `ACT_BUILD`;
- pathfinding;
- requirement fetching;
- `ACT_MULTIPLE_CONSTRUCTION`;
- completion and map mutation.

The UI may classify and explain these states, but must not reimplement their rules.

---

## 5. Full-screen target interface

Construction should become a full-screen workspace, using the actual world renderer as the dominant central surface.

Conceptual layout:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Construction   [ Build ] [ Plan ] [ Plans ]                Search...             [ Back ]   │
├───────────────────────┬────────────────────────────────────────────┬─────────────────────────┤
│ CONSTRUCTIONS         │                                            │ INSPECTOR               │
│                       │                                            │                         │
│ Recent                │                                            │ Wooden Wall             │
│  Wooden wall          │                                            │                         │
│  Wooden door          │             WORLD VIEWPORT                 │ Result                  │
│                       │                                            │ Wooden wall             │
│ Walls                 │                                            │                         │
│  Wooden wall          │                  @                         │ Time                    │
│  Log wall             │                                            │ 48 min                  │
│  Metal wall           │                                            │                         │
│                       │                                            │ Materials               │
│ Doors                 │                                            │ Planks       12 / 8     │
│ Floors                │                                            │ Nails       146 / 20    │
│ Furniture             │                                            │                         │
│ Deconstruct           │                                            │ Target                  │
│ ...                   │                                            │ Valid                   │
│                       │                                            │                         │
│                       │                                            │ [ Build here ]          │
├───────────────────────┴────────────────────────────────────────────┴─────────────────────────┤
│ LMB Select   Drag/Pan   Wheel Zoom   RMB Context/Cancel                         Plans: 12   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

Suggested desktop proportions:

- palette: roughly 20–24%;
- viewport: roughly 52–62%;
- inspector: roughly 22–26%.

The viewport should receive the majority of available space. Side panes may collapse or stack on constrained terminals, but game semantics must remain identical.

---

## 6. Reusable world viewport

Do not build another screen-specific map input system if the vehicle editor already contains reusable concepts that can be extracted.

The reusable viewport state should distinguish at least:

```text
camera position
≠ player position
≠ hovered tile
≠ selected tile
≠ construction target
≠ planned tile
```

A possible model:

```cpp
struct ui_world_viewport_state {
    tripoint_bub_ms camera_center;
    std::optional<tripoint_bub_ms> hovered_tile;
    std::optional<tripoint_bub_ms> selected_tile;
    int zoom = 0;
};
```

Reusable viewport behavior should cover, where practical:

- mouse-to-world conversion;
- hover tracking;
- tile selection;
- panning;
- pointer capture;
- wheel zoom;
- cursor-relative zoom if supported;
- clipping input to the viewport;
- preventing viewport drag release from activating side-panel controls;
- camera movement independent from character movement.

Construction supplies overlay semantics and construction-specific actions.

---

## 7. Workspace state

Use stable IDs rather than raw row indices or long-lived construction pointers.

Example:

```cpp
enum class construction_workspace_mode {
    build,
    plan,
    plans
};

enum class construction_placement_tool {
    single,
    paint,
    line,
    rectangle_outline,
    rectangle_fill
};

struct construction_workspace_state {
    construction_workspace_mode mode = construction_workspace_mode::build;
    construction_category_id category;
    construction_group_str_id selected_group;
    std::string search;
    ui_world_viewport_state viewport;
    construction_placement_tool placement_tool = construction_placement_tool::single;
    std::optional<tripoint_abs_ms> selected_target;
    std::vector<tripoint_abs_ms> placement_preview;
};
```

Persist only UI state that is useful across redraws/reopens. Game-state truth remains in map, construction, zone, and activity systems.

---

## 8. Construction palette

The left pane should present player-facing construction groups, not internal stage/variant entries.

Conceptual organization:

```text
Recent

Walls
    Wooden wall
    Log wall
    Brick wall

Doors
    Wooden door
    Metal door

Floors
Furniture
Utilities
Deconstruction
...
```

The player selects **Wooden Wall**, not `Stage/Variant #2`.

Internal variants should be resolved only after a target tile is known.

### 8.1 Search

Use the shared search field.

Search should cover at least:

- construction group name;
- result terrain/furniture name where meaningful;
- category.

Later it may include skill/tool terms if useful.

### 8.2 Recent

Maintain a small bounded list of recently selected construction groups, for example 5–10 entries.

This is convenience UI state only.

---

## 9. Target resolution layer

Introduce a focused construction-specific resolver rather than duplicating variant selection and status logic throughout the screen.

Example result:

```cpp
struct construction_target_resolution {
    const construction *construction = nullptr;

    enum class status {
        valid_now,
        valid_plan,
        unavailable_requirements,
        invalid_location
    } status = status::invalid_location;

    std::string reason;
};
```

Possible API:

```cpp
construction_target_resolution resolve_construction_target(
    Character &who,
    const construction_group_str_id &group,
    const tripoint_bub_ms &target,
    construction_resolution_flags flags
);
```

Responsibilities:

1. obtain construction definitions in the selected group;
2. identify the variant matching current terrain/furniture;
3. call existing authoritative construction checks;
4. evaluate current player requirements;
5. distinguish physical invalidity from temporary lack of requirements;
6. return the exact construction entry that normal execution should use;
7. provide an explanation suitable for the inspector.

The screen must never maintain a parallel table of terrain compatibility rules.

---

## 10. Map target states

Do not reduce placement feedback to green/red.

### 10.1 Ready now

Target is physically valid and the current player can execute it now.

Conceptual presentation: **green**.

### 10.2 Valid plan, unavailable now

The location is a valid construction target, but the player currently lacks requirements or another temporary execution condition.

Conceptual presentation: **amber**.

Example:

```text
Valid construction location.

Currently missing:
- 4 planks
- Hammering 2
```

### 10.3 Invalid location

The construction itself cannot validly apply to that tile.

Conceptual presentation: **red**.

Example:

```text
Cannot build Wooden Wall here.
Existing terrain is incompatible.
```

### 10.4 Planned

Persistent blueprint/plan overlay, visually distinct from current validity.

### 10.5 Under construction

Existing `partial_con`, visually distinct from both plan and completed terrain.

The exact colors/glyphs should use the established UI/theme conventions rather than screen-specific arbitrary styling.

---

## 11. Hover and ghost preview

When a construction is selected and the pointer moves over the world viewport:

1. resolve the selected group against the hovered world tile;
2. update the inspector;
3. render target validity;
4. draw a non-destructive ghost preview of the resulting terrain/furniture where possible.

The preferred TILES presentation is the actual resulting tile sprite rendered as a preview/ghost plus a separate validity overlay.

Fallbacks may use outlines or markers where a result cannot be previewed safely.

Never modify real map state merely to generate the preview.

---

## 12. Inspector

The right pane is contextual and scrollable.

For a ready target:

```text
Wooden Wall

Target
Wooden frame

Result
Wooden wall

Status
Ready to build

Time
48 minutes

Skills
Fabrication 2        ✓

Components
Plank        12 / 8  ✓
Nail        146 / 20 ✓

Tools
Hammering 2          ✓

[ Build here ]
```

For a valid plan that cannot currently be executed:

```text
Status
Valid plan

Missing
Plank        4 / 8
Hammering 2
```

For an invalid target:

```text
Status
Cannot build here

Existing terrain is incompatible.
```

Requirements and disabled reasons should be inline where possible rather than producing chains of popups.

Use the shared clipped-text hover helper for truncated content.

---

## 13. Build mode

Build mode represents immediate/manual construction.

### 13.1 Selecting a target

With an active Build result, a normal viewport click is the primary construction command:

- validate the clicked tile;
- start immediately when the character can work there;
- otherwise issue the normal route-to-adjacent order and start automatically after arrival;
- if the order cannot start, keep the tile pinned and show the exact reason in the inspector.

Without an active Build result, a viewport click pins the tile for inspection only.  Right-click
**Inspect tile** provides the same deliberate inspection path without duplicating the primary build
command in the context menu.

### 13.2 Adjacent executable target

With an active construction selected, LMB starts the normal construction flow immediately.  A deliberately
pinned/inspected target may also expose `Build here` in the inspector as an alternate explicit action.

### 13.3 Distant executable target

With an active construction selected, LMB issues the route-to-site order and construction starts automatically
after arrival.  A deliberately pinned/inspected target may expose `Go there and build` in the inspector.

The map click and inspector action must enter the same validated execution path; the inspector is not a required
second confirmation.

---

## 14. Distant build orders

Distant one-shot construction should use normal pathfinding and normal construction after arrival.

Suggested semantic state:

```cpp
struct pending_construction_order {
    tripoint_abs_ms target;
    construction_group_str_id group;
};
```

Execution:

```text
Go there and build
        ↓
find valid adjacent working position
        ↓
normal route/pathfinding
        ↓
normal movement and safety interruption
        ↓
arrive
        ↓
re-resolve construction group against current tile
        ↓
revalidate requirements/location
        ↓
start normal construction
```

Do not remotely consume materials or create a `partial_con` before the character reaches the work site unless the existing activity system already requires that behavior.

If the target becomes invalid during travel, cancel cleanly with an explanatory message.

---

## 15. Plan mode

Plan mode creates persistent construction intent without beginning work.

Selecting Wooden Wall and clicking a valid plan tile means:

```text
plan Wooden Wall at this world tile
```

It must not mean:

```text
instantly create Wooden Wall
```

or:

```text
immediately consume its materials
```

### 15.1 Initial scope

Phase 1 of planning should support **single-tile plans only**.

Paint, line, and rectangle tools are later phases once storage semantics and execution are proven.

---

## 16. Existing blueprint integration

Use existing `CONSTRUCTION_BLUEPRINT` functionality as the persistence/execution backend rather than inventing a second unrelated construction-planning system.

The Construction Workspace should hide the Zone Manager implementation detail from the player:

```text
player: "Plan Wooden Wall here"
        ↓
Construction Workspace plan adapter
        ↓
CONSTRUCTION_BLUEPRINT representation
        ↓
ACT_MULTIPLE_CONSTRUCTION
```

The backend may still use zones, but the player-facing concept is a construction plan.

---

## 17. Plan adapter

Create an explicit adapter layer between UI plans and blueprint-zone storage so the UI does not become permanently coupled to rectangular zone representation.

This is important for future arbitrary painted shapes.

Conceptually:

```text
Construction plan API
        ↓
blueprint storage adapter
        ↓
existing zones
```

Initial implementation may use:

- one 1×1 blueprint zone per isolated tile;
- merged zones for compatible contiguous regions where safe;
- the same construction-group options already used by blueprint zones.

If zone storage later proves inefficient for arbitrary painted shapes, the adapter can evolve without rewriting the workspace.

---

## 18. Plan overlap rules

A tile should normally contain one active desired construction intention.

Recommended behavior:

- same plan over same tile: no-op / merge;
- different plan over existing plan: explicit replacement semantics;
- unfinished `partial_con`: never silently replace;
- completed world state: evaluate as a new construction normally.

Right-click/context actions may include:

```text
Inspect
Remove plan
Replace plan
Continue construction
Center view
```

Only contextually valid actions should be shown.

---

## 19. Execute Plans mode

Expose the existing multi-construction machinery as a clear user-facing command:

```text
[ Execute plans ]
```

The workspace itself must not become a turn-by-turn scheduler.

Execution should flow through existing systems:

```text
plans / blueprint zones
        ↓
ACT_MULTIPLE_CONSTRUCTION
        ↓
existing target selection
        ↓
existing route-to-adjacent behavior
        ↓
existing requirement fetching
        ↓
partial_con / ACT_BUILD
        ↓
completion
```

Normal interruptions, safety checks, hazards, path failure, changing map state, and missing requirements remain authoritative.

---

## 20. Plans tab

The third primary mode should summarize persistent planned work.

Example:

```text
Plans

17 total

Ready                  9
Missing materials       4
Blocked                 2
In progress             2

Wooden wall             8
Wooden floor            5
Wooden door             2
Other                   2

[ Execute plans ]
```

Selecting a plan/category should highlight its world positions.

Selecting a blocked item should pan/center the viewport on the relevant location.

Plan status should normally be derived dynamically from current world state rather than persisted as stale metadata.

Suggested derived statuses:

```cpp
enum class construction_plan_status {
    ready,
    missing_requirements,
    unreachable,
    invalidated,
    in_progress,
    completed
};
```

---

## 21. Revalidation rule

A construction plan is an intention, not permission.

Before execution at any target:

```text
plan still exists?
        ↓
tile still valid?
        ↓
construction variant still correct?
        ↓
already complete?
        ↓
requirements available?
        ↓
reachable work position?
        ↓
normal safety/activity rules permit continuation?
```

Only then begin/continue work.

This must hold for immediate distant orders and planned construction alike.

---

## 22. Working-position pathfinding

Construction normally requires the character to work adjacent to the target rather than standing on it.

For distant orders:

1. enumerate suitable adjacent work positions;
2. reject impossible/inaccessible positions;
3. find a normal route;
4. travel using normal movement behavior;
5. revalidate after arrival;
6. start normal construction.

Do not write a Construction-UI-specific pathfinder.

---

## 23. Unfinished construction

`partial_con` must be a first-class visual state.

Conceptual inspector:

```text
Wooden Wall
Under construction

Progress
37%

Remaining work
~29 min

[ Continue ]
```

A plan and a partial construction are different concepts:

```text
plan        = intent, no work necessarily started
partial_con = physical work has begun
```

Do not conflate them in storage or presentation.

---

## 24. Invalidated plans

Plans should not disappear silently merely because the world changes.

Example:

```text
Wooden Wall
Plan blocked

Reason
Vehicle occupies this tile.

[ Remove plan ]
```

Temporary blocking may remain as a plan and be skipped by execution. Permanently incompatible state should be clearly surfaced as invalidated.

The exact executor behavior should follow existing authoritative construction checks.

---

## 25. Construction chains

The player-facing plan should represent the **desired final result**, not a specific internal stage.

Example:

```text
Wooden Wall

Build sequence
1. Wooden frame      20 min
2. Wooden wall       40 min

Total                60 min
```

The target resolver determines the next valid stage from current terrain.

The plan remains `Wooden Wall` until its final result is reached.

This is especially important for blueprint execution and removes the current `Stage/Variant #1/#2` implementation detail from normal UI.

---

## 26. Multi-tile placement tools

Do not implement all placement tools in the first patch.

Recommended order:

1. Single tile.
2. Paint/drag.
3. Line.
4. Rectangle outline.
5. Filled rectangle.

Every tool produces the same generic candidate set:

```cpp
std::vector<tripoint_abs_ms> candidate_tiles;
```

Then the same pipeline handles them:

```text
generate candidates
        ↓
resolve selected construction on every tile
        ↓
classify validity
        ↓
preview
        ↓
commit permitted plans
```

Placement tools must not each implement their own construction validity rules.

---

## 27. Bulk placement preview

Before committing a larger designation, show a summary such as:

```text
Wooden wall

18 tiles selected
15 ready now
 2 valid plans but unavailable now
 1 impossible

Estimated requirements
120 planks
300 nails
~12 hours work

[ Place 17 valid plans ]
[ Cancel ]
```

Default planning policy:

```text
ready + valid-plan tiles → plannable
physically invalid tiles → excluded
```

Any override of invalid tiles should require a clearly justified game mechanic rather than being a generic UI option.

---

## 28. Requirement aggregation

Bulk material/time totals are estimates, not reservations or guarantees.

Label them accordingly:

```text
Estimated requirements
```

not:

```text
Reserved materials
```

Use real construction requirement data. Do not maintain handwritten material mappings.

Alternatives, construction chains, existing partial work, and later world changes may change actual consumption.

---

## 29. No material reservation in initial implementation

Planning should not reserve/remove materials.

A reservation system would create broad gameplay problems involving:

- later crafting use;
- nested containers;
- vehicle cargo;
- ownership;
- NPC access;
- destroyed/moved items;
- multiple workers;
- canceled plans.

Keep resource possession dynamic and let execution revalidate when work starts.

---

## 30. Map interaction rules

Construction should be mouse-first but not mouse-only.

### 30.1 Simple click

With an active Build / Place / Remove / Marker tool, LMB issues that tool's primary action.  Distant
orders route to the work site and start automatically.  If execution fails, the clicked tile stays
pinned so the inspector can explain why.  In neutral Build inspection mode, LMB only pins/inspects.

### 30.2 Inspector action

A deliberately pinned target may expose the same primary action in the inspector.  This is the
inspection/diagnostic path, not a required second confirmation.  RMB is reserved for inspection,
alternate contextual work, plan-local actions, centering, and target clearing.

### 30.3 Right click

Use shared context-menu behavior for contextual actions and cancellation.

### 30.4 Camera drag

Moves only the viewport.

### 30.5 Mouse wheel

Zooms the world viewport using the shared/vehicle-style camera rules.

### 30.6 Drag placement

In Plan mode, placement tools may own press/drag/release through shared pointer capture.

Releasing a map drag over a toolbar/panel control must not click that control.

---

## 31. Keyboard parity

Keep keyboard access to the same semantic controls.

Support at least:

- Back/Quit;
- search focus;
- Build/Plan/Plans tabs;
- palette navigation;
- viewport movement;
- zoom;
- confirm target;
- build/order action;
- cancel;
- placement-tool selection;
- Execute plans.

Keyboard must invoke the same action handlers as mouse interaction rather than retaining a parallel legacy state machine.

---

## 32. Overlay rendering

Use the actual world renderer for the center viewport.

Construction overlays should be layered conceptually as:

```text
normal terrain
        ↓
planned construction / partial construction overlays
        ↓
selected construction ghost
        ↓
validity indicator
        ↓
selected tile
        ↓
hover indicator
```

Do not modify the map merely to preview a construction result.

The preferred TILES implementation should reuse actual terrain/furniture graphics where possible.

---

## 33. Range, visibility, and knowledge

Do not turn Construction into clairvoyant remote map editing.

### 33.1 Build mode

The viewport may inspect beyond adjacent range, but execution still requires a reachable physical work position.

### 33.2 Plan mode

Allow planning over a useful existing activity/zone-scale range rather than only adjacent tiles, while respecting world knowledge and game constraints.

Avoid new UI-only magic range constants where an existing game range is appropriate.

### 33.3 Visibility

Validity previews must not reveal hidden terrain information that the player should not know.

This requires deliberate handling for distant/obscured targets.

### 33.4 Z-levels

Initial scope should remain on the player's current z-level unless an existing construction explicitly requires another behavior.

Use full tripoint coordinates so later z-level expansion remains possible.

---

## 34. Activity and workspace lifetime

Starting a normal construction activity should suspend/close the Construction Workspace and return control to gameplay.

When the player opens Construction again, restore useful UI state where safe:

- active tab/mode;
- selected construction group;
- category;
- search;
- viewport position where sensible.

Persistent plans and partial constructions naturally come from game state, not the old UI instance.

Do not keep a fragile live UI object across arbitrary gameplay activities unless there is a strong architectural reason.

---

## 35. Source organization

Do not put the complete workspace implementation into `construction.cpp`.

Suggested responsibility split:

```text
src/construction.cpp
    existing construction mechanics
    minimal reusable mechanic APIs where needed

src/construction_ui.cpp
src/construction_ui.h
    Construction Workspace
    layout
    screen state
    palette
    inspector
    viewport orchestration

src/construction_target.cpp
src/construction_target.h
    group/variant target resolution
    validity classification
    explanation data

src/construction_plan.cpp
src/construction_plan.h
    plan API
    blueprint-zone adapter
    plan queries / edits / aggregation
```

Exact names may change to fit project conventions, but responsibilities should remain separated.

Activity code should receive only the minimal changes necessary to expose/reuse existing mechanics.

---

## 36. Shared-helper work

Before adding construction-specific interaction behavior, audit whether it belongs in shared helpers.

Likely reusable additions/extractions:

- world viewport pointer handling;
- map hover/selection state;
- pointer capture across map/pan/placement interactions;
- generic paint/line/rectangle selection geometry;
- toolbar tabs;
- context-menu semantics;
- scrollable palette;
- scrollable inspector;
- clipped-text hover;
- map overlay interaction.

A useful generic primitive may be a drag-selection controller supporting:

```text
single
paint
line
rectangle
```

while callers supply world-coordinate conversion and semantics.

This can later serve Zones and other map designation workflows.

Do not over-generalize construction semantics into a generic RTS editor. Generalize viewport/input/selection behavior, not game-specific construction rules.

---

## 37. Phased implementation

### Phase 1 — Full-screen immediate Construction

Implement:

- full-screen Construction Workspace;
- Build tab;
- actual map viewport;
- palette/categories;
- shared search field;
- inspector;
- map hover and selection;
- construction target resolver;
- ghost result preview;
- ready/unavailable/invalid classification;
- current player location;
- immediate adjacent `Build here`;
- Back control;
- shared scrollbars/controls/input behavior.

Do **not** implement persistent planning yet.

Acceptance:

- selecting a construction does not start it;
- clicking the map does not move the character;
- adjacent build starts the same underlying construction/`partial_con`/`ACT_BUILD` flow as current gameplay;
- UI never directly changes terrain/furniture;
- current construction restrictions remain authoritative.

### Phase 2 — Distant one-shot build orders

Implement:

- distant target selection;
- `Go there and build`;
- route to a valid adjacent work tile;
- pending construction order state;
- revalidation after arrival;
- normal travel interruption behavior.

Acceptance:

```text
select Wooden Wall
click target 8 tiles away
Go there and build
```

causes the character to physically travel before normal construction begins.

No teleporting, remote component consumption, or remote construction.

### Phase 3 — Single-tile plans

Implement:

- Plan tab;
- persistent construction plan adapter;
- existing blueprint-zone backend;
- one-tile planning;
- plan overlay;
- inspect/remove/replace plan;
- reopening Construction shows existing plans.

Acceptance:

A plan survives leaving/reopening the screen without beginning work or consuming materials.

### Phase 4 — Plans tab and Execute Plans

Implement:

- Plans tab;
- plan counts/statuses;
- selecting plans highlights them on the map;
- jump to blocked/in-progress targets;
- `Execute plans`;
- integration with `ACT_MULTIPLE_CONSTRUCTION`;
- clear reporting of missing/blocked/in-progress states.

Acceptance:

The player can create several plans and order the character to carry them out using the existing multi-construction/path/fetch/build pipeline.

### Phase 5 — Multi-tile planning tools

Add:

- paint;
- line;
- rectangle outline;
- filled rectangle;
- shared pointer capture;
- bulk preview;
- validity counts;
- estimated aggregate requirements.

### Phase 6 — Plan-management polish

Add as useful:

- mass remove;
- replace plan type;
- filtering by plan/status;
- recent plans/constructions;
- improved aggregate estimates;
- clearer result/plan graphics;
- jump-to-problem workflows.

### Phase 7 — Reuse for Zones

Once the Construction Workspace proves the interaction model, extract/reuse its generic map-editing pieces for the Zone Manager modernization:

```text
viewport
hover
selection
paint
line
rectangle
overlays
pointer capture
camera controls
context menus
```

Construction-specific resolution/planning remains construction-specific.

---

## 38. Compatibility requirements

Preserve:

- existing saves;
- existing construction JSON;
- construction groups/IDs;
- `partial_con` serialization/semantics;
- `ACT_BUILD`;
- `ACT_MULTIPLE_CONSTRUCTION`;
- NPC construction behavior;
- existing construction blueprint zones;
- existing requirement and completion semantics;
- keyboard usability;
- non-TILES behavior where applicable.

The redesign must not require rewriting construction data files.

---

## 39. Explicit non-goals

This modernization does **not** include:

- magical remote construction;
- instant terrain painting;
- rewriting construction balance;
- replacing pathfinding;
- replacing requirement logic;
- replacing `partial_con`;
- replacing `ACT_BUILD`;
- replacing `ACT_MULTIPLE_CONSTRUCTION`;
- colony-wide worker assignment;
- a new global job scheduler;
- component reservation;
- arbitrary global-range planning;
- a second independent blueprint execution system.

Those require separate design decisions if later desired.

---

## 40. Final architectural invariant

Every construction interaction should preserve this split:

```text
UI
"What does the player want, and where?"
        ↓
Construction resolver
"What does that mean on this tile?"
        ↓
Existing simulation
"Is it valid and what does it require?"
        ↓
Existing activity/path/fetch systems
"Perform the physical work."
        ↓
Map
"Change only when construction completes."
```

The final player-facing workflow should therefore be:

```text
Open Construction
        ↓
select desired construction
        ↓
inspect actual world viewport
        ↓
hover → ghost + validity
        ↓
select target
        ↓
┌───────────────────────┬────────────────────────┐
│ Build                 │ Plan                   │
│                       │                        │
│ Build here            │ persistent blueprint   │
│ Go there and build    │ no resources consumed  │
└───────────┬───────────┴────────────┬───────────┘
            │                        │
            │                 Execute Plans
            │                        │
            └────────────┬───────────┘
                         ↓
               existing CDDA systems
                         ↓
                physical character work
                         ↓
             actual world state changes
```

This gives Construction an RTS-style spatial planning workflow while keeping Cataclysm-DDA's existing construction simulation authoritative.
