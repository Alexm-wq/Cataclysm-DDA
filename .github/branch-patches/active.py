from pathlib import Path
import json
from collections import Counter, defaultdict

root = Path("data/json/construction")
summary = Counter()
by_file = defaultdict(Counter)
untagged = []

for path in sorted(root.glob("*.json")):
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        print(f"PARSE_ERROR {path}: {exc}")
        continue
    if not isinstance(data, list):
        continue
    for obj in data:
        if not isinstance(obj, dict) or obj.get("type") != "construction":
            continue
        intent = obj.get("ui_intent", "<unset>")
        category = obj.get("category", "OTHER")
        summary[intent] += 1
        by_file[path.name][intent] += 1
        if intent == "<unset>":
            comps = obj.get("components", [])
            component_groups = len(comps) if isinstance(comps, list) else 0
            pre = obj.get("pre_terrain", obj.get("pre_flags", ""))
            post = obj.get("post_terrain", "")
            untagged.append((
                path.name,
                obj.get("id", ""),
                obj.get("group", ""),
                category,
                component_groups,
                pre,
                post,
                obj.get("post_special", ""),
            ))

print("CONSTRUCTION_FILES")
print(" ".join(sorted(p.name for p in root.glob("*.json"))))
print("INTENT_COUNTS", dict(sorted(summary.items())))
print("PER_FILE")
for name in sorted(by_file):
    print(name, dict(sorted(by_file[name].items())))
print("UNTAGGED")
for row in untagged:
    print("\t".join(str(value) for value in row))
print("UNTAGGED_COUNT", len(untagged))
