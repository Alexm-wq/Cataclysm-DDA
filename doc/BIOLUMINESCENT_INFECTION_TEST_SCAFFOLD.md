# Bioluminescent Infection — Test Scaffold

> **STATUS: TEST / PROTOTYPE ONLY**
>
> The monsters and data in this scaffold are **not the final bioluminescent infection implementation**.
> They exist only to test sprite integration, hostile monster spawning, basic movement/pathing, and the
> quick-access test spawner. Future implementation work must revisit and replace the placeholder enemy
> definitions with properly designed enemies.

## Purpose

This is the first integration scaffold for the bioluminescent infection concept. It deliberately avoids
committing to final gameplay design. The current actors let us verify that the visual language works in
UltiCa and that custom infection monsters can be spawned and observed in normal map play.

## Current test actors

- `mon_ocular_parasite_human` — ocular parasite host.
- `mon_bioluminescent_overgrowth_brute_test` — bulky overgrowth/brute visual prototype.
- `mon_bioluminescent_elongated_host_test` — elongated human-host visual prototype.

The two new IDs explicitly contain `_test` so they cannot be mistaken for final monster definitions.

## Test behavior

- These monsters are hostile test enemies and use the zombie faction only as a temporary placeholder.
- They are **not added to natural monster spawn groups**.
- They can be created from the quick-access **Test monster spawner**.
- The spawner places them exactly three tiles away when a valid tile on that radius is available.
- Their current combat setup is intentionally harmless: no melee dice or special attacks are defined, so
  normal melee damage remains zero.
- HP, speed, dodge, vision, faction, species, harvest data, pathing, names, and descriptions are provisional.

## What the future implementation must redo

The final bioluminescent infection work should treat these definitions as disposable scaffolding rather than
balance targets. It should explicitly redesign, as appropriate:

- final monster names, IDs, descriptions, categories, faction/species relationships, and lore;
- attacks, damage types, attack costs, special attacks, status effects, grabs, projectiles, and defenses;
- HP, speed, dodge, armor, senses, morale/aggression, pathing, and AI behavior;
- biological roles for the glowing organs instead of using bioluminescence as decoration only;
- infection ecology, progression/evolution, transformation rules, group composition, and encounter roles;
- natural spawn groups, map/region placement, density, difficulty progression, and rarity;
- death behavior, corpses, harvesting, drops, weakpoints, dissection results, and other interaction data;
- sound, light emission, stealth/visibility interactions, and any infection-specific environmental effects;
- final sprite naming/organization and any animation or alternate-state assets needed by the finished enemies.

The current sprites may be retained, revised, or replaced independently, but their presence here does not make
the current monster mechanics canonical.

## Implementation rule

When the real bioluminescent infection feature is implemented, do **not** simply promote these test monsters
into normal spawn tables. Replace or comprehensively rework the prototype definitions first, then add the
finished enemies to normal world generation only after their intended behavior and balance are defined.
