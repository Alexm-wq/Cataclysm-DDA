#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_ACTION_ENTRY_H
#define CATA_SRC_UI_HELPERS_MODELS_ACTION_ENTRY_H

#include <optional>
#include <string>
#include <utility>

/** Renderer-independent description of an action exposed by a UI control. */
struct ui_action_entry {
    std::string label;
    std::string id;
    bool enabled = true;
    bool selected = false;
    // Keep disabled_reason before optional extension fields so historical
    // aggregate initializers retain { label, id, enabled, selected, reason }.
    std::string disabled_reason;
    std::optional<bool> checked;

    ui_action_entry() = default;
    ui_action_entry( std::string label, std::string id, const bool enabled = true,
                     const bool selected = false, std::string disabled_reason = std::string(),
                     const std::optional<bool> checked = std::nullopt ) :
        label( std::move( label ) ), id( std::move( id ) ), enabled( enabled ), selected( selected ),
        disabled_reason( std::move( disabled_reason ) ), checked( checked ) {}
};

enum class ui_action_result_type : int {
    ignored,
    handled,
    closed,
    activated,
    disabled
};

/** Result returned by reusable action controls after handling one input event. */
struct ui_action_result {
    ui_action_result_type type = ui_action_result_type::ignored;
    std::optional<ui_action_entry> entry;

    bool consumed() const {
        return type != ui_action_result_type::ignored;
    }
};

#endif // CATA_SRC_UI_HELPERS_MODELS_ACTION_ENTRY_H
