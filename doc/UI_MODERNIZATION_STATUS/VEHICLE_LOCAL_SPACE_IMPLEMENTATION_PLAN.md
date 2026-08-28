# Rigid vehicle local-space implementation plan

Branch: `mouse-inventory-0-i-test`

Status: design/implementation plan. No gameplay changes are implemented by this document.

## 1. Goal

Replace the current vehicle representation in which rotated vehicle mounts are snapped individually back onto the world tile grid with a rigid local-space vehicle model.

The intended result is:

- a vehicle keeps its exact local shape and part spacing at every allowed heading;
- turning never stretches, compresses, shears, or staircase-distorts a long vehicle;
- the world remains a discrete Cataclysm tile grid;
- vehicle position and orientation remain discrete enough to preserve Cataclysm's turn-based movement model;
- any world tile touched by the rigid vehicle knows that vehicle geometry overlaps it;
- exact collision uses only the portion of the vehicle that really overlaps that tile, rather than treating every touched tile as completely solid;
- characters and other occupants can move on a vehicle-local grid while the vehicle is turned;
- entering and leaving a vehicle performs an explicit local-space/world-grid transition;
- existing tilesets continue to work without authored rotated vehicle sprites.

The central rule is:

> Vehicle-local geometry is authoritative. World-grid occupancy is derived from it.

This is the inverse of the current failure mode, where the rasterized world-grid positions of individual parts effectively become the visible vehicle shape.

## 2. Existing code we should preserve and build on

Cataclysm already contains much of the conceptual local-space model that this project needs:

- `vehicle_part::mount` is the part's mount point in vehicle-local coordinates.
- `vpart_position::mount_pos()` is explicitly documented as a coordinate in the vehicle's own coordinate system, independent of movement and rotation.
- vehicle parts already keep translated/precalculated positions for current facing/turning.
- `vehicles::steer_increment` is currently `15_degrees`.
- the tiles renderer already has vehicle-part-specific rendering and rotation handling.

Therefore this project should not invent a second vehicle coordinate system. It should make the existing local mount system authoritative and introduce a precise transform/geometry layer between local mounts and world tiles.

For the first implementation, preserve the existing 15-degree steering cadence. That gives 24 legal headings and already satisfies the requirement that vehicle orientation remain deliberately quantized to the game world. The project should change how the vehicle is transformed and rasterized, not silently redesign steering behavior at the same time.

## 3. Non-goals for the first implementation

The initial project should **not**:

- convert Cataclysm to continuous real-time movement;
- allow arbitrary unquantized vehicle headings;
- require physics-engine integration;
- require new vehicle sprites;
- make ordinary terrain non-grid-aligned;
- convert every creature and every map interaction to floating-point world coordinates;
- rewrite all legacy `veh_at()` callers in one patch;
- change vehicle acceleration, turn costs, handling, fuel use, or driving balance unless required to fix a geometry bug;
- add smooth movement interpolation as a prerequisite.

Sub-tile visual translation and smooth driving animation can be considered after rigid turning is correct.

## 4. Architecture

The implementation should have three layers.

```text
Reusable 2D spatial helpers
        |
        v
Vehicle rigid-geometry model
        |
        +--> exact collision / hit testing
        +--> touched world-cell rasterization
        +--> local <-> world conversion
        +--> renderer transforms
        +--> occupant attachment
        |
        v
Compatibility adapters for existing map/game systems
```

The reusable helpers must not know about vehicle parts, passengers, terrain, or gameplay rules. Vehicle-specific semantics stay in `vehicle_geometry`/`vehicle`.

## 5. Reusable geometry helpers

Create a small, focused reusable geometry module. Suggested files:

- `src/spatial_geometry.h`
- `src/spatial_geometry.cpp`
- `tests/spatial_geometry_test.cpp`

Do not build a large general-purpose physics framework. Add only primitives required by the vehicle implementation.

### 5.1 `rigid_transform_2d`

Represent a rigid 2D pose:

- world-space origin/pivot;
- quantized rotation angle;
- local-to-world point transform;
- world-to-local inverse transform;
- local-to-world vector/direction transform;
- transform composition if later required.

The transform must use continuous intermediate coordinates. Do not round until an API explicitly requests a world tile.

Conceptually:

```cpp
world = origin + rotate( local - pivot, angle );
local = pivot + rotate( world - origin, -angle );
```

Use double precision for geometry calculations unless profiling demonstrates a reason not to. The world remains integer-grid based; precision here exists to avoid geometry drift and inconsistent rasterization.

### 5.2 Shape primitives

Initially support the minimum set required by vehicle mount cells:

- transformed unit rectangle / oriented rectangle;
- convex polygon representation for clipped/intersection results if necessary;
- axis-aligned bounding box for broadphase tests.

A vehicle mount cell should begin as a unit square in vehicle-local space. Rotating the vehicle rotates that square rigidly with every other mount.

### 5.3 Intersection helpers

Provide reusable operations such as:

```text
contains_point(shape, point)
intersects(shape_a, shape_b)
intersects_tile(shape, tile)
intersection_area(shape, tile)
bounds(shape)
```

The precise API can follow existing Cataclysm geometry conventions, but callers should not implement their own rotation/intersection math.

### 5.4 Grid supercover/rasterization

Provide one canonical helper that answers:

> Which integer world cells are touched by this continuous shape?

Every meaningful overlap counts. Use only a very small geometric epsilon to suppress floating-point edge noise; do **not** require 25%, 50%, or center-point coverage.

This is the compatibility bridge between rigid geometry and Cataclysm's discrete map.

The helper should optionally return overlap information, not only a boolean tile list. For example:

```cpp
struct grid_overlap {
    tripoint_bub_ms tile;
    double coverage;
    // Optional clipped shape or enough information for precise follow-up queries.
};
```

Exact API design should avoid storing expensive clipped polygons when a broadphase tile plus the original rigid shape is sufficient.

## 6. Vehicle geometry layer

Create a vehicle-specific wrapper around the generic geometry module. Suggested files:

- `src/vehicle_geometry.h`
- `src/vehicle_geometry.cpp`
- `tests/vehicle_geometry_test.cpp`

### 6.1 Vehicle pose

The vehicle pose consists of:

- its existing map/world anchor;
- its existing pivot semantics;
- its quantized heading;
- optionally a sub-tile translation field later, but **not required for version 1**.

Do not duplicate `face`, `move`, or steering state unnecessarily. The geometry layer should derive a `rigid_transform_2d` from existing vehicle state.

### 6.2 Mount geometry remains rigid

Each unique local mount has a unit-cell footprint. Multiple vehicle parts installed at the same mount share that spatial footprint but retain their separate gameplay identities.

For every pose:

```text
vehicle-local mount cell
        |
        v
shared rigid transform
        |
        v
continuous world-space mount shape
```

No mount is independently rounded before rendering or collision.

This guarantees that:

- pairwise distances between mounts never change with heading;
- vehicle area does not change with heading;
- straight vehicle edges remain straight;
- long vehicles do not accumulate rounding error.

### 6.3 Preserve part identity

Do not reduce the entire vehicle to one anonymous collision polygon. Cataclysm needs to know what part was hit, boarded, opened, damaged, shot, or interacted with.

The geometry model should therefore retain a mapping similar to:

```text
local mount
 -> transformed unit cell
 -> installed parts at that mount
```

A union/bounding shape may be cached for broadphase work, but precise queries must still resolve to mount/part identity.

### 6.4 Geometry classes by semantics

Do not assume every part at a mount has identical collision semantics. Derive different views from the same transformed mount geometry as needed:

- **presence geometry:** any meaningful vehicle geometry in a world tile;
- **obstacle geometry:** closed/solid vehicle locations that block creature movement, using existing obstacle/movecost semantics;
- **boardable/interior geometry:** local mounts a character can occupy or enter;
- **collision geometry:** mounts/parts participating in vehicle/terrain/vehicle impacts;
- **interaction geometry:** transformed location used by mouse picking and actions.

This keeps existing vehicle-part rules intact while changing the coordinate representation underneath them.

## 7. World-grid occupancy and map queries

The map needs to know all cells touched by a rigid vehicle, even if the overlap is small.

### 7.1 Touched cells are not fully solid cells

Example:

```text
+-------+
|     /#|
|   /###|
| @/####|
+-------+
```

The vehicle overlaps this map cell, so vehicle-presence queries must report it. However, if the character footprint at `@` does not intersect the vehicle, the character may still be able to stand there.

Therefore:

```text
"vehicle overlaps tile" != "entire tile is blocked"
```

### 7.2 New precise map query

Add a query capable of returning all vehicle/mount overlaps at a world cell. Exact naming can follow existing map conventions, for example:

```cpp
std::vector<vehicle_overlap_ref> map::vehicle_overlaps_at( tripoint_bub_ms p );
```

A tile may contain:

- more than one transformed mount from the same vehicle;
- parts of two different vehicles;
- vehicle geometry and an otherwise usable portion of ground.

The new query must represent this instead of assuming one cell maps to exactly one vehicle part.

### 7.3 Keep `veh_at()` as a compatibility adapter

Do not break hundreds of callers immediately.

Existing `veh_at()` should remain available during migration and return a deterministic primary vehicle/part from the overlap set. Selection should be documented and stable; likely criteria are:

1. geometry containing the tile center;
2. otherwise greatest overlap area;
3. deterministic vehicle/mount tie-break.

Systems where exactness matters must migrate to the precise overlap query rather than depending on this adapter.

### 7.4 Cache design

The map vehicle cache should become a broadphase index from world cell to a small overlap list rather than a single snapped vpart assumption.

Do not serialize this cache. Rebuild it from vehicle pose/local mounts after load, vehicle movement, rotation, part installation/removal, folding/unfolding, racking, or any other geometry-changing event.

Cache invalidation should be centralized in vehicle/map helpers rather than duplicated across call sites.

## 8. Exact hitboxes and collision

### 8.1 Vehicle hitbox

The authoritative vehicle hitbox is the transformed local geometry, not the set of touched cells.

A vehicle that is 2 x 6 mount cells remains approximately 12 square-tile units of geometry at every heading even if a 15-degree orientation touches substantially more than 12 integer world cells.

### 8.2 Character collision outside vehicles

Ordinary world movement can remain tile-to-tile.

For a candidate destination:

1. obtain a small character collision footprint centered on the destination tile;
2. query nearby vehicle overlap candidates;
3. perform precise shape intersection;
4. allow the move if the character footprint does not intersect blocking vehicle geometry.

Do not use an overlap percentage threshold such as "vehicle covers >50% of tile".

### 8.3 Swept character movement

Checking only destination occupancy could allow a one-tile move to cross a thin diagonal vehicle body even when both tile centers are clear.

For movement near rigid vehicle geometry, perform a swept test between source and destination footprints. Keep this narrowphase local to nearby vehicle candidates so normal walking remains inexpensive.

### 8.4 Vehicle movement and turning

For a candidate vehicle pose:

1. compute broadphase touched cells/AABB;
2. gather potentially colliding terrain, creatures, and vehicles;
3. perform exact geometry tests where required;
4. resolve contact back to the relevant vehicle mount/part so existing damage rules still have part identity.

Turning must consider the swept body between the old and new 15-degree headings. Initial implementation may deterministically sample intermediate orientations if an exact swept-rotation solution would overcomplicate the first patch. The sampling increment must be small enough to prevent a long corner from tunneling through walls.

### 8.5 Vehicle-to-vehicle collision

Use rigid geometry intersection for the narrowphase. Do not declare the whole world cell collided merely because both vehicles touch the same cell.

The tile overlap index remains useful as a broadphase candidate generator.

## 9. Vehicle-local occupants

A turned vehicle requires an occupant coordinate frame independent of the world grid.

### 9.1 Do not overload `in_vehicle`

`Character::in_vehicle` currently describes seating/boarding semantics. Walking on a vehicle interior is a different concept.

Introduce a local spatial attachment representing something like:

```cpp
struct vehicle_local_position {
    safe vehicle reference/id;
    point_rel_ms mount;
};
```

The exact persistent vehicle identifier must be chosen from existing safe-reference/save mechanisms rather than inventing a raw pointer-based save format.

### 9.2 Compatibility world position

Do **not** require the entire `Creature` coordinate model to become continuous in the first version.

While an actor is vehicle-attached:

- the vehicle-local mount is the authoritative position within the vehicle;
- rendering uses the exact transformed local position;
- vehicle-local walking changes the local mount directly;
- a derived/snapped world tile remains available for legacy map, LOS, effect, and AI code;
- vehicle movement/rotation updates that compatibility world position as necessary.

This contains the invasive coordinate change while allowing systems to migrate gradually.

### 9.3 Scope of attachment

The architecture should ultimately work for any creature that is standing on/in a moving vehicle, not only the avatar. At minimum audit:

- avatar;
- NPCs/passengers;
- boarded characters;
- monsters or animals standing inside/on vehicle geometry.

If converting all creature types at once proves too invasive, implement the attachment API generically but stage adoption. Do not hardwire a player-only coordinate system that must later be replaced.

### 9.4 Vehicle-local movement

Inside/on a vehicle, one movement action still moves one local mount cell.

The local grid does not rotate or deform. The vehicle transform rotates the complete grid into world space.

World-oriented input should be translated to the local neighbor whose transformed direction best matches the requested world/screen direction. Mouse movement can inverse-transform the clicked point and directly identify the intended local mount.

### 9.5 Entry transition

Entering is explicit rather than guessed from rounded coordinates:

```text
world-grid actor
    -> interact/step through a specific transformed boardable/door location
    -> resolve that location's local mount
    -> attach actor to vehicle local frame
```

Existing door/boardable semantics determine whether the transition is legal.

### 9.6 Exit transition

Leaving transforms the local exit/door position and outward normal into world space, then chooses a legal nearby world tile.

Rank candidate tiles by:

1. correct side/outward direction of the exit;
2. no exact intersection with vehicle geometry along the exit path;
3. normal map passability;
4. distance from the transformed exit point;
5. deterministic tie-break.

If no legal world tile exists, exiting fails normally.

The final snap is acceptable because Cataclysm movement is already discrete; no continuous walking animation is required for correctness.

### 9.7 Forced detachment

Use the same local-to-world transition infrastructure for:

- vehicle part beneath occupant destroyed;
- actor thrown from vehicle;
- jumping from moving vehicle;
- folding/removing/destroying vehicle;
- racking/carrier transitions where an attachment becomes invalid.

## 10. Rendering

### 10.1 No new sprites required

The renderer should continue using existing vehicle-part tiles.

For each part/mount:

```text
local mount position
    -> rigid vehicle transform
    -> world position
    -> camera/tile transform
    -> existing part sprite with vehicle orientation
```

The critical rule is that part positions are transformed continuously and only rasterized at screen-render time. They are never positioned from independently snapped world tiles.

### 10.2 Per-part transform first

Start by extending the existing vehicle-part rendering path to use shared rigid placement and angle. This preserves dynamic part overlays and minimizes renderer disruption.

If arbitrary rotated part sprites show visible one-pixel seams, add an optional vehicle-composite render target/cache later. Do not make a whole-vehicle texture cache a prerequisite for proving the geometry.

### 10.3 Rendering cache

Cache transformed/render data by at least:

- vehicle geometry revision;
- vehicle heading;
- tileset/zoom information if necessary.

Invalidate when installed parts, variants, open/closed states that change appearance, or geometry change. Dynamic overlays such as lights/turrets should remain separable where practical.

### 10.4 Mouse hit testing

Use the inverse rigid transform:

```text
screen -> world -> vehicle local -> mount/part
```

This lets mouse interaction select the visibly rendered door/part even when the vehicle is at 15, 30, 45, etc. degrees.

The same reusable inverse-transform helper can later support the vehicle editor preview and other rotated world objects.

## 11. Save/load compatibility

Vehicle geometry itself should be derived from existing vehicle mounts, pivot, position, and facing, so it should not require a new serialized copy of transformed geometry.

Never serialize:

- transformed polygons;
- touched-cell lists;
- broadphase caches;
- render caches.

Serialize new occupant local attachment only if required.

For old saves:

- load the existing world position and `in_vehicle` state;
- if the actor is currently associated with a valid vehicle location, resolve the corresponding local mount and create the new attachment;
- if resolution fails, keep the actor in world space rather than corrupting the save.

Save/load tests must cover rotated vehicles and attached occupants.

## 12. Files expected to change

### Core geometry and vehicle model

- `src/vehicle.h`
- `src/vehicle.cpp`
- `src/vpart_position.h`
- `src/vpart_position.cpp`
- **new** `src/spatial_geometry.h`
- **new** `src/spatial_geometry.cpp`
- **new** `src/vehicle_geometry.h`
- **new** `src/vehicle_geometry.cpp`

### Map occupancy / movement / collision

- `src/map.h`
- `src/map.cpp`
- `src/vehicle_move.cpp`

### Occupants / transitions / persistence

- `src/character.h` and `src/character.cpp`, or the appropriate shared `Creature` layer after audit
- `src/savegame_json.cpp`
- boarding/unboarding call sites in `map.cpp` and related vehicle-use code

### Tiles renderer

- `src/cata_tiles.h`
- `src/cata_tiles.cpp`

A lower-level SDL file should only be modified if the current tile draw API cannot place/rotate a sprite at the required continuous screen position.

### Tests

- existing `tests/vehicle_test.cpp` where appropriate
- **new** `tests/spatial_geometry_test.cpp`
- **new** `tests/vehicle_geometry_test.cpp`
- focused map/character/save tests as required by existing test organization

## 13. Secondary systems to audit

These are not automatically "must edit" files. They are a migration/audit list because they may assume `world tile <-> one vpart` identity:

- projectile and ranged-hit resolution;
- explosions and blast damage to vehicle parts;
- creature/NPC pathfinding around vehicles;
- monster movement on/inside vehicles;
- grabbing/pushing vehicles;
- towing;
- vehicle racks/carried vehicles;
- traps beneath or contacted by vehicles;
- item locations/cargo lookups tied to world vpart position;
- activities that persist a vehicle-part world coordinate;
- remote controls and range checks;
- vehicle editor/world-preview picking;
- map memory and vehicle decoration caches;
- zone interactions attached to vehicle locations;
- part removal/install code that invalidates map caches;
- vehicle destruction/splitting/merging/folding/unfolding.

During implementation, search for callers of at least:

```text
veh_at
bub_part_pos
part_at
parts_at_relative
precalc
mount_pos
board_vehicle
unboard_vehicle
displace_vehicle
in_vehicle
```

Classify every caller as:

- compatible with deterministic `veh_at()` adapter;
- needs all overlaps;
- needs exact geometry;
- needs local mount identity.

Do not mechanically rewrite every caller.

## 14. Implementation phases

### Phase 0 - Baseline and diagnostics

Before behavior changes:

- add/identify a reproducible long-vehicle fixture approximating the RoseRide failure case;
- record its unique local mounts and current bounding dimensions;
- capture old behavior at representative headings;
- add optional debug drawing for local mount centers, transformed cell outlines, touched world cells, and pivot.

This makes geometry errors visible immediately.

### Phase 1 - Reusable spatial helpers only

Implement and test:

- rigid transform/inverse;
- oriented unit rectangles;
- AABB broadphase;
- exact rectangle/tile intersection;
- supercover touched-cell rasterization.

No vehicle behavior changes in this phase.

### Phase 2 - Vehicle rigid-geometry model

Build the vehicle geometry cache from existing mounts and pose.

Expose queries for:

- transformed mount shape;
- all touched world cells;
- local mount under world point;
- exact overlap with a tile/shape;
- geometry bounds;
- local/world conversions.

Keep existing simulation authoritative temporarily and assert/debug-compare old and new results.

### Phase 3 - Map overlap index

Change/supplement the map vehicle cache so touched cells can contain multiple overlap refs.

Add the precise overlap API and keep `veh_at()` as a deterministic compatibility adapter.

Migrate only the minimum callers needed to keep cache updates, part removal, and vehicle lookup correct.

### Phase 4 - Rigid rendering

Switch tile rendering to transformed local mount positions.

Acceptance gate: the long test vehicle must remain visually rigid through every legal 15-degree heading even if gameplay collision is still temporarily old-style.

### Phase 5 - Rigid movement/collision becomes authoritative

Use the new geometry for:

- terrain collision;
- vehicle-to-vehicle broadphase/narrowphase;
- touched-cell registration after movement/turning;
- part-hit resolution;
- creature collision near partial overlaps;
- swept turn checks.

Remove old geometry assumptions only after equivalent tests exist.

### Phase 6 - Vehicle-local occupants

Add local attachment, local-grid movement, entry/exit transitions, compatibility world position, and save migration.

Keep seated/boarded semantics separate from merely being spatially attached to the vehicle frame.

### Phase 7 - Migrate exact consumers and clean up

Audit the secondary systems list. Migrate only callers that genuinely need precision.

When no required system depends on the old snapped-part representation:

- remove obsolete precalculated geometry used only for snapping;
- retain compatibility APIs that remain useful;
- remove temporary debug/experimental toggles;
- document the final spatial contract.

## 15. Tests and invariants

### 15.1 Generic geometry tests

For all legal vehicle headings and representative arbitrary helper angles:

- local -> world -> local round-trip within epsilon;
- transformed unit square retains area;
- inverse direction transform is correct;
- touching a tile corner is included by supercover above epsilon;
- exact edge-only floating-point noise does not create unstable neighboring occupancy;
- results are deterministic across repeated calls.

### 15.2 Rigid vehicle invariants

For a long rectangular vehicle and irregular deathmobile shape:

- unique local mount count does not change with heading;
- pairwise distances between mount centers do not change;
- total rigid footprint area does not change;
- vehicle length/width in local space never change;
- 0 degrees and 90 degrees are exact rotations of the same geometry;
- 15/30/45/60/75-degree poses do not staircase-deform the body;
- touched world-cell count may change with angle, but exact area may not.

### 15.3 Partial-cell collision tests

Cover cases where:

- vehicle touches 1-5% of a tile corner;
- `vehicle_overlaps_at(tile)` reports the vehicle;
- a character footprint in the clear portion can stand there;
- a character footprint intersecting the corner cannot;
- movement between two clear tile centers is blocked if the swept path crosses the vehicle;
- projectiles/other vehicles can hit the overlapped portion.

### 15.4 Map lookup tests

Test:

- multiple mounts from one rotated vehicle touching the same tile;
- two vehicles touching the same tile;
- deterministic compatibility `veh_at()` selection;
- cache invalidation after move, turn, install, remove, split, fold/unfold where applicable.

### 15.5 Occupant tests

Test:

- actor local mount remains unchanged while vehicle rotates;
- rendered/precise world position follows the rigid transform;
- compatibility world tile updates deterministically;
- local movement remains one mount cell at a time;
- actor enters through a specific transformed door/boardable location;
- exit chooses the correct outside tile;
- blocked exit fails;
- destruction/forced detach chooses a valid world position;
- save/load preserves attachment.

### 15.6 Renderer/in-game regression checklist

Use at least:

- very long RoseRide-style vehicle;
- semi truck/trailer;
- small car;
- motorcycle/bicycle;
- asymmetric/irregular deathmobile;
- vehicle beside a wall while turning;
- two vehicles passing/colliding at diagonal headings;
- player walking around the outer corner of a turned vehicle;
- player walking through a large vehicle interior while it is turned;
- opening/closing doors and interacting with parts at diagonal headings.

## 16. Performance strategy

The expensive geometry should be pose/revision cached.

Recompute transformed vehicle geometry only when:

- vehicle anchor/pivot changes;
- heading changes;
- geometry-affecting parts are added/removed;
- vehicle is split/merged/folded/unfolded/racked in a way that changes mounts.

Normal map queries should first use touched-cell/AABB broadphase, then exact intersection only for the small candidate set.

Do not run polygon intersection against every vehicle on every character step.

Profile especially:

- large deathmobiles;
- multiple vehicles in the reality bubble;
- repeated 15-degree turning;
- vehicle-vs-vehicle collision;
- NPC pathfinding near diagonal vehicles;
- tiles rendering at common zoom levels.

## 17. Temporary compatibility/debug option

During development, keep the rigid system behind a temporary experimental/debug toggle if that materially helps A/B testing old versus new behavior.

The final target is **not** to maintain two permanent vehicle simulation modes. Once the new geometry is stable and the old path is no longer needed for comparison, remove the toggle and obsolete snapping path.

## 18. Helper reuse beyond this project

The generic helper layer should be reusable for:

- vehicle editor previews and hit testing;
- mouse selection of rotated vehicle parts;
- towing/carried-vehicle transforms;
- accurate projectile intersections with rotated multi-tile objects;
- future rigid non-grid-aligned world objects;
- renderer object transforms that later coexist with projected z-level rendering.

The vehicle-specific layer should remain vehicle-specific. Do not push passenger rules, vpart flags, vehicle damage, or map semantics into `spatial_geometry` merely to make it look generic.

## 19. Acceptance criteria for the first complete version

The project is complete enough for normal testing when all of the following are true:

1. The same vehicle shape is rendered rigidly at every legal heading.
2. Existing 15-degree steering increments remain intact unless intentionally changed in a separate balance/design decision.
3. Any meaningful geometric overlap marks the corresponding world tile as containing vehicle geometry.
4. A partially touched tile is not automatically treated as fully solid; exact collision follows the visible rigid body.
5. Vehicle-to-terrain and vehicle-to-vehicle collision use rigid geometry for the narrowphase.
6. A character can move on a turned vehicle using stable vehicle-local cells.
7. Entering/exiting performs deterministic local/world conversion and cannot place the actor through the vehicle or a wall.
8. Existing vehicle tilesets render without requiring new directional sprites.
9. Old saves load without losing vehicles or occupants.
10. Vehicle part identity is preserved for damage, interaction, cargo, controls, doors, seats, and other gameplay systems.
11. Large vehicles no longer distort when turning.
12. Geometry/map caches remain performant in normal reality-bubble vehicle counts.

## 20. Recommended first implementation slice

The safest first coding slice is deliberately small:

1. add `spatial_geometry` helpers and tests;
2. add `vehicle_geometry` that transforms existing local mounts rigidly;
3. add debug visualization for transformed outlines/touched cells;
4. add the long-vehicle rigidity regression tests;
5. do **not** change movement, collision, occupants, or rendering yet.

Once that foundation proves that the exact same local vehicle can be transformed through all 24 current headings without changing shape, the remaining phases become migrations onto one tested geometry source rather than a collection of independent vehicle hacks.
