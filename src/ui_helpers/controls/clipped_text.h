#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_CLIPPED_TEXT_H
#define CATA_SRC_UI_HELPERS_CONTROLS_CLIPPED_TEXT_H

#include <string>

#include "../../cuboid_rectangle.h"
#include "../../point.h"

namespace catacurses
{
class window;
}
struct input_event;
class nc_color;

/** Shared hover expansion for trim_and_print, without screen-specific input
 * handlers. Only the top UI records targets; the tooltip never captures input.
 * UI bounds and input positions use renderer pixels in TILES, text cells otherwise.
 */
namespace ui_clipped_text
{
void set_context( const void *owner, const rectangle<point> &bounds );
void forget_context( const void *owner );
void begin_frame();
void end_frame();
void record( const catacurses::window &window, const point &pos, int width,
             const nc_color &base_color, const std::string &text );
void erase_window( const catacurses::window &window );
void present_window( const catacurses::window &window );
bool handle_input( const input_event &event );
void draw();
}

#endif // CATA_SRC_UI_HELPERS_CONTROLS_CLIPPED_TEXT_H
