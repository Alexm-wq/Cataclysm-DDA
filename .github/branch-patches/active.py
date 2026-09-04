from pathlib import Path

src = Path("src/construction_ui.cpp")
text = src.read_text(encoding="utf-8")
old = '''    if( operation == construction_operation::remove ) {
        search_field.clear();
        palette_actions.clear();
        palette.invalidate_geometry();
#if defined(TILES)
        clear_ui_tile_previews();
#endif
        trim_and_print( palette_window, point( 2, 2 ), palette_width - 4, c_light_green,
                        _( "Select a tile on the map." ) );
        fold_and_print( palette_window, point( 2, 4 ), palette_width - 4, c_light_gray,
                        _( "Remove resolves the correct dismantle or removal action from the selected terrain or furniture." ) );
        if( const std::optional<tripoint_bub_ms> target = displayed_target() ) {
            const std::string existing = here.has_furn( *target ) ? here.furn( *target )->name() :
                                         here.ter( *target )->name();
            trim_and_print( palette_window, point( 2, 8 ), palette_width - 4, c_light_cyan,
                            string_format( _( "Target: %s" ), existing ) );
        }
        wnoutrefresh( palette_window );
        return;
    }

'''
if text.count(old) != 1:
    raise RuntimeError(f"dead Remove palette branch: expected one match, found {text.count(old)}")
text = text.replace(old, "", 1)
src.write_text(text, encoding="utf-8")

doc_path = Path("doc/UI_MODERNIZATION_PLANS/CONSTRUCTION_UI_IMPLEMENTATION_PLAN.md")
doc = doc_path.read_text(encoding="utf-8")
old = '''### 13.2 Adjacent executable target

If the character can work there immediately, expose:

```text
[ Build here ]
```

This should enter the same normal construction flow currently used after the adjacent-tile selector.

### 13.3 Distant executable target

If a target is valid but the character is not adjacent, expose an explicit action such as:

```text
[ Go there and build ]
```

This distinction is essential. A map click is selection; the explicit action is an execution order.
'''
new = '''### 13.2 Adjacent executable target

With an active construction selected, LMB starts the normal construction flow immediately.  A deliberately
pinned/inspected target may also expose `Build here` in the inspector as an alternate explicit action.

### 13.3 Distant executable target

With an active construction selected, LMB issues the route-to-site order and construction starts automatically
after arrival.  A deliberately pinned/inspected target may expose `Go there and build` in the inspector.

The map click and inspector action must enter the same validated execution path; the inspector is not a required
second confirmation.
'''
if doc.count(old) != 1:
    raise RuntimeError(f"stale build contract: expected one match, found {doc.count(old)}")
doc = doc.replace(old, new, 1)
doc_path.write_text(doc, encoding="utf-8")

Path("/tmp/branch_patch_commit_message").write_text(
    "Clean up construction interaction remnants\n", encoding="utf-8"
)
