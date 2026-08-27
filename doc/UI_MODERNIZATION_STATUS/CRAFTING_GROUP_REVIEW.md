# Cataclysm-DDA crafting-group review

Branch: `mouse-inventory-0-i-test`

Reviewed baseline: `bc1fc99bc8074f2c3dcd54e949efb892ba25d6d7`

Status: implemented on the test branch; in-game validation pending.

Review date: 2026-08-27

## Results

- Reviewed all **5,629 recipe assignments** across the original **244 groups**.
- **1,893 recipes reassigned**; another **64** retain their group but move to a more appropriate category/subcategory.
- Final taxonomy: **305 groups**, with no unreviewed fallback groups or generic “Other” headings.
- Added visible **Construction**, containing **194 recipes** in **18 groups**.
- Preserved all **557 hidden camp recipes**, now organized into eight groups.
- No recipe requirements, outputs, skills, learning rules, times, item properties or camp progression changed.

## Approach

Reviewed group member lists and recipe families, then checked item descriptions,
recipe contents, item capabilities and deployment behavior for ambiguous cases.
Assignments are explicit recipe IDs, not runtime keyword rules. Same-result
manufacturing methods are checked together. Existing families remain where they
fit; useful differences such as seed designation, camp jobs and dedicated armor
repair remain separate.

This review records the taxonomy decisions, representative corrections,
validation results and complete final group inventory. Exact recipe membership
is maintained in [the crafting-group definitions](../../data/json/recipes/crafting_groups/README.md).

## Construction

| Subcategory | Groups |
| --- | --- |
| Materials | Lumber; masonry; glazing; fasteners/hardware; structural metal/fencing |
| Tools | Woodworking; building/demolition; lifting/access |
| Furniture | Furniture/storage; bedding; decorations/planters; training equipment |
| Shelters | Tents/shelter kits; sleeping bags |
| Workshops | Workshop stations; food-processing stations |
| Utilities | Fire containment/heating; pipes/plumbing |

The existing `CC_BUILDING` is a hidden, mechanically significant category for
camp blueprints. It was **not** unhidden or reused for ordinary crafting.

## Representative corrections

| Recipe or family | Correct destination |
| --- | --- |
| Concrete, cement, mortar, wet adobe and bricks | Construction → Masonry materials |
| Planks from logs, including manual and powered methods | Construction → Lumber |
| Tables, chairs, stools, bedding and shelters | Appropriate Construction groups |
| Workbenches, anvils, forges and kilns | Construction → Workshop stations |
| Vehicle armor kits and boat hulls | Vehicle armor and hulls |
| Steel ballistic inserts and iridescent plates | Armor → Components → Ballistic armor plates |
| Brigandine shoulder attachments and exoskeleton modules | Armor → Components |
| Tireplate | Retained as torso armor; it is not an insert or vehicle armor |
| Medical oxygen delivery kits | Medical equipment and mobility aids |
| Welding gases, filler rods, solder and rosin | Welding and soldering supplies |
| Finished ovens, minifridges and freezers | Appliances |
| Grain mills versus water wheels/wind turbines | Food-processing stations versus electrical generation |
| Ketene lamp | Laboratory and extraction equipment; not lighting |
| Drums and bagpipes | Percussion and wind instruments respectively |
| Canned/uncanned fruit juice | Drinks |
| Rehydrated cheese | Dairy products; not Drinks |
| Animal feed; bone/chitin fertilizer meal | Animals → Feed; Chemicals → Fertilizers and pest control |
| All flour milling methods | Flours |
| Chemical peroxide and acetic anhydride | Chemical reagents; removed from Acids |
| Root cellars and storage shacks | Camp buildings and shelters; not communications/utilities |

## Validation performed

- Full-data validator: **5,629 recipes, 305 groups**, no omissions, duplicate assignments, invalid category/subcategory references, unknown historical nest references or unintended hidden-category changes.
- Exact equality of the baseline and final assigned recipe-ID sets.
- Equivalent output/variant consistency, with documented workflow exceptions.
- Negative checks: duplicate, missing and unknown recipes, invalid subcategory, accidental hidden-category reassignment.
- Inheritance regression checks: inherited results/variants, non-inherited suffixes, abstract/obsolete exclusions.
- Official JSON formatter: all 14 JSON files pass an idempotent second check.
- Translation extraction: all 305 headings handled; added the missing crafting-group extractor.
- Python compilation and `git diff --check` pass.
- Patch applies cleanly to an index loaded from the reviewed baseline.

Added the validator to the repository's JSON CI workflow. **No full game build
or in-game smoke test was run.** Existing saved category filters may need to be
cleared to show the newly introduced categories. The classic recipe/nested
classification is intentionally unchanged.

## Check the implementation

Run from the repository root:

```sh
python3 tools/json_tools/validate_crafting_groups.py
```

### Pending in-game checks

- Clear saved category filters if Construction or new subcategories do not appear.
- Browse Construction materials, tools, furniture, shelters, workshops and utilities.
- Search representative items from the correction table and confirm their headings.
- Compare alternate recipes for the same output, such as planks, flour and fruit juice.
- Check that hidden camp blueprints remain absent from ordinary player crafting.
- Confirm a normal recipe still crafts with its existing requirements and output.

## Final category inventory

| Category | Groups | Recipes |
| --- | ---: | ---: |
| `CC_AMMO` | 14 | 312 |
| `CC_ANIMALS` | 6 | 65 |
| `CC_APPLIANCE` | 2 | 10 |
| `CC_ARMOR` | 114 | 1868 |
| `CC_BUILDING` | 8 | 557 |
| `CC_CAMP` | 3 | 17 |
| `CC_CHEM` | 11 | 222 |
| `CC_CONSTRUCTION` | 18 | 194 |
| `CC_ELECTRONIC` | 10 | 114 |
| `CC_FOOD` | 23 | 1029 |
| `CC_MUSIC` | 3 | 7 |
| `CC_OTHER` | 49 | 739 |
| `CC_WEAPON` | 44 | 495 |

## Final group inventory

| Category | Group | Recipes |
| --- | --- | ---: |
| `CC_AMMO` | Ammunition casings | 10 |
| `CC_AMMO` | Arrows and bolts | 19 |
| `CC_AMMO` | Atlatl spears | 3 |
| `CC_AMMO` | Components | 7 |
| `CC_AMMO` | Firearm primers | 5 |
| `CC_AMMO` | Flamethrower fuels | 3 |
| `CC_AMMO` | Homemade rockets | 3 |
| `CC_AMMO` | Launcher ammunition | 12 |
| `CC_AMMO` | Pistol | 107 |
| `CC_AMMO` | Rifle | 96 |
| `CC_AMMO` | Shot | 35 |
| `CC_AMMO` | Slingshot ammunition | 4 |
| `CC_AMMO` | Specialty ammunition | 5 |
| `CC_AMMO` | Sprayable chemicals | 3 |
| `CC_ANIMALS` | Animal feed | 19 |
| `CC_ANIMALS` | Animal handling and carriers | 7 |
| `CC_ANIMALS` | Bovine armor | 14 |
| `CC_ANIMALS` | Canine armor | 10 |
| `CC_ANIMALS` | Equine armor | 14 |
| `CC_ANIMALS` | Equine storage | 1 |
| `CC_APPLIANCE` | Kitchen and refrigeration appliances | 6 |
| `CC_APPLIANCE` | Lighting | 4 |
| `CC_ARMOR` | Aprons | 21 |
| `CC_ARMOR` | Arms | 44 |
| `CC_ARMOR` | Ballistic armor plates | 15 |
| `CC_ARMOR` | Bandoliers | 7 |
| `CC_ARMOR` | Belt loops | 3 |
| `CC_ARMOR` | Belts | 7 |
| `CC_ARMOR` | Brigandine coats | 15 |
| `CC_ARMOR` | Brigandine coats with shoulder guards | 15 |
| `CC_ARMOR` | Brigandine shoulder attachments | 15 |
| `CC_ARMOR` | Brigandines | 15 |
| `CC_ARMOR` | Brigandines with shoulder guards | 15 |
| `CC_ARMOR` | Bronze greaves | 3 |
| `CC_ARMOR` | Bronze helmets | 6 |
| `CC_ARMOR` | Bronze vambraces | 3 |
| `CC_ARMOR` | Canvas aketons | 6 |
| `CC_ARMOR` | Canvas arming gloves | 6 |
| `CC_ARMOR` | Canvas arming pants | 6 |
| `CC_ARMOR` | Canvas coifs | 3 |
| `CC_ARMOR` | Canvas gambesons | 9 |
| `CC_ARMOR` | Cardboard armor suits | 1 |
| `CC_ARMOR` | Chitinous arm guards | 6 |
| `CC_ARMOR` | Chitinous armor | 6 |
| `CC_ARMOR` | Chitinous boots | 6 |
| `CC_ARMOR` | Chitinous gauntlets | 6 |
| `CC_ARMOR` | Chitinous helmets | 12 |
| `CC_ARMOR` | Chitinous leg guards | 6 |
| `CC_ARMOR` | Cloaks | 6 |
| `CC_ARMOR` | Collars | 3 |
| `CC_ARMOR` | Costume ears | 3 |
| `CC_ARMOR` | Cuirasses | 18 |
| `CC_ARMOR` | Dusters | 25 |
| `CC_ARMOR` | Exoskeleton armor modules | 12 |
| `CC_ARMOR` | Feet | 71 |
| `CC_ARMOR` | Fur armors | 6 |
| `CC_ARMOR` | Gas masks | 5 |
| `CC_ARMOR` | Hands | 56 |
| `CC_ARMOR` | Head | 100 |
| `CC_ARMOR` | Holsters | 20 |
| `CC_ARMOR` | Hoodies | 22 |
| `CC_ARMOR` | Iron greaves | 3 |
| `CC_ARMOR` | Jewelry | 17 |
| `CC_ARMOR` | Jumpsuits | 26 |
| `CC_ARMOR` | Kabutos | 3 |
| `CC_ARMOR` | Leather armors | 3 |
| `CC_ARMOR` | Legs | 81 |
| `CC_ARMOR` | Loincloths | 4 |
| `CC_ARMOR` | Nylon aketons | 6 |
| `CC_ARMOR` | Nylon arming gloves | 6 |
| `CC_ARMOR` | Nylon arming pants | 6 |
| `CC_ARMOR` | Nylon coifs | 3 |
| `CC_ARMOR` | Nylon gambesons | 9 |
| `CC_ARMOR` | Padded arming pants | 3 |
| `CC_ARMOR` | Padded gambeson hoods | 3 |
| `CC_ARMOR` | Padded gambesons | 6 |
| `CC_ARMOR` | Pot helms | 4 |
| `CC_ARMOR` | Pouches | 26 |
| `CC_ARMOR` | Quivers | 9 |
| `CC_ARMOR` | Rebreathers | 5 |
| `CC_ARMOR` | Respirator filters and cartridges | 8 |
| `CC_ARMOR` | Scrap armors | 6 |
| `CC_ARMOR` | Scrap helmets | 3 |
| `CC_ARMOR` | Sheaths, scabbards and weapon slings | 16 |
| `CC_ARMOR` | Sheet metal armors | 12 |
| `CC_ARMOR` | Splint mail greaves | 15 |
| `CC_ARMOR` | Splint mail vambraces | 15 |
| `CC_ARMOR` | Steel arm guards | 30 |
| `CC_ARMOR` | Steel brigandine gloves | 15 |
| `CC_ARMOR` | Steel chain aventails | 15 |
| `CC_ARMOR` | Steel chain chausses | 15 |
| `CC_ARMOR` | Steel chain coifs | 15 |
| `CC_ARMOR` | Steel chain gloves | 15 |
| `CC_ARMOR` | Steel chain half-legs | 15 |
| `CC_ARMOR` | Steel chain hauberks | 15 |
| `CC_ARMOR` | Steel chain jumpsuits | 30 |
| `CC_ARMOR` | Steel chain legs | 15 |
| `CC_ARMOR` | Steel chain partial aventails | 15 |
| `CC_ARMOR` | Steel chain sleeveless jumpsuits | 15 |
| `CC_ARMOR` | Steel chain sleeves | 15 |
| `CC_ARMOR` | Steel chain suits | 18 |
| `CC_ARMOR` | Steel chain vests | 15 |
| `CC_ARMOR` | Steel chestplates | 30 |
| `CC_ARMOR` | Steel close helms | 30 |
| `CC_ARMOR` | Steel demi-gauntlets | 10 |
| `CC_ARMOR` | Steel elbow guards | 15 |
| `CC_ARMOR` | Steel facemasks | 15 |
| `CC_ARMOR` | Steel knee guards | 15 |
| `CC_ARMOR` | Steel lamellar cuirasses | 6 |
| `CC_ARMOR` | Steel lamellar repair | 6 |
| `CC_ARMOR` | Steel leg guards | 30 |
| `CC_ARMOR` | Steel mirror armor | 15 |
| `CC_ARMOR` | Steel mitten gauntlets | 10 |
| `CC_ARMOR` | Steel nasal helmets | 15 |
| `CC_ARMOR` | Steel plate armors | 60 |
| `CC_ARMOR` | Steel sabatons | 10 |
| `CC_ARMOR` | Steel splint arm guards | 15 |
| `CC_ARMOR` | Steel splint leg guards | 15 |
| `CC_ARMOR` | Steel turban helmets | 15 |
| `CC_ARMOR` | Storage gear | 71 |
| `CC_ARMOR` | Suit | 28 |
| `CC_ARMOR` | Survivor boots | 27 |
| `CC_ARMOR` | Survivor gloves | 33 |
| `CC_ARMOR` | Survivor hoods | 24 |
| `CC_ARMOR` | Survivor masks | 15 |
| `CC_ARMOR` | Survivor pants | 6 |
| `CC_ARMOR` | Tails | 3 |
| `CC_ARMOR` | Throat guards | 3 |
| `CC_ARMOR` | Torso | 125 |
| `CC_ARMOR` | Trenchcoats | 15 |
| `CC_ARMOR` | Wetsuits | 16 |
| `CC_ARMOR` | Wool aketons | 6 |
| `CC_ARMOR` | Wool arming gloves | 6 |
| `CC_ARMOR` | Wool arming pants | 6 |
| `CC_ARMOR` | Wool coifs | 3 |
| `CC_ARMOR` | Wool gambesons | 9 |
| `CC_BUILDING` | Camp buildings and shelters | 167 |
| `CC_BUILDING` | Camp defenses | 36 |
| `CC_BUILDING` | Camp farms and livestock | 51 |
| `CC_BUILDING` | Camp furnishings and storage | 120 |
| `CC_BUILDING` | Camp kitchens and food processing | 48 |
| `CC_BUILDING` | Camp surveys and setup | 52 |
| `CC_BUILDING` | Camp water, power and communications | 56 |
| `CC_BUILDING` | Camp workshops | 27 |
| `CC_CAMP` | Companion data recovery | 7 |
| `CC_CAMP` | Companion fishing | 3 |
| `CC_CAMP` | Companion material production | 7 |
| `CC_CHEM` | Acids | 18 |
| `CC_CHEM` | Chemical reagents | 56 |
| `CC_CHEM` | Cleaners and disinfectants | 8 |
| `CC_CHEM` | Drugs and medicine | 26 |
| `CC_CHEM` | Explosive compounds and propellants | 10 |
| `CC_CHEM` | Fertilizers and pest control | 26 |
| `CC_CHEM` | Fuel | 6 |
| `CC_CHEM` | Mutagen primers | 28 |
| `CC_CHEM` | Mutagens | 30 |
| `CC_CHEM` | Mutation samples and precursors | 6 |
| `CC_CHEM` | Refined cannabis | 8 |
| `CC_CONSTRUCTION` | Bedding | 17 |
| `CC_CONSTRUCTION` | Building and demolition tools | 33 |
| `CC_CONSTRUCTION` | Decorations and planters | 5 |
| `CC_CONSTRUCTION` | Fasteners and hardware | 7 |
| `CC_CONSTRUCTION` | Fireplaces and heaters | 6 |
| `CC_CONSTRUCTION` | Food-processing stations | 10 |
| `CC_CONSTRUCTION` | Furniture and storage | 12 |
| `CC_CONSTRUCTION` | Glass and glazing | 4 |
| `CC_CONSTRUCTION` | Lifting and access equipment | 8 |
| `CC_CONSTRUCTION` | Lumber | 21 |
| `CC_CONSTRUCTION` | Masonry materials | 12 |
| `CC_CONSTRUCTION` | Pipes and plumbing | 7 |
| `CC_CONSTRUCTION` | Sleeping bags | 3 |
| `CC_CONSTRUCTION` | Structural metal and fencing | 6 |
| `CC_CONSTRUCTION` | Tents and shelters | 6 |
| `CC_CONSTRUCTION` | Training equipment | 4 |
| `CC_CONSTRUCTION` | Woodworking tools | 17 |
| `CC_CONSTRUCTION` | Workshop stations | 16 |
| `CC_ELECTRONIC` | Batteries | 11 |
| `CC_ELECTRONIC` | Cameras and surveillance | 6 |
| `CC_ELECTRONIC` | Electric lights and headlights | 14 |
| `CC_ELECTRONIC` | Electrical components and motors | 19 |
| `CC_ELECTRONIC` | Electronics assembly tools | 2 |
| `CC_ELECTRONIC` | Inactive bots | 22 |
| `CC_ELECTRONIC` | Methanol fuel cartridges | 4 |
| `CC_ELECTRONIC` | Power connections and charging | 17 |
| `CC_ELECTRONIC` | Radios and remote activation | 6 |
| `CC_ELECTRONIC` | Solar, wind and water power | 13 |
| `CC_FOOD` | Bread, pancakes and baking | 38 |
| `CC_FOOD` | Brewing and fermentation | 32 |
| `CC_FOOD` | Cocktails and mixed drinks | 29 |
| `CC_FOOD` | Condiments, oils and sweeteners | 78 |
| `CC_FOOD` | Cooking ingredients | 16 |
| `CC_FOOD` | Dairy products | 21 |
| `CC_FOOD` | Desserts and confectionery | 54 |
| `CC_FOOD` | Dried and powdered foods | 46 |
| `CC_FOOD` | Drinks | 89 |
| `CC_FOOD` | Egg dishes | 15 |
| `CC_FOOD` | Flours | 16 |
| `CC_FOOD` | Grain processing and cereals | 54 |
| `CC_FOOD` | Meat dishes | 178 |
| `CC_FOOD` | Pasta | 12 |
| `CC_FOOD` | Pemmican | 3 |
| `CC_FOOD` | Pizzas, pies and casseroles | 15 |
| `CC_FOOD` | Sandwiches, burgers and wraps | 40 |
| `CC_FOOD` | Seeds | 71 |
| `CC_FOOD` | Shelled nuts | 9 |
| `CC_FOOD` | Snacks | 19 |
| `CC_FOOD` | Soups, stews and broths | 53 |
| `CC_FOOD` | Teas | 21 |
| `CC_FOOD` | Vegetables, grains and plant-based dishes | 120 |
| `CC_MUSIC` | Percussion instruments | 2 |
| `CC_MUSIC` | String instruments | 3 |
| `CC_MUSIC` | Wind instruments | 2 |
| `CC_OTHER` | Adhesives and sealants | 3 |
| `CC_OTHER` | Antiseptics | 6 |
| `CC_OTHER` | Armor components | 16 |
| `CC_OTHER` | Bags, buckets and general containers | 11 |
| `CC_OTHER` | Barrels, tanks and gas cylinders | 20 |
| `CC_OTHER` | Bleeding control | 9 |
| `CC_OTHER` | Bottles, canteens and waterskins | 23 |
| `CC_OTHER` | Bowls, cups and food containers | 18 |
| `CC_OTHER` | Boxes | 20 |
| `CC_OTHER` | Bundle of items | 14 |
| `CC_OTHER` | Cleaning and personal care | 11 |
| `CC_OTHER` | Cookware and kitchen tools | 52 |
| `CC_OTHER` | Currency bundles and wrappers | 17 |
| `CC_OTHER` | Decoys and distractions | 4 |
| `CC_OTHER` | Deflated tires | 8 |
| `CC_OTHER` | Fabric and tailoring supplies | 31 |
| `CC_OTHER` | Farming and harvesting tools | 16 |
| `CC_OTHER` | Fibers, thread and yarn | 19 |
| `CC_OTHER` | Firestarting and flame lighting | 18 |
| `CC_OTHER` | Fishing and butchering tools | 15 |
| `CC_OTHER` | Games and recreation | 9 |
| `CC_OTHER` | Gunsmithing and reloading tools | 5 |
| `CC_OTHER` | Inflated tires | 8 |
| `CC_OTHER` | Knapping and abrasive tools | 7 |
| `CC_OTHER` | Laboratory and extraction equipment | 19 |
| `CC_OTHER` | Leather, hides and pelts | 10 |
| `CC_OTHER` | Locks and access tools | 5 |
| `CC_OTHER` | Mechanical and tool components | 11 |
| `CC_OTHER` | Mechanical tools | 15 |
| `CC_OTHER` | Medical equipment and mobility aids | 10 |
| `CC_OTHER` | Metal ingots and scrap | 45 |
| `CC_OTHER` | Metalworking and welding tools | 23 |
| `CC_OTHER` | Optics and measuring instruments | 6 |
| `CC_OTHER` | Plastics and rubber | 9 |
| `CC_OTHER` | Ropes and cordage | 48 |
| `CC_OTHER` | Sewing and textile tools | 18 |
| `CC_OTHER` | Splints | 6 |
| `CC_OTHER` | Steel wires | 11 |
| `CC_OTHER` | Traps | 13 |
| `CC_OTHER` | Vehicle armor and hulls | 13 |
| `CC_OTHER` | Vehicle frames | 8 |
| `CC_OTHER` | Vehicle propulsion and controls | 25 |
| `CC_OTHER` | Vehicle seating and cargo | 16 |
| `CC_OTHER` | Vehicle utility rigs | 25 |
| `CC_OTHER` | Water collection and purification | 12 |
| `CC_OTHER` | Welding and soldering supplies | 10 |
| `CC_OTHER` | Wheels and wheel mounts | 11 |
| `CC_OTHER` | Wood, stone and ash | 5 |
| `CC_OTHER` | Writing and record keeping | 5 |
| `CC_WEAPON` | Arming swords | 5 |
| `CC_WEAPON` | Attachment mounts | 8 |
| `CC_WEAPON` | Bashing weapons | 31 |
| `CC_WEAPON` | Battle axes | 6 |
| `CC_WEAPON` | Bows | 7 |
| `CC_WEAPON` | Broadswords | 5 |
| `CC_WEAPON` | Cavalry sabers | 5 |
| `CC_WEAPON` | Crossbows | 6 |
| `CC_WEAPON` | Cutlasses | 6 |
| `CC_WEAPON` | Cutting weapons | 33 |
| `CC_WEAPON` | Estocs | 5 |
| `CC_WEAPON` | Explosive | 25 |
| `CC_WEAPON` | Falxes | 5 |
| `CC_WEAPON` | Flintlock arms | 7 |
| `CC_WEAPON` | Jian | 5 |
| `CC_WEAPON` | Katana | 5 |
| `CC_WEAPON` | Kilijes | 5 |
| `CC_WEAPON` | Kriegsmessers | 5 |
| `CC_WEAPON` | Kukris | 6 |
| `CC_WEAPON` | Longswords | 5 |
| `CC_WEAPON` | Maces | 13 |
| `CC_WEAPON` | Macuahuitls | 9 |
| `CC_WEAPON` | Magazines | 30 |
| `CC_WEAPON` | Modified attachments | 5 |
| `CC_WEAPON` | Mods | 57 |
| `CC_WEAPON` | Nodachi | 5 |
| `CC_WEAPON` | Piercing | 30 |
| `CC_WEAPON` | Pipe rifles | 3 |
| `CC_WEAPON` | Ranged weapons | 29 |
| `CC_WEAPON` | Rapiers | 5 |
| `CC_WEAPON` | Shamshirs | 5 |
| `CC_WEAPON` | Sling-ready explosives | 6 |
| `CC_WEAPON` | Spears | 27 |
| `CC_WEAPON` | Staffs | 11 |
| `CC_WEAPON` | Survival knives | 6 |
| `CC_WEAPON` | Talwars | 5 |
| `CC_WEAPON` | Tepoztopilis | 8 |
| `CC_WEAPON` | Throwing weapons | 11 |
| `CC_WEAPON` | Trench knives | 6 |
| `CC_WEAPON` | Unarmed | 24 |
| `CC_WEAPON` | Wakizashi | 5 |
| `CC_WEAPON` | Weapon shafts and components | 3 |
| `CC_WEAPON` | Whips | 2 |
| `CC_WEAPON` | Zweihänders | 5 |
