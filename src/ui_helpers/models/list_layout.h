#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_LIST_LAYOUT_H
#define CATA_SRC_UI_HELPERS_MODELS_LIST_LAYOUT_H

#include <algorithm>

/** Text-cell columns, keeping one cell for the scrollbar and a gap before hints. */
struct ui_list_columns {
    int label_width = 0;
    int hint_x = 0;
    int hint_width = 0;
};

inline ui_list_columns ui_list_columns_for_width( const int width, const int requested_hint_width )
{
    const int content_width = std::max( 0, width - 1 );
    const int hint_width = std::clamp( requested_hint_width, 0, std::max( 0, width - 2 ) / 2 );
    const int hint_x = content_width - hint_width;
    return { hint_x - ( hint_width > 0 ? 1 : 0 ), hint_x, hint_width };
}

#endif // CATA_SRC_UI_HELPERS_MODELS_LIST_LAYOUT_H
