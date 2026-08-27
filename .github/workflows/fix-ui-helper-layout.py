from pathlib import Path

root = Path('src')
old = root / 'ui_dropdown.h'
new_dir = root / 'ui_helpers'
new = new_dir / 'dropdown.h'
veh = root / 'veh_interact.h'

if not old.exists():
    raise SystemExit('src/ui_dropdown.h missing')
if new.exists():
    raise SystemExit('src/ui_helpers/dropdown.h already exists')

text = old.read_text()

old_fields = '''struct ui_dropdown_entry {\n    std::string label;\n    std::string id;\n    bool enabled = true;\n    bool selected = false;\n    // When set, ui_dropdown renders a standard [x]/[ ] prefix.\n    // This keeps checkbox presentation consistent for reusable filter menus.\n    std::optional<bool> checked;\n    std::string disabled_reason;\n};\n'''
new_fields = '''struct ui_dropdown_entry {\n    std::string label;\n    std::string id;\n    bool enabled = true;\n    bool selected = false;\n    // Keep disabled_reason before optional extension fields so existing aggregate\n    // initializers retain their historical { label, id, enabled, selected, reason } layout.\n    std::string disabled_reason;\n    // When set, ui_dropdown renders a standard [x]/[ ] prefix.\n    // This keeps checkbox presentation consistent for reusable filter menus.\n    std::optional<bool> checked;\n};\n'''
if text.count(old_fields) != 1:
    raise SystemExit('ui_dropdown_entry field block did not match exactly')
text = text.replace(old_fields, new_fields, 1)
text = text.replace('#ifndef CATA_SRC_UI_DROPDOWN_H', '#ifndef CATA_SRC_UI_HELPERS_DROPDOWN_H', 1)
text = text.replace('#define CATA_SRC_UI_DROPDOWN_H', '#define CATA_SRC_UI_HELPERS_DROPDOWN_H', 1)
text = text.replace('#endif // CATA_SRC_UI_DROPDOWN_H', '#endif // CATA_SRC_UI_HELPERS_DROPDOWN_H', 1)

new_dir.mkdir(parents=True, exist_ok=True)
new.write_text(text)
old.unlink()

veh_text = veh.read_text()
if veh_text.count('#include "ui_dropdown.h"') != 1:
    raise SystemExit('veh_interact include did not match exactly')
veh_text = veh_text.replace('#include "ui_dropdown.h"', '#include "ui_helpers/dropdown.h"', 1)
veh.write_text(veh_text)

# Guard against the exact MSVC regression: the fifth aggregate element must still be the reason string.
new_text = new.read_text()
order = [
    new_text.index('std::string label;'),
    new_text.index('std::string id;'),
    new_text.index('bool enabled = true;'),
    new_text.index('bool selected = false;'),
    new_text.index('std::string disabled_reason;'),
    new_text.index('std::optional<bool> checked;'),
]
if order != sorted(order):
    raise SystemExit('ui_dropdown_entry compatibility field order is wrong')

print('moved dropdown helper to src/ui_helpers and restored aggregate compatibility')
