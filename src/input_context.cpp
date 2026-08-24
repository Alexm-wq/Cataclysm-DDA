#include "input_context.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iterator>
#include <memory>
#include <optional>
#include <set>
#include <type_traits>
#include <utility>

#include "action.h"
#include "cata_imgui.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "color.h"
#include "coordinates.h"
#include "cuboid_rectangle.h"
#include "cursesdef.h"
#include "game.h"
#include "help.h"
#include "imgui/imgui.h"
#include "input.h"
#include "map.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "popup.h"
#include "sdltiles.h"
#include "string_formatter.h"
#include "string_input_popup.h"
#include "translations.h"
#include "ui_manager.h"

namespace
{
std::chrono::steady_clock::time_point aim_last_plain_click_time;
point aim_last_plain_click_pos = point::zero;
bool aim_has_last_plain_click = false;
const std::string aim_open_container_action = "ITEMS_CONTAINER";
constexpr std::chrono::milliseconds aim_double_click_interval( 400 );
} // namespace

// input_context_base.cpp.inc is the previous input_context.cpp verbatim.  Its
// headers are already included above, so this narrowly intercepts the one use
// of input_event::mouse_pos in handle_input() without changing the shared input
// event representation.  A quick second plain SELECT at the same screen point
// in ADVANCED_INVENTORY becomes the inventory's existing ITEMS_CONTAINER action.
#define mouse_pos mouse_pos; \
    if( category == "ADVANCED_INVENTORY" && action == "SELECT" && \
        next_action.type == input_event_t::mouse && next_action.modifiers.empty() ) { \
        const auto aim_click_now = std::chrono::steady_clock::now(); \
        const bool aim_is_double_click = aim_has_last_plain_click && \
                                         coordinate == aim_last_plain_click_pos && \
                                         aim_click_now - aim_last_plain_click_time <= \
                                         aim_double_click_interval; \
        aim_last_plain_click_time = aim_click_now; \
        aim_last_plain_click_pos = coordinate; \
        aim_has_last_plain_click = true; \
        if( aim_is_double_click ) { \
            aim_has_last_plain_click = false; \
            result = &aim_open_container_action; \
            break; \
        } \
    }

#include "input_context_base.cpp.inc"

#undef mouse_pos
