# Construction UI modernization status

**Branch:** `mouse-inventory-0-i-test`
**Implementation base:** `e94b0c4`
**Status:** immediate-construction workspace implemented; in-game acceptance pending
**Plan:** [Construction implementation plan](../UI_MODERNIZATION_PLANS/CONSTRUCTION_UI_IMPLEMENTATION_PLAN.md)

## Implemented

- Full-screen, map-centric Construction Workspace with the real world renderer between a construction palette and contextual inspector.
- Shared Build/Plan/Plans toolbar and right-aligned Back control. Build is active; Plan and Plans are shown with explicit disabled reasons until their persistent blueprint and execution work is implemented.
- Shared search field and modal editor, category dropdown, unavailable-construction toggle, scrollable selection list, scrollable inspector, primary action button, and map context dropdown.
- Stable construction-group selection. Internal variants are resolved against the hovered or selected world tile rather than exposed as palette rows.
- Reusable world-viewport controller for clipped pointer routing, hover, selection, context actions, middle-button pan capture, and non-wrapping wheel zoom. Construction owns only screen placement and world-coordinate semantics.
- Hover ghost of the resulting terrain/furniture, explicit selected-tile marker, and ready/unavailable/invalid/in-progress classification in the inspector.
- Inspector details for current terrain/furniture, result and description, time, skills, real tool/component requirements, precise target state, and disabled-action reasons.
- Map clicks only select or inspect. Construction starts only from `Build here`, the context action, or its keyboard binding.
- Adjacent Build revalidates the selected construction and enters the existing component consumption, `partial_con`, and `ACT_BUILD` flow. The UI never mutates terrain or furniture directly.
- Compact terminals switch Palette/Map/Inspector panes through the same action-strip controls while preserving the world viewport. Very small terminals retain the legacy picker as a compatibility fallback.
- Blueprint selection used by Zone Manager remains on the existing legacy path. Existing construction JSON, IDs, `partial_con`, completion, NPC, and blueprint behavior are unchanged.

## Shared-helper boundary

`ui_world_viewport` owns screen-space viewport clipping, hover, selection/context routing, pan capture, release consumption, and wheel intent. The Construction screen supplies screen-to-world conversion, camera changes, target resolution, and build semantics.

Existing `ui_action_strip`, `ui_text_field`, `ui_selection_list`, `ui_scroll_view`, and `ui_dropdown` controls own all button, search, list, scrollbar, dropdown, hover, disabled, click, pass-through, and capture behavior. Shared clipped-text expansion remains automatic through the normal trimmed-text rendering path.

## Validation

- Passed: 26 shared-helper cases with 1,266 assertions, including viewport clipping, context routing, zoom routing, off-viewport rejection, pan capture, and release over another surface.
- Passed: TILES and non-TILES C++17 syntax checks for the new Construction workspace, target resolver, construction integration, and shared-helper tests.
- Passed: the project's strict warning set for the new workspace and resolver in both TILES and non-TILES configurations, compiled directly without the precompiled header.
- Passed: keybinding JSON parsing and `git diff --check`.
- Blocked outside the implementation: the exact Make object target stops in the existing precompiled header because its `starts_with` macro triggers `-Werror=unused-macros` in this environment.
- Not run: full game link, complete game tests, Windows/MSVC build, or interactive TILES/curses acceptance.

## Deferred by the plan

- Distant `Go there and build` travel/activity orchestration.
- Persistent single-tile plans and the blueprint-zone adapter.
- Plans summary and `Execute plans` integration.
- Paint, line, rectangle, bulk preview, and aggregate estimates.

The corresponding controls are not presented as functioning gameplay. Where visible for workspace continuity, they are disabled with an explanation.

## In-game acceptance checklist

- [ ] Palette search, clear, category dropdown, show-unavailable toggle, long translated names, and clipped-name hover expansion.
- [ ] Map hover and click select without movement, component consumption, or activity changes.
- [ ] Ready, missing-requirements, invalid-location, obscured, occupied, and unfinished-construction targets.
- [ ] Terrain and furniture ghost results in both TILES and curses; selected marker remains distinct from hover.
- [ ] Primary and right-click Build actions start the same adjacent construction, create `partial_con`, consume normal requirements once, and assign `ACT_BUILD`.
- [ ] Faction warning acceptance/cancellation, darkness restrictions, target changes between preview and confirmation, and canceled/failed builds.
- [ ] Palette, inspector, and dropdown scrollbar capture when released over map/buttons; outside-click dropdown pass-through.
- [ ] Middle-button camera capture and release, cursor leaving the viewport, wheel zoom limits, keyboard camera movement, and view/zoom restoration on exit.
- [ ] Wide desktop, compact pane switching, minimum supported terminal, runtime resize, ultrawide, and both panel configurations.
- [ ] Zone Manager blueprint selection still uses the legacy construction selector and existing blueprint storage.
