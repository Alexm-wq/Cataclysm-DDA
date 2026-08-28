from pathlib import Path

path = Path("src/bionics_ui.cpp")
text = path.read_text()

replacements = [
    (
        '''    const bool empty = tabs[tab].rows.empty();
    const int preferred_list = std::clamp( names + 25, 44, 56 );
    const int width = std::min( TERMX, empty ? 86 : preferred_list + 51 );
''',
        '''    const bool empty = tabs[tab].rows.empty();
    // Roomy desktop layouts should use the available screen instead of forcing
    // both panes into the old compact width.  The narrow fallbacks below still
    // take over on terminals that cannot sustain a useful two-pane view.
    const int preferred_list = std::clamp( names + 32, 58, 66 );
    const int preferred_detail = 54;
    const int preferred_width = preferred_list + preferred_detail + 3;
    const int width = std::min( TERMX, empty ? 94 : preferred_width );
'''
    ),
    (
        '''    single_pane = width < 88 && height - toolbar_rows - 5 < 13;
    configure_toolbar();
    status_y = 1 + toolbar.rows_used();
    divider_y = status_y + 1;
    const int top = divider_y + 1;
    const int body_height = std::max( 0, height - top - 2 );
    stacked = width < 88 && body_height >= 13;
    single_pane = width < 88 && !stacked;
''',
        '''    const bool narrow_layout = width < 104;
    single_pane = narrow_layout && height - toolbar_rows - 5 < 13;
    configure_toolbar();
    status_y = 1 + toolbar.rows_used();
    divider_y = status_y + 1;
    const int top = divider_y + 1;
    const int body_height = std::max( 0, height - top - 2 );
    stacked = narrow_layout && body_height >= 13;
    single_pane = narrow_layout && !stacked;
'''
    ),
    (
        '''    if( !single_pane && !stacked ) {
        list_width = std::min( preferred_list, ( width - 3 ) / 2 );
        detail_origin.x = list_width + 2;
        detail_width = std::max( 0, width - detail_origin.x - 1 );
''',
        '''    if( !single_pane && !stacked ) {
        const int pane_width = std::max( 0, width - 3 );
        const int min_detail_width = 48;
        const int target_list_width = std::clamp( pane_width * 55 / 100, 52, preferred_list );
        list_width = std::min( target_list_width,
                               std::max( 1, pane_width - min_detail_width ) );
        detail_origin.x = list_width + 2;
        detail_width = std::max( 0, width - detail_origin.x - 1 );
'''
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one layout block, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text)
Path("/tmp/branch_patch_commit_message").write_text(
    "Widen bionics desktop layout [skip ci]\n"
)
