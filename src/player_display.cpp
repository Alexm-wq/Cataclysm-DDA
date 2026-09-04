#include <algorithm>
#include <cstddef>
#include <functional>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "avatar.h"
#include "bionics.h"
#include "bodygraph.h"
#include "bodypart.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "character.h"
#include "color.h"
#include "cursesdef.h"
#include "debug.h"
#include "display.h"
#include "effect.h"
#include "enum_conversions.h"
#include "game_inventory.h"
#include "input_context.h"
#include "item.h"
#include "item_location.h"
#include "itype.h"
#include "mutation.h"
#include "options.h"
#include "output.h"
#include "point.h"
#include "proficiency.h"
#include "skill.h"
#include "string_formatter.h"
#include "string_input_popup.h"
#include "translations.h"
#include "uilist.h"
#include "ui_manager.h"
#include "units.h"
#include "ui_helpers/controls/action_strip.h"
#include "ui_helpers/controls/dropdown.h"
#include "ui_helpers/controls/selection_list.h"

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

enum class character_page : int {
    overview,
    body,
    skills,
    traits,
    effects,
    bionics,
    proficiencies,
};

struct character_hub_model {
    std::vector<const Skill *> skills;
    std::vector<trait_and_var> traits;
    std::vector<std::pair<std::string, std::string>> effects;
    std::vector<bionic_id> bionics;
    std::vector<display_proficiency> proficiencies;
    std::vector<std::pair<bodypart_id, bool>> bodyparts;
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
        case character_page::effects:
            return _( "Effects" );
        case character_page::bionics:
            return _( "Bionics" );
        case character_page::proficiencies:
            return _( "Proficiencies" );
    }
    return std::string();
}

static void refresh_character_model( Character &you, character_hub_model &model )
{
    model.skills = Skill::get_skills_sorted_by( []( const Skill & lhs, const Skill & rhs ) {
        return lhs.get_sort_rank() < rhs.get_sort_rank();
    } );

    model.traits = you.get_mutations_variants( false );
    std::sort( model.traits.begin(), model.traits.end(), trait_var_display_sort );

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

    model.bionics = you.get_bionics();
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

static void populate_page_list( Character &you, const character_hub_model &model,
                                character_page page, ui_selection_list &list )
{
    std::vector<ui_action_entry> entries;

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

        case character_page::effects:
            entries.reserve( model.effects.size() );
            for( size_t i = 0; i < model.effects.size(); ++i ) {
                entries.emplace_back( model.effects[i].first,
                                      string_format( "effect_%d", static_cast<int>( i ) ) );
            }
            break;

        case character_page::bionics:
            entries.reserve( model.bionics.size() );
            for( const bionic_id &bio : model.bionics ) {
                entries.emplace_back( bio->name.translated(), bio.str() );
            }
            break;

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
    if( !list.visible_indices().empty() ) {
        list.select_only( 0 );
    } else {
        list.clear_selection();
    }
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
            ui_action_entry( label, id, true, page == target ),
            0,
            ui_action_alignment::left
        } );
    };
    const auto add_action = [&]( const std::string &label, const char *id ) {
        result.push_back( {
            ui_action_entry( label, id ),
            0,
            ui_action_alignment::left
        } );
    };

    add_page( _( "Overview" ), "PAGE_OVERVIEW", character_page::overview );
    add_page( _( "Body" ), "PAGE_BODY", character_page::body );
    add_page( _( "Skills" ), "PAGE_SKILLS", character_page::skills );
    add_page( _( "Traits" ), "PAGE_TRAITS", character_page::traits );
    add_action( _( "Mutations" ), "MUTATIONS" );
    add_page( _( "Effects" ), "PAGE_EFFECTS", character_page::effects );
    add_page( _( "Bionics" ), "PAGE_BIONICS", character_page::bionics );
    add_page( _( "Proficiencies" ), "PAGE_PROFICIENCIES", character_page::proficiencies );
    add_action( _( "Morale" ), "MORALE" );
    add_action( _( "Medical" ), "MEDICAL" );

    ui_action_entry more( _( "More" ), "MORE" );
    more.dropdown = true;
    result.push_back( { std::move( more ), 1, ui_action_alignment::left } );
    result.push_back( {
        ui_action_entry( _( "Back" ), "BACK" ),
        2,
        ui_action_alignment::right
    } );

    return result;
}

static std::vector<ui_dropdown_entry> more_entries( bool customize_character )
{
    std::vector<ui_dropdown_entry> entries;
    entries.emplace_back( _( "Change armor appearance" ), "CHANGE_ARMOR_SPRITE" );
    if( customize_character ) {
        entries.emplace_back( _( "Customize character" ), "CUSTOMIZE" );
        entries.emplace_back( _( "Change profession name" ), "CHANGE_PROFESSION" );
    }
    return entries;
}

static std::vector<ui_action_entry> footer_entries( character_page page, bool can_upgrade_stats )
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
        case character_page::effects:
            return {};
        case character_page::bionics:
            return { ui_action_entry( _( "Open bionics" ), "OPEN_BIONICS" ) };
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
    if( length <= 0 ) {
        return;
    }
    catacurses::mvwhline( win, point( x, y ), LINE_OXOX, length );
}

static void draw_vertical_separator( const catacurses::window &win, int x, int y, int length )
{
    if( length <= 0 ) {
        return;
    }
    catacurses::mvwvline( win, point( x, y ), LINE_XOXO, length );
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
                           int content_bottom )
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

    const int upper_top = 4;
    const int upper_data = upper_top + 2;
    const int lower_sep = std::min( content_bottom - 4, 15 );
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
    draw_key_value( win, col1_x, row++, col1_w, _( "Weight:" ), display::weight_string( you ) );
    draw_key_value( win, col1_x, row++, col1_w, _( "Height:" ), you.height_string() );
    draw_key_value( win, col1_x, row++, col1_w, _( "Age:" ), you.age_string() );
    draw_key_value( win, col1_x, row, col1_w, _( "Blood type:" ),
                    io::enum_to_string( you.my_blood_type ) + ( you.blood_rh_factor ? "+" : "-" ) );

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
    draw_key_value( win, col3_x, row++, col3_w, _( "Effects:" ),
                    string_format( "%d", static_cast<int>( model.effects.size() ) ),
                    model.effects.empty() ? c_light_gray : c_light_red );

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

static void draw_page_detail( const catacurses::window &win, Character &you,
                              const character_hub_model &model, character_page page,
                              int selected, int x, int y, int width, int height )
{
    if( width <= 2 || height <= 0 ) {
        return;
    }

    draw_section_title( win, x, y, width, _( "DETAILS" ) );
    const int text_y = y + 2;
    const int text_height = std::max( 0, height - 2 );
    if( selected < 0 || text_height <= 0 ) {
        trim_and_print( win, point( x, text_y ), width, c_dark_gray, _( "Nothing selected." ) );
        return;
    }

    switch( page ) {
        case character_page::skills:
            if( selected < static_cast<int>( model.skills.size() ) ) {
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
            if( selected < static_cast<int>( model.traits.size() ) ) {
                const trait_and_var &trait = model.traits[selected];
                trim_and_print( win, point( x, text_y ), width,
                                trait.trait->get_display_color(), trait.name() );
                if( text_height > 3 ) {
                    fold_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                    you.mutation_desc( trait.trait ) );
                }
            }
            break;

        case character_page::effects:
            if( selected < static_cast<int>( model.effects.size() ) ) {
                trim_and_print( win, point( x, text_y ), width, c_light_green,
                                model.effects[selected].first );
                if( text_height > 3 ) {
                    fold_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                    model.effects[selected].second );
                }
            }
            break;

        case character_page::bionics:
            if( selected < static_cast<int>( model.bionics.size() ) ) {
                const bionic_id &bio = model.bionics[selected];
                trim_and_print( win, point( x, text_y ), width, c_light_green,
                                bio->name.translated() );
                if( text_height > 3 ) {
                    fold_and_print( win, point( x, text_y + 2 ), width, c_light_gray,
                                    bio->description.translated() );
                }
            }
            break;

        case character_page::proficiencies:
            if( selected < static_cast<int>( model.proficiencies.size() ) ) {
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
            if( selected < static_cast<int>( model.bodyparts.size() ) ) {
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
                            ui_selection_list &list, int content_bottom )
{
    const int width = getmaxx( win );
    const int split = std::clamp( width * 2 / 5, 30, std::max( 31, width - 34 ) );
    const int list_x = 2;
    const int list_width = std::max( 1, split - list_x - 1 );
    const int detail_x = split + 2;
    const int detail_width = std::max( 1, width - detail_x - 2 );
    const int top = 4;
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

    draw_page_detail( win, you, model, page, list.cursor(), detail_x, top, detail_width,
                      content_bottom - top + 1 );
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
        case character_page::effects:
            return _( "Effects | Select an active effect to inspect it" );
        case character_page::bionics:
            return _( "Bionics | Select a bionic for details; use Open bionics to manage it" );
        case character_page::proficiencies:
            return _( "Proficiencies | Select a proficiency for details" );
    }
    return std::string();
}

} // namespace

void Character::disp_info( bool customize_character )
{
    customize_character |= debug_mode;

    character_hub_model model;
    refresh_character_model( *this, model );

    character_page page = character_page::overview;
    ui_selection_list page_list;
    ui_selection_list overview_body_list;
    ui_action_strip navigation;
    ui_action_strip footer;
    ui_dropdown more_menu;
    std::optional<inclusive_rectangle<point>> more_trigger;

    catacurses::window window;
    ui_adaptor ui;

    const auto rebuild_lists = [&]() {
        refresh_character_model( *this, model );
        populate_page_list( *this, model, page, page_list );
        if( window ) {
            const int width = getmaxx( window );
            const int inner_width = std::max( 1, width - 4 );
            const int col_width = std::max( 1, inner_width / 3 - 3 );
            populate_overview_body_list( *this, model, overview_body_list, col_width );
        }
    };

    const auto set_page = [&]( character_page next ) {
        page = next;
        more_menu.close();
        refresh_character_model( *this, model );
        populate_page_list( *this, model, page, page_list );
        ui.invalidate_ui();
    };

    ui.on_screen_resize( [&]( ui_adaptor & ui ) {
        window = catacurses::newwin( TERMY, TERMX, point::zero );
        ui.position_from_window( window );
        page_list.invalidate_geometry();
        overview_body_list.invalidate_geometry();
        more_menu.close();
        rebuild_lists();
    } );
    ui.mark_resize();

    ui.on_redraw( [&]( ui_adaptor & ui ) {
        ui.disable_cursor();
        werase( window );

        const int width = getmaxx( window );
        const int height = getmaxy( window );
        if( width < 4 || height < 8 ) {
            wnoutrefresh( window );
            return;
        }

        draw_border( window, c_light_gray );
        center_print( window, 0, c_light_green, _( "CHARACTER" ) );

        navigation.configure( window, point( 2, 1 ), navigation_entries( page ),
                              std::max( 0, width - 4 ), 1 );
        navigation.draw( window );
        more_trigger = navigation.bounds_for_id( "MORE" );

        draw_separator( window, 2, 1, width - 2 );
        trim_and_print( window, point( 2, 3 ), std::max( 1, width - 4 ), c_light_gray,
                        identity_line( *this ) );

        const int content_bottom = height - 5;
        if( page == character_page::overview ) {
            const int inner_width = std::max( 1, width - 4 );
            const int col_width = std::max( 1, inner_width / 3 - 3 );
            if( overview_body_list.visible_indices().size() != model.bodyparts.size() ) {
                populate_overview_body_list( *this, model, overview_body_list, col_width );
            }
            draw_overview( window, *this, model, overview_body_list, content_bottom );
        } else {
            draw_list_page( window, *this, model, page, page_list, content_bottom );
        }

        draw_separator( window, height - 4, 1, width - 2 );
        const bool can_upgrade_stats = get_option<bool>( "STATS_THROUGH_KILLS" ) && is_avatar();
        footer.configure( window, point( 2, height - 3 ), footer_entries( page, can_upgrade_stats ),
                          std::max( 0, width - 4 ), 1 );
        footer.draw( window );
        trim_and_print( window, point( 2, height - 2 ), std::max( 1, width - 4 ), c_dark_gray,
                        string_format( _( "Selection: %s" ), page_help( page ) ) );

        wnoutrefresh( window );
        more_menu.draw( window );
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
        } else if( id == "MUTATIONS" ) {
            power_mutations();
        } else if( id == "MORALE" ) {
            disp_morale();
        } else if( id == "MEDICAL" ) {
            disp_medical();
        } else if( id == "OPEN_BIONICS" ) {
            power_bionics();
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

    bool done = false;
    while( !done ) {
        ui_manager::redraw_invalidated();
        const std::string action = ctxt.handle_input();
        const std::optional<point> mouse = ctxt.get_coordinates_text( window );

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

        const ui_action_result nav_result = navigation.handle_pointer_input( action, mouse );
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
            } else if( !handle_page_action( id ) ) {
                run_external_action( id );
            }
            continue;
        }

        const ui_action_result footer_result = footer.handle_pointer_input( action, mouse );
        if( footer_result.type == ui_action_result_type::activated && footer_result.entry ) {
            run_external_action( footer_result.entry->id );
            continue;
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
        }

        if( action == "LEFT" || action == "RIGHT" || action == "NEXT_TAB" ||
            action == "PREV_TAB" ) {
            static const std::vector<character_page> pages = {
                character_page::overview,
                character_page::body,
                character_page::skills,
                character_page::traits,
                character_page::effects,
                character_page::bionics,
                character_page::proficiencies
            };
            const bool forward = action == "RIGHT" || action == "NEXT_TAB";
            const auto found = std::find( pages.begin(), pages.end(), page );
            if( found == pages.end() ) {
                set_page( forward ? pages.front() : pages.back() );
            } else {
                const int index = static_cast<int>( found - pages.begin() );
                const int next = ( index + ( forward ? 1 : -1 ) +
                                   static_cast<int>( pages.size() ) ) %
                                 static_cast<int>( pages.size() );
                set_page( pages[next] );
            }
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
            list_result = page_list.handle_input( action, ctxt, mouse );
            if( list_result.type == ui_action_result_type::activated ) {
                const int selected = page_list.cursor();
                if( page == character_page::proficiencies &&
                    selected >= 0 && selected < static_cast<int>( model.proficiencies.size() ) ) {
                    show_proficiencies_window( *this, model.proficiencies[selected].id );
                    rebuild_lists();
                } else if( page == character_page::bionics ) {
                    power_bionics();
                    rebuild_lists();
                } else if( page == character_page::traits ) {
                    power_mutations();
                    rebuild_lists();
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
