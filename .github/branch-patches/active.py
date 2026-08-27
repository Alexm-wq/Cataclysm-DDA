from pathlib import Path

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

old = '''                                state.batch_size, fold_width, avail->color( true ), crafting_group );\n'''
new = '''                                state.batch_size, fold_width, avail->color( true ), crafting_characters );\n'''
if text.count(old) != 1:
    raise SystemExit(f"cached recipe info crafter vector: expected 1, found {text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix crafting inspector crafter vector argument\n", encoding="utf-8"
)
