# Crafting groups

These files define the section-title taxonomy for the modern crafting browser.

Each non-abstract, non-obsolete base-game `recipe` belongs to exactly one
`crafting_group`. Practice recipes, uncraft recipes and the nested headings
themselves are excluded. Recipe IDs include variants and `id_suffix` exactly as
the game loads them; alternate recipes must not be dropped during regrouping.

## Classification rules

- Classify by the result's primary purpose, using item descriptions, usable
  qualities, deployment behavior and recipe contents. Do not classify by source
  filename, crafting skill, material, a substring of the ID or a secondary use
  as an improvised weapon.
- Keep alternate methods, sizes and materials together when they serve the same
  purpose. Canned juice is still a drink; making planks by hand or with power
  tools belongs under lumber. Preserve useful existing equipment families.
- Distinguish raw materials, intermediate parts and finished equipment. A steel
  ballistic insert is armor; a vehicle armor kit is a vehicle part. Brigandine
  shoulder attachments and exoskeleton modules are armor components, not suits.
- Group tools by their job, including manual and powered versions. Separate
  portable kitchen equipment, installed workshop stations and vehicle-mounted
  rigs. Electric generation is not the same as a grain mill driven by wind or
  water. A ketene lamp is laboratory equipment, not lighting.
- Prefer useful families over one group per item, material, caliber or room.
  Generic "Other" headings are not a substitute for inspecting the recipe.
- `source_nested_category`, when present, records the group's historical origin;
  it does not require copying mistakes or preserving identical membership.
  `fallback: true` is reserved for an explicitly unreviewed group. The reviewed
  base-game taxonomy does not currently need fallback groups.

## Construction and camp projects

`construction.json` uses the visible **CC_CONSTRUCTION** category:

| Subcategory | Includes |
| --- | --- |
| Materials | Lumber, masonry, glazing, fasteners, structural metal and fencing |
| Tools | Woodworking, building, demolition, lifting and access equipment |
| Furniture | Furniture, bedding, decorations, planters and training installations |
| Shelters | Tents, shelter kits and sleeping bags |
| Workshops | Workshop and food-processing stations |
| Utilities | Heating equipment and plumbing components |

**CC_BUILDING is different:** it is the hidden camp-blueprint category, and its
`is_building` flag changes recipe behavior. Do not move normal craftable items
into it, unhide it or remove that flag. `building.json` keeps camp surveys,
structures, furnishings, farms, kitchens, workshops, defenses and utilities in
separate groups without changing the underlying camp recipes. Root cellars and
storage rooms are structures; furnishing those rooms is a separate task.

Companion-only production/data-recovery jobs remain in CC_CAMP. Likewise, seed
designation and dedicated lamellar-armor repair groups remain distinct from
ordinary manufacture even when they produce an otherwise identical item.

## Compatibility and validation

The modern browser uses group category/subcategory metadata for filtering and
headings. Legacy nested-category and recipe definitions remain unchanged, as do
requirements, outputs, skills, learning, times and camp progression. Register
new subcategories in `../recipes.json`, otherwise the sidebar cannot select them.
Existing saved category filters may need to be cleared to include new categories.

Run from the repository root:

```sh
python3 tools/json_tools/validate_crafting_groups.py
```

This checks complete recipe coverage, unique assignments, valid category and
subcategory references, historical nested-category references, sorted members,
equivalent-result consistency and preservation of hidden-category visibility.
It resolves recipe inheritance and does not replace an in-game smoke test.

The [2026-08-27 taxonomy review](../../../../doc/UI_MODERNIZATION_STATUS/CRAFTING_GROUP_REVIEW.md)
records the changes, final group inventory and pending in-game checks.
