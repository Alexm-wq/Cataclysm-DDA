# Vehicle Editor Viewport Integration Plan

Status: implementation plan for `mouse-inventory-0-i-test`

Baseline inspected: `f15a9da97e0db4831dd8ead019364f2d6cb12243` (`Keep weather animating during mouse input`)

## Goal

The first vehicle-editor patch is deliberately a UI/input foundation, not a vehicle-mechanics rewrite.

The vehicle grid becomes the primary editor viewport. It owns mount selection and viewport navigation. Existing Install / Repair / Mend / Refill / Remove / Siphon / Unload / Rename / Change Shape / Assign Crew / Relabel mechanics continue to route through the existing `veh_interact` command handlers.

The minimum successful first implementation is:

- large vehicle viewport using roughly 65-75% of the useful editor area;
- explicit mouse-selectable mount cells;
- independent viewport pan/zoom, with the vehicle centered initially;
- 3-5 mounts of empty editable space around the vehicle bounds;
- obvious selected-mount border;
- right-side inspector listing every installed part at the selected mount;
- independent specific-part selection in that inspector;
- inspector wheel scrolling and a visible/draggable scrollbar;
- existing keyboard mount movement and all existing vehicle commands still functional;
- no right-click action menu, layer filtering, preview mode, or new vehicle mechanics yet.

## Existing architecture and integration points

### `veh_interact` already has the correct command-side mount state

`src/veh_interact.h/.cpp` already has one logical vehicle mount cursor, currently named `dd` on this branch. `move_cursor()` updates that cursor and then refreshes all command-relevant state for the selected square:

- `cpart` — displayed structural part at the selected mount;
- `parts_here` — every vehicle part at that mount;
- `need_repair` — repairable/broken subset;
- `can_mount` — install candidates and requirement ordering;
- `terrain_here`;
- nearby lifting/jacking context.

Command validity in `cant_do()` is already derived from those caches. This is important: mouse selection should feed the same mount refresh path rather than create a second coordinate used only by the new UI.

The legacy coordinate convention is awkward: the actual selected vehicle mount is effectively `-dd`. Existing rendering uses `(vp.mount + dd).rotate(3)` and command/install checks use `-dd`. Activity serialization also stores `dd` directly. Do not casually change those semantics in the first UI patch.

### Current viewport couples selection and camera

`display_veh()` always draws the current selected mount at the center of `w_disp`. The same `dd` value both chooses the mount and translates the entire vehicle diagram. That coupling must be removed.

The editor needs two independent concepts:

1. selected vehicle mount (command target), and
2. viewport transform (where the grid is currently shown after panning/zooming).

Panning must never change the selected mount. Selecting a new mount must not recenter the viewport unless the selection is outside the visible region and keyboard navigation needs `ensure_selected_mount_visible()`.

### Existing part rendering is reusable

`src/vehicle_display.cpp` already supplies:

- `vehicle::get_display_of_tile(...)` for the composite symbol/color at a mount;
- `vehicle::print_part_list(...)` for the current stacked-part naming/detail conventions;
- `vehicle::print_vparts_descs(...)` for existing descriptions.

The editor viewport should continue using `get_display_of_tile()` for the initial composite representation. The new inspector should reuse the naming/content logic from `print_part_list()` rather than inventing different tank/cargo/fuel labels. A custom inspector renderer is still preferable because clickable rows, persistent selected-part state, scrolling, and exact row hit testing are needed.

### Vehicle bounds helper already exists

`vehicle::get_bounding_box(bool use_precalc = true, bool no_fake = false)` exists. For the editor's local mount-coordinate canvas, use the non-precalculated/local form and exclude fake parts where appropriate. Expand the resulting bounds by a fixed editor margin (default 4 mounts; acceptable range 3-5).

Do not let the viewport pan infinitely. Clamp the canvas to those expanded bounds plus enough half-viewport slack to keep edge cells reachable.

### Existing mouse infrastructure should be reused

The branch's unified inventory already has the correct mouse-event pattern:

- register `SELECT`, `CLICK_AND_DRAG`, `MOUSE_MOVE`, `SEC_SELECT`, `SCROLL_UP`, `SCROLL_DOWN` as needed;
- use `input_context::get_coordinates_text(window)`;
- validate with `window_contains_point_relative(...)`;
- route wheel behavior based on the window under the cursor;
- capture mouse-down state when an action needs robust press/release semantics across redraws;
- invalidate/redraw through the current `ui_adaptor` rather than rebuilding the screen.

The branch also already defines middle-mouse camera actions for `DEFAULTMODE` (`CAMERA_PAN_START` / `CAMERA_PAN_END`). `VEH_INTERACT` needs equivalent category bindings or a deliberately shared binding path so the same physical interaction works in the vehicle editor.

### Scrollbar support is already first-class

Use the `scrollbar` class from `output.h`, not the legacy `draw_scrollbar()` helper. It supports:

- `content_size()`;
- `viewport_pos()`;
- `viewport_size()`;
- `set_draggable(input_context&)`;
- `handle_dragging(...)`;
- `apply(...)`.

The installed-parts list should therefore have a visible scrollbar from the first implementation, including draggable-thumb support if the input path is active.

## State model

Keep one authoritative mount selection and one authoritative part selection.

Recommended first-patch state inside `veh_interact`:

```cpp
// Legacy command cursor remains authoritative for command compatibility.
point_rel_ms dd = point_rel_ms::zero;

// Actual selected vehicle part index, if a specific stacked part is selected.
std::optional<int> selected_part;

// Viewport-only state. Never used by command mechanics.
point editor_origin_chars = point::zero;
int editor_zoom = default_editor_zoom;
bool editor_view_initialized = false;
bool editor_pan_active = false;
point editor_pan_anchor = point::zero;
point editor_pan_origin_at_press = point::zero;

// Inspector state.
int inspector_part_top = 0;
int inspector_detail_top = 0;
```

Do not add a second mutable `selected_mount` alongside `dd` unless `dd` is removed completely in the same change. Two authoritative mount coordinates would be worse than the current design.

Instead encapsulate the legacy sign convention immediately:

```cpp
point_rel_ms selected_mount() const;
void select_mount( map &here, const point_rel_ms &mount );
void refresh_mount_context( map &here );
```

`selected_mount()` returns the actual mount coordinate. `select_mount()` assigns the legacy cursor representation and calls one shared `refresh_mount_context()`. `move_cursor()` becomes a keyboard-relative wrapper around `select_mount()` rather than containing its own cache-refresh implementation.

This gives later code a sane API without changing activity serialization in the first patch.

### Selected-part rules

`selected_part` stores an actual vehicle part index, not an index into `parts_here`.

On mount change:

1. rebuild `parts_here`;
2. if `selected_part` is still present in `parts_here`, preserve it;
3. otherwise select `cpart` when valid;
4. otherwise select the first real part in `parts_here`;
5. otherwise clear it for an empty mount.

Clicking an inspector row sets `selected_part = parts_here[row]` and updates the detail pane only. It must not alter the mount.

The existing transient `sel_vehicle_part` / `sel_vpart_info` variables remain command-operation state in phase one. Do not silently repurpose them as permanent editor selection because Install mode points `sel_vpart_info` at a candidate that is not an installed part.

## Layout

Replace the current three-column layout in normal editor mode with four conceptual regions:

```text
┌─────────────────────────────────────────────────────────┬──────────────────┐
│ Vehicle / mode / existing command hotkeys               │                  │
├─────────────────────────────────────────────────────────┤                  │
│                                                         │ Mount (+1,-2)    │
│                                                         │                  │
│                  VEHICLE VIEWPORT                       │ Installed parts  │
│                                                         │ Frame        100%│
│          large pan/zoom/clickable grid                  │ Seat          83%│
│                                                         │ Tank          91%│
│                                                         │ Roof         100%│
│                                                         │             █    │
│                                                         ├──────────────────┤
│                                                         │ Selected part    │
│                                                         │ details / desc   │
├─────────────────────────────────────────────────────────┴──────────────────┤
│ compact vehicle summary: speed | mass | fuel | battery | wheels | etc.     │
└────────────────────────────────────────────────────────────────────────────┘
```

Target proportions at ordinary desktop terminal sizes:

- viewport: approximately 70-72% of body width;
- inspector: approximately 28-30%;
- top command/mode strip: 1-3 rows;
- compact bottom summary: approximately 3-5 rows;
- remaining vertical space belongs to the viewport/inspector body.

Use clamps/minimum widths rather than hard-coded percentages only. The inspector should retain enough width to display useful part names (target minimum around 30 terminal columns where possible). The viewport gets the remainder.

At small terminal sizes, degrade gracefully: reduce cell zoom and/or inspector width before allowing negative/zero window sizes. Do not crash because the desktop-oriented layout does not fit.

### Existing command submodes

Do not rewrite Install/Repair/Remove/etc lists in this phase.

Normal editor mode uses the new viewport + inspector. When an existing command opens its chooser, the right-side inspector region can be temporarily repurposed for the existing `w_list`, `w_msg`, `w_details`, and overview content. The viewport should remain visible whenever practical so the selected mount stays spatially obvious.

The command handler logic, requirement computation, theft checks, activities, time costs, and command completion behavior remain unchanged.

## Grid representation

A one-character mount is too small for reliable mouse editing. Render each mount as a multi-character cell with an explicit border/hit rectangle.

Suggested zoom pitches (exact values can be tuned after the first compile):

```text
compact: 3 x 3 chars
normal:  5 x 3 chars
large:   7 x 5 chars
x-large: 9 x 5 chars
```

Use the same logical grid at every zoom. The vehicle symbol from `get_display_of_tile()` is centered in the cell. Empty cells remain visible inside the expanded editor bounds.

Selected mount: draw a strong full-cell border/highlight. Do not rely only on reversing the vehicle glyph; selection must remain obvious on an empty coordinate.

Optional hover treatment can be included if cheap, but it is not required for the first functional milestone.

## Coordinate transforms

Centralize all mapping. No input handler should perform ad-hoc `rotate(3)` / sign arithmetic.

Recommended helpers:

```cpp
point editor_grid_from_mount( const point_rel_ms &mount ) const;
point_rel_ms mount_from_editor_grid( const point &grid ) const;
point viewport_cell_center( const point_rel_ms &mount ) const;
std::optional<point_rel_ms> mount_at_viewport_point( const point &local ) const;
inclusive_rectangle<point> viewport_rect_for_mount( const point_rel_ms &mount ) const;
```

Preserve the current visual orientation: the existing renderer maps mount deltas through `.rotate(3)`. Its inverse is `.rotate(1)`.

A simple implementation is to make `editor_origin_chars` the viewport-local terminal coordinate at which vehicle mount `(0,0)` is centered:

```text
mount
  -> rotate(3)
  -> multiply by current cell pitch
  -> add editor_origin_chars
  -> viewport-local terminal coordinate
```

The inverse hit test subtracts `editor_origin_chars`, resolves the containing cell using the current pitch, then rotates the grid coordinate back with `rotate(1)`.

Use floor/nearest-cell helpers carefully for negative coordinates. Do not rely on C++ truncating integer division toward zero because that produces asymmetric hit boxes left/up of origin.

All later layers, context menus, and preview/editor split work should consume these helpers rather than rebuilding coordinate math.

## Initial centering and pan clamp

On first layout or vehicle change:

1. obtain local vehicle mount bounds;
2. expand by four mounts on all sides;
3. rotate bounds into editor-grid orientation if necessary;
4. choose a zoom that fits a useful portion of the vehicle while retaining readable cells;
5. place the center of the vehicle bounds at the center of the viewport;
6. mark the viewport initialized.

On window resize, preserve the currently viewed mount as much as possible. Recompute window geometry and clamp the origin rather than always snapping back to the vehicle center.

Middle-drag changes only `editor_origin_chars`. Clamp after every pan update.

Keyboard selection should normally leave the camera alone. If the selected mount moves outside the viewport's safe inner rectangle, call `ensure_selected_mount_visible()` and pan just enough to bring it back into view. This prevents the old behavior where every cursor move forcibly recenters the vehicle.

## Mouse interaction routing

Add a dedicated `veh_interact::handle_mouse(...)` or equivalent so `do_main_loop()` stays readable.

Priority routing:

1. active draggable scrollbar;
2. inspector region;
3. viewport region;
4. other command/UI regions.

### Viewport

- left release (`SELECT`): resolve `mount_at_viewport_point()`, clamp/check it against editor canvas bounds, call `select_mount()`;
- middle press: begin pan and capture mouse point + starting origin;
- `MOUSE_MOVE` during pan: update origin from drag delta and redraw;
- middle release: end pan;
- wheel up/down: zoom in/out around the mouse cursor;
- moving/zooming the viewport never changes `selected_mount()`.

Zoom should be cursor-anchored: record the mount/cell under the cursor before changing pitch, change zoom, then shift `editor_origin_chars` so that same logical point stays under the cursor. This avoids the map jumping toward the center on every wheel tick.

### Inspector installed-parts list

- left click row: select that exact installed part;
- wheel: scroll the list, not the vehicle viewport;
- scrollbar thumb: draggable using `scrollbar::set_draggable()` / `handle_dragging()`;
- keyboard inspector navigation may be added if it can be done without stealing existing vehicle directional bindings; otherwise keep click + wheel in the first patch and retain existing command keyboard paths.

The list keeps the selected row visible whenever selection changes programmatically.

### Mouse-event robustness

Reuse the inventory's press/release-capture approach if any inspector button or scrollbar interaction can redraw between press and release. Never rediscover a different row on release after a layout-changing redraw.

## Inspector content

Top section:

```text
Mount (+1, -2)
Installed parts
────────────────
Frame                  100%
Reinforced quarterpanel 73%
60 L tank               91%
Roof                    100%
```

Rows come directly from `parts_here`. Preserve Cataclysm's existing part naming/status semantics from `vehicle::print_part_list()`:

- real/active parts only;
- durability/status prefix/name;
- tank/battery content when useful;
- cargo used/maximum volume when useful;
- Interior/Exterior information where it remains readable;
- mount label if present.

A condition percentage can be displayed if there is an existing canonical helper for base-item damage/maximum damage. If not, do not introduce a second durability formula merely for cosmetics in the first pass; keep the existing durability indication and add percentages once verified.

Bottom section for a selected installed part:

```text
60 L vehicle tank

Condition   91%
Contents    23 / 60 L
Fuel        Gasoline
Location    (+1,-2)

[existing vpart description]
```

Use existing `vpart_info::format_description()` and existing fuel/cargo APIs. This section should have its own scroll offset if the description does not fit. It may also use a scrollbar.

For an empty mount, show the coordinate and an explicit `No installed parts` state. Do not treat an empty mount as no selection: empty coordinates are necessary install targets.

## Bottom vehicle summary

The old screen spends eight rows across three windows on stats. The first editor layout should compress the always-visible summary to the most useful high-level values, such as:

- safe/max speed;
- acceleration;
- mass;
- battery/fuel summary;
- wheels/boat status;
- drag/rolling/offroad where space permits.

Do not delete the underlying existing stat calculations. Less-critical values can remain available in the inspector/detail area or be retained in a compact multi-row summary depending on available width. This is presentation-only.

## Command compatibility requirements

The following must stay mechanically identical in phase one:

- theft/ownership checks;
- install candidate calculation and `vehicle::can_mount()`;
- repair target validation and repair times;
- removal dependency checks and removal times;
- refill/siphon/unload behavior;
- mend behavior;
- shape selection/activity handoff;
- crew assignment;
- relabel/rename;
- crafting inventory/tool/lifting calculations;
- `ACT_VEHICLE` activity serialization/target semantics.

Mouse mount selection must eventually arrive at the same `cpart`, `parts_here`, `need_repair`, `can_mount`, `terrain_here`, and lifting state that keyboard `move_cursor()` produces today.

A useful debug invariant during implementation is:

```text
select mount M by keyboard == select mount M by mouse
```

with equality for `selected_mount`, `cpart`, `parts_here`, `need_repair`, and command availability.

## Files expected to change in the first implementation

Primary:

- `src/veh_interact.h`
  - viewport/inspector state;
  - transform/selection/mouse helper declarations;
  - new windows or renamed editor windows.

- `src/veh_interact.cpp`
  - layout allocation;
  - mount-context extraction;
  - viewport rendering;
  - inspector rendering;
  - mouse routing;
  - pan/zoom/bounds logic;
  - main-loop integration.

Likely:

- `data/raw/keybindings.json`
  - `VEH_INTERACT` bindings for SELECT / mouse move / scrolling / middle-pan actions if category lookup does not inherit the required global/default bindings.

Potential but avoid unless necessary:

- `src/vehicle_display.cpp` / `src/vehicle.h`
  - only if a small reusable helper should be extracted for part-row text/condition. Prefer not to alter vehicle mechanics for the first editor patch.

## Implementation sequence for the first patch

### Stage 1 — normalize selection API without changing behavior

Extract `selected_mount()`, `select_mount()`, and `refresh_mount_context()` from the current `dd`/`move_cursor()` logic. Verify keyboard cursor behavior still produces identical `cpart`, `parts_here`, and command availability.

Add `selected_part` and selection validation, but do not use it to drive existing command handlers yet.

### Stage 2 — replace window geometry

Create the large viewport, inspector part-list region, inspector detail region, and compact stats strip. Keep resize handling in the existing `ui_adaptor`.

At this point the old vehicle can still be rendered with no mouse support; this isolates layout failures from input failures.

### Stage 3 — introduce editor transform and large cells

Implement bounds, expanded canvas, initial centering, zoom pitch, mount-to-screen and screen-to-mount helpers. Rewrite `display_veh()` to draw the explicit grid and vehicle composite symbols through this transform.

Make the selected mount border visible even when the mount is empty.

### Stage 4 — mouse mount selection

Register mouse actions and route viewport clicks through `mount_at_viewport_point()` -> `select_mount()`. Mouse and keyboard must now converge on the same mount-context refresh.

### Stage 5 — pan and zoom

Add middle-drag viewport panning, bounds clamping, wheel zoom, and cursor-anchored zoom. Add `ensure_selected_mount_visible()` for keyboard navigation.

### Stage 6 — stacked-parts inspector

Render `parts_here` as clickable rows, add `selected_part`, wheel scrolling, scrollbar and draggable thumb, selected-part details, and empty-mount state.

### Stage 7 — command-mode compatibility pass

Run each existing command entry path from a mouse-selected mount and from a keyboard-selected mount. Adjust window placement only; do not rewrite mechanics.

## First-patch acceptance tests

Manual tests should include all of the following before adding context menus/layers:

1. Open editor on a tiny vehicle, normal car, and large multi-tile vehicle.
2. Vehicle is centered initially with visible empty grid around it.
3. Left-click every side of the vehicle and confirm the selected mount border lands exactly under the mouse.
4. Click empty coordinates inside the editor margin; they remain valid selected mounts and Install still sees them correctly where legal.
5. Compare keyboard and mouse selection of the same mount.
6. Select a mount containing multiple stacked parts; inspector lists all of them.
7. Click each inspector row and verify the detail pane changes without changing the mount.
8. Test a tank, battery, cargo part, broken part, roof/armor/structure stack, and labeled mount.
9. Overflow the installed-parts list; wheel scroll and scrollbar both work and selected row remains stable.
10. Middle-drag aggressively; selected mount and selected part do not change.
11. Zoom at the center and near each viewport edge; the logical point beneath the cursor remains stable.
12. Keyboard-move selection until it leaves the visible area; viewport pans only enough to reveal it rather than recentering every step.
13. Resize the window at several dimensions; no negative window sizes, stale hit boxes, or lost selection.
14. Run Install, Repair, Mend, Refill, Remove, Siphon, Unload, Rename, Change Shape, Assign Crew, and Relabel from the new layout.
15. Confirm activity time/move costs and targets are unchanged.

## Deliberately deferred

Do not include these in the first viewport patch:

- right-click context actions;
- Ground / Middle / Roof / Composite layers;
- live world preview;
- drag-and-drop vehicle parts;
- install-by-dragging a part from a catalog;
- new repair/remove/refill mechanics;
- persistent editor state across separate openings unless it falls out trivially;
- renderer/tile-art rework.

However, keep one future hook in the viewport renderer: a single `part_visible_in_editor(...)` or equivalent filter point that initially returns true. Later layer filtering can then change render/selectability without replacing the coordinate transform.

## Phase order after the viewport foundation

1. Right-click context menu operating on `selected_mount` / `selected_part` and calling the existing commands.
2. Pure visualization/selectability layers: Composite, Ground, Middle, Roof.
3. Editor / Preview / Split presentation modes using the already-stable editor transform and selection model.

The critical invariant for all later work is that the viewport owns spatial selection. Commands consume that selection; they do not create their own independent coordinates.
