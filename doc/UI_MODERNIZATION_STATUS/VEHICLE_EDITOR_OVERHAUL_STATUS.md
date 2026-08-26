# Vehicle Editor Overhaul — Living Implementation Status

Status: **active — approximately 90% complete**

Completion estimate: maintainer estimate, not a percentage calculated from commit count.

Branch: `mouse-inventory-0-i-test`

Last audited implementation head: `fef22b8181b197d266841d5d96fcb95844fe1e42` (`Fix split live preview zoom anchor`)

Last audited: 2026-08-26

Related detailed plan: `../VEHICLE_EDITOR_VIEWPORT_IMPLEMENTATION_PLAN.md`

Related roadmap: `../UI_MODERNIZATION_IMPLEMENTATION_PLAN.md`

## Purpose of this document

This is the living implementation record for the mouse-first vehicle editor overhaul.

The original viewport implementation plan describes the architecture that was intended before implementation. This file records **what the branch actually contains now**, including features that have already advanced beyond the original first-patch scope: visual layers/filters, context actions, live install UI, viewport modes, and live rendered vehicle previews.

Update this file as the implementation changes. The completion percentage is a qualitative maintainer estimate based on remaining user-visible work and stabilization, not commit volume.

## Current state

The vehicle editor has already crossed the main architectural barrier from the old cursor-centered diagram into a first-class editor viewport.

The editor now has an independent viewport/camera, mouse-selectable mounts, an inspector, panning/zooming, semantic layer/filter controls, context actions, a live install pane, multiple viewport modes, and a live tiles preview with its own camera controls. Existing vehicle command mechanics still route through `veh_interact` rather than being reimplemented as UI-only rules.

The remaining work is predominantly **polish, edge-case hardening, layout/input consistency, and final parity checks**, not a redesign of the redesign.

Current estimate: **~90% complete**.

## Implemented functionality

### First-class editor viewport

- [x] Vehicle grid promoted to the primary editing surface instead of a small cursor-centered diagram.
- [x] Large viewport layout with the inspector occupying the smaller side region.
- [x] Vehicle mount selection separated from viewport/camera position.
- [x] Mouse-selectable mount cells.
- [x] Visible selected-mount treatment.
- [x] Empty editable area around the vehicle can be presented as part of the editor canvas.
- [x] Vehicle is initially centered appropriately in the editor view.
- [x] Existing command-side mount state remains authoritative for install/remove/repair/etc. behavior.

### Inspector and stacked-part selection

- [x] Right-side inspector introduced for the selected mount.
- [x] Installed parts at a selected mount are presented independently of the main grid.
- [x] A specific stacked vehicle part can be selected in the inspector rather than treating the mount as a single opaque object.
- [x] Inspector/context action API use has been corrected after implementation testing.
- [x] Vehicle condition/detail presentation received visual cleanup and consistent condition coloring.

### Mouse navigation and camera behavior

- [x] Middle-mouse viewport panning.
- [x] Pan state hardened against mouse press/release lifecycle problems.
- [x] Mouse wheel/editor zoom support.
- [x] Zoom anchored to the cursor rather than blindly zooming around the viewport center.
- [x] Vehicle editor orientation aligned with world-facing orientation.
- [x] Mouse routing between viewport and side panes corrected so wheel/click behavior applies to the region under the cursor.
- [x] Editor redraw path cleaned up after the initial viewport implementation.

### Visual filters and layers

- [x] Vehicle editor visual filters/layers implemented.
- [x] Layer/filter controls use semantic vehicle categories rather than arbitrary rendering buckets.
- [x] Filter contrast was improved after first implementation.
- [x] Ghost/filtered-part visibility was improved so hidden context remains readable without overpowering the active layer.
- [x] View filtering remains presentation/editor state rather than mutating vehicle data.

### Context actions

- [x] Vehicle editor context actions implemented.
- [x] Context actions operate from selected mount/part state rather than creating a separate command target.
- [x] Inspector context actions were fixed after initial implementation.
- [x] Later context-action fixes hardened the user-facing action path.
- [x] Test-mode support was added to make unfinished/new editor interactions easier to expose deliberately during development.

### Live install pane

- [x] Live vehicle install pane implemented inside the new editor workflow.
- [x] Install list/search interaction integrated into the editor rather than relying entirely on the old modal flow.
- [x] Install search label/interaction cleanup applied.
- [x] Double-click installation of a selected vehicle part supported.
- [x] Install actions remain tied to normal vehicle installation validation/mechanics.

### Viewport mode controls

- [x] Explicit vehicle editor viewport mode buttons added.
- [x] Mode selection is mouse-accessible rather than being hidden behind keyboard-only state.
- [x] Live rendered viewport mode introduced alongside the editor/composite-style view.

### Live tiles vehicle preview

- [x] Live vehicle editor viewport rendering implemented using the game's tiles rendering path.
- [x] Tiles-rendered vehicle preview integrated into the editor rather than rendered as a disconnected screenshot.
- [x] Dedicated live-preview camera controls added.
- [x] Live preview panning implemented and coordinate-type issues fixed.
- [x] Live preview zoom anchored toward the cursor.
- [x] Preview zoom behavior adjusted to match gameplay expectations.
- [x] Raw-pixel zoom handling added/fixed for the preview path.
- [x] Split editor/live-preview zoom anchoring received a dedicated correction at the current audited head.

### Input, keybinding, and development integration

- [x] Vehicle editor mouse actions registered through normal input contexts.
- [x] New mouse/editor actions added to keybinding data where required.
- [x] SDL mouse state/routing extended for editor camera behavior.
- [x] Tiles renderer received small hooks needed by live preview rendering.
- [x] Game/action routing received integration hooks for editor/test behavior.
- [x] Dedicated workflow support added for toggling Vehicle Editor Test mode during development builds.

## Remaining / partially complete work

The remaining ~10% is primarily stabilization and UX completion.

### High-priority completion work

- [ ] Finish live-preview pan/zoom edge-case testing. The newest commits are still correcting zoom-anchor behavior, so this is the clearest active stabilization area.
- [ ] Verify cursor-anchored zoom at different UI scales, tile sizes, viewport dimensions, and split-pane sizes.
- [ ] Verify editor-grid and live-preview cameras remain independent where intended and synchronized only where explicitly designed.
- [ ] Audit resize/reflow behavior so selection, inspector state, filters, camera origin, and hit testing survive window-size changes.
- [ ] Audit stacked-part inspector selection after install/remove/repair operations that change the part list at the selected mount.
- [ ] Audit right-click/context action availability for empty mounts, stacked parts, broken parts, tanks, cargo, and unusual vehicle components.
- [ ] Finalize any remaining visual hierarchy/contrast issues between active layer, ghosted layers, selected mount, selected part, and install preview.
- [ ] Check keyboard parity for every new mouse-first editor operation and ensure keyboard navigation works on the same authoritative selection state.

### Live install / command parity

- [ ] Verify the live install pane exposes all important invalid/unavailable reasons clearly enough for mouse-first use.
- [ ] Verify install search/filter state remains stable across install actions and editor redraws.
- [ ] Confirm install/remove/repair/refill/etc. paths do not accidentally diverge from normal `veh_interact` requirement, tool, activity, or move-cost rules.
- [ ] Identify any remaining legacy command panels that should be retained for compatibility versus migrated into the new inspector/context workflow.

### Cleanup and regression hardening

- [ ] Remove or simplify development-only/editor Test-mode scaffolding once the relevant functionality no longer needs gating, or document why it remains useful.
- [ ] Add targeted regression coverage where practical for selection/camera coordinate transforms and vehicle mount resolution.
- [ ] Perform manual coverage with very small, very large, asymmetric, rotated, and heavily stacked vehicles.
- [ ] Check narrow-terminal/responsive degradation rather than assuming the normal desktop width.
- [ ] Final pass over redraw frequency to avoid unnecessary full-window redraws during mouse movement, preview animation, or pane interactions.

### Follow-on work outside this editor's 100% gate

These are related vehicle/UI modernization tasks but should not keep this editor permanently below 100%:

- [ ] Separate **Vehicle Controls / Driving UI** dashboard from the vehicle builder/editor.
- [ ] Reuse viewport/camera primitives in Construction, Zones, Overmap, and other map-editor-like activities where appropriate.
- [ ] Extract shared inspector/search/selector pieces only after a second real caller proves the abstraction useful.

## Primary edited code surface

A comparison from immediately before the first-pass viewport (`9918616c`) through the audited implementation head (`fef22b81`) shows the vehicle-editor series concentrated in a relatively small set of files. The dominant implementation is in `veh_interact`.

### Core editor implementation

| File | Role in the overhaul |
| --- | --- |
| `src/veh_interact.cpp` | Main editor redesign: viewport layout, selection, inspector, pan/zoom, filters/layers, context actions, install pane, mode buttons, live preview state and interaction. |
| `src/veh_interact.h` | New persistent editor state, camera/selection/filter/preview declarations and helpers. |
| `src/veh_utils.cpp` / `src/veh_utils.h` | Vehicle utility behavior adjusted where editor actions/selection require it. |

Across the audited vehicle-editor range, `src/veh_interact.cpp` alone contains roughly **2,400 additions and 380 deletions**, which accurately reflects that the editor architecture itself has been rebuilt there rather than distributed into a second parallel vehicle UI.

### Tiles / live preview integration

| File | Role in the overhaul |
| --- | --- |
| `src/cata_tiles.cpp` / `src/cata_tiles.h` | Small renderer hooks needed to draw the live vehicle preview from the editor. |
| `src/sdltiles.cpp` / `src/sdltiles.h` | SDL/tile mouse and camera integration used by the editor/live preview. |
| `src/sdl_utils.h` | Supporting SDL coordinate/input helpers used by the live-preview path. |

### Game/input integration

| File | Role in the overhaul |
| --- | --- |
| `src/game.cpp` | Game-level integration used by editor/live preview/test behavior. |
| `src/handle_action.cpp` | Action routing/integration for editor test and viewport behavior. |
| `data/raw/keybindings.json` | New editor mouse/camera actions and bindings. |

### Development workflow

| File | Role in the overhaul |
| --- | --- |
| `.github/workflows/toggle-vehicle-editor-test-mode.yml` | Development workflow for explicitly toggling Vehicle Editor Test mode. |
| `.github/workflows/cleanup-tmp-branches.yml` | Supporting temporary-branch cleanup introduced during this development workflow. |

## Reused existing infrastructure that was not rewritten

This distinction matters when maintaining the editor.

`src/vehicle_display.cpp` provides useful existing vehicle display/part-description behavior and was identified in the original implementation plan as reusable infrastructure. However, its branch history shows **no vehicle-editor overhaul commits in this series**. Do not describe it as an edited editor file unless a future commit actually changes it.

Similarly, the editor deliberately reuses existing vehicle mechanics/validation wherever possible. Rendering or UI code should not become a second implementation of installability, repairability, fuel rules, tool requirements, or activity timing.

## Representative implementation timeline

This list emphasizes architectural/user-visible milestones rather than every compile or presentation fix.

| Commit | What it established |
| --- | --- |
| [`3a166ff9`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/3a166ff99af27ce2fcff1a6577be2a8e7bab2f7a) | Original vehicle editor viewport integration plan. |
| [`b7d8f755`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/b7d8f7552a7f4900b28d5e7551947c4251d35d73) | First-pass first-class vehicle editor viewport, large layout, independent selection/camera, inspector and mouse input foundation. |
| [`810c1d3a`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/810c1d3a8ca73f9934d268086f562d15e913d4ea) | Editor redraw cleanup after the first pass. |
| [`6ef9077b`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/6ef9077bf5452b1d79cbf631bb99bc7a7c9dc326) | Correct mouse pane routing. |
| [`6c005df9`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/6c005df976d809ac1f6a7fc18ec6b18c07713e09) | Hardened middle-mouse pan state. |
| [`1da5d7e6`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/1da5d7e60d14e1e034ecd6216b3a493671bc3f4d) | Editor orientation aligned with world facing. |
| [`dcd890db`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/dcd890dbfacb5a12743db57e20fbafd5cc9f9b4e) | Cursor-anchored editor zoom. |
| [`49fc791a`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/49fc791a143a35597563079cfa05dbfb78ecf636) | Visual filters and layers. |
| [`34731cee`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/34731cee67876754ce91cfa10305fa8ab52aa373) | Semantic vehicle editor filter categories. |
| [`c82e47ea`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/c82e47ead39a2548d521f86e1de608449b1a6242) | Improved ghost/filtered-part visibility. |
| [`9e4d7dd8`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/9e4d7dd8618c94de219f14dd423938fdcd0b10f5) | Context actions and Vehicle Editor Test mode. |
| [`914d69ae`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/914d69ae40624a615bdac519cbef6e43d4d7727a) | Inspector context-action fixes. |
| [`c2f6bbf0`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/c2f6bbf0262396f518aa29c4dc00ad951b95de81) | Live vehicle install pane. |
| [`6ca09deb`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/6ca09deb32c917023c29ccb65e98859ca654d156) | Double-click vehicle part installation. |
| [`12fe8aa3`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/12fe8aa37b546ecd42a220badf9c5255d5dc2c8e) | Explicit vehicle editor viewport mode buttons. |
| [`ca8d1bcf`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/ca8d1bcf8ed575501b059b52a696b5de548b8da0) | Live vehicle editor viewport rendering. |
| [`5c5113f7`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/5c5113f7b058941c802766d3a3547e60a17eb031) | Live preview camera controls. |
| [`5206e6a4`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/5206e6a40500868d00842e6460e65a24812ba47d) | Cursor-anchored live-preview zoom. |
| [`ca52eeec`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/ca52eeec8af22d463bde6b3f6b8863de7a975220) | Live-preview zoom behavior aligned with gameplay. |
| [`fef22b81`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/fef22b8181b197d266841d5d96fcb95844fe1e42) | Latest audited split live-preview zoom-anchor correction. |

## Evidence note

The first-pass viewport commit alone changed `veh_interact.cpp/.h` by hundreds of lines and introduced the independent editor selection/camera foundation. The full audited vehicle-editor range from `9918616c` to `fef22b81` spans **15 edited implementation/integration files** plus documentation, with approximately **3,000 net lines of implementation-side change** across the editor and its rendering/input hooks.

The comparison makes the architectural concentration clear:

- `src/veh_interact.cpp`: +2441 / -378
- `src/veh_interact.h`: +144
- the rest of the touched files are comparatively small integration hooks.

That is a useful maintenance signal: future editor-specific behavior should normally remain centralized in `veh_interact` unless it is genuinely reusable renderer/input infrastructure.

## Completion gate

Treat the vehicle editor overhaul as 100% for its own scope when all of the following are true:

1. mount and stacked-part selection remain correct across all install/remove/repair mutations;
2. panning and cursor-anchored zoom behave predictably in both editor-grid and live-preview modes;
3. resizing/UI scaling does not corrupt coordinate transforms or hit testing;
4. filters/layers and ghosting clearly communicate what is active without hiding required context;
5. context actions and live install UI expose the same valid/invalid outcomes as normal vehicle mechanics;
6. keyboard and mouse control operate on the same authoritative selection state;
7. no normal editor interaction requires Test mode merely to avoid a broken production path;
8. the editor is stable on small, large, rotated, asymmetric, and heavily stacked vehicles.

A separate driving dashboard and reuse of the viewport framework in other game systems are follow-on modernization work, not blockers for calling the vehicle editor complete.

## How to update this document

When vehicle editor work lands:

1. change `Last audited implementation head` to the newest reviewed editor commit;
2. move completed items from **Remaining** into the appropriate **Implemented** section;
3. add milestone commits only for architectural changes, new user-visible capabilities, or important stability invariants;
4. add files to **Primary edited code surface** only when the editor actually starts modifying them;
5. keep reused-but-unchanged infrastructure in the separate reuse section;
6. adjust the completion estimate from remaining user-visible work, not the number or size of commits;
7. keep driving UI and other broader vehicle modernization in the main roadmap unless they become part of the editor itself.