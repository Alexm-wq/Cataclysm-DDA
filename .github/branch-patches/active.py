from __future__ import annotations

import copy
import json
import re
from collections import defaultdict
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


# ---------------------------------------------------------------------------
# Add a real, loader-backed crafting-group metadata type.  The modern browser
# will consume this later; this pass only establishes and populates the data.
# ---------------------------------------------------------------------------

h = Path("src/crafting_gui.h")
text = h.read_text(encoding="utf-8")
text = replace_once(
    text,
    '#include "type_id.h"\n',
    '#include "translation.h"\n#include "type_id.h"\n',
    "crafting_gui translation include",
)
text = replace_once(
    text,
    '''void load_recipe_category( const JsonObject &jsobj, const std::string &src );\nvoid reset_recipe_categories();\n''',
    '''void load_recipe_category( const JsonObject &jsobj, const std::string &src );\nvoid load_crafting_group( const JsonObject &jsobj, const std::string &src );\nvoid reset_recipe_categories();\nvoid reset_crafting_groups();\n''',
    "crafting group loader declarations",
)
text = replace_once(
    text,
    '''struct crafting_category {\n''',
    '''struct crafting_group {\n    std::string id;\n    translation name;\n    crafting_category_id category;\n    std::string subcategory;\n    int order = 0;\n    bool fallback = false;\n    std::string source_nested_category;\n    std::vector<recipe_id> recipes;\n};\n\nconst std::vector<crafting_group> &all_crafting_groups();\nconst crafting_group *crafting_group_for_recipe( const recipe_id &id );\n\nstruct crafting_category {\n''',
    "crafting group struct",
)
h.write_text(text, encoding="utf-8")

cpp = Path("src/crafting_gui.cpp")
text = cpp.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''generic_factory<crafting_category> craft_cat_list( "recipe_category" );\n''',
    '''generic_factory<crafting_category> craft_cat_list( "recipe_category" );\nstd::vector<crafting_group> craft_group_list;\nstd::map<std::string, size_t> craft_group_by_id;\nstd::map<recipe_id, size_t> craft_group_by_recipe;\n''',
    "crafting group storage",
)
text = replace_once(
    text,
    '''void load_recipe_category( const JsonObject &jsobj, const std::string &src )\n{\n    craft_cat_list.load( jsobj, src );\n}\n\n''',
    '''void load_recipe_category( const JsonObject &jsobj, const std::string &src )\n{\n    craft_cat_list.load( jsobj, src );\n}\n\nvoid load_crafting_group( const JsonObject &jo, const std::string & )\n{\n    crafting_group group;\n    group.id = jo.get_string( "id" );\n    mandatory( jo, false, "name", group.name );\n    mandatory( jo, false, "category", group.category );\n    mandatory( jo, false, "subcategory", group.subcategory );\n    optional( jo, false, "order", group.order, 0 );\n    optional( jo, false, "fallback", group.fallback, false );\n    optional( jo, false, "source_nested_category", group.source_nested_category, std::string() );\n    mandatory( jo, false, "recipes", group.recipes );\n\n    if( group.id.empty() ) {\n        jo.throw_error_at( "id", "crafting group id must not be empty" );\n    }\n    if( craft_group_by_id.count( group.id ) > 0 ) {\n        jo.throw_error_at( "id", string_format( "duplicate crafting group id %s", group.id ) );\n    }\n    for( const recipe_id &recipe : group.recipes ) {\n        const auto existing = craft_group_by_recipe.find( recipe );\n        if( existing != craft_group_by_recipe.end() ) {\n            jo.throw_error_at( "recipes", string_format(\n                                   "recipe %s belongs to both crafting group %s and %s",\n                                   recipe.str(), craft_group_list[existing->second].id, group.id ) );\n        }\n    }\n\n    const size_t index = craft_group_list.size();\n    craft_group_by_id.emplace( group.id, index );\n    for( const recipe_id &recipe : group.recipes ) {\n        craft_group_by_recipe.emplace( recipe, index );\n    }\n    craft_group_list.push_back( std::move( group ) );\n}\n\n''',
    "crafting group loader",
)
text = replace_once(
    text,
    '''void reset_recipe_categories()\n{\n    craft_cat_list.reset();\n}\n\n''',
    '''void reset_recipe_categories()\n{\n    craft_cat_list.reset();\n}\n\nvoid reset_crafting_groups()\n{\n    craft_group_list.clear();\n    craft_group_by_id.clear();\n    craft_group_by_recipe.clear();\n}\n\nconst std::vector<crafting_group> &all_crafting_groups()\n{\n    return craft_group_list;\n}\n\nconst crafting_group *crafting_group_for_recipe( const recipe_id &id )\n{\n    const auto found = craft_group_by_recipe.find( id );\n    return found == craft_group_by_recipe.end() ? nullptr : &craft_group_list[found->second];\n}\n\n''',
    "crafting group accessors",
)
cpp.write_text(text, encoding="utf-8")

init = Path("src/init.cpp")
text = init.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    add( "recipe_category", &load_recipe_category );\n    add( "recipe",  &recipe_dictionary::load_recipe );\n''',
    '''    add( "recipe_category", &load_recipe_category );\n    add( "crafting_group", &load_crafting_group );\n    add( "recipe",  &recipe_dictionary::load_recipe );\n''',
    "crafting group dynamic loader",
)
text = replace_count(
    text,
    '''    reset_recipe_categories();\n''',
    '''    reset_recipe_categories();\n    reset_crafting_groups();\n''',
    2,
    "crafting group reset",
)
init.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Build an exhaustive base-game taxonomy in separate, category-scoped lists.
# Existing top-level nested categories are treated as curated family metadata.
# Everything else receives an explicit fallback group derived from its existing
# crafting subcategory, so no real recipe is left without exactly one group.
# ---------------------------------------------------------------------------

group_dir = Path("data/json/recipes/crafting_groups")
if group_dir.exists():
    for old in group_dir.glob("*.json"):
        old.unlink()
else:
    group_dir.mkdir(parents=True)

records: list[tuple[Path, int, dict]] = []
for path in sorted(Path("data/json").rglob("*.json")):
    if group_dir in path.parents:
        continue
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise SystemExit(f"cannot parse {path}: {err}") from err
    objects = payload if isinstance(payload, list) else [payload]
    for index, obj in enumerate(objects):
        if isinstance(obj, dict):
            records.append((path, index, obj))

# Resolve the small subset of copy-from inheritance needed for recipe identity
# and category metadata.  This intentionally does not attempt to reproduce all
# JSON extend/delete semantics because none of those affect these scalar fields.
defs: dict[str, dict] = {}
for _, _, obj in records:
    for key in ("abstract", "id"):
        value = obj.get(key)
        if isinstance(value, str):
            defs.setdefault(value, obj)
    result = obj.get("result")
    if isinstance(result, str):
        defs.setdefault(result, obj)

resolved_cache: dict[int, dict] = {}


def resolve(obj: dict, stack: tuple[str, ...] = ()) -> dict:
    cache_key = id(obj)
    if cache_key in resolved_cache:
        return resolved_cache[cache_key]
    merged: dict = {}
    parent_name = obj.get("copy-from")
    if isinstance(parent_name, str) and parent_name in defs:
        if parent_name in stack:
            raise SystemExit(f"copy-from cycle while resolving {' -> '.join(stack + (parent_name,))}")
        merged.update(copy.deepcopy(resolve(defs[parent_name], stack + (parent_name,))))
    merged.update(copy.deepcopy(obj))
    if "abstract" not in obj:
        merged.pop("abstract", None)
    resolved_cache[cache_key] = merged
    return merged


def normal_recipe_id(raw: dict, effective: dict) -> str | None:
    if raw.get("type") != "recipe" or "abstract" in raw or effective.get("obsolete") is True:
        return None
    result = effective.get("result")
    if isinstance(result, str) and result:
        rid = result
        variant = effective.get("variant")
        if isinstance(variant, str) and variant:
            rid += "_" + variant
        suffix = effective.get("id_suffix")
        if isinstance(suffix, str) and suffix:
            rid += "_" + suffix
        return rid
    explicit = raw.get("id") or effective.get("id")
    if isinstance(explicit, str) and explicit:
        return explicit
    return None


recipes: dict[str, dict] = {}
recipe_origins: dict[str, str] = {}
unresolved: list[str] = []
nested: dict[str, dict] = {}

for path, index, raw in records:
    effective = resolve(raw)
    if raw.get("type") == "nested_category" and isinstance(effective.get("id"), str):
        nested[effective["id"]] = effective
        continue
    if raw.get("type") != "recipe" or "abstract" in raw or effective.get("obsolete") is True:
        continue
    rid = normal_recipe_id(raw, effective)
    category = effective.get("category")
    subcategory = effective.get("subcategory")
    if not rid or not isinstance(category, str) or not isinstance(subcategory, str):
        unresolved.append(f"{path}:{index} id={rid!r} category={category!r} subcategory={subcategory!r}")
        continue
    if rid in recipes:
        # Multiple JSON records for the same effective recipe id would make a
        # one-owner taxonomy ambiguous, so reject instead of silently choosing.
        raise SystemExit(f"duplicate effective recipe id {rid}: {recipe_origins[rid]} and {path}:{index}")
    recipes[rid] = {
        "id": rid,
        "category": category,
        "subcategory": subcategory,
    }
    recipe_origins[rid] = f"{path}:{index}"

if unresolved:
    raise SystemExit("normal recipes missing identity/category metadata:\n" + "\n".join(unresolved[:50]))


# Recursively flatten nested-category descendants down to real recipe ids.
expanded_nested: dict[str, set[str]] = {}


def expand_nested(nid: str, stack: tuple[str, ...] = ()) -> set[str]:
    if nid in expanded_nested:
        return expanded_nested[nid]
    if nid in stack:
        raise SystemExit(f"nested-category cycle: {' -> '.join(stack + (nid,))}")
    obj = nested.get(nid)
    if obj is None:
        return set()
    members: set[str] = set()
    for child in obj.get("nested_category_data", []):
        if child in recipes:
            members.add(child)
        elif child in nested:
            members.update(expand_nested(child, stack + (nid,)))
    expanded_nested[nid] = members
    return members

for nid in nested:
    expand_nested(nid)


def is_top_level_nested(obj: dict) -> bool:
    category = obj.get("category")
    subcategory = obj.get("subcategory")
    return isinstance(category, str) and isinstance(subcategory, str) and category != "CC_*" and not subcategory.startswith("CSC_*_")


def capitalize_name(value):
    if isinstance(value, str):
        return value[:1].upper() + value[1:] if value else value
    if isinstance(value, dict):
        result = copy.deepcopy(value)
        for key in ("str", "str_sp", "str_pl"):
            if isinstance(result.get(key), str) and result[key]:
                result[key] = result[key][:1].upper() + result[key][1:]
        return result
    return "Miscellaneous"


def display_name_key(value) -> str:
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, dict):
        return str(value.get("str") or value.get("str_sp") or value.get("str_pl") or "").casefold()
    return ""


def slug(value: str) -> str:
    value = value.lower().replace("*", "all")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "misc"


def fallback_title(category: str, subcategory: str) -> str:
    cat = category.removeprefix("CC_")
    prefix = f"CSC_{cat}_"
    suffix = subcategory[len(prefix):] if subcategory.startswith(prefix) else subcategory.removeprefix("CSC_")
    explicit = {
        ("WEAPON", "BASHING"): "Bashing weapons",
        ("WEAPON", "CUTTING"): "Cutting weapons",
        ("WEAPON", "STABBING"): "Piercing weapons",
        ("WEAPON", "RANGED"): "Ranged weapons",
        ("WEAPON", "OTHER"): "Other weapons",
        ("ARMOR", "STORAGE"): "Storage gear",
        ("FOOD", "DRINKS"): "Drinks",
        ("FOOD", "MEAT"): "Meat dishes",
        ("FOOD", "VEGGY"): "Vegetable dishes",
        ("CHEM", "DRUGS"): "Drugs and medicine",
        ("ELECTRONIC", "PARTS"): "Electronic parts",
    }
    if (cat, suffix) in explicit:
        return explicit[(cat, suffix)]
    words = suffix.replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:] if words else "Miscellaneous"


# Candidate curated groups from existing visible nested categories.
curated: list[dict] = []
for nid, obj in nested.items():
    if not is_top_level_nested(obj):
        continue
    members = expanded_nested.get(nid, set())
    if not members:
        continue
    curated.append({
        "nested_id": nid,
        "name": capitalize_name(obj.get("name", nid.removeprefix("nested_").replace("_", " "))),
        "category": obj["category"],
        "subcategory": obj["subcategory"],
        "members": members,
    })

candidates_by_recipe: dict[str, list[dict]] = defaultdict(list)
for group in curated:
    for rid in group["members"]:
        candidates_by_recipe[rid].append(group)

assignment: dict[str, tuple[str, dict]] = {}
groups: dict[str, dict] = {}
used_group_ids: set[str] = set()


def unique_group_id(base: str) -> str:
    candidate = base
    suffix = 2
    while candidate in used_group_ids:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used_group_ids.add(candidate)
    return candidate


# Prefer curated groups matching the recipe's actual category/subcategory.  If
# more than one remains, the smaller descendant set is the more specific family.
for rid, recipe in recipes.items():
    choices = candidates_by_recipe.get(rid, [])
    matching = [g for g in choices if g["category"] == recipe["category"] and g["subcategory"] == recipe["subcategory"]]
    pool = matching or choices
    if not pool:
        continue
    chosen = min(pool, key=lambda g: (len(g["members"]), display_name_key(g["name"]), g["nested_id"]))
    assignment[rid] = ("curated", chosen)

# Materialize only curated groups that actually won at least one recipe.
curated_winners: dict[str, list[str]] = defaultdict(list)
curated_by_id: dict[str, dict] = {}
for rid, (kind, chosen) in assignment.items():
    if kind == "curated":
        curated_winners[chosen["nested_id"]].append(rid)
        curated_by_id[chosen["nested_id"]] = chosen

for nid, members in curated_winners.items():
    src = curated_by_id[nid]
    gid = unique_group_id("cg_" + slug(nid.removeprefix("nested_")))
    groups[gid] = {
        "type": "crafting_group",
        "id": gid,
        "name": src["name"],
        "category": src["category"],
        "subcategory": src["subcategory"],
        "order": 0,
        "source_nested_category": nid,
        "recipes": sorted(members),
    }
    for rid in members:
        assignment[rid] = ("group", groups[gid])

# Remaining recipes are still explicit metadata, grouped by their current
# subcategory and clearly marked fallback for later taxonomy refinement.
fallback_members: dict[tuple[str, str], list[str]] = defaultdict(list)
for rid, recipe in recipes.items():
    if rid not in assignment:
        fallback_members[(recipe["category"], recipe["subcategory"])].append(rid)

for (category, subcategory), members in sorted(fallback_members.items()):
    cat_slug = slug(category.removeprefix("CC_"))
    sub_slug = slug(subcategory.removeprefix("CSC_"))
    gid = unique_group_id(f"cg_{cat_slug}_{sub_slug}")
    group = {
        "type": "crafting_group",
        "id": gid,
        "name": fallback_title(category, subcategory),
        "category": category,
        "subcategory": subcategory,
        "order": 0,
        "fallback": True,
        "recipes": sorted(members),
    }
    groups[gid] = group
    for rid in members:
        assignment[rid] = ("group", group)

if set(assignment) != set(recipes):
    missing = sorted(set(recipes) - set(assignment))
    extra = sorted(set(assignment) - set(recipes))
    raise SystemExit(f"crafting group coverage mismatch; missing={missing[:20]} extra={extra[:20]}")

# Assert one-owner coverage from the materialized lists themselves.
seen: dict[str, str] = {}
for gid, group in groups.items():
    for rid in group["recipes"]:
        if rid in seen:
            raise SystemExit(f"recipe {rid} appears in both {seen[rid]} and {gid}")
        seen[rid] = gid
if set(seen) != set(recipes):
    raise SystemExit(f"materialized crafting groups do not cover all recipes ({len(seen)} / {len(recipes)})")

# Stable per-category ordering.  Later GUI code can render these directly.
by_category: dict[str, list[dict]] = defaultdict(list)
for group in groups.values():
    by_category[group["category"]].append(group)

for category, category_groups in by_category.items():
    category_groups.sort(key=lambda g: (display_name_key(g["name"]), g["id"]))
    for order, group in enumerate(category_groups, start=10):
        group["order"] = order * 10
    filename = slug(category.removeprefix("CC_")) + ".json"
    (group_dir / filename).write_text(
        json.dumps(category_groups, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

readme = '''# Crafting groups\n\nThese files define the section-title taxonomy for the modern crafting browser.\n\nEach normal base-game `recipe` belongs to exactly one `crafting_group`. Existing\nvisible `nested_category` definitions are used as the curated source wherever\npossible and recorded in `source_nested_category`. Recipes not covered by an\nexisting curated nest are still assigned explicitly and marked `fallback: true`;\nthose groups are the review queue for later taxonomy refinement.\n\nThe legacy nested-category data remains untouched for compatibility. The modern\nbrowser can migrate to these flat group headings independently.\n'''
(group_dir / "README.md").write_text(readme, encoding="utf-8")

curated_group_count = sum(1 for g in groups.values() if "source_nested_category" in g)
fallback_group_count = sum(1 for g in groups.values() if g.get("fallback"))
fallback_recipe_count = sum(len(g["recipes"]) for g in groups.values() if g.get("fallback"))
print(
    f"crafting-group taxonomy: {len(recipes)} recipes, {len(groups)} groups, "
    f"{curated_group_count} curated groups, {fallback_group_count} fallback groups, "
    f"{fallback_recipe_count} recipes in fallback groups, {len(by_category)} category files"
)
for category in sorted(by_category):
    category_groups = by_category[category]
    recipe_count = sum(len(g["recipes"]) for g in category_groups)
    fallback_count = sum(1 for g in category_groups if g.get("fallback"))
    print(f"  {category}: {recipe_count} recipes / {len(category_groups)} groups / {fallback_count} fallback groups")

Path("/tmp/branch_patch_commit_message").write_text(
    "Add exhaustive crafting group metadata taxonomy\n", encoding="utf-8"
)
