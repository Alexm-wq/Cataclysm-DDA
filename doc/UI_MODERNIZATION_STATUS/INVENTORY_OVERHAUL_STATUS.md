# Inventory Overhaul — Living Implementation Status

Status: **active — approximately 90% complete**

Completion estimate: maintainer estimate, not a percentage calculated from commit count.

Branch: `mouse-inventory-0-i-test`

Last audited branch head: `fef22b8181b197d266841d5d96fcb95844fe1e42` (`Fix split live preview zoom anchor`)

Last audited: 2026-08-26

Related roadmap: `../UI_MODERNIZATION_IMPLEMENTATION_PLAN.md`

## Purpose of this document

This is the living implementation record for the desktop mouse-driven inventory overhaul.

Unlike the long-term UI roadmap, this document tracks **what is already implemented in the branch**, which source files the work actually touches, what major commits established each part of the system, and what remains before the overhaul can reasonably be called complete.

Update this file as the implementation changes. Do not infer completion from the number of commits: much of the commit history is stabilization work around a relatively small number of architectural changes.

## Current state

The inventory overhaul is no longer an experimental mouse layer on top of the old advanced inventory. The branch now has a substantially different interaction model built around a persistent, mouse-capable unified workspace.

The main architecture is in `advanced_inv`, but the feature crosses activity handoff, item locations, pockets/containers, reload handling, SDL input, game UI blocking, and tests. The most important remaining work is therefore **edge-case completion, regression hardening, cleanup, and extraction/reuse**, rather than another fundamental rewrite.

Current estimate: **~90% complete**.

## Implemented functionality

### Unified desktop inventory workspace

- [x] Desktop mouse controls added to advanced inventory.
- [x] Unified mouse inventory workspace established rather than treating mouse input as isolated shortcuts.
- [x] Mouse row hit-testing and selection integrated with the existing pane/cursor model.
- [x] Mouse and keyboard navigation kept coherent instead of rendering two unrelated selections.
- [x] Clickable sorting controls.
- [x] Persistent workspace/status handling through redraws and ordinary interaction.
- [x] World UI is blocked correctly behind the persistent inventory while the inventory owns interaction.
- [x] The world/map can remain live where appropriate without briefly replacing the persistent inventory frame.

### Selection and navigation

- [x] Normal single-click selection.
- [x] Ctrl multi-select support.
- [x] Selection state survives ordinary scrolling and redraws.
- [x] Wheel navigation no longer leaves a stale second highlight behind.
- [x] Container chevron expansion/collapse does not steal or duplicate selection.
- [x] Opening a container as the new pane location deliberately clears the old selection where required.
- [x] Selection state is kept coherent when rows are regenerated after inventory changes.

### Nested containers and hierarchy

- [x] Nested container contents can be represented inline as a hierarchy/tree.
- [x] Expand/collapse state is persistent instead of being rebuilt from scratch every frame.
- [x] Containers can be opened through mouse interaction, including double-click behavior.
- [x] Mutable traversal of nested items is supported for operations that actually move/change the item.
- [x] Nested item extraction and unload paths were hardened against stale references/lifetime crashes.
- [x] Data caches used by nested inventory presentation are made self-healing when the underlying inventory changes.

### Drag and drop

- [x] Drag/drop between inventory panes.
- [x] Same-pane transfers into containers.
- [x] Hierarchical drag routing for nested container targets.
- [x] Invalid drag/drop state is tracked and cleared with the drag lifecycle rather than remaining stuck after a failed operation.
- [x] Drag source/target state survives the inventory refreshes required by actual game item movement.
- [x] Multi-item drag operations can operate on the active selection rather than only the row under the cursor.
- [x] Drop-path crashes caused by mutable/stale item locations were addressed.

### Quantity and split-stack interaction

- [x] Quantity selection integrated into mouse transfers.
- [x] Split-stack workflow implemented.
- [x] Quantity/split modal lifetime bugs fixed.
- [x] Stack selection is preserved correctly after a split.
- [x] Split and quantity dialogs no longer intentionally tear down and redraw the whole inventory workspace.
- [x] Result/status presentation is synchronized with the post-operation inventory state.
- [x] Modal/activity handoff was hardened to avoid the most obvious inventory-frame flicker.

### Stack recombination and stacking policy

- [x] Dragging compatible identical items back together can recombine stacks using game-compatible stack behavior.
- [x] Mutable stack item locations are resolved correctly for recombination operations.
- [x] Explicit stack actions are supported independently of incidental row grouping.
- [x] Inventory auto-stack transfer mode/toggle added.
- [x] Explicit stacking can override the automatic stacking preference when the user deliberately requests it.

### Context actions and direct manipulation

- [x] Mouse context-menu plumbing for inventory rows.
- [x] Container-specific context actions.
- [x] Stack-specific context actions.
- [x] Mouse-open behavior for containers.
- [x] Direct manipulation uses normal item/activity mechanics rather than inventing a UI-only item movement system.

### Persistent inventory and activity handoff

- [x] Inventory can remain visually persistent while an inventory-triggered activity executes.
- [x] Re-entry/handoff state is cleared when the persistent workspace actually resumes.
- [x] Ordinary progress activities are allowed to leave/re-enter the persistent inventory path correctly.
- [x] Inventory frame is kept stable across activity handoff.
- [x] Temporary world/UI flashes during AIM/persistent-inventory handoff were specifically reduced/blocked.
- [x] Workspace status rendering has been decoupled from unnecessary full inventory redraws.

### Integration and regression work already done

- [x] Item-location mutability/lifetime fixes needed by nested and stack operations.
- [x] Item/pocket traversal hooks needed by inline containers.
- [x] Reload/item-location integration touched so the new inventory representation does not bypass normal reload semantics.
- [x] SDL/input routing extended for desktop mouse behavior.
- [x] Advanced-inventory regression tests were added/updated during the overhaul.
- [x] Reload tests were touched where inventory/item-location behavior crossed reload logic.
- [x] Numerous crash, stale-cache, selection, redraw, and modal-lifecycle fixes applied after manual testing.

## Remaining / partially complete work

The remaining ~10% should be treated primarily as **completion and hardening**, not as another architecture replacement.

### High-priority completion work

- [ ] Continue manual edge-case testing of drag/drop across player inventory, map/ground inventory, vehicle storage, nested containers, and unusual pocket arrangements.
- [ ] Finish any remaining flicker/redraw edge cases around modal dialogs and activities instead of adding more one-off screen rebuilds.
- [ ] Audit all quantity/split paths for stable selection, scroll position, expanded-container state, and status feedback after mutation.
- [ ] Audit multi-selection + nested-container combinations, especially when selected rows disappear, merge, split, move, or become invalid during an operation.
- [ ] Audit stacking behavior for all game-supported stack-compatibility edge cases and keep UI grouping separate from actual item merging.
- [ ] Remove or simplify compatibility/workaround code that is no longer required after the persistent-workspace lifecycle has stabilized.

### Regression coverage still worth adding

- [ ] More explicit tests for same-pane container transfers.
- [ ] More explicit tests for hierarchical/nested drag targets.
- [ ] Multi-select move regression coverage.
- [ ] Split -> recombine -> move regression coverage.
- [ ] Auto-stack versus explicit-stack policy tests.
- [ ] Activity handoff/re-entry state tests where practical.

### Follow-on reuse, not required for the core 100% mark

These belong to the wider UI modernization roadmap and should reuse the inventory work rather than expanding the inventory overhaul indefinitely:

- [ ] Trade UI migration onto the shared inventory/list-detail interaction model.
- [ ] Pickup / Drop / Consume / Read / Unload selectors migrated onto shared item-selection components where practical.
- [ ] Reload/ammo selection modernization using the same item browser and compatibility information.
- [ ] Repair/disassembly selectors using shared list/detail components.

## Primary edited code surface

The overhaul is concentrated in advanced inventory but is intentionally cross-cutting. The files below are the **relevant edited implementation surface observed in the audited commits**, not merely files whose APIs happen to be called.

### Core inventory implementation

| File | Role in the overhaul |
| --- | --- |
| `src/advanced_inv.cpp` | Main unified workspace, mouse interaction, selection, drag/drop, hierarchy, quantity/split, stack behavior, context actions, persistent UI lifecycle. |
| `src/advanced_inv.h` | Persistent workspace state and additional inventory interaction declarations/state. |
| `src/advanced_inv_area.cpp` | Area/source behavior required by the expanded inventory workspace. |
| `src/advanced_inv_pane.cpp` | Pane row/navigation/state behavior used by the mouse-capable workspace. |

### Input and rendering integration

| File | Role in the overhaul |
| --- | --- |
| `src/input.cpp` / `src/input.h` | Mouse action/input-context support used by the new workspace. |
| `src/sdltiles.cpp` / `src/sdltiles.h` | Desktop SDL mouse event routing and presentation behavior required by the new interactions. |
| `src/output.h` | Shared UI/output support used by the modernized interaction paths. |
| `src/game.cpp` / `src/game.h` | Persistent UI/world handoff and game-level integration. |
| `src/handle_action.cpp` | Action routing around persistent inventory and game input. |

### Item, container, and reload integration

| File | Role in the overhaul |
| --- | --- |
| `src/item.cpp` / `src/item.h` | Item-side support touched by inventory operations. |
| `src/item_contents.cpp` | Nested contents traversal/handling used by inline container behavior. |
| `src/item_pocket.cpp` | Pocket/container behavior required by nested movement. |
| `src/item_location.cpp` / `src/item_location.h` | Stable/mutable item locations for direct manipulation, stack operations, and nested moves. |
| `src/item_reload.cpp` / `src/item_reload.h` | Reload-side integration with item locations and inventory presentation. |
| `src/reload.cpp` | Reload workflow integration. |
| `src/character_inventory.cpp` | Character inventory-side support for the new movement/query paths. |
| `src/character.cpp` / `src/character.h` | Character inventory/activity hooks touched by the overhaul. |
| `src/game_inventory.cpp` / `src/game_inventory.h` | Existing game-inventory selector integration points affected by the new behavior. |

### Activity / persistent-workspace integration

| File | Role in the overhaul |
| --- | --- |
| `src/activity_item_handling.cpp` / `src/activity_item_handling.h` | Normal item-moving activity path used instead of bypassing gameplay mechanics. |
| `src/activity_handlers.cpp` | Activity completion/handoff integration. |
| `src/activity_type.cpp` | Activity metadata/behavior touched by persistent inventory handling. |
| `src/character_activity.cpp` | Character-side activity lifecycle integration. |
| `src/player_activity.cpp` / `src/player_activity.h` | Persistent activity state and inventory re-entry/handoff behavior. |
| `src/avatar_action.cpp` / `src/avatar_action.h` | Avatar action paths reached by inventory direct actions. |
| `src/avatar_funcs.cpp` | Supporting avatar/inventory behavior touched by the integration. |

### Tests

| File | Role in the overhaul |
| --- | --- |
| `tests/advanced_inv_test.cpp` | Advanced inventory and nested-item regression coverage. |
| `tests/item_reload_test.cpp` | Reload/item-location coverage affected by the inventory changes. |

Not every supporting file above is inventory-only. They contain hooks needed so the new UI continues to use normal CDDA item locations, pockets, activities, reload rules, and game input rather than maintaining parallel UI-only mechanics.

## Representative implementation timeline

This list is intentionally selective. Small compile fixes and repeated flicker/presentation iterations are not all listed individually.

| Commit | What it established |
| --- | --- |
| [`7b285fdf`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/7b285fdf15fa1d32c663cf3ca76b3b4966123116) | Initial desktop mouse inventory controls. |
| [`4ee8bd6a`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/4ee8bd6a325c6762bc8fcf7dcff6aaa3cda4598a) | Unified mouse inventory workspace; major architectural step. |
| [`faa134a4`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/faa134a409d85029b0cdac5dd512c0190ba30901) | Refined mouse interactions. |
| [`4edb5b3d`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/4edb5b3df544b3259ebf2631a76fa9e9f2bf629c) | Container, context-menu, and stack mouse controls. |
| [`3642ea37`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/3642ea37471ea8c6a43822a31d1bd17d07b86c3b) | Mutable nested-item traversal. |
| [`8c4fe886`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/8c4fe88605fc433cd785cb20e6155657b887cd0d) | Same-pane container drag transfers. |
| [`b04ae2bc`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/b04ae2bc3130f12f2e5c446dff6c5a34b4d0834e) | Hardened nested extraction/unload paths. |
| [`d9c3fd47`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/d9c3fd478df91f4c35b663bd27206e625ad5e6ef) | Clickable sorting and persistent container trees. |
| [`ce6cff2a`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/ce6cff2a5797a4086ddf82c359bd6e9f31647b6b) | Expanded unified mouse inventory controls. |
| [`76c0cc90`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/76c0cc90d73bc76ed31afa2c8c4c0aeb1fdc0c1c) | Ctrl multi-select and drop-path crash fix. |
| [`94d6b909`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/94d6b90982a7ca32f08cf01aaee9eadb48a65e39) | Hierarchical inventory dragging refinement. |
| [`37b214f2`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/37b214f2c3589d1b9a85c518f65c65874cd278ac) | Coherent mouse-wheel/selection navigation. |
| [`1950703d`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/1950703ddb7af81eca7ad49d8751faee62166996) | Correct persistent-inventory handoff cleanup after reopening. |
| [`86e71e54`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/86e71e54d6dc37f49775a7480b6027d291efc3cf) | Double-click container opening. |
| [`c4d6c440`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/c4d6c4400f2495b82dec4b4dc9a41a9effe2fc5e) | Drag-state cleanup and stack recombination. |
| [`46a88c5c`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/46a88c5c6eea15121be21b3f2220a4db10b70b70) | Split-stack flicker reduction and stacked-selection preservation. |
| [`004b1b34`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/004b1b34e28584100803b37eb92e7809ba325cda) | Stable inventory frame across activity handoff. |
| [`44b28ecb`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/44b28ecb278f9005c60adb6c9d1aa8b42bdd1cbc) | Auto-stack transfer toggle. |
| [`b86618be`](https://github.com/Alexm-wq/Cataclysm-DDA/commit/b86618be15cea070531415028ac9c36c570b4d1b) | Explicit stacking overrides auto-stack preference. |

## Evidence note

The initial desktop mouse inventory series begins at `7b285fdf`. A comparison through the persistent-inventory handoff milestone at `1950703d` already spans **39 files with roughly 3,900 additions**, before later stack-policy and further lifecycle cleanup commits. This is why the overhaul should be treated as an integrated UI/item/activity change rather than a small patch to `advanced_inv.cpp`.

The latest audited commit specifically touching `src/advanced_inv.cpp` is `b86618be` (`Let explicit stacking override auto-stack mode`). The branch continued after that with vehicle-editor work and shared UI/input changes.

## Completion gate

Treat the inventory overhaul as 100% for its own scope when all of the following are true:

1. no known common drag/drop, nested-container, split/merge, or multi-select workflow is broken;
2. modal/activity transitions do not produce visible inventory teardown/reopen flashes in normal use;
3. persistent selection, scroll, and expanded-container state survive all ordinary inventory mutations;
4. stack recombination/auto-stack behavior consistently follows game stack rules;
5. mouse and keyboard navigation never produce competing visible selections;
6. the remaining high-risk interaction paths have regression coverage or deliberate documented manual coverage;
7. temporary lifecycle/workaround code has either been removed or documented as intentionally permanent.

The migration of Trade and other selectors onto reusable inventory components is **follow-on modernization**, not a blocker for calling the inventory overhaul itself complete.

## How to update this document

When inventory work lands:

1. change `Last audited branch head` to the new reviewed commit;
2. move completed items from **Remaining** to the appropriate **Implemented** section;
3. add a milestone commit only when it changes architecture, user-visible capability, or an important lifecycle invariant;
4. update the edited-file tables only when the architectural surface actually expands;
5. adjust the completion estimate based on remaining user-visible work, not commit volume;
6. keep speculative/future features in the main UI modernization roadmap rather than silently expanding this scope.