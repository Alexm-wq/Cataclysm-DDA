#pragma once
#ifndef CATA_SRC_TILE_CONTEXT_PROVIDERS_H
#define CATA_SRC_TILE_CONTEXT_PROVIDERS_H

#include <vector>

#include "tile_context.h"

/** Add the deliberately small set of actions whose target is the avatar itself. */
void add_self_tile_context_actions( const tile_context_snapshot &snapshot,
                                    std::vector<tile_context_action> &actions );

/** Add first-pass actions whose target is terrain/furniture at the clicked coordinate. */
void add_basic_tile_context_actions( const tile_context_snapshot &snapshot,
                                     std::vector<tile_context_action> &actions );

/** Collect the first-pass self + tile providers without executing anything. */
std::vector<tile_context_action> collect_basic_tile_context_actions(
    const tile_context_snapshot &snapshot );

#endif // CATA_SRC_TILE_CONTEXT_PROVIDERS_H
