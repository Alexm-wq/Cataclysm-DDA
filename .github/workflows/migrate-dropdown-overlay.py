from pathlib import Path

path = Path('src/ui_helpers/dropdown.h')
text = path.read_text()

text = text.replace('#include "output.h"\n#include "point.h"\n', '#include "output.h"\n#include "point.h"\n#include "ui_helpers/overlay.h"\n', 1)

text = text.replace('''        void close() {\n            entries_.clear();\n            hovered_ = -1;\n            pos_ = point::zero;\n            width_ = 0;\n            height_ = 0;\n            window_ = catacurses::window();\n        }\n''', '''        void close() {\n            entries_.clear();\n            hovered_ = -1;\n            pos_ = point::zero;\n            width_ = 0;\n            height_ = 0;\n            overlay_.close();\n        }\n''', 1)

old_draw = '''        void draw( const catacurses::window &parent ) {\n            if( !is_open() ) {\n                window_ = catacurses::window();\n                return;\n            }\n\n            const point screen_pos( getbegx( parent ) + pos_.x, getbegy( parent ) + pos_.y );\n            const bool needs_window = !window_ || getmaxx( window_ ) != width_ ||\n                                      getmaxy( window_ ) != height_ ||\n                                      getbegx( window_ ) != screen_pos.x ||\n                                      getbegy( window_ ) != screen_pos.y;\n            if( needs_window ) {\n                window_ = catacurses::newwin( height_, width_, screen_pos );\n            }\n\n            werase( window_ );\n            draw_border( window_, style_.border );\n            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {\n                const ui_dropdown_entry &row = entries_[i];\n                const bool highlighted = i == hovered_ || row.selected;\n                const nc_color color = !row.enabled ? style_.disabled :\n                                       highlighted ? style_.highlight : style_.text;\n                const std::string label = row.checked.has_value() ?\n                                          string_format( *row.checked ? "[x] %s" : "[ ] %s", row.label ) :\n                                          row.label;\n                trim_and_print( window_, point( 1, i + 1 ), std::max( 1, width_ - 2 ), color,\n                                label );\n            }\n            wnoutrefresh( window_ );\n        }\n'''
new_draw = '''        void draw( const catacurses::window &parent ) {\n            if( !is_open() ) {\n                overlay_.close();\n                return;\n            }\n\n            overlay_.configure( parent, pos_, width_, height_ );\n            catacurses::window &window = overlay_.begin_draw( parent );\n            if( !window ) {\n                return;\n            }\n\n            draw_border( window, style_.border );\n            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {\n                const ui_dropdown_entry &row = entries_[i];\n                const bool highlighted = i == hovered_ || row.selected;\n                const nc_color color = !row.enabled ? style_.disabled :\n                                       highlighted ? style_.highlight : style_.text;\n                const std::string label = row.checked.has_value() ?\n                                          string_format( *row.checked ? "[x] %s" : "[ ] %s", row.label ) :\n                                          row.label;\n                trim_and_print( window, point( 1, i + 1 ), std::max( 1, width_ - 2 ), color,\n                                label );\n            }\n            overlay_.refresh();\n        }\n'''
if text.count(old_draw) != 1:
    raise SystemExit('dropdown draw block mismatch')
text = text.replace(old_draw, new_draw, 1)

text = text.replace('''    private:\n        catacurses::window window_;\n        std::vector<ui_dropdown_entry> entries_;\n''', '''    private:\n        ui_overlay overlay_;\n        std::vector<ui_dropdown_entry> entries_;\n''', 1)

if 'catacurses::window window_;' in text:
    raise SystemExit('raw dropdown backing window still present')
if 'ui_overlay overlay_;' not in text:
    raise SystemExit('overlay member missing')
if 'overlay_.begin_draw( parent )' not in text or 'overlay_.refresh()' not in text:
    raise SystemExit('overlay draw path missing')

path.write_text(text)
print('ui_dropdown now composes flicker-safe ui_overlay')
