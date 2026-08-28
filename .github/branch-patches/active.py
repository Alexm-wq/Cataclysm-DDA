from pathlib import Path
import subprocess


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected block not found in {path_str}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# The menu picker opts into single-click activation without changing the default
# selection-list contract used by existing screens.
replace_once(
    "src/ui_helpers/controls/selection_list.h",
    """        void set_entries( std::vector<ui_action_entry> entries, bool multiple = true ) {\n            entries_ = std::move( entries );\n""",
    """        void set_entries( std::vector<ui_action_entry> entries, bool multiple = true ) {\n            entries_ = std::move( entries );\n""",
)
replace_once(
    "src/ui_helpers/controls/selection_list.h",
    """            hits_.clear();\n        }\n\n        void draw( const catacurses::window &window, const point &origin, int width, int height,\n""",
    """            hits_.clear();\n        }\n\n        /** Opt in to immediate activation for single-select picker rows. */\n        void activate_on_single_click( const bool value = true ) {\n            activate_on_single_click_ = value;\n        }\n\n        void draw( const catacurses::window &window, const point &origin, int width, int height,\n""",
)
replace_once(
    "src/ui_helpers/controls/selection_list.h",
    """                if( !multiple_ ) {\n                    select_only( cursor_ );\n                }\n""",
    """                if( !multiple_ ) {\n                    select_only( cursor_ );\n                    if( activate_on_single_click_ ) {\n                        activate = true;\n                    }\n                }\n""",
)
replace_once(
    "src/ui_helpers/controls/selection_list.h",
    """        int cursor_ = 0;\n        int hovered_ = -1;\n        bool multiple_ = true;\n""",
    """        int cursor_ = 0;\n        int hovered_ = -1;\n        bool multiple_ = true;\n        bool activate_on_single_click_ = false;\n""",
)

# The pixel icon helper already handles the HUD geometry.  Add a generic one-cell
# glyph fallback so assigned keybindings and '?' can be rendered by the same helper.
replace_once(
    "src/sdltiles.cpp",
    """    } else if( button.icon == \"<\" ) {\n        const int scale = std::max( 1, std::min( inner_w / 3, inner_h / 5 ) );\n        const int total_w = 3 * scale;\n        const int total_h = 5 * scale;\n        const int left = button.pos_pixels.x + ( button.size_pixels.x - total_w ) / 2;\n        const int top = button.pos_pixels.y + ( button.size_pixels.y - total_h ) / 2;\n        draw_glyph( glyph_chevron_left, left, top, scale );\n    }\n}\n""",
    """    } else if( button.icon == \"<\" ) {\n        const int scale = std::max( 1, std::min( inner_w / 3, inner_h / 5 ) );\n        const int total_w = 3 * scale;\n        const int total_h = 5 * scale;\n        const int left = button.pos_pixels.x + ( button.size_pixels.x - total_w ) / 2;\n        const int top = button.pos_pixels.y + ( button.size_pixels.y - total_h ) / 2;\n        draw_glyph( glyph_chevron_left, left, top, scale );\n    } else if( font && utf8_width( button.icon ) == 1 ) {\n        const int pair = std::clamp( button.icon_color_pair, 0,\n                         static_cast<int>( cata_cursesport::colorpairs.size() ) - 1 );\n        const int left = button.pos_pixels.x + ( button.size_pixels.x - font->width ) / 2;\n        const int top = button.pos_pixels.y + ( button.size_pixels.y - font->height ) / 2;\n        draw_string( *font, renderer, geometry, button.icon, point( left, top ),\n                     cata_cursesport::colorpairs[pair].FG );\n    }\n}\n""",
)

# Compose the new picker entirely from reusable controls.
replace_once(
    "src/game.cpp",
    """#include <algorithm>\n#include <bitset>\n""",
    """#include <algorithm>\n#include <array>\n#include <bitset>\n""",
)
replace_once(
    "src/game.cpp",
    """#include \"ui_extended_description.h\"\n#include \"ui_manager.h\"\n#include \"uistate.h\"\n""",
    """#include \"ui_extended_description.h\"\n#include \"ui_manager.h\"\n#include \"ui_helpers/controls/action_strip.h\"\n#include \"ui_helpers/controls/selection_list.h\"\n#include \"ui_helpers/controls/text_field.h\"\n#include \"uistate.h\"\n""",
)
replace_once(
    "src/game.cpp",
    """static constexpr int safemode_corner_button_count = 6;\nstatic constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;\n\n#if defined(TILES)\n""",
    """static constexpr int safemode_corner_button_count = 6;\nstatic constexpr int safemode_corner_safe_index = safemode_corner_button_count - 1;\nstatic std::array<action_id, safemode_corner_safe_index> safemode_corner_menu_slots{};\n\nstruct safemode_corner_menu_candidate {\n    action_id action = ACTION_NULL;\n    std::string label;\n    std::string category;\n};\n\nstatic std::vector<safemode_corner_menu_candidate> safemode_corner_menu_candidates()\n{\n    // Deliberately whitelist only top-level interfaces that make sense from normal map play.\n    // Contextual operations such as refuel/reload/open/smash never enter this picker.\n    return {\n        { ACTION_INVENTORY, _( \"Inventory\" ), _( \"Inventory\" ) },\n        { ACTION_ITEMACTION, _( \"Item actions\" ), _( \"Inventory\" ) },\n        { ACTION_BIONICS, _( \"Bionics\" ), _( \"Inventory\" ) },\n        { ACTION_MUTATIONS, _( \"Mutations\" ), _( \"Inventory\" ) },\n        { ACTION_CRAFT, _( \"Crafting\" ), _( \"Crafting\" ) },\n        { ACTION_CONSTRUCT, _( \"Construction\" ), _( \"Crafting\" ) },\n        { ACTION_MAP, _( \"Map\" ), _( \"World\" ) },\n        { ACTION_ZONES, _( \"Zone manager\" ), _( \"World\" ) },\n        { ACTION_LIST_ITEMS, _( \"Nearby items\" ), _( \"World\" ) },\n        { ACTION_PL_INFO, _( \"Character info\" ), _( \"Character\" ) },\n        { ACTION_MEDICAL, _( \"Medical\" ), _( \"Character\" ) },\n        { ACTION_BODYSTATUS, _( \"Body status\" ), _( \"Character\" ) },\n        { ACTION_MORALE, _( \"Morale\" ), _( \"Character\" ) },\n        { ACTION_MISSIONS, _( \"Missions\" ), _( \"Information\" ) },\n        { ACTION_FACTIONS, _( \"Factions\" ), _( \"Information\" ) },\n        { ACTION_MESSAGES, _( \"Messages\" ), _( \"Information\" ) },\n        { ACTION_DIARY, _( \"Diary\" ), _( \"Information\" ) },\n        { ACTION_ACTIONMENU, _( \"Action menu\" ), _( \"General\" ) },\n        { ACTION_OPEN_MOVEMENT, _( \"Movement mode\" ), _( \"General\" ) }\n    };\n}\n\nstatic std::string safemode_corner_action_icon( const action_id action )\n{\n    if( action == ACTION_NULL ) {\n        return \"?\";\n    }\n    const std::optional<input_event> key = hotkey_for_action( action, 0, true );\n    if( !key ) {\n        return \"?\";\n    }\n    const std::string label = key->short_description();\n    return utf8_width( label ) == 1 ? label : \"?\";\n}\n\n#if defined(TILES)\n""",
)

# Insert the modal picker immediately before the HUD draw function.
replace_once(
    "src/game.cpp",
    """void game::draw_safemode_mouse_controls()\n{\n""",
    """static std::optional<action_id> query_safemode_corner_menu()\n{\n    const int width = std::min( 68, TERMX - 4 );\n    const int height = std::min( 24, TERMY - 4 );\n    if( width < 32 || height < 12 ) {\n        return std::nullopt;\n    }\n\n    const point origin( std::max( 0, ( TERMX - width ) / 2 ),\n                        std::max( 0, ( TERMY - height ) / 2 ) );\n    catacurses::window window = catacurses::newwin( height, width, origin );\n    ui_text_field search_field;\n    ui_action_strip categories;\n    ui_action_strip navigation;\n    ui_selection_list menu_list;\n    menu_list.activate_on_single_click();\n\n    input_context ctxt( \"SAFE_CORNER_MENU_PICKER\" );\n    for( const std::string &action : { \"UP\", \"DOWN\", \"PAGE_UP\", \"PAGE_DOWN\",\n                                      \"HOME\", \"END\", \"CONFIRM\", \"QUIT\", \"SELECT\",\n                                      \"MOUSE_MOVE\", \"SCROLL_UP\", \"SCROLL_DOWN\" } ) {\n        ctxt.register_action( action );\n    }\n\n    std::string search;\n    const std::vector<safemode_corner_menu_candidate> candidates = safemode_corner_menu_candidates();\n    const auto rebuild_list = [&]() {\n        std::vector<ui_action_entry> entries;\n        for( const safemode_corner_menu_candidate &candidate : candidates ) {\n            if( !search.empty() && !lcmatch( candidate.label, search ) &&\n                !lcmatch( candidate.category, search ) ) {\n                continue;\n            }\n            entries.emplace_back( candidate.label, action_ident( candidate.action ) );\n        }\n        menu_list.set_entries( std::move( entries ), false );\n    };\n    rebuild_list();\n\n    const auto edit_search = [&]() {\n        string_input_popup popup;\n        popup.window( window, search_field.edit_start(), search_field.edit_end_x() )\n        .text( search )\n        .max_length( 60 )\n        .string_color( c_white )\n        .cursor_color( h_light_gray )\n        .underscore_color( c_light_gray );\n        popup.query();\n        if( !popup.canceled() ) {\n            search = popup.text();\n            rebuild_list();\n        }\n    };\n\n    while( true ) {\n        werase( window );\n        draw_border( window, c_light_gray );\n        trim_and_print( window, point( 2, 1 ), width - 4, c_light_green, _( \"Assign menu shortcut\" ) );\n\n        const std::vector<ui_action_strip_item> nav_items = {\n            { ui_action_entry( _( \"Back\" ), \"BACK\" ), 0, ui_action_alignment::right }\n        };\n        navigation.configure( window, point( 2, 1 ), nav_items, width - 4, 1 );\n        navigation.draw( window );\n\n        search_field.configure( window, point( 2, 3 ), width - 4, _( \"Search: \" ), search,\n                                _( \"menu name\" ), true );\n        search_field.draw( window );\n\n        ui_action_strip_style category_style;\n        category_style.text = c_light_cyan;\n        category_style.selected = h_light_cyan;\n        category_style.disabled = c_dark_gray;\n        categories.configure( window, point( 2, 5 ), {\n            ui_action_entry( _( \"All\" ), \"CATEGORY_ALL\", true, true ),\n            ui_action_entry( _( \"Inventory\" ), \"CATEGORY_INVENTORY\", false ),\n            ui_action_entry( _( \"Crafting\" ), \"CATEGORY_CRAFTING\", false ),\n            ui_action_entry( _( \"World\" ), \"CATEGORY_WORLD\", false ),\n            ui_action_entry( _( \"Character\" ), \"CATEGORY_CHARACTER\", false ),\n            ui_action_entry( _( \"Info\" ), \"CATEGORY_INFO\", false )\n        }, width - 4, 2, category_style );\n        categories.draw( window );\n\n        trim_and_print( window, point( 2, 7 ), width - 4, c_light_gray,\n                        _( \"Available map menus\" ) );\n        menu_list.draw( window, point( 2, 8 ), width - 4, std::max( 1, height - 10 ) );\n        wnoutrefresh( window );\n\n        const std::string action = ctxt.handle_input();\n        const std::optional<point> pos = ctxt.get_coordinates_text( window );\n        if( action == \"QUIT\" ) {\n            return std::nullopt;\n        }\n\n        if( action == \"MOUSE_MOVE\" || action == \"SELECT\" ) {\n            const ui_action_result back_result = navigation.handle_input( action, pos );\n            if( back_result.type == ui_action_result_type::activated ) {\n                return std::nullopt;\n            }\n            const ui_action_result category_result = categories.handle_input( action, pos );\n            if( action == \"SELECT\" && category_result.consumed() ) {\n                continue;\n            }\n        }\n\n        if( action == \"SELECT\" && pos ) {\n            const ui_text_field_hit search_hit = search_field.hit_test( *pos );\n            if( search_hit == ui_text_field_hit::clear ) {\n                if( !search.empty() ) {\n                    search.clear();\n                    rebuild_list();\n                }\n                continue;\n            }\n            if( search_hit == ui_text_field_hit::edit ) {\n                edit_search();\n                continue;\n            }\n        }\n\n        const ui_action_result list_result = menu_list.handle_input( action, ctxt, pos );\n        if( list_result.type == ui_action_result_type::activated && list_result.entry ) {\n            const action_id selected = look_up_action( list_result.entry->id );\n            if( selected != ACTION_NULL ) {\n                return selected;\n            }\n        }\n    }\n}\n\nvoid game::draw_safemode_mouse_controls()\n{\n""",
)

# Make each assignable slot enabled and use its assigned key (or '?') as the icon.
replace_once(
    "src/game.cpp",
    """            const bool is_safe = i == safemode_corner_safe_index;\n            ui_icon_button_style style;\n            ui_action_entry action( \"\", is_safe ? \"SAFE_MODE_TOGGLE\" :\n                                    string_format( \"SAFE_RESERVED_%d\", i ), is_safe );\n            std::string icon = is_safe ? \"[!]\" : \"■\";\n\n            style.border = c_light_gray;\n""",
    """            const bool is_safe = i == safemode_corner_safe_index;\n            ui_icon_button_style style;\n            ui_action_entry action( \"\", is_safe ? \"SAFE_MODE_TOGGLE\" :\n                                    string_format( \"SAFE_SLOT_%d\", i ) );\n            const std::string icon = is_safe ? \"[!]\" :\n                                     safemode_corner_action_icon( safemode_corner_menu_slots[i] );\n\n            style.border = c_light_gray;\n""",
)
replace_once(
    "src/game.cpp",
    """            } else {\n                // Reserved cells stay disabled, but remain visually present as one grey tile.\n                style.disabled_border = c_light_gray;\n                style.disabled_icon = c_light_gray;\n            }\n""",
    """            } else {\n                style.icon = c_light_gray;\n                style.hover_icon = c_white;\n                style.selected_icon = c_white;\n            }\n""",
)

# Empty slots open the picker; assigned slots return their actual map action.
replace_once(
    "src/game.cpp",
    """                if( result.type == ui_action_result_type::activated && result.entry &&\n                    result.entry->id == \"SAFE_MODE_TOGGLE\" ) {\n                    safemode_corner_tooltip.clear_pointer();\n                    invalidate_main_ui_adaptor();\n                    return ACTION_TOGGLE_SAFEMODE;\n                }\n                if( result.type == ui_action_result_type::disabled ) {\n                    return ACTION_CLICK_AND_DRAG;\n                }\n""",
    """                if( result.type == ui_action_result_type::activated && result.entry ) {\n                    safemode_corner_tooltip.clear_pointer();\n                    if( result.entry->id == \"SAFE_MODE_TOGGLE\" ) {\n                        invalidate_main_ui_adaptor();\n                        return ACTION_TOGGLE_SAFEMODE;\n                    }\n                    if( i < safemode_corner_safe_index ) {\n                        if( safemode_corner_menu_slots[i] != ACTION_NULL ) {\n                            return safemode_corner_menu_slots[i];\n                        }\n                        const std::optional<action_id> selected = query_safemode_corner_menu();\n                        if( selected ) {\n                            safemode_corner_menu_slots[i] = *selected;\n                        }\n                        invalidate_main_ui_adaptor();\n                        ui_manager::redraw_invalidated();\n                        return ACTION_CLICK_AND_DRAG;\n                    }\n                }\n""",
)

subprocess.run(["git", "diff", "--check"], check=True)
