# Construction UI modernization status

**Branch:** `mouse-inventory-0-i-test`
**Implementation base:** `0109a82`
**Status:** Build/Remove workspace implemented; in-game acceptance pending
**Plan:** [Construction implementation plan](../UI_MODERNIZATION_PLANS/CONSTRUCTION_UI_IMPLEMENTATION_PLAN.md)

## Implemented

- Full-screen, map-centric Construction Workspace with the real world renderer between a construction palette and contextual inspector.
- Shared Build/Remove/Plan/Plans toolbar and right-aligned Back control. Build and Remove are active; Plan and Plans are shown with explicit disabled reasons until their persistent blueprint and execution work is implemented.
- Build is a searchable, categorized catalog with two-line rows, useful time/skill summaries, and tileset-backed terrain/furniture result thumbnails, following the vehicle Reshape catalog presentation.
- Remove is a map-driven tool, not a second catalog. Its empty desktop palette collapses so the map gains the width; selecting a world tile resolves the most specific applicable removal or deconstruction action and names that destructive action directly.
- Shared search field and modal editor, category dropdown, unavailable-construction toggle, scrollable selection list, scrollable inspector, primary action button, and map context dropdown.
- Filter-safe construction-group selection. Filtering out the active group clears it without overwriting the remembered group, allowing restoration only when it is visible again.
- Internal variants are resolved deterministically by readiness, darkness, missing requirement dimensions, skill deficit, time, and stable ID rather than data order; alternative requirement paths are counted in the inspector.
- Reusable world-viewport controller for clipped pointer routing, main-map coordinate projection, hover, selection, context actions, camera centering/movement, middle-button pan capture, capped cursor-anchored wheel zoom, and world-anchored colored status markers. Construction owns only screen placement and construction semantics; Zones can reuse the same map adapter.
- Hover previews only before selection. Once selected, the inspector/action stays committed to that tile; later hover is a lightweight map marker until another click changes the target.
- All eight adjacent Build candidates display ready `✓`, missing-requirement `!`, invalid `×`, or unfinished `▣` state directly on the map, with color as a secondary cue.
- Inspector details for current terrain/furniture, result and description, time, skills, real tool/component requirements, precise target state, and disabled-action reasons.
- Map clicks only select or inspect. Construction starts only from `Build here`, the context action, or its keyboard binding.
- Adjacent Build revalidates the selected construction and enters the existing component consumption, `partial_con`, and `ACT_BUILD` flow. Continue resumes an adjacent existing `partial_con` directly without consuming its components again. The UI never mutates terrain or furniture directly.
- Removal semantics are explicit construction data (`build`, `remove`, or last-resort `remove_generic`), with generic deconstruction ranked after specific removal instead of depending on group-name prefixes or category iteration order.
- Center view preserves the committed target. Normal UI text uses player-relative target descriptions; raw coordinates appear only in debug mode, and the footer remains dedicated to controls/status.
- Compact terminals switch Palette/Map/Inspector panes through the same action-strip controls while preserving the world viewport. Very small terminals retain the legacy picker as a compatibility fallback.
- Blueprint selection used by Zone Manager remains on the existing legacy path. Existing construction JSON, IDs, `partial_con`, completion, NPC, and blueprint behavior are unchanged.

## Shared-helper boundary

`ui_world_viewport` owns screen-space viewport clipping, main-map screen-to-world conversion, hover, selection/context routing, camera movement, pan capture, release consumption, non-wrapping cursor-anchored zoom, and renderer-independent world marker dispatch. The Construction screen supplies target resolution, marker meaning, and construction-specific actions.

Existing `ui_action_strip`, `ui_text_field`, `ui_selection_list`, `ui_scroll_view`, and `ui_dropdown` controls own all button, search, list, multi-line row, scrollbar, dropdown, hover, disabled, click, pass-through, and capture behavior. The generic tileset thumbnail bridge is shared with vehicle Reshape. Shared clipped-text expansion remains automatic through the normal trimmed-text rendering path.

## Validation

- Passed: 26 shared-helper cases with 1,266 assertions, including viewport clipping, context routing, zoom routing, off-viewport rejection, pan capture, and release over another surface.
- Passed: TILES and non-TILES C++17 syntax checks for the Construction workspace, Build/Remove target resolver, viewport implementation, thumbnail integration, vehicle-editor compatibility, construction integration, and shared-helper tests.
- Passed: the project's strict warning set for the changed workspace, resolver, viewport, thumbnail, vehicle-editor, and helper sources in both TILES and non-TILES configurations, compiled directly without the precompiled header.
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
- [ ] Build result thumbnails, two-line row hitboxes, list wheel scrolling, and tileset fallback symbols.
- [ ] Remove has no recipe list; selecting terrain/furniture resolves the correct specific action and requirements without falling back to a cheaper generic deconstruction.
- [ ] Map hover and click select without movement, component consumption, or activity changes.
- [ ] Ready, missing-requirements, invalid-location, obscured, occupied, and unfinished-construction targets.
- [ ] Terrain and furniture ghost results in both TILES and curses; selected marker remains distinct from hover.
- [ ] Primary and right-click Build actions start the same adjacent construction, create `partial_con`, consume normal requirements once, and assign `ACT_BUILD`.
- [ ] Faction warning acceptance/cancellation, darkness restrictions, target changes between preview and confirmation, and canceled/failed builds.
- [ ] Palette, inspector, and dropdown scrollbar capture when released over map/buttons; outside-click dropdown pass-through.
- [ ] Middle-button camera capture and release, cursor leaving the viewport, vehicle-style pane/map wheel routing, wheel zoom limits and cursor anchoring, keyboard camera movement, and view/zoom restoration on exit.
- [ ] Wide desktop, compact pane switching, minimum supported terminal, runtime resize, ultrawide, and both panel configurations.
- [ ] Zone Manager blueprint selection still uses the legacy construction selector and existing blueprint storage.
