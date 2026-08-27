from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: str, start: str, end: str, replacement: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(start) != 1:
        raise SystemExit(f"{label}: expected 1 start anchor, found {text.count(start)}")
    begin = text.index(start)
    finish = text.find(end, begin + len(start))
    if finish < 0:
        raise SystemExit(f"{label}: end anchor not found")
    p.write_text(text[:begin] + replacement + text[finish:], encoding="utf-8")


# Keep the transient-control dismissal rule in one renderer-independent helper so
# dropdown and tree-dropdown callers cannot drift into subtly different behavior.
replace_once(
    "src/ui_helpers/models/action_entry.h",
    '''enum class ui_outside_click_policy : int {\n    consume,\n    passthrough\n};\n\n''',
    '''enum class ui_outside_click_policy : int {\n    consume,\n    passthrough\n};\n\ninline bool ui_outside_pointer_passthrough( const ui_outside_click_policy policy,\n        const bool over_trigger )\n{\n    return policy == ui_outside_click_policy::passthrough && !over_trigger;\n}\n\n''',
    "shared outside pointer policy",
)

for path in ("src/ui_helpers/controls/dropdown.h", "src/ui_helpers/controls/tree_dropdown.h"):
    replace_once(
        path,
        '''            const bool passthrough_policy = outside_click == ui_outside_click_policy::passthrough;\n            const bool over_trigger = parent_pos && trigger_bounds && trigger_bounds->contains( *parent_pos );\n            const bool pass_outside = passthrough_policy && !over_trigger;\n''',
        '''            const bool passthrough_policy = outside_click == ui_outside_click_policy::passthrough;\n            const bool over_trigger = parent_pos && trigger_bounds && trigger_bounds->contains( *parent_pos );\n            const bool pass_outside = ui_outside_pointer_passthrough( outside_click, over_trigger );\n''',
        f"shared outside pointer policy use in {path}",
    )

# Checkbox/toggle affordances are controls in their own right; avoid decorating them
# as nested brackets such as "[ [x] Materials ]" when used by an action strip.
replace_once(
    "src/ui_helpers/controls/action_strip.h",
    '''            std::string label = entry.checked.has_value() ?\n                                string_format( *entry.checked ? "[x] %s" : "[ ] %s", entry.label ) :\n                                entry.label;\n            if( entry.dropdown ) {\n                label += " ▼";\n            }\n            if( style.decorate ) {\n                label = string_format( "[ %s ]", label );\n            }\n''',
    '''            std::string label = entry.checked.has_value() ?\n                                string_format( *entry.checked ? "[x] %s" : "[ ] %s", entry.label ) :\n                                entry.label;\n            if( entry.dropdown ) {\n                label += " ▼";\n            }\n            if( style.decorate && !entry.checked.has_value() ) {\n                label = string_format( "[ %s ]", label );\n            }\n''',
    "action strip checkbox decoration",
)

replace_once(
    "tests/ui_helpers_test.cpp",
    '''TEST_CASE( "ui_transient_control_can_close_with_pointer_passthrough", "[ui][ui_helpers]" )\n{\n    const ui_action_result consumed_close{ ui_action_result_type::closed, std::nullopt };\n    const ui_action_result passthrough_close{ ui_action_result_type::closed, std::nullopt, true };\n\n    CHECK( consumed_close.consumed() );\n    CHECK_FALSE( consumed_close.passes_through() );\n    CHECK_FALSE( passthrough_close.consumed() );\n    CHECK( passthrough_close.passes_through() );\n}\n\n''',
    '''TEST_CASE( "ui_transient_control_can_close_with_pointer_passthrough", "[ui][ui_helpers]" )\n{\n    const ui_action_result consumed_close{ ui_action_result_type::closed, std::nullopt };\n    const ui_action_result passthrough_close{ ui_action_result_type::closed, std::nullopt, true };\n\n    CHECK( consumed_close.consumed() );\n    CHECK_FALSE( consumed_close.passes_through() );\n    CHECK_FALSE( passthrough_close.consumed() );\n    CHECK( passthrough_close.passes_through() );\n\n    CHECK_FALSE( ui_outside_pointer_passthrough( ui_outside_click_policy::consume, false ) );\n    CHECK_FALSE( ui_outside_pointer_passthrough( ui_outside_click_policy::passthrough, true ) );\n    CHECK( ui_outside_pointer_passthrough( ui_outside_click_policy::passthrough, false ) );\n}\n\n''',
    "outside pointer policy test",
)
replace_once(
    "tests/ui_helpers_test.cpp",
    '''    CHECK( ui_action_strip::format_label( plain ) == "[ Filter ]" );\n    CHECK( ui_action_strip::format_label( dropdown ) == "[ Filter ▼ ]" );\n}\n\n''',
    '''    CHECK( ui_action_strip::format_label( plain ) == "[ Filter ]" );\n    CHECK( ui_action_strip::format_label( dropdown ) == "[ Filter ▼ ]" );\n    CHECK( ui_action_strip::format_label( ui_action_entry( "Materials", "MATERIALS", true, false,\n            std::string(), true ) ) == "[x] Materials" );\n}\n\n''',
    "action strip checkbox affordance test",
)

# Crafting owns the search field's placement/width.  Keep the helper behavior but
# make the field materially smaller so it no longer dominates the header.
replace_once(
    "src/crafting_gui.cpp",
    '''        const int search_width = std::min( browser_width - 4,\n                                           std::clamp( browser_width / 3, 28, 48 ) );\n''',
    '''        const int search_width = std::min( browser_width - 4,\n                                           std::clamp( browser_width / 4, 22, 36 ) );\n''',
    "crafting search width",
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Tighten shared UI controls for crafting\n", encoding="utf-8"
)
