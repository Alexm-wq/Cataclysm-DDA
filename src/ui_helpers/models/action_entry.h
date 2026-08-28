#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_ACTION_ENTRY_H
#define CATA_SRC_UI_HELPERS_MODELS_ACTION_ENTRY_H

#include <optional>
#include <string>
#include <utility>

/** Optional semantic emphasis; the owning control supplies its palette. */
enum class ui_action_tone {
    normal,
    positive
};

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
    // Semantic affordance: this action opens a transient dropdown/menu.
    bool dropdown = false;
    ui_action_tone tone = ui_action_tone::normal;

    ui_action_entry() = default;
    ui_action_entry( std::string label, std::string id, const bool enabled = true,
                     const bool selected = false, std::string disabled_reason = std::string(),
                     const std::optional<bool> checked = std::nullopt, const bool dropdown = false ) :
        label( std::move( label ) ), id( std::move( id ) ), enabled( enabled ), selected( selected ),
        disabled_reason( std::move( disabled_reason ) ), checked( checked ), dropdown( dropdown ) {}
};

enum class ui_outside_click_policy : int {
    consume,
    passthrough
};

inline bool ui_outside_pointer_passthrough( const ui_outside_click_policy policy,
        const bool over_trigger )
{
    return policy == ui_outside_click_policy::passthrough && !over_trigger;
}

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
    // A transient control may close while allowing this same pointer event to
    // continue to the list, scrollbar, or action underneath it.
    bool passthrough = false;

    bool consumed() const {
        return type != ui_action_result_type::ignored && !passthrough;
    }
    bool passes_through() const {
        return passthrough;
    }
};

#endif // CATA_SRC_UI_HELPERS_MODELS_ACTION_ENTRY_H
