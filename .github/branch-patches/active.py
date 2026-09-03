from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''        void configure( const catacurses::window &parent, point pos,\n                        std::vector<ui_dropdown_entry> entries,\n                        int requested_width = 0,\n                        const ui_dropdown_style &style = ui_dropdown_style() ) {''',
    '''        void configure( const catacurses::window &parent, point pos,\n                        std::vector<ui_dropdown_entry> entries,\n                        int requested_width = 0,\n                        const ui_dropdown_style &style = ui_dropdown_style(),\n                        int maximum_visible_rows = 0 ) {'''
)

replace_once(
    "src/ui_helpers/controls/dropdown.h",
    '''            height_ = std::min( static_cast<int>( entries_.size() ) + 2, parent_height );\n            if( height_ < 3 ) {''',
    '''            height_ = std::min( static_cast<int>( entries_.size() ) + 2, parent_height );\n            if( maximum_visible_rows > 0 ) {\n                height_ = std::min( height_, maximum_visible_rows + 2 );\n            }\n            if( height_ < 3 ) {'''
)

replace_once(
    "src/game.cpp",
    '''    std::map<std::string, int> container_name_totals;\n    for( const item_location &container : context_containers ) {\n        if( container ) {\n            ++container_name_totals[container->tname()];\n        }\n    }\n    std::map<std::string, int> container_name_seen;\n    std::unordered_map<std::string, size_t> container_actions;\n    for( size_t i = 0; i < context_containers.size(); ++i ) {\n        const item_location &container = context_containers[i];\n        if( !container ) {\n            continue;\n        }\n        const std::string name = container->tname();\n        std::string label = string_format( _( "Open %s" ), name );\n        if( container_name_totals[name] > 1 ) {\n            label = string_format( _( "Open %1$s (%2$d)" ), name, ++container_name_seen[name] );\n        }''',
    '''    // Context labels identify the container itself, not a verbose rendering of\n    // its contents.  Keep every physical item separate, but make crowded tiles readable.\n    std::map<std::string, int> container_name_totals;\n    for( const item_location &container : context_containers ) {\n        if( container ) {\n            ++container_name_totals[container->tname( 1, tname::item_identity_name )];\n        }\n    }\n    std::map<std::string, int> container_name_seen;\n    std::unordered_map<std::string, size_t> container_actions;\n    for( size_t i = 0; i < context_containers.size(); ++i ) {\n        const item_location &container = context_containers[i];\n        if( !container ) {\n            continue;\n        }\n        const std::string name = container->tname( 1, tname::item_identity_name );\n        std::string label = string_format( _( "Open %s" ), name );\n        if( container_name_totals[name] > 1 ) {\n            const int occurrence = ++container_name_seen[name];\n            label = string_format( _( "Open %1$s (%2$d/%3$d)" ), name, occurrence,\n                                   container_name_totals[name] );\n        }'''
)

replace_once(
    "src/game.cpp",
    '''        context_menu.configure( catacurses::stdscr, menu_anchor, entries, 0, style );''',
    '''        // Context menus should remain compact even when a tile contains dozens of\n        // individually addressable containers.  The shared dropdown scroll model keeps\n        // every entry reachable without allowing the popup to consume the whole screen.\n        context_menu.configure( catacurses::stdscr, menu_anchor, entries, 0, style, 10 );'''
)

Path("/tmp/branch_patch_commit_message").write_text("Keep crowded world context menus compact\n")
print("compact context container labels and scroll cap patched")
