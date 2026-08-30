from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))


def annotate_group_named(path: str, group: str, intent: str, action: str, name: str) -> None:
    p = Path(path)
    text = p.read_text()
    needle = f'    "group": "{group}",\n'
    count = text.count(needle)
    if count < 1:
        raise RuntimeError(f"{path}: expected at least one {group} definition")
    replacement = (
        needle
        + f'    "ui_intent": "{intent}",\n'
        + f'    "ui_action": "{action}",\n'
        + f'    "ui_name": "{name}",\n'
    )
    p.write_text(text.replace(needle, replacement))


# Digging is one player verb.  Soil/sand/clay/gravel, deepening an existing
# shallow pit, and mining through rock remain separate simulation recipes, but
# the clicked tile chooses the applicable backend automatically.
annotate_group_named(
    "data/json/construction/terrain.json",
    "dig_a_shallow_pit",
    "terrain_work",
    "dig",
    "Dig"
)
annotate_group_named(
    "data/json/construction/terrain.json",
    "dig_a_pit",
    "terrain_work",
    "dig",
    "Dig"
)

# Graves share the historical shallow-pit group but are not the same player
# intent.  Keep their special behavior and expose it explicitly as Exhume grave.
for constr_id in ( "constr_exhume", "constr_exhume_new" ):
    path = Path("data/json/construction/terrain.json")
    text = path.read_text()
    old = (
        f'    "id": "{constr_id}",\n'
        '    "skill": "survival",\n'
        '    "group": "dig_a_shallow_pit",\n'
        '    "ui_intent": "terrain_work",\n'
        '    "ui_action": "dig",\n'
        '    "ui_name": "Dig",\n'
    )
    new = (
        f'    "id": "{constr_id}",\n'
        '    "skill": "survival",\n'
        '    "group": "dig_a_shallow_pit",\n'
        '    "ui_intent": "terrain_work",\n'
        '    "ui_action": "exhume_grave",\n'
        '    "ui_name": "Exhume grave",\n'
    )
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"terrain.json: expected one annotated {constr_id}, found {count}")
    path.write_text(text.replace(old, new, 1))

# A peephole is an optional modification of an already-built door, not the last
# hidden stage of the Build wooden/metal door catalog result.  Both backends
# intentionally merge into one contextual action.
for constr_id, group in (
    ( "constr_door_peep", "build_door" ),
    ( "constr_door_metal_peep", "build_metal_door" ),
):
    path = Path("data/json/construction/doors.json")
    text = path.read_text()
    old = f'    "id": "{constr_id}",\n    "group": "{group}",\n'
    new = (
        old
        + '    "ui_intent": "modify",\n'
        + '    "ui_action": "install_peephole",\n'
        + '    "ui_name": "Install peephole",\n'
    )
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"doors.json: expected one {constr_id}, found {count}")
    path.write_text(text.replace(old, new, 1))

# Wooden shutters likewise modify a window that already exists.  Keep this
# narrow rather than classifying the entire mixed REINFORCE category.
path = Path("data/json/construction/windows.json")
text = path.read_text()
old = '    "id": "constr_window_boarded_shutters",\n    "group": "wooden_shutters",\n'
new = (
    old
    + '    "ui_intent": "upgrade",\n'
    + '    "ui_action": "install_window_shutters",\n'
    + '    "ui_name": "Install wooden shutters",\n'
)
count = text.count(old)
if count != 1:
    raise RuntimeError(f"windows.json: expected one shutter construction, found {count}")
path.write_text(text.replace(old, new, 1))

Path("/tmp/branch_patch_commit_message").write_text(
    "Make digging and small structural upgrades contextual [skip ci]\n"
)
