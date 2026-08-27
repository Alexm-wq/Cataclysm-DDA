from pathlib import Path

replacements = {
    'src/ui_helpers/controls/dropdown.h': {
        '#include "catacharset.h"': '#include "../../catacharset.h"',
        '#include "color.h"': '#include "../../color.h"',
        '#include "cursesdef.h"': '#include "../../cursesdef.h"',
        '#include "output.h"': '#include "../../output.h"',
        '#include "point.h"': '#include "../../point.h"',
        '#include "ui_helpers/primitive/overlay.h"': '#include "../primitive/overlay.h"',
    },
    'src/ui_helpers/primitive/overlay.h': {
        '#include "cursesdef.h"': '#include "../../cursesdef.h"',
        '#include "point.h"': '#include "../../point.h"',
    },
    'src/ui_helpers/primitive/scrollbar.h': {
        '#include "color.h"': '#include "../../color.h"',
        '#include "cuboid_rectangle.h"': '#include "../../cuboid_rectangle.h"',
        '#include "cursesdef.h"': '#include "../../cursesdef.h"',
        '#include "point.h"': '#include "../../point.h"',
        '#include "ui_helpers/models/scroll_model.h"': '#include "../models/scroll_model.h"',
    },
    'src/ui_helpers/primitive/scrollbar.cpp': {
        '#include "ui_helpers/primitive/scrollbar.h"': '#include "scrollbar.h"',
        '#include "cata_utility.h"': '#include "../../cata_utility.h"',
        '#include "input_context.h"': '#include "../../input_context.h"',
        '#include "output.h"': '#include "../../output.h"',
    },
    'src/ui_helpers/dropdown.h': {
        '#include "ui_helpers/controls/dropdown.h"': '#include "controls/dropdown.h"',
        '#include "ui_helpers/models/multiselect_filter.h"': '#include "models/multiselect_filter.h"',
    },
    'src/ui_helpers/overlay.h': {
        '#include "ui_helpers/primitive/overlay.h"': '#include "primitive/overlay.h"',
    },
}

for filename, changes in replacements.items():
    path = Path(filename)
    text = path.read_text()
    for old, new in changes.items():
        if text.count(old) != 1:
            raise SystemExit(f'{filename}: expected one {old!r}, got {text.count(old)}')
        text = text.replace(old, new, 1)
    path.write_text(text)

print('made ui helper internal includes location-independent')
