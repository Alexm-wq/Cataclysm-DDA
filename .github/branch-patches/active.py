from pathlib import Path
import json
from collections import Counter, defaultdict

root = Path("data/json/construction")
counts = Counter()
groups = defaultdict(list)
place_count = 0
context_count = 0
remove_count = 0

for path in sorted(root.glob("*.json")):
    data = json.loads(path.read_text())
    for obj in data:
        if not isinstance(obj, dict) or obj.get("type") != "construction":
            continue
        ident = obj.get("id", "")
        intent = obj.get("ui_intent")
        section = obj.get("ui_section")
        if intent is None or section is None:
            raise RuntimeError(f"{path}: {ident} lacks explicit UI semantics")
        counts[intent] += 1
        groups[obj.get("group", "")].append(obj)

        operation = obj.get("operation", "build")
        if operation in {"remove", "remove_generic"} and intent != "remove":
            raise RuntimeError(f"{path}: removal {ident} is exposed as {intent}")
        if intent == "remove":
            remove_count += 1
            if operation not in {"remove", "remove_generic"}:
                raise RuntimeError(f"{path}: {ident} is UI remove without removal operation")
        if intent == "place":
            place_count += 1
            components = obj.get("components", [])
            if len(components) != 1:
                raise RuntimeError(f"{path}: place action {ident} has {len(components)} component groups")
        if intent in {"repair", "finish", "modify", "upgrade", "terrain_work", "decorate"}:
            context_count += 1
            if not obj.get("pre_terrain") and not obj.get("pre_flags") and not obj.get("pre_special"):
                raise RuntimeError(f"{path}: contextual action {ident} has no target precondition")

# Guard the known multi-stage ordinary-window chain.  These three definitions
# must stay Build so selecting the finished window can traverse the hidden
# backend stages without exposing them as separate catalog rows.
window_chain = {
    obj.get("id"): obj.get("ui_intent")
    for obj in groups["build_window"]
    if obj.get("id") in {"constr_window_empty", "constr_window_no_curtains", "constr_window_domestic"}
}
expected_chain = {
    "constr_window_empty": "build",
    "constr_window_no_curtains": "build",
    "constr_window_domestic": "build",
}
if window_chain != expected_chain:
    raise RuntimeError(f"ordinary window build chain is discontinuous: {window_chain}")

windows = json.loads((root / "windows.json").read_text())
window_intents = {obj.get("id"): obj.get("ui_intent") for obj in windows if isinstance(obj, dict)}
for ident in ("constr_window_bars", "constr_window_bars_alarm", "constr_window_bars_frame"):
    if window_intents.get(ident) != "upgrade":
        raise RuntimeError(f"{ident} is not contextual upgrade")

zlevels = json.loads((root / "zlvels_transition.json").read_text())
z_intents = {obj.get("id"): obj.get("ui_intent") for obj in zlevels if isinstance(obj, dict)}
if z_intents.get("constr_manhole_cover") != "place":
    raise RuntimeError("manhole cover is not inventory placement")

construction_source = Path("src/construction.cpp").read_text()
required_source_fragments = (
    "carried_source_only ) {",
    "component.has( who, is_crafting_component, 1, craft_flags::none )",
    "inventory no_map_components;",
    "who.select_item_component( alternatives, 1, no_map_components",
)
for fragment in required_source_fragments:
    if fragment not in construction_source:
        raise RuntimeError(f"carried-source execution contract missing: {fragment}")

ui_source = Path("src/construction_ui.cpp").read_text()
for fragment in (
    '"CONTEXT_GROUP_DECORATE"',
    "open_context_intent_menu( *context_anchor, *context_target",
    '_( "Decorate…" )',
):
    if fragment not in ui_source:
        raise RuntimeError(f"collapsed decoration contract missing: {fragment}")

target_source = Path("src/construction_target.cpp").read_text()
marker_cases = target_source.count("case construction_ui_intent::marker:")
if marker_cases != 1:
    raise RuntimeError(f"expected one marker switch case, found {marker_cases}")

print("FINAL_INTENT_COUNTS", dict(sorted(counts.items())))
print("TOTAL", sum(counts.values()))
print("PLACE", place_count)
print("CONTEXTUAL", context_count)
print("REMOVE", remove_count)
print("WINDOW_CHAIN", window_chain)
print("SOURCE_CONTRACTS", "ok")
