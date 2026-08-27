from pathlib import Path

cpp_path = Path('src/veh_interact.cpp')
h_path = Path('src/veh_interact.h')
cpp = cpp_path.read_text()
h = h_path.read_text()


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    return text.replace(old, new, 1)


def replace_all(text, old, new, label, minimum=1):
    count = text.count(old)
    if count < minimum:
        raise SystemExit(f'{label}: expected at least {minimum} matches, got {count}')
    return text.replace(old, new)


def function_end(text, signature):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'function not found: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'opening brace not found: {signature}')
    depth = 0
    in_string = False
    in_char = False
    escape = False
    i = brace
    while i < len(text):
        ch = text[i]
        if escape:
            escape = False
        elif ch == '\\' and (in_string or in_char):
            escape = True
        elif ch == '"' and not in_char:
            in_string = not in_string
        elif ch == "'" and not in_string:
            in_char = not in_char
        elif not in_string and not in_char:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return start, i + 1
        i += 1
    raise SystemExit(f'unterminated function: {signature}')


def replace_function(text, signature, replacement):
    start, end = function_end(text, signature)
    return text[:start] + replacement.rstrip() + text[end:]


def insert_after_function(text, signature, addition):
    _, end = function_end(text, signature)
    return text[:end] + '\n\n' + addition.rstrip() + text[end:]

# Header: sets are the canonical multi-select state.  `all` stays a synthetic UI row.
h = replace_once(h, '#include <optional>\n#include <string>\n',
                 '#include <optional>\n#include <set>\n#include <string>\n', 'add set include')

h = replace_once(h,
'''        editor_layer active_editor_layer = editor_layer::composite;\n        editor_system_filter active_system_filter = editor_system_filter::all;\n        editor_condition_filter active_condition_filter = editor_condition_filter::all;\n        editor_dropdown open_editor_dropdown = editor_dropdown::none;\n''',
'''        editor_layer active_editor_layer = editor_layer::composite;\n        // Multi-select filters store only concrete categories.  The synthetic\n        // "All" row is checked exactly when every concrete category is selected.\n        std::set<editor_system_filter> active_system_filters = {\n            editor_system_filter::structural, editor_system_filter::propulsion,\n            editor_system_filter::fuel, editor_system_filter::electrical,\n            editor_system_filter::storage, editor_system_filter::controls,\n            editor_system_filter::passenger, editor_system_filter::lighting,\n            editor_system_filter::utility, editor_system_filter::turrets,\n            editor_system_filter::combat, editor_system_filter::other\n        };\n        std::set<editor_condition_filter> active_condition_filters = {\n            editor_condition_filter::healthy, editor_condition_filter::damaged,\n            editor_condition_filter::broken, editor_condition_filter::replacement\n        };\n        editor_dropdown open_editor_dropdown = editor_dropdown::none;\n''', 'replace single filter state')

h = replace_once(h,
'''        bool part_matches_system( const vehicle_part &vp ) const;\n        bool part_matches_condition( const vehicle_part &vp ) const;\n        std::string editor_layer_name( editor_layer layer ) const;\n''',
'''        bool part_matches_system( const vehicle_part &vp ) const;\n        bool part_matches_condition( const vehicle_part &vp ) const;\n        bool all_system_filters_selected() const;\n        bool all_condition_filters_selected() const;\n        bool system_filter_selected( editor_system_filter filter ) const;\n        bool condition_filter_selected( editor_condition_filter filter ) const;\n        void toggle_editor_filter( editor_dropdown which, int option );\n        std::string editor_system_filter_summary() const;\n        std::string editor_condition_filter_summary() const;\n        std::string editor_layer_name( editor_layer layer ) const;\n''', 'declare multiselect helpers')

cpp = replace_function(cpp, 'bool veh_interact::part_matches_system( const vehicle_part &vp ) const', r'''bool veh_interact::part_matches_system( const vehicle_part &vp ) const
{
    return active_system_filters.count( primary_system_for_part( vp ) ) > 0;
}''')

cpp = replace_function(cpp, 'bool veh_interact::part_matches_condition( const vehicle_part &vp ) const', r'''bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
{
    const double health = vp.health_percent();
    const bool destroyed = vp.is_broken();

    editor_condition_filter condition = editor_condition_filter::healthy;
    if( destroyed && !vp.is_repairable() ) {
        condition = editor_condition_filter::replacement;
    } else if( destroyed ) {
        condition = editor_condition_filter::broken;
    } else if( health < 0.999 ) {
        condition = editor_condition_filter::damaged;
    }
    return active_condition_filters.count( condition ) > 0;
}''')

helpers = r'''bool veh_interact::all_system_filters_selected() const
{
    return active_system_filters.size() == static_cast<std::size_t>( editor_system_filter::other );
}

bool veh_interact::all_condition_filters_selected() const
{
    return active_condition_filters.size() ==
           static_cast<std::size_t>( editor_condition_filter::replacement );
}

bool veh_interact::system_filter_selected( const editor_system_filter filter ) const
{
    return filter == editor_system_filter::all ? all_system_filters_selected() :
           active_system_filters.count( filter ) > 0;
}

bool veh_interact::condition_filter_selected( const editor_condition_filter filter ) const
{
    return filter == editor_condition_filter::all ? all_condition_filters_selected() :
           active_condition_filters.count( filter ) > 0;
}

void veh_interact::toggle_editor_filter( const editor_dropdown which, const int option )
{
    if( which == editor_dropdown::system ) {
        if( option < 0 || option > static_cast<int>( editor_system_filter::other ) ) {
            return;
        }
        const editor_system_filter filter = static_cast<editor_system_filter>( option );
        if( filter == editor_system_filter::all ) {
            if( all_system_filters_selected() ) {
                active_system_filters.clear();
            } else {
                active_system_filters.clear();
                for( int i = 1; i <= static_cast<int>( editor_system_filter::other ); ++i ) {
                    active_system_filters.insert( static_cast<editor_system_filter>( i ) );
                }
            }
        } else if( active_system_filters.erase( filter ) == 0 ) {
            active_system_filters.insert( filter );
        }
        if( install_info ) {
            install_info->dirty = true;
        }
    } else if( which == editor_dropdown::condition ) {
        if( option < 0 || option > static_cast<int>( editor_condition_filter::replacement ) ) {
            return;
        }
        const editor_condition_filter filter = static_cast<editor_condition_filter>( option );
        if( filter == editor_condition_filter::all ) {
            if( all_condition_filters_selected() ) {
                active_condition_filters.clear();
            } else {
                active_condition_filters.clear();
                for( int i = 1; i <= static_cast<int>( editor_condition_filter::replacement ); ++i ) {
                    active_condition_filters.insert( static_cast<editor_condition_filter>( i ) );
                }
            }
        } else if( active_condition_filters.erase( filter ) == 0 ) {
            active_condition_filters.insert( filter );
        }
    }
    reset_part_selection();
}

std::string veh_interact::editor_system_filter_summary() const
{
    if( all_system_filters_selected() ) {
        return editor_system_name( editor_system_filter::all );
    }
    if( active_system_filters.empty() ) {
        return _( "None" );
    }
    if( active_system_filters.size() == 1 ) {
        return editor_system_name( *active_system_filters.begin() );
    }
    return string_format( _( "%d selected" ), static_cast<int>( active_system_filters.size() ) );
}

std::string veh_interact::editor_condition_filter_summary() const
{
    if( all_condition_filters_selected() ) {
        return editor_condition_name( editor_condition_filter::all );
    }
    if( active_condition_filters.empty() ) {
        return _( "None" );
    }
    if( active_condition_filters.size() == 1 ) {
        return editor_condition_name( *active_condition_filters.begin() );
    }
    return string_format( _( "%d selected" ), static_cast<int>( active_condition_filters.size() ) );
}'''
cpp = insert_after_function(cpp,
                            'std::string veh_interact::editor_condition_name( const editor_condition_filter filter ) const',
                            helpers)

cpp = replace_function(cpp,
                       'void veh_interact::editor_filter_button_geometry( const editor_dropdown which, int &x, int &width ) const',
r'''void veh_interact::editor_filter_button_geometry( const editor_dropdown which, int &x, int &width ) const
{
    const std::string system_button = string_format( "[ %s ▼ ]", editor_system_filter_summary() );
    const int system_x = 9;
    if( which == editor_dropdown::system ) {
        x = system_x;
        width = utf8_width( system_button );
        return;
    }

    const int condition_label_x = system_x + utf8_width( system_button ) + 2;
    x = condition_label_x + utf8_width( _( "Condition: " ) );
    const std::string condition_button = string_format( "[ %s ▼ ]",
                                         editor_condition_filter_summary() );
    width = utf8_width( condition_button );
}''')

# Checkbox prefix needs four additional columns in the shared dropdown.
cpp = replace_all(cpp, 'width = std::max( width, utf8_width( option ) + 4 );',
                  'width = std::max( width, utf8_width( option ) + 8 );',
                  'widen filter dropdown')

# Keep the dropdown open while individual filters are toggled.
old_click = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        if( const std::optional<int> option = editor_filter_dropdown_menu.hit_test( pos ) ) {\n            if( open_editor_dropdown == editor_dropdown::system ) {\n                active_system_filter = static_cast<editor_system_filter>( *option );\n                if( install_info ) {\n                    install_info->dirty = true;\n                }\n            } else {\n                active_condition_filter = static_cast<editor_condition_filter>( *option );\n            }\n            open_editor_dropdown = editor_dropdown::none;\n            editor_filter_dropdown_menu.close();\n            reset_part_selection();\n            return true;\n        }\n'''
new_click = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        if( const std::optional<int> option = editor_filter_dropdown_menu.hit_test( pos ) ) {\n            toggle_editor_filter( open_editor_dropdown, *option );\n            return true;\n        }\n'''
cpp = replace_once(cpp, old_click, new_click, 'toggle filter without closing')

cpp = replace_all(cpp,
                  'editor_system_name( active_system_filter )',
                  'editor_system_filter_summary()',
                  'system button/heading summaries')
cpp = replace_all(cpp,
                  'editor_condition_name( active_condition_filter )',
                  'editor_condition_filter_summary()',
                  'condition button summaries')

# Dropdown rows are explicit checkboxes.  The helper still highlights checked rows and hover.
old_entries = '''        if( open_editor_dropdown == editor_dropdown::system ) {\n            const editor_system_filter filter = static_cast<editor_system_filter>( i );\n            entry.label = editor_system_name( filter );\n            entry.selected = filter == active_system_filter;\n        } else {\n            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );\n            entry.label = editor_condition_name( filter );\n            entry.selected = filter == active_condition_filter;\n        }\n'''
new_entries = '''        if( open_editor_dropdown == editor_dropdown::system ) {\n            const editor_system_filter filter = static_cast<editor_system_filter>( i );\n            const bool checked = system_filter_selected( filter );\n            entry.label = string_format( checked ? "[x] %s" : "[ ] %s", editor_system_name( filter ) );\n            entry.selected = checked;\n        } else {\n            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );\n            const bool checked = condition_filter_selected( filter );\n            entry.label = string_format( checked ? "[x] %s" : "[ ] %s", editor_condition_name( filter ) );\n            entry.selected = checked;\n        }\n'''
cpp = replace_once(cpp, old_entries, new_entries, 'checkbox filter rows')

# Install candidate filtering follows the same multi-select system filter.
cpp = replace_all(cpp,
'''        if( active_system_filter != editor_system_filter::all &&\n            primary_system_for_part_info( *part ) != active_system_filter ) {\n            continue;\n        }\n''',
'''        if( active_system_filters.count( primary_system_for_part_info( *part ) ) == 0 ) {\n            continue;\n        }\n''', 'install system multiselect')

# Viewport filtering/tinting: only tint when a subset is active, and tint each part by its own selected system.
cpp = replace_once(cpp,
'''    const bool system_active = active_system_filter != editor_system_filter::all;\n    const bool condition_active = active_condition_filter != editor_condition_filter::all;\n''',
'''    const bool system_active = !all_system_filters_selected();\n    const bool condition_active = !all_condition_filters_selected();\n''', 'filter-active state')
cpp = replace_once(cpp,
                  '    const auto system_color = [&]() -> nc_color {\n        switch( active_system_filter ) {',
                  '    const auto system_color = [&]( const editor_system_filter filter ) -> nc_color {\n        switch( filter ) {',
                  'system color argument')
cpp = replace_once(cpp, '            return system_color();',
                  '            return system_color( primary_system_for_part( part ) );',
                  'per-part system tint')

# No stale exclusive-filter state should remain.
if 'active_system_filter' in cpp or 'active_condition_filter' in cpp:
    leftovers = [line for line in cpp.splitlines() if 'active_system_filter' in line or 'active_condition_filter' in line]
    raise SystemExit('stale exclusive filter references:\n' + '\n'.join(leftovers[:20]))
if 'active_system_filter' in h or 'active_condition_filter' in h:
    raise SystemExit('stale exclusive filter reference in header')

cpp_path.write_text(cpp)
h_path.write_text(h)
print('vehicle System/Condition filters converted to checkbox multiselect')
