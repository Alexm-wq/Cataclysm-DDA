#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "bionics.h"
#include "bionics_ui_model.h"
#include "bodygraph.h"
#include "bodypart.h"
#include "calendar.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "character.h"
#include "color.h"
#include "cursesdef.h"
#include "debug.h"
#include "display.h"
#include "effect.h"
#include "enum_conversions.h"
#include "game.h"
#include "game_inventory.h"
#include "input.h"
#include "input_context.h"
#include "item.h"
#include "item_location.h"
#include "itype.h"
#include "magic.h"
#include "map.h"
#include "mutation.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "proficiency.h"
#include "ret_val.h"
#include "skill.h"
#include "string_formatter.h"
#include "string_input_popup.h"
#include "translations.h"
#include "uilist.h"
#include "ui_manager.h"
#include "units.h"
#include "uistate.h"
#include "vehicle.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/dropdown.h"
#include "ui_helpers/controls/key_field.h"
#include "ui_helpers/controls/scroll_view.h"
#include "ui_helpers/controls/selection_list.h"

static const json_character_flag json_flag_BIONIC_GUN( "BIONIC_GUN" );
static const itype_id character_hub_battery( "battery" );

// Keep the same shortcut alphabet as the dedicated mutation/bionic controls.
// '!' and '=' remain available to their normal menu bindings.
static const invlet_wrapper character_hub_mutation_chars(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\"#&()*+./:;@[\\]^_{|}" );

// Rescale temperature value to one that the player sees.
static int temperature_print_rescaling( units::temperature temp )
{
    return ( units::to_legacy_bodypart_temp( temp ) / 100.0 ) * 2 - 100;
}

static bool should_combine_bps( const Character &p, const bodypart_id &l, const bodypart_id &r,
                                const item *selected_clothing )
{
    return l != r &&
           l == r->opposite_part && r == l->opposite_part &&
           p.compare_encumbrance_data( l, r ) &&
           temperature_print_rescaling( p.get_part_temp_conv( l ) ) ==
           temperature_print_rescaling( p.get_part_temp_conv( r ) ) &&
           ( !selected_clothing || selected_clothing->covers( l ) == selected_clothing->covers( r ) ) &&
           p.get_part_hp_cur( l ) == p.get_part_hp_cur( r );
}

static std::vector<std::pair<bodypart_id, bool>> list_and_combine_bps( const Character &p,
        const item *selected_clothing )
{
    std::vector<std::pair<bodypart_id, bool>> bps;
    for( const bodypart_id &bp : p.get_all_body_parts( get_body_part_flags::sorted ) ) {
        if( should_combine_bps( p, bp, bp->opposite_part.id(), selected_clothing ) ) {
            if( std::find( bps.begin(), bps.end(),
                           std::pair<bodypart_id, bool>( bp->opposite_part.id(), true ) ) == bps.end() ) {
                bps.emplace_back( bp, true );
            }
        } else {
            bps.emplace_back( bp, false );
        }
    }
    return bps;
}

void Character::print_encumbrance( ui_adaptor &ui, const catacurses::window &win,
                                   const int line, const item *const selected_clothing ) const
{
    const std::vector<std::pair<bodypart_id, bool>> bps = list_and_combine_bps( *this,
            selected_clothing );

    const int height = getmaxy( win ) - 1;
    const bool do_draw_scrollbar = height < static_cast<int>( bps.size() );
    const int width = getmaxx( win ) - ( do_draw_scrollbar ? 1 : 0 );
    const int firstline = clamp( line - height / 2, 0, std::max( 0,
                                 static_cast<int>( bps.size() ) - height ) );

    for( int i = 0; i < height; ++i ) {
        const int thisline = firstline + i;
        if( thisline < 0 ) {
            continue;
        }
        if( static_cast<size_t>( thisline ) >= bps.size() ) {
            break;
        }

        const bodypart_id &bp = bps[thisline].first;
        const bool combine = bps[thisline].second;
        const int encumbrance = get_part_encumbrance( bp );
        const int layer_penalty = get_part_layer_penalty( bp );

        const bool highlighted = selected_clothing ? selected_clothing->covers( bp ) : false;
        std::string out = body_part_name_as_heading( bp, combine ? 2 : 1 );
        if( utf8_width( out ) > 7 ) {
            out = utf8_truncate( out, 7 );
        }

        const bool highlight_line = thisline == line;
        const nc_color limb_color = highlight_line ?
                                    ( highlighted ? h_green : h_light_gray ) :
                                    ( highlighted ? c_green : c_light_gray );
        const int y_pos = 1 + i;
        if( highlight_line ) {
            ui.set_cursor( win, point( 1, y_pos ) );
        }
        mvwprintz( win, point( 1, y_pos ), limb_color, "%s", out );

        int column = std::max( 10, ( width / 2 ) - 3 );
        mvwprintz( win, point( column, y_pos ), display::encumb_color( encumbrance ), "%3d",
                   encumbrance - layer_penalty );
        column += 3;
        mvwprintz( win, point( column, y_pos ), c_light_gray, "+" );
        ++column;
        mvwprintz( win, point( column, y_pos ), display::encumb_color( encumbrance ), "%-3d",
                   layer_penalty );
        mvwprintz( win, point( width - 6, y_pos ), display::bodytemp_color( *this, bp ), "(% 3d)",
                   temperature_print_rescaling( get_part_temp_conv( bp ) ) );
    }

    if( do_draw_scrollbar ) {
        draw_scrollbar( win, firstline, height, bps.size(), point( width, 1 ), c_white, true );
    }
}

namespace
{
using bio_uid = bionic::bionic_uid;

enum class character_page : int {
    overview,
    body,
    skills,
    traits,
    mutations,
    effects,
    bionics,
    proficiencies,
};

// Used only by the legacy ACTION_BIONICS/ACTION_MUTATIONS entry points.  They
// now open this hub on the appropriate page instead of constructing a second UI.
static std::optional<character_page> pending_character_page;

struct character_hub_model {
    std::vector<const Skill *> skills;
    std::vector<trait_and_var> traits;
    std::array<std::vector<trait_id>, 2> mutations;
    std::vector<std::pair<std::string, std::string>> effects;
    std::array<std::vector<bio_uid>, 2> bionics;
    std::vector<display_proficiency> proficiencies;
    std::vector<std::pair<bodypart_id, bool>> bodyparts;
};

struct character_detail_line {
    std::string text;
    nc_color color = c_light_gray;
};

static std::string page_name( character_page page )
{
    switch( page ) {
        case character_page::overview:
            return _( "Overview" );
        case character_page::body:
            return _( "Body" );
        case character_page::skills:
            return _( "Skills" );
        case character_page::traits:
            return _( "Traits" );
        case character_page::mutations:
            return _( "Mutations" );
        case character_page::effects:
            return _( "Effects" );
        case character_page::bionics:
            return _( "Bionics" );
        case character_page::proficiencies:
            return _( "Proficiencies" );
    }
    return std::string();
}

static bool is_management_page( character_page page )
{
    return page == character_page::mutations || page == character_page::bionics;
}

static std::string bionic_sort_label( bionic_ui_sort_mode mode )
{
    switch( mode ) {
        case bionic_ui_sort_mode::POWER:
            return _( "Power usage" );
        case bionic_ui_sort_mode::NAME:
            return _( "Name" );
        case bionic_ui_sort_mode::INVLET:
            return _( "Manual (shortcut)" );
        default:
            return _( "Installation order" );
    }
}

static std::string bionic_fuel_label( float threshold )
{
    return threshold < 0 ? _( "Disabled" ) :
           string_format( _( "%d %%" ), static_cast<int>( threshold * 100 + 0.5f ) );
}

static void add_detail( std::vector<character_detail_line> &lines, const std::string &text,
                        int width, nc_color color = c_light_gray )
{
    const std::vector<std::string> folded = foldstring( text, std::max( 1, width ) );
    if( folded.empty() ) {
        lines.push_back( { "", color } );
        return;
    }
    for( const std::string &line : folded ) {
        lines.push_back( { line, color } );
    }
}

static void refresh_character_model( Character &you, character_hub_model &model )
{
    model.skills = Skill::get_skills_sorted_by( []( const Skill & lhs, const Skill & rhs ) {
        return lhs.get_sort_rank() < rhs.get_sort_rank();
    } );

    model.traits = you.get_mutations_variants( false );
    std::sort( model.traits.begin(), model.traits.end(), trait_var_display_sort );

    for( std::vector<trait_id> &rows : model.mutations ) {
        rows.clear();
    }
    for( std::pair<const trait_id, Character::trait_data> &mut : you.cached_mutations ) {
        if( mut.second.corrupted > 0 || !mut.first->player_display ) {
            continue;
        }
        if( mut.second.key == ' ' && mut.first->activated ) {
            for( const char letter : character_hub_mutation_chars ) {
                if( you.trait_by_invlet( letter ).is_null() ) {
                    mut.second.key = letter;
                    break;
                }
            }
        }
        model.mutations[mut.first->activated ? 0 : 1].push_back( mut.first );
    }
    for( std::vector<trait_id> &rows : model.mutations ) {
        std::sort( rows.begin(), rows.end(), [&]( const trait_id & lhs, const trait_id & rhs ) {
            return you.mutation_name( lhs ) < you.mutation_name( rhs );
        } );
    }

    model.effects.clear();
    for( const std::reference_wrapper<const effect> &effect_ref : you.get_effects() ) {
        const effect &cur = effect_ref.get();
        const std::string name = cur.disp_name();
        if( name.empty() ) {
            continue;
        }
        model.effects.emplace_back( name, cur.disp_desc() + '\n' + cur.disp_mod_source_info() );
    }
    if( you.get_perceived_pain() > 0 ) {
        model.effects.emplace_back(
            _( "Pain" ),
            string_format( _( "Perceived pain: %d" ), you.get_perceived_pain() ) );
    }

    model.bionics[0] = bionics_ui::sorted_bionics( *you.my_bionics, true,
                        uistate.bionic_sort_mode );
    model.bionics[1] = bionics_ui::sorted_bionics( *you.my_bionics, false,
                        uistate.bionic_sort_mode );
    model.proficiencies = you.display_proficiencies();
    model.bodyparts = list_and_combine_bps( you, nullptr );
}

static int character_move_cost( Character &you )
{
    float move_cost = 100.0f;
    you.run_cost_effects( move_cost );
    return static_cast<int>( move_cost );
}

static std::string bodypart_row_label( const Character &you,
                                       const std::pair<bodypart_id, bool> &row,
                                       int width )
{
    const bodypart_id &bp = row.first;
    const int encumbrance = you.get_part_encumbrance( bp );
    const int layer_penalty = you.get_part_layer_penalty( bp );
    const int warmth = temperature_print_rescaling( you.get_part_temp_conv( bp ) );
    const int name_width = std::max( 6, width - 17 );
    return string_format( "%s %3d+%-3d (% 3d)",
                          left_justify( body_part_name_as_heading( bp, row.second ? 2 : 1 ), name_width ),
                          encumbrance - layer_penalty, layer_penalty, warmth );
}

static trait_id selected_mutation( const character_hub_model &model, int tab, int cursor )
{
    if( tab < 0 || tab > 1 || cursor < 0 ||
        cursor >= static_cast<int>( model.mutations[tab].size() ) ) {
        return trait_id();
    }
    return model.mutations[tab][cursor];
}

static std::optional<bio_uid> selected_bionic_uid( const character_hub_model &model,
        int tab, int cursor )
{
    if( tab < 0 || tab > 1 || cursor < 0 ||
        cursor >= static_cast<int>( model.bionics[tab].size() ) ) {
        return std::nullopt;
    }
    return model.bionics[tab][cursor];
}

static bionic *find_bionic( Character &you, const std::optional<bio_uid> &uid )
{
    return uid ? you.find_bionic_by_uid( *uid ).value_or( nullptr ) : nullptr;
}

static void populate_page_list( Character &you, const character_hub_model &model,
                                character_page page, ui_selection_list &list,
                                int mutation_tab, int bionic_tab,
                                const std::optional<trait_id> &preferred_mutation,
                                const std::optional<bio_uid> &preferred_bionic )
{
    const int old_cursor = list.cursor();
    std::vector<ui_action_entry> entries;
    int preferred_index = -1;

    switch( page ) {
        case character_page::skills:
            entries.reserve( model.skills.size() );
            for( const Skill *skill : model.skills ) {
                const SkillLevel &level = you.get_skill_level_object( skill->ident() );
                entries.emplace_back(
                    string_format( "%s  %d (%d%%)", skill->name(), level.knowledgeLevel(),
                                   std::max( 0, level.knowledgeExperience() ) ),
                    skill->ident().str() );
            }
            break;

        case character_page::traits:
            entries.reserve( model.traits.size() );
            for( const trait_and_var &trait : model.traits ) {
                entries.emplace_back( trait.name(), trait.trait.str() );
            }
            break;

        case character_page::mutations: {
            const std::vector<trait_id> &rows = model.mutations[mutation_tab];
            entries.reserve( rows.size() );
            for( int i = 0; i < static_cast<int>( rows.size() ); ++i ) {
                const trait_id &id = rows[i];
                const Character::trait_data &data = you.cached_mutations.at( id );
                std::string label;
                if( id->activated ) {
                    label = string_format( "%c  %s", data.key == ' ' ? '-' : data.key,
                                           you.mutation_name( id ) );
                    label += data.powered ? _( "  · Active" ) : _( "  · Inactive" );
                } else {
                    label = you.mutation_name( id );
                }
                entries.emplace_back( std::move( label ), id.str() );
                if( preferred_mutation && *preferred_mutation == id ) {
                    preferred_index = i;
                }
            }
            break;
        }

        case character_page::effects:
            entries.reserve( model.effects.size() );
            for( size_t i = 0; i < model.effects.size(); ++i ) {
                entries.emplace_back( model.effects[i].first,
                                      string_format( "effect_%d", static_cast<int>( i ) ) );
            }
            break;

        case character_page::bionics: {
            const std::vector<bio_uid> &rows = model.bionics[bionic_tab];
            entries.reserve( rows.size() );
            for( int i = 0; i < static_cast<int>( rows.size() ); ++i ) {
                bionic *bio = find_bionic( you, rows[i] );
                if( !bio ) {
                    entries.emplace_back( _( "Missing bionic" ), std::to_string( rows[i] ) );
                    continue;
                }
                std::string label = string_format( "%c  %s", bio->invlet == ' ' ? '-' : bio->invlet,
                                                   bio->info().name.translated() );
                if( bio->incapacitated_time > 0_turns ) {
                    label += _( "  · Incapacitated" );
                } else if( bio->info().activated ) {
                    label += bio->powered ? _( "  · Active" ) : _( "  · Inactive" );
                }
                entries.emplace_back( std::move( label ), std::to_string( rows[i] ) );
                if( preferred_bionic && *preferred_bionic == rows[i] ) {
                    preferred_index = i;
                }
            }
            break;
        }

        case character_page::proficiencies:
            entries.reserve( model.proficiencies.size() );
            for( const display_proficiency &prof : model.proficiencies ) {
                const std::string label = prof.known ?
                                          prof.id->name() :
                                          string_format( "%s  %.0f%%", prof.id->name(), prof.practice * 100.0f );
                entries.emplace_back( label, prof.id.str() );
            }
            break;

        case character_page::body:
            entries.reserve( model.bodyparts.size() );
            for( size_t i = 0; i < model.bodyparts.size(); ++i ) {
                entries.emplace_back(
                    bodypart_row_label( you, model.bodyparts[i], 36 ),
                    string_format( "bodypart_%d", static_cast<int>( i ) ) );
            }
            break;

        case character_page::overview:
            break;
    }

    list.set_entries( std::move( entries ), false );
    list.hover_previews( true );
    if( list.visible_indices().empty() ) {
        list.clear_selection();
        return;
    }
    const int selected = preferred_index >= 0 ? preferred_index :
                         std::clamp( old_cursor, 0,
                                     static_cast<int>( list.visible_indices().size() ) - 1 );
    list.select_only( selected );
}

static void populate_overview_body_list( const Character &you, const character_hub_model &model,
        ui_selection_list &list, int width )
{
    std::vector<ui_action_entry> entries;
    entries.reserve( model.bodyparts.size() );
    for( size_t i = 0; i < model.bodyparts.size(); ++i ) {
        entries.emplace_back( bodypart_row_label( you, model.bodyparts[i], width ),
                              string_format( "bodypart_%d", static_cast<int>( i ) ) );
    }
    const int old_cursor = list.cursor();
    list.set_entries( std::move( entries ), false );
    list.hover_previews( true );
    if( !list.visible_indices().empty() ) {
        list.select_only( std::clamp( old_cursor, 0,
                                     static_cast<int>( list.visible_indices().size() ) - 1 ) );
    } else {
        list.clear_selection();
    }
}

static std::vector<ui_action_strip_item> navigation_entries( character_page page )
{
    std::vector<ui_action_strip_item> result;
    const auto add_page = [&]( const std::string &label, const char *id, character_page target ) {
        result.push_back( {
            ui_action_entry( label, id, true, page == target ), 0, ui_action_alignment::left
        } );
    };

    add_page( _( "Overview" ), "PAGE_OVERVIEW", character_page::overview );
    add_page( _( "Body" ), "PAGE_BODY", character_page::body );
    add_page( _( "Skills" ), "PAGE_SKILLS", character_page::skills );
    add_page( _( "Traits" ), "PAGE_TRAITS", character_page::traits );
    add_page( _( "Mutations" ), "PAGE_MUTATIONS", character_page::mutations );
    add_page( _( "Effects" ), "PAGE_EFFECTS", character_page::effects );
    add_page( _( "Bionics" ), "PAGE_BIONICS", character_page::bionics );
    add_page( _( "Proficiencies" ), "PAGE_PROFICIENCIES", character_page::proficiencies );

    ui_action_entry more( _( "More" ), "MORE" );
    more.dropdown = true;
    result.push_back( { std::move( more ), 1, ui_action_alignment::left } );
    result.push_back( {
        ui_action_entry( _( "Back" ), "BACK" ), 2, ui_action_alignment::right
    } );
    return result;
}

static std::vector<ui_action_strip_item> page_toolbar_entries( character_page page,
        const character_hub_model &model, int mutation_tab, int bionic_tab )
{
    if( page == character_page::mutations ) {
        return {
            { ui_action_entry( string_format( _( "Activatable (%d)" ), model.mutations[0].size() ),
                               "MUT_ACTIVE", true, mutation_tab == 0 ) },
            { ui_action_entry( string_format( _( "Passive (%d)" ), model.mutations[1].size() ),
                               "MUT_PASSIVE", true, mutation_tab == 1 ) }
        };
    }
    if( page == character_page::bionics ) {
        return {
            { ui_action_entry( string_format( _( "Activatable (%d)" ), model.bionics[0].size() ),
                               "BIO_ACTIVE", true, bionic_tab == 0 ) },
            { ui_action_entry( string_format( _( "Passive (%d)" ), model.bionics[1].size() ),
                               "BIO_PASSIVE", true, bionic_tab == 1 ) },
            { ui_action_entry( string_format( _( "Sort: %s" ),
                               bionic_sort_label( uistate.bionic_sort_mode ) ),
                               "BIO_SORT", true, false, std::string(), std::nullopt, true ), 1 }
        };
    }
    return {};
}

static std::vector<ui_dropdown_entry> more_entries( bool customize_character )
{
    std::vector<ui_dropdown_entry> entries;
    entries.emplace_back( _( "Morale" ), "MORALE" );
    entries.emplace_back( _( "Medical" ), "MEDICAL" );
    entries.emplace_back( _( "Change armor appearance" ), "CHANGE_ARMOR_SPRITE" );
    if( customize_character ) {
        entries.emplace_back( _( "Customize character" ), "CUSTOMIZE" );
        entries.emplace_back( _( "Change profession name" ), "CHANGE_PROFESSION" );
    }
    return entries;
}

static bool mutation_can_activate( const avatar &p, const trait_id &id )
{
    if( id.is_null() || !id->activated ) {
        return false;
    }
    if( p.cached_mutations.at( id ).powered ) {
        return true;
    }
    return ( !id->hunger || p.get_kcal_percent() >= 0.8f ) &&
           ( !id->thirst || p.get_thirst() <= 400 ) &&
           ( !id->sleepiness || p.get_sleepiness() <= 400 ) &&
           ( !id->mana || p.magic->available_mana() >= id->cost );
}

static std::string mutation_activation_failure( const avatar &p, const trait_id &id )
{
    if( id.is_null() ) {
        return _( "Select a mutation first." );
    }
    if( !id->activated ) {
        return _( "This mutation is passive." );
    }
    if( p.cached_mutations.at( id ).powered ) {
        return std::string();
    }
    if( id->hunger && p.get_kcal_percent() < 0.8f ) {
        return _( "Not enough stored calories to activate this mutation." );
    }
    if( id->thirst && p.get_thirst() > 400 ) {
        return _( "You are too thirsty to activate this mutation." );
    }
    if( id->sleepiness && p.get_sleepiness() > 400 ) {
        return _( "You are too tired to activate this mutation." );
    }
    if( id->mana && p.magic->available_mana() < id->cost ) {
        return _( "Not enough mana to activate this mutation." );
    }
    return std::string();
}

static ui_action_entry bionic_power_action( avatar &p, bionic &bio )
{
    if( !bio.info().activated ) {
        return ui_action_entry( _( "Passive" ), "BIO_POWER", false, false,
                                _( "This is a passive bionic." ) );
    }
    const ret_val<void> eligible = bio.powered ? p.can_deactivate_bionic( bio ) :
                                   p.can_activate_bionic( bio );
    return ui_action_entry( bio.powered ? _( "Deactivate" ) : _( "Activate" ),
                            "BIO_POWER", eligible.success(), bio.powered, eligible.str() );
}

static std::vector<ui_action_entry> footer_entries( Character &you,
        const character_hub_model &model, character_page page, int cursor,
        int mutation_tab, int bionic_tab, bool can_upgrade_stats )
{
    switch( page ) {
        case character_page::overview:
            if( can_upgrade_stats ) {
                return {
                    ui_action_entry( _( "Upgrade Strength" ), "UPGRADE_STAT_0" ),
                    ui_action_entry( _( "Upgrade Dexterity" ), "UPGRADE_STAT_1" ),
                    ui_action_entry( _( "Upgrade Intelligence" ), "UPGRADE_STAT_2" ),
                    ui_action_entry( _( "Upgrade Perception" ), "UPGRADE_STAT_3" )
                };
            }
            return {};
        case character_page::body:
            return { ui_action_entry( _( "Detailed body status" ), "BODY_STATUS" ) };
        case character_page::skills:
            return {};
        case character_page::traits:
            return { ui_action_entry( _( "Select variant" ), "SELECT_TRAIT_VARIANT" ) };
        case character_page::mutations: {
            avatar *p = you.as_avatar();
            const trait_id id = selected_mutation( model, mutation_tab, cursor );
            if( !p || id.is_null() ) {
                return {};
            }
            std::vector<ui_action_entry> entries;
            if( id->activated ) {
                const bool powered = p->cached_mutations.at( id ).powered;
                entries.emplace_back( powered ? _( "Deactivate" ) : _( "Activate" ), "MUT_POWER",
                                      mutation_can_activate( *p, id ), powered,
                                      mutation_activation_failure( *p, id ) );
            }
            const Character::trait_data &data = p->cached_mutations.at( id );
            entries.emplace_back( data.show_sprite ? _( "Sprite: Shown" ) : _( "Sprite: Hidden" ),
                                  "MUT_SPRITE", true, data.show_sprite );
            entries.emplace_back( string_format( _( "Shortcut: %s" ),
                                  data.key == ' ' ? _( "None" ) : std::string( 1, data.key ) ),
                                  "MUT_SHORTCUT" );
            return entries;
        }
        case character_page::effects:
            return {};
        case character_page::bionics: {
            avatar *p = you.as_avatar();
            bionic *bio = p ? find_bionic( *p, selected_bionic_uid( model, bionic_tab, cursor ) ) : nullptr;
            if( !p || !bio ) {
                return {};
            }
            std::vector<ui_action_entry> entries;
            if( bio->info().activated ) {
                entries.push_back( bionic_power_action( *p, *bio ) );
            }
            entries.emplace_back( bio->show_sprite ? _( "Sprite: Shown" ) : _( "Sprite: Hidden" ),
                                  "BIO_SPRITE", true, bio->show_sprite );
            entries.emplace_back( string_format( _( "Shortcut: %s" ),
                                  bio->invlet == ' ' ? _( "None" ) : std::string( 1, bio->invlet ) ),
                                  "BIO_SHORTCUT" );
            if( bio->supports_safe_fuel() ) {
                entries.emplace_back( string_format( _( "Fuel reserve: %s" ),
                                      bionic_fuel_label( bio->get_safe_fuel_thresh() ) ),
                                      "BIO_FUEL", true, false, std::string(), std::nullopt, true );
            }
            if( bio->can_install_weapon() || bio->has_weapon() ) {
                entries.emplace_back( bio->has_weapon() ? _( "Uninstall weapon" ) : _( "Install weapon" ),
                                      "BIO_WEAPON", !bio->powered, false,
                                      _( "Deactivate this bionic first." ) );
            }
            return entries;
        }
        case character_page::proficiencies:
            return { ui_action_entry( _( "Open proficiencies" ), "OPEN_PROFICIENCIES" ) };
    }
    return {};
}

static std::string identity_line( const Character &you )
{
    std::string role = you.disp_profession();
    if( you.custom_profession.empty() && you.crossed_threshold() ) {
        for( const trait_and_var &trait : you.get_mutations_variants() ) {
            if( trait.trait->threshold ) {
                role = trait.name();
                break;
            }
        }
    }
    if( role.empty() ) {
        return string_format( _( "%1$s | %2$s" ), you.get_name(),
                              you.male ? _( "Male" ) : _( "Female" ) );
    }
    return string_format( _( "%1$s | %2$s | %3$s" ), you.get_name(),
                          you.male ? _( "Male" ) : _( "Female" ), role );
}

static void draw_separator( const catacurses::window &win, int y, int x, int length )
{
    if( length > 0 ) {
        catacurses::mvwhline( win, point( x, y ), LINE_OXOX, length );
    }
}

static void draw_vertical_separator( const catacurses::window &win, int x, int y, int length )
{
    if( length > 0 ) {
        catacurses::mvwvline( win, point( x, y ), LINE_XOXO, length );
    }
}

static void draw_section_title( const catacurses::window &win, int x, int y, int width,
                                const std::string &title )
{
    trim_and_print( win, point( x, y ), std::max( 0, width ), c_light_green, title );
}

static void draw_key_value( const catacurses::window &win, int x, int y, int width,
                            const std::string &key, const std::string &value,
                            nc_color value_color = c_light_gray )
{
    if( width <= 2 ) {
        return;
    }
    trim_and_print( win, point( x, y ), std::max( 1, width / 2 ), c_light_gray, key );
    const int value_width = std::max( 1, width / 2 - 1 );
    right_print( win, y, getmaxx( win ) - ( x + width ), value_color,
                 trim_by_length( value, value_width ) );
}

static void draw_overview( const catacurses::window &win, Character &you,
                           const character_hub_model &model, ui_selection_list &body_list,
                           int content_top, int content_bottom )
{
    const int width = getmaxx( win );
    const int inner_left = 2;
    const int inner_right = width - 2;
    const int inner_width = std::max( 1, inner_right - inner_left );
    const int first_sep = inner_left + inner_width / 3;
    const int second_sep = inner_left + ( inner_width * 2 ) / 3;
    const int col1_x = inner_left;
    const int col2_x = first_sep + 2;
    const int col3_x = second_sep + 2;
    const int col1_w = std::max( 1, first_sep - col1_x - 1 );
    const int col2_w = std::max( 1, second_sep - col2_x - 1 );
    const int col3_w = std::max( 1, inner_right - col3_x );

    const int upper_top = content_top;
    const int upper_data = upper_top + 2;
    const int lower_sep = std::min( content_bottom - 4, upper_top + 11 );
    const int upper_height = std::max( 1, lower_sep - upper_top );

    draw_vertical_separator( win, first_sep, upper_top, upper_height );
    draw_vertical_separator( win, second_sep, upper_top, upper_height );

    draw_section_title( win, col1_x, upper_top, col1_w, _( "ATTRIBUTES / BIO" ) );
    draw_section_title( win, col2_x, upper_top, col2_w, _( "BODY" ) );
    draw_section_title( win, col3_x, upper_top, col3_w, _( "STATUS" ) );

    int row = upper_data;
    draw_key_value( win, col1_x, row++, col1_w, _( "Strength:" ),
                    string_format( "%d (%d)", you.get_str(), you.get_str_base() ),
                    you.get_str() < you.get_str_base() ? c_light_red : c_light_gray );
    draw_key_value( win, col1_x, row++, col1_w, _( "Dexterity:" ),
                    string_format( "%d (%d)", you.get_dex(), you.get_dex_base() ),
                    you.get_dex() < you.get_dex_base() ? c_light_red : c_light_gray );
    draw_key_value( win, col1_x, row++, col1_w, _( "Intelligence:" ),
                    string_format( "%d (%d)", you.get_int(), you.get_int_base() ),
                    you.get_int() < you.get_int_base() ? c_light_red : c_light_gray );
    draw_key_value( win, col1_x, row++, col1_w, _( "Perception:" ),
                    string_format( "%d (%d)", you.get_per(), you.get_per_base() ),
                    you.get_per() < you.get_per_base() ? c_light_red : c_light_gray );

    ++row;
    if( row <= lower_sep ) {
        draw_key_value( win, col1_x, row++, col1_w, _( "Weight:" ), display::weight_string( you ) );
    }
    if( row <= lower_sep ) {
        draw_key_value( win, col1_x, row++, col1_w, _( "Height:" ), you.height_string() );
    }
    if( row <= lower_sep ) {
        draw_key_value( win, col1_x, row++, col1_w, _( "Age:" ), you.age_string() );
    }
    if( row <= lower_sep ) {
        draw_key_value( win, col1_x, row, col1_w, _( "Blood type:" ),
                        io::enum_to_string( you.my_blood_type ) + ( you.blood_rh_factor ? "+" : "-" ) );
    }

    const int body_height = std::max( 0, lower_sep - upper_data );
    ui_selection_list_style body_style;
    body_style.text = c_light_gray;
    body_style.cursor = h_white;
    body_style.selected = h_white;
    body_style.allow_label_colors = false;
    body_list.draw( win, point( col2_x, upper_data ), col2_w, body_height, body_style );

    row = upper_data;
    const int speed = you.get_speed();
    const int move_cost = character_move_cost( you );
    draw_key_value( win, col3_x, row++, col3_w, _( "Speed:" ), string_format( "%d", speed ),
                    speed >= 100 ? c_light_green : c_light_red );
    draw_key_value( win, col3_x, row++, col3_w, _( "Move cost:" ), string_format( "%d", move_cost ),
                    move_cost <= 100 ? c_light_green : c_light_red );
    draw_key_value( win, col3_x, row++, col3_w, _( "Pain:" ),
                    string_format( "%d", you.get_perceived_pain() ),
                    you.get_perceived_pain() > 0 ? c_light_red : c_light_gray );
    draw_key_value( win, col3_x, row, col3_w, _( "Effects:" ),
                    string_format( "%d", static_cast<int>( model.effects.size() ) ),
                    model.effects.empty() ? c_light_gray : c_light_red );

    if( lower_sep <= upper_top || lower_sep >= content_bottom ) {
        return;
    }
    draw_separator( win, lower_sep, inner_left, inner_width );
    const int lower_top = lower_sep + 1;
    draw_section_title( win, inner_left, lower_top, inner_width, _( "ACTIVE EFFECTS" ) );
    int effect_y = lower_top + 2;
    for( const auto &entry : model.effects ) {
        if( effect_y > content_bottom ) {
            break;
        }
        trim_and_print( win, point( inner_left, effect_y++ ), inner_width, c_light_gray, entry.first );
    }
    if( model.effects.empty() && effect_y <= content_bottom ) {
        trim_and_print( win, point( inner_left, effect_y ), inner_width, c_dark_gray,
                        _( "No active effects." ) );
    }
}

static std::vector<character_detail_line> mutation_detail_lines( Character &you,
        const trait_id &id, int width )
{
    std::vector<character_detail_line> lines;
    if( id.is_null() ) {
        add_detail( lines, _( "Select a mutation to see its details." ), width );
        return lines;
    }

    avatar *p = you.as_avatar();
    const Character::trait_data &data = you.cached_mutations.at( id );
    add_detail( lines, you.mutation_name( id ), width, id->get_display_color() );
    add_detail( lines,
                id->activated ? ( data.powered ? _( "ACTIVE" ) : _( "INACTIVE" ) ) : _( "PASSIVE" ),
                width, data.powered ? c_light_green : c_light_cyan );
    if( p && id->activated ) {
        const std::string failure = mutation_activation_failure( *p, id );
        if( !failure.empty() ) {
            add_detail( lines, failure, width, c_light_red );
        }
    }

    add_detail( lines, "", width );
    if( id->activated ) {
        add_detail( lines, _( "Activation" ), width, c_light_cyan );
        std::vector<std::string> resources;
        if( id->hunger ) {
            resources.emplace_back( _( "calories" ) );
        }
        if( id->thirst ) {
            resources.emplace_back( _( "thirst" ) );
        }
        if( id->sleepiness ) {
            resources.emplace_back( _( "sleepiness" ) );
        }
        if( id->mana ) {
            resources.emplace_back( _( "mana" ) );
        }
        if( id->cost > 0 && !resources.empty() ) {
            add_detail( lines, string_format( _( "Cost: %d %s" ), id->cost,
                        enumerate_as_string( resources, enumeration_conjunction::none ) ), width );
        } else if( id->cost > 0 ) {
            add_detail( lines, string_format( _( "Cost: %d" ), id->cost ), width );
        } else {
            add_detail( lines, _( "No activation cost." ), width );
        }
        if( id->cooldown > 0_turns ) {
            add_detail( lines, string_format( _( "Cooldown: %s" ),
                                              to_string_clipped( id->cooldown ) ), width );
        }
        add_detail( lines, "", width );
    }

    add_detail( lines, you.mutation_desc( id ), width, c_light_blue );
    if( !you.purifiable( id ) ) {
        add_detail( lines, "", width );
        add_detail( lines, _( "This trait is intrinsic and cannot be removed by purifier." ),
                    width, c_yellow );
    }
    add_detail( lines, "", width );
    add_detail( lines, _( "Settings" ), width, c_light_cyan );
    add_detail( lines, string_format( _( "Shortcut: %s" ),
                                      data.key == ' ' ? _( "None" ) : std::string( 1, data.key ) ), width );
    add_detail( lines, data.show_sprite ? _( "Sprite: Shown" ) : _( "Sprite: Hidden" ), width );
    return lines;
}

static std::vector<character_detail_line> bionic_detail_lines( Character &you, bionic *bio,
        int width )
{
    std::vector<character_detail_line> lines;
    avatar *p = you.as_avatar();
    if( !bio ) {
        add_detail( lines, _( "Select a bionic to see its details." ), width );
        return lines;
    }

    const bionic_data &data = bio->info();
    add_detail( lines, data.name.translated(), width, c_white );
    add_detail( lines,
                bio->incapacitated_time > 0_turns ? _( "INCAPACITATED" ) :
                !data.activated ? _( "PASSIVE" ) : bio->powered ? _( "ACTIVE" ) : _( "INACTIVE" ),
                width,
                bio->incapacitated_time > 0_turns ? c_light_red :
                bio->powered ? c_light_green : c_light_cyan );
    if( p && data.activated ) {
        const ui_action_entry action = bionic_power_action( *p, *bio );
        if( !action.enabled ) {
            add_detail( lines, action.disabled_reason, width, c_light_red );
        }
    }

    add_detail( lines, "", width );
    add_detail( lines, _( "Power" ), width, c_light_cyan );
    if( data.power_activate > 0_J ) {
        add_detail( lines, string_format( _( "Activation: %s" ),
                                          units::display( data.power_activate ) ), width );
    }
    if( data.has_flag( json_flag_BIONIC_GUN ) && bio->has_weapon() ) {
        add_detail( lines, string_format( _( "Firing: %s" ),
                                          units::display( bio->get_weapon().get_gun_bionic_drain() ) ), width );
    }
    if( data.power_deactivate > 0_J ) {
        add_detail( lines, string_format( _( "Deactivation: %s" ),
                                          units::display( data.power_deactivate ) ), width );
    }
    if( data.power_trigger > 0_J ) {
        add_detail( lines, string_format( _( "Trigger: %s" ),
                                          units::display( data.power_trigger ) ), width );
    }
    if( data.charge_time > 0_turns && data.power_over_time > 0_J ) {
        add_detail( lines, data.charge_time == 1_turns ?
                    string_format( _( "Running: %s / turn" ), units::display( data.power_over_time ) ) :
                    string_format( _( "Running: %s / %d turns" ), units::display( data.power_over_time ),
                                   to_turns<int>( data.charge_time ) ), width );
    }
    if( data.power_activate == 0_J && data.power_over_time == 0_J && data.power_trigger == 0_J &&
        data.power_deactivate == 0_J && !data.has_flag( json_flag_BIONIC_GUN ) ) {
        add_detail( lines, _( "No power cost." ), width );
    }
    if( p && bio->is_safe_fuel_on() && bio->powered &&
        bio->get_safe_fuel_thresh() * p->get_max_power_level() - 1_kJ <= p->get_power_level() ) {
        add_detail( lines, _( "Fuel saving: generation paused at the reserve threshold." ),
                    width, c_yellow );
    }

    add_detail( lines, "", width );
    add_detail( lines, data.description.translated(), width, c_light_blue );
    if( bio->has_weapon() ) {
        add_detail( lines, string_format( _( "Installed weapon: %s" ), bio->get_weapon().tname() ), width );
    }

    add_detail( lines, "", width );
    add_detail( lines, _( "Settings" ), width, c_light_cyan );
    add_detail( lines, string_format( _( "Shortcut: %s" ),
                                      bio->invlet == ' ' ? _( "None" ) : std::string( 1, bio->invlet ) ), width );
    add_detail( lines, bio->show_sprite ? _( "Sprite: Shown" ) : _( "Sprite: Hidden" ), width );
    if( bio->supports_safe_fuel() ) {
        add_detail( lines, string_format( _( "Fuel reserve: %s" ),
                                          bionic_fuel_label( bio->get_safe_fuel_thresh() ) ), width );
    }

    if( p && get_option<bool>( "CBM_SLOTS_ENABLED" ) ) {
        add_detail( lines, "", width );
        add_detail( lines, _( "Body slots" ), width, c_light_cyan );
        if( data.occupied_bodyparts.empty() ) {
            add_detail( lines, _( "No body slots occupied." ), width );
        }
        for( const auto &part : data.occupied_bodyparts ) {
            const bodypart_id bp = part.first.id();
            const int total = p->get_total_bionics_slots( bp );
            add_detail( lines, string_format( _( "%s: this CBM %d; total %d / %d" ),
                                              body_part_name_as_heading( bp, 1 ), part.second,
                                              total - p->get_free_bionics_slots( bp ), total ), width );
        }
    }
    return lines;
}

static std::string bionic_global_status( Character &you )
{
    avatar *p = you.as_avatar();
    std::string result = string_format( _( "Power %s / %s" ), units::display( you.get_power_level() ),
                                        units::display( you.get_max_power_level() ) );
    if( !p ) {
        return result;
    }

    std::vector<std::string> fuel;
    std::set<const item *> seen;
    const auto append = [&]( const item * source ) {
        if( !source || !seen.insert( source ).second ) {
            return;
        }
        const item *content = nullptr;
        if( source->ammo_remaining() > 0 ) {
            content = &source->first_ammo();
        } else {
            const auto contents = source->all_items_top();
            if( !contents.empty() ) {
                content = contents.front();
            }
        }
        if( content ) {
            fuel.push_back( string_format( "%s: %d", content->tname(), content->charges ) );
        }
    };

    for( const bionic &bio : *p->my_bionics ) {
        for( const item *source : p->get_bionic_fuels( bio.id ) ) {
            append( source );
        }
    }
    for( const item *ups : p->get_cable_ups() ) {
        append( ups );
    }
    for( vehicle *veh : p->get_cable_vehicle() ) {
        const int64_t charges = veh->connected_battery_power_level( get_map() ).first;
        if( charges > 0 ) {
            fuel.push_back( string_format( "%s: %d", item( character_hub_battery ).tname(), charges ) );
        }
    }
    if( !fuel.empty() ) {
        result += "   " + string_format( _( "Fuel: %s" ),
                                         enumerate_as_string( fuel, enumeration_conjunction::none ) );
    }
    return result;
}

static void draw_page_detail( const catacurses::window &win, Character &you,
                              const character_hub_model &model, character_page page,
                              int selected, int mutation_tab, int bionic_tab,
                              int x, int y, int width, int height )
{
    if( width <= 2 || height <= 0 ) {
        return;
    }

    draw_section_title( win, x, y, width, _( "DETAILS" ) );
    const int text_y = y + 2;
    const int text_height = std::max( 0, height - 2 );
    if( text_height <= 0 ) {
        return;
    }

    switch( page ) {
        case character_page::skills:
            if( selected >= 0 && selected < static_cast<int>( model.skills.size() ) ) {
                const Skill *skill = model.skills[selected];
                const SkillLevel &level = you.get_skill_level_object( skill->ident() );
                trim_and_print( win, point( x, text_y ), width, c_light_green, skill->name() );
                trim_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                string_format( _( "Practical level: %d (%d%%)" ),
                                               level.level(), std::max( 0, level.exercise() ) ) );
                trim_and_print( win, point( x, text_y + 3 ), width, c_light_gray,
                                string_format( _( "Knowledge level: %d (%d%%)" ),
                                               level.knowledgeLevel(),
                                               std::max( 0, level.knowledgeExperience() ) ) );
                if( text_height > 6 ) {
                    fold_and_print( win, point( x, text_y + 5 ), width, c_light_gray,
                                    skill->description() );
                }
            }
            break;
        case character_page::traits:
            if( selected >= 0 && selected < static_cast<int>( model.traits.size() ) ) {
                const trait_and_var &trait = model.traits[selected];
                trim_and_print( win, point( x, text_y ), width,
                                trait.trait->get_display_color(), trait.name() );
                if( text_height > 3 ) {
                    fold_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                    you.mutation_desc( trait.trait ) );
                }
            }
            break;
        case character_page::mutations:
            break;
        case character_page::effects:
            if( selected >= 0 && selected < static_cast<int>( model.effects.size() ) ) {
                trim_and_print( win, point( x, text_y ), width, c_light_green,
                                model.effects[selected].first );
                if( text_height > 3 ) {
                    fold_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                    model.effects[selected].second );
                }
            }
            break;
        case character_page::bionics:
            break;
        case character_page::proficiencies:
            if( selected >= 0 && selected < static_cast<int>( model.proficiencies.size() ) ) {
                const display_proficiency &prof = model.proficiencies[selected];
                trim_and_print( win, point( x, text_y ), width, prof.color, prof.id->name() );
                trim_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                prof.known ? _( "Known" ) :
                                string_format( _( "Learning progress: %.2f%%" ),
                                               prof.practice * 100.0f ) );
                if( text_height > 5 ) {
                    fold_and_print( win, point( x, text_y + 4 ), width, c_light_gray,
                                    prof.id->description() );
                }
            }
            break;
        case character_page::body:
            if( selected >= 0 && selected < static_cast<int>( model.bodyparts.size() ) ) {
                const bodypart_id &bp = model.bodyparts[selected].first;
                const int encumbrance = you.get_part_encumbrance( bp );
                const int layer_penalty = you.get_part_layer_penalty( bp );
                trim_and_print( win, point( x, text_y ), width, c_light_green,
                                body_part_name_as_heading( bp, model.bodyparts[selected].second ? 2 : 1 ) );
                trim_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                string_format( _( "Encumbrance: %d + %d layering" ),
                                               encumbrance - layer_penalty, layer_penalty ) );
                trim_and_print( win, point( x, text_y + 3 ), width,
                                display::bodytemp_color( you, bp ),
                                string_format( _( "Warmth: %d" ),
                                               temperature_print_rescaling( you.get_part_temp_conv( bp ) ) ) );
                if( text_height > 6 ) {
                    fold_and_print( win, point( x, text_y + 5 ), width, c_dark_gray,
                                    _( "Open Detailed body status for wounds, hit points, treatment and other body-part details." ) );
                }
            }
            break;
        case character_page::overview:
            break;
    }
}

static void draw_list_page( const catacurses::window &win, Character &you,
                            const character_hub_model &model, character_page page,
                            ui_selection_list &list, ui_action_strip &page_toolbar,
                            int mutation_tab, int bionic_tab,
                            int content_top, int content_bottom )
{
    page_toolbar.clear();
    const int width = getmaxx( win );
    const int top = content_top;
    if( top > content_bottom ) {
        return;
    }
    const int split = std::clamp( width * 2 / 5, 28, std::max( 29, width - 34 ) );
    const int list_x = 2;
    const int list_width = std::max( 1, split - list_x - 1 );
    const int detail_x = split + 2;
    const int detail_width = std::max( 1, width - detail_x - 2 );
    const int list_y = top + 2;
    const int list_height = std::max( 0, content_bottom - list_y + 1 );

    draw_vertical_separator( win, split, top, std::max( 0, content_bottom - top + 1 ) );
    draw_section_title( win, list_x, top, list_width, page_name( page ) );

    ui_selection_list_style list_style;
    list_style.text = c_light_gray;
    list_style.cursor = h_white;
    list_style.selected = h_white;
    list_style.allow_label_colors = true;
    list.draw( win, point( list_x, list_y ), list_width, list_height, list_style );

    draw_page_detail( win, you, model, page, list.cursor(), mutation_tab, bionic_tab,
                      detail_x, top, detail_width, content_bottom - top + 1 );
}

static void draw_management_page( const catacurses::window &win, Character &you,
                                  const character_hub_model &model, character_page page,
                                  ui_selection_list &list, ui_action_strip &page_toolbar,
                                  ui_scroll_view &detail_scroll, ui_action_strip &management_actions,
                                  int mutation_tab, int bionic_tab,
                                  int content_top, int content_bottom )
{
    const int width = getmaxx( win );
    int top = content_top;
    page_toolbar.configure( win, point( 2, top ),
                            page_toolbar_entries( page, model, mutation_tab, bionic_tab ),
                            std::max( 0, width - 4 ), 2 );
    page_toolbar.draw( win );
    top += page_toolbar.rows_used() + 1;

    if( page == character_page::bionics && top <= content_bottom ) {
        trim_and_print( win, point( 2, top ), std::max( 1, width - 4 ), c_light_gray,
                        bionic_global_status( you ) );
        top += 2;
    }
    if( top > content_bottom ) {
        management_actions.clear();
        detail_scroll.hide();
        return;
    }

    // Management pages deliberately use their own layout.  The hub is the shell;
    // these pages retain the dense list/inspector structure of their former windows.
    const int split = std::clamp( width * 52 / 100, 44, std::max( 45, width - 48 ) );
    const int list_x = 2;
    const int list_width = std::max( 1, split - list_x - 1 );
    const int detail_x = split + 2;
    const int detail_width = std::max( 1, width - detail_x - 2 );
    draw_vertical_separator( win, split, top, std::max( 0, content_bottom - top + 1 ) );

    const std::string list_title = page == character_page::mutations ?
                                   ( mutation_tab == 0 ? _( "ACTIVATABLE MUTATIONS" ) : _( "PASSIVE MUTATIONS" ) ) :
                                   ( bionic_tab == 0 ? _( "ACTIVATABLE BIONICS" ) : _( "PASSIVE BIONICS" ) );
    draw_section_title( win, list_x, top, list_width, list_title );
    draw_section_title( win, detail_x, top, detail_width, _( "DETAILS" ) );

    const int list_y = top + 2;
    const int list_height = std::max( 0, content_bottom - list_y + 1 );
    ui_selection_list_style list_style;
    list_style.text = c_light_gray;
    list_style.cursor = h_white;
    list_style.selected = h_white;
    list_style.allow_label_colors = true;
    list.draw( win, point( list_x, list_y ), list_width, list_height, list_style );
    if( list.visible_indices().empty() ) {
        trim_and_print( win, point( list_x, list_y ), std::max( 1, list_width - 1 ), c_dark_gray,
                        page == character_page::mutations ?
                        ( mutation_tab == 0 ? _( "No activatable mutations." ) : _( "No passive mutations." ) ) :
                        ( bionic_tab == 0 ? _( "No activatable bionics installed." ) :
                          _( "No passive bionics installed." ) ) );
    }

    std::vector<character_detail_line> lines;
    if( page == character_page::mutations ) {
        lines = mutation_detail_lines( you, selected_mutation( model, mutation_tab, list.cursor() ),
                                       std::max( 1, detail_width - 1 ) );
    } else {
        lines = bionic_detail_lines( you,
                                     find_bionic( you, selected_bionic_uid( model, bionic_tab, list.cursor() ) ),
                                     std::max( 1, detail_width - 1 ) );
    }

    const std::vector<ui_action_entry> actions = footer_entries(
                you, model, page, list.cursor(), mutation_tab, bionic_tab, false );
    const int action_top = std::max( top + 2, content_bottom - 1 );
    management_actions.configure( win, point( detail_x, action_top ), actions,
                                  detail_width, 2 );
    if( action_top > top + 2 ) {
        draw_separator( win, action_top - 1, detail_x, detail_width );
    }
    management_actions.draw( win );

    const int detail_y = top + 2;
    const int detail_height = std::max( 0, action_top - detail_y - 1 );
    detail_scroll.configure( point( detail_x, detail_y ), detail_width, detail_height,
                             static_cast<int>( lines.size() ) );
    for( int i = 0; i < static_cast<int>( lines.size() ); ++i ) {
        if( const std::optional<point> pos = detail_scroll.position( i ) ) {
            trim_and_print( win, *pos, std::max( 1, detail_width - 1 ),
                            lines[i].color, lines[i].text );
        }
    }
    detail_scroll.draw_scrollbar( win );
}

static void change_armor_sprite( Character &you )
{
    item_location target_loc = game_menus::inv::change_sprite( you );
    if( !target_loc || !target_loc.get_item() ) {
        return;
    }

    item *target_item = target_loc.get_item();
    uilist menu;
    menu.title = _( "Change sprite" );
    menu.addentry( 0, true, MENU_AUTOASSIGN, _( "Select sprite from items" ) );
    menu.addentry( 1, true, MENU_AUTOASSIGN, _( "Restore default sprite" ) );
    menu.addentry( 2, true, MENU_AUTOASSIGN, _( "Cancel" ) );
    menu.query();

    if( menu.ret == 0 ) {
        const auto armor_filter = []( const item & candidate ) {
            return candidate.is_armor();
        };
        item_location sprite_loc = game_menus::inv::titled_filter_menu(
                                       armor_filter, you, _( "Select appearance of this armor:" ), -1,
                                       _( "You have nothing to wear." ) );
        if( sprite_loc && sprite_loc.get_item() ) {
            const item *sprite_item = sprite_loc.get_item();
            const std::string variant = sprite_item->has_itype_variant() ?
                                        sprite_item->itype_variant().id : "";
            target_item->set_var( "sprite_override", sprite_item->typeId().str() );
            target_item->set_var( "sprite_override_variant", variant );
        }
    } else if( menu.ret == 1 ) {
        target_item->erase_var( "sprite_override" );
        target_item->erase_var( "sprite_override_variant" );
    }
}

static void customize_character_dialog( Character &you )
{
    uilist menu;
    menu.title = _( "Customize Character" );
    menu.addentry( 1, true, 'g', _( "Change gender" ) );
    menu.addentry( 2, true, 'n', _( "Change name" ) );
    menu.query();

    if( menu.ret == 1 ) {
        you.male = !you.male;
    } else if( menu.ret == 2 ) {
        std::string name = you.play_name.value_or( std::string() );
        string_input_popup popup;
        popup.title( _( "New name (leave empty to reset):" ) )
        .width( 85 )
        .edit( name );
        if( popup.confirmed() ) {
            if( name.empty() ) {
                you.play_name.reset();
            } else {
                you.play_name = name;
            }
        }
    }
}

static void change_profession_name( Character &you )
{
    string_input_popup popup;
    popup.title( _( "Profession Name:" ) )
    .width( 25 )
    .text( you.custom_profession )
    .max_length( 25 )
    .query();
    if( popup.confirmed() ) {
        you.custom_profession = popup.text();
    }
}

static std::string page_help( character_page page )
{
    switch( page ) {
        case character_page::overview:
            return _( "Overview | General character values and current physical condition" );
        case character_page::body:
            return _( "Body | Encumbrance and warmth by body part" );
        case character_page::skills:
            return _( "Skills | Select a skill to inspect practical and knowledge progress" );
        case character_page::traits:
            return _( "Traits | Select a trait to inspect its effects" );
        case character_page::mutations:
            return _( "Mutations | Full mutation management; scroll the inspector for complete details" );
        case character_page::effects:
            return _( "Effects | Select an active effect to inspect it" );
        case character_page::bionics:
            return _( "Bionics | Full CBM management; scroll the inspector for power, settings and slot details" );
        case character_page::proficiencies:
            return _( "Proficiencies | Select a proficiency for details" );
    }
    return std::string();
}

static void assign_mutation_shortcut( avatar &p, const trait_id &id, int key )
{
    if( id.is_null() ) {
        return;
    }
    if( key == ' ' ) {
        p.cached_mutations[id].key = ' ';
        return;
    }
    const trait_id other = p.trait_by_invlet( key );
    if( !other.is_null() && other != id ) {
        std::swap( p.cached_mutations[id].key, p.cached_mutations[other].key );
    } else {
        p.cached_mutations[id].key = static_cast<char>( key );
    }
}

} // namespace

void Character::disp_info( bool customize_character )
{
    customize_character |= debug_mode;

    character_hub_model model;
    refresh_character_model( *this, model );

    character_page page = pending_character_page.value_or( character_page::overview );
    pending_character_page.reset();
    int mutation_tab = 0;
    int bionic_tab = 0;
    if( page == character_page::mutations && model.mutations[0].empty() && !model.mutations[1].empty() ) {
        mutation_tab = 1;
    }
    if( page == character_page::bionics && model.bionics[0].empty() && !model.bionics[1].empty() ) {
        bionic_tab = 1;
    }

    std::array<std::optional<trait_id>, 2> mutation_selection;
    std::array<std::optional<bio_uid>, 2> bionic_selection;
    ui_selection_list page_list;
    ui_selection_list overview_body_list;
    ui_action_strip navigation;
    ui_action_strip page_toolbar;
    ui_action_strip footer;
    ui_action_strip management_actions;
    ui_scroll_view detail_scroll;
    ui_dropdown more_menu;
    ui_dropdown page_menu;
    ui_key_field shortcut;
    std::optional<inclusive_rectangle<point>> more_trigger;
    std::optional<inclusive_rectangle<point>> page_menu_trigger;
    std::optional<bio_uid> page_menu_bionic;
    std::string page_menu_kind;
    std::string status;

    catacurses::window window;
    ui_adaptor ui;
    bool hidden = false;
    bool done = false;

    const auto close_page_menu = [&]() {
        page_menu.close();
        page_menu_trigger.reset();
        page_menu_bionic.reset();
        page_menu_kind.clear();
    };

    const auto sync_selection = [&]() {
        if( page == character_page::mutations ) {
            const trait_id id = selected_mutation( model, mutation_tab, page_list.cursor() );
            mutation_selection[mutation_tab] = id.is_null() ? std::nullopt : std::optional<trait_id>( id );
        } else if( page == character_page::bionics ) {
            bionic_selection[bionic_tab] = selected_bionic_uid( model, bionic_tab, page_list.cursor() );
        }
    };

    const auto rebuild_lists = [&]() {
        refresh_character_model( *this, model );
        if( page == character_page::mutations && model.mutations[mutation_tab].empty() &&
            !model.mutations[1 - mutation_tab].empty() ) {
            mutation_tab = 1 - mutation_tab;
        }
        if( page == character_page::bionics && model.bionics[bionic_tab].empty() &&
            !model.bionics[1 - bionic_tab].empty() ) {
            bionic_tab = 1 - bionic_tab;
        }
        populate_page_list( *this, model, page, page_list, mutation_tab, bionic_tab,
                            mutation_selection[mutation_tab], bionic_selection[bionic_tab] );
        sync_selection();
        if( window ) {
            const int width = getmaxx( window );
            const int inner_width = std::max( 1, width - 4 );
            const int col_width = std::max( 1, inner_width / 3 - 3 );
            populate_overview_body_list( *this, model, overview_body_list, col_width );
        }
    };

    const auto set_page = [&]( character_page next ) {
        sync_selection();
        page = next;
        status.clear();
        shortcut.cancel();
        detail_scroll.model().scroll_to_start();
        management_actions.clear();
        more_menu.close();
        close_page_menu();
        refresh_character_model( *this, model );
        if( page == character_page::mutations && model.mutations[mutation_tab].empty() &&
            !model.mutations[1 - mutation_tab].empty() ) {
            mutation_tab = 1 - mutation_tab;
        }
        if( page == character_page::bionics && model.bionics[bionic_tab].empty() &&
            !model.bionics[1 - bionic_tab].empty() ) {
            bionic_tab = 1 - bionic_tab;
        }
        populate_page_list( *this, model, page, page_list, mutation_tab, bionic_tab,
                            mutation_selection[mutation_tab], bionic_selection[bionic_tab] );
        sync_selection();
        ui.invalidate_ui();
    };

    ui.on_screen_resize( [&]( ui_adaptor & adaptor ) {
        page_list.invalidate_geometry();
        overview_body_list.invalidate_geometry();
        page_toolbar.clear();
        footer.clear();
        management_actions.clear();
        detail_scroll.hide();
        more_menu.close();
        close_page_menu();
        if( hidden ) {
            adaptor.position( point::zero, point::zero );
            return;
        }
        const int width = std::min( TERMX, std::max( 76, TERMX * 4 / 5 ) );
        const int height = std::min( TERMY, std::max( 22, TERMY * 4 / 5 ) );
        window = catacurses::newwin( height, width,
                                     point( ( TERMX - width ) / 2, ( TERMY - height ) / 2 ) );
        adaptor.position_from_window( window );
        rebuild_lists();
    } );
    ui.mark_resize();

    ui.on_redraw( [&]( ui_adaptor & adaptor ) {
        adaptor.disable_cursor();
        if( hidden || !window ) {
            return;
        }
        werase( window );

        const int width = getmaxx( window );
        const int height = getmaxy( window );
        if( width < 4 || height < 10 ) {
            wnoutrefresh( window );
            return;
        }

        draw_border( window, c_light_gray );
        center_print( window, 0, c_light_green, _( "CHARACTER" ) );

        navigation.configure( window, point( 2, 1 ), navigation_entries( page ),
                              std::max( 0, width - 4 ), 3 );
        navigation.draw( window );
        more_trigger = navigation.bounds_for_id( "MORE" );
        const int nav_bottom = 1 + navigation.rows_used();
        draw_separator( window, nav_bottom, 1, width - 2 );
        const int identity_y = nav_bottom + 1;
        trim_and_print( window, point( 2, identity_y ), std::max( 1, width - 4 ), c_light_gray,
                        identity_line( *this ) );

        const bool management_page = is_management_page( page );
        const bool can_upgrade_stats = get_option<bool>( "STATS_THROUGH_KILLS" ) && is_avatar();
        const int footer_sep = management_page ? height - 3 : height - 5;
        const int footer_top = height - 4;
        const int content_top = identity_y + 1;
        const int content_bottom = footer_sep - 1;

        if( page == character_page::overview ) {
            const int inner_width = std::max( 1, width - 4 );
            const int col_width = std::max( 1, inner_width / 3 - 3 );
            if( overview_body_list.visible_indices().size() != model.bodyparts.size() ) {
                populate_overview_body_list( *this, model, overview_body_list, col_width );
            }
            page_toolbar.clear();
            management_actions.clear();
            detail_scroll.hide();
            draw_overview( window, *this, model, overview_body_list, content_top, content_bottom );
        } else if( management_page ) {
            footer.clear();
            draw_management_page( window, *this, model, page, page_list, page_toolbar,
                                  detail_scroll, management_actions, mutation_tab, bionic_tab,
                                  content_top, content_bottom );
        } else {
            management_actions.clear();
            detail_scroll.hide();
            draw_list_page( window, *this, model, page, page_list, page_toolbar,
                            mutation_tab, bionic_tab, content_top, content_bottom );
        }

        draw_separator( window, footer_sep, 1, width - 2 );
        if( !management_page ) {
            const std::vector<ui_action_entry> footer_actions = footer_entries(
                        *this, model, page, page_list.cursor(), mutation_tab, bionic_tab, can_upgrade_stats );
            footer.configure( window, point( 2, footer_top ), footer_actions,
                              std::max( 0, width - 4 ), 2 );
            footer.draw( window );
        }

        const std::string hint = shortcut.armed() ?
                                 _( "Press a shortcut; Space clears, Esc cancels." ) :
                                 !status.empty() ? status : page_help( page );
        trim_and_print( window, point( 2, height - 2 ), std::max( 1, width - 4 ),
                        shortcut.armed() ? c_yellow : status.empty() ? c_dark_gray : c_light_gray,
                        string_format( _( "Selection: %s" ), hint ) );

        wnoutrefresh( window );
        more_menu.draw( window );
        page_menu.draw( window );
    } );

    input_context ctxt( "PLAYER_INFO" );
    ctxt.register_navigate_ui_list();
    ctxt.register_action( "COORDINATE" );
    ctxt.register_action( "SELECT" );
    ctxt.register_action( "MOUSE_MOVE" );
    ctxt.register_action( "LEFT", to_translation( "Previous character page" ) );
    ctxt.register_action( "RIGHT", to_translation( "Next character page" ) );
    ctxt.register_action( "NEXT_TAB", to_translation( "Next character page" ) );
    ctxt.register_action( "PREV_TAB", to_translation( "Previous character page" ) );
    ctxt.register_action( "QUIT" );
    ctxt.register_action( "CONFIRM" );
    ctxt.register_action( "HELP_KEYBINDINGS" );
    ctxt.register_action( "VIEW_PROFICIENCIES", to_translation( "View character proficiencies" ) );
    ctxt.register_action( "VIEW_BODYSTAT", to_translation( "View character's body status" ) );
    ctxt.register_action( "morale" );
    ctxt.register_action( "MEDICAL_MENU" );
    ctxt.register_action( "SWITCH_GENDER", to_translation( "Customize base appearance and name" ) );
    ctxt.register_action( "CHANGE_PROFESSION_NAME", to_translation( "Change profession name" ) );
    ctxt.register_action( "CHANGE_ARMOR_SPRITE" );
    ctxt.register_action( "SELECT_TRAIT_VARIANT" );
    ctxt.register_action( "REASSIGN" );
    ctxt.register_action( "TOGGLE_SPRITE" );
    ctxt.register_action( "TOGGLE_SAFE_FUEL" );
    ctxt.register_action( "SORT" );
    ctxt.register_action( "BIONICS_WEAPON" );
    ctxt.register_action( "SELECT_STATS_TAB" );
    ctxt.register_action( "SELECT_ENCUMBRANCE_TAB" );
    ctxt.register_action( "SELECT_SKILLS_TAB" );
    ctxt.register_action( "SELECT_TRAITS_TAB" );
    ctxt.register_action( "SELECT_BIONICS_TAB" );
    ctxt.register_action( "SELECT_EFFECTS_TAB" );
    ctxt.register_action( "SELECT_PROFICIENCIES_TAB" );

    const auto run_external_action = [&]( const std::string &id ) {
        if( id == "BODY_STATUS" ) {
            display_bodygraph( *this );
        } else if( id == "MORALE" ) {
            disp_morale();
        } else if( id == "MEDICAL" ) {
            disp_medical();
        } else if( id == "OPEN_PROFICIENCIES" ) {
            show_proficiencies_window( *this );
        } else if( id == "CUSTOMIZE" && customize_character ) {
            customize_character_dialog( *this );
        } else if( id == "CHANGE_PROFESSION" && customize_character ) {
            change_profession_name( *this );
        } else if( id == "CHANGE_ARMOR_SPRITE" ) {
            change_armor_sprite( *this );
        } else if( id == "SELECT_TRAIT_VARIANT" && page == character_page::traits ) {
            const int selected = page_list.cursor();
            if( selected >= 0 && selected < static_cast<int>( model.traits.size() ) ) {
                const mutation_variant *variant = model.traits[selected].trait->pick_variant_menu();
                set_mut_variant( model.traits[selected].trait, variant );
            }
        } else if( id.size() == 14 && id.rfind( "UPGRADE_STAT_", 0 ) == 0 &&
                   get_option<bool>( "STATS_THROUGH_KILLS" ) && is_avatar() ) {
            const int stat = id.back() - '0';
            if( stat >= 0 && stat < 4 ) {
                as_avatar()->upgrade_stat_prompt( static_cast<character_stat>( stat ) );
            }
        }
        rebuild_lists();
        ui.invalidate_ui();
    };

    const auto handle_page_action = [&]( const std::string &id ) -> bool {
        if( id == "PAGE_OVERVIEW" ) {
            set_page( character_page::overview );
        } else if( id == "PAGE_BODY" ) {
            set_page( character_page::body );
        } else if( id == "PAGE_SKILLS" ) {
            set_page( character_page::skills );
        } else if( id == "PAGE_TRAITS" ) {
            set_page( character_page::traits );
        } else if( id == "PAGE_MUTATIONS" ) {
            set_page( character_page::mutations );
        } else if( id == "PAGE_EFFECTS" ) {
            set_page( character_page::effects );
        } else if( id == "PAGE_BIONICS" ) {
            set_page( character_page::bionics );
        } else if( id == "PAGE_PROFICIENCIES" ) {
            set_page( character_page::proficiencies );
        } else {
            return false;
        }
        return true;
    };

    const auto open_bionic_sort = [&]() {
        std::vector<ui_dropdown_entry> choices;
        const std::array<bionic_ui_sort_mode, 4> modes = {
            bionic_ui_sort_mode::POWER, bionic_ui_sort_mode::NAME,
            bionic_ui_sort_mode::INVLET, bionic_ui_sort_mode::NONE
        };
        for( const bionic_ui_sort_mode mode : modes ) {
            const std::string id = mode == bionic_ui_sort_mode::POWER ? "power" :
                                   mode == bionic_ui_sort_mode::NAME ? "name" :
                                   mode == bionic_ui_sort_mode::INVLET ? "invlet" : "none";
            choices.emplace_back( bionic_sort_label( mode ), id, true,
                                  uistate.bionic_sort_mode == mode );
        }
        page_menu_kind = "BIO_SORT";
        page_menu_trigger = page_toolbar.bounds_for_id( "BIO_SORT" );
        const point anchor = page_menu_trigger ?
                             point( page_menu_trigger->p_min.x, page_menu_trigger->p_max.y + 1 ) : point( 2, 5 );
        page_menu.configure( window, anchor, std::move( choices ) );
        page_menu.focus_selected();
    };

    const auto open_bionic_fuel = [&]( bio_uid uid ) {
        bionic *bio = find_bionic( *this, uid );
        if( !bio || !bio->supports_safe_fuel() ) {
            return;
        }
        std::vector<ui_dropdown_entry> choices;
        for( int i = 0; i < static_cast<int>( bionics_ui::fuel_thresholds.size() ); ++i ) {
            const float value = bionics_ui::fuel_thresholds[i];
            choices.emplace_back( bionic_fuel_label( value ), std::to_string( i ), true,
                                  bio->get_safe_fuel_thresh() == value );
        }
        page_menu_kind = "BIO_FUEL";
        page_menu_bionic = uid;
        page_menu_trigger = management_actions.bounds_for_id( "BIO_FUEL" );
        const point anchor = page_menu_trigger ?
                             point( page_menu_trigger->p_min.x, page_menu_trigger->p_max.y + 1 ) : point( 2, 5 );
        page_menu.configure( window, anchor, std::move( choices ) );
        page_menu.focus_selected();
    };

    const auto run_mutation_action = [&]( const std::string &id ) {
        avatar *p = as_avatar();
        const trait_id mut = selected_mutation( model, mutation_tab, page_list.cursor() );
        if( !p || mut.is_null() ) {
            status = _( "Select a mutation first." );
            return;
        }
        mutation_selection[mutation_tab] = mut;
        if( id == "MUT_POWER" ) {
            Character::trait_data &data = p->cached_mutations[mut];
            if( data.powered ) {
                p->add_msg_if_player( m_neutral, _( "You stop using your %s." ), p->mutation_name( mut ) );
                p->deactivate_mutation( mut );
            } else if( mutation_can_activate( *p, mut ) ) {
                p->add_msg_if_player( m_neutral,
                                      string_format( mut->activation_msg, p->mutation_name( mut ) ) );
                p->activate_mutation( mut );
            } else {
                status = mutation_activation_failure( *p, mut );
                return;
            }
            g->invalidate_main_ui_adaptor();
        } else if( id == "MUT_SPRITE" ) {
            p->cached_mutations[mut].show_sprite = !p->cached_mutations[mut].show_sprite;
            g->invalidate_main_ui_adaptor();
        } else if( id == "MUT_SHORTCUT" ) {
            shortcut.arm();
            status.clear();
            ui.invalidate_ui();
            return;
        }
        status.clear();
        rebuild_lists();
        ui.invalidate_ui();
    };

    const auto handoff_bionic = [&]( bio_uid uid, bool weapon_management ) {
        avatar *p = as_avatar();
        bionic *bio = p ? find_bionic( *p, uid ) : nullptr;
        if( !p || !bio ) {
            status = _( "Select a bionic first." );
            return;
        }
        if( weapon_management && ( !( bio->can_install_weapon() || bio->has_weapon() ) || bio->powered ) ) {
            status = _( "Deactivate this bionic first." );
            return;
        }
        if( !weapon_management ) {
            const ui_action_entry eligible = bionic_power_action( *p, *bio );
            if( !eligible.enabled ) {
                status = eligible.disabled_reason;
                return;
            }
        }

        const bool was_powered = bio->powered;
        const bool closes_activate = bio->info().activated_close_ui;
        const bool closes_deactivate = bio->info().deactivated_close_ui;
        shortcut.cancel();
        more_menu.close();
        close_page_menu();
        hidden = true;
        ui.mark_resize();
        g->invalidate_main_ui_adaptor();
        ui_manager::redraw();

        if( weapon_management ) {
            if( bio->has_weapon() ) {
                if( std::optional<item> weapon = bio->uninstall_weapon() ) {
                    p->i_add_or_drop( *weapon );
                }
            } else {
                uilist menu;
                menu.title = _( "Select weapon to install" );
                std::vector<item *> weapons = p->items_with( [bio]( const item & it ) {
                    return it.has_any_flag( bio->info().installable_weapon_flags );
                } );
                for( int i = 0; i < static_cast<int>( weapons.size() ); ++i ) {
                    menu.addentry( i, true, MENU_AUTOASSIGN, weapons[i]->tname() );
                }
                if( weapons.empty() ) {
                    status = _( "You don't have any items you can install in this bionic." );
                } else {
                    menu.query();
                    if( menu.ret >= 0 && menu.ret < static_cast<int>( weapons.size() ) ) {
                        item &weapon = *weapons[menu.ret];
                        if( bio->can_install_weapon( weapon ) && bio->install_weapon( weapon ) ) {
                            item_location( *p, &weapon ).remove_item();
                        } else {
                            status = string_format( _( "Unable to install %s" ), weapon.tname() );
                        }
                    }
                }
            }
        } else if( was_powered ) {
            p->deactivate_bionic( *bio );
            done = closes_deactivate;
        } else {
            bool close_ui = false;
            if( closes_activate ) {
                ui.reset();
            }
            p->activate_bionic( *bio, false, &close_ui );
            bionic *after = find_bionic( *p, uid );
            done = closes_activate || ( close_ui && after && after->has_weapon() &&
                                        after->get_weapon().shots_remaining( get_map(), p ) > 0 );
        }
        done = done || p->get_moves() < 0;
        if( done ) {
            return;
        }
        hidden = false;
        rebuild_lists();
        ui.mark_resize();
        g->invalidate_main_ui_adaptor();
    };

    const auto run_bionic_action = [&]( const std::string &id ) {
        avatar *p = as_avatar();
        const std::optional<bio_uid> uid = selected_bionic_uid( model, bionic_tab, page_list.cursor() );
        bionic *bio = p ? find_bionic( *p, uid ) : nullptr;
        if( !p || !uid || !bio ) {
            status = _( "Select a bionic first." );
            return;
        }
        bionic_selection[bionic_tab] = *uid;
        if( id == "BIO_POWER" ) {
            handoff_bionic( *uid, false );
            return;
        }
        if( id == "BIO_WEAPON" ) {
            handoff_bionic( *uid, true );
            return;
        }
        if( id == "BIO_SPRITE" ) {
            bio->show_sprite = !bio->show_sprite;
            g->invalidate_main_ui_adaptor();
            status.clear();
            rebuild_lists();
        } else if( id == "BIO_SHORTCUT" ) {
            shortcut.arm();
            status.clear();
        } else if( id == "BIO_FUEL" ) {
            open_bionic_fuel( *uid );
        }
        ui.invalidate_ui();
    };

    while( !done ) {
        ui_manager::redraw_invalidated();

        if( shortcut.armed() ) {
            ui_key_field_result result;
            if( page == character_page::mutations ) {
                result = shortcut.read( [&]( int key ) {
                    return character_hub_mutation_chars.valid( key );
                } );
                const trait_id id = selected_mutation( model, mutation_tab, page_list.cursor() );
                if( result.type == ui_key_field_result_type::assigned ||
                    result.type == ui_key_field_result_type::cleared ) {
                    if( avatar *p = as_avatar(); p && !id.is_null() ) {
                        assign_mutation_shortcut( *p, id,
                                                  result.type == ui_key_field_result_type::cleared ? ' ' : result.key );
                        mutation_selection[mutation_tab] = id;
                        rebuild_lists();
                    }
                    status.clear();
                } else if( result.type == ui_key_field_result_type::invalid ) {
                    status = _( "Invalid shortcut. Use a mutation letter, Space to clear, or Esc to cancel." );
                } else if( result.type == ui_key_field_result_type::cancelled ) {
                    status.clear();
                }
            } else if( page == character_page::bionics ) {
                result = shortcut.read( bionics_ui::valid_shortcut );
                const std::optional<bio_uid> uid = selected_bionic_uid( model, bionic_tab, page_list.cursor() );
                if( result.type == ui_key_field_result_type::assigned ||
                    result.type == ui_key_field_result_type::cleared ) {
                    if( avatar *p = as_avatar(); p && uid ) {
                        bionics_ui::assign_shortcut( *p->my_bionics, *uid,
                                                     result.type == ui_key_field_result_type::cleared ? ' ' : result.key );
                        bionic_selection[bionic_tab] = *uid;
                        rebuild_lists();
                    }
                    status.clear();
                } else if( result.type == ui_key_field_result_type::invalid ) {
                    status = _( "Invalid shortcut. Use a bionic letter, Space to clear, or Esc to cancel." );
                } else if( result.type == ui_key_field_result_type::cancelled ) {
                    status.clear();
                }
            } else {
                shortcut.cancel();
            }
            ui.invalidate_ui();
            continue;
        }

        const std::string action = ctxt.handle_input();
        const std::optional<point> mouse = ctxt.get_coordinates_text( window );

        if( page_menu.is_open() ) {
            const std::string kind = page_menu_kind;
            const std::optional<bio_uid> owner = page_menu_bionic;
            const ui_action_result result = page_menu.handle_input(
                        action, mouse, true, ui_outside_click_policy::passthrough,
                        page_menu_trigger, &ctxt );
            if( result.type == ui_action_result_type::activated && result.entry ) {
                if( kind == "BIO_SORT" ) {
                    const std::string &id = result.entry->id;
                    uistate.bionic_sort_mode = id == "power" ? bionic_ui_sort_mode::POWER :
                                               id == "name" ? bionic_ui_sort_mode::NAME :
                                               id == "invlet" ? bionic_ui_sort_mode::INVLET :
                                               bionic_ui_sort_mode::NONE;
                    rebuild_lists();
                    detail_scroll.model().scroll_to_start();
                    ui.mark_resize();
                } else if( kind == "BIO_FUEL" && owner ) {
                    if( bionic *bio = find_bionic( *this, owner ); bio && bio->supports_safe_fuel() ) {
                        const int index = std::stoi( result.entry->id );
                        if( index >= 0 && index < static_cast<int>( bionics_ui::fuel_thresholds.size() ) ) {
                            bio->set_safe_fuel_thresh( bionics_ui::fuel_thresholds[index] );
                            bionic_selection[bionic_tab] = *owner;
                            g->invalidate_main_ui_adaptor();
                            rebuild_lists();
                        }
                    }
                }
                close_page_menu();
                ui.invalidate_ui();
                continue;
            }
            if( result.consumed() ) {
                if( !page_menu.is_open() ) {
                    close_page_menu();
                }
                ui.invalidate_ui();
                continue;
            }
        }

        if( more_menu.is_open() ) {
            const ui_action_result dropdown_result = more_menu.handle_input(
                        action, mouse, true, ui_outside_click_policy::passthrough, more_trigger, &ctxt );
            if( dropdown_result.type == ui_action_result_type::activated && dropdown_result.entry ) {
                const std::string id = dropdown_result.entry->id;
                if( !handle_page_action( id ) ) {
                    run_external_action( id );
                }
                continue;
            }
            if( dropdown_result.consumed() ) {
                ui.invalidate_ui();
                continue;
            }
        }

        const auto route_disabled = [&]( const ui_action_result &result ) {
            if( result.type == ui_action_result_type::disabled && result.entry ) {
                status = result.entry->disabled_reason;
                ui.invalidate_ui();
                return true;
            }
            return false;
        };

        const ui_action_result nav_result = navigation.handle_pointer_input( action, mouse );
        if( route_disabled( nav_result ) ) {
            continue;
        }
        if( nav_result.type == ui_action_result_type::activated && nav_result.entry ) {
            const std::string id = nav_result.entry->id;
            if( id == "BACK" ) {
                done = true;
            } else if( id == "MORE" ) {
                if( more_trigger ) {
                    more_menu.configure( window,
                                         point( more_trigger->p_min.x, more_trigger->p_max.y + 1 ),
                                         more_entries( customize_character ), 30 );
                }
                ui.invalidate_ui();
            } else {
                handle_page_action( id );
            }
            continue;
        }

        const ui_action_result toolbar_result = page_toolbar.handle_pointer_input( action, mouse );
        if( route_disabled( toolbar_result ) ) {
            continue;
        }
        if( toolbar_result.type == ui_action_result_type::activated && toolbar_result.entry ) {
            const std::string id = toolbar_result.entry->id;
            if( id == "MUT_ACTIVE" || id == "MUT_PASSIVE" ) {
                sync_selection();
                mutation_tab = id == "MUT_ACTIVE" ? 0 : 1;
                populate_page_list( *this, model, page, page_list, mutation_tab, bionic_tab,
                                    mutation_selection[mutation_tab], bionic_selection[bionic_tab] );
                sync_selection();
                detail_scroll.model().scroll_to_start();
                status.clear();
                ui.invalidate_ui();
            } else if( id == "BIO_ACTIVE" || id == "BIO_PASSIVE" ) {
                sync_selection();
                bionic_tab = id == "BIO_ACTIVE" ? 0 : 1;
                populate_page_list( *this, model, page, page_list, mutation_tab, bionic_tab,
                                    mutation_selection[mutation_tab], bionic_selection[bionic_tab] );
                sync_selection();
                detail_scroll.model().scroll_to_start();
                status.clear();
                ui.invalidate_ui();
            } else if( id == "BIO_SORT" ) {
                open_bionic_sort();
                ui.invalidate_ui();
            }
            continue;
        }

        if( is_management_page( page ) ) {
            const ui_action_result management_result = management_actions.handle_pointer_input( action, mouse );
            if( route_disabled( management_result ) ) {
                continue;
            }
            if( management_result.type == ui_action_result_type::activated && management_result.entry ) {
                const std::string &id = management_result.entry->id;
                if( id.rfind( "MUT_", 0 ) == 0 ) {
                    run_mutation_action( id );
                } else if( id.rfind( "BIO_", 0 ) == 0 ) {
                    run_bionic_action( id );
                }
                continue;
            }
            if( detail_scroll.has_capture() && detail_scroll.handle_input( action, ctxt, mouse ) ) {
                ui.invalidate_ui();
                continue;
            }
            if( detail_scroll.handle_input( action, ctxt, mouse ) ) {
                ui.invalidate_ui();
                continue;
            }
        } else {
            const ui_action_result footer_result = footer.handle_pointer_input( action, mouse );
            if( route_disabled( footer_result ) ) {
                continue;
            }
            if( footer_result.type == ui_action_result_type::activated && footer_result.entry ) {
                run_external_action( footer_result.entry->id );
                continue;
            }
        }

        if( action == "QUIT" ) {
            done = true;
            continue;
        }
        if( action == "HELP_KEYBINDINGS" ) {
            ctxt.display_menu();
            ui.invalidate_ui();
            continue;
        }

        if( action == "SELECT_STATS_TAB" ) {
            set_page( character_page::overview );
            continue;
        } else if( action == "SELECT_ENCUMBRANCE_TAB" ) {
            set_page( character_page::body );
            continue;
        } else if( action == "SELECT_SKILLS_TAB" ) {
            set_page( character_page::skills );
            continue;
        } else if( action == "SELECT_TRAITS_TAB" ) {
            set_page( character_page::traits );
            continue;
        } else if( action == "SELECT_BIONICS_TAB" ) {
            set_page( character_page::bionics );
            continue;
        } else if( action == "SELECT_EFFECTS_TAB" ) {
            set_page( character_page::effects );
            continue;
        } else if( action == "SELECT_PROFICIENCIES_TAB" ) {
            set_page( character_page::proficiencies );
            continue;
        } else if( action == "VIEW_BODYSTAT" ) {
            run_external_action( "BODY_STATUS" );
            continue;
        } else if( action == "VIEW_PROFICIENCIES" ) {
            run_external_action( "OPEN_PROFICIENCIES" );
            continue;
        } else if( action == "morale" ) {
            run_external_action( "MORALE" );
            continue;
        } else if( action == "MEDICAL_MENU" ) {
            run_external_action( "MEDICAL" );
            continue;
        } else if( action == "SWITCH_GENDER" && customize_character ) {
            run_external_action( "CUSTOMIZE" );
            continue;
        } else if( action == "CHANGE_PROFESSION_NAME" && customize_character ) {
            run_external_action( "CHANGE_PROFESSION" );
            continue;
        } else if( action == "CHANGE_ARMOR_SPRITE" ) {
            run_external_action( "CHANGE_ARMOR_SPRITE" );
            continue;
        } else if( action == "SELECT_TRAIT_VARIANT" && page == character_page::traits ) {
            run_external_action( "SELECT_TRAIT_VARIANT" );
            continue;
        } else if( action == "REASSIGN" ) {
            if( page == character_page::mutations ) {
                run_mutation_action( "MUT_SHORTCUT" );
                continue;
            } else if( page == character_page::bionics ) {
                run_bionic_action( "BIO_SHORTCUT" );
                continue;
            }
        } else if( action == "TOGGLE_SPRITE" ) {
            if( page == character_page::mutations ) {
                run_mutation_action( "MUT_SPRITE" );
                continue;
            } else if( page == character_page::bionics ) {
                run_bionic_action( "BIO_SPRITE" );
                continue;
            }
        } else if( action == "TOGGLE_SAFE_FUEL" && page == character_page::bionics ) {
            run_bionic_action( "BIO_FUEL" );
            continue;
        } else if( action == "SORT" && page == character_page::bionics ) {
            open_bionic_sort();
            ui.invalidate_ui();
            continue;
        } else if( action == "BIONICS_WEAPON" && page == character_page::bionics ) {
            run_bionic_action( "BIO_WEAPON" );
            continue;
        }

        if( action == "LEFT" || action == "RIGHT" || action == "NEXT_TAB" ||
            action == "PREV_TAB" ) {
            static const std::vector<character_page> pages = {
                character_page::overview,
                character_page::body,
                character_page::skills,
                character_page::traits,
                character_page::mutations,
                character_page::effects,
                character_page::bionics,
                character_page::proficiencies
            };
            const bool forward = action == "RIGHT" || action == "NEXT_TAB";
            const auto found = std::find( pages.begin(), pages.end(), page );
            const int index = found == pages.end() ? 0 : static_cast<int>( found - pages.begin() );
            const int next = ( index + ( forward ? 1 : -1 ) + static_cast<int>( pages.size() ) ) %
                             static_cast<int>( pages.size() );
            set_page( pages[next] );
            continue;
        }

        ui_action_result list_result;
        if( page == character_page::overview ) {
            list_result = overview_body_list.handle_input( action, ctxt, mouse );
            if( list_result.type == ui_action_result_type::activated ) {
                set_page( character_page::body );
                continue;
            }
        } else if( !page_list.visible_indices().empty() ) {
            const int old_cursor = page_list.cursor();
            list_result = page_list.handle_input( action, ctxt, mouse );
            sync_selection();
            if( is_management_page( page ) && page_list.cursor() != old_cursor ) {
                detail_scroll.model().scroll_to_start();
            }
            if( list_result.type == ui_action_result_type::activated ) {
                const int selected = page_list.cursor();
                if( page == character_page::proficiencies &&
                    selected >= 0 && selected < static_cast<int>( model.proficiencies.size() ) ) {
                    show_proficiencies_window( *this, model.proficiencies[selected].id );
                    rebuild_lists();
                } else if( page == character_page::mutations ) {
                    run_mutation_action( "MUT_POWER" );
                } else if( page == character_page::bionics ) {
                    run_bionic_action( "BIO_POWER" );
                } else if( page == character_page::body ) {
                    display_bodygraph( *this );
                    rebuild_lists();
                }
            }
        }

        if( list_result.type != ui_action_result_type::ignored || action == "MOUSE_MOVE" ) {
            ui.invalidate_ui();
        }
    }
}

// These are intentionally free functions so the legacy avatar entry points can
// redirect into the Character Hub without expanding Character's public API.
void show_character_hub_bionics( Character &you )
{
    pending_character_page = character_page::bionics;
    you.disp_info( false );
}

void show_character_hub_mutations( Character &you )
{
    pending_character_page = character_page::mutations;
    you.disp_info( false );
}
