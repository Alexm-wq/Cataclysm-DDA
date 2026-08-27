from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/veh_interact.cpp"
replace_once(
    path,
    '''            if( parts_pos->y >= 3 ) {\n                const std::vector<int> parts = inspector_parts();\n                const int row = part_scroll.viewport_pos() + parts_pos->y - 3;\n                if( row >= 0 && row < static_cast<int>( parts.size() ) ) {\n                    selected_part = parts[row];\n''',
    '''            if( parts_pos->y >= 3 ) {\n                const std::vector<int> parts = inspector_parts();\n                const std::optional<int> row = part_scroll.index_at_viewport_row( parts_pos->y - 3 );\n                if( row && *row < static_cast<int>( parts.size() ) ) {\n                    selected_part = parts[*row];\n''',
    "inspector context row mapping",
)
replace_once(
    path,
    '''        if( !install_info && parts_pos && parts_pos->y >= 3 ) {\n            const std::vector<int> parts = inspector_parts();\n            const int row = part_scroll.viewport_pos() + parts_pos->y - 3;\n            if( row >= 0 && row < static_cast<int>( parts.size() ) ) {\n                selected_part = parts[row];\n''',
    '''        if( !install_info && parts_pos && parts_pos->y >= 3 ) {\n            const std::vector<int> parts = inspector_parts();\n            const std::optional<int> row = part_scroll.index_at_viewport_row( parts_pos->y - 3 );\n            if( row && *row < static_cast<int>( parts.size() ) ) {\n                selected_part = parts[*row];\n''',
    "inspector select row mapping",
)
replace_once(
    path,
    '''    if( pos->y >= first_row && pos->y < footer_y && visible > 0 ) {\n        const int index = reshape_info->variant_scroll.viewport_pos() + ( pos->y - first_row ) / entry_height;\n        if( index >= 0 && index < static_cast<int>( reshape_info->variants.size() ) ) {\n            const bool double_click = reshape_info->double_click.click(\n                                          reshape_info->variants[index] );\n            const int viewport_before_click = reshape_info->variant_scroll.viewport_pos();\n            preview_reshape_variant( index );\n''',
    '''    if( pos->y >= first_row && pos->y < footer_y && visible > 0 ) {\n        const std::optional<int> index = reshape_info->variant_scroll.index_at_viewport_row(\n                                             ( pos->y - first_row ) / entry_height );\n        if( index && *index < static_cast<int>( reshape_info->variants.size() ) ) {\n            const bool double_click = reshape_info->double_click.click(\n                                          reshape_info->variants[*index] );\n            const int viewport_before_click = reshape_info->variant_scroll.viewport_pos();\n            preview_reshape_variant( *index );\n''',
    "reshape helper row mapping",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Use scroll-model row mapping in vehicle lists\n", encoding="utf-8"
)
