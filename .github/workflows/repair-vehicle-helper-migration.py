from pathlib import Path
p = Path('.github/workflows/apply-vehicle-helper-migration.py')
s = p.read_text()
old = """old_anchor = '''    int anchor_x = 1;\\n    for( const editor_toolbar_button &button : editor_toolbar_buttons ) {\\n        if( button.action == which ) {\\n            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );\\n            break;\\n        }\\n    }'''"""
new = """old_anchor = '''    int anchor_x = 1;\\n    for( const ui_action_strip_item &button : editor_toolbar_buttons ) {\\n        if( button.action == which ) {\\n            anchor_x = getbegx( w_mode ) + button.pos.x - getbegx( w_border );\\n            break;\\n        }\\n    }'''"""
if s.count(old) != 1:
    raise SystemExit(f'anchor guard repair expected 1 match, found {s.count(old)}')
p.write_text(s.replace(old, new, 1))
