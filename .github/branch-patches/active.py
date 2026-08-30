from pathlib import Path
import json
from collections import defaultdict

root = Path("data/json/construction")
groups = defaultdict(list)
suspicious_build = []
suspicious_place = []
context_without_precondition = []

for path in sorted(root.glob("*.json")):
    data = json.loads(path.read_text())
    for obj in data:
        if not isinstance(obj, dict) or obj.get("type") != "construction":
            continue
        ident = obj.get("id", "")
        group = obj.get("group", "")
        intent = obj["ui_intent"]
        components = obj.get("components", [])
        comp_groups = len(components) if isinstance(components, list) else 0
        groups[group].append((intent, path.name, ident, obj.get("pre_terrain", ""), obj.get("post_terrain", "")))

        if intent == "build":
            low = f"{ident} {group}".lower()
            suspect_tokens = (
                "place_", "paint_", "repair_", "remove_", "seal_", "mark_",
                "dig_", "fill_", "clear_", "extract_", "cut_", "mine_",
                "jackhammer_", "wax_", "reinforce_", "install_", "take_paint",
                "cover_", "reveal_", "hang_", "finish_", "upgrade_",
            )
            if any(token in low for token in suspect_tokens) or not obj.get("post_terrain", ""):
                suspicious_build.append((path.name, ident, group, comp_groups,
                                         obj.get("pre_terrain", obj.get("pre_flags", "")),
                                         obj.get("post_terrain", ""), obj.get("post_special", "")))
        elif intent == "place":
            if comp_groups != 1:
                suspicious_place.append((path.name, ident, group, comp_groups))
        elif intent in {"repair", "finish", "modify", "upgrade", "terrain_work", "decorate"}:
            if not obj.get("pre_terrain") and not obj.get("pre_flags") and not obj.get("pre_special"):
                context_without_precondition.append((path.name, ident, group, intent))

print("SUSPICIOUS_BUILD")
for row in suspicious_build:
    print("\t".join(str(v) for v in row))
print("SUSPICIOUS_BUILD_COUNT", len(suspicious_build))
print("SUSPICIOUS_PLACE")
for row in suspicious_place:
    print("\t".join(str(v) for v in row))
print("SUSPICIOUS_PLACE_COUNT", len(suspicious_place))
print("CONTEXT_WITHOUT_PRECONDITION")
for row in context_without_precondition:
    print("\t".join(str(v) for v in row))
print("CONTEXT_WITHOUT_PRECONDITION_COUNT", len(context_without_precondition))
print("MIXED_INTENT_GROUPS")
for group, rows in sorted(groups.items()):
    intents = sorted({row[0] for row in rows})
    if len(intents) > 1:
        print(group, intents)
        for row in rows:
            print("  ", "\t".join(str(v) for v in row))
