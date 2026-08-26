from pathlib import Path

p = Path('src/veh_interact.cpp')
s = p.read_text()

def rep(old, new, label):
    global s
    c = s.count(old)
    if c != 1:
        raise SystemExit(f'{label}: expected 1 match, got {c}')
    s = s.replace(old, new, 1)

rep(
'''    int tank_range_anchor = -1;\n    int last_clicked_tank_index = -1;\n    std::optional<std::chrono::steady_clock::time_point> last_tank_click_time;\n''',
'''    int tank_range_anchor = -1;\n''',
'remove target double-click state')

rep(
'''                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range   Double-click = continue" ) );\n''',
'''                        _( "Click = select one   Ctrl+click = toggle   Shift+click = range" ) );\n''',
'remove target double-click hint')

rep(
'''                msg = _( "That fuel store is already full or cannot currently be refilled." );\n                refuel_info->last_clicked_tank_index = -1;\n                refuel_info->last_tank_click_time.reset();\n                return true;\n''',
'''                msg = _( "That fuel store is already full or cannot currently be refilled." );\n                return true;\n''',
'remove invalid target double-click reset')

rep(
'''            const input_event raw = main_context.get_raw_input();\n            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;\n            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;\n            const auto now = std::chrono::steady_clock::now();\n            const bool double_click = !ctrl && !shift &&\n                                      refuel_info->last_clicked_tank_index == slot &&\n                                      refuel_info->last_tank_click_time &&\n                                      now - *refuel_info->last_tank_click_time <= std::chrono::milliseconds( 500 );\n\n''',
'''            const input_event raw = main_context.get_raw_input();\n            const bool ctrl = raw.modifiers.count( keymod_t::ctrl ) != 0;\n            const bool shift = raw.modifiers.count( keymod_t::shift ) != 0;\n\n''',
'target click has selection semantics only')

rep(
'''            if( double_click ) {\n                refuel_info->last_clicked_tank_index = -1;\n                refuel_info->last_tank_click_time.reset();\n                refuel_info->stage = refuel_stage::source;\n                refuel_info->source_pos = 0;\n                refuel_info->source_range_anchor = -1;\n                refresh_refuel_sources( here );\n            } else if( !ctrl && !shift ) {\n                refuel_info->last_clicked_tank_index = slot;\n                refuel_info->last_tank_click_time = now;\n            } else {\n                refuel_info->last_clicked_tank_index = -1;\n                refuel_info->last_tank_click_time.reset();\n            }\n            return true;\n''',
'''            // Tank-row clicks only modify target selection.  Advancing to fuel\n            // sources is explicit via the button or keyboard confirm, so a rapid\n            // second click can never consume or collapse a multi-selection.\n            return true;\n''',
'remove target auto-advance')

# Compatibility for the preview should be based on whether any selected source
# of the validated common fuel can refill the target, not whichever row happens
# to be first in the selected-source vector.
rep(
'''        preview.compatible = refill_source_compatible( part,\n                             refuel_info->sources[selected_sources.front()].location );\n        preview.capacity = preview.compatible ? part.item_capacity( *fuel_type ) : 0;\n''',
'''        preview.compatible = std::any_of( selected_sources.begin(), selected_sources.end(),\n        [&]( const int source_index ) {\n            return refill_source_compatible( part, refuel_info->sources[source_index].location );\n        } );\n        preview.capacity = preview.compatible ? part.item_capacity( *fuel_type ) : 0;\n''',
'preview compatibility across selected sources')

p.write_text(s)
