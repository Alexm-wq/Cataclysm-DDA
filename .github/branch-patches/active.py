from pathlib import Path

path = Path("src/sdltiles.cpp")
text = path.read_text(encoding="utf-8")
old = "void refresh_display()\nvoid refresh_display()\n{\n"
new = "void refresh_display()\n{\n"
if text.count(old) != 1:
    raise SystemExit(f"expected one duplicated refresh_display declaration, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix duplicate refresh_display declaration\n", encoding="utf-8"
)
