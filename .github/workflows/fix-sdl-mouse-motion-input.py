from pathlib import Path

path = Path('src/sdltiles.cpp')
text = path.read_text()

old = '''                    // Only monitor motion when cursor is visible\n                    last_input = input_event( MouseInput::Move, input_event_t::mouse );\n'''
new = '''                    // Mouse motion is advisory/hover input.  CheckMessages drains the\n                    // entire SDL queue into last_input, so an unconditional assignment\n                    // here can erase a keyboard/button event that was already polled in\n                    // the same batch (notably Esc while the mouse is moving).  Motion\n                    // may provide an input only when no actionable event has been\n                    // captured yet; later keyboard/buttons still override the motion.\n                    if( last_input.type == input_event_t::error ) {\n                        last_input = input_event( MouseInput::Move, input_event_t::mouse );\n                    }\n'''
count = text.count(old)
if count != 1:
    raise SystemExit(f'mouse motion assignment: expected 1 match, got {count}')
text = text.replace(old, new, 1)

assert 'if( last_input.type == input_event_t::error ) {\n                        last_input = input_event( MouseInput::Move' in text
path.write_text(text)
print('made SDL mouse motion non-destructive to already captured input')
