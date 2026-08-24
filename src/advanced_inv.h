#pragma once
#ifndef CATA_SRC_ADVANCED_INV_H
#define CATA_SRC_ADVANCED_INV_H

#include <array>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "advanced_inv_area.h"
#include "advanced_inv_pane.h"
#include "cursesdef.h"
#include "ret_val.h"

class Character;
class advanced_inv_listitem;
class drop_or_stash_item_info;
class input_context;
class string_input_popup;
class ui_adaptor;
struct advanced_inv_save_state;

/**
 * Player-facing entry points for the unified inventory workspace.  Presets only
 * choose the initial two-pane layout; they never change item rules or move costs.
 */
enum class inventory_workspace_preset : int {
    manage,
    pickup,
    pickup_all,
    drop,
    wear,
    take_off,
    wield,
    reload
};

struct inventory_workspace_entry {
    inventory_workspace_preset preset = inventory_workspace_preset::manage;
    std::optional<tripoint_bub_ms> target;
};

void create_advanced_inv();
void create_advanced_inv( const inventory_workspace_entry &entry );

/**
 * Cancels ongoing move all action.
 * TODO: Make this not needed.
 */
void cancel_aim_processing();

class advanced_inventory
{
    public:
        explicit advanced_inventory( const inventory_workspace_entry &entry = {} );
        ~advanced_inventory();

        void display();
        void temp_hide();

        void init();

        void process_action( const std::string &input_action );
        /**
         * Converts from screen relative location to game-space relative location
         * for control rotation in isometric mode.
        */
        aim_location screen_relative_location( aim_location area );
        std::string get_location_key( aim_location area );

        advanced_inv_area &get_one_square( const aim_location &loc ) {
            return squares[loc];
        }

        /**
         * Refers to the two panes, used as index into @ref panes.
         */
        enum side {
            left  = 0,
            right = 1,
            NUM_PANES = 2
        };

        void recalc_pane( side p );

        side get_src() {
            return src;
        }
        side get_dest() {
            return dest;
        }

        advanced_inventory_pane &get_pane( side side ) {
            return panes[side];
        }
    private:

        static constexpr int head_height = 5;
        bool move_all_items_and_waiting_to_quit = false;

        std::unique_ptr<ui_adaptor> ui;
        std::unique_ptr<string_input_popup> spopup;

        // swap the panes and windows via std::swap()
        void swap_panes();

        // minimap that displays things around character
        catacurses::window minimap;
        catacurses::window mm_border;
        const int minimap_width  = 3;
        const int minimap_height = 3;
        void draw_minimap();
        void refresh_minimap();
        char get_minimap_sym( side p ) const;

        bool inCategoryMode = false;

        int linesPerPage = 0;
        int w_height = 0;
        int w_width = 0;

        int headstart = 0;
        int colstart = 0;

        bool recalc = false;
        bool always_recalc = false;

        /**
         * Mouse drag state.  Item locations remain valid while the AIM is open and
         * let a drag finish in the other pane without bypassing the normal move
         * activity and its move cost.
         */
        item_location mouse_drag_item;
        std::optional<side> mouse_drag_side;
        item_location mouse_pressed_item;
        std::optional<side> mouse_pressed_side;
        point mouse_pressed_point = point::zero;
        std::optional<side> mouse_hover_side;
        point mouse_hover_point = point::zero;

        struct action_button {
            std::string label;
            point pos = point::zero;
            int width = 0;
            std::string action;
            std::string disabled_reason;
            bool enabled = true;
        };
        struct sort_button {
            advanced_inv_sortby mode = SORTBY_NONE;
            std::string label;
            point pos = point::zero;
            int width = 0;
        };
        inventory_workspace_entry entry;
        bool context_actions_open = false;
        bool context_use_methods_open = false;
        std::optional<side> context_menu_side;
        point context_menu_anchor = point::zero;
        point context_menu_pos = point::zero;
        int context_menu_width = 0;
        int context_menu_height = 0;
        bool context_click_started = false;
        std::string context_pressed_action;
        std::vector<action_button> action_buttons;
        bool sort_dropdown_open = false;
        std::optional<side> sort_dropdown_side;
        point sort_dropdown_pos = point::zero;
        int sort_dropdown_width = 0;
        int sort_dropdown_height = 0;
        bool sort_click_started = false;
        std::optional<side> sort_pressed_side;
        std::optional<advanced_inv_sortby> sort_pressed_mode;
        std::array<int, NUM_PANES> sort_button_width{};
        std::vector<sort_button> sort_buttons;
        /** Inline expansion is persisted per visual pane; the two views may expand differently. */
        std::array<std::vector<item_location>, NUM_PANES> expanded_inline_containers;
        /** Ctrl-click selections are stable item locations, independent of sorting and indentation. */
        std::array<std::vector<item_location>, NUM_PANES> multi_selected_rows;
        /** Rows rejected by the destination currently under a batch drag. */
        std::vector<item_location> batch_blocked_rows;
        item_location batch_blocked_destination;
        std::string batch_blocked_reason;
        std::string batch_blocked_details;
        bool mouse_pressed_multi = false;
        std::string workspace_status;
        /**
         * Which panels is active (item moved from there).
         */
        side src;
        /**
         * Which panel is the destination (items want to go to there).
         */
        side dest;
        /**
         * True if (and only if) the filter of the active panel is currently
         * being edited.
         */
        bool filter_edit = false;
        /**
         * Two panels (left and right) showing the items, use a value of @ref side
         * as index.
         */
        std::array<advanced_inventory_pane, NUM_PANES> panes;
        static const advanced_inventory_pane null_pane;
        std::array<advanced_inv_area, NUM_AIM_LOCATIONS> squares;

        catacurses::window head;

        bool exit = false;

        advanced_inv_save_state *save_state;

        /**
         * registers all the ctxt for display()
         */
        input_context register_ctxt() const;
        /**
         * Handle native mouse input for the two panes and the adjacent-tile map.
         * Returns true when the input has been consumed.
         */
        bool handle_mouse( const input_context &ctxt, const std::string &action );
        /** Return the item index displayed on a pane row, or -1. */
        int item_index_at_row( const advanced_inventory_pane &pane, int row ) const;
        /** Return the visible row for an item index, or -1 when it is on another page. */
        int item_row_for_index( const advanced_inventory_pane &pane, int index ) const;
        /** Handle a click on one of the location buttons drawn in a pane header. */
        bool handle_location_click( side pane_side, const point &p );
        /** Apply the initial layout requested by pickup/drop/wear/etc. */
        void apply_entry_preset();
        /** Draw the workspace status lines above the two panes. */
        void redraw_action_strip();
        /** Draw the right-click dropdown beside its item row. */
        void draw_context_menu();
        void close_context_menu();
        bool handle_action_click( const point &p );
        bool run_context_action( const std::string &action );
        std::vector<advanced_inv_listitem> selected_entries( side pane_side ) const;
        ret_val<void> validate_batch_entry( const advanced_inv_listitem &entry,
                                            aim_location destination,
                                            const item_location &destination_container ) const;
        void preview_batch_transfer( side source_side, side destination_side, aim_location destination,
                                     const item_location &destination_container );
        bool move_selected_items( side source_side, side destination_side, aim_location destination,
                                  const item_location &destination_container );
        /** Draw and handle the pane-local dropdown opened by its Sort by button. */
        void open_sort_dropdown( side pane_side );
        void close_sort_dropdown();
        void draw_sort_dropdown();
        bool handle_sort_click( const point &p );
        void set_sort_mode( side pane_side, advanced_inv_sortby mode );
        /** Draw the dragged item name beside the cursor in the tile build. */
        void draw_drag_ghost();
        /** User-visible status plus optional detailed debug.log event. */
        void set_workspace_status( const std::string &message, bool log_event = true );
        void log_workspace_event( const std::string &event ) const;
        bool location_has_items( aim_location location ) const;
        bool location_is_dangerous( aim_location location ) const;
        bool location_is_fully_blocked( aim_location location ) const;
        bool is_inline_container_expanded( side pane_side,
                                           const item_location &container ) const;
        void toggle_inline_container( side pane_side, const item_location &container );
        /**
         *  a smaller chunk of display()
         */
        bool start_activity( aim_location destarea, aim_location srcarea,
                             advanced_inv_listitem *sitem, int &amount_to_move,
                             bool from_vehicle, bool to_vehicle );

        /**
         * returns whether the display loop exits or not
         */
        bool action_move_item( advanced_inv_listitem *sitem,
                               advanced_inventory_pane &dpane, const advanced_inventory_pane &spane,
                               const std::string &action );

        /** Move a dragged item into an exact container without changing either pane's view. */
        bool action_move_item_to_container( advanced_inv_listitem *sitem,
                                            const advanced_inventory_pane &spane,
                                            const item_location &destination_container,
                                            const std::string &action );
        /** Move a nested row back to the root represented by its current pane. */
        bool action_move_item_to_pane_root( advanced_inv_listitem *sitem, side pane_side,
                                            const std::string &action );
        /** Side-effect-free validation used by drag hover feedback and release handling. */
        ret_val<void> validate_container_transfer( const item_location &source_item,
                const item_location &destination_container, int amount = 0 ) const;

        void action_examine( advanced_inv_listitem *sitem, advanced_inventory_pane &spane );

        bool action_unload( advanced_inv_listitem *sitem, advanced_inventory_pane &spane,
                            advanced_inventory_pane &dpane, bool unload_pane_container = false );

        /** Give part of a non-liquid stack its own persistent inventory identity. */
        bool action_split_stack( advanced_inv_listitem *sitem, advanced_inventory_pane &spane );

        /** Reload the selected gun or magazine using the normal reload activity. */
        bool action_reload( advanced_inv_listitem *sitem );

        /** Show mouse/keyboard item actions that are valid for the selected item. */
        bool action_context_menu( advanced_inv_listitem *sitem, advanced_inventory_pane &spane,
                                  advanced_inventory_pane &dpane );

        // store/load settings (such as index, filter, etc)
        void save_settings( bool only_panes );
        void load_settings();
        // Adds an auto-resumed activity that reopens AIM. If this is called
        // before assigning an item-moving activity, AIM is reopened when the
        // item-moving activity finishes. This function should only be called
        // when AIM is going to be automatically closed due to pending item-moving
        // activity, otherwise the player will need to close AIM multiple times.
        void do_return_entry();
        // returns true if currently processing a routine
        // (such as `MOVE_ALL_ITEMS' with `AIM_ALL' source)
        bool is_processing() const;

        static std::string get_sortname( advanced_inv_sortby sortby );
        void print_items( side p, bool active );

        void redraw_pane( side p );
        void redraw_sidebar();

        bool move_all_items();
        /**
        * Fills drop_or_stash_item_info vectors with the contents of the AIM's panes, for use with move_all_items.
        */
        bool fill_lists_with_pane_items( Character &player_character, advanced_inv_sortby sort_priority,
                                         advanced_inventory_pane &spane, advanced_inventory_pane &dpane,
                                         std::vector<drop_or_stash_item_info> &item_list,
                                         std::vector<drop_or_stash_item_info> &fav_list, bool forbid_buckets );

        // Returns the x coordinate where the header started. The header is
        // displayed right of it, everything left of it is still free.
        int print_header( advanced_inventory_pane &pane, aim_location sel );

        /**
         * Translate an action ident from the input context to an aim_location.
         * @param action Action ident to translate
         * @param ret If the action ident referred to a location, its id is stored
         * here. Only valid when the function returns true.
         * @return true if the action did refer to an location (which has been
         * stored in ret), false otherwise.
         */
        bool get_square( const std::string &action, aim_location &ret );
        void change_square( aim_location changeSquare, advanced_inventory_pane &dpane,
                            advanced_inventory_pane &spane );
        /** Cycle the pane's sort mode without opening a second menu. */
        void cycle_sort_mode( advanced_inventory_pane &pane );
        /**
         * Checks whether one can put items into the supplied location.
         * If the supplied location is AIM_ALL, query for the actual location
         * (stores the result in def) and check that destination.
         * @return false if one can not put items in the destination, true otherwise.
         * The result true also indicates the def is not AIM_ALL (because the
         * actual location has been queried).
         */
        bool query_destination( aim_location &def );
        /**
         * Setup how many items/charges (if counted by charges) should be moved.
         * @param destarea Where to move to. This must not be AIM_ALL.
         * @param sitem The source item, it must contain a valid reference to an item!
         * @param action The action we are querying
         * @param amount The input value is ignored, contains the amount that should
         *      be moved. Only valid if this returns true.
         * @return false if nothing should/can be moved. True only if there can and
         *      should be moved. A return value of true indicates that amount now contains
         *      a valid item count to be moved.
         */
        bool query_charges( aim_location destarea, const advanced_inv_listitem &sitem,
                            const std::string &action, int &amount,
                            const item_location &destination_container );
};

#endif // CATA_SRC_ADVANCED_INV_H
