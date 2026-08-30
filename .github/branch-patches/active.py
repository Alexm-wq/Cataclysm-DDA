from pathlib import Path
import json
import re
from collections import Counter

ROOT = Path("data/json/construction")


def top_object_spans(text: str):
    spans = []
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                spans.append((start, i + 1))
                start = None
    if depth != 0 or in_string:
        raise RuntimeError("unbalanced JSON while locating construction objects")
    return spans


def set_string_field(block: str, field: str, value: str, after: str = "group") -> str:
    lines = block.splitlines(keepends=True)
    prefix = f'    "{field}":'
    replacement = f'    "{field}": {json.dumps(value, ensure_ascii=False)},\n'
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = replacement
            return "".join(lines)

    after_prefix = f'    "{after}":'
    for i, line in enumerate(lines):
        if line.startswith(after_prefix):
            lines.insert(i + 1, replacement)
            return "".join(lines)
    raise RuntimeError(f"construction object has no top-level {after!r} field")


def component_group_count(obj):
    components = obj.get("components", [])
    return len(components) if isinstance(components, list) else 0


def classify_intent(path: Path, obj: dict) -> str:
    op = obj.get("operation", "build")
    ident = obj.get("id", "")
    group = obj.get("group", "")
    category = obj.get("category", "OTHER")
    existing = obj.get("ui_intent")

    # Simulation-level removal metadata is authoritative.  Two old scaffolding
    # recipes are corrected below to use the same explicit operation model.
    if op in {"remove", "remove_generic"}:
        return "remove"

    # Preserve the contextual classifications already audited in the previous
    # pass unless a stronger operation rule above applies.
    if existing:
        return existing

    marker_ids = {
        "constr_crafting_spot",
        "constr_firewood_source",
        "constr_practice_target",
        "constr_stooking_spot",
    }
    if ident in marker_ids:
        return "marker"

    # These actions finish/close an existing world object rather than build a
    # new catalog result from scratch.
    if ident in {"constr_coffin_c", "constr_crate_c"}:
        return "finish"

    if category == "REPAIR":
        return "repair"
    if category == "DECORATE":
        return "decorate"

    # Finished appliance items are installed from carried inventory.  Wiring
    # is an operation on an existing wall and remains contextual.
    if path.name == "appliances.json":
        if ident in {"app_wall_wiring", "app_wall_wiring_homemade"}:
            return "modify"
        return "place"

    # Genuine inventory placement recipes.  Requiring one component group is
    # deliberate: similarly named recipes that fabricate an anvil/press/etc.
    # from several materials stay in Build.
    if group.startswith("place_") and component_group_count(obj) == 1:
        return "place"
    if ident == "constr_ground_cable":
        return "place"
    if category == "BULK":
        return "place"

    # Optional transformations of existing objects belong to tile actions.
    if ident in {
        "constr_adobe_brick_wall_embrasure_removebricks",
        "constr_brick_wall_embrasure_removebricks",
        "constr_archery_target_bale",
        "constr_strconc_wall_rope",
    }:
        return "modify"

    if ident in {
        "constr_bunkbed",
        "constr_down_bunkbed",
        "convert_splitrail_to_privacy_fence",
        "constr_wall_wattle_from_fence",
    }:
        return "upgrade"

    if path.name == "windows.json":
        # Curtains/tape removal are reversible treatments of an existing
        # window.  Reinforcement itself is a structural upgrade.
        if "curtain" in ident and obj.get("pre_terrain"):
            return "modify"
        if group == "remove_tape_from_window":
            return "modify"
        if category == "REINFORCE":
            return "upgrade"

    terrain_groups = (
        "dig_",
        "mine_",
        "fill_",
        "clear_",
        "extract_",
        "cut_grass",
        "chop_tree",
        "remove_grass",
        "remove_gravel",
        "remove_rubber_mulch",
        "jackhammer_",
    )
    if group.startswith(terrain_groups):
        return "terrain_work"
    if group in {
        "construct_open_air",
        "dig_a_water_channel",
        "glass_pit",
        "spike_pit",
        "pit_straw",
        "dig_grave_and_bury_sealed_coffin",
    }:
        return "terrain_work"
    if ident in {
        "constr_grave",
        "constr_open_air",
        "constr_pit_glass",
        "constr_pit_spiked",
        "constr_pit_straw",
        "constr_water_channel",
        "constr_dig_downstair",
        "constr_mine_downstair",
        "constr_mine_upstair",
    }:
        return "terrain_work"

    # The generic reinforce category describes upgrades unless a more precise
    # reversible/window rule above already caught the definition.
    if category == "REINFORCE":
        return "upgrade"

    return "build"


def classify_section(path: Path, obj: dict, intent: str) -> str:
    name = path.name
    ident = obj.get("id", "")
    group = obj.get("group", "")

    if name == "appliances.json":
        return "infrastructure" if "wiring" in ident else "appliances"
    if name in {"bridges_docks.json", "mechanisms.json", "railroads.json", "zlvels_transition.json"}:
        return "infrastructure"
    if name in {"doors.json", "embrasures.json", "floors_indoors.json", "roofs.json", "walls.json", "windows.json"}:
        return "structures"
    if name in {"fences_gates.json", "flora.json", "terrain.json"}:
        return "outdoor"
    if name == "floors_outdoors.json":
        return "infrastructure" if "gangway" in ident else "outdoor"
    if name == "furniture_barriers.json":
        return "outdoor"
    if name in {
        "furniture_decorative.json",
        "furniture_domestic_plants.json",
        "furniture_seats.json",
        "furniture_signs.json",
        "furniture_sleep.json",
        "furniture_storage.json",
        "furniture_surfaces.json",
    }:
        if "workbench" in ident:
            return "workshop"
        if ident == "constr_stooking_spot":
            return "outdoor"
        return "furniture"
    if name in {"furniture_fireplaces.json", "furniture_tools.json"}:
        return "workshop"
    if name in {"furniture_industrial.json", "furniture_roofs.json"}:
        return "infrastructure"
    if name == "furniture_recreation.json":
        if any(token in ident for token in ("parkour", "training_dummy", "archery_target")):
            return "outdoor"
        return "furniture"
    if name == "furniture_rural.json":
        return "outdoor"
    if name == "furniture_terrains.json":
        return "infrastructure" if "scrap_bridge" in ident else "outdoor"
    if name == "manufactured.json":
        if "radio_" in ident:
            return "infrastructure"
        if "brick_oven" in ident:
            return "workshop"
        return "outdoor"
    if name == "misc.json":
        if ident == "constr_veh":
            return "other"
        return "outdoor" if intent in {"terrain_work", "marker"} else "other"
    return "other"


def rewrite_data_file(path: Path) -> Counter:
    text = path.read_text()
    replacements = []
    counts = Counter()
    for start, end in top_object_spans(text):
        block = text[start:end]
        obj = json.loads(block)
        if obj.get("type") != "construction":
            continue

        ident = obj.get("id", "")
        # These were legacy build-action removals.  Make their backend operation
        # explicit so Remove mode can resolve them without name heuristics.
        if ident in {
            "remove_scaffolding_pipe_down_above_updown",
            "remove_scaffolding_pipe_up",
        } and obj.get("operation", "build") == "build":
            block = set_string_field(block, "operation", "remove")
            obj["operation"] = "remove"

        intent = classify_intent(path, obj)
        section = classify_section(path, obj, intent)
        # Insert section first so intent remains immediately below group.
        block = set_string_field(block, "ui_section", section)
        block = set_string_field(block, "ui_intent", intent)
        replacements.append((start, end, block))
        counts[intent] += 1

    for start, end, block in reversed(replacements):
        text = text[:start] + block + text[end:]
    path.write_text(text)

    # Data sanity only: ensure the edited JSON still parses and every core
    # construction now has explicit semantics.
    data = json.loads(text)
    for obj in data:
        if isinstance(obj, dict) and obj.get("type") == "construction":
            if "ui_intent" not in obj or "ui_section" not in obj:
                raise RuntimeError(f"{path}: construction {obj.get('id')} lacks explicit UI semantics")
    return counts


# Source correction found during the semantic audit: marker was left in the
# contextual resolver switch after markers moved to their own mode.
target = Path("src/construction_target.cpp")
source = target.read_text()
old = '''                case construction_ui_intent::marker:\n                    ready_reason = _( "Ready to mark." );\n                    break;\n                case construction_ui_intent::build:\n                case construction_ui_intent::place:\n                case construction_ui_intent::marker:\n                case construction_ui_intent::remove:\n'''
new = '''                case construction_ui_intent::build:\n                case construction_ui_intent::place:\n                case construction_ui_intent::marker:\n                case construction_ui_intent::remove:\n'''
if source.count(old) != 1:
    raise RuntimeError("construction_target.cpp marker switch guard did not match exactly once")
target.write_text(source.replace(old, new, 1))

# Keep right-click action wording aligned with the inspector for the new modes.
ui = Path("src/construction_ui.cpp")
source = ui.read_text()
old = '''    if( !adjacent ) {\n        build_label = operation == construction_operation::remove ?\n                      _( "Go there and remove" ) : _( "Go there and build" );\n        build_reason = operation == construction_operation::remove ?\n                       _( "Distant removal orders are not implemented yet." ) :\n                       _( "Distant build orders are not implemented yet." );\n    }\n'''
new = '''    if( !adjacent ) {\n        build_label = operation == construction_operation::remove ? _( "Go there and remove" ) :\n                      operation == construction_operation::place ? _( "Go there and place" ) :\n                      operation == construction_operation::markers ? _( "Go there and mark" ) :\n                      _( "Go there and build" );\n        build_reason = operation == construction_operation::remove ?\n                       _( "Distant removal orders are not implemented yet." ) :\n                       operation == construction_operation::place ?\n                       _( "Distant placement orders are not implemented yet." ) :\n                       operation == construction_operation::markers ?\n                       _( "Distant marker orders are not implemented yet." ) :\n                       _( "Distant build orders are not implemented yet." );\n    }\n'''
if source.count(old) != 1:
    raise RuntimeError("construction_ui.cpp distant context wording guard did not match exactly once")
ui.write_text(source.replace(old, new, 1))

all_counts = Counter()
changed_files = 0
for path in sorted(ROOT.glob("*.json")):
    before = path.read_text()
    counts = rewrite_data_file(path)
    all_counts.update(counts)
    if path.read_text() != before:
        changed_files += 1

print("Explicit construction UI semantics:", dict(sorted(all_counts.items())))
print("Construction data files rewritten:", changed_files)
print("Construction definitions classified:", sum(all_counts.values()))

Path("/tmp/branch_patch_commit_message").write_text(
    "Classify construction UI semantics exhaustively [skip ci]\n"
)
