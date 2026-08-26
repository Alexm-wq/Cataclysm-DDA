#include "crafting_gui.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstring>
#include <functional>
#include <iterator>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <string_view>
#include <unordered_set>
#include <utility>
#include <vector>

#include "calendar.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "character.h"
#include "character_id.h"
#include "color.h"
#include "crafting.h"
#include "cuboid_rectangle.h"
#include "cursesdef.h"
#include "debug.h"
#include "display.h"
#include "flag.h"
#include "flat_set.h"
#include "flexbuffer_json.h"
#include "game_constants.h"
#include "game_inventory.h"
#include "generic_factory.h"
#include "input.h"
#include "input_context.h"
#include "input_enums.h"
#include "inventory.h"
#include "inventory_ui.h"
#include "item.h"
#include "item_factory.h"
#include "item_location.h"
#include "itype.h"
#include "localized_comparator.h"
#include "magic_enchantment.h"
#include "options.h"
#include "output.h"
#include "pimpl.h"
#include "point.h"
#include "popup.h"
#include "recipe.h"
#include "recipe_dictionary.h"
#include "requirements.h"
#include "skill.h"
#include "string_formatter.h"
#include "string_input_popup.h"
#include "translation.h"
#include "translation_cache.h"
#include "translations.h"
#include "type_id.h"
#include "uilist.h"
#include "ui_iteminfo.h"
#include "ui_manager.h"
#include "uistate.h"

static const limb_score_id limb_score_manip( "manip" );

static const std::string flag_AFFECTED_BY_PAIN( "AFFECTED_BY_PAIN" );
static const std::string flag_BLIND_EASY( "BLIND_EASY" );
static const std::string flag_BLIND_HARD( "BLIND_HARD" );
static const std::string flag_NO_ENCHANTMENT( "NO_ENCHANTMENT" );
static const std::string flag_NO_MANIP( "NO_MANIP" );

enum TAB_MODE {
    NORMAL,
    FILTERED,
    BATCH
};

enum CRAFTING_SPEED_STATE {
    TOO_DARK_TO_CRAFT,
    TOO_SLOW_TO_CRAFT,
    SLOW_BUT_CRAFTABLE,
    FAST_CRAFTING,
    NORMAL_CRAFTING
};

static const std::map<const CRAFTING_SPEED_STATE, translation> craft_speed_reason_strings = {
    {TOO_DARK_TO_CRAFT, to_translation( "too dark to craft" )},
    {TOO_SLOW_TO_CRAFT, to_translation( "unable to craft" )},
    {SLOW_BUT_CRAFTABLE, to_translation( "crafting is slowed to %d%%: %s" )},
    {FAST_CRAFTING, to_translation( "crafting is accelerated to %d%%: %s" )},
    {NORMAL_CRAFTING, to_translation( "craftable" )}
};

namespace
{

generic_factory<crafting_category> craft_cat_list( "recipe_category" );

} // namespace

template<>
const crafting_category &string_id<crafting_category>::obj() const
{
    return craft_cat_list.obj( *this );
}

template<>
bool string_id<crafting_category>::is_valid() const
{
    return craft_cat_list.is_valid( *this );
}

static bool query_is_yes( std::string_view query );
static void draw_hidden_amount( const catacurses::window &w, int amount, int num_recipe );
static void draw_can_craft_indicator( const catacurses::window &w, const recipe &rec,
                                      Character &crafter );
static std::map<size_t, inclusive_rectangle<point>> draw_recipe_tabs( const catacurses::window &w,
        const tab_list &tab, TAB_MODE mode,
        bool filtered_unread, std::map<std::string, bool> &unread );
static std::map<size_t, inclusive_rectangle<point>> draw_recipe_subtabs(
            const catacurses::window &w, const std::string &tab,
            size_t subtab,
            const recipe_subset &available_recipes, TAB_MODE mode,
            std::map<std::string, bool> &unread );
/**
 * return index of newly chosen crafter.
 * return < 0 if error happens or nobody is choosen.
 */
static int choose_crafter( const std::vector<Character *> &crafting_group, int crafter_i,
                           const recipe *rec, bool rec_valid );

static std::string peek_related_recipe( const recipe *current, const recipe_subset &available,
                                        Character &crafter );
static int related_menu_fill( uilist &rmenu,
                              const std::vector<std::pair<itype_id, std::string>> &related_recipes,
                              const recipe_subset &available );
static item get_recipe_result_item( const recipe &rec, Character &crafter );
static void compare_recipe_with_item( const item &recipe_item, Character &crafter );

static std::string get_cat_unprefixed( std::string_view prefixed_name )
{
    return std::string( prefixed_name.substr( 3, prefixed_name.size() - 3 ) );
}

void load_recipe_category( const JsonObject &jsobj, const std::string &src )
{
    craft_cat_list.load( jsobj, src );
}

void crafting_category::load( const JsonObject &jo, std::string_view )
{
    // Ensure id is correct
    if( id.str().find( "CC_" ) != 0 ) {
        jo.throw_error( "Crafting category id has to be prefixed with 'CC_'" );
    }

    optional( jo, was_loaded, "is_hidden", is_hidden, false );
    optional( jo, was_loaded, "is_practice", is_practice, false );
    optional( jo, was_loaded, "is_building", is_building, false );
    optional( jo, was_loaded, "is_wildcard", is_wildcard, false );
    mandatory( jo, was_loaded, "recipe_subcategories", subcategories,
               auto_flags_reader<> {} );

    // Ensure subcategory ids are correct and remove dupes
    std::string cat_name = get_cat_unprefixed( id.str() );
    std::unordered_set<std::string> known;
    for( auto it = subcategories.begin(); it != subcategories.end(); ) {
        const std::string &subcat_id = *it;
        if( subcat_id.find( "CSC_" + cat_name + "_" ) != 0 && subcat_id != "CSC_ALL" ) {
            jo.throw_error( "Crafting sub-category id has to be prefixed with CSC_<category_name>_" );
        }
        if( known.find( subcat_id ) != known.end() ) {
            it = subcategories.erase( it );
            continue;
        }
        known.emplace( subcat_id );
        ++it;
    }
}

static std::string get_subcat_unprefixed( std::string_view cat,
        const std::string &prefixed_name )
{
    std::string prefix = "CSC_" + get_cat_unprefixed( cat ) + "_";

    if( prefixed_name.find( prefix ) == 0 ) {
        return prefixed_name.substr( prefix.size(), prefixed_name.size() - prefix.size() );
    }

    return prefixed_name == "CSC_ALL" ? translate_marker( "ALL" ) : translate_marker( "NONCRAFT" );
}

void reset_recipe_categories()
{
    craft_cat_list.reset();
}

static bool cannot_gain_skill_or_prof( const Character &crafter, const recipe &recp )
{
    if( recp.skill_used &&
        static_cast<int>( crafter.get_skill_level( recp.skill_used ) ) <= recp.get_skill_cap() ) {
        return false;
    }
    for( const proficiency_id &prof : recp.used_proficiencies() ) {
        if( !crafter.has_proficiency( prof ) ) {
            return false;
        }
    }
    return true;
}

namespace
{
struct availability {
        explicit availability( Character &_crafter, const recipe *r, int batch_size = 1,
                               bool camp_crafting = false, inventory *inventory_override = nullptr ) :
            crafter( _crafter ) {
            rec = r;
            inv_override = inventory_override;
            const inventory &inv = camp_crafting ? *inv_override : crafter.crafting_inventory();
            auto all_items_filter = r->get_component_filter( recipe_filter_flags::none );
            auto no_rotten_filter = r->get_component_filter( recipe_filter_flags::no_rotten );
            auto no_favorite_filter = r->get_component_filter( recipe_filter_flags::no_favorite );
            const deduped_requirement_data &req = r->deduped_requirements();
            has_all_skills = r->skill_used.is_null() ||
                             crafter.get_skill_level( r->skill_used ) >= r->get_difficulty( crafter );
            crafter_has_primary_skill = r->skill_used.is_null()
                                        || crafter.get_knowledge_level( rec->skill_used )
                                        >= static_cast<int>( rec->get_difficulty( crafter ) * 0.8f );
            has_proficiencies = r->character_has_required_proficiencies( crafter );
            std::string reason;
            craft_flags flag = camp_crafting ? craft_flags::none : craft_flags::start_only;

            if( crafter.is_npc() && !r->npc_can_craft( reason ) && !camp_crafting ) {
                can_craft = false;
            } else if( r->is_nested() ) {
                can_craft = check_can_craft_nested( _crafter, *r );
            } else {
                can_craft = ( !r->is_practice() || has_all_skills ) && has_proficiencies &&
                            req.can_make_with_inventory( inv, all_items_filter, batch_size, flag );
            }
            would_use_rotten = !req.can_make_with_inventory( inv, no_rotten_filter, batch_size,
                               flag );
            would_use_favorite = !req.can_make_with_inventory( inv, no_favorite_filter, batch_size,
                                 flag );
            useless_practice = r->is_practice() && cannot_gain_skill_or_prof( crafter, *r );
            is_nested_category = r->is_nested();
            const requirement_data &simple_req = r->simple_requirements();
            apparently_craftable = ( !r->is_practice() || has_all_skills ) && has_proficiencies &&
                                   simple_req.can_make_with_inventory( inv, all_items_filter, batch_size, flag );
            for( const auto& [skill, skill_lvl] : r->required_skills ) {
                if( crafter.get_skill_level( skill ) < skill_lvl ) {
                    has_all_skills = false;
                    break;
                }
            }
        }
        Character &crafter;
        bool can_craft;
        // group can introduce recipe this crafter cannot craft because of low primary skill
        bool crafter_has_primary_skill;
        bool would_use_rotten;
        bool would_use_favorite;
        bool useless_practice;
        bool apparently_craftable;
        bool has_proficiencies;
        bool has_all_skills;
        bool is_nested_category;
        // Used as an indicator to see if crafting is called via camp. if not nullptr, we must be camp crafting
        inventory *inv_override;
    private:
        const recipe *rec;
        mutable float proficiency_time_maluses = -1.0f;
        mutable float max_proficiency_time_maluses = -1.0f;
        mutable float proficiency_skill_maluses = -1.0f;
        mutable float max_proficiency_skill_maluses = -1.0f;
    public:
        float get_proficiency_time_maluses() const {
            if( proficiency_time_maluses < 0 ) {
                proficiency_time_maluses = rec->proficiency_time_maluses( crafter );
            }

            return proficiency_time_maluses;
        }
        float get_max_proficiency_time_maluses() const {
            if( max_proficiency_time_maluses < 0 ) {
                max_proficiency_time_maluses = rec->max_proficiency_time_maluses( crafter );
            }

            return max_proficiency_time_maluses;
        }
        float get_proficiency_skill_maluses() const {
            if( proficiency_skill_maluses < 0 ) {
                proficiency_skill_maluses = rec->proficiency_skill_maluses( crafter );
            }

            return proficiency_skill_maluses;
        }
        float get_max_proficiency_skill_maluses() const {
            if( max_proficiency_skill_maluses < 0 ) {
                max_proficiency_skill_maluses = rec->max_proficiency_skill_maluses( crafter );
            }

            return max_proficiency_skill_maluses;
        }

        nc_color selected_color() const {
            if( !can_craft && is_nested_category ) {
                return h_blue;
            } else if( !can_craft ) {
                return h_dark_gray;
            } else if( !crafter_has_primary_skill && is_nested_category ) {
                return h_magenta;
            } else if( !crafter_has_primary_skill ) {
                return h_light_red;
            } else if( is_nested_category ) {
                return h_light_blue;
            }  else if( would_use_rotten || useless_practice ) {
                return has_all_skills ? h_brown : h_red;
            } else if( would_use_favorite ) {
                return has_all_skills ? h_pink : h_red;
            } else {
                return has_all_skills ? h_white : h_yellow;
            }
        }

        nc_color color( bool ignore_missing_skills = false ) const {
            if( !can_craft && is_nested_category ) {
                return c_blue;
            } else if( !can_craft ) {
                return c_dark_gray;
            } else if( !crafter_has_primary_skill && is_nested_category ) {
                return c_magenta;
            } else if( !crafter_has_primary_skill ) {
                return c_light_red;
            } else if( is_nested_category ) {
                return c_light_blue;
            } else if( would_use_rotten || useless_practice ) {
                return has_all_skills || ignore_missing_skills ? c_brown : c_red;
            } else if( would_use_favorite ) {
                return has_all_skills ? c_pink : c_red;
            } else {
                return has_all_skills || ignore_missing_skills ? c_white : c_yellow;
            }
        }

        static bool check_can_craft_nested( Character &_crafter, const recipe &r ) {
            // recursively check if you can craft anything in the nest
            for( const recipe_id &nested_r : r.nested_category_data ) {
                if( availability( _crafter, &nested_r.obj() ).can_craft ) {
                    return true;
                }
            }
            return false;
        }
};
} // namespace

namespace
{

enum class crafting_browser_pane : int {
    categories = 0,
    recipes,
    inspector
};

enum class crafting_sidebar_entry_type : int {
    heading,
    special,
    filter,
    category,
    subcategory
};

struct crafting_sidebar_entry {
    crafting_sidebar_entry_type type = crafting_sidebar_entry_type::heading;
    std::string label;
    std::string category;
    std::string subcategory;
    bool enabled = true;
};

struct crafting_browser_button {
    std::string action;
    std::string label;
    bool enabled = true;
    std::string disabled_reason;
    point pos;
    int width = 0;

    crafting_browser_button() = default;
    crafting_browser_button( std::string action, std::string label, const bool enabled,
                             std::string disabled_reason, const point &pos = point::zero,
                             const int width = 0 ) :
        action( std::move( action ) ), label( std::move( label ) ), enabled( enabled ),
        disabled_reason( std::move( disabled_reason ) ), pos( pos ), width( width ) {}
};

struct crafting_browser_state {
    const recipe *selected_recipe = nullptr;
    std::string selected_category;
    std::string selected_subcategory;
    std::string search_query;
    bool craftable_only = false;
    bool memorized_only = false;
    bool unread_only = false;
    bool unread_first = false;
    int recipe_scroll = 0;
    int category_scroll = 0;
    int inspector_scroll = 0;
    int item_popup_scroll = 0;
    int batch_size = 1;
    crafting_browser_pane focused_pane = crafting_browser_pane::recipes;
    const recipe *hovered_recipe = nullptr;
    const recipe *last_clicked_recipe = nullptr;
    std::optional<std::chrono::steady_clock::time_point> last_click_time;
    bool context_open = false;
    point context_pos;
    int context_width = 0;
    int context_height = 0;
};

static bool crafting_recipe_can_start( const recipe &rec, const availability &avail,
                                       const Character &crafter )
{
    return !rec.is_nested() && avail.can_craft && avail.crafter_has_primary_skill &&
           crafter.lighting_craft_speed_multiplier( rec ) > 0.0f &&
           crafter.crafting_speed_multiplier( rec ) > 0.0f;
}

static std::string crafting_unavailable_reason( const recipe &rec, const availability &avail,
        Character &crafter, const int batch_size )
{
    if( rec.is_nested() ) {
        return _( "Choose a recipe inside this group." );
    }
    if( !avail.crafter_has_primary_skill ) {
        return rec.is_practice() ?
               _( "The crafter lacks the theoretical knowledge to practice this." ) :
               _( "The crafter lacks the theoretical knowledge to understand this recipe." );
    }
    if( !avail.has_proficiencies ) {
        return _( "The crafter lacks a required proficiency." );
    }
    std::string npc_reason;
    if( crafter.is_npc() && !rec.npc_can_craft( npc_reason ) && !avail.inv_override ) {
        return npc_reason;
    }
    if( !avail.can_craft ) {
        if( avail.apparently_craftable ) {
            return _( "The same item is needed by multiple requirements." );
        }

        const inventory &crafting_inv = avail.inv_override ? *avail.inv_override :
                                        crafter.crafting_inventory();
        const requirement_data &req = rec.simple_requirements();
        const craft_flags flags = avail.inv_override ? craft_flags::none : craft_flags::start_only;
        req.can_make_with_inventory( crafting_inv, rec.get_component_filter(), batch_size, flags );
        const std::vector<std::string> missing_lines = string_split( req.list_missing(), '\n' );
        for( const std::string &raw_line : missing_lines ) {
            const std::string line = trim( raw_line );
            if( line.empty() || line.back() == ':' ) {
                continue;
            }
            return string_format( _( "Missing: %s" ), line );
        }
        return _( "The recipe requirements are not satisfied." );
    }
    if( crafter.lighting_craft_speed_multiplier( rec ) <= 0.0f ) {
        return _( "The crafter cannot see well enough to craft this." );
    }
    if( crafter.crafting_speed_multiplier( rec ) <= 0.0f ) {
        return _( "The crafter is currently unable to work on this recipe." );
    }
    return std::string();
}

} // namespace

static std::string craft_success_chance_string( const recipe &recp, const Character &guy )
{
    float chance = 100.f * ( 1.f - guy.recipe_success_chance( recp ) );
    std::string color;
    if( chance > 75 ) {
        color = "yellow";
    } else if( chance > 50 ) {
        color = "light_gray";
    } else if( chance > 25 ) {
        color = "green";
    } else {
        color = "cyan";
    }

    return string_format( _( "Minor Failure Chance: <color_%s>%2.2f%%</color>" ), color, chance );
}

static std::string cata_fail_chance_string( const recipe &recp, const Character &guy )
{
    float chance = 100.f * guy.item_destruction_chance( recp );
    std::string color;
    if( chance > 50 ) {
        color = "i_red";
    } else if( chance > 20 ) {
        color = "red";
    } else if( chance > 5 ) {
        color = "yellow";
    } else {
        color = "light_gray";
    }

    return string_format( _( "Catastrophic Failure Chance: <color_%s>%2.2f%%</color>" ), color,
                          chance );
}

static std::vector<std::string> recipe_info(
    const recipe &recp,
    const availability &avail,
    Character &guy,
    std::string_view qry_comps,
    const int batch_size,
    const int fold_width,
    const nc_color &color,
    const std::vector<Character *> &crafting_group )
{
    std::ostringstream oss;
    oss << _( "<color_light_green>DETAILS</color>\n" );
    oss << string_format( _( "Difficulty: <color_cyan>%d</color>\n" ),
                          recp.get_difficulty( guy ) );
    if( !recp.is_nested() ) {
        const int result_amount = recp.makes_amount() * batch_size;
        oss << string_format( _( "Result: <color_cyan>%d</color> x %s\n" ), result_amount,
                              recp.result_name( /*decorated=*/true ) );
        oss << string_format( _( "Batch: <color_cyan>%d</color>\n" ), batch_size );
    }
    oss << string_format( _( "Crafter: %s\n" ), guy.name_and_maybe_activity() );

    oss << _( "\n<color_light_green>SKILLS</color>\n" );
    oss << string_format( _( "Primary skill: %s\n" ), recp.primary_skill_string( guy ) );
    if( !avail.crafter_has_primary_skill ) {
        if( recp.is_practice() ) {
            oss << _( "<color_red>Crafter cannot practice this because they "
                      "lack the theoretical knowledge for it.</color>\n" );
        } else {
            oss << _( "<color_red>Crafter cannot craft this because they "
                      "lack the theoretical knowledge to understand the recipe.</color>\n" );
        }
    }

    if( !recp.required_skills.empty() ) {
        oss << string_format( _( "Other skills: %s\n" ), recp.required_skills_string( guy ) );
    }

    const std::string req_profs = recp.required_proficiencies_string( &guy );
    if( !req_profs.empty() ) {
        oss << string_format( _( "Proficiencies Required: %s\n" ), req_profs );
    }
    const std::string used_profs = recp.used_proficiencies_string( &guy );
    if( !used_profs.empty() ) {
        oss << string_format( _( "Proficiencies Used: %s\n" ), used_profs );
    }
    const std::string missing_profs = recp.missing_proficiencies_string( &guy );
    if( !missing_profs.empty() ) {
        oss << string_format( _( "Proficiencies Missing: %s\n" ), missing_profs );
    }

    oss << craft_success_chance_string( recp, guy ) << "\n";
    oss << cata_fail_chance_string( recp, guy ) << "\n";

    if( !recp.is_nested() ) {
        const int expected_turns = guy.expected_time_to_craft( recp, batch_size )
                                   / to_moves<int>( 1_turns );
        oss << string_format( _( "Time to complete: <color_cyan>%s</color>\n" ),
                              to_string( time_duration::from_turns( expected_turns ) ) );

    }

    const std::string batch_savings = recp.batch_savings_string();
    if( !batch_savings.empty() ) {
        oss << string_format( _( "Batch time savings: <color_cyan>%s</color>\n" ), batch_savings );
    }

    oss << string_format( _( "Activity level: <color_cyan>%s</color>\n" ),
                          display::activity_level_str( recp.exertion_level() ) );

    const int makes = recp.makes_amount();
    if( makes > 1 ) {
        oss << string_format( _( "Recipe makes: <color_cyan>%d</color>\n" ), makes );
    }

    oss << string_format( _( "Craftable in the dark?  <color_cyan>%s</color>\n" ),
                          recp.has_flag( flag_BLIND_EASY ) ? _( "Easy" ) :
                          recp.has_flag( flag_BLIND_HARD ) ? _( "Hard" ) :
                          _( "Impossible" ) );

    const inventory &crafting_inv = avail.inv_override ? *avail.inv_override : guy.crafting_inventory();
    if( recp.result() ) {
        const int nearby_amount = crafting_inv.count_item( recp.result() );
        std::string nearby_string;
        if( nearby_amount == 0 ) {
            nearby_string = "<color_light_gray>0</color>";
        } else if( nearby_amount > 9000 ) {
            // at some point you get too many to count at a glance and just know you have a lot
            nearby_string = _( "<color_red>It's Over 9000!!!</color>" );
        } else {
            nearby_string = string_format( "<color_yellow>%d</color>", nearby_amount );
        }
        oss << string_format( _( "Nearby: %s\n" ), nearby_string );
    }

    const bool can_craft_this = avail.can_craft;
    if( can_craft_this && avail.would_use_rotten ) {
        oss << _( "<color_red>Will use rotten ingredients</color>\n" );
    }
    if( can_craft_this && avail.would_use_favorite ) {
        oss << _( "<color_red>Will use favorited ingredients</color>\n" );
    }
    const bool too_complex = recp.deduped_requirements().is_too_complex();
    if( can_craft_this && too_complex ) {
        oss << _( "Due to the complex overlapping requirements, this "
                  "recipe <color_yellow>may appear to be craftable "
                  "when it is not</color>.\n" );
    }
    std::string reason;
    bool npc_cant = avail.crafter.is_npc() && !recp.npc_can_craft( reason ) && !avail.inv_override ;
    if( !can_craft_this && avail.apparently_craftable && !recp.is_nested() && !npc_cant ) {
        oss << _( "<color_red>Cannot be crafted because the same item is needed "
                  "for multiple components.</color>\n" );
    }

    if( !can_craft_this && npc_cant ) {
        oss << colorize( reason, c_red ) << "\n";
    }

    const bool disp_prof_msg = avail.has_proficiencies && !recp.is_nested();
    const float time_maluses = avail.get_proficiency_time_maluses();
    const float max_time_malus = avail.get_max_proficiency_time_maluses();
    const float skill_maluses = avail.get_proficiency_skill_maluses();
    const float max_skill_malus = avail.get_max_proficiency_skill_maluses();
    if( disp_prof_msg && time_maluses < max_time_malus && skill_maluses < max_skill_malus ) {
        oss << string_format( _( "<color_green>This recipe will be %.2fx faster than normal, "
                                 "and your effective skill will be %.2f levels higher than normal, because of "
                                 "the proficiencies the crafter has.</color>\n" ),
                              max_time_malus / time_maluses, max_skill_malus - skill_maluses );
    } else if( disp_prof_msg && time_maluses < max_time_malus ) {
        oss << string_format( _( "<color_green>This recipe will be %.2fx faster than normal, "
                                 "because of the proficiencies the crafter has.</color>\n" ), max_time_malus / time_maluses );
    } else if( disp_prof_msg && skill_maluses < max_skill_malus ) {
        oss << string_format(
                _( "<color_green>Your effective skill will be %.2f levels higher than normal, "
                   "because of the proficiencies the crafter has.</color>\n" ), max_skill_malus - skill_maluses );
    }
    if( !can_craft_this && !avail.has_proficiencies ) {
        oss << _( "<color_red>Cannot be crafted because the crafter lacks"
                  " the required proficiencies.</color>\n" );
    }

    if( recp.has_byproducts() ) {
        oss << _( "Byproducts:\n" );
        for( const std::pair<const itype_id, int> &bp : recp.get_byproducts() ) {
            const itype *t = item::find_type( bp.first );
            int amount = bp.second * batch_size;
            if( t->count_by_charges() ) {
                oss << string_format( "> %s (%d)\n", t->nname( 1 ), amount );
            } else {
                oss << string_format( "> %d %s\n", amount,
                                      t->nname( static_cast<unsigned int>( amount ) ) );
            }
        }
    }

    std::vector<std::string> result = foldstring( oss.str(), fold_width );

    if( !recp.is_nested() ) {
        result.emplace_back( colorize( _( "REQUIREMENTS" ), c_light_green ) );
        const requirement_data &req = recp.simple_requirements();
        const std::vector<std::string> tools = req.get_folded_tools_list(
                fold_width, color, crafting_inv, batch_size );
        const std::vector<std::string> comps = req.get_folded_components_list(
                fold_width, color, crafting_inv, recp.get_component_filter(), batch_size, qry_comps );
        result.insert( result.end(), tools.begin(), tools.end() );
        result.insert( result.end(), comps.begin(), comps.end() );
    }

    oss = std::ostringstream();
    if( !guy.knows_recipe( &recp ) ) {
        oss << _( "Recipe not memorized yet\n" );
        const std::set<itype_id> books_with_recipe = guy.get_books_for_recipe( crafting_inv, &recp );
        if( !books_with_recipe.empty() ) {
            const std::string enumerated_books = enumerate_as_string( books_with_recipe,
            []( const itype_id & type_id ) {
                return colorize( item::nname( type_id ), c_cyan );
            } );
            oss << string_format( _( "Written in: %s\n" ), enumerated_books );
        }
        std::vector<const Character *> knowing_helpers;
        for( const Character *helper : crafting_group ) {
            // guy.getID() != helper->getID(): guy doesn't know the recipe anyway, but this should be faster
            if( guy.getID() != helper->getID() && helper->knows_recipe( &recp ) ) {
                knowing_helpers.push_back( helper );
            }
        }
        if( !knowing_helpers.empty() ) {
            const std::string enumerated_helpers = enumerate_as_string( knowing_helpers,
            []( const Character * helper ) {
                return colorize( helper->is_avatar() ? _( "You" ) : helper->get_name(), c_cyan );
            } );
            oss << string_format( _( "Known by: %s\n" ), enumerated_helpers );
        }
    }
    std::vector<std::string> tmp = foldstring( oss.str(), fold_width );
    result.insert( result.end(), tmp.begin(), tmp.end() );

    std::string description = recp.description.translated();
    if( description.empty() && recp.result() ) {
        description = item::find_type( recp.result() )->description.translated();
    }
    if( !description.empty() ) {
        result.emplace_back( colorize( _( "DESCRIPTION" ), c_light_green ) );
        tmp = foldstring( description, fold_width );
        result.insert( result.end(), tmp.begin(), tmp.end() );
    }

    return result;
}

static std::string practice_recipe_description( const recipe &recp,
        const Character &crafter )
{
    std::ostringstream oss;
    oss << recp.description.translated() << "\n\n";
    if( recp.practice_data->min_difficulty != recp.practice_data->max_difficulty ) {
        std::string txt = string_format( _( "Difficulty range: %d to %d" ),
                                         recp.practice_data->min_difficulty, recp.practice_data->max_difficulty );
        oss << txt << "\n";
    }
    if( recp.skill_used ) {
        const int player_skill_level = crafter.get_all_skills().get_skill_level( recp.skill_used );
        if( player_skill_level < recp.practice_data->min_difficulty ) {
            std::string txt = string_format(
                                  _( "The crafter does not possess the minimum <color_cyan>%s</color> skill level required to practice this." ),
                                  recp.skill_used->name() );
            txt = string_format( "<color_red>%s</color>", txt );
            oss << txt << "\n";
        }
        if( recp.practice_data->skill_limit != MAX_SKILL ) {
            std::string txt = string_format(
                                  _( "This practice action will not increase your <color_cyan>%s</color> skill above %d." ),
                                  recp.skill_used->name(), recp.practice_data->skill_limit );
            if( player_skill_level >= recp.practice_data->skill_limit ) {
                txt = string_format( "<color_brown>%s</color>", txt );
            }
            oss << txt << "\n";
        }
    }
    return oss.str();
}

static input_context make_crafting_context( bool highlight_unread_recipes )
{
    input_context ctxt( "CRAFTING" );
    ctxt.register_cardinal();
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "CONFIRM" );
    ctxt.register_action( "SCROLL_RECIPE_INFO_UP" );
    ctxt.register_action( "SCROLL_RECIPE_INFO_DOWN" );
    ctxt.register_action( "PAGE_UP", to_translation( "Fast scroll up" ) );
    ctxt.register_action( "PAGE_DOWN", to_translation( "Fast scroll down" ) );
    ctxt.register_action( "HOME" );
    ctxt.register_action( "END" );
    ctxt.register_action( "SCROLL_ITEM_INFO_UP" );
    ctxt.register_action( "SCROLL_ITEM_INFO_DOWN" );
    ctxt.register_action( "PREV_TAB" );
    ctxt.register_action( "NEXT_TAB" );
    ctxt.register_action( "FILTER" );
    ctxt.register_action( "RESET_FILTER" );
    ctxt.register_action( "TOGGLE_FAVORITE" );
    ctxt.register_action( "HELP_RECIPE" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    ctxt.register_action( "CYCLE_BATCH" );
    ctxt.register_action( "CHOOSE_CRAFTER" );
    ctxt.register_action( "RELATED_RECIPES" );
    ctxt.register_action( "HIDE_SHOW_RECIPE" );
    ctxt.register_action( "SELECT" );
    ctxt.register_action( "SEC_SELECT" );
    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "SCROLL_UP" );
    ctxt.register_action( "SCROLL_DOWN" );
    ctxt.register_action( "COMPARE" );
    if( highlight_unread_recipes ) {
        ctxt.register_action( "TOGGLE_RECIPE_UNREAD" );
        ctxt.register_action( "MARK_ALL_RECIPES_READ" );
        ctxt.register_action( "TOGGLE_UNREAD_RECIPES_FIRST" );
    }
    return ctxt;
}

class recipe_result_info_cache
{
        Character &crafter;
        std::vector<iteminfo> info;
        const recipe *last_recipe = nullptr;
        int last_terminal_width = 0;
        int panel_width;
        int cached_batch_size = 1;
        int lang_version = 0;

        void get_byproducts_data( const recipe *rec, std::vector<iteminfo> &summary_info,
                                  std::vector<iteminfo> &details_info );
        void get_item_details( item &dummy_item, int quantity_per_batch,
                               std::vector<iteminfo> &details_info, const std::string &classification, bool uses_charges,
                               const std::string &description = std::string() );
        void get_item_header( item &dummy_item, int quantity_per_batch, std::vector<iteminfo> &info,
                              const std::string &classification, bool uses_charges,
                              const std::string &description = std::string() );
        void insert_iteminfo_block_separator( std::vector<iteminfo> &info_vec,
                                              const std::string &title ) const;
    public:
        explicit recipe_result_info_cache( Character &_crafter ) : crafter( _crafter ) {};
        item_info_data get_result_data( const recipe *rec, int batch_size, int &scroll_pos,
                                        const catacurses::window &window );
};

void recipe_result_info_cache::get_byproducts_data( const recipe *rec,
        std::vector<iteminfo> &summary_info, std::vector<iteminfo> &details_info )
{
    const std::string byproduct_string = _( "Byproduct" );

    for( const std::pair<const itype_id, int> &bp : rec->get_byproducts() ) {
        insert_iteminfo_block_separator( details_info, byproduct_string );
        item dummy_item = item( bp.first );
        bool uses_charges = dummy_item.count_by_charges();
        get_item_header( dummy_item, bp.second, summary_info, _( "With byproduct" ), uses_charges );
        get_item_details( dummy_item, bp.second, details_info, byproduct_string, uses_charges );
    }
}

void recipe_result_info_cache::get_item_details( item &dummy_item,
        const int quantity_per_batch, std::vector<iteminfo> &details_info,
        const std::string &classification, const bool uses_charges, const std::string &description )
{
    std::vector<iteminfo> temp_info;
    int total_quantity = quantity_per_batch * cached_batch_size;
    get_item_header( dummy_item, quantity_per_batch, details_info, classification, uses_charges,
                     description );
    if( uses_charges ) {
        dummy_item.charges *= total_quantity;
        dummy_item.info( true, temp_info );
        dummy_item.charges /= total_quantity;
    } else {
        dummy_item.info( true, temp_info, total_quantity );
    }
    details_info.insert( std::end( details_info ), std::begin( temp_info ), std::end( temp_info ) );
}

void recipe_result_info_cache::get_item_header( item &dummy_item, const int quantity_per_batch,
        std::vector<iteminfo> &info, const std::string &classification, const bool uses_charges,
        const std::string &description )
{
    int total_quantity = quantity_per_batch * cached_batch_size;
    //Handle multiple charges and multiple discrete items separately
    if( uses_charges ) {
        std::string display_name = ( description.empty() ? dummy_item.display_name() : description );
        dummy_item.charges = total_quantity;
        info.emplace_back( "DESCRIPTION",
                           "<bold>" + classification + ": </bold>" + display_name );
        //Reset charges so that multiple calls to this function don't produce unexpected results
        dummy_item.charges /= total_quantity;
    } else {
        std::string display_name = ( description.empty() ? dummy_item.display_name(
                                         total_quantity ) : description );
        //Add summary line.  Don't need to indicate count if there's only 1
        info.emplace_back( "DESCRIPTION",
                           "<bold>" + classification + ": </bold>" + display_name +
                           ( total_quantity == 1 ? "" : string_format( " (%d)", total_quantity ) ) );
    }
    if( dummy_item.has_flag( flag_VARSIZE ) &&
        dummy_item.has_flag( flag_FIT ) ) {
        /* Resulting item can be (poor fit).  Check if it can actually be crafted as poor fit
         * Currently, that means: can it have poorly-fitted components?*/
        std::vector<std::vector<item_comp> > item_component_reqs =
            last_recipe->simple_requirements().get_components();
        bool has_varsize_components = false;
        for( const std::vector<item_comp> &component_options : item_component_reqs ) {
            for( const item_comp &component : component_options ) {
                const itype *type = item::find_type( component.type );
                if( type->has_flag( flag_VARSIZE ) ) {
                    has_varsize_components = true;
                    break;
                }
            }
            if( has_varsize_components ) {
                break;
            }
        }
        if( has_varsize_components ) {
            info.emplace_back( "DESCRIPTION",
                               _( "<bold>Note:</bold> If crafted from poorly-fitting components, the resulting item may also be poorly-fitted." ) );
        }
    }
}

static item get_recipe_result_item( const recipe &rec, Character &crafter )
{
    item dummy_result = item( rec.result(), calendar::turn, item::default_charges_tag{} );
    if( !rec.variant().empty() ) {
        dummy_result.set_itype_variant( rec.variant() );
    }
    //Check if recipe result is a clothing item that can be properly fitted
    if( dummy_result.has_flag( flag_VARSIZE ) && !dummy_result.has_flag( flag_FIT ) ) {
        //Check if it can actually fit.  If so, list the fitted info
        item::sizing general_fit = dummy_result.get_sizing( crafter );
        if( general_fit == item::sizing::small_sized_small_char ||
            general_fit == item::sizing::human_sized_human_char ||
            general_fit == item::sizing::big_sized_big_char ||
            general_fit == item::sizing::ignore ) {
            dummy_result.set_flag( flag_FIT );
        }
    }
    if( dummy_result.count_by_charges() ) {
        dummy_result.charges = 1;
    }
    dummy_result.set_var( "recipe_exemplar", rec.ident().str() );
    return dummy_result;
}

item_info_data recipe_result_info_cache::get_result_data( const recipe *rec, const int batch_size,
        int &scroll_pos, const catacurses::window &window )
{
    //lang check here is needed to rebuild cache when using "Toggle language to English" option
    if( lang_version == detail::get_current_language_version() ) {
        /* If the recipe has not changed, return the cached version in info.
           Unfortunately, the separator lines are baked into info at a specific width, so if the terminal width
           has changed, the info needs to be regenerated */
        if( rec == last_recipe
            && rec != nullptr
            && TERMX == last_terminal_width
            && batch_size == cached_batch_size
          ) {
            item_info_data data( "", "", info, {}, scroll_pos );
            return data;
        }
    } else {
        lang_version = detail::get_current_language_version();
    }

    cached_batch_size = batch_size;
    last_recipe = rec;
    scroll_pos = 0;
    last_terminal_width = TERMX;
    panel_width = getmaxx( window );

    info.clear(); //New recipe, new info

    /*We need to do some calculations to put together the results summary and very similar calculations to
      put together the details, so, have a separate vector specifically for the details, to be appended later */
    std::vector<iteminfo> details_info;

    //Make a temporary item for the result.  NOTE: If the result would normally be in a container, this is not.
    item dummy_result = get_recipe_result_item( *rec, crafter );
    std::string result_description;
    if( dummy_result.is_null() ) {
        result_description = rec->description.translated();
    }
    bool result_uses_charges = dummy_result.count_by_charges();
    int const makes_amount = rec->makes_amount();
    item dummy_container;

    //Several terms are used repeatedly in headers/descriptions, list them here for a single entry/translation point
    const std::string result_string = _( "Result" );
    const std::string recipe_output_string = _( "Recipe Outputs" );
    const std::string recipe_result_string = _( "Recipe Result" );
    const std::string container_string = _( "Container" );
    // Every learnable recipe in a container is sealed.
    const std::string in_container_string = _( "In sealed container" );
    const std::string container_info_string = _( "Container Information" );

    //Set up summary at top so people know they can look further to learn about byproducts and such
    //First, see if we need it at all:
    if( rec->container_id() == itype_id::NULL_ID() && !rec->has_byproducts() ) {
        //We don't need a summary for a single item, just give us the details
        insert_iteminfo_block_separator( details_info, recipe_result_string );
        get_item_details( dummy_result, makes_amount, details_info, result_string, result_uses_charges,
                          result_description );

    } else { //We do need a summary
        //Top of the header
        insert_iteminfo_block_separator( info, recipe_output_string );
        //If the primary result uses charges and is in a container, need to calculate number of charges
        //If it's in a container, focus on the contents
        if( rec->container_id() != itype_id::NULL_ID() ) {
            dummy_container = item( rec->container_id(), calendar::turn, item::default_charges_tag{} );
            //Put together the summary in info:
            get_item_header( dummy_result, makes_amount, info, recipe_result_string, result_uses_charges );
            get_item_header( dummy_container, 1, info, in_container_string,
                             false ); //Seems reasonable to assume a container won't use charges
            //Put together the details in details_info:
            insert_iteminfo_block_separator( details_info, recipe_result_string );
            get_item_details( dummy_result, makes_amount, details_info, recipe_result_string,
                              result_uses_charges );

            insert_iteminfo_block_separator( details_info, container_info_string );
            get_item_details( dummy_container, 1, details_info, container_string, false );
        } else { //If it's not in a container, just tell us about the item
            //Add a line to the summary:
            get_item_header( dummy_result, makes_amount, info, recipe_result_string, result_uses_charges );
            //Add the details 'header'
            insert_iteminfo_block_separator( details_info, recipe_result_string );
            //Get the item details:
            get_item_details( dummy_result, makes_amount, details_info, recipe_result_string,
                              result_uses_charges );
        }
        if( rec->has_byproducts() ) {
            get_byproducts_data( rec, info, details_info );
        }
        info.emplace_back( "DESCRIPTION", "  " );  //Blank line for formatting
    }
    //Merge summary and details
    info.insert( std::end( info ), std::begin( details_info ), std::end( details_info ) );
    item_info_data data( "", "", info, {}, scroll_pos );
    return data;
}

void recipe_result_info_cache::insert_iteminfo_block_separator( std::vector<iteminfo> &info_vec,
        const std::string &title ) const
{
    info_vec.emplace_back( "DESCRIPTION", "--" );
    info_vec.emplace_back( "DESCRIPTION", std::string( center_text_pos( title, 0,
                           panel_width ), ' ' ) +
                           "<bold>" + title + "</bold>" );
    info_vec.emplace_back( "DESCRIPTION", "--" );
}

std::pair<std::vector<const recipe *>, bool> recipes_from_cat( const recipe_subset
        &available_recipes, const crafting_category_id &cat, const std::string &subcat )
{
    if( subcat == "CSC_*_FAVORITE" ) {
        return std::make_pair( available_recipes.favorite(), false );
    } else if( subcat == "CSC_*_RECENT" ) {
        return std::make_pair( available_recipes.recent(), false );
    } else if( subcat == "CSC_*_HIDDEN" ) {
        return std::make_pair( available_recipes.hidden(), true );
    } else {
        return std::make_pair( available_recipes.in_category( cat, subcat != "CSC_ALL" ? subcat : "" ),
                               false );
    }
}

struct recipe_info_cache {
    const recipe *recp = nullptr;
    character_id guy_id;
    std::string qry_comps;
    int batch_size;
    int fold_width;
    std::vector<std::string> text;
};

static const std::vector<std::string> &cached_recipe_info( recipe_info_cache &info_cache,
        const recipe &recp, const availability &avail, Character &guy, const std::string &qry_comps,
        const int batch_size, const int fold_width, const nc_color &color,
        const std::vector<Character *> &crafting_group )
{
    static int lang_version = detail::get_current_language_version();

    if( info_cache.recp != &recp ||
        info_cache.guy_id != guy.getID() ||
        info_cache.qry_comps != qry_comps ||
        info_cache.batch_size != batch_size ||
        info_cache.fold_width != fold_width ||
        lang_version != detail::get_current_language_version()
      ) {
        info_cache.recp = &recp;
        info_cache.guy_id = guy.getID();
        info_cache.qry_comps = qry_comps;
        info_cache.batch_size = batch_size;
        info_cache.fold_width = fold_width;
        info_cache.text = recipe_info( recp, avail, guy, qry_comps, batch_size, fold_width, color,
                                       crafting_group );
        lang_version = detail::get_current_language_version();
    }
    return info_cache.text;
}

struct item_info_cache {
    const recipe *last_recipe = nullptr;
    item dummy;
};

static recipe_subset filter_recipes( const recipe_subset &available_recipes,
                                     std::string_view qry,
                                     const Character &crafter,
                                     const std::function<void( size_t, size_t )> &progress_callback )
{
    size_t qry_begin = 0;
    size_t qry_end = 0;
    recipe_subset filtered_recipes = available_recipes;
    do {
        // Find next ','
        qry_end = qry.find_first_of( ',', qry_begin );

        std::string qry_filter_str = trim( qry.substr( qry_begin, qry_end - qry_begin ) );
        // Process filter
        if( qry_filter_str.size() > 2 && qry_filter_str[1] == ':' ) {
            switch( qry_filter_str[0] ) {
                case 't':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::tool, progress_callback );
                    break;

                case 'c':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::component, progress_callback );
                    break;

                case 's':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::skill, progress_callback );
                    break;

                case 'p':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::primary_skill, progress_callback );
                    break;

                case 'Q':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::quality, progress_callback );
                    break;

                case 'q':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::quality_result, progress_callback );
                    break;

                case 'L':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::length, progress_callback );
                    break;

                case 'V':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::volume, progress_callback );
                    break;

                case 'M':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::mass, progress_callback );
                    break;

                case 'v':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::covers, progress_callback );
                    break;

                case 'e':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::layer, progress_callback );
                    break;

                case 'd':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::description_result, progress_callback );
                    break;

                case 'm': {
                    // get_learned_recipes lists NO nested_recipes
                    const recipe_subset &learned = crafter.get_learned_recipes();
                    recipe_subset temp_subset;
                    if( query_is_yes( qry_filter_str ) ) {
                        temp_subset = available_recipes.intersection( learned );
                    } else {
                        // nested_recipes cannot be learned so don't show them
                        temp_subset = available_recipes.difference( learned )
                                      .difference( recipe_dict.all_nested() );
                    }
                    filtered_recipes = filtered_recipes.intersection( temp_subset );
                    break;
                }

                case 'P':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::proficiency, progress_callback );
                    break;

                case 'l':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::difficulty, progress_callback );
                    break;

                case 'r': {
                    recipe_subset result;
                    for( const itype *e : item_controller->all() ) {
                        if( lcmatch( e->nname( 1 ), qry_filter_str.substr( 2 ) ) ) {
                            result.include( recipe_subset( available_recipes,
                                                           available_recipes.recipes_that_produce( e->get_id() ) ) );
                        }
                    }
                    filtered_recipes = result;

                    break;
                }

                case 'a':
                    filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 2 ),
                                       recipe_subset::search_type::activity_level, progress_callback );
                    break;
                default:
                    break;
            }
        } else if( qry_filter_str.size() > 1 && qry_filter_str[0] == '-' ) {
            filtered_recipes = filtered_recipes.reduce( qry_filter_str.substr( 1 ),
                               recipe_subset::search_type::exclude_name, progress_callback );
        } else {
            filtered_recipes = filtered_recipes.reduce( qry_filter_str );
        }

        qry_begin = qry_end + 1;
    } while( qry_end != std::string::npos );
    return filtered_recipes;
}

namespace
{
struct SearchPrefix {
    char key;
    translation example;
    translation description;
};
} // namespace

static const std::vector<SearchPrefix> prefixes = {
    //~ Example result description search term
    { 'q', to_translation( "metal sawing" ), to_translation( "<color_cyan>quality</color> of resulting item" ) },
    { 'd', to_translation( "reach attack" ), to_translation( "<color_cyan>full description</color> of resulting item (slow)" ) },
    { 'c', to_translation( "plank" ), to_translation( "<color_cyan>component</color> required to craft" ) },
    { 'p', to_translation( "tailoring" ), to_translation( "<color_cyan>primary skill</color> used to craft" ) },
    { 's', to_translation( "food handling" ), to_translation( "<color_cyan>any skill</color> used to craft" ) },
    { 'Q', to_translation( "fine bolt turning" ), to_translation( "<color_cyan>quality</color> required to craft" ) },
    { 't', to_translation( "soldering iron" ), to_translation( "<color_cyan>tool</color> required to craft" ) },
    { 'm', to_translation( "yes" ), to_translation( "recipe <color_cyan>memorized</color> (or not)" ) },
    { 'P', to_translation( "Blacksmithing" ), to_translation( "<color_cyan>proficiency</color> used to craft" ) },
    { 'l', to_translation( "5" ), to_translation( "<color_cyan>difficulty</color> of the recipe as a number or range" ) },
    { 'r', to_translation( "buttermilk" ), to_translation( "recipe's (<color_cyan>by</color>)<color_cyan>products</color>" ) },
    { 'L', to_translation( "122 cm" ), to_translation( "result can contain item of <color_cyan>length</color>" ) },
    { 'V', to_translation( "450 ml" ), to_translation( "result can contain item of <color_cyan>volume</color>" ) },
    { 'M', to_translation( "250 kg" ), to_translation( "result can contain item of <color_cyan>mass</color>" ) },
    { 'v', to_translation( "head" ), to_translation( "<color_cyan>body part</color> the result covers" ) },
    { 'e', to_translation( "close to skin" ), to_translation( "<color_cyan>layer</color> the result covers" ) },
    { 'a', to_translation( "brisk" ), to_translation( "recipe's <color_cyan>activity level</color>" ) }
};

static const translation filter_help_start = to_translation(
            "The default is to search result names.  Some single-character prefixes "
            "can be used with a colon <color_red>:</color> to search in other ways.  Additional filters "
            "are separated by commas <color_red>,</color>.\n"
            "Filtering by difficulty can accept range; "
            "<color_yellow>l</color><color_white>:5~10</color> for all recipes from difficulty 5 to 10.\n"
            "\n\n"
            "<color_white>Examples:</color>\n" );

static bool mouse_in_window( std::optional<point> coord, const catacurses::window &w_ )
{
    if( coord.has_value() ) {
        inclusive_rectangle<point> window_area( point( getbegx( w_ ), getbegy( w_ ) ),
                                                point( getmaxx( w_ ) + getbegx( w_ ), getmaxy( w_ ) + getbegy( w_ ) ) );
        if( window_area.contains( coord.value() ) ) {
            return true;
        }
    }
    return false;
}

static void recursively_expance_recipes( std::vector<const recipe *> &current,
        std::vector<int> &indent, std::map<const recipe *, availability> &availability_cache, int i,
        Character &crafter, bool unread_recipes_first, bool highlight_unread_recipes,
        const recipe_subset &available_recipes, const std::set<recipe_id> &hidden_recipes,
        const bool camp_crafting = false, inventory *inventory_override = nullptr )
{
    std::vector<const recipe *> tmp;
    for( const recipe_id &nested : current[i]->nested_category_data ) {

        if( available_recipes.contains( &nested.obj() )
            && hidden_recipes.find( nested ) == hidden_recipes.end()
          ) {
            // only do this if we can actually craft the recipe
            tmp.push_back( &nested.obj() );
            indent.insert( indent.begin() + i + 1, indent[i] + 2 );
            if( !availability_cache.count( &nested.obj() ) ) {
                availability_cache.emplace( &nested.obj(), availability( crafter, &nested.obj(), 1,
                                                camp_crafting, inventory_override ) );
            }
        }
    }

    std::stable_sort( tmp.begin(), tmp.end(), [
                       &crafter, &availability_cache, unread_recipes_first,
                       highlight_unread_recipes
    ]( const recipe * const a, const recipe * const b ) {
        if( highlight_unread_recipes && unread_recipes_first ) {
            const bool a_read = uistate.read_recipes.count( a->ident() );
            const bool b_read = uistate.read_recipes.count( b->ident() );
            if( a_read != b_read ) {
                return !a_read;
            }
        }
        const bool can_craft_a = availability_cache.at( a ).can_craft;
        const bool can_craft_b = availability_cache.at( b ).can_craft;
        if( can_craft_a != can_craft_b ) {
            return can_craft_a;
        }
        if( b->difficulty != a->difficulty ) {
            return b->difficulty < a->difficulty;
        }
        const std::string a_name = a->result_name();
        const std::string b_name = b->result_name();
        if( a_name != b_name ) {
            return localized_compare( a_name, b_name );
        }
        return b->time_to_craft( crafter ) <
               a->time_to_craft( crafter );
    } );

    current.insert( current.begin() + i + 1, tmp.begin(), tmp.end() );
}

// take the current and itterate through expanding each recipe
static void expand_recipes( std::vector<const recipe *> &current,
                            std::vector<int> &indent, std::map<const recipe *, availability> &availability_cache,
                            Character &crafter, bool unread_recipes_first, bool highlight_unread_recipes,
                            const recipe_subset &available_recipes, const std::set<recipe_id> &hidden_recipes,
                            const bool camp_crafting = false, inventory *inventory_override = nullptr )
{
    //TODO Make this more effecient
    for( size_t i = 0; i < current.size(); ++i ) {
        if( current[i]->is_nested()
            && uistate.expanded_recipes.find( current[i]->ident() ) != uistate.expanded_recipes.end()
          ) {
            // add all the recipes from the nests
            recursively_expance_recipes( current, indent, availability_cache, i, crafter,
                                         unread_recipes_first, highlight_unread_recipes, available_recipes,
                                         hidden_recipes, camp_crafting, inventory_override );
        }
    }
}

static std::string list_nested( Character &crafter, const recipe *rec,
                                const recipe_subset &available_recipes,
                                int indent = 0 )
{
    std::string description;
    availability avail( crafter, rec );
    if( rec->is_nested() ) {
        description += colorize( std::string( indent,
                                              ' ' ) + rec->result_name() + ":\n", avail.color() );
        for( const recipe_id &r : rec->nested_category_data ) {
            description += list_nested( crafter, &r.obj(), available_recipes, indent + 2 );
        }
    } else if( available_recipes.contains( rec ) ) {
        description += colorize( std::string( indent,
                                              ' ' ) + rec->result_name() + "\n", avail.color() );
    }

    return description;
}

static void nested_toggle( recipe_id rec, bool &recalc, bool &keepline )
{
    auto loc = uistate.expanded_recipes.find( rec );
    if( loc != uistate.expanded_recipes.end() ) {
        uistate.expanded_recipes.erase( rec );
    } else {
        uistate.expanded_recipes.insert( rec );
    }
    recalc = true;
    keepline = true;
}

static bool selection_ok( const std::vector<const recipe *> &list, const int current_line,
                          const bool nested_acceptable )
{
    if( list.empty() ) {
        popup( _( "Nothing selected!" ) );
    } else if( list[current_line]->is_nested() && !nested_acceptable ) {
        popup( _( "Select a recipe within this group" ) );
    } else {
        return true;
    }
    return false;
}

static std::pair<Character *, const recipe *> select_crafter_and_crafting_recipe_legacy(
    int &batch_size_out, const recipe_id &goto_recipe, Character *crafter,
    std::string filterstring, bool camp_crafting, inventory *inventory_override );

static std::pair<Character *, const recipe *> select_crafter_and_crafting_recipe_browser(
    int &batch_size_out, const recipe_id &goto_recipe, Character *crafter,
    std::string filterstring, const bool camp_crafting, inventory *inventory_override )
{
    if( crafter == nullptr ) {
        return { nullptr, nullptr };
    }

    const bool highlight_unread_recipes = get_option<bool>( "HIGHLIGHT_UNREAD_RECIPES" );
    input_context ctxt = make_crafting_context( highlight_unread_recipes );
    std::unique_ptr<recipe_result_info_cache> result_info =
        std::make_unique<recipe_result_info_cache>( *crafter );
    recipe_info_cache r_info_cache;

    crafting_browser_state state;
    state.selected_category = uistate.crafting_browser_category;
    state.selected_subcategory = uistate.crafting_browser_subcategory;
    state.search_query = filterstring.empty() ? uistate.crafting_browser_search : filterstring;
    state.craftable_only = uistate.crafting_browser_craftable_only;
    state.memorized_only = uistate.crafting_browser_memorized_only;
    state.unread_only = highlight_unread_recipes && uistate.crafting_browser_unread_only;
    state.unread_first = highlight_unread_recipes && uistate.crafting_browser_unread_first;
    state.category_scroll = std::max( 0, uistate.crafting_browser_category_scroll );
    state.recipe_scroll = std::max( 0, uistate.crafting_browser_recipe_scroll );
    state.inspector_scroll = std::max( 0, uistate.crafting_browser_inspector_scroll );
    state.batch_size = std::clamp( uistate.crafting_browser_batch_size, 1, 50 );
    state.focused_pane = static_cast<crafting_browser_pane>(
                             std::clamp( uistate.crafting_browser_focused_pane, 0, 2 ) );

    std::vector<std::string> crafting_categories;
    crafting_categories.reserve( craft_cat_list.size() );
    for( const crafting_category &cat : craft_cat_list.get_all() ) {
        if( !cat.is_hidden ) {
            crafting_categories.emplace_back( cat.id.str() );
        }
    }
    if( crafting_categories.empty() ) {
        return { crafter, nullptr };
    }

    const auto category_is_valid = [&]( const std::string & category ) {
        return std::find( crafting_categories.begin(), crafting_categories.end(), category ) !=
               crafting_categories.end();
    };
    const auto first_subcategory = []( const std::string & category ) {
        const std::vector<std::string> *subcategories = subcategories_for_category( category );
        if( subcategories == nullptr || subcategories->empty() ) {
            return std::string();
        }
        return subcategories->front();
    };
    const auto subcategory_is_valid = [&]( const std::string & category,
    const std::string & subcategory ) {
        const std::vector<std::string> *subcategories = subcategories_for_category( category );
        return subcategories != nullptr &&
               std::find( subcategories->begin(), subcategories->end(), subcategory ) !=
               subcategories->end();
    };

    if( !category_is_valid( state.selected_category ) ) {
        state.selected_category = category_is_valid( "CC_*" ) ? "CC_*" : crafting_categories.front();
    }
    if( !subcategory_is_valid( state.selected_category, state.selected_subcategory ) ) {
        state.selected_subcategory = first_subcategory( state.selected_category );
    }

    const recipe_subset &available_recipes =
        crafter->get_group_available_recipes( inventory_override );
    if( uistate.crafting_browser_recipe.is_valid() ) {
        const recipe *saved_recipe = &uistate.crafting_browser_recipe.obj();
        if( available_recipes.contains( saved_recipe ) ) {
            state.selected_recipe = saved_recipe;
        }
    }
    if( goto_recipe.is_valid() && available_recipes.contains( &goto_recipe.obj() ) ) {
        state.selected_recipe = &goto_recipe.obj();
        state.selected_category = goto_recipe->category.str();
        state.selected_subcategory = "CSC_ALL";
        if( uistate.hidden_recipes.count( goto_recipe ) ) {
            state.selected_category = "CC_*";
            state.selected_subcategory = "CSC_*_HIDDEN";
        }
    }

    const std::vector<Character *> crafting_group = crafter->get_crafting_group();
    int crafter_i = find( crafting_group.begin(), crafting_group.end(), crafter ) -
                    crafting_group.begin();
    std::map<character_id, std::map<const recipe *, availability>> guy_availability_cache;
    std::map<const recipe *, availability> *availability_cache =
        &guy_availability_cache[crafter->getID()];

    std::vector<const recipe *> current;
    std::vector<int> indent;
    std::vector<availability> available;
    bool show_hidden = false;
    size_t num_hidden = 0;
    bool recalc = true;
    bool recalc_unread = highlight_unread_recipes;
    bool done = false;
    const recipe *chosen = nullptr;
    std::string workspace_status;

    std::map<std::string, bool> is_cat_unread;
    std::map<std::string, std::map<std::string, bool>> is_subcat_unread;
    std::vector<crafting_sidebar_entry> sidebar_entries;
    std::vector<std::pair<inclusive_rectangle<point>, int>> sidebar_hits;
    std::vector<std::pair<inclusive_rectangle<point>, int>> recipe_hits;
    std::vector<std::pair<inclusive_rectangle<point>, crafting_browser_pane>> pane_hits;
    std::vector<crafting_browser_button> inspector_buttons;
    std::vector<crafting_browser_button> toolbar_buttons;
    std::vector<crafting_browser_button> context_buttons;
    int hovered_sidebar_entry = -1;
    std::string hovered_inspector_action;
    std::string hovered_toolbar_action;
    int hovered_context_button = -1;

    catacurses::window w_header;
    catacurses::window w_sidebar;
    catacurses::window w_recipes;
    catacurses::window w_inspector;
    catacurses::window w_actions;
    bool compact_layout = false;
    int browser_width = 0;
    int browser_start = 0;
    int header_height = 3;
    int body_height = 0;
    constexpr int action_height = 5;
    inclusive_rectangle<point> search_hit;
    inclusive_rectangle<point> search_clear_hit;
    point search_edit_start;
    int search_edit_end = 0;

    std::unique_ptr<availability> selected_batch_availability;
    const recipe *selected_availability_recipe = nullptr;
    character_id selected_availability_crafter;
    int selected_availability_batch = 0;

    const auto selected_index = [&]() -> int {
        if( state.selected_recipe == nullptr ) {
            return -1;
        }
        const auto found = std::find( current.begin(), current.end(), state.selected_recipe );
        return found == current.end() ? -1 : static_cast<int>( found - current.begin() );
    };

    const auto select_index = [&]( const int requested, const bool mark_read ) {
        if( current.empty() ) {
            state.selected_recipe = nullptr;
            return;
        }
        const int index = std::clamp( requested, 0, static_cast<int>( current.size() ) - 1 );
        const recipe *previous = state.selected_recipe;
        state.selected_recipe = current[index];
        if( previous != state.selected_recipe ) {
            workspace_status.clear();
            state.inspector_scroll = 0;
            state.context_open = false;
            state.last_clicked_recipe = nullptr;
            state.last_click_time.reset();
            selected_batch_availability.reset();
            r_info_cache.recp = nullptr;
        }
        if( mark_read && highlight_unread_recipes ) {
            if( previous != nullptr ) {
                uistate.read_recipes.insert( previous->ident() );
            }
            uistate.read_recipes.insert( state.selected_recipe->ident() );
            recalc_unread = true;
        }
    };

    const auto selected_availability = [&]() -> availability * {
        if( state.selected_recipe == nullptr ) {
            return nullptr;
        }
        if( selected_batch_availability == nullptr ||
            selected_availability_recipe != state.selected_recipe ||
            selected_availability_crafter != crafter->getID() ||
            selected_availability_batch != state.batch_size ) {
            selected_batch_availability = std::make_unique<availability>(
                                              *crafter, state.selected_recipe, state.batch_size,
                                              camp_crafting, inventory_override );
            selected_availability_recipe = state.selected_recipe;
            selected_availability_crafter = crafter->getID();
            selected_availability_batch = state.batch_size;
        }
        return selected_batch_availability.get();
    };

    const auto invalidate_selected_details = [&]() {
        selected_batch_availability.reset();
        selected_availability_recipe = nullptr;
        selected_availability_batch = 0;
        r_info_cache.recp = nullptr;
    };

    const auto persist_state = [&]() {
        uistate.crafting_browser_category = state.selected_category;
        uistate.crafting_browser_subcategory = state.selected_subcategory;
        uistate.crafting_browser_recipe = state.selected_recipe != nullptr ?
                                          state.selected_recipe->ident() : recipe_id::NULL_ID();
        uistate.crafting_browser_search = state.search_query;
        uistate.crafting_browser_craftable_only = state.craftable_only;
        uistate.crafting_browser_memorized_only = state.memorized_only;
        uistate.crafting_browser_unread_only = state.unread_only;
        uistate.crafting_browser_unread_first = state.unread_first;
        uistate.crafting_browser_category_scroll = state.category_scroll;
        uistate.crafting_browser_recipe_scroll = state.recipe_scroll;
        uistate.crafting_browser_inspector_scroll = state.inspector_scroll;
        uistate.crafting_browser_batch_size = state.batch_size;
        uistate.crafting_browser_focused_pane = static_cast<int>( state.focused_pane );
    };

    const auto rebuild_sidebar = [&]() {
        sidebar_entries.clear();
        sidebar_entries.push_back( { crafting_sidebar_entry_type::heading, _( "BROWSER" ), "", "", false } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::special, _( "★ Favorites" ),
                                     "CC_*", "CSC_*_FAVORITE", true } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::special, _( "Recent" ),
                                     "CC_*", "CSC_*_RECENT", true } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::special, _( "Hidden" ),
                                     "CC_*", "CSC_*_HIDDEN", true } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::special, _( "Nested groups" ),
                                     "CC_*", "CSC_*_NESTED", true } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::heading, _( "FILTERS" ), "", "", false } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::filter, _( "Craftable now" ),
                                     "FILTER_CRAFTABLE", "", true } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::filter, _( "Memorized" ),
                                     "FILTER_MEMORIZED", "", true } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::filter, _( "Unread" ),
                                     "FILTER_UNREAD", "", highlight_unread_recipes } );
        sidebar_entries.push_back( { crafting_sidebar_entry_type::heading, _( "CATEGORIES" ), "", "", false } );

        for( const std::string &category : crafting_categories ) {
            const crafting_category &cat = crafting_category_id( category ).obj();
            if( cat.is_wildcard ) {
                continue;
            }
            std::string label = _( get_cat_unprefixed( category ) );
            if( is_cat_unread[category] ) {
                label += " +";
            }
            sidebar_entries.push_back( { crafting_sidebar_entry_type::category, label,
                                         category, "CSC_ALL", true } );
            if( state.selected_category != category ) {
                continue;
            }
            for( const std::string &subcategory : cat.subcategories ) {
                if( subcategory == "CSC_ALL" ) {
                    continue;
                }
                std::string sub_label = "  " + _( get_subcat_unprefixed( category, subcategory ) );
                if( is_subcat_unread[category][subcategory] ) {
                    sub_label += " +";
                }
                sidebar_entries.push_back( { crafting_sidebar_entry_type::subcategory, sub_label,
                                             category, subcategory, true } );
            }
        }
    };

    ui_adaptor ui( ui_adaptor::disable_uis_below{} );
    ui.on_screen_resize( [&]( ui_adaptor & ui ) {
        browser_width = TERMX;
        browser_start = 0;
        compact_layout = browser_width < 100;
        header_height = compact_layout ? 5 : 3;
        body_height = std::max( 8, TERMY - header_height - action_height );

        w_header = catacurses::newwin( header_height, browser_width, point( browser_start, 0 ) );
        w_actions = catacurses::newwin( action_height, browser_width,
                                        point( browser_start, header_height + body_height ) );
        if( compact_layout ) {
            const point body_pos( browser_start, header_height );
            w_sidebar = catacurses::newwin( body_height, browser_width, body_pos );
            w_recipes = catacurses::newwin( body_height, browser_width, body_pos );
            w_inspector = catacurses::newwin( body_height, browser_width, body_pos );
        } else {
            const int sidebar_width = std::clamp( browser_width / 6, 20, 30 );
            const int recipe_width = std::clamp( browser_width * 36 / 100, 34, 62 );
            const int inspector_width = browser_width - sidebar_width - recipe_width;
            w_sidebar = catacurses::newwin( body_height, sidebar_width,
                                            point( browser_start, header_height ) );
            w_recipes = catacurses::newwin( body_height, recipe_width,
                                            point( browser_start + sidebar_width, header_height ) );
            w_inspector = catacurses::newwin( body_height, inspector_width,
                                              point( browser_start + sidebar_width + recipe_width,
                                                      header_height ) );
        }
        ui.position( point( browser_start, 0 ), point( browser_width, TERMY ) );
    } );
    ui.mark_resize();

    ui.on_redraw( [&]( ui_adaptor & ui ) {
        rebuild_sidebar();
        sidebar_hits.clear();
        recipe_hits.clear();
        pane_hits.clear();
        inspector_buttons.clear();
        toolbar_buttons.clear();
        context_buttons.clear();

        werase( w_header );
        draw_border( w_header, BORDER_COLOR );
        const std::string title = camp_crafting ? _( "CAMP CRAFTING" ) : _( "CRAFTING" );
        mvwprintz( w_header, point( 2, 1 ), c_light_green, "%s", title );

        const int search_y = compact_layout ? 2 : 1;
        const int search_x = compact_layout ? 2 : std::max( 28, browser_width / 2 );
        const int search_width = std::max( 16, browser_width - search_x - 2 );
        const std::string search_label = _( "Search: " );
        mvwprintz( w_header, point( search_x, search_y ), c_light_gray, "%s", search_label );
        const int field_x = search_x + utf8_width( search_label );
        const int field_width = std::max( 8, search_width - utf8_width( search_label ) );
        mvwputch( w_header, point( field_x, search_y ), c_light_cyan, '[' );
        mvwputch( w_header, point( field_x + field_width - 1, search_y ), c_light_cyan, ']' );
        const bool has_search = !state.search_query.empty();
        const std::string shown_search = has_search ? state.search_query : _( "Search recipes…" );
        trim_and_print( w_header, point( field_x + 1, search_y ), std::max( 1, field_width - 5 ),
                        has_search ? c_white : c_dark_gray, shown_search );
        trim_and_print( w_header, point( field_x + field_width - 4, search_y ), 3,
                        has_search ? c_light_red : c_dark_gray, "[x]" );
        search_hit = inclusive_rectangle<point>( point( field_x, search_y ),
                     point( field_x + field_width - 5, search_y ) );
        search_clear_hit = inclusive_rectangle<point>( point( field_x + field_width - 4, search_y ),
                           point( field_x + field_width - 2, search_y ) );
        search_edit_start = point( field_x + 1, search_y );
        search_edit_end = field_x + field_width - 5;

        if( compact_layout ) {
            int pane_x = 2;
            const std::array<std::pair<crafting_browser_pane, std::string>, 3> panes = {{
                    { crafting_browser_pane::categories, _( "Categories" ) },
                    { crafting_browser_pane::recipes, _( "Recipes" ) },
                    { crafting_browser_pane::inspector, _( "Inspector" ) }
                }};
            for( const auto &pane : panes ) {
                const std::string label = string_format( "[ %s ]", pane.second );
                const int label_width = utf8_width( label );
                trim_and_print( w_header, point( pane_x, 3 ), label_width,
                                state.focused_pane == pane.first ? h_light_cyan : c_light_cyan, label );
                pane_hits.emplace_back( inclusive_rectangle<point>( point( pane_x, 3 ),
                                        point( pane_x + label_width - 1, 3 ) ), pane.first );
                pane_x += label_width + 1;
            }
        }
        wnoutrefresh( w_header );

        const bool draw_sidebar = !compact_layout ||
                                  state.focused_pane == crafting_browser_pane::categories;
        const bool draw_recipes = !compact_layout ||
                                  state.focused_pane == crafting_browser_pane::recipes;
        const bool draw_inspector = !compact_layout ||
                                    state.focused_pane == crafting_browser_pane::inspector;

        if( draw_sidebar ) {
            werase( w_sidebar );
            draw_border( w_sidebar, BORDER_COLOR, _( "CATEGORIES" ), c_light_green );
            const int sidebar_width = getmaxx( w_sidebar );
            const int visible = std::max( 1, getmaxy( w_sidebar ) - 2 );
            const int max_scroll = std::max( 0, static_cast<int>( sidebar_entries.size() ) - visible );
            state.category_scroll = std::clamp( state.category_scroll, 0, max_scroll );
            for( int row = 0; row < visible; ++row ) {
                const int index = state.category_scroll + row;
                if( index >= static_cast<int>( sidebar_entries.size() ) ) {
                    break;
                }
                const crafting_sidebar_entry &entry = sidebar_entries[index];
                bool selected = false;
                std::string label = entry.label;
                if( entry.type == crafting_sidebar_entry_type::special ||
                    entry.type == crafting_sidebar_entry_type::subcategory ) {
                    selected = state.selected_category == entry.category &&
                               state.selected_subcategory == entry.subcategory;
                } else if( entry.type == crafting_sidebar_entry_type::category ) {
                    selected = state.selected_category == entry.category &&
                               state.selected_subcategory == "CSC_ALL";
                } else if( entry.type == crafting_sidebar_entry_type::filter ) {
                    if( entry.category == "FILTER_CRAFTABLE" ) {
                        selected = state.craftable_only;
                    } else if( entry.category == "FILTER_MEMORIZED" ) {
                        selected = state.memorized_only;
                    } else if( entry.category == "FILTER_UNREAD" ) {
                        selected = state.unread_only;
                    }
                    label = string_format( "[%s] %s", selected ? "x" : " ", entry.label );
                }

                nc_color color = c_light_gray;
                if( entry.type == crafting_sidebar_entry_type::heading ) {
                    color = c_light_green;
                } else if( !entry.enabled ) {
                    color = c_dark_gray;
                } else if( selected ) {
                    color = h_light_cyan;
                } else if( hovered_sidebar_entry == index ) {
                    color = hilite( c_light_gray );
                }
                const int y = row + 1;
                trim_and_print( w_sidebar, point( 1, y ), std::max( 1, sidebar_width - 2 ),
                                color, label );
                if( entry.enabled && entry.type != crafting_sidebar_entry_type::heading ) {
                    sidebar_hits.emplace_back( inclusive_rectangle<point>( point( 1, y ),
                                               point( sidebar_width - 2, y ) ), index );
                }
            }
            if( static_cast<int>( sidebar_entries.size() ) > visible ) {
                scrollbar().offset_x( sidebar_width - 1 ).offset_y( 1 )
                .content_size( static_cast<int>( sidebar_entries.size() ) )
                .viewport_pos( state.category_scroll ).viewport_size( visible ).apply( w_sidebar );
            }
            wnoutrefresh( w_sidebar );
        }

        if( draw_recipes ) {
            werase( w_recipes );
            const std::string list_title = string_format( _( "RECIPES (%d)" ),
                                           static_cast<int>( current.size() ) );
            draw_border( w_recipes, BORDER_COLOR, list_title, c_light_green );
            const int list_width = getmaxx( w_recipes );
            const int first_row = 2;
            const int visible = std::max( 1, getmaxy( w_recipes ) - first_row - 1 );
            const int max_scroll = std::max( 0, static_cast<int>( current.size() ) - visible );
            state.recipe_scroll = std::clamp( state.recipe_scroll, 0, max_scroll );

            std::string scope = state.search_query.empty() ?
                                _( get_subcat_unprefixed( state.selected_category,
                                                        state.selected_subcategory ) ) :
                                string_format( _( "Search: %s" ), state.search_query );
            if( num_hidden > 0 ) {
                scope += string_format( _( " | %d hidden" ), static_cast<int>( num_hidden ) );
            }
            trim_and_print( w_recipes, point( 1, 1 ), std::max( 1, list_width - 2 ),
                            c_dark_gray, scope );

            if( current.empty() ) {
                trim_and_print( w_recipes, point( 2, first_row ), std::max( 1, list_width - 4 ),
                                c_dark_gray, _( "No recipes match this view." ) );
            }
            for( int row = 0; row < visible; ++row ) {
                const int index = state.recipe_scroll + row;
                if( index >= static_cast<int>( current.size() ) ) {
                    break;
                }
                const recipe *rec = current[index];
                const bool selected = rec == state.selected_recipe;
                const bool hovered = rec == state.hovered_recipe;
                nc_color color = available[index].color();
                if( selected ) {
                    color = available[index].selected_color();
                } else if( hovered ) {
                    color = hilite( color );
                }

                const bool favorite = uistate.favorite_recipes.count( rec->ident() );
                const bool unread = highlight_unread_recipes &&
                                    !uistate.read_recipes.count( rec->ident() );
                std::string prefix;
                prefix += favorite ? "*" : " ";
                prefix += unread ? "+" : " ";
                prefix += " ";
                if( rec->is_nested() ) {
                    prefix += uistate.expanded_recipes.count( rec->ident() ) ? "[-] " : "[+] ";
                }
                std::string name = prefix + std::string( index < static_cast<int>( indent.size() ) ?
                                   indent[index] : 0, ' ' ) + rec->result_name( /*decorated=*/true );
                const std::string metadata = string_format( "D%d", rec->get_difficulty( *crafter ) );
                const int metadata_x = std::max( 5, list_width - utf8_width( metadata ) - 2 );
                const int name_width = std::max( 1, metadata_x - 1 );
                const int y = first_row + row;
                trim_and_print( w_recipes, point( 1, y ), std::max( 1, list_width - 2 ),
                                color, std::string( std::max( 1, list_width - 2 ), ' ' ) );
                trim_and_print( w_recipes, point( 1, y ), name_width, color, name );
                mvwprintz( w_recipes, point( metadata_x, y ), color, "%s", metadata );
                recipe_hits.emplace_back( inclusive_rectangle<point>( point( 1, y ),
                                          point( list_width - 2, y ) ), index );
                if( selected && state.focused_pane == crafting_browser_pane::recipes ) {
                    ui.set_cursor( w_recipes, point( 1, y ) );
                }
            }
            if( static_cast<int>( current.size() ) > visible ) {
                scrollbar().offset_x( list_width - 1 ).offset_y( first_row )
                .content_size( static_cast<int>( current.size() ) )
                .viewport_pos( state.recipe_scroll ).viewport_size( visible ).apply( w_recipes );
            }

            if( state.context_open && state.selected_recipe != nullptr ) {
                availability *avail = selected_availability();
                const std::string reason = avail == nullptr ? _( "Nothing selected." ) :
                                           crafting_unavailable_reason( *state.selected_recipe, *avail,
                                                   *crafter, state.batch_size );
                const bool craft_enabled = avail != nullptr &&
                                           crafting_recipe_can_start( *state.selected_recipe, *avail, *crafter );
                const bool normal_recipe = !state.selected_recipe->is_nested();
                const bool favorite = uistate.favorite_recipes.count( state.selected_recipe->ident() );
                const bool hidden = uistate.hidden_recipes.count( state.selected_recipe->ident() );
                context_buttons = {
                    { "CONFIRM", craft_enabled ? _( "Craft" ) :
                      string_format( _( "Craft — %s" ), reason ), craft_enabled, reason },
                    { "CYCLE_BATCH", _( "Craft batch…" ), normal_recipe,
                      _( "Choose a concrete recipe first." ) },
                    { "TOGGLE_FAVORITE", favorite ? _( "Unfavorite" ) : _( "Favorite" ), true, "" },
                    { "HIDE_SHOW_RECIPE", hidden ? _( "Unhide" ) : _( "Hide" ), true, "" },
                    { "HELP_RECIPE", _( "Examine" ), normal_recipe,
                      _( "Choose a concrete recipe first." ) },
                    { "CHOOSE_CRAFTER", _( "Choose crafter…" ), true, "" },
                    { "RELATED_RECIPES", _( "Related recipes…" ), normal_recipe,
                      _( "Choose a concrete recipe first." ) },
                    { "COMPARE", _( "Compare…" ), normal_recipe,
                      _( "Choose a concrete recipe first." ) }
                };
                int widest = 0;
                for( const crafting_browser_button &button : context_buttons ) {
                    widest = std::max( widest, utf8_width( button.label ) );
                }
                state.context_width = std::clamp( widest + 2, 18, std::max( 18, list_width - 2 ) );
                state.context_height = static_cast<int>( context_buttons.size() ) + 2;
                state.context_pos.x = std::clamp( state.context_pos.x, 1,
                                                  std::max( 1, list_width - state.context_width - 1 ) );
                state.context_pos.y = std::clamp( state.context_pos.y, 1,
                                                  std::max( 1, getmaxy( w_recipes ) -
                                                            state.context_height - 1 ) );
                const std::string blank( state.context_width, ' ' );
                for( int row = 0; row < state.context_height; ++row ) {
                    mvwprintz( w_recipes, state.context_pos + point( 0, row ), c_black, "%s", blank );
                }
                mvwhline( w_recipes, state.context_pos, c_light_gray, LINE_OXOX, state.context_width );
                mvwhline( w_recipes, state.context_pos + point( 0, state.context_height - 1 ),
                          c_light_gray, LINE_OXOX, state.context_width );
                mvwvline( w_recipes, state.context_pos, c_light_gray, LINE_XOXO,
                          state.context_height );
                mvwvline( w_recipes, state.context_pos + point( state.context_width - 1, 0 ),
                          c_light_gray, LINE_XOXO, state.context_height );
                mvwputch( w_recipes, state.context_pos, c_light_gray, LINE_OXXO );
                mvwputch( w_recipes, state.context_pos + point( state.context_width - 1, 0 ),
                          c_light_gray, LINE_OOXX );
                mvwputch( w_recipes, state.context_pos + point( 0, state.context_height - 1 ),
                          c_light_gray, LINE_XXOO );
                mvwputch( w_recipes, state.context_pos +
                          point( state.context_width - 1, state.context_height - 1 ),
                          c_light_gray, LINE_XOOX );
                for( int i = 0; i < static_cast<int>( context_buttons.size() ); ++i ) {
                    crafting_browser_button &button = context_buttons[i];
                    button.pos = state.context_pos + point( 1, i + 1 );
                    button.width = state.context_width - 2;
                    const nc_color color = !button.enabled ? c_dark_gray :
                                           hovered_context_button == i ? h_green : c_light_green;
                    trim_and_print( w_recipes, button.pos, button.width, color, button.label );
                }
            }
            wnoutrefresh( w_recipes );
        }

        if( draw_inspector ) {
            werase( w_inspector );
            draw_border( w_inspector, BORDER_COLOR, _( "RECIPE" ), c_light_green );
            const int inspector_width = getmaxx( w_inspector );
            const int inspector_height = getmaxy( w_inspector );
            if( state.selected_recipe == nullptr ) {
                trim_and_print( w_inspector, point( 2, 1 ), std::max( 1, inspector_width - 4 ),
                                c_dark_gray, _( "Select a recipe to inspect it." ) );
            } else {
                availability *avail = selected_availability();
                const std::string reason = avail == nullptr ? _( "Nothing selected." ) :
                                           crafting_unavailable_reason( *state.selected_recipe, *avail,
                                                   *crafter, state.batch_size );
                const bool craftable = avail != nullptr &&
                                       crafting_recipe_can_start( *state.selected_recipe, *avail, *crafter );
                trim_and_print( w_inspector, point( 1, 1 ), std::max( 1, inspector_width - 2 ),
                                c_light_green, state.selected_recipe->result_name( /*decorated=*/true ) );
                trim_and_print( w_inspector, point( 1, 2 ), std::max( 1, inspector_width - 2 ),
                                craftable ? c_green : c_light_red,
                                craftable ? _( "✓ Craftable now" ) : reason );

                int batch_x = 1;
                mvwprintz( w_inspector, point( batch_x, 3 ), c_light_gray, "%s", _( "Batch: " ) );
                batch_x += utf8_width( _( "Batch: " ) );
                const bool batch_enabled = !state.selected_recipe->is_nested();
                const std::array<std::pair<std::string, std::string>, 4> batch_controls = {{
                        { "BATCH_DEC", "[ - ]" },
                        { "BATCH_EDIT", string_format( "[ %d ]", state.batch_size ) },
                        { "BATCH_INC", "[ + ]" },
                        { "BATCH_MAX", _( "[ Max ]" ) }
                    }};
                for( const auto &control : batch_controls ) {
                    const int control_width = utf8_width( control.second );
                    if( batch_x + control_width >= inspector_width - 1 ) {
                        break;
                    }
                    const nc_color color = !batch_enabled ? c_dark_gray :
                                           hovered_inspector_action == control.first ?
                                           h_light_cyan : c_light_cyan;
                    trim_and_print( w_inspector, point( batch_x, 3 ), control_width, color,
                                    control.second );
                    inspector_buttons.push_back( { control.first, control.second, batch_enabled,
                                                   _( "Choose a concrete recipe first." ),
                                                   point( batch_x, 3 ), control_width } );
                    batch_x += control_width + 1;
                }
                wattron( w_inspector, c_dark_gray );
                mvwhline( w_inspector, point( 1, 4 ), LINE_OXOX, std::max( 0, inspector_width - 2 ) );
                wattroff( w_inspector, c_dark_gray );

                if( avail != nullptr ) {
                    const std::string qry = trim( state.search_query );
                    const std::string qry_comps = qry.starts_with( "c:" ) ? qry.substr( 2 ) : "";
                    const int fold_width = std::max( 10, inspector_width - 3 );
                    const std::vector<std::string> &info = cached_recipe_info(
                                r_info_cache, *state.selected_recipe, *avail, *crafter, qry_comps,
                                state.batch_size, fold_width, avail->color( true ), crafting_group );
                    const int first_row = 5;
                    const int visible = std::max( 1, inspector_height - first_row - 1 );
                    const int max_scroll = std::max( 0, static_cast<int>( info.size() ) - visible );
                    state.inspector_scroll = std::clamp( state.inspector_scroll, 0, max_scroll );
                    for( int row = 0; row < visible; ++row ) {
                        const int index = state.inspector_scroll + row;
                        if( index >= static_cast<int>( info.size() ) ) {
                            break;
                        }
                        nc_color dummy = c_light_gray;
                        print_colored_text( w_inspector, point( 1, first_row + row ), dummy,
                                            c_light_gray, info[index] );
                    }
                    if( static_cast<int>( info.size() ) > visible ) {
                        scrollbar().offset_x( inspector_width - 1 ).offset_y( first_row )
                        .content_size( static_cast<int>( info.size() ) )
                        .viewport_pos( state.inspector_scroll ).viewport_size( visible )
                        .apply( w_inspector );
                    }
                }
            }
            wnoutrefresh( w_inspector );
        }

        werase( w_actions );
        draw_border( w_actions, BORDER_COLOR );
        availability *avail = selected_availability();
        const std::string reason = state.selected_recipe == nullptr || avail == nullptr ?
                                   _( "Select a recipe." ) :
                                   crafting_unavailable_reason( *state.selected_recipe, *avail,
                                           *crafter, state.batch_size );
        const bool craft_enabled = state.selected_recipe != nullptr && avail != nullptr &&
                                   crafting_recipe_can_start( *state.selected_recipe, *avail, *crafter );
        const bool normal_recipe = state.selected_recipe != nullptr &&
                                   !state.selected_recipe->is_nested();
        const bool favorite = state.selected_recipe != nullptr &&
                              uistate.favorite_recipes.count( state.selected_recipe->ident() );
        const bool hidden = state.selected_recipe != nullptr &&
                            uistate.hidden_recipes.count( state.selected_recipe->ident() );
        toolbar_buttons = {
            { "CONFIRM", _( "Craft" ), craft_enabled, reason },
            { "CYCLE_BATCH", _( "Batch…" ), normal_recipe, _( "Choose a concrete recipe first." ) },
            { "TOGGLE_FAVORITE", favorite ? _( "Unfavorite" ) : _( "Favorite" ),
              state.selected_recipe != nullptr, _( "Select a recipe first." ) },
            { "HIDE_SHOW_RECIPE", hidden ? _( "Unhide" ) : _( "Hide" ),
              state.selected_recipe != nullptr, _( "Select a recipe first." ) },
            { "HELP_RECIPE", _( "Examine" ), normal_recipe, _( "Choose a concrete recipe first." ) },
            { "CHOOSE_CRAFTER", _( "Crafter…" ), true, "" },
            { "RELATED_RECIPES", _( "Related" ), normal_recipe, _( "Choose a concrete recipe first." ) },
            { "COMPARE", _( "Compare" ), normal_recipe, _( "Choose a concrete recipe first." ) },
            { "QUIT", _( "Back" ), true, "" }
        };
        int button_x = 1;
        int button_y = 1;
        for( crafting_browser_button &button : toolbar_buttons ) {
            const std::string label = string_format( "[ %s ]", button.label );
            const int label_width = utf8_width( label );
            if( button_x + label_width >= browser_width - 1 ) {
                button_x = 1;
                ++button_y;
            }
            if( button_y > 2 ) {
                button.width = 0;
                continue;
            }
            button.pos = point( button_x, button_y );
            button.width = label_width;
            const nc_color color = !button.enabled ? c_dark_gray :
                                   hovered_toolbar_action == button.action ?
                                   h_light_cyan : c_light_cyan;
            trim_and_print( w_actions, button.pos, label_width, color, label );
            button_x += label_width + 1;
        }
        const std::string status = !workspace_status.empty() ? workspace_status :
                                   state.selected_recipe == nullptr ? _( "Select a recipe to begin." ) :
                                   craft_enabled ?
                                   string_format( _( "Crafter: %s | Batch: %d | Ready" ),
                                           crafter->name_and_maybe_activity(), state.batch_size ) :
                                   string_format( _( "Crafter: %s | %s" ),
                                           crafter->name_and_maybe_activity(), reason );
        trim_and_print( w_actions, point( 1, 3 ), std::max( 1, browser_width - 2 ),
                        craft_enabled && workspace_status.empty() ? c_green : c_light_gray, status );
        wnoutrefresh( w_actions );
    } );

    const auto rebuild_recipe_list = [&]() {
        const recipe *previous_recipe = state.selected_recipe;
        const int previous_index = selected_index();
        current.clear();
        available.clear();
        indent.clear();
        show_hidden = false;
        num_hidden = 0;

        static_popup progress_popup;
        std::chrono::steady_clock::time_point last_update = std::chrono::steady_clock::now();
        static constexpr std::chrono::milliseconds update_interval( 500 );
        std::function<void( size_t, size_t )> progress_callback =
        [&]( const size_t at, const size_t out_of ) {
            const std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
            if( now - last_update < update_interval || out_of == 0 ) {
                return;
            }
            last_update = now;
            progress_popup.message( _( "Searching recipes… %3.0f%%" ),
                                    100.0 * at / out_of );
            ui_manager::redraw();
            refresh_display();
            inp_mngr.pump_events();
        };

        std::vector<const recipe *> candidates;
        if( !state.search_query.empty() ) {
            const recipe_subset filtered = filter_recipes( available_recipes,
                                           trim( state.search_query ), *crafter, progress_callback );
            candidates.insert( candidates.end(), filtered.begin(), filtered.end() );
        } else {
            const std::pair<std::vector<const recipe *>, bool> result =
                recipes_from_cat( available_recipes, crafting_category_id( state.selected_category ),
                                  state.selected_subcategory );
            candidates = result.first;
            show_hidden = result.second;
        }

        if( !show_hidden ) {
            const size_t before_hidden = candidates.size();
            candidates.erase( std::remove_if( candidates.begin(), candidates.end(),
            []( const recipe * rec ) {
                return uistate.hidden_recipes.count( rec->ident() );
            } ), candidates.end() );
            num_hidden = before_hidden - candidates.size();
        }

        for( const recipe *rec : candidates ) {
            if( !availability_cache->count( rec ) ) {
                availability_cache->emplace( rec, availability( *crafter, rec, 1,
                                               camp_crafting, inventory_override ) );
            }
        }

        if( state.selected_subcategory != "CSC_*_RECENT" || !state.search_query.empty() ) {
            std::stable_sort( candidates.begin(), candidates.end(),
            [&]( const recipe * a, const recipe * b ) {
                if( highlight_unread_recipes && state.unread_first ) {
                    const bool a_read = uistate.read_recipes.count( a->ident() );
                    const bool b_read = uistate.read_recipes.count( b->ident() );
                    if( a_read != b_read ) {
                        return !a_read;
                    }
                }
                const availability &a_avail = availability_cache->at( a );
                const availability &b_avail = availability_cache->at( b );
                if( a_avail.can_craft != b_avail.can_craft ) {
                    return a_avail.can_craft;
                }
                if( a->difficulty != b->difficulty ) {
                    return a->difficulty < b->difficulty;
                }
                if( a->result_name() != b->result_name() ) {
                    return localized_compare( a->result_name(), b->result_name() );
                }
                return a->time_to_craft( *crafter ) < b->time_to_craft( *crafter );
            } );
        }

        indent.assign( candidates.size(), 0 );
        expand_recipes( candidates, indent, *availability_cache, *crafter, state.unread_first,
                        highlight_unread_recipes, available_recipes, uistate.hidden_recipes,
                        camp_crafting, inventory_override );
        const std::vector<int> candidate_indent = indent;
        indent.clear();

        for( int i = 0; i < static_cast<int>( candidates.size() ); ++i ) {
            const recipe *rec = candidates[i];
            if( !availability_cache->count( rec ) ) {
                availability_cache->emplace( rec, availability( *crafter, rec, 1,
                                               camp_crafting, inventory_override ) );
            }
            const availability &rec_avail = availability_cache->at( rec );
            if( state.craftable_only &&
                !( rec_avail.can_craft && rec_avail.crafter_has_primary_skill ) ) {
                continue;
            }
            if( state.memorized_only && !crafter->knows_recipe( rec ) ) {
                continue;
            }
            if( state.unread_only && uistate.read_recipes.count( rec->ident() ) ) {
                continue;
            }
            current.push_back( rec );
            indent.push_back( i < static_cast<int>( candidate_indent.size() ) ?
                              candidate_indent[i] : 0 );
        }

        available.reserve( current.size() );
        for( const recipe *rec : current ) {
            available.push_back( availability_cache->at( rec ) );
        }

        const auto preserved = std::find( current.begin(), current.end(), previous_recipe );
        if( preserved != current.end() ) {
            state.selected_recipe = *preserved;
        } else if( !current.empty() ) {
            const int replacement = std::clamp( previous_index < 0 ? 0 : previous_index, 0,
                                                static_cast<int>( current.size() ) - 1 );
            state.selected_recipe = current[replacement];
            state.inspector_scroll = 0;
        } else {
            state.selected_recipe = nullptr;
            state.inspector_scroll = 0;
        }
        invalidate_selected_details();

        const int index = selected_index();
        const int visible = w_recipes ? std::max( 1, getmaxy( w_recipes ) - 3 ) :
                            std::max( 1, body_height - 3 );
        if( index >= 0 ) {
            if( index < state.recipe_scroll ) {
                state.recipe_scroll = index;
            } else if( index >= state.recipe_scroll + visible ) {
                state.recipe_scroll = index - visible + 1;
            }
        } else {
            state.recipe_scroll = 0;
        }
    };

    const auto update_unread_maps = [&]() {
        if( !highlight_unread_recipes ) {
            return;
        }
        for( const std::string &category : crafting_categories ) {
            is_cat_unread[category] = false;
            for( const std::string &subcategory :
                 crafting_category_id( category )->subcategories ) {
                is_subcat_unread[category][subcategory] = false;
                const auto result = recipes_from_cat( available_recipes,
                                    crafting_category_id( category ), subcategory );
                for( const recipe *rec : result.first ) {
                    if( !result.second && uistate.hidden_recipes.count( rec->ident() ) ) {
                        continue;
                    }
                    if( !uistate.read_recipes.count( rec->ident() ) ) {
                        is_cat_unread[category] = true;
                        is_subcat_unread[category][subcategory] = true;
                        break;
                    }
                }
            }
        }
    };

    const auto local_mouse = [&]( const catacurses::window & win ) -> std::optional<point> {
        const std::optional<point> pos = ctxt.get_coordinates_text( win );
        if( !pos || pos->x < 0 || pos->y < 0 || pos->x >= getmaxx( win ) ||
            pos->y >= getmaxy( win ) ) {
            return std::nullopt;
        }
        return pos;
    };

    const auto set_batch_size = [&]( const int new_size ) {
        const int clamped = std::clamp( new_size, 1, 50 );
        if( clamped != state.batch_size ) {
            state.batch_size = clamped;
            invalidate_selected_details();
            workspace_status = string_format( _( "Batch size set to %d." ), state.batch_size );
        }
    };

    const auto choose_batch_size = [&]() {
        int amount = state.batch_size;
        string_input_popup popup;
        popup.title( _( "Batch size (1–50)" ) ).width( 8 ).only_digits( true ).edit( amount );
        set_batch_size( amount );
    };

    do {
        if( recalc_unread ) {
            update_unread_maps();
            recalc_unread = false;
        }
        if( recalc ) {
            recalc = false;
            rebuild_recipe_list();
        }

        ui_manager::redraw();
        std::string action = ctxt.handle_input();
        const std::optional<point> header_pos = local_mouse( w_header );
        const std::optional<point> sidebar_pos = local_mouse( w_sidebar );
        const std::optional<point> recipes_pos = local_mouse( w_recipes );
        const std::optional<point> inspector_pos = local_mouse( w_inspector );
        const std::optional<point> actions_pos = local_mouse( w_actions );

        if( state.context_open ) {
            if( action == "QUIT" || action == "SEC_SELECT" ) {
                state.context_open = false;
                hovered_context_button = -1;
                continue;
            }
            if( action == "MOUSE_MOVE" ) {
                hovered_context_button = -1;
                if( recipes_pos ) {
                    for( int i = 0; i < static_cast<int>( context_buttons.size() ); ++i ) {
                        const crafting_browser_button &button = context_buttons[i];
                        if( recipes_pos->y == button.pos.y &&
                            recipes_pos->x >= button.pos.x &&
                            recipes_pos->x < button.pos.x + button.width ) {
                            hovered_context_button = i;
                            break;
                        }
                    }
                }
                continue;
            }
            if( action == "SELECT" ) {
                int hit = -1;
                if( recipes_pos ) {
                    for( int i = 0; i < static_cast<int>( context_buttons.size() ); ++i ) {
                        const crafting_browser_button &button = context_buttons[i];
                        if( recipes_pos->y == button.pos.y &&
                            recipes_pos->x >= button.pos.x &&
                            recipes_pos->x < button.pos.x + button.width ) {
                            hit = i;
                            break;
                        }
                    }
                }
                if( hit >= 0 ) {
                    const crafting_browser_button button = context_buttons[hit];
                    state.context_open = false;
                    hovered_context_button = -1;
                    if( button.enabled ) {
                        action = button.action;
                    } else {
                        workspace_status = button.disabled_reason;
                        continue;
                    }
                } else {
                    state.context_open = false;
                    hovered_context_button = -1;
                    continue;
                }
            } else if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
                continue;
            }
        }

        if( action == "MOUSE_MOVE" ) {
            hovered_sidebar_entry = -1;
            state.hovered_recipe = nullptr;
            hovered_inspector_action.clear();
            hovered_toolbar_action.clear();
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::categories ) && sidebar_pos ) {
                for( const auto &hit : sidebar_hits ) {
                    if( hit.first.contains( *sidebar_pos ) ) {
                        hovered_sidebar_entry = hit.second;
                        break;
                    }
                }
            }
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                for( const auto &hit : recipe_hits ) {
                    if( hit.first.contains( *recipes_pos ) ) {
                        state.hovered_recipe = current[hit.second];
                        break;
                    }
                }
            }
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::inspector ) && inspector_pos ) {
                for( const crafting_browser_button &button : inspector_buttons ) {
                    if( inspector_pos->y == button.pos.y &&
                        inspector_pos->x >= button.pos.x &&
                        inspector_pos->x < button.pos.x + button.width ) {
                        hovered_inspector_action = button.action;
                        break;
                    }
                }
            }
            if( actions_pos ) {
                for( const crafting_browser_button &button : toolbar_buttons ) {
                    if( button.width > 0 && actions_pos->y == button.pos.y &&
                        actions_pos->x >= button.pos.x &&
                        actions_pos->x < button.pos.x + button.width ) {
                        hovered_toolbar_action = button.action;
                        break;
                    }
                }
            }
            continue;
        }

        if( action == "SELECT" ) {
            bool handled = false;
            if( compact_layout && header_pos ) {
                for( const auto &hit : pane_hits ) {
                    if( hit.first.contains( *header_pos ) ) {
                        state.focused_pane = hit.second;
                        handled = true;
                        break;
                    }
                }
            }
            if( !handled && header_pos && search_clear_hit.contains( *header_pos ) ) {
                action = "RESET_FILTER";
                handled = true;
            } else if( !handled && header_pos && search_hit.contains( *header_pos ) ) {
                action = "FILTER";
                handled = true;
            }
            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::categories ) && sidebar_pos ) {
                for( const auto &hit : sidebar_hits ) {
                    if( !hit.first.contains( *sidebar_pos ) ) {
                        continue;
                    }
                    const crafting_sidebar_entry &entry = sidebar_entries[hit.second];
                    if( entry.type == crafting_sidebar_entry_type::filter ) {
                        if( entry.category == "FILTER_CRAFTABLE" ) {
                            state.craftable_only = !state.craftable_only;
                        } else if( entry.category == "FILTER_MEMORIZED" ) {
                            state.memorized_only = !state.memorized_only;
                        } else if( entry.category == "FILTER_UNREAD" && highlight_unread_recipes ) {
                            state.unread_only = !state.unread_only;
                        }
                    } else {
                        state.selected_category = entry.category;
                        state.selected_subcategory = entry.subcategory;
                        if( compact_layout ) {
                            state.focused_pane = crafting_browser_pane::recipes;
                        }
                    }
                    recalc = true;
                    handled = true;
                    break;
                }
            }
            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::inspector ) && inspector_pos ) {
                for( const crafting_browser_button &button : inspector_buttons ) {
                    if( inspector_pos->y == button.pos.y &&
                        inspector_pos->x >= button.pos.x &&
                        inspector_pos->x < button.pos.x + button.width ) {
                        if( button.enabled ) {
                            action = button.action;
                        } else {
                            workspace_status = button.disabled_reason;
                        }
                        handled = true;
                        break;
                    }
                }
            }
            if( !handled && actions_pos ) {
                for( const crafting_browser_button &button : toolbar_buttons ) {
                    if( button.width > 0 && actions_pos->y == button.pos.y &&
                        actions_pos->x >= button.pos.x &&
                        actions_pos->x < button.pos.x + button.width ) {
                        if( button.enabled ) {
                            action = button.action;
                        } else {
                            workspace_status = button.disabled_reason;
                        }
                        handled = true;
                        break;
                    }
                }
            }
            if( !handled && ( !compact_layout ||
                             state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                for( const auto &hit : recipe_hits ) {
                    if( !hit.first.contains( *recipes_pos ) ) {
                        continue;
                    }
                    const recipe *clicked = current[hit.second];
                    const auto now = std::chrono::steady_clock::now();
                    const bool double_click = state.last_clicked_recipe == clicked &&
                                              state.last_click_time &&
                                              now - *state.last_click_time <=
                                              std::chrono::milliseconds( 500 );
                    select_index( hit.second, true );
                    if( double_click ) {
                        state.last_clicked_recipe = nullptr;
                        state.last_click_time.reset();
                        action = "CONFIRM";
                    } else {
                        state.last_clicked_recipe = clicked;
                        state.last_click_time = now;
                    }
                    handled = true;
                    break;
                }
            }
            if( handled && action == "SELECT" ) {
                continue;
            }
        } else if( action == "SEC_SELECT" ) {
            if( ( !compact_layout ||
                  state.focused_pane == crafting_browser_pane::recipes ) && recipes_pos ) {
                for( const auto &hit : recipe_hits ) {
                    if( hit.first.contains( *recipes_pos ) ) {
                        select_index( hit.second, false );
                        state.context_open = true;
                        state.context_pos = *recipes_pos;
                        hovered_context_button = -1;
                        break;
                    }
                }
            }
            continue;
        }

        if( action == "SCROLL_UP" || action == "SCROLL_DOWN" ) {
            const int direction = action == "SCROLL_UP" ? -1 : 1;
            if( compact_layout ) {
                if( state.focused_pane == crafting_browser_pane::categories ) {
                    state.category_scroll = std::max( 0, state.category_scroll + direction );
                } else if( state.focused_pane == crafting_browser_pane::recipes ) {
                    state.recipe_scroll = std::max( 0, state.recipe_scroll + direction * 3 );
                } else {
                    state.inspector_scroll = std::max( 0, state.inspector_scroll + direction * 3 );
                }
            } else if( sidebar_pos ) {
                state.category_scroll = std::max( 0, state.category_scroll + direction );
            } else if( recipes_pos ) {
                state.recipe_scroll = std::max( 0, state.recipe_scroll + direction * 3 );
            } else if( inspector_pos ) {
                state.inspector_scroll = std::max( 0, state.inspector_scroll + direction * 3 );
            }
            continue;
        }

        const int index = selected_index();
        const int visible_recipes = std::max( 1, getmaxy( w_recipes ) - 3 );
        if( action == "DOWN" && !current.empty() ) {
            select_index( ( index < 0 ? 0 : index + 1 ) % current.size(), true );
        } else if( action == "UP" && !current.empty() ) {
            select_index( index <= 0 ? static_cast<int>( current.size() ) - 1 : index - 1, true );
        } else if( action == "PAGE_DOWN" && !current.empty() ) {
            select_index( std::min( static_cast<int>( current.size() ) - 1,
                                    std::max( 0, index ) + visible_recipes ), true );
        } else if( action == "PAGE_UP" && !current.empty() ) {
            select_index( std::max( 0, std::max( 0, index ) - visible_recipes ), true );
        } else if( action == "HOME" && !current.empty() ) {
            select_index( 0, true );
        } else if( action == "END" && !current.empty() ) {
            select_index( static_cast<int>( current.size() ) - 1, true );
        } else if( action == "SCROLL_RECIPE_INFO_UP" || action == "SCROLL_ITEM_INFO_UP" ) {
            state.inspector_scroll = std::max( 0, state.inspector_scroll -
                                              std::max( 1, getmaxy( w_inspector ) - 7 ) );
        } else if( action == "SCROLL_RECIPE_INFO_DOWN" || action == "SCROLL_ITEM_INFO_DOWN" ) {
            state.inspector_scroll += std::max( 1, getmaxy( w_inspector ) - 7 );
        } else if( action == "PREV_TAB" || action == "NEXT_TAB" ) {
            const auto found = std::find( crafting_categories.begin(), crafting_categories.end(),
                                          state.selected_category );
            int category_index = found == crafting_categories.end() ? 0 :
                                 static_cast<int>( found - crafting_categories.begin() );
            const int direction = action == "PREV_TAB" ? -1 : 1;
            category_index = ( category_index + direction +
                               static_cast<int>( crafting_categories.size() ) ) %
                             static_cast<int>( crafting_categories.size() );
            state.selected_category = crafting_categories[category_index];
            state.selected_subcategory = first_subcategory( state.selected_category );
            recalc = true;
        } else if( action == "LEFT" || action == "RIGHT" ) {
            const std::vector<std::string> *subcategories =
                subcategories_for_category( state.selected_category );
            if( subcategories != nullptr && !subcategories->empty() ) {
                const auto found = std::find( subcategories->begin(), subcategories->end(),
                                              state.selected_subcategory );
                int subcategory_index = found == subcategories->end() ? 0 :
                                        static_cast<int>( found - subcategories->begin() );
                const int direction = action == "LEFT" ? -1 : 1;
                subcategory_index = ( subcategory_index + direction +
                                      static_cast<int>( subcategories->size() ) ) %
                                    static_cast<int>( subcategories->size() );
                state.selected_subcategory = ( *subcategories )[subcategory_index];
                recalc = true;
            }
        } else if( action == "FILTER" ) {
            std::string edited = state.search_query;
            string_input_popup popup;
            popup.window( w_header, search_edit_start, search_edit_end )
            .identifier( "craft_recipe_filter" )
            .hist_use_uilist( false )
            .edit( edited );
            if( edited != state.search_query ) {
                state.search_query = edited;
                recalc = true;
                recalc_unread = highlight_unread_recipes;
            }
        } else if( action == "RESET_FILTER" ) {
            if( !state.search_query.empty() ) {
                state.search_query.clear();
                recalc = true;
                recalc_unread = highlight_unread_recipes;
            }
        } else if( action == "BATCH_DEC" ) {
            set_batch_size( state.batch_size - 1 );
        } else if( action == "BATCH_INC" ) {
            set_batch_size( state.batch_size + 1 );
        } else if( action == "BATCH_EDIT" || action == "CYCLE_BATCH" ) {
            if( state.selected_recipe != nullptr && !state.selected_recipe->is_nested() ) {
                choose_batch_size();
            }
        } else if( action == "BATCH_MAX" ) {
            if( state.selected_recipe != nullptr && !state.selected_recipe->is_nested() ) {
                int maximum = 0;
                for( int amount = 1; amount <= 50; ++amount ) {
                    availability candidate( *crafter, state.selected_recipe, amount,
                                            camp_crafting, inventory_override );
                    if( crafting_recipe_can_start( *state.selected_recipe, candidate, *crafter ) ) {
                        maximum = amount;
                    }
                }
                if( maximum > 0 ) {
                    set_batch_size( maximum );
                } else {
                    workspace_status = _( "No craftable batch is currently available." );
                }
            }
        } else if( action == "CONFIRM" ) {
            availability *avail = selected_availability();
            if( state.selected_recipe == nullptr || avail == nullptr ) {
                workspace_status = _( "Nothing selected." );
            } else if( state.selected_recipe->is_nested() ) {
                bool keep_line = false;
                nested_toggle( state.selected_recipe->ident(), recalc, keep_line );
            } else if( !crafting_recipe_can_start( *state.selected_recipe, *avail, *crafter ) ) {
                workspace_status = crafting_unavailable_reason( *state.selected_recipe, *avail,
                                   *crafter, state.batch_size );
            } else if( avail->inv_override == nullptr &&
                       !crafter->check_eligible_containers_for_crafting( *state.selected_recipe,
                               state.batch_size ) ) {
                // The native check owns its explanatory popup.
            } else {
                chosen = state.selected_recipe;
                batch_size_out = state.batch_size;
                uistate.read_recipes.insert( chosen->ident() );
                done = true;
            }
        } else if( action == "HELP_RECIPE" && state.selected_recipe != nullptr &&
                   !state.selected_recipe->is_nested() ) {
            uistate.read_recipes.insert( state.selected_recipe->ident() );
            recalc_unread = highlight_unread_recipes;
            item_info_data data = result_info->get_result_data( state.selected_recipe,
                                  state.batch_size, state.item_popup_scroll, w_inspector );
            data.handle_scrolling = true;
            data.arrow_scrolling = true;
            const int info_width = std::min( TERMX, FULL_SCREEN_WIDTH );
            const int info_height = std::min( TERMY, FULL_SCREEN_HEIGHT );
            iteminfo_window info_window( data,
                                         point( ( TERMX - info_width ) / 2,
                                                ( TERMY - info_height ) / 2 ),
                                         info_width, info_height );
            info_window.execute();
        } else if( action == "CHOOSE_CRAFTER" ) {
            const bool rec_valid = state.selected_recipe != nullptr;
            const int new_crafter_i = choose_crafter( crafting_group, crafter_i,
                                      state.selected_recipe, rec_valid );
            if( new_crafter_i >= 0 && new_crafter_i != crafter_i ) {
                crafter_i = new_crafter_i;
                crafter = crafting_group[crafter_i];
                availability_cache = &guy_availability_cache[crafter->getID()];
                result_info = std::make_unique<recipe_result_info_cache>( *crafter );
                invalidate_selected_details();
                recalc = true;
                workspace_status = string_format( _( "Crafter changed to %s." ),
                                                  crafter->name_and_maybe_activity() );
            }
        } else if( action == "TOGGLE_FAVORITE" && state.selected_recipe != nullptr ) {
            const recipe_id id = state.selected_recipe->ident();
            if( uistate.favorite_recipes.erase( id ) == 0 ) {
                uistate.favorite_recipes.insert( id );
                uistate.read_recipes.insert( id );
            }
            if( state.selected_subcategory == "CSC_*_FAVORITE" && state.search_query.empty() ) {
                recalc = true;
            }
            recalc_unread = highlight_unread_recipes;
        } else if( action == "HIDE_SHOW_RECIPE" && state.selected_recipe != nullptr ) {
            const recipe_id id = state.selected_recipe->ident();
            if( uistate.hidden_recipes.erase( id ) == 0 ) {
                uistate.hidden_recipes.insert( id );
                uistate.read_recipes.insert( id );
            }
            recalc = true;
            recalc_unread = highlight_unread_recipes;
        } else if( action == "TOGGLE_RECIPE_UNREAD" && state.selected_recipe != nullptr &&
                   highlight_unread_recipes ) {
            const recipe_id id = state.selected_recipe->ident();
            if( uistate.read_recipes.erase( id ) == 0 ) {
                uistate.read_recipes.insert( id );
            }
            recalc_unread = true;
            if( state.unread_only ) {
                recalc = true;
            }
        } else if( action == "MARK_ALL_RECIPES_READ" && highlight_unread_recipes ) {
            if( query_yn( _( "Mark every recipe in the current browser view as read?" ) ) ) {
                for( const recipe *rec : current ) {
                    uistate.read_recipes.insert( rec->ident() );
                }
                recalc_unread = true;
                if( state.unread_only ) {
                    recalc = true;
                }
            }
        } else if( action == "TOGGLE_UNREAD_RECIPES_FIRST" &&
                   highlight_unread_recipes ) {
            state.unread_first = !state.unread_first;
            recalc = true;
        } else if( action == "RELATED_RECIPES" && state.selected_recipe != nullptr &&
                   !state.selected_recipe->is_nested() ) {
            uistate.read_recipes.insert( state.selected_recipe->ident() );
            const std::string related = peek_related_recipe( state.selected_recipe,
                                        available_recipes, *crafter );
            if( !related.empty() ) {
                state.search_query = related;
                recalc = true;
                recalc_unread = highlight_unread_recipes;
            }
        } else if( action == "COMPARE" && state.selected_recipe != nullptr &&
                   !state.selected_recipe->is_nested() ) {
            const item recipe_result = get_recipe_result_item( *state.selected_recipe, *crafter );
            compare_recipe_with_item( recipe_result, *crafter );
        } else if( action == "HELP_KEYBINDINGS" ) {
            workspace_status = enumerate_as_string( std::vector<std::string> {
                ctxt.get_desc( "CONFIRM", _( "Craft" ) ),
                ctxt.get_desc( "FILTER", _( "Search" ) ),
                ctxt.get_desc( "CYCLE_BATCH", _( "Batch" ) ),
                ctxt.get_desc( "TOGGLE_FAVORITE", _( "Favorite" ) ),
                ctxt.get_desc( "HELP_RECIPE", _( "Examine" ) )
            }, enumeration_conjunction::none );
        } else if( action == "QUIT" ) {
            chosen = nullptr;
            done = true;
        }

        const int new_index = selected_index();
        if( new_index >= 0 ) {
            if( new_index < state.recipe_scroll ) {
                state.recipe_scroll = new_index;
            } else if( new_index >= state.recipe_scroll + visible_recipes ) {
                state.recipe_scroll = new_index - visible_recipes + 1;
            }
        }
    } while( !done );

    persist_state();
    return { crafter, chosen };
}

std::pair<Character *, const recipe *> select_crafter_and_crafting_recipe( int &batch_size_out,
        const recipe_id &goto_recipe, Character *crafter, std::string filterstring, bool camp_crafting,
        inventory *inventory_override )
{
    if( TERMX < 72 || TERMY < 20 ) {
        return select_crafter_and_crafting_recipe_legacy( batch_size_out, goto_recipe, crafter,
                std::move( filterstring ), camp_crafting, inventory_override );
    }
    return select_crafter_and_crafting_recipe_browser( batch_size_out, goto_recipe, crafter,
            std::move( filterstring ), camp_crafting, inventory_override );
}

static std::pair<Character *, const recipe *> select_crafter_and_crafting_recipe_legacy(
    int &batch_size_out, const recipe_id &goto_recipe, Character *crafter,
    std::string filterstring, bool camp_crafting, inventory *inventory_override )
{
    if( crafter == nullptr ) {
        return {nullptr, nullptr};
    }
    recipe_result_info_cache result_info( *crafter );
    recipe_info_cache r_info_cache;
    int line_recipe_info = 0;
    int line_item_info = 0;
    int line_item_info_popup = 0;
    const int headHeight = 3;
    const int subHeadHeight = 2;

    bool isWide = false;
    int width = 0;
    int dataLines = 0;
    int dataHalfLines = 0;
    int dataHeight = 0;
    int item_info_width = 0;
    const bool highlight_unread_recipes = get_option<bool>( "HIGHLIGHT_UNREAD_RECIPES" );

    input_context ctxt = make_crafting_context( highlight_unread_recipes );

    catacurses::window w_head_tabs; //For the recipe category tabs on the left
    catacurses::window w_head_info; //For the new/hidden/status information on the right
    catacurses::window w_subhead;
    catacurses::window w_data;
    catacurses::window w_iteminfo;
    inclusive_rectangle<point> mouseover_area_list;
    inclusive_rectangle<point> mouseover_area_recipe;
    std::vector<std::string> keybinding_tips;
    int keybinding_x = 0;
    ui_adaptor ui;
    ui.on_screen_resize( [&]( ui_adaptor & ui ) {
        const int freeWidth = TERMX - FULL_SCREEN_WIDTH;
        isWide = ( TERMX > FULL_SCREEN_WIDTH && freeWidth > 15 );

        width = isWide ? ( freeWidth > FULL_SCREEN_WIDTH ? FULL_SCREEN_WIDTH * 2 : TERMX ) :
                FULL_SCREEN_WIDTH;
        const unsigned int header_info_width = std::max( width / 4, width - FULL_SCREEN_WIDTH - 1 );
        const int wStart = ( TERMX - width ) / 2;

        std::vector<std::string> act_descs;
        const auto add_action_desc = [&]( const std::string & act, const std::string & txt ) {
            act_descs.emplace_back(
                ctxt.get_desc( act, txt, input_context::allow_all_keys ) );
        };
        add_action_desc( "CONFIRM", pgettext( "crafting gui", "Craft" ) );
        add_action_desc( "HELP_RECIPE", pgettext( "crafting gui", "Describe" ) );
        add_action_desc( "FILTER", pgettext( "crafting gui", "Filter" ) );
        add_action_desc( "RESET_FILTER", pgettext( "crafting gui", "Reset filter" ) );
        if( highlight_unread_recipes ) {
            add_action_desc( "TOGGLE_RECIPE_UNREAD", pgettext( "crafting gui", "Read/unread" ) );
            add_action_desc( "MARK_ALL_RECIPES_READ", pgettext( "crafting gui", "Mark all as read" ) );
            add_action_desc( "TOGGLE_UNREAD_RECIPES_FIRST",
                             pgettext( "crafting gui", "Show unread recipes first" ) );
        }
        add_action_desc( "HIDE_SHOW_RECIPE", pgettext( "crafting gui", "Show/hide" ) );
        add_action_desc( "RELATED_RECIPES", pgettext( "crafting gui", "Related" ) );
        add_action_desc( "TOGGLE_FAVORITE", pgettext( "crafting gui", "Favorite" ) );
        add_action_desc( "CYCLE_BATCH", pgettext( "crafting gui", "Batch" ) );
        add_action_desc( "CHOOSE_CRAFTER", pgettext( "crafting gui", "Choose crafter" ) );
        add_action_desc( "HELP_KEYBINDINGS", pgettext( "crafting gui", "Keybindings" ) );
        keybinding_x = isWide ? 5 : 2;
        keybinding_tips = foldstring( enumerate_as_string( act_descs, enumeration_conjunction::none ),
                                      width - keybinding_x * 2 );

        const int tailHeight = keybinding_tips.size() + 2;
        dataLines = TERMY - ( headHeight + subHeadHeight ) - tailHeight;
        dataHalfLines = dataLines / 2;
        dataHeight = TERMY - ( headHeight + subHeadHeight );

        w_head_tabs = catacurses::newwin( headHeight, ( width - header_info_width ), point( wStart, 0 ) );
        w_head_info = catacurses::newwin( headHeight, header_info_width,
                                          point( wStart + ( width - header_info_width ), 0 ) );
        w_subhead = catacurses::newwin( subHeadHeight, width, point( wStart, 3 ) );
        w_data = catacurses::newwin( dataHeight, width, point( wStart,
                                     headHeight + subHeadHeight ) );

        if( isWide ) {
            item_info_width = width - FULL_SCREEN_WIDTH - 1;
            const int item_info_height = dataHeight - tailHeight;
            const point item_info( wStart + width - item_info_width, headHeight + subHeadHeight );

            w_iteminfo = catacurses::newwin( item_info_height, item_info_width,
                                             item_info );
        } else {
            item_info_width = 0;
            w_iteminfo = {};
        }

        ui.position( point( wStart, 0 ), point( width, TERMY ) );
    } );
    ui.mark_resize();

    bool is_filtered_unread = false;
    std::map<std::string, bool> is_cat_unread;
    std::map<std::string, std::map<std::string, bool>> is_subcat_unread;
    std::vector<std::string> crafting_categories;
    crafting_categories.reserve( craft_cat_list.size() );
    for( const crafting_category &cat : craft_cat_list.get_all() ) {
        if( cat.is_hidden ) {
            continue;
        }
        crafting_categories.emplace_back( cat.id.str() );
    }
    tab_list tab( crafting_categories );
    tab_list subtab( crafting_category_id( tab.cur() )->subcategories );
    std::map<size_t, inclusive_rectangle<point>> translated_tab_map;
    std::map<size_t, inclusive_rectangle<point>> translated_subtab_map;
    std::map<size_t, inclusive_rectangle<point>> list_map;
    // List of all recipes to show, to choose from
    std::vector<const recipe *> current;
    // how much to indent any item
    std::vector<int> indent;
    std::vector<availability> available;
    int line = 0;
    bool unread_recipes_first = false;
    bool user_moved_line = false;
    bool recalc = true;
    bool recalc_unread = highlight_unread_recipes;
    bool keepline = false;
    bool done = false;
    bool batch = false;
    bool show_hidden = false;
    size_t num_hidden = 0;
    int num_recipe = 0;
    int batch_line = 0;
    const recipe *chosen = nullptr;
    int last_line = -1;
    bool just_toggled_unread = false;

    const std::vector<Character *> crafting_group = crafter->get_crafting_group();
    int crafter_i = find( crafting_group.begin(), crafting_group.end(),
                          crafter ) - crafting_group.begin();

    // Get everyone's recipes
    const recipe_subset &available_recipes = crafter->get_group_available_recipes( inventory_override );
    std::map<character_id, std::map<const recipe *, availability>> guy_availability_cache;
    // next line also inserts empty cache for crafter->getID()
    std::map<const recipe *, availability> *availability_cache =
        &guy_availability_cache[crafter->getID()];

    const std::string new_recipe_str = pgettext( "crafting gui", "NEW!" );
    const nc_color new_recipe_str_col = c_light_green;
    const int new_recipe_str_width = utf8_width( new_recipe_str );

    if( goto_recipe.is_valid() ) {
        const std::vector<const recipe *> &gotocat = available_recipes.in_category( goto_recipe->category );
        if( !gotocat.empty() ) {
            const auto gotorec = std::find_if( gotocat.begin(),
            gotocat.end(), [&goto_recipe]( const recipe * r ) {
                return r && r->ident() == goto_recipe;
            } );
            if( gotorec != gotocat.end() && ( *gotorec )->category.is_valid() ) {
                while( tab.cur() != goto_recipe->category.str() ) {
                    tab.next();
                }
                subtab = tab_list( crafting_category_id( tab.cur() )->subcategories );
                chosen = *gotorec;
                show_hidden = true;
                keepline = true;
                current = gotocat;
                line = gotorec - gotocat.begin();
            }
        }
    }

    ui.on_redraw( [&]( ui_adaptor & ui ) {
        if( highlight_unread_recipes && recalc_unread ) {
            if( filterstring.empty() ) {
                for( const std::string &cat : crafting_categories ) {
                    is_cat_unread[cat] = false;
                    for( const std::string &subcat : crafting_category_id( cat )->subcategories ) {
                        is_subcat_unread[cat][subcat] = false;
                        const std::pair<std::vector<const recipe *>, bool> result = recipes_from_cat( available_recipes,
                                crafting_category_id( cat ), subcat );
                        const std::vector<const recipe *> &recipes = result.first;
                        const bool include_hidden = result.second;
                        for( const recipe *const rcp : recipes ) {
                            const recipe_id &rcp_id = rcp->ident();
                            if( !include_hidden && uistate.hidden_recipes.count( rcp_id ) ) {
                                continue;
                            }
                            if( uistate.read_recipes.count( rcp_id ) ) {
                                continue;
                            }
                            is_cat_unread[cat] = true;
                            is_subcat_unread[cat][subcat] = true;
                            break;
                        }
                    }
                }
            } else {
                is_filtered_unread = false;
                for( const recipe *const rcp : current ) {
                    const recipe_id &rcp_id = rcp->ident();
                    if( uistate.hidden_recipes.count( rcp_id ) ) {
                        continue;
                    }
                    if( uistate.read_recipes.count( rcp_id ) ) {
                        continue;
                    }
                    is_filtered_unread = true;
                    break;
                }
            }
            recalc_unread = false;
        }

        const TAB_MODE m = batch ? BATCH : filterstring.empty() ? NORMAL : FILTERED;
        translated_tab_map = draw_recipe_tabs( w_head_tabs, tab, m, is_filtered_unread, is_cat_unread );
        translated_subtab_map = draw_recipe_subtabs( w_subhead, tab.cur(), subtab.cur_index(),
                                available_recipes, m,
                                is_subcat_unread[tab.cur()] );

        //Clear the crafting info panel, since that can change on a per-recipe basis
        werase( w_head_info );

        if( !show_hidden ) {
            draw_hidden_amount( w_head_info, num_hidden, num_recipe );
        }

        // Clear the screen of recipe data, and draw it anew
        werase( w_data );

        for( size_t i = 0; i < keybinding_tips.size(); ++i ) {
            nc_color dummy = c_white;
            print_colored_text( w_data, point( keybinding_x, dataLines + 1 + i ),
                                dummy, c_white, keybinding_tips[i] );
        }

        // Draw borders
        wattron( w_data, BORDER_COLOR );
        mvwhline( w_data, point( 1, dataHeight - 1 ), LINE_OXOX, width - 2 );
        mvwvline( w_data, point::zero, LINE_XOXO, dataHeight - 1 );
        mvwvline( w_data, point( width - 1, 0 ), LINE_XOXO, dataHeight - 1 );
        mvwaddch( w_data, point( 0, dataHeight - 1 ), LINE_XXOO ); // |_
        mvwaddch( w_data, point( width - 1, dataHeight - 1 ), LINE_XOOX ); // _|
        wattroff( w_data, BORDER_COLOR );

        const int max_recipe_name_width = 27;
        const int recmax = current.size();
        // pair<int, int>
        const auto& [istart, iend] = subindex_around_cursor( recmax, dataLines, line );
        list_map.clear();
        for( int i = istart; i < iend; ++i ) {
            if( i >= static_cast<int>( indent.size() ) || indent[i] < 0 ) {
                indent.assign( current.size(), 0 );
                debugmsg( _( "Indent for line %i not set correctly.  Indents reset to 0." ), i );
            }
            std::string tmp_name = std::string( indent[i],
                                                ' ' ) + current[i]->result_name( /*decorated=*/true );
            if( batch ) {
                tmp_name = string_format( _( "%2dx %s" ), i + 1, tmp_name );
            }
            const bool rcp_read = !highlight_unread_recipes ||
                                  uistate.read_recipes.count( current[i]->ident() );
            const bool highlight = i == line;
            nc_color col = highlight ? available[i].selected_color() : available[i].color();
            const point print_from( 2, i - istart );
            if( highlight ) {
                ui.set_cursor( w_data, print_from );
            }
            int rcp_name_trim_width = max_recipe_name_width;
            if( !rcp_read ) {
                const point offset( max_recipe_name_width - new_recipe_str_width, 0 );
                mvwprintz( w_data, print_from + offset, new_recipe_str_col, "%s", new_recipe_str );
                rcp_name_trim_width -= new_recipe_str_width + 1;
            }
            mvwprintz( w_data, print_from, col, "%s", trim_by_length( tmp_name, rcp_name_trim_width ) );
            list_map.emplace( i, inclusive_rectangle<point>( print_from, point( 2 + max_recipe_name_width,
                              i - istart ) ) );
        }

        const int batch_size = batch ? line + 1 : 1;
        if( !current.empty() ) {
            const recipe &recp = *current[line];

            draw_can_craft_indicator( w_head_info, recp, *crafter );

            const availability &avail = available[line];
            // border + padding + name + padding
            const int xpos = 1 + 1 + max_recipe_name_width + 3;
            const int fold_width = FULL_SCREEN_WIDTH - xpos - 2;
            const int w_left = getbegx( w_data );
            mouseover_area_list = inclusive_rectangle<point>( point( 1 + w_left, headHeight + subHeadHeight ),
                                  point( w_left + xpos - 1, headHeight + subHeadHeight + dataLines ) );
            mouseover_area_recipe = inclusive_rectangle<point>( point( xpos + w_left,
                                    headHeight + subHeadHeight ), point( xpos + w_left + fold_width + 1,
                                            headHeight + subHeadHeight + dataLines ) );
            const nc_color color = avail.color( true );
            const std::string qry = trim( filterstring );
            std::string qry_comps;
            if( qry.compare( 0, 2, "c:" ) == 0 ) {
                qry_comps = qry.substr( 2 );
            }

            const std::vector<std::string> &info = cached_recipe_info( r_info_cache,
                                                   recp, avail, *crafter, qry_comps, batch_size, fold_width, color, crafting_group );

            const int total_lines = info.size();
            line_recipe_info = clamp( line_recipe_info, 0, total_lines - dataLines );
            for( int i = line_recipe_info; i < std::min( line_recipe_info + dataLines, total_lines ); ++i ) {
                nc_color dummy = color;
                print_colored_text( w_data, point( xpos, i - line_recipe_info ), dummy, color, info[i] );
            }

            if( total_lines > dataLines ) {
                scrollbar()
                .offset_x( xpos + fold_width + 1 )
                .content_size( total_lines )
                .viewport_pos( line_recipe_info )
                .viewport_size( dataLines )
                .apply( w_data );
            }
        }

        scrollbar()
        .offset_x( 0 )
        .offset_y( 0 )
        .content_size( recmax )
        .viewport_pos( istart )
        .viewport_size( dataLines )
        .apply( w_data );

        wnoutrefresh( w_data );

        if( isWide && !current.empty() ) {
            const recipe *cur_recipe = current[line];
            werase( w_iteminfo );
            if( cur_recipe->is_practice() ) {
                const std::string desc = practice_recipe_description( *cur_recipe, *crafter );
                fold_and_print( w_iteminfo, point::zero, item_info_width, c_light_gray, desc );
                scrollbar().offset_x( item_info_width - 1 ).offset_y( 0 ).content_size( 1 ).viewport_size( getmaxy(
                            w_iteminfo ) ).apply( w_iteminfo );
                wnoutrefresh( w_iteminfo );
            } else if( cur_recipe->is_nested() ) {
                std::string desc = cur_recipe->description.translated() + "\n\n";
                desc += list_nested( *crafter, cur_recipe, available_recipes );
                fold_and_print( w_iteminfo, point::zero, item_info_width, c_light_gray, desc );
                scrollbar().offset_x( item_info_width - 1 ).offset_y( 0 ).content_size( 1 ).viewport_size( getmaxy(
                            w_iteminfo ) ).apply( w_iteminfo );
                wnoutrefresh( w_iteminfo );
            } else {
                item_info_data data = result_info.get_result_data( cur_recipe, batch_size, line_item_info,
                                      w_iteminfo );
                data.without_getch = true;
                data.without_border = true;
                data.scrollbar_left = false;
                data.use_full_win = true;
                data.padding = 0;
                draw_item_info( w_iteminfo, data );
            }
        }
    } );

    do {
        if( recalc ) {
            // When we switch tabs, redraw the header
            recalc = false;
            const recipe *prev_rcp = nullptr;
            if( keepline && line >= 0 && static_cast<size_t>( line ) < current.size() ) {
                prev_rcp = current[line];
            }

            show_hidden = false;
            available.clear();

            if( batch ) {
                current.clear();
                for( int i = 1; i <= 50; i++ ) {
                    current.push_back( chosen );
                    available.emplace_back( *crafter, chosen, i, camp_crafting, inventory_override );
                }
                indent.assign( current.size(), 0 );
            } else {
                static_popup popup;
                std::chrono::steady_clock::time_point last_update = std::chrono::steady_clock::now();
                static constexpr std::chrono::milliseconds update_interval( 500 );
                // Get a key description for the cancel button.
                // Rather than propagating the context, create a new one here as a one-off.
                // See register_action( "QUIT" ) in recipe_dictionary.cpp (line 289 when this was commited).
                input_context dummy;
                dummy.register_action( "QUIT" );
                std::string cancel_btn = dummy.get_button_text( "QUIT", _( "Cancel" ) );
                std::function<void( size_t, size_t )> progress_callback =
                [&]( size_t at, size_t out_of ) {
                    std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
                    if( now - last_update < update_interval ) {
                        return;
                    }
                    last_update = now;
                    double percent = 100.0 * at / out_of;
                    popup.message( _( "Searching… %3.0f%%\n%s\n" ), percent, cancel_btn );
                    ui_manager::redraw();
                    refresh_display();
                    inp_mngr.pump_events();
                };

                std::vector<const recipe *> picking;
                if( !filterstring.empty() ) {
                    std::string qry = trim( filterstring );
                    recipe_subset filtered_recipes =
                        filter_recipes( available_recipes, qry, *crafter, progress_callback );
                    picking.insert( picking.end(), filtered_recipes.begin(), filtered_recipes.end() );
                } else {
                    const std::pair<std::vector<const recipe *>, bool> result = recipes_from_cat( available_recipes,
                            crafting_category_id( tab.cur() ), subtab.cur() );
                    show_hidden = result.second;
                    if( show_hidden ) {
                        current = result.first;
                    } else {
                        picking = result.first;
                    }
                }

                if( !show_hidden ) {
                    current.clear();
                    for( const recipe *i : picking ) {
                        if( uistate.hidden_recipes.find( i->ident() ) == uistate.hidden_recipes.end() ) {
                            current.push_back( i );
                        }
                    }
                    num_hidden = picking.size() - current.size();
                    num_recipe = picking.size();
                }

                available.reserve( current.size() );
                // cache recipe availability on first display
                for( const recipe *e : current ) {
                    if( !availability_cache->count( e ) ) {
                        availability_cache->emplace( e, availability( *crafter, e, 1, camp_crafting, inventory_override ) );
                    }
                }

                if( subtab.cur() != "CSC_*_RECENT" ) {
                    std::stable_sort( current.begin(), current.end(), [
                       crafter, &availability_cache, unread_recipes_first,
                       highlight_unread_recipes
                    ]( const recipe * const a, const recipe * const b ) {
                        if( highlight_unread_recipes && unread_recipes_first ) {
                            const bool a_read = uistate.read_recipes.count( a->ident() );
                            const bool b_read = uistate.read_recipes.count( b->ident() );
                            if( a_read != b_read ) {
                                return !a_read;
                            }
                        }
                        const bool can_craft_a = availability_cache->at( a ).can_craft;
                        const bool can_craft_b = availability_cache->at( b ).can_craft;
                        if( can_craft_a != can_craft_b ) {
                            return can_craft_a;
                        }
                        if( b->difficulty != a->difficulty ) {
                            return b->difficulty < a->difficulty;
                        }
                        const std::string a_name = a->result_name();
                        const std::string b_name = b->result_name();
                        if( a_name != b_name ) {
                            return localized_compare( a_name, b_name );
                        }
                        return b->time_to_craft( *crafter ) <
                               a->time_to_craft( *crafter );
                    } );
                }

                // set up indents and append the expanded entries
                // have to do this after we sort the list
                indent.assign( current.size(), 0 );
                expand_recipes( current, indent, *availability_cache, *crafter, unread_recipes_first,
                                highlight_unread_recipes, available_recipes, uistate.hidden_recipes );

                std::transform( current.begin(), current.end(),
                std::back_inserter( available ), [&]( const recipe * e ) {
                    return availability_cache->at( e );
                } );
            }

            line = 0;
            if( keepline && prev_rcp ) {
                // point to previously selected recipe
                int rcp_idx = 0;
                for( const recipe *const rcp : current ) {
                    if( rcp == prev_rcp ) {
                        line = rcp_idx;
                        break;
                    }
                    ++rcp_idx;
                }
            }
        }
        keepline = false;

        if( highlight_unread_recipes && !current.empty() && user_moved_line ) {
            // only automatically mark as read when moving cursor up or down by
            // one line, which means that the user is likely reading through the
            // list.
            user_moved_line = false;
            uistate.read_recipes.insert( current[line]->ident() );
            if( last_line != -1 ) {
                uistate.read_recipes.insert( current[last_line]->ident() );
                last_line = -1;
            }
            recalc_unread = true;
        }

        const bool previously_toggled_unread = just_toggled_unread;
        just_toggled_unread = false;
        ui_manager::redraw();
        const int scroll_item_info_lines = catacurses::getmaxy( w_iteminfo ) - 4;
        std::string action = ctxt.handle_input();
        const int recmax = static_cast<int>( current.size() );
        const int scroll_rate = recmax > 20 ? 10 : 3;

        std::optional<point> coord = ctxt.get_coordinates_text( catacurses::stdscr );
        const bool mouse_in_list = coord.has_value() && mouseover_area_list.contains( coord.value() );
        const bool mouse_in_recipe = coord.has_value() && mouseover_area_recipe.contains( coord.value() );

        // Check mouse selection of recipes separately so that selecting an already-selected recipe
        // can go straight to "CONFIRM"
        if( action == "SELECT" ) {
            if( coord.has_value() ) {
                point local_coord = coord.value() - point( getbegx( w_data ), getbegy( w_data ) );
                for( const auto &entry : list_map ) {
                    if( entry.second.contains( local_coord ) ) {
                        if( line == static_cast<int>( entry.first ) ) {
                            action = "CONFIRM";
                        } else {
                            if( !previously_toggled_unread ) {
                                last_line = line;
                            }
                            line = entry.first;
                            user_moved_line = highlight_unread_recipes;
                        }
                    }
                }
            }
        }

        if( action == "SELECT" ) {
            bool handled = false;
            if( coord.has_value() ) {
                point local_coord = coord.value() - point( getbegx( w_head_tabs ), getbegy( w_head_tabs ) );
                for( const auto &entry : translated_tab_map ) {
                    if( entry.second.contains( local_coord ) ) {
                        tab.set_index( entry.first );
                        recalc = true;
                        subtab = tab_list( crafting_category_id( tab.cur() )->subcategories );
                        handled = true;
                    }
                }
                local_coord = coord.value() - point( getbegx( w_subhead ), getbegy( w_subhead ) );
                if( !handled && !batch && filterstring.empty() ) {
                    for( const auto &entry : translated_subtab_map ) {
                        if( entry.second.contains( local_coord ) ) {
                            subtab.set_index( entry.first );
                            recalc = true;
                        }
                    }
                }
            }
        } else if( action == "SCROLL_RECIPE_INFO_UP" ) {
            line_recipe_info -= dataLines;
        } else if( action == "SCROLL_UP" && mouse_in_recipe ) {
            --line_recipe_info;
        } else if( action == "SCROLL_RECIPE_INFO_DOWN" ) {
            line_recipe_info += dataLines;
        } else if( action == "SCROLL_DOWN" && mouse_in_recipe ) {
            ++line_recipe_info;
        } else if( action == "LEFT" || ( action == "SCROLL_UP" && mouse_in_window( coord, w_subhead ) ) ) {
            if( batch || !filterstring.empty() ) {
                continue;
            }
            std::string start = subtab.cur();
            do {
                subtab.prev();
            } while( subtab.cur() != start &&
                     available_recipes.empty_category( crafting_category_id( tab.cur() ),
                             subtab.cur() != "CSC_ALL" ? subtab.cur() : "" ) );
            recalc = true;
        } else if( action == "SCROLL_ITEM_INFO_UP" ) {
            line_item_info -= scroll_item_info_lines;
        } else if( action == "SCROLL_UP" && mouse_in_window( coord, w_iteminfo ) ) {
            --line_item_info;
        } else if( action == "SCROLL_ITEM_INFO_DOWN" ) {
            line_item_info += scroll_item_info_lines;
        } else if( action == "SCROLL_DOWN" && mouse_in_window( coord, w_iteminfo ) ) {
            ++line_item_info;
        } else if( action == "PREV_TAB" || ( action == "SCROLL_UP" &&
                                             mouse_in_window( coord, w_head_tabs ) ) ) {
            tab.prev();
            // Default ALL
            subtab = tab_list( crafting_category_id( tab.cur() )->subcategories );
            recalc = true;
        } else if( action == "RIGHT" || ( action == "SCROLL_DOWN" &&
                                          mouse_in_window( coord, w_subhead ) ) ) {
            if( batch || !filterstring.empty() ) {
                continue;
            }
            std::string start = subtab.cur();
            do {
                subtab.next();
            } while( subtab.cur() != start &&
                     available_recipes.empty_category( crafting_category_id( tab.cur() ),
                             subtab.cur() != "CSC_ALL" ? subtab.cur() : "" ) );
            recalc = true;
        } else if( action == "NEXT_TAB" || ( action == "SCROLL_DOWN" &&
                                             mouse_in_window( coord, w_head_tabs ) ) ) {
            tab.next();
            // Default ALL
            subtab = tab_list( crafting_category_id( tab.cur() )->subcategories );
            recalc = true;
        } else if( action == "DOWN" ) {
            if( !previously_toggled_unread ) {
                last_line = line;
            }
            line++;
            user_moved_line = highlight_unread_recipes;
        } else if( action == "SCROLL_DOWN" && mouse_in_list ) {
            line = std::min( recmax - 1, line + 1 );
        } else if( action == "UP" ) {
            if( !previously_toggled_unread ) {
                last_line = line;
            }
            line--;
            user_moved_line = highlight_unread_recipes;
        } else if( action == "SCROLL_UP" && mouse_in_list ) {
            line = std::max( 0, line - 1 );
        } else if( action == "PAGE_UP" || action == "PAGE_DOWN" ) {
            line = inc_clamp( line, action == "PAGE_UP" ? -scroll_rate : scroll_rate, recmax );
        } else if( action == "HOME" ) {
            line = 0;
            user_moved_line = highlight_unread_recipes;
        } else if( action == "END" ) {
            line = -1;
            user_moved_line = highlight_unread_recipes;
        } else if( action == "CONFIRM" ) {
            if( available.empty() ) {
                popup( _( "Nothing selected!" ) );
            } else if( current[line]->is_nested() ) {
                nested_toggle( current[line]->ident(), recalc, keepline );
            } else if( !available[line].can_craft ||
                       !available[line].crafter_has_primary_skill ) {
                popup( _( "Crafter can't craft that!" ) );
            } else if( available[line].inv_override == nullptr &&
                       !crafter->check_eligible_containers_for_crafting( *current[line], batch ? line + 1 : 1 ) ) {
                // popup is already inside check
            } else if( crafter->lighting_craft_speed_multiplier( *current[line] ) <= 0.0f ) {
                popup( _( "Crafter can't see!" ) );
            } else {
                chosen = current[line];
                batch_size_out = batch ? line + 1 : 1;
                done = true;
                uistate.read_recipes.insert( chosen->ident() );
            }
        } else if( action == "HELP_RECIPE" && selection_ok( current, line, false ) ) {
            uistate.read_recipes.insert( current[line]->ident() );
            recalc_unread = highlight_unread_recipes;
            ui.invalidate_ui();

            item_info_data data = result_info.get_result_data( current[line], 1, line_item_info_popup,
                                  w_iteminfo );
            data.handle_scrolling = true;
            data.arrow_scrolling = true;
            const int info_width = std::min( TERMX, FULL_SCREEN_WIDTH );
            const int info_height = std::min( TERMY, FULL_SCREEN_HEIGHT );
            iteminfo_window info_window( data, point( ( TERMX - info_width ) / 2, ( TERMY - info_height ) / 2 ),
                                         info_width, info_height );
            info_window.execute();
        } else if( action == "FILTER" ) {
            int max_example_length = 0;
            for( const auto &prefix : prefixes ) {
                max_example_length = std::max( max_example_length, utf8_width( prefix.example.translated() ) );
            }
            std::string spaces( max_example_length, ' ' );

            std::string description = filter_help_start.translated();

            {
                std::string example_name = _( "shirt" );
                int padding = max_example_length - utf8_width( example_name );
                description += string_format(
                                   _( "  <color_white>%s</color>%.*s    %s\n" ),
                                   example_name, padding, spaces,
                                   _( "<color_cyan>name</color> of resulting item" ) );

                std::string example_exclude = _( "clean" );
                padding = max_example_length - utf8_width( example_exclude );
                description += string_format(
                                   _( "  <color_yellow>-</color><color_white>%s</color>%.*s   %s\n" ),
                                   example_exclude, padding, spaces,
                                   _( "<color_cyan>names</color> to exclude" ) );
            }

            for( const auto &prefix : prefixes ) {
                int padding = max_example_length - utf8_width( prefix.example.translated() );
                description += string_format(
                                   _( "  <color_yellow>%c</color><color_white>:%s</color>%.*s  %s\n" ),
                                   prefix.key, prefix.example, padding, spaces, prefix.description );
            }

            description +=
                _( "\nUse <color_red>up/down arrow</color> to go through your search history." );

            string_input_popup popup;
            popup
            .title( _( "Search:" ) )
            .width( 85 )
            .description( description )
            .desc_color( c_light_gray )
            .identifier( "craft_recipe_filter" )
            .hist_use_uilist( false )
            .edit( filterstring );

            if( popup.confirmed() ) {
                recalc = true;
                recalc_unread = highlight_unread_recipes;
                if( batch ) {
                    // exit from batch selection
                    batch = false;
                    line = batch_line;
                }
            }
        } else if( action == "QUIT" ) {
            chosen = nullptr;
            done = true;
        } else if( action == "RESET_FILTER" ) {
            filterstring.clear();
            recalc = true;
            recalc_unread = highlight_unread_recipes;
        } else if( action == "CYCLE_BATCH" && selection_ok( current, line, false ) ) {
            batch = !batch;
            if( batch ) {
                batch_line = line;
                chosen = current[batch_line];
                uistate.read_recipes.insert( chosen->ident() );
                recalc_unread = highlight_unread_recipes;
            } else {
                keepline = true;
            }
            recalc = true;
        } else if( action == "CHOOSE_CRAFTER" ) {
            // allow for switching crafter when no recipes are shown (e.g. filter)
            bool rec_valid = !current.empty();
            const recipe *rec = rec_valid ? current[line] : nullptr;
            int new_crafter_i = choose_crafter( crafting_group, crafter_i, rec, rec_valid );
            if( new_crafter_i >= 0 && new_crafter_i != crafter_i ) {
                crafter_i = new_crafter_i;
                crafter = crafting_group[crafter_i];
                // next line also inserts empty cache for crafter->getID() if non existant
                availability_cache = &guy_availability_cache[crafter->getID()];
                recalc = true;
                keepline = true;
            }
        } else if( action == "TOGGLE_FAVORITE" && selection_ok( current, line, true ) ) {
            keepline = true;
            recalc = filterstring.empty() && subtab.cur() == "CSC_*_FAVORITE";
            if( uistate.favorite_recipes.find( current[line]->ident() ) != uistate.favorite_recipes.end() ) {
                uistate.favorite_recipes.erase( current[line]->ident() );
                if( recalc ) {
                    if( static_cast<size_t>( line ) + 1 < current.size() ) {
                        line++;
                    } else {
                        line--;
                    }
                }
            } else {
                uistate.favorite_recipes.insert( current[line]->ident() );
                uistate.read_recipes.insert( current[line]->ident() );
            }
            recalc_unread = highlight_unread_recipes;
        } else if( action == "HIDE_SHOW_RECIPE" && selection_ok( current, line, true ) ) {
            if( show_hidden ) {
                uistate.hidden_recipes.erase( current[line]->ident() );
            } else {
                uistate.hidden_recipes.insert( current[line]->ident() );
                uistate.read_recipes.insert( current[line]->ident() );
            }

            recalc = true;
            recalc_unread = highlight_unread_recipes;
            keepline = true;
            if( static_cast<size_t>( line ) + 1 < current.size() ) {
                line++;
            } else {
                line--;
            }
        } else if( action == "TOGGLE_RECIPE_UNREAD" && selection_ok( current, line, true ) ) {
            const recipe_id rcp = current[line]->ident();
            if( uistate.read_recipes.count( rcp ) ) {
                for( const recipe_id nested_rcp : rcp->nested_category_data ) {
                    uistate.read_recipes.erase( nested_rcp );
                }
                uistate.read_recipes.erase( rcp );
            } else {
                for( const recipe_id nested_rcp : rcp->nested_category_data ) {
                    uistate.read_recipes.insert( nested_rcp );
                }
                uistate.read_recipes.insert( rcp );
            }
            recalc_unread = highlight_unread_recipes;
            just_toggled_unread = true;
        } else if( action == "MARK_ALL_RECIPES_READ" ) {
            bool current_list_has_unread = false;
            for( const recipe *const rcp : current ) {
                for( const recipe_id nested_rcp : rcp->nested_category_data ) {
                    if( !uistate.read_recipes.count( nested_rcp->ident() ) ) {
                        current_list_has_unread = true;
                        break;
                    }
                    if( current_list_has_unread ) {
                        break;
                    }
                }
                if( !uistate.read_recipes.count( rcp->ident() ) ) {
                    current_list_has_unread = true;
                    break;
                }
            }
            std::string query_str;
            if( !current_list_has_unread ) {
                query_str = _( "<color_yellow>/!\\</color> Mark all recipes as read?  "
                               // NOLINTNEXTLINE(cata-text-style): single spaced for symmetry
                               "This cannot be undone. <color_yellow>/!\\</color>" );
            } else if( filterstring.empty() ) {
                query_str = string_format( _( "Mark recipes in this tab as read?  This cannot be undone.  "
                                              "You can mark all recipes by choosing yes and pressing %s again." ),
                                           ctxt.get_desc( "MARK_ALL_RECIPES_READ" ) );
            } else {
                query_str = string_format( _( "Mark filtered recipes as read?  This cannot be undone.  "
                                              "You can mark all recipes by choosing yes and pressing %s again." ),
                                           ctxt.get_desc( "MARK_ALL_RECIPES_READ" ) );
            }
            if( query_yn( query_str ) ) {
                if( current_list_has_unread ) {
                    for( const recipe *const rcp : current ) {
                        for( const recipe_id nested_rcp : rcp->nested_category_data ) {
                            uistate.read_recipes.insert( nested_rcp->ident() );
                        }
                        uistate.read_recipes.insert( rcp->ident() );
                    }
                } else {
                    for( const recipe *const rcp : available_recipes ) {
                        for( const recipe_id nested_rcp : rcp->nested_category_data ) {
                            uistate.read_recipes.insert( nested_rcp->ident() );
                        }
                        uistate.read_recipes.insert( rcp->ident() );
                    }
                }
            }
            recalc_unread = highlight_unread_recipes;
        } else if( action == "TOGGLE_UNREAD_RECIPES_FIRST" ) {
            unread_recipes_first = !unread_recipes_first;
            recalc = true;
            keepline = true;
        } else if( action == "RELATED_RECIPES" && selection_ok( current, line, false ) ) {
            uistate.read_recipes.insert( current[line]->ident() );
            recalc_unread = highlight_unread_recipes;
            ui.invalidate_ui();

            std::string recipe_name = peek_related_recipe( current[line], available_recipes, *crafter );
            if( !recipe_name.empty() ) {
                filterstring = recipe_name;
                recalc = true;
                recalc_unread = highlight_unread_recipes;
            }
        } else if( action == "COMPARE" && selection_ok( current, line, false ) ) {
            const item recipe_result = get_recipe_result_item( *current[line], *crafter );
            compare_recipe_with_item( recipe_result, *crafter );
        } else if( action == "HELP_KEYBINDINGS" ) {
            // Regenerate keybinding tips
            ui.mark_resize();
        }
        if( line < 0 ) {
            line = current.size() - 1;
        } else if( line >= static_cast<int>( current.size() ) ) {
            line = 0;
        }
    } while( !done );

    return { crafter, chosen };
}

int choose_crafter( const std::vector<Character *> &crafting_group, int crafter_i,
                    const recipe *rec, bool rec_valid )
{
    std::vector<std::string> header = { _( "Crafter" ) };
    if( rec_valid ) {
        header.emplace_back( rec->is_practice() ? _( "Can practice" ) : _( "Can craft" ) );
        header.emplace_back( _( "Missing" ) );
    }
    header.emplace_back( _( "Status" ) );
    uimenu choose_char_menu( static_cast<int>( header.size() ) );
    choose_char_menu.set_title( _( "Choose the crafter" ) );
    choose_char_menu.addentry( -1, false, header );

    int i = 0;
    for( Character *chara : crafting_group ) {
        std::vector<std::string> entry = { chara->name_and_maybe_activity() };
        if( rec_valid ) {
            availability avail = availability( *chara, rec );
            std::vector<std::string> reasons;

            bool has_stuff = rec->deduped_requirements().can_make_with_inventory(
                                 chara->crafting_inventory(), rec->get_component_filter( recipe_filter_flags::none ), 1,
                                 craft_flags::start_only );
            if( !has_stuff ) {
                reasons.emplace_back( _( "stuff" ) );
            }
            if( !avail.crafter_has_primary_skill ) {
                reasons.emplace_back( _( "skill" ) );
            }
            if( !avail.has_proficiencies ) {  // this is required proficiency
                reasons.emplace_back( _( "proficiency" ) );
            }
            if( chara->lighting_craft_speed_multiplier( *rec ) <= 0.0f ) {
                reasons.emplace_back( _( "light" ) );
            }
            std::string dummy;
            if( chara->is_npc() && !rec->npc_can_craft( dummy ) ) {
                reasons.emplace_back( _( "is NPC" ) );
            }

            entry.emplace_back(
                // *INDENT-OFF* readable ternary operator
                rec->is_nested()
                    ? colorize( "-", c_yellow )
                    : reasons.empty()
                        ? colorize( _( "yes" ), c_green )
                        : colorize( _( "no" ), c_red ) );
                // *INDENT-ON* readable ternary operator
            entry.emplace_back( colorize( string_join( reasons, ", " ), c_red ) );
        }
        entry.emplace_back( chara->in_sleep_state()
                            ? colorize( _( "asleep" ), c_red )
                            : colorize( _( "awake" ), c_green ) );
        choose_char_menu.addentry( i, !chara->in_sleep_state(), entry );
        ++i;
    }

    choose_char_menu.set_selected( crafter_i + 1 );  // +1 for header entry
    return choose_char_menu.query();
}

std::string peek_related_recipe( const recipe *current, const recipe_subset &available,
                                 Character &crafter )
{
    auto compare_second =
        []( const std::pair<itype_id, std::string> &a,
    const std::pair<itype_id, std::string> &b ) {
        return localized_compare( a.second, b.second );
    };

    // current recipe components
    std::vector<std::pair<itype_id, std::string>> related_components;
    const requirement_data &req = current->simple_requirements();
    for( const std::vector<item_comp> &comp_list : req.get_components() ) {
        for( const item_comp &a : comp_list ) {
            related_components.emplace_back( a.type, item::nname( a.type, 1 ) );
        }
    }
    std::sort( related_components.begin(), related_components.end(), compare_second );
    // current recipe result
    std::vector<std::pair<itype_id, std::string>> related_results;
    item tmp( current->result() );
    // use this item
    const itype_id tid = tmp.typeId();
    const std::set<const recipe *> &known_recipes =
        crafter.get_learned_recipes().of_component( tid );
    for( const recipe * const &b : known_recipes ) {
        if( available.contains( b ) ) {
            related_results.emplace_back( b->result(), b->result_name( /*decorated=*/true ) );
        }
    }
    std::stable_sort( related_results.begin(), related_results.end(), compare_second );

    if( related_components.empty() && related_results.empty() ) {
        return "";
    }

    uilist rel_menu;
    int np_last = -1;
    if( !related_components.empty() ) {
        rel_menu.addentry( ++np_last, false, -1, _( "COMPONENTS" ) );
    }
    np_last = related_menu_fill( rel_menu, related_components, available );
    if( !related_results.empty() ) {
        rel_menu.addentry( ++np_last, false, -1, _( "RESULTS" ) );
    }

    related_menu_fill( rel_menu, related_results, available );

    rel_menu.settext( _( "Related recipes:" ) );
    rel_menu.query();
    if( rel_menu.ret != UILIST_CANCEL ) {

        // Grab the recipe name without our bullet point.
        std::string recipe = rel_menu.entries[rel_menu.ret].txt.substr( strlen( "─ " ) );

        // If the string is decorated as a favourite, return it without the star
        if( recipe.rfind( "* ", 0 ) == 0 ) {
            return recipe.substr( strlen( "* " ) );
        }

        return recipe;
    }

    return "";
}

int related_menu_fill( uilist &rmenu,
                       const std::vector<std::pair<itype_id, std::string>> &related_recipes,
                       const recipe_subset &available )
{
    const std::vector<uilist_entry> &entries = rmenu.entries;
    int np_last = entries.empty() ? -1 : entries.back().retval;

    if( related_recipes.empty() ) {
        return np_last;
    }

    std::string recipe_name_prev;
    for( const std::pair<itype_id, std::string> &p : related_recipes ) {

        // we have different recipes with the same names
        // list only one of them as we show and filter by name only
        std::string recipe_name = p.second;
        if( recipe_name == recipe_name_prev ) {
            continue;
        }
        recipe_name_prev = recipe_name;

        std::vector<const recipe *> current_part = available.recipes_that_produce( p.first );
        if( current_part.empty() ) {
            continue;
        }

        bool different_recipes = false;

        // 1st pass: check if we need to add group
        for( size_t recipe_n = 0; recipe_n < current_part.size(); recipe_n++ ) {
            if( current_part[recipe_n]->result_name( /*decorated=*/true ) != recipe_name ) {
                // add group
                rmenu.addentry( ++np_last, false, -1, recipe_name );
                different_recipes = true;
                break;
            } else if( recipe_n == current_part.size() - 1 ) {
                // only one result
                rmenu.addentry( ++np_last, true, -1, "─ " + recipe_name );
            }
        }
        if( !different_recipes ) {
            continue;
        }
        std::string prev_item_name;
        // 2nd pass: add different recipes
        for( size_t recipe_n = 0; recipe_n < current_part.size(); recipe_n++ ) {
            std::string cur_item_name = current_part[recipe_n]->result_name( /*decorated=*/true );
            if( cur_item_name != prev_item_name ) {
                std::string sym = recipe_n == current_part.size() - 1 ? "└ " : "├ ";
                rmenu.addentry( ++np_last, true, -1, sym + cur_item_name );
            }
            prev_item_name = cur_item_name;
        }
    }

    return np_last;
}

static void compare_recipe_with_item( const item &recipe_item, Character &crafter )
{
    inventory_pick_selector inv_s( crafter );

    inv_s.add_character_items( crafter );
    inv_s.set_title( _( "Compare" ) );
    inv_s.set_hint( _( "Select item to compare with." ) );

    if( inv_s.empty() ) {
        popup( std::string( _( "There are no items to compare." ) ), PF_GET_KEY );
        return;
    }

    do {
        const item_location to_compare = inv_s.execute();
        if( !to_compare ) {
            break;
        }
        game_menus::inv::compare_item_menu menu( recipe_item, *to_compare );
        menu.show();
    } while( true );
}

static bool query_is_yes( std::string_view query )
{
    const std::string_view subquery = query.substr( 2 );

    return subquery == "yes" || subquery == "y" || subquery == "1" ||
           subquery == "true" || subquery == "t" || subquery == "on" ||
           subquery == _( "yes" );
}

static void draw_hidden_amount( const catacurses::window &w, int amount, int num_recipe )
{
    if( amount == 1 ) {
        right_print( w, 1, 1, c_red, string_format( _( "* %s hidden recipe - %s in category *" ), amount,
                     num_recipe ) );
    } else if( amount >= 2 ) {
        right_print( w, 1, 1, c_red, string_format( _( "* %s hidden recipes - %s in category *" ), amount,
                     num_recipe ) );
    } else if( amount == 0 ) {
        right_print( w, 1, 1, c_green, string_format( _( "* No hidden recipe - %s in category *" ),
                     num_recipe ) );
    }
    //Finish border connection with the recipe tabs
    wattron( w, BORDER_COLOR );
    mvwhline( w, point( 0, getmaxy( w ) - 1 ), LINE_OXOX, getmaxx( w ) - 1 );
    mvwaddch( w, point( getmaxx( w ) - 1, getmaxy( w ) - 1 ), LINE_OOXX ); // ^|
    wattroff( w, BORDER_COLOR );
    wnoutrefresh( w );
}

// Anchors top-right
static void draw_can_craft_indicator( const catacurses::window &w, const recipe &rec,
                                      Character &crafter )
{
    int limb_modifier = rec.has_flag( flag_NO_MANIP ) ? 100 : crafter.get_limb_score(
                            limb_score_manip ) * 100;
    int mut_multi = rec.has_flag( flag_NO_ENCHANTMENT ) ? 100 : ( 1.0 +
                    crafter.enchantment_cache->get_value_multiply( enchant_vals::mod::CRAFTING_SPEED_MULTIPLIER ) ) *
                    100;

    std::stringstream modifiers_list;
    if( limb_modifier != 100 ) {
        if( limb_modifier < 100 ) {
            modifiers_list << _( "hands encumbrance/wounds" ) << " " << limb_modifier << "%";
        } else {
            modifiers_list << _( "extra manipulators" ) << " " << limb_modifier << "%";
        }
    }
    if( mut_multi != 100 ) {
        if( !modifiers_list.str().empty() ) {
            modifiers_list << ", ";
        }
        modifiers_list << _( "traits" ) << " " << mut_multi << "%";
    }

    if( crafter.lighting_craft_speed_multiplier( rec ) <= 0.0f ) {
        right_print( w, 0, 1, i_red, craft_speed_reason_strings.at( TOO_DARK_TO_CRAFT ).translated() );
    } else if( crafter.crafting_speed_multiplier( rec ) <= 0.0f ) {
        right_print( w, 0, 1, i_red, craft_speed_reason_strings.at( TOO_SLOW_TO_CRAFT ).translated() );
    } else if( crafter.crafting_speed_multiplier( rec ) < 1.0f ) {
        int morale_modifier = crafter.morale_crafting_speed_multiplier( rec ) * 100;
        int lighting_modifier = crafter.lighting_craft_speed_multiplier( rec ) * 100;
        int pain_multi = rec.has_flag( flag_AFFECTED_BY_PAIN ) ? 100 * std::max( 0.0f,
                         1.0f - ( crafter.get_perceived_pain() / 100.0f ) ) : 100;

        if( morale_modifier < 100 ) {
            if( !modifiers_list.str().empty() ) {
                modifiers_list << ", ";
            }
            modifiers_list << _( "morale" ) << " " << morale_modifier << "%";
        }
        if( lighting_modifier < 100 ) {
            if( !modifiers_list.str().empty() ) {
                modifiers_list << ", ";
            }
            modifiers_list << _( "lighting" ) << " " << lighting_modifier << "%";
        }
        if( pain_multi < 100 ) {
            if( !modifiers_list.str().empty() ) {
                modifiers_list << ", ";
            }
            modifiers_list << _( "pain" ) << " " << pain_multi << "%";
        }

        right_print( w, 0, 1, i_yellow,
                     string_format( craft_speed_reason_strings.at( SLOW_BUT_CRAFTABLE ).translated(),
                                    static_cast<int>( crafter.crafting_speed_multiplier( rec ) * 100 ),
                                    modifiers_list.str() ) );
    } else if( crafter.crafting_speed_multiplier( rec ) > 1.0f ) {
        right_print( w, 0, 1, i_green,
                     string_format( craft_speed_reason_strings.at( FAST_CRAFTING ).translated(),
                                    static_cast<int>( crafter.crafting_speed_multiplier( rec ) * 100 ),
                                    modifiers_list.str() ) );
    } else {
        right_print( w, 0, 1, i_green, craft_speed_reason_strings.at( NORMAL_CRAFTING ).translated() );
    }
    wnoutrefresh( w );
}

static std::map<size_t, inclusive_rectangle<point>> draw_recipe_tabs( const catacurses::window &w,
        const tab_list &tab, TAB_MODE mode,
        const bool filtered_unread, std::map<std::string, bool> &unread )
{
    werase( w );
    std::map<size_t, inclusive_rectangle<point>> tab_map;

    switch( mode ) {
        case NORMAL: {
            std::vector<std::string> translated_cats;
            translated_cats.reserve( craft_cat_list.size() );
            for( const crafting_category &cat : craft_cat_list.get_all() ) {
                if( cat.is_hidden ) {
                    continue;
                }
                if( unread[ cat.id.str() ] ) {
                    translated_cats.emplace_back( _( get_cat_unprefixed(
                                                         cat.id.str() ) ).append( "<color_light_green>⁺</color>" ) );
                } else {
                    translated_cats.emplace_back( _( get_cat_unprefixed( cat.id.str() ) ) );
                }
            }
            std::pair<std::vector<std::string>, size_t> fitted_tabs = fit_tabs_to_width( getmaxx( w ),
                    tab.cur_index(), translated_cats );
            tab_map = draw_tabs( w, fitted_tabs.first, tab.cur_index() - fitted_tabs.second,
                                 fitted_tabs.second );
            break;
        }
        case FILTERED: {
            wattron( w, BORDER_COLOR );
            mvwhline( w, point( 0, getmaxy( w ) - 1 ), LINE_OXOX, getmaxx( w ) - 1 );
            mvwaddch( w, point( 0, getmaxy( w ) - 1 ), LINE_OXXO ); // ┌
            wattroff( w, BORDER_COLOR );
            std::string tab_name = _( "Searched" );
            if( filtered_unread ) {
                tab_name += " ";  // space for green "+"
            }
            draw_tab( w, 2, tab_name, true );
            if( filtered_unread ) {
                mvwprintz( w, point( 2 + utf8_width( tab_name ), 1 ), c_light_green, "⁺" );
            }
            break;
        }
        case BATCH:
            wattron( w, BORDER_COLOR );
            mvwhline( w, point( 0, getmaxy( w ) - 1 ), LINE_OXOX, getmaxx( w ) - 1 );
            mvwaddch( w, point( 0, getmaxy( w ) - 1 ), LINE_OXXO ); // ┌
            wattroff( w, BORDER_COLOR );
            draw_tab( w, 2, _( "Batch" ), true );
            break;
    }
    //draw_tabs will produce a border ending with ┐ but that's inappropriate here, so clean it up
    mvwputch( w, point( getmaxx( w ) - 1, 2 ), BORDER_COLOR, LINE_OXOX );  // ─
    wnoutrefresh( w );
    return tab_map;
}

static std::map<size_t, inclusive_rectangle<point>> draw_recipe_subtabs(
            const catacurses::window &w, const std::string &tab,
            const size_t subtab,
            const recipe_subset &available_recipes, TAB_MODE mode,
            std::map<std::string, bool> &unread )
{
    werase( w );
    std::map<size_t, inclusive_rectangle<point>> subtab_map;
    int width = getmaxx( w );

    wattron( w, BORDER_COLOR );
    mvwvline( w, point::zero, LINE_XOXO, getmaxy( w ) );  // |
    mvwvline( w, point( width - 1, 0 ), LINE_XOXO, getmaxy( w ) );  // |
    wattroff( w, BORDER_COLOR );

    switch( mode ) {
        case NORMAL: {
            std::vector<std::string> translated_subcats;
            std::vector<bool> empty_subcats;
            std::vector<bool> unread_subcats;
            crafting_category_id current_cat = crafting_category_id( tab );
            size_t subcats_count = current_cat->subcategories.size();
            translated_subcats.reserve( subcats_count );
            empty_subcats.reserve( subcats_count );
            unread_subcats.reserve( subcats_count );
            for( const std::string &subcat : current_cat->subcategories ) {
                translated_subcats.emplace_back( _( get_subcat_unprefixed( tab, subcat ) ) );
                empty_subcats.emplace_back( available_recipes.empty_category(
                                                crafting_category_id( tab ),
                                                subcat != "CSC_ALL" ? subcat : "" ) );
                unread_subcats.emplace_back( unread[subcat] );
            }
            std::pair<std::vector<std::string>, size_t> fitted_subcat_list = fit_tabs_to_width( getmaxx( w ),
                    subtab, translated_subcats );
            size_t offset = fitted_subcat_list.second;
            if( fitted_subcat_list.first.size() + offset > subcats_count ) {
                break;
            }
            // Draw the tabs on each other
            int pos_x = 2;
            // Step between tabs, two for tabs border
            int tab_step = 3;
            for( size_t i = 0; i < fitted_subcat_list.first.size(); ++i ) {
                if( empty_subcats[i + offset] ) {
                    draw_subtab( w, pos_x, fitted_subcat_list.first[i], subtab == i + offset, true,
                                 empty_subcats[i + offset] );
                } else {
                    subtab_map.emplace( i + offset, draw_subtab( w, pos_x, fitted_subcat_list.first[i],
                                        subtab == i + offset, true, empty_subcats[i + offset] ) );
                }
                pos_x += utf8_width( fitted_subcat_list.first[i] ) + tab_step;
                if( unread_subcats[i + offset] ) {
                    mvwprintz( w, point( pos_x - 2, 0 ), c_light_green, "⁺" );
                }
            }
            break;
        }
        case FILTERED:
        case BATCH:
            werase( w );
            wattron( w, BORDER_COLOR );
            mvwvline( w, point::zero, LINE_XOXO, 3 ); // |
            mvwvline( w, point( width - 1, 0 ), LINE_XOXO, 3 ); // |
            wattroff( w, BORDER_COLOR );
            break;
    }

    wnoutrefresh( w );
    return subtab_map;
}

const std::vector<std::string> *subcategories_for_category( const std::string &category )
{
    crafting_category_id cat( category );
    if( !cat.is_valid() ) {
        return nullptr;
    }
    return &cat->subcategories;
}
