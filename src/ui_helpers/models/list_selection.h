#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_LIST_SELECTION_H
#define CATA_SRC_UI_HELPERS_MODELS_LIST_SELECTION_H

#include <algorithm>
#include <vector>

#include "double_click_tracker.h"

enum class ui_list_row_highlight {
    none,
    focused,
    selected
};

/** Single-selection lists highlight their cursor, not a competing hover row.
 * Explicit multi-selected rows keep their selection emphasis while another row
 * is being browsed.
 */
inline ui_list_row_highlight ui_list_highlight( const int index, const int cursor,
        const int hovered, const bool selected, const bool multiple )
{
    const bool focused = index == ( multiple && hovered >= 0 ? hovered : cursor );
    if( selected && ( multiple || focused ) ) {
        return ui_list_row_highlight::selected;
    }
    return focused ? ui_list_row_highlight::focused : ui_list_row_highlight::none;
}

/** Hover previews a single-selection list only until a choice is selected.
 * Afterwards the cursor moves by click or keyboard, so crossing other rows on
 * the way to a confirmation button cannot hide the selected choice.
 */
inline int ui_list_cursor_after_hover( const int cursor, const int hovered,
                                      const std::vector<bool> &selected, const bool multiple )
{
    const bool preview = !multiple && hovered >= 0 &&
                         std::find( selected.begin(), selected.end(), true ) == selected.end();
    return preview ? hovered : cursor;
}

/** Shared Ctrl/Shift selection and activation for ordered lists. */
class ui_list_selection
{
    public:
        using time_point = ui_double_click_tracker<int>::time_point;

        void reset() {
            anchor_ = -1;
            clicks_.reset();
        }

        void set_anchor( int index ) {
            anchor_ = index;
            clicks_.reset();
        }

        /** Returns true on an unmodified double-click of an enabled row.
         * Re-clicking a selected row preserves a multi-selection for activation.
         * Call reset() whenever the row identities or their order change.
         */
        template<typename Enabled>
        bool click( std::vector<bool> &selected, int index, const Enabled &enabled,
                    bool ctrl, bool shift,
                    time_point now = ui_double_click_tracker<int>::clock::now() ) {
            const int count = static_cast<int>( selected.size() );
            if( index < 0 || index >= count || !enabled( index ) ) {
                clicks_.reset();
                return false;
            }
            if( anchor_ >= count ) {
                anchor_ = -1;
            }
            const bool activate = !ctrl && !shift && clicks_.click( index, now );
            if( ctrl || shift ) {
                clicks_.reset();
            }
            if( shift && anchor_ >= 0 ) {
                if( !ctrl ) {
                    std::fill( selected.begin(), selected.end(), false );
                }
                for( int i = std::min( anchor_, index ); i <= std::max( anchor_, index ); ++i ) {
                    if( enabled( i ) ) {
                        selected[i] = true;
                    }
                }
            } else if( ctrl ) {
                selected[index] = !selected[index];
                anchor_ = index;
            } else if( !selected[index] ) {
                std::fill( selected.begin(), selected.end(), false );
                selected[index] = true;
                anchor_ = index;
            } else if( anchor_ < 0 ) {
                anchor_ = index;
            }
            return activate;
        }

    private:
        int anchor_ = -1;
        ui_double_click_tracker<int> clicks_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_LIST_SELECTION_H
