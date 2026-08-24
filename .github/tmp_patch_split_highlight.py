from pathlib import Path

path = Path("src/advanced_inv.cpp")
text = path.read_text()

def replace_once(old: str, new: str, label: str) -> None:
    global text
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    text = text.replace(old, new, 1)

replace_once(
'''    // Attempt to move to the target item if there is one.
    if( pane.target_item_after_recalc ) {
        for( size_t i = 0; i < pane.items.size(); i++ ) {
            if( pane.items[i].items.front() == pane.target_item_after_recalc ) {
                pane.index = i;
                pane.target_item_after_recalc = item_location::nowhere;
                break;
            }
        }
    }
''',
'''    // Attempt to move to the target item if there is one.  A restack can keep
    // the physical target in the rebuilt row without leaving it as items.front(),
    // so search the complete row and re-anchor a single selection to its new
    // representative.
    if( pane.target_item_after_recalc ) {
        const item_location target = pane.target_item_after_recalc;
        for( size_t i = 0; i < pane.items.size(); i++ ) {
            if( std::find( pane.items[i].items.begin(), pane.items[i].items.end(), target ) !=
                pane.items[i].items.end() ) {
                pane.index = i;
                const item_location representative = pane.items[i].items.front();
                auto selected = std::find( multi_selected_rows[p].begin(),
                                           multi_selected_rows[p].end(), target );
                if( selected != multi_selected_rows[p].end() ) {
                    *selected = representative;
                }
                if( selection_anchors[p] == target ) {
                    selection_anchors[p] = representative;
                }
                pane.target_item_after_recalc = item_location::nowhere;
                break;
            }
        }
    }
''',
"restore stack target row")

replace_once(
'''    const std::optional<int> requested = test_mode ?
            std::optional<int>( std::max( 1, available / 2 ) ) :
            query_separate_stack_amount( source->tname(), available );
''',
'''    // Keep the inventory frame blocked until the split mutation and pane-recalc
    // flags are complete.  Otherwise closing the amount popup can briefly expose
    // the pre-split frame before the new stack state is ready.
    std::unique_ptr<ui_adaptor> split_recalc_guard;
    if( !test_mode ) {
        split_recalc_guard = std::make_unique<ui_adaptor>( ui_adaptor::disable_uis_below{} );
    }
    const std::optional<int> requested = test_mode ?
            std::optional<int>( std::max( 1, available / 2 ) ) :
            query_separate_stack_amount( source->tname(), available );
''',
"split redraw guard")

path.write_text(text)
