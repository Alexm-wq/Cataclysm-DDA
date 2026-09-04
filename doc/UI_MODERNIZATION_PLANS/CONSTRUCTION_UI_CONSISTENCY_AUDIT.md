# Construction UI Consistency Audit — Applied

This document records the interaction-consistency pass applied after the initial Construction Workspace implementation.

## Canonical interaction contract

- Hover is preview state. Active Build, Place, Remove, and Marker previews follow the hovered map tile independently from a pinned target.
- LMB with an active tool is the primary action. Adjacent work starts normally; distant work routes to a valid working position and starts automatically.
- If a primary LMB action cannot start, the clicked tile remains pinned so the inspector keeps the exact failure reason visible.
- Neutral Build mode uses LMB for inspection only when no build result is selected.
- RMB is reserved for inspection, contextual/alternate work, plan-local actions, centering, and clearing the pinned target. It does not duplicate the active tool's primary command.
- Inspector primary actions remain available for deliberately pinned/inspected targets; they are not a required second confirmation.
- Esc backs out hierarchically: popup/context menu, pinned target, selected tool/catalog entry, then workspace. Hover alone never consumes an Esc press.
- Running construction exposes an explicit Pause action instead of treating arbitrary mouse or keyboard input as cancellation. Compact layouts also expose Pause in the header.

## Consistency changes

- Failed target clicks remain selected for diagnosis.
- Hover ghost ownership is separated from pinned/unfinished-target ownership.
- Running-task pseudo-buttons were replaced with status plus Pause.
- `Plan` / `Plans` were renamed to `Add plans` / `Manage plans`.
- Empty map clicks in Manage plans no longer leave an invisible selected target.
- Build/Add-plans mode switches preserve catalog choice but clear the world target.
- RMB `Clear selection` became target-only `Clear target`.
- Global `Build all plans` was removed from per-tile context menus.
- Marker and compatible contextual construction actions use the same distant route-to-site handoff model.
- Marker placement receives a cursor-following ghost marker when there is no terrain/furniture result sprite.
- Place/Marker inspector naming no longer exposes the generic `Special construction operation` fallback when a player-facing action/group name exists.
- Tool-specific footer instructions remain stable after a target is pinned.
- Diagnostic/status text survives harmless scrolling and focus changes.
- The Place/Marker-only eight-neighbor validity halo was removed in favor of the common hover-target feedback model.
- Compact mouse selection and keyboard selection now use the same selection-vs-activation focus transition.
- The unreachable Remove palette rendering branch was removed; Remove remains a map-first tool with no catalog pane.

## Validation targets

The interaction pass should be smoke-tested across Build, Place, Remove, Markers, Add plans, and Manage plans, including adjacent and distant execution, failed targets, interruption/continue behavior, compact layout Pause, RMB contextual work, keyboard focus traversal, map zoom/pan, and plan selection/removal/execution.
