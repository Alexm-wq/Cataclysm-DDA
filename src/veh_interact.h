#pragma once
#ifndef CATA_SRC_VEH_INTERACT_H
#define CATA_SRC_VEH_INTERACT_H

#include <cstddef>
#include <functional>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "color.h"
#include "coordinates.h"
#include "cursesdef.h"
#include "input_context.h"
#include "input_enums.h"
#include "item_location.h"
#include "mapdata.h"
#include "memory_fast.h"
#include "player_activity.h"
#include "point.h"
#include "type_id.h"
#include "ui_helpers/dropdown.h"
#include "units.h"
#include "vpart_position.h"

class Character;
class inventory;
class map;
class time_duration;
class vpart_info;
struct requirement_data;

/** Represents possible return values from the cant_do function. */
enum class task_reason : int {
    UNKNOWN_TASK = -1, //No such task
    CAN_DO, //Task can be done
    INVALID_TARGET, //No valid target i.e. can't "change tire" if no tire present
    LACK_TOOLS, //Player doesn't have all the tools they need
    NOT_FREE, //Part is attached to something else and can't be unmounted
    LACK_SKILL, //Player doesn't have high enough mechanics skill
    MOVING_VEHICLE, // vehicle is moving, no modifications allowed
    LOW_MORALE, // Player has too low morale (for operations that require it)
    LOW_LIGHT // Player cannot see enough to work (for operations that require it)
};

class ui_adaptor;
class vehicle;
struct vehicle_part;

// For marking 'leaking' tanks/reactors/batteries
const std::string leak_marker = "<color_red>*</color>";

class veh_interact
{
        using part_selector = std::function<bool( const map &here, const vehicle_part &pt )>;

    public:
        static player_activity run( map &here,  vehicle &veh, const point_rel_ms &p );
        /** Drop any editor frame retained for an interrupted/aborted ACT_VEHICLE handoff. */
        static void discard_persistent_editor();
        /** Temporarily remove the retained editor while a game-level distraction query owns the screen. */
        static void suspend_persistent_editor_for_query();
        /** Restore the untouched retained editor after a distraction query continues the activity. */
        static void restore_persistent_editor_after_query();

        /** Prompt for a part matching the selector function */
        static std::optional<vpart_reference> select_part( map &here, const vehicle &veh,
                const part_selector &sel,
                const std::string &title = std::string() );

        static void complete_vehicle( map &here, Character &you );

    private:
        explicit veh_interact( map &here, vehicle &veh, const point_rel_ms &p = point_rel_ms::zero );
        ~veh_interact();

        // Legacy command cursor.  The selected vehicle mount is -dd; keep this
        // representation for activity serialization while the editor exposes explicit helpers.
        point_rel_ms dd = point_rel_ms::zero;

        // Vehicle-editor viewport state.  Selection is independent from camera/pan state.
        point_rel_ms viewport_center_mount = point_rel_ms::zero;
        point viewport_pan = point::zero;
        point viewport_drag_anchor = point::zero;
        point viewport_drag_pan_origin = point::zero;
        int viewport_zoom = 2;
        point live_preview_pan = point::zero;
        point live_preview_drag_anchor = point::zero;
        point live_preview_drag_pan_origin = point::zero;
        int live_preview_zoom = 2;
        bool live_preview_dragging = false;
        int selected_part = -1;
        int part_scroll = 0;
        int part_detail_scroll = 0;
        bool viewport_dragging = false;
        bool viewport_initialized = false;

        enum class editor_view_mode {
            editor,
            live,
            split
        };
        enum class editor_layer {
            composite,
            ground,
            middle,
            roof
        };
        enum class editor_system_filter {
            all,
            structural,
            propulsion,
            fuel,
            electrical,
            storage,
            controls,
            passenger,
            lighting,
            utility,
            turrets,
            combat,
            other
        };
        enum class editor_condition_filter {
            all,
            healthy,
            damaged,
            broken,
            replacement
        };
        enum class editor_dropdown {
            none,
            system,
            condition
        };
        enum class editor_context_surface {
            none,
            viewport,
            parts
        };

        editor_view_mode active_editor_view_mode = editor_view_mode::editor;
        std::optional<editor_view_mode> live_preview_last_draw_mode;
        editor_layer active_editor_layer = editor_layer::composite;
        ui_multiselect_filter<editor_system_filter> active_system_filters {
            editor_system_filter::structural, editor_system_filter::propulsion,
            editor_system_filter::fuel, editor_system_filter::electrical,
            editor_system_filter::storage, editor_system_filter::controls,
            editor_system_filter::passenger, editor_system_filter::lighting,
            editor_system_filter::utility, editor_system_filter::turrets,
            editor_system_filter::combat, editor_system_filter::other
        };
        ui_multiselect_filter<editor_condition_filter> active_condition_filters {
            editor_condition_filter::healthy, editor_condition_filter::damaged,
            editor_condition_filter::broken, editor_condition_filter::replacement
        };
        editor_dropdown open_editor_dropdown = editor_dropdown::none;

        struct editor_context_button {
            std::string label;
            point pos = point::zero;
            int width = 0;
            std::string action;
            std::string disabled_reason;
            bool enabled = true;
        };
        bool editor_test_mode = false;
        bool editor_context_open = false;
        editor_context_surface editor_context_target = editor_context_surface::none;
        point editor_context_anchor = point::zero;
        point editor_context_pos = point::zero;
        point editor_mouse_pos = point::zero;
        int editor_context_width = 0;
        int editor_context_height = 0;
        std::vector<editor_context_button> editor_context_buttons;
        std::string editor_context_hover_action;

        struct editor_toolbar_button {
            std::string label;
            std::string action;
            point pos = point::zero;
            int width = 0;
            bool enabled = true;
            int group = 0;
        };
        std::vector<editor_toolbar_button> editor_toolbar_buttons;
        int editor_toolbar_hover_button = -1;
        std::string editor_toolbar_hover_action;
        std::string pending_editor_action;
        std::string open_editor_toolbar_dropdown;
        point editor_toolbar_dropdown_pos = point::zero;
        int editor_toolbar_dropdown_width = 0;
        int editor_toolbar_dropdown_height = 0;
        std::vector<editor_context_button> editor_toolbar_dropdown_buttons;
        /* starting offset for vehicle parts description display and max offset for scrolling */
        int start_at = 0;
        int start_limit = 0;
        /* starting offset for the overview and the max offset for scrolling */
        int overview_offset = 0;
        int overview_limit = 0;
        /* starting offset for installation scrolling */
        int w_msg_scroll_offset = 0;
        /* starting offset for fuels scrolling */
        int fuel_index = 0;

        // Legacy single refill target plus the persistent editor's batch payload.
        item_location refill_target;
        std::vector<int> refill_part_indices;
        std::vector<item_location> refill_targets;

        const vehicle_part *sel_vehicle_part = nullptr;
        const vpart_info *sel_vpart_info = nullptr;

        // Command currently being run by the player
        char sel_cmd = ' ';

        int cpart = -1;
        int page_size = 0;
        // height of the stats window
        const int stats_h = 8;
        // element width defaults for 80 column display
        int disp_w = 26; // width of the left column
        int pane_w = 25; // width of the center and right columns
        catacurses::window w_border;
        catacurses::window w_mode;
        catacurses::window w_msg;
        catacurses::window w_disp;
        catacurses::window w_live_preview_full;
        catacurses::window w_live_preview_split;
        catacurses::window w_parts;
        catacurses::window w_stats;
        catacurses::window w_stats_1;
        catacurses::window w_stats_2;
        catacurses::window w_stats_3;
        catacurses::window w_list;
        catacurses::window w_details;
        catacurses::window w_name;
        catacurses::window w_refuel_overlay;
        // Shared transient-menu renderer.  Every vehicle-editor dropdown/context
        // menu uses the same highlighting, hit testing, and SDL-safe overlay path.
        ui_dropdown editor_filter_dropdown_menu;
        ui_dropdown editor_context_dropdown_menu;
        ui_dropdown editor_toolbar_dropdown_menu;

        // Keep the adaptor alive while ACT_VEHICLE runs so the editor frame is never
        // torn down to the world view between an action and automatic editor re-entry.
        shared_ptr_fast<ui_adaptor> ui;
        bool activity_handoff = false;
        bool first_frame_after_handoff = false;

        std::optional<std::string> title;
        std::optional<std::string> msg;

        bool ui_hidden = false;

        int highlight_part = -1;

        struct install_info_t;

        std::unique_ptr<install_info_t> install_info;
        std::string install_search_cache;
        bool install_available_materials_only_cache = false;
        bool install_show_all_cache = false;
        std::string install_selected_part_cache;

        struct remove_info_t;

        std::unique_ptr<remove_info_t> remove_info;

        struct reshape_info_t;

        std::unique_ptr<reshape_info_t> reshape_info;

        struct refuel_info_t;

        std::unique_ptr<refuel_info_t> refuel_info;

        static veh_interact *persistent_editor;
        void begin_activity_handoff();
        void resume_activity_handoff( map &here, const point_rel_ms &p );

        vehicle *veh;
        const inventory *crafting_inv;
        input_context main_context;

        // maximum weight capacity of available lifting equipment (if any)
        units::mass max_lift;
        // maximum weight_capacity of available jacking equipment (if any)
        units::mass max_jack;

        shared_ptr_fast<ui_adaptor> create_or_get_ui_adaptor( map &here );
        void hide_ui( map &here, bool hide );

        player_activity serialize_activity( map &here );

        /** Format list of requirements returning true if all are met */
        bool format_reqs( std::string &msg, const requirement_data &reqs,
                          const std::map<skill_id, int> &skills, time_duration time ) const;

        int part_at( const point_rel_ms &d );
        void move_cursor( map &here, const point_rel_ms &d, int dstart_at = 0 );

        point_rel_ms selected_mount() const;
        point viewport_cell_size() const;
        int editor_viewport_top() const;
        int editor_schematic_width() const;
        bool point_in_editor_schematic( const point &screen ) const;
        bool point_in_live_preview( const point &screen ) const;
        point live_preview_cell_size() const;
        tripoint_bub_ms live_preview_vehicle_center( map &here ) const;
        point mount_to_viewport( const point_rel_ms &mount ) const;
        std::optional<point_rel_ms> viewport_to_mount( const point &screen ) const;
        void center_viewport_on_vehicle();
        void clamp_viewport_pan();
        void ensure_selected_mount_visible();
        void select_mount( map &here, const point_rel_ms &mount );
        editor_layer editor_layer_for_part( const vpart_info &vpi ) const;
        bool part_info_matches_layer( const vpart_info &vpi ) const;
        bool part_matches_layer( const vehicle_part &vp ) const;
        editor_system_filter primary_system_for_part_info( const vpart_info &vpi ) const;
        editor_system_filter primary_system_for_part( const vehicle_part &vp ) const;
        bool part_matches_system( const vehicle_part &vp ) const;
        bool part_matches_condition( const vehicle_part &vp ) const;
        void toggle_editor_filter( editor_dropdown which, int option );
        std::string editor_system_filter_summary() const;
        std::string editor_condition_filter_summary() const;
        std::string editor_layer_name( editor_layer layer ) const;
        std::string editor_system_name( editor_system_filter filter ) const;
        std::string editor_condition_name( editor_condition_filter filter ) const;
        void editor_filter_button_geometry( editor_dropdown which, int &x, int &width ) const;
        void editor_dropdown_geometry( editor_dropdown which, int &x, int &y, int &width, int &height ) const;
        std::optional<std::pair<int, nc_color>> editor_mount_display( const point_rel_ms &mount ) const;
        int editor_part_symbol( const vehicle_part &vp ) const;
        nc_color editor_condition_color( const vehicle_part &vp ) const;
        std::vector<int> inspector_parts() const;
        void reset_part_selection();
        void scroll_part_inspector( int delta );
        void scroll_part_details( int delta );
        bool handle_editor_controls_click( const point &pos );
        void close_editor_context_menu();
        void open_editor_context_menu( map &here, const point &pos, editor_context_surface surface );
        bool handle_editor_context_click( map &here, const point &pos );
        bool run_editor_context_action( map &here, const std::string &action );
        void update_editor_context_hover( map &here );
        bool set_editor_repair_requirements( map &here, vehicle_part &part );
        void display_editor_context_menu();
        bool editor_toolbar_action_enabled( const map &here, const std::string &action );
        void rebuild_editor_toolbar( const map &here );
        void update_editor_toolbar_hover( map &here, const std::optional<point> &pos );
        bool handle_editor_toolbar_mouse( map &here, const std::string &action,
                                          const std::optional<point> &pos );
        void open_editor_toolbar_menu( const map &here, const std::string &which );
        void close_editor_toolbar_dropdown();
        bool handle_editor_toolbar_dropdown_mouse( const std::string &action );
        void display_editor_toolbar_dropdown();
        bool handle_editor_mouse( map &here, const std::string &action );
        void display_editor_controls();
        void display_editor_filter_dropdown();

        task_reason cant_do( const map &here,  char mode );
        bool can_potentially_install( const vpart_info &vpart );
        /** Move index (parameter pos) according to input action:
         * (up or down, single step or whole page).
         * @param pos index to change.
         * @param action input action (taken from input_context::handle_input)
         * @param size size of the list to scroll, used to wrap the cursor around.
         * @param header number of lines reserved for list header.
         * @return false if the action is not a move action, the index is not changed in this case.
         */
        bool move_in_list( int &pos, const std::string &action, int size,
                           int header = 0 ) const;
        void move_fuel_cursor( map &here, int delta );

        /**
         * @name Task handlers
         *
         * One function for each specific task
         * @warning presently functions may mutate local state
         * @param msg failure message to display (if any)
         */
        /*@{*/
        void do_install( map &here );
        void refresh_install_candidates();
        void sync_install_selection( map &here );
        bool install_materials_available( const vpart_info &vpart );
        bool confirm_install( map &here );
        void close_install_mode();
        void do_repair( map &here );
        void do_mend( map &here );
        void do_refill( map &here );
        void open_reshape_mode();
        void close_reshape_mode();
        void sync_reshape_selection();
        void preview_reshape_variant( int index );
        bool apply_reshape_variant();
        bool handle_reshape_mouse( const std::string &action );
        void refresh_refuel_sources( map &here );
        void refresh_quick_refuel_fuels( map &here );
        bool refill_source_compatible( const vehicle_part &part, const item_location &source ) const;
        int refill_source_available( const item_location &source ) const;
        int refill_part_remaining( const vehicle_part &part, const item_location &source ) const;
        bool queue_refill_plan( const std::vector<std::pair<int, item_location>> &plan );
        bool queue_selected_refill_source( map &here );
        bool queue_quick_refill_all( map &here );
        bool add_test_refuel_containers( map &here );
        void close_refuel_mode();
        bool handle_refuel_mouse( map &here, const std::string &action );
        void display_refuel_pane( map &here );
        void do_remove( map &here );
        void do_rename();
        void do_siphon( map &here );
        // Returns true if exiting the screen
        bool do_unload( map &here );
        void do_assign_crew( map &here );
        void do_relabel( const map &here );
        /*@}*/

        /**
        * Calculates the lift requirements for a given vehicle_part
        * @return bool true if lift requirements are fulfilled
        * @return string msg for the ui to show the lift requirements
        */
        std::pair<bool, std::string> calc_lift_requirements( map &here, const vpart_info &sel_vpart_info );

        void display_grid();
        void display_veh( map &here );
        void display_live_preview( map &here );
        void display_part_inspector();
        void display_part_details();
        void display_reshape_pane();
        void display_stats( map &here ) const;
        void display_name();
        void display_mode( const map &here );
        void display_list( size_t pos, const std::vector<const vpart_info *> &list, int header = 0 );
        void display_details( const vpart_info *part );

        struct part_option {
            part_option( const std::string &key, vehicle_part *part, bool selectable, const input_event &hotkey,
                         std::function<void( const vehicle_part &pt, const catacurses::window &w, int y )> details ) :
                key( key ), part( part ), selectable( selectable ), hotkey( hotkey ),
                details( std::move( details ) ) {}

            part_option( const std::string &key, vehicle_part *part, bool selectable, const input_event &hotkey,
                         std::function<void( const vehicle_part &pt, const catacurses::window &w, int y )> details,
                         std::function<void( const vehicle_part &pt )> message ) :
                key( key ), part( part ), selectable( selectable ), hotkey( hotkey ),
                details( std::move( details ) ),
                message( std::move( message ) ) {}

            std::string key;
            vehicle_part *part;

            /** Can the part be selected and used */
            bool selectable;

            /** Can @param action be run for this entry? */
            input_event hotkey;

            /** Writes any extra details for this entry */
            std::function<void( const vehicle_part &pt, const catacurses::window &w, int y )> details;

            /** Writes to message window when part is selected */
            std::function<void( const vehicle_part &pt )> message;
        };
        std::vector<part_option> overview_opts;
        std::map<std::string, std::function<void( const catacurses::window &, int )>> overview_headers;
        using overview_enable_t = std::function<bool( const map &here, const vehicle_part &pt )>;
        using overview_action_t = std::function<void( map &here, vehicle_part &pt )>;
        overview_enable_t overview_enable;
        overview_action_t overview_action;
        int overview_pos = -1;

        void calc_overview( map &here );
        void display_overview( const map &here );
        /**
         * Display overview of parts, optionally with interactive selection of one part
         *
         * @param enable used to determine parts of interest. If \p action also present, these
                         parts are the ones that can be selected. Otherwise, these are the parts
                         that will be highlighted
         * @param action callback when part is selected.
         */
        void overview( map &here, const overview_enable_t &enable = {},
                       const overview_action_t &action = {} );
        void move_overview_line( int );

        void count_durability();

        nc_color total_durability_color;
        std::string total_durability_text;

        /** Returns the most damaged part's index, or -1 if they're all healthy. */
        vehicle_part *get_most_damaged_part() const;

        /** Returns the index of the part that needs repair the most.
         * This may not be mostDamagedPart since not all parts can be repaired
         * If there are no damaged parts this returns -1 */
        vehicle_part *get_most_repairable_part() const;

        //do_remove supporting operation, writes requirements to ui
        bool can_remove_part( map &here, int idx, const Character &you );
        //do install support, writes requirements to ui
        bool update_part_requirements( map &here );

        /* Vector of all vpart TYPES that can be mounted in the current square.
         * Can be converted to a vector<vpart_info>.
         * Updated whenever the cursor moves. */
        std::vector<const vpart_info *> can_mount;

        /* Vector of vparts in the current square that can be repaired. Strictly a
         * subset of parts_here.
         * Can probably be removed entirely, otherwise is a vector<vehicle_part>.
         * Updated whenever parts_here is updated.
         */
        std::vector<int> need_repair;

        /* Vector of all vparts that exist on the vehicle in the current square.
         * Can be converted to a vector<vehicle_part>.
         * Updated whenever the cursor moves. */
        std::vector<int> parts_here;

        /* Terrain at current square.
         * Updated whenever the cursor moves. */
        ter_t terrain_here;

        void cache_tool_availability();
        void allocate_windows();
        void do_main_loop( map &here );

        void cache_tool_availability_update_lifting( const tripoint_bub_ms &world_cursor_pos );

        /** Returns true if the vehicle has a jack powerful enough to lift itself installed */
        bool can_self_jack( map &here );
};

void act_vehicle_siphon( map &here, vehicle *veh );

void orient_part( map &here, vehicle *veh, const vpart_info &vpinfo, int partnum,
                  const std::optional<point_rel_ms> &part_placement = std::nullopt );

#endif // CATA_SRC_VEH_INTERACT_H
