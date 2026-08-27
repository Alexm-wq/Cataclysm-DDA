from pathlib import Path

path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

replacements = {
    "    const auto category_summary = [&]() {\n": "    const auto category_summary = [&]() -> std::string {\n",
    "    const auto filter_summary = [&]() {\n": "    const auto filter_summary = [&]() -> std::string {\n",
    "    const auto sort_summary = [&]() {\n": "    const auto sort_summary = [&]() -> std::string {\n",
    "    const auto scope_summary = [&]() {\n": "    const auto scope_summary = [&]() -> std::string {\n",
}

for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one occurrence of {old.strip()!r}, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Fix crafting summary return types for MSVC\n", encoding="utf-8"
)
