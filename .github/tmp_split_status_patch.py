from pathlib import Path

path = Path('src/advanced_inv.cpp')
text = path.read_text()

old_discrete = '''        spane.target_item_after_recalc = sitem->items.front();
        if( split_recalc_guard ) {
            redraw_pane( left );
            redraw_pane( right );
            redraw_sidebar();
            recalc = false;
        }
        set_workspace_status( string_format( _( "Separated %1$d of %2$d %3$s into its own persistent stack." ),
                                             amount, available, source->type_name( amount ) ) );
'''
new_discrete = '''        spane.target_item_after_recalc = sitem->items.front();
        set_workspace_status( string_format( _( "Separated %1$d of %2$d %3$s into its own persistent stack." ),
                                             amount, available, source->type_name( amount ) ) );
        if( split_recalc_guard ) {
            redraw_pane( left );
            redraw_pane( right );
            redraw_sidebar();
            recalc = false;
        }
'''

old_charge = '''    spane.target_item_after_recalc = inserted;
    if( split_recalc_guard ) {
        redraw_pane( left );
        redraw_pane( right );
        redraw_sidebar();
        recalc = false;
    }
    set_workspace_status( string_format( _( "Created a separate stack of %1$d %2$s; %3$d remain." ),
                                         amount, source->type_name( amount ), source->charges ) );
'''
new_charge = '''    spane.target_item_after_recalc = inserted;
    set_workspace_status( string_format( _( "Created a separate stack of %1$d %2$s; %3$d remain." ),
                                         amount, source->type_name( amount ), source->charges ) );
    if( split_recalc_guard ) {
        redraw_pane( left );
        redraw_pane( right );
        redraw_sidebar();
        recalc = false;
    }
'''

if text.count(old_discrete) != 1:
    raise SystemExit(f'discrete status block count={text.count(old_discrete)}')
if text.count(old_charge) != 1:
    raise SystemExit(f'charge status block count={text.count(old_charge)}')

text = text.replace(old_discrete, new_discrete, 1)
text = text.replace(old_charge, new_charge, 1)
path.write_text(text)
