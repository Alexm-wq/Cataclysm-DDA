from pathlib import Path

cpp_path = Path('src/veh_interact.cpp')
h_path = Path('src/veh_interact.h')
dropdown_path = Path('src/ui_dropdown.h')
cpp = cpp_path.read_text()
h = h_path.read_text()
dropdown = dropdown_path.read_text()


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


def insert_after(text, needle, addition, label):
    count = text.count(needle)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    return text.replace(needle, needle + addition, 1)


def insert_after_function(text, signature, addition):
    _, end = function_end(text, signature)
    return text[:end] + '\n\n' + addition.rstrip() + text[end:]

# ---------------------------------------------------------------------------
# Shared dropdown helper: checkbox rendering + reusable multi-select model.
# ---------------------------------------------------------------------------
dropdown = replace_once(
    dropdown,
    '#include <algorithm>\n#include <optional>\n#include <string>\n',
    '#include <algorithm>\n#include <initializer_list>\n#include <optional>\n#include <set>\n#include <string>\n',
    'dropdown helper includes')

dropdown = replace_once(
    dropdown,
'''    bool enabled = true;\n    bool selected = false;\n    std::string disabled_reason;\n''',
'''    bool enabled = true;\n    bool selected = false;\n    // When set, ui_dropdown renders a standard [x]/[ ] prefix.\n    // This keeps checkbox presentation consistent for reusable filter menus.\n    std::optional<bool> checked;\n    std::string disabled_reason;\n''',
    'dropdown checkbox state')

multiselect_model = r'''

/**
 * Reusable selection model for checkbox filter dropdowns.
 *
 * The model stores concrete options only; callers can expose a synthetic "All"
 * row and wire it directly to toggle_all().  It starts with every option selected,
 * matching the common "show everything" filter default.
 */
template<typename T>
class ui_multiselect_filter
{
    public:
        ui_multiselect_filter() = default;

        ui_multiselect_filter( std::initializer_list<T> options )
            : options_( options ), selected_( options.begin(), options.end() ) {}

        bool contains( const T &option ) const {
            return selected_.count( option ) > 0;
        }

        bool all_selected() const {
            return !options_.empty() && selected_.size() == options_.size();
        }

        bool none_selected() const {
            return selected_.empty();
        }

        std::size_t selected_count() const {
            return selected_.size();
        }

        std::optional<T> first_selected() const {
            for( const T &option : options_ ) {
                if( contains( option ) ) {
                    return option;
                }
            }
            return std::nullopt;
        }

        void select_all() {
            selected_.clear();
            selected_.insert( options_.begin(), options_.end() );
        }

        void clear() {
            selected_.clear();
        }

        void toggle_all() {
            if( all_selected() ) {
                clear();
            } else {
                select_all();
            }
        }

        void toggle( const T &option ) {
            if( std::find( options_.begin(), options_.end(), option ) == options_.end() ) {
                return;
            }
            if( selected_.erase( option ) == 0 ) {
                selected_.insert( option );
            }
        }

        const std::vector<T> &options() const {
            return options_;
        }

    private:
        std::vector<T> options_;
        std::set<T> selected_;
};
'''
dropdown = insert_after(
    dropdown,
'''struct ui_dropdown_style {\n    nc_color border = c_light_cyan;\n    nc_color text = c_light_gray;\n    nc_color disabled = c_dark_gray;\n    nc_color highlight = h_green;\n};\n''',
    multiselect_model,
    'shared multiselect model')

dropdown = replace_once(
    dropdown,
'''            int widest = 0;\n            for( const ui_dropdown_entry &entry : entries_ ) {\n                widest = std::max( widest, utf8_width( entry.label ) );\n            }\n''',
'''            int widest = 0;\n            for( const ui_dropdown_entry &entry : entries_ ) {\n                const int checkbox_width = entry.checked.has_value() ? 4 : 0;\n                widest = std::max( widest, utf8_width( entry.label ) + checkbox_width );\n            }\n''',
    'checkbox-aware dropdown width')

dropdown = replace_once(
    dropdown,
'''                const nc_color color = !row.enabled ? style_.disabled :\n                                       highlighted ? style_.highlight : style_.text;\n                trim_and_print( window_, point( 1, i + 1 ), std::max( 1, width_ - 2 ), color,\n                                row.label );\n''',
'''                const nc_color color = !row.enabled ? style_.disabled :\n                                       highlighted ? style_.highlight : style_.text;\n                const std::string label = row.checked.has_value() ?\n                                          string_format( *row.checked ? "[x] %s" : "[ ] %s", row.label ) :\n                                          row.label;\n                trim_and_print( window_, point( 1, i + 1 ), std::max( 1, width_ - 2 ), color,\n                                label );\n''',
    'checkbox dropdown rendering')

# ---------------------------------------------------------------------------
# Vehicle editor state uses the shared selection model.
# ---------------------------------------------------------------------------
h = replace_once(
    h,
'''        editor_layer active_editor_layer = editor_layer::composite;\n        editor_system_filter active_system_filter = editor_system_filter::all;\n        editor_condition_filter active_condition_filter = editor_condition_filter::all;\n        editor_dropdown open_editor_dropdown = editor_dropdown::none;\n''',
'''        editor_layer active_editor_layer = editor_layer::composite;\n        ui_multiselect_filter<editor_system_filter> active_system_filters {\n            editor_system_filter::structural, editor_system_filter::propulsion,\n            editor_system_filter::fuel, editor_system_filter::electrical,\n            editor_system_filter::storage, editor_system_filter::controls,\n            editor_system_filter::passenger, editor_system_filter::lighting,\n            editor_system_filter::utility, editor_system_filter::turrets,\n            editor_system_filter::combat, editor_system_filter::other\n        };\n        ui_multiselect_filter<editor_condition_filter> active_condition_filters {\n            editor_condition_filter::healthy, editor_condition_filter::damaged,\n            editor_condition_filter::broken, editor_condition_filter::replacement\n        };\n        editor_dropdown open_editor_dropdown = editor_dropdown::none;\n''',
    'vehicle multiselect state')

h = replace_once(
    h,
'''        bool part_matches_system( const vehicle_part &vp ) const;\n        bool part_matches_condition( const vehicle_part &vp ) const;\n        std::string editor_layer_name( editor_layer layer ) const;\n''',
'''        bool part_matches_system( const vehicle_part &vp ) const;\n        bool part_matches_condition( const vehicle_part &vp ) const;\n        void toggle_editor_filter( editor_dropdown which, int option );\n        std::string editor_system_filter_summary() const;\n        std::string editor_condition_filter_summary() const;\n        std::string editor_layer_name( editor_layer layer ) const;\n''',
    'vehicle multiselect declarations')

cpp = replace_function(
    cpp,
    'bool veh_interact::part_matches_system( const vehicle_part &vp ) const',
r'''bool veh_interact::part_matches_system( const vehicle_part &vp ) const
{
    return active_system_filters.contains( primary_system_for_part( vp ) );
}''')

cpp = replace_function(
    cpp,
    'bool veh_interact::part_matches_condition( const vehicle_part &vp ) const',
r'''bool veh_interact::part_matches_condition( const vehicle_part &vp ) const
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
    return active_condition_filters.contains( condition );
}''')

vehicle_helpers = r'''void veh_interact::toggle_editor_filter( const editor_dropdown which, const int option )
{
    if( which == editor_dropdown::system ) {
        if( option < 0 || option > static_cast<int>( editor_system_filter::other ) ) {
            return;
        }
        if( option == static_cast<int>( editor_system_filter::all ) ) {
            active_system_filters.toggle_all();
        } else {
            active_system_filters.toggle( static_cast<editor_system_filter>( option ) );
        }
        if( install_info ) {
            install_info->dirty = true;
        }
    } else if( which == editor_dropdown::condition ) {
        if( option < 0 || option > static_cast<int>( editor_condition_filter::replacement ) ) {
            return;
        }
        if( option == static_cast<int>( editor_condition_filter::all ) ) {
            active_condition_filters.toggle_all();
        } else {
            active_condition_filters.toggle( static_cast<editor_condition_filter>( option ) );
        }
    }
    reset_part_selection();
}

std::string veh_interact::editor_system_filter_summary() const
{
    if( active_system_filters.all_selected() ) {
        return editor_system_name( editor_system_filter::all );
    }
    if( active_system_filters.none_selected() ) {
        return _( "None" );
    }
    if( active_system_filters.selected_count() == 1 ) {
        if( const std::optional<editor_system_filter> selected = active_system_filters.first_selected() ) {
            return editor_system_name( *selected );
        }
    }
    return string_format( _( "%d selected" ),
                          static_cast<int>( active_system_filters.selected_count() ) );
}

std::string veh_interact::editor_condition_filter_summary() const
{
    if( active_condition_filters.all_selected() ) {
        return editor_condition_name( editor_condition_filter::all );
    }
    if( active_condition_filters.none_selected() ) {
        return _( "None" );
    }
    if( active_condition_filters.selected_count() == 1 ) {
        if( const std::optional<editor_condition_filter> selected = active_condition_filters.first_selected() ) {
            return editor_condition_name( *selected );
        }
    }
    return string_format( _( "%d selected" ),
                          static_cast<int>( active_condition_filters.selected_count() ) );
}'''
cpp = insert_after_function(
    cpp,
    'std::string veh_interact::editor_condition_name( const editor_condition_filter filter ) const',
    vehicle_helpers)

cpp = replace_function(
    cpp,
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

# Requested width is calculated outside ui_dropdown, so reserve the checkbox prefix here too.
cpp = replace_all(
    cpp,
    'width = std::max( width, utf8_width( option ) + 4 );',
    'width = std::max( width, utf8_width( option ) + 8 );',
    'filter dropdown checkbox width')

old_click = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        if( const std::optional<int> option = editor_filter_dropdown_menu.hit_test( pos ) ) {\n            if( open_editor_dropdown == editor_dropdown::system ) {\n                active_system_filter = static_cast<editor_system_filter>( *option );\n                if( install_info ) {\n                    install_info->dirty = true;\n                }\n            } else {\n                active_condition_filter = static_cast<editor_condition_filter>( *option );\n            }\n            open_editor_dropdown = editor_dropdown::none;\n            editor_filter_dropdown_menu.close();\n            reset_part_selection();\n            return true;\n        }\n'''
new_click = '''    if( open_editor_dropdown != editor_dropdown::none ) {\n        if( const std::optional<int> option = editor_filter_dropdown_menu.hit_test( pos ) ) {\n            toggle_editor_filter( open_editor_dropdown, *option );\n            return true;\n        }\n'''
cpp = replace_once(cpp, old_click, new_click, 'keep filter dropdown open while toggling')

cpp = replace_all(
    cpp,
    'editor_system_name( active_system_filter )',
    'editor_system_filter_summary()',
    'system filter summary')
cpp = replace_all(
    cpp,
    'editor_condition_name( active_condition_filter )',
    'editor_condition_filter_summary()',
    'condition filter summary')

old_entries = '''        if( open_editor_dropdown == editor_dropdown::system ) {\n            const editor_system_filter filter = static_cast<editor_system_filter>( i );\n            entry.label = editor_system_name( filter );\n            entry.selected = filter == active_system_filter;\n        } else {\n            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );\n            entry.label = editor_condition_name( filter );\n            entry.selected = filter == active_condition_filter;\n        }\n'''
new_entries = '''        if( open_editor_dropdown == editor_dropdown::system ) {\n            const editor_system_filter filter = static_cast<editor_system_filter>( i );\n            const bool checked = filter == editor_system_filter::all ?\n                                 active_system_filters.all_selected() : active_system_filters.contains( filter );\n            entry.label = filter == editor_system_filter::all ? _( "All" ) : editor_system_name( filter );\n            entry.checked = checked;\n            entry.selected = checked;\n        } else {\n            const editor_condition_filter filter = static_cast<editor_condition_filter>( i );\n            const bool checked = filter == editor_condition_filter::all ?\n                                 active_condition_filters.all_selected() : active_condition_filters.contains( filter );\n            entry.label = filter == editor_condition_filter::all ? _( "All" ) : editor_condition_name( filter );\n            entry.checked = checked;\n            entry.selected = checked;\n        }\n'''
cpp = replace_once(cpp, old_entries, new_entries, 'shared checkbox filter entries')

# Install candidate list uses the same System multi-select model.
cpp = replace_all(
    cpp,
'''        if( active_system_filter != editor_system_filter::all &&\n            primary_system_for_part_info( *part ) != active_system_filter ) {\n            continue;\n        }\n''',
'''        if( !active_system_filters.contains( primary_system_for_part_info( *part ) ) ) {\n            continue;\n        }\n''',
    'install candidate system filters')

# A subset (including the empty subset) activates visual filter treatment.
cpp = replace_once(
    cpp,
'''    const bool system_active = active_system_filter != editor_system_filter::all;\n    const bool condition_active = active_condition_filter != editor_condition_filter::all;\n''',
'''    const bool system_active = !active_system_filters.all_selected();\n    const bool condition_active = !active_condition_filters.all_selected();\n''',
    'viewport filter active state')

cpp = replace_once(
    cpp,
'''    const auto system_color = [&]() -> nc_color {\n        switch( active_system_filter ) {\n''',
'''    const auto system_color = [&]( const editor_system_filter filter ) -> nc_color {\n        switch( filter ) {\n''',
    'multi-system tint selector')
cpp = replace_once(
    cpp,
    '            return system_color();',
    '            return system_color( primary_system_for_part( part ) );',
    'per-part system tint')

# Exact old exclusive-state spellings must be gone.  Plural helper names are fine.
for stale in [
    'active_system_filter =',
    'active_condition_filter =',
    'active_system_filter !=',
    'active_condition_filter !=',
    'switch( active_system_filter',
    'switch( active_condition_filter',
]:
    if stale in cpp or stale in h:
        raise SystemExit(f'stale exclusive filter state remains: {stale}')

assert 'class ui_multiselect_filter' in dropdown
assert 'std::optional<bool> checked' in dropdown
assert 'active_system_filters.toggle_all()' in cpp
assert 'active_condition_filters.toggle_all()' in cpp
assert 'entry.checked = checked' in cpp
assert 'toggle_editor_filter( open_editor_dropdown, *option )' in cpp

cpp_path.write_text(cpp)
h_path.write_text(h)
dropdown_path.write_text(dropdown)
print('vehicle filters use shared checkbox multi-select helper')
