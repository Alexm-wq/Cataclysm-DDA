from pathlib import Path

ROOT = Path('.')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, got {count}')
    return text.replace(old, new, 1)


def function_span(text, signature):
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


# ---------------------------------------------------------------------------
# Split helper tree into primitive / controls / models.
# ---------------------------------------------------------------------------
old_overlay = Path('src/ui_helpers/overlay.h')
old_dropdown = Path('src/ui_helpers/dropdown.h')
if not old_overlay.exists() or not old_dropdown.exists():
    raise SystemExit('expected current ui helper headers are missing')

overlay = old_overlay.read_text()
dropdown = old_dropdown.read_text()

# The actual overlay implementation moves to primitive/. Keep a compatibility shim.
overlay_impl = overlay.replace('CATA_SRC_UI_HELPERS_OVERLAY_H',
                               'CATA_SRC_UI_HELPERS_PRIMITIVE_OVERLAY_H')
Path('src/ui_helpers/primitive').mkdir(parents=True, exist_ok=True)
Path('src/ui_helpers/controls').mkdir(parents=True, exist_ok=True)
Path('src/ui_helpers/models').mkdir(parents=True, exist_ok=True)
Path('src/ui_helpers/primitive/overlay.h').write_text(overlay_impl)
old_overlay.write_text('''#pragma once\n#ifndef CATA_SRC_UI_HELPERS_OVERLAY_COMPAT_H\n#define CATA_SRC_UI_HELPERS_OVERLAY_COMPAT_H\n\n// Compatibility include. New UI code should include ui_helpers/primitive/overlay.h.\n#include "ui_helpers/primitive/overlay.h"\n\n#endif // CATA_SRC_UI_HELPERS_OVERLAY_COMPAT_H\n''')

# Extract the reusable multiselect model from dropdown.h.
model_start = dropdown.find('/**\n * Reusable selection model for checkbox filter dropdowns.')
model_end = dropdown.find('/**\n * Reusable mouse-first dropdown/context-menu overlay.', model_start)
if model_start < 0 or model_end < 0:
    raise SystemExit('multiselect model block not found')
model_block = dropdown[model_start:model_end].strip()
model_header = f'''#pragma once\n#ifndef CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H\n#define CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H\n\n#include <algorithm>\n#include <initializer_list>\n#include <optional>\n#include <set>\n#include <vector>\n\n{model_block}\n\n#endif // CATA_SRC_UI_HELPERS_MODELS_MULTISELECT_FILTER_H\n'''
Path('src/ui_helpers/models/multiselect_filter.h').write_text(model_header)

# Remove model-only includes and block from control implementation.
dropdown_control = dropdown[:model_start] + dropdown[model_end:]
dropdown_control = dropdown_control.replace('CATA_SRC_UI_HELPERS_DROPDOWN_H',
                                             'CATA_SRC_UI_HELPERS_CONTROLS_DROPDOWN_H')
dropdown_control = dropdown_control.replace('#include <initializer_list>\n', '')
dropdown_control = dropdown_control.replace('#include <set>\n', '')
dropdown_control = dropdown_control.replace('#include "ui_helpers/overlay.h"',
                                             '#include "ui_helpers/primitive/overlay.h"')
Path('src/ui_helpers/controls/dropdown.h').write_text(dropdown_control)
old_dropdown.write_text('''#pragma once\n#ifndef CATA_SRC_UI_HELPERS_DROPDOWN_COMPAT_H\n#define CATA_SRC_UI_HELPERS_DROPDOWN_COMPAT_H\n\n// Compatibility include. New UI code should include the control/model directly.\n#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/models/multiselect_filter.h"\n\n#endif // CATA_SRC_UI_HELPERS_DROPDOWN_COMPAT_H\n''')

# Vehicle editor adopts the organized includes directly.
veh_h = Path('src/veh_interact.h').read_text()
veh_h = replace_once(veh_h, '#include "ui_helpers/dropdown.h"\n',
                     '#include "ui_helpers/controls/dropdown.h"\n#include "ui_helpers/models/multiselect_filter.h"\n',
                     'vehicle helper include')
Path('src/veh_interact.h').write_text(veh_h)

# ---------------------------------------------------------------------------
# Reusable scroll state model, independent of curses/rendering.
# ---------------------------------------------------------------------------
scroll_model = r'''#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_SCROLL_MODEL_H
#define CATA_SRC_UI_HELPERS_MODELS_SCROLL_MODEL_H

#include <algorithm>

/**
 * Renderer-independent viewport state for scrollable UI controls.
 *
 * Selection is intentionally not part of this model.  Callers explicitly request
 * ensure_visible() when selection/focus should move the viewport.  This keeps free
 * mouse-wheel scrolling independent from the current selected row.
 */
class ui_scroll_model
{
    public:
        ui_scroll_model() = default;
        ui_scroll_model( int content_size, int viewport_size, int viewport_pos = 0 ) {
            set_content_size( content_size );
            set_viewport_size( viewport_size );
            set_viewport_pos( viewport_pos );
        }

        int content_size() const {
            return content_size_;
        }
        int viewport_size() const {
            return viewport_size_;
        }
        int viewport_pos() const {
            return viewport_pos_;
        }
        int max_viewport_pos() const {
            return std::max( 0, content_size_ - viewport_size_ );
        }
        bool can_scroll() const {
            return content_size_ > viewport_size_;
        }

        ui_scroll_model &set_content_size( int value ) {
            content_size_ = std::max( 0, value );
            clamp();
            return *this;
        }
        ui_scroll_model &set_viewport_size( int value ) {
            viewport_size_ = std::max( 0, value );
            clamp();
            return *this;
        }
        ui_scroll_model &set_viewport_pos( int value ) {
            viewport_pos_ = value;
            clamp();
            return *this;
        }
        ui_scroll_model &scroll_by( int delta ) {
            return set_viewport_pos( viewport_pos_ + delta );
        }
        ui_scroll_model &page_by( int pages ) {
            return scroll_by( pages * std::max( 1, viewport_size_ ) );
        }
        ui_scroll_model &scroll_to_start() {
            viewport_pos_ = 0;
            return *this;
        }
        ui_scroll_model &scroll_to_end() {
            viewport_pos_ = max_viewport_pos();
            return *this;
        }
        ui_scroll_model &ensure_visible( int index ) {
            if( index < 0 || content_size_ <= 0 || viewport_size_ <= 0 ) {
                return *this;
            }
            if( index < viewport_pos_ ) {
                viewport_pos_ = index;
            } else if( index >= viewport_pos_ + viewport_size_ ) {
                viewport_pos_ = index - viewport_size_ + 1;
            }
            clamp();
            return *this;
        }

    private:
        void clamp() {
            viewport_pos_ = std::clamp( viewport_pos_, 0, max_viewport_pos() );
        }

        int content_size_ = 0;
        int viewport_size_ = 0;
        int viewport_pos_ = 0;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_SCROLL_MODEL_H
'''
Path('src/ui_helpers/models/scroll_model.h').write_text(scroll_model)

# ---------------------------------------------------------------------------
# Move scrollbar declaration + implementation into primitive/.
# ---------------------------------------------------------------------------
out_h_path = Path('src/output.h')
out_cpp_path = Path('src/output.cpp')
out_h = out_h_path.read_text()
out_cpp = out_cpp_path.read_text()

class_start = out_h.find('class scrollbar\n{')
class_end_marker = '\nstruct multiline_list_entry {'
class_end = out_h.find(class_end_marker, class_start)
if class_start < 0 or class_end < 0:
    raise SystemExit('scrollbar class block not found in output.h')
class_block = out_h[class_start:class_end].rstrip()

scrollbar_header = f'''#pragma once\n#ifndef CATA_SRC_UI_HELPERS_PRIMITIVE_SCROLLBAR_H\n#define CATA_SRC_UI_HELPERS_PRIMITIVE_SCROLLBAR_H\n\n#include <optional>\n#include <string>\n\n#include "color.h"\n#include "cuboid_rectangle.h"\n#include "cursesdef.h"\n#include "point.h"\n#include "ui_helpers/models/scroll_model.h"\n\nclass input_context;\n\n{class_block[:-2]}\n\n        /** Copy renderer-independent scroll state into this visual scrollbar. */\n        scrollbar &model( const ui_scroll_model &state ) {{\n            return content_size( state.content_size() )\n                   .viewport_pos( state.viewport_pos() )\n                   .viewport_size( state.viewport_size() );\n        }}\n\n        /** Drag directly into a renderer-independent scroll model. */\n        bool handle_dragging( const std::string &action, const std::optional<point> &coord,\n                              ui_scroll_model &state ) {{\n            int position = state.viewport_pos();\n            const bool handled = handle_dragging( action, coord, position );\n            if( handled ) {{\n                state.set_viewport_pos( position );\n            }}\n            return handled;\n        }}\n}};\n\n#endif // CATA_SRC_UI_HELPERS_PRIMITIVE_SCROLLBAR_H\n'''
Path('src/ui_helpers/primitive/scrollbar.h').write_text(scrollbar_header)

# output.h remains a compatibility umbrella for legacy callers.
out_h = out_h[:class_start] + out_h[class_end:]
include_anchor = '#include "units_fwd.h"\n'
if include_anchor not in out_h:
    raise SystemExit('output.h include anchor missing')
out_h = out_h.replace(include_anchor,
                      include_anchor + '#include "ui_helpers/primitive/scrollbar.h"\n', 1)
out_h_path.write_text(out_h)

# Extract every scrollbar method from output.cpp into its own compilation unit.
signatures = [
    'scrollbar::scrollbar()',
    'scrollbar &scrollbar::offset_x(',
    'scrollbar &scrollbar::offset_y(',
    'scrollbar &scrollbar::content_size(',
    'scrollbar &scrollbar::viewport_pos(',
    'scrollbar &scrollbar::viewport_size(',
    'scrollbar &scrollbar::border_color(',
    'scrollbar &scrollbar::arrow_color(',
    'scrollbar &scrollbar::slot_color(',
    'scrollbar &scrollbar::bar_color(',
    'scrollbar &scrollbar::scroll_to_last(',
    'scrollbar &scrollbar::set_draggable(',
    'void scrollbar::apply(',
    'bool scrollbar::handle_dragging(',
]
methods = []
spans = []
for sig in signatures:
    start, end = function_span(out_cpp, sig)
    methods.append(out_cpp[start:end].strip())
    spans.append((start, end))
for start, end in sorted(spans, reverse=True):
    out_cpp = out_cpp[:start] + out_cpp[end:]
out_cpp_path.write_text(out_cpp)

scrollbar_cpp = '''#include "ui_helpers/primitive/scrollbar.h"\n\n#include <algorithm>\n#include <cmath>\n\n#include "input_context.h"\n#include "output.h"\n\n''' + '\n\n'.join(methods) + '\n'
Path('src/ui_helpers/primitive/scrollbar.cpp').write_text(scrollbar_cpp)

# ---------------------------------------------------------------------------
# Teach all supported build systems to compile organized helper .cpp files.
# ---------------------------------------------------------------------------
cmake_path = Path('src/CMakeLists.txt')
cmake = cmake_path.read_text()
cmake = replace_once(cmake,
'''file(GLOB CATACLYSM_DDA_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp)\n\nlist(REMOVE_ITEM CATACLYSM_DDA_SOURCES ${MAIN_CPP} ${MESSAGES_CPP})\n\nfile(GLOB CATACLYSM_DDA_HEADERS ${CMAKE_CURRENT_SOURCE_DIR}/*.h)\n''',
'''file(GLOB CATACLYSM_DDA_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp)\nfile(GLOB_RECURSE UI_HELPER_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/ui_helpers/*.cpp)\nlist(APPEND CATACLYSM_DDA_SOURCES ${UI_HELPER_SOURCES})\n\nlist(REMOVE_ITEM CATACLYSM_DDA_SOURCES ${MAIN_CPP} ${MESSAGES_CPP})\n\nfile(GLOB CATACLYSM_DDA_HEADERS ${CMAKE_CURRENT_SOURCE_DIR}/*.h)\nfile(GLOB_RECURSE UI_HELPER_HEADERS ${CMAKE_CURRENT_SOURCE_DIR}/ui_helpers/*.h)\nlist(APPEND CATACLYSM_DDA_HEADERS ${UI_HELPER_HEADERS})\n''',
'CMake helper source discovery')
cmake_path.write_text(cmake)

make_path = Path('Makefile')
make = make_path.read_text()
make = replace_once(make,
'''else\n  SOURCES := $(wildcard $(SRC_DIR)/*.cpp)\nendif\nTHIRD_PARTY_SOURCES := $(wildcard $(SRC_DIR)/third-party/flatbuffers/*.cpp)\n''',
'''else\n  SOURCES := $(wildcard $(SRC_DIR)/*.cpp)\nendif\nUI_HELPER_SOURCES := $(wildcard $(SRC_DIR)/ui_helpers/primitive/*.cpp $(SRC_DIR)/ui_helpers/controls/*.cpp $(SRC_DIR)/ui_helpers/models/*.cpp)\nSOURCES += $(UI_HELPER_SOURCES)\nTHIRD_PARTY_SOURCES := $(wildcard $(SRC_DIR)/third-party/flatbuffers/*.cpp)\n''',
'Make helper sources')
make = replace_once(make,
'HEADERS := $(wildcard $(SRC_DIR)/*.h)\n',
'HEADERS := $(wildcard $(SRC_DIR)/*.h $(SRC_DIR)/ui_helpers/*.h $(SRC_DIR)/ui_helpers/primitive/*.h $(SRC_DIR)/ui_helpers/controls/*.h $(SRC_DIR)/ui_helpers/models/*.h)\n',
'Make helper headers')
make_path.write_text(make)

msvc_path = Path('msvc-full-features/Cataclysm-lib-vcpkg-static.vcxproj')
msvc = msvc_path.read_text()
msvc = replace_once(msvc,
'''  <ItemGroup>\n    <ClInclude Include="..\\src\\*.h" Exclude="..\\src\\messages.h" />\n  </ItemGroup>\n  <ItemGroup>\n    <ClCompile Include="..\\src\\*.cpp" Exclude="..\\src\\main.cpp;..\\src\\messages.cpp" />\n  </ItemGroup>\n''',
'''  <ItemGroup>\n    <ClInclude Include="..\\src\\*.h" Exclude="..\\src\\messages.h" />\n    <ClInclude Include="..\\src\\ui_helpers\\*.h" />\n    <ClInclude Include="..\\src\\ui_helpers\\primitive\\*.h" />\n    <ClInclude Include="..\\src\\ui_helpers\\controls\\*.h" />\n    <ClInclude Include="..\\src\\ui_helpers\\models\\*.h" />\n  </ItemGroup>\n  <ItemGroup>\n    <ClCompile Include="..\\src\\*.cpp" Exclude="..\\src\\main.cpp;..\\src\\messages.cpp" />\n    <ClCompile Include="..\\src\\ui_helpers\\primitive\\*.cpp" />\n    <ClCompile Include="..\\src\\ui_helpers\\controls\\*.cpp" />\n    <ClCompile Include="..\\src\\ui_helpers\\models\\*.cpp" />\n  </ItemGroup>\n''',
'MSVC helper source discovery')
msvc_path.write_text(msvc)

# ---------------------------------------------------------------------------
# Sanity checks.
# ---------------------------------------------------------------------------
assert 'class scrollbar\n{' not in out_h
assert '#include "ui_helpers/primitive/scrollbar.h"' in out_h
assert 'scrollbar::scrollbar()' not in out_cpp
assert Path('src/ui_helpers/primitive/scrollbar.cpp').read_text().count('scrollbar::scrollbar()') == 1
assert 'class ui_multiselect_filter' not in Path('src/ui_helpers/controls/dropdown.h').read_text()
assert 'class ui_multiselect_filter' in Path('src/ui_helpers/models/multiselect_filter.h').read_text()
assert 'class ui_scroll_model' in Path('src/ui_helpers/models/scroll_model.h').read_text()
assert '#include "ui_helpers/primitive/overlay.h"' in Path('src/ui_helpers/controls/dropdown.h').read_text()
print('organized UI helpers and extracted scrollbar')
