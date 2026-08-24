from pathlib import Path

path = Path('src/advanced_inv.cpp')
text = path.read_text()

old = '''        recalc = true;\n        panes[left].recalc = true;\n        panes[right].recalc = true;\n        spane.target_item_after_recalc = sitem->items.front();\n        set_workspace_status( string_format( _( \"Separated %1$d of %2$d %3$s into its own persistent stack.\" ),\n'''
new = '''        recalc = true;\n        panes[left].recalc = true;\n        panes[right].recalc = true;\n        spane.target_item_after_recalc = sitem->items.front();\n        if( split_recalc_guard ) {\n            redraw_pane( left );\n            redraw_pane( right );\n            redraw_sidebar();\n            recalc = false;\n        }\n        set_workspace_status( string_format( _( \"Separated %1$d of %2$d %3$s into its own persistent stack.\" ),\n'''
if text.count(old) != 1:
    raise SystemExit(f'discrete split match count={text.count(old)}')
text = text.replace(old, new, 1)

old = '''    recalc = true;\n    panes[left].recalc = true;\n    panes[right].recalc = true;\n    spane.target_item_after_recalc = inserted;\n    set_workspace_status( string_format( _( \"Created a separate stack of %1$d %2$s; %3$d remain.\" ),\n'''
new = '''    recalc = true;\n    panes[left].recalc = true;\n    panes[right].recalc = true;\n    spane.target_item_after_recalc = inserted;\n    if( split_recalc_guard ) {\n        redraw_pane( left );\n        redraw_pane( right );\n        redraw_sidebar();\n        recalc = false;\n    }\n    set_workspace_status( string_format( _( \"Created a separate stack of %1$d %2$s; %3$d remain.\" ),\n'''
if text.count(old) != 1:
    raise SystemExit(f'charge split match count={text.count(old)}')
text = text.replace(old, new, 1)

path.write_text(text)
