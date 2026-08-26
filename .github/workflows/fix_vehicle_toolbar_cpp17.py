from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text(encoding='utf-8')
replacements = {
    'entry.action.starts_with( "TOOLBAR_MENU_" )': 'entry.action.rfind( "TOOLBAR_MENU_", 0 ) == 0',
    '!button.action.starts_with( "TOOLBAR_MENU_" )': 'button.action.rfind( "TOOLBAR_MENU_", 0 ) != 0',
    'button.action.starts_with( "TOOLBAR_MENU_" )': 'button.action.rfind( "TOOLBAR_MENU_", 0 ) == 0',
}
for old, new in replacements.items():
    count = text.count(old)
    if count == 0:
        raise SystemExit(f'expected pattern not found: {old}')
    text = text.replace(old, new)

if '.starts_with(' in text:
    raise SystemExit('starts_with remains in veh_interact.cpp')
path.write_text(text, encoding='utf-8')
