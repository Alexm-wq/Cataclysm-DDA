from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str) -> str:
    text, count = re.subn(pattern, repl, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text


root = Path('.')

# ---------------------------------------------------------------------------
# Shared world viewport: header-safe defaults, optional stepped zoom, and
# center-preserving auxiliary-window rebinding.
# ---------------------------------------------------------------------------
p = root / 'src/ui_helpers/controls/world_viewport.h'
s = p.read_text(encoding='utf-8')
s = replace_once(s, '#include <optional>\n#include <string>\n',
                 '#include <optional>\n#include <string>\n#include <vector>\n',
                 'world viewport vector include')
s = replace_once(s, '#include "../../game_constants.h"\n', '',
                 'remove unrelated game_constants include')
s = replace_once(
    s,
    '''struct ui_world_viewport_map_config {\n    int initial_draw_scale = DEFAULT_TILESET_ZOOM;\n    int minimum_draw_scale = MINIMUM_TILESET_ZOOM;\n    int maximum_draw_scale = MAXIMUM_TILESET_ZOOM;\n    int zoom_factor = 2;\n    bool cursor_anchored_zoom = true;\n};''',
    '''inline constexpr int ui_world_viewport_default_draw_scale = 16;\ninline constexpr int ui_world_viewport_minimum_draw_scale = 4;\ninline constexpr int ui_world_viewport_maximum_draw_scale = 64;\n\nstruct ui_world_viewport_map_config {\n    int initial_draw_scale = ui_world_viewport_default_draw_scale;\n    int minimum_draw_scale = ui_world_viewport_minimum_draw_scale;\n    int maximum_draw_scale = ui_world_viewport_maximum_draw_scale;\n    int zoom_factor = 2;\n    std::vector<int> draw_scale_steps;\n    bool cursor_anchored_zoom = true;\n};''',
    'header-safe viewport defaults')
s = replace_once(
    s,
    '        void attach_map_preview( const catacurses::window &window );\n',
    '        void attach_map_preview( const catacurses::window &window,\n                                 bool preserve_visual_center = false );\n',
    'preview attach declaration')
s = replace_once(
    s,
    '        int independent_draw_scale_ = DEFAULT_TILESET_ZOOM;\n',
    '        int independent_draw_scale_ = ui_world_viewport_default_draw_scale;\n',
    'independent zoom default')
p.write_text(s, encoding='utf-8')

p = root / 'src/ui_helpers/controls/world_viewport.cpp'
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    '''    map_config_.zoom_factor = std::max( 2, map_config_.zoom_factor );\n    independent_center_ = center;\n    independent_draw_scale_ = map_config_.initial_draw_scale;''',
    '''    map_config_.zoom_factor = std::max( 2, map_config_.zoom_factor );\n    for( int &scale : map_config_.draw_scale_steps ) {\n        scale = std::clamp( scale, map_config_.minimum_draw_scale,\n                            map_config_.maximum_draw_scale );\n    }\n    std::sort( map_config_.draw_scale_steps.begin(), map_config_.draw_scale_steps.end() );\n    map_config_.draw_scale_steps.erase(\n        std::unique( map_config_.draw_scale_steps.begin(), map_config_.draw_scale_steps.end() ),\n        map_config_.draw_scale_steps.end() );\n    if( !map_config_.draw_scale_steps.empty() ) {\n        const auto closest = std::min_element( map_config_.draw_scale_steps.begin(),\n                                               map_config_.draw_scale_steps.end(),\n        [&]( const int lhs, const int rhs ) {\n            return std::abs( lhs - map_config_.initial_draw_scale ) <\n                   std::abs( rhs - map_config_.initial_draw_scale );\n        } );\n        map_config_.initial_draw_scale = *closest;\n    }\n    independent_center_ = center;\n    independent_draw_scale_ = map_config_.initial_draw_scale;''',
    'sanitize stepped zoom config')
s = sub_once(
    s,
    r'''void ui_world_viewport::attach_map_preview\( const catacurses::window &window \)\n\{.*?\n\}\n\nvoid ui_world_viewport::detach_map_preview''',
    '''void ui_world_viewport::attach_map_preview( const catacurses::window &window,\n        const bool preserve_visual_center )\n{\n#if defined(TILES)\n    std::optional<tripoint_bub_ms> old_mid_map;\n    if( preserve_visual_center && map_preview_window_ && independent_center_ ) {\n        const window_dimensions old_dim = get_window_dimensions( map_preview_window_ );\n        const point old_mid( old_dim.window_size_pixel.x / 2, old_dim.window_size_pixel.y / 2 );\n        old_mid_map = map_preview_pixel_to_map( map_preview_window_, old_mid,\n                      *independent_center_, independent_draw_scale_ );\n    }\n    if( map_preview_window_ ) {\n        clear_map_preview_window();\n    }\n#endif\n    map_preview_window_ = window;\n#if defined(TILES)\n    if( preserve_visual_center && old_mid_map && map_preview_window_ && independent_center_ ) {\n        const window_dimensions new_dim = get_window_dimensions( map_preview_window_ );\n        const point new_mid( new_dim.window_size_pixel.x / 2, new_dim.window_size_pixel.y / 2 );\n        const std::optional<tripoint_bub_ms> new_mid_map = map_preview_pixel_to_map(\n                    map_preview_window_, new_mid, *independent_center_, independent_draw_scale_ );\n        if( new_mid_map ) {\n            *independent_center_ += *old_mid_map - *new_mid_map;\n        }\n    }\n#endif\n    refresh_map_preview_registration();\n}\n\nvoid ui_world_viewport::detach_map_preview''',
    'center-preserving preview attachment')
s = sub_once(
    s,
    r'''    if\( independent_center_ \) \{\n        const int old_zoom = independent_draw_scale_;\n        int next = old_zoom;\n        if\( direction > 0 \) \{.*?        refresh_map_preview_registration\(\);\n        return;\n    \}''',
    '''    if( independent_center_ ) {\n        const int old_zoom = independent_draw_scale_;\n        int next = old_zoom;\n        if( !map_config_.draw_scale_steps.empty() ) {\n            if( direction > 0 ) {\n                const auto it = std::upper_bound( map_config_.draw_scale_steps.begin(),\n                                                  map_config_.draw_scale_steps.end(), old_zoom );\n                if( it != map_config_.draw_scale_steps.end() ) {\n                    next = *it;\n                }\n            } else {\n                auto it = std::lower_bound( map_config_.draw_scale_steps.begin(),\n                                            map_config_.draw_scale_steps.end(), old_zoom );\n                if( it == map_config_.draw_scale_steps.end() || *it >= old_zoom ) {\n                    if( it != map_config_.draw_scale_steps.begin() ) {\n                        --it;\n                        next = *it;\n                    }\n                } else {\n                    next = *it;\n                }\n            }\n        } else if( direction > 0 ) {\n            if( old_zoom > map_config_.maximum_draw_scale / map_config_.zoom_factor ) {\n                next = map_config_.maximum_draw_scale;\n            } else {\n                next = old_zoom * map_config_.zoom_factor;\n            }\n        } else {\n            next = old_zoom / map_config_.zoom_factor;\n        }\n        next = std::clamp( next, map_config_.minimum_draw_scale,\n                           map_config_.maximum_draw_scale );\n        if( next == old_zoom ) {\n            return;\n        }\n\n        independent_draw_scale_ = next;\n        if( anchor && map_config_.cursor_anchored_zoom ) {\n            const std::optional<tripoint_bub_ms> after = map_position(\n                        context, viewer, hovered_, false );\n            if( after ) {\n                *independent_center_ += *anchor - *after;\n            }\n        }\n        refresh_map_preview_registration();\n        return;\n    }''',
    'stepped independent zoom')
s = replace_once(
    s,
    '    return map_draw_scale() * 100 / DEFAULT_TILESET_ZOOM;\n',
    '    return map_draw_scale() * 100 / ui_world_viewport_default_draw_scale;\n',
    'viewport zoom percentage')
p.write_text(s, encoding='utf-8')

# ---------------------------------------------------------------------------
# Vehicle editor: keep its schematic semantics local, but move the Live/Split
# world camera, zoom, pan, renderer registration and projection to the helper.
# ---------------------------------------------------------------------------
p = root / 'src/veh_interact.h'
s = p.read_text(encoding='utf-8')
s = replace_once(
    s,
    '#include "ui_helpers/controls/text_field.h"\n',
    '#include "ui_helpers/controls/text_field.h"\n#include "ui_helpers/controls/world_viewport.h"\n',
    'vehicle world viewport include')
s = replace_once(
    s,
    '''        point viewport_drag_pan_origin = point::zero;\n        int viewport_zoom = 2;\n        point live_preview_pan = point::zero;\n        point live_preview_drag_anchor = point::zero;\n        point live_preview_drag_pan_origin = point::zero;\n        int live_preview_zoom = 2;\n        bool live_preview_dragging = false;\n        int selected_part = -1;''',
    '''        point viewport_drag_pan_origin = point::zero;\n        int viewport_zoom = 2;\n        ui_world_viewport live_world_viewport;\n        int selected_part = -1;''',
    'vehicle live camera state')
s = replace_once(s, '        std::optional<editor_view_mode> live_preview_last_draw_mode;\n', '',
                 'remove vehicle live draw mode state')
s = replace_once(s, '        point live_preview_cell_size() const;\n', '',
                 'remove live cell size declaration')
p.write_text(s, encoding='utf-8')

p = root / 'src/veh_interact.cpp'
s = p.read_text(encoding='utf-8')

# Detach helper before resize replaces curses windows.
s = replace_once(
    s,
    '''#if defined(TILES)\n    // Window objects are replaced below; never leave the SDL preview registry\n    // pointing at an old curses window across a resize.\n    clear_map_preview_window();\n#endif''',
    '''    // Window objects are replaced below; never leave the shared auxiliary\n    // viewport pointing at an old curses window across a resize.\n    live_world_viewport.cancel_map_capture();\n    live_world_viewport.detach_map_preview();''',
    'vehicle resize preview detach')

# Initialize the shared Live/Split camera once; layout rebinding preserves it.
s = replace_once(
    s,
    '''    move_cursor( here, point_rel_ms::zero );\n    center_viewport_on_vehicle();\n    reset_part_selection();''',
    '''    move_cursor( here, point_rel_ms::zero );\n    center_viewport_on_vehicle();\n    ui_world_viewport_map_config live_view_config;\n    live_view_config.initial_draw_scale = 16;\n    live_view_config.minimum_draw_scale = 8;\n    live_view_config.maximum_draw_scale = 32;\n    live_view_config.draw_scale_steps = { 8, 16, 24, 32 };\n    live_view_config.cursor_anchored_zoom = true;\n    live_world_viewport.configure_map_camera( live_preview_vehicle_center( here ), live_view_config );\n    reset_part_selection();''',
    'vehicle shared live camera init')

# Helper owns Live/Split cleanup; vehicle-specific tile thumbnails remain local.
s = sub_once(
    s,
    r'''veh_interact::~veh_interact\(\)\n\{\n#if defined\(TILES\)\n    clear_map_preview_window\(\);\n    clear_vehicle_part_preview_tiles\(\);\n    set_sdl_mouse_capture\( false \);\n#endif\n\}''',
    '''veh_interact::~veh_interact()\n{\n    live_world_viewport.cancel_map_capture();\n    live_world_viewport.detach_map_preview();\n#if defined(TILES)\n    clear_vehicle_part_preview_tiles();\n    set_sdl_mouse_capture( false );\n#endif\n}''',
    'vehicle destructor viewport cleanup')

# Mode transitions cancel shared map capture instead of maintaining duplicate drag state.
s = s.replace('    live_preview_dragging = false;\n', '    live_world_viewport.cancel_map_capture();\n')
s = s.replace('            live_preview_dragging = false;\n', '            live_world_viewport.cancel_map_capture();\n')
s = s.replace('    live_preview_last_draw_mode.reset();\n', '')

# Remove old hand-computed Live tile cell size.
s = sub_once(
    s,
    r'''point veh_interact::live_preview_cell_size\(\) const\n\{.*?\n\}\n\ntripoint_bub_ms veh_interact::live_preview_vehicle_center''',
    '''tripoint_bub_ms veh_interact::live_preview_vehicle_center''',
    'remove vehicle live cell size implementation')

# Header text now reads the shared viewport's real draw scale.
s = s.replace('live_preview_zoom * 50', 'live_world_viewport.map_zoom_percent()')
s = s.replace(
    '''const int shown_zoom = active_editor_view_mode == editor_view_mode::live ?\n                               live_preview_zoom : viewport_zoom;''',
    '''const int shown_zoom = active_editor_view_mode == editor_view_mode::live ?\n                               live_world_viewport.map_zoom_percent() : viewport_zoom * 50;''')
s = s.replace('shown_zoom * 50', 'shown_zoom')

# Replace manual SDL preview registration/reanchoring with the shared backend.
s = sub_once(
    s,
    r'''void veh_interact::display_live_preview\( map &here \)\n\{.*?\n\}\n\nvoid veh_interact::display_part_inspector''',
    '''void veh_interact::display_live_preview( map &here )\n{\n#if defined(TILES)\n    ( void )here;\n    if( active_editor_view_mode == editor_view_mode::editor ) {\n        live_world_viewport.hide();\n        live_world_viewport.detach_map_preview();\n        return;\n    }\n\n    catacurses::window &preview = active_editor_view_mode == editor_view_mode::live ?\n                                  w_live_preview_full : w_live_preview_split;\n    if( !preview ) {\n        live_world_viewport.hide();\n        live_world_viewport.detach_map_preview();\n        return;\n    }\n\n    const int left = active_editor_view_mode == editor_view_mode::live ?\n                     0 : editor_schematic_width() + 1;\n    live_world_viewport.configure( inclusive_rectangle<point>(\n            point( left, editor_viewport_top() ),\n            point( getmaxx( w_disp ) - 1, getmaxy( w_disp ) - 1 ) ) );\n    // Live and Split are different destination windows.  Rebinding through the\n    // helper preserves the map square at the visual center while retaining the\n    // same independent camera/zoom state.\n    live_world_viewport.attach_map_preview( preview, true );\n    live_world_viewport.draw_map_preview();\n#else\n    ( void )here;\n#endif\n}\n\nvoid veh_interact::display_part_inspector''',
    'shared vehicle live preview renderer')

# Switching Editor/Live/Split cancels either viewport capture path.
s = s.replace(
    '''            viewport_dragging = false;\n            live_world_viewport.cancel_map_capture();\n#if defined(TILES)\n            set_sdl_mouse_capture( false );\n#endif''',
    '''            viewport_dragging = false;\n            live_world_viewport.cancel_map_capture();\n#if defined(TILES)\n            set_sdl_mouse_capture( false );\n#endif''')

# Route Live/Split input through ui_world_viewport.  Keep the schematic's custom
# mount-space pan because it is not a world map.
old_mouse_block = re.compile(r'''#if defined\(TILES\)\n    const bool middle_mouse_down = is_middle_mouse_button_down\(\);\n    const bool mouse_focused = has_sdl_mouse_focus\(\);\n    if\( \( viewport_dragging \|\| live_world_viewport\.cancel_map_capture\(\) \) &&.*?    if\( action == "MOUSE_MOVE" && viewport_dragging \) \{''', re.S)
# The generic string replacement above changes a boolean field line into a call,
# so match the original block more defensively by its endpoints instead.
start = s.find('#if defined(TILES)\n    const bool middle_mouse_down = is_middle_mouse_button_down();\n    const bool mouse_focused = has_sdl_mouse_focus();')
end_marker = '    if( action == "MOUSE_MOVE" && viewport_dragging ) {'
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError('vehicle mouse camera block: endpoints not found')
replacement = '''#if defined(TILES)\n    const bool middle_mouse_down = is_middle_mouse_button_down();\n    const bool mouse_focused = has_sdl_mouse_focus();\n    if( viewport_dragging && ( !middle_mouse_down || !mouse_focused ) ) {\n        viewport_dragging = false;\n        set_sdl_mouse_capture( false );\n    }\n    if( live_world_viewport.has_capture() && ( !middle_mouse_down || !mouse_focused ) ) {\n        live_world_viewport.cancel_map_capture();\n    }\n    if( action == "MOUSE_MOVE" && over_live_preview && !live_world_viewport.has_capture() &&\n        middle_mouse_down && mouse_focused && open_editor_dropdown == editor_dropdown::none &&\n        open_editor_toolbar_dropdown.empty() && !editor_context_open ) {\n        const ui_world_viewport_action pan = live_world_viewport.handle_map_input(\n                    "CAMERA_PAN_START", main_context, get_avatar(), viewport_pos );\n        if( pan.consumed() ) {\n            return true;\n        }\n    }\n#endif\n\n    if( ( over_live_preview || live_world_viewport.has_capture() ) &&\n        open_editor_dropdown == editor_dropdown::none &&\n        open_editor_toolbar_dropdown.empty() && !editor_context_open ) {\n        const ui_world_viewport_action live_action = live_world_viewport.handle_map_input(\n                    action, main_context, get_avatar(), viewport_pos );\n        if( live_action.consumed() ) {\n            return true;\n        }\n    }\n\n    if( action == "CAMERA_PAN_START" ) {\n        if( open_editor_dropdown != editor_dropdown::none ||\n            !open_editor_toolbar_dropdown.empty() || editor_context_open || !viewport_pos ) {\n            return false;\n        }\n        if( over_schematic_content ) {\n            viewport_dragging = true;\n            viewport_drag_anchor = *viewport_pos;\n            viewport_drag_pan_origin = viewport_pan;\n#if defined(TILES)\n            set_sdl_mouse_capture( true );\n#endif\n            return true;\n        }\n        return false;\n    }\n    if( action == "CAMERA_PAN_END" ) {\n        if( viewport_dragging ) {\n            viewport_dragging = false;\n#if defined(TILES)\n            set_sdl_mouse_capture( false );\n#endif\n            return true;\n        }\n#if defined(TILES)\n        set_sdl_mouse_capture( false );\n#endif\n        return false;\n    }\n    if( action == "MOUSE_MOVE" && viewport_dragging ) {'''
s = s[:start] + replacement + s[end + len(end_marker):]

# The wheel branch still contains the old Live camera implementation.  It is now
# normally consumed above, but remove it completely so no duplicate state remains.
s = sub_once(
    s,
    r'''        if\( over_live_preview \) \{.*?            return true;\n        \}\n        if\( over_schematic_content \) \{''',
    '''        if( over_live_preview ) {\n            const ui_world_viewport_action live_action = live_world_viewport.handle_map_input(\n                        action, main_context, get_avatar(), viewport_pos );\n            return live_action.consumed();\n        }\n        if( over_schematic_content ) {''',
    'remove duplicate vehicle live wheel camera')

# Hiding for modal/query handoff must release the shared auxiliary renderer.
s = replace_once(
    s,
    '''    if( hide != ui_hidden ) {\n        ui_hidden = hide;\n        create_or_get_ui_adaptor( here )->mark_resize();\n    }''',
    '''    if( hide != ui_hidden ) {\n        ui_hidden = hide;\n        if( hide ) {\n            live_world_viewport.cancel_map_capture();\n            live_world_viewport.detach_map_preview();\n        }\n        create_or_get_ui_adaptor( here )->mark_resize();\n    }''',
    'vehicle hide preview cleanup')
s = replace_once(
    s,
    '''    persistent_editor->ui_hidden = true;\n    persistent_editor->ui->mark_resize();''',
    '''    persistent_editor->ui_hidden = true;\n    persistent_editor->live_world_viewport.cancel_map_capture();\n    persistent_editor->live_world_viewport.detach_map_preview();\n    persistent_editor->ui->mark_resize();''',
    'vehicle modal preview cleanup')

# Fail loudly if any obsolete Live/Split camera state survived.
for obsolete in [
    'live_preview_pan', 'live_preview_drag_anchor', 'live_preview_drag_pan_origin',
    'live_preview_dragging', 'live_preview_zoom', 'live_preview_last_draw_mode',
    'live_preview_cell_size'
]:
    if obsolete in s:
        raise RuntimeError(f'obsolete vehicle viewport state survived: {obsolete}')
if 'set_map_preview_window(' in s or 'map_preview_pixel_to_map(' in s or 'clear_map_preview_window();' in s:
    raise RuntimeError('vehicle editor still owns auxiliary map renderer mechanics')

p.write_text(s, encoding='utf-8')

Path('/tmp/branch_patch_commit_message').write_text(
    'Move vehicle live viewport onto shared helper [skip ci]\n', encoding='utf-8')
