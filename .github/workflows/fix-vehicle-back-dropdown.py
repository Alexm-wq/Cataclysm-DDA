from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text()
old = '''        if( !button.enabled ) {\n            return true;\n        }\n        pending_editor_action = button.action;\n        return false;\n'''
new = '''        if( !button.enabled ) {\n            return true;\n        }\n        if( button.action == "QUIT" ) {\n            // Toolbar Back is an explicit navigation command.  Do not let the\n            // generic QUIT transient-menu handling consume it merely because a\n            // filter/context menu is open; dismiss those first and let this same\n            // click reach the normal editor/mode close path.\n            close_editor_context_menu();\n            open_editor_dropdown = editor_dropdown::none;\n        }\n        pending_editor_action = button.action;\n        return false;\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'expected one toolbar direct action block, got {count}')
path.write_text(text.replace(old, new, 1))
print('vehicle toolbar Back dropdown priority fixed')
