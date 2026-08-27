from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text()

old_order = '''            display_editor_context_menu();\n            display_mode( here );\n            display_live_preview( here );\n'''
new_order = '''            display_editor_context_menu();\n            // Register/draw the SDL-backed Live/Split preview before refreshing the\n            // toolbar overlay.  The toolbar dropdown is painted into w_border, so\n            // refreshing it last keeps the inline menu above the live renderer\n            // without disabling or resizing the preview camera.\n            display_live_preview( here );\n            display_mode( here );\n'''
if text.count(old_order) != 1:
    raise SystemExit(f'redraw order: expected 1 match, got {text.count(old_order)}')
text = text.replace(old_order, new_order, 1)

old_guard = '''#if defined(TILES)\n    if( !open_editor_toolbar_dropdown.empty() ) {\n        live_preview_last_draw_mode.reset();\n        clear_map_preview_window();\n        return;\n    }\n    if( active_editor_view_mode == editor_view_mode::editor ) {\n'''
new_guard = '''#if defined(TILES)\n    if( active_editor_view_mode == editor_view_mode::editor ) {\n'''
if text.count(old_guard) != 1:
    raise SystemExit(f'dropdown preview guard: expected 1 match, got {text.count(old_guard)}')
text = text.replace(old_guard, new_guard, 1)

assert 'if( !open_editor_toolbar_dropdown.empty() ) {\n        live_preview_last_draw_mode.reset();\n        clear_map_preview_window();' not in text
assert 'display_live_preview( here );\n            display_mode( here );' in text
assert 'set_map_preview_window( preview, world_center, live_preview_zoom * 8 );' in text

path.write_text(text)
print('patched toolbar/live preview draw ordering')
