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
    '''                            refuel_info->stage = refuel_stage::source;\n                            refuel_info->source_pos = 0;\n                            refuel_info->source_range_anchor = -1;\n''',
    '''                            refuel_info->stage = refuel_stage::source;\n                            refuel_info->source_pos = 0;\n                            refuel_info->source_scroll.scroll_to_start();\n                            refuel_info->source_range_anchor = -1;\n''',
    "keyboard source stage reset",
)
replace_once(
    path,
    '''        if( id == "REFUEL_CHOOSE_SOURCES" ) {\n            refuel_info->stage = refuel_stage::source;\n            refuel_info->source_pos = 0;\n            refuel_info->source_range_anchor = -1;\n''',
    '''        if( id == "REFUEL_CHOOSE_SOURCES" ) {\n            refuel_info->stage = refuel_stage::source;\n            refuel_info->source_pos = 0;\n            refuel_info->source_scroll.scroll_to_start();\n            refuel_info->source_range_anchor = -1;\n''',
    "mouse source action reset",
)
replace_once(
    path,
    '''                refuel_info->stage = refuel_stage::source;\n                refuel_info->source_pos = 0;\n                refuel_info->source_range_anchor = -1;\n                refresh_refuel_sources( here );\n''',
    '''                refuel_info->stage = refuel_stage::source;\n                refuel_info->source_pos = 0;\n                refuel_info->source_scroll.scroll_to_start();\n                refuel_info->source_range_anchor = -1;\n                refresh_refuel_sources( here );\n''',
    "double click source stage reset",
)
replace_once(
    path,
    '''        } else if( id == "REFUEL_QUICK_FILL" ) {\n            refuel_info->stage = refuel_stage::quick_fuel;\n            refuel_info->quick_fuel_pos = 0;\n            refresh_quick_refuel_fuels( here );\n''',
    '''        } else if( id == "REFUEL_QUICK_FILL" ) {\n            refuel_info->stage = refuel_stage::quick_fuel;\n            refuel_info->quick_fuel_pos = 0;\n            refuel_info->quick_fuel_scroll.scroll_to_start();\n            refresh_quick_refuel_fuels( here );\n''',
    "quick fill stage reset",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Keep refuel scroll state explicit across stages\n", encoding="utf-8"
)
