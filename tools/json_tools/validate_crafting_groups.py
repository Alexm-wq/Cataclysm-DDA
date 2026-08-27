#!/usr/bin/env python3
"""Check the base-game crafting taxonomy without compiling the game.

Recipe identity follows recipe::load: inherit result/variant, then append the
current declaration's id_suffix (which is not inherited).  Practice, nested,
uncraft, abstract and obsolete recipes are not part of this taxonomy.
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path


def read_entries(data_dir):
    entries = []
    for path in sorted(data_dir.rglob("*.json")):
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        for obj in data if isinstance(data, list) else [data]:
            if isinstance(obj, dict):
                entries.append((str(path), obj))
    return entries


def resolve_recipes(entries):
    pending = [(path, obj) for path, obj in entries
               if obj.get("type") == "recipe"]
    resolved = {}
    while pending:
        deferred = []
        for path, raw in pending:
            parent = raw.get("copy-from")
            if parent and parent not in resolved:
                deferred.append((path, raw))
                continue
            data = dict(resolved[parent][1]) if parent else {}
            data.update(raw)
            if "abstract" in raw:
                key = raw["abstract"]
            else:
                data.pop("abstract", None)
                key = data.get("result") or raw.get("id")
                if not key:
                    raise ValueError(f"{path}: recipe has no result or id")
                if data.get("variant"):
                    key += "_" + data["variant"]
                if "id_suffix" in raw:
                    key += "_" + raw["id_suffix"]
            resolved[key] = (path, data, raw)
        if len(deferred) == len(pending):
            parents = sorted({obj["copy-from"] for _, obj in deferred})
            raise ValueError("Unresolved recipe parents: " + ", ".join(parents))
        pending = deferred
    return {key: value for key, value in resolved.items()
            if "abstract" not in value[2] and not value[1].get("obsolete")}


def validate(entries):
    recipes = resolve_recipes(entries)
    categories = {obj["id"]: obj for _, obj in entries
                  if obj.get("type") == "recipe_category"}
    nested_ids = {obj["id"] for _, obj in entries
                  if obj.get("type") == "nested_category" and "id" in obj}
    groups = {}
    owners = {}
    errors = []
    result_groups = defaultdict(lambda: defaultdict(list))
    for path, group in entries:
        if group.get("type") != "crafting_group":
            continue
        gid = group.get("id")
        if not gid or gid in groups:
            errors.append(f"{path}: empty or duplicate group id: {gid}")
        groups[gid] = group
        category = categories.get(group.get("category"))
        if not category or category.get("is_wildcard"):
            errors.append(f"{gid}: invalid group category")
        elif group.get("subcategory") not in category["recipe_subcategories"]:
            errors.append(f"{gid}: invalid subcategory {group.get('subcategory')}")
        source = group.get("source_nested_category")
        if source and source not in nested_ids:
            errors.append(f"{gid}: unknown source nested category {source}")
        members = group.get("recipes", [])
        if not members:
            errors.append(f"{gid}: empty group")
        if members != sorted(members):
            errors.append(f"{gid}: recipe ids are not sorted")
        for rid in members:
            if rid in owners:
                errors.append(f"{rid}: duplicate assignment to {owners[rid]} and {gid}")
            owners[rid] = gid
            if rid not in recipes:
                errors.append(f"{gid}: unknown, abstract or obsolete recipe {rid}")
                continue
            _, recipe, raw = recipes[rid]
            original_category = categories.get(recipe.get("category"), {})
            if category and bool(category.get("is_hidden")) != bool(
                    original_category.get("is_hidden")):
                errors.append(f"{rid}: group changes hidden recipe visibility")
            # Camp jobs, seed designation and dedicated armor repair are
            # intentionally separate workflows, even with an identical result.
            if recipe.get("category") in {"CC_CAMP", "CC_BUILDING"}:
                continue
            if raw.get("id_suffix") in {"seed_designation", "repair"}:
                continue
            result = recipe.get("result")
            if result:
                identity = (result, recipe.get("variant", ""))
                result_groups[identity][gid].append(rid)
    for rid in sorted(recipes.keys() - owners.keys()):
        errors.append(f"{rid}: missing crafting group")
    for identity, assignments in sorted(result_groups.items()):
        if len(assignments) > 1:
            errors.append(f"{identity}: equivalent results split between "
                          + ", ".join(sorted(assignments)))
    return errors, len(recipes), len(groups)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path,
                        default=Path(__file__).resolve().parents[2] / "data/json")
    args = parser.parse_args()
    try:
        errors, recipes, groups = validate(read_entries(args.data_dir))
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print(f"Validated {recipes} recipes in {groups} crafting groups: "
          "complete coverage, unique assignments, valid categories, "
          "consistent results and preserved visibility.")


if __name__ == "__main__":
    main()
