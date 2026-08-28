from pathlib import Path

path = Path("src/sdltiles.cpp")
text = path.read_text(encoding="utf-8")
old = "static Font_Ptr font;\nstatic Font_Ptr font;\n"
if text.count(old) != 1:
    raise SystemExit(f"expected one duplicated font declaration, found {text.count(old)}")
path.write_text(text.replace(old, "static Font_Ptr font;\n", 1), encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Fix geometry-layer HUD font declaration\n", encoding="utf-8"
)
