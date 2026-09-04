#pragma once
#ifndef CATA_SRC_BODYGRAPH_VIEW_MODEL_H
#define CATA_SRC_BODYGRAPH_VIEW_MODEL_H

#include <algorithm>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "bodygraph.h"
#include "bodypart.h"
#include "cata_utility.h"
#include "catacharset.h"
#include "character.h"
#include "character_attire.h"
#include "damage.h"
#include "effect.h"
#include "flag.h"
#include "messages.h"
#include "output.h"
#include "string_formatter.h"
#include "subbodypart.h"
#include "translations.h"
#include "units.h"
#include "weather.h"

/**
 * Presentation-independent state for embedding the existing bodygraph in another UI.
 *
 * The legacy Body Status window owns both its data model and its curses windows.  The
 * Character Hub only needs the model: graph navigation, selectable body/sub-body parts,
 * selected-region highlighting and the exact information that the legacy inspector
 * exposes.  Keeping that here prevents the Hub from reimplementing body-map semantics.
 */
struct bodygraph_view_entry {
    bodypart_id bodypart;
    const sub_body_part_type *subpart = nullptr;
    const bodygraph_part *graph_part = nullptr;
    bool present = false;

    std::string name() const {
        return subpart ? subpart->name.translated() : bodypart->name.translated();
    }

    bool has_nested_graph() const {
        return graph_part != nullptr && !graph_part->nested_graph.is_null();
    }

    bodygraph_id nested_graph() const {
        return graph_part ? graph_part->nested_graph : bodygraph_id::NULL_ID();
    }
};

class bodygraph_view_model
{
    public:
        explicit bodygraph_view_model( const Character &who ) : who_( who ), graph_( root_graph() ) {
            rebuild();
        }

        static bodygraph_id root_graph() {
            return bodygraph_id( "full_body" );
        }

        const bodygraph_id &graph() const {
            return graph_;
        }

        bool at_root() const {
            return history_.empty();
        }

        const std::vector<bodygraph_view_entry> &entries() const {
            return entries_;
        }

        int selected_index() const {
            return selected_;
        }

        const bodygraph_view_entry *selected() const {
            return selected_ >= 0 && selected_ < static_cast<int>( entries_.size() ) ?
                   &entries_[selected_] : nullptr;
        }

        void select( int index ) {
            if( entries_.empty() ) {
                selected_ = -1;
                return;
            }
            selected_ = std::clamp( index, 0, static_cast<int>( entries_.size() ) - 1 );
        }

        bool select_bodypart( const bodypart_id &id ) {
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                if( entries_[i].bodypart == id && entries_[i].subpart == nullptr ) {
                    selected_ = i;
                    return true;
                }
            }
            for( int i = 0; i < static_cast<int>( entries_.size() ); ++i ) {
                if( entries_[i].bodypart == id ) {
                    selected_ = i;
                    return true;
                }
            }
            return false;
        }

        bool enter_selected() {
            const bodygraph_view_entry *entry = selected();
            if( !entry || !entry->has_nested_graph() ) {
                return false;
            }
            history_.emplace_back( graph_, selected_ );
            graph_ = entry->nested_graph();
            selected_ = 0;
            rebuild();
            return true;
        }

        bool back() {
            if( history_.empty() ) {
                return false;
            }
            const std::pair<bodygraph_id, int> previous = history_.back();
            history_.pop_back();
            graph_ = previous.first;
            selected_ = previous.second;
            rebuild();
            select( selected_ );
            return true;
        }

        void reset() {
            history_.clear();
            graph_ = root_graph();
            selected_ = 0;
            rebuild();
        }

        std::string graph_title() const {
            if( graph_->parent_bp.has_value() ) {
                return uppercase_first_letter( graph_->parent_bp.value()->name.translated() );
            }
            return _( "Full body" );
        }

        std::vector<std::string> graph_lines( int width = 0, int height = 0 ) const {
            const bodygraph_part *selected_part = selected() ? selected()->graph_part : nullptr;
            const auto process_sym = [&]( const bodygraph_part *part, const std::string &sym ) {
                return colorize( sym, part != nullptr && selected_part == part ?
                                 selected_part->sel_color : graph_->fill_color );
            };
            return get_bodygraph_lines( who_, process_sym, graph_, width, height );
        }

        std::vector<std::string> info_lines( int width ) const {
            const bodygraph_view_entry *entry = selected();
            if( !entry || !entry->present ) {
                return {};
            }

            bodygraph_info info;
            std::set<sub_bodypart_id> sub_parts;
            if( entry->subpart != nullptr ) {
                sub_parts.emplace( entry->subpart->id );
            } else {
                for( const sub_bodypart_str_id &sbp : entry->bodypart->sub_parts ) {
                    if( !sbp->secondary ) {
                        sub_parts.emplace( sbp.id() );
                    }
                }
            }
            who_.worn.prepare_bodymap_info( info, entry->bodypart, sub_parts, who_ );

            std::vector<std::string> out;
            out.emplace_back( colorize( to_upper_case( entry->name() ), c_light_green ) );
            if( info.specific_sublimb ) {
                out.emplace_back( string_format( "%s: %s", colorize( _( "Sub part of" ), c_dark_gray ),
                                                 info.parent_bp_name ) );
            }
            const std::vector<std::string> detail = format_info( info, std::max( 8, width ) );
            out.insert( out.end(), detail.begin(), detail.end() );
            return out;
        }

    private:
        const Character &who_;
        bodygraph_id graph_;
        std::vector<std::pair<bodygraph_id, int>> history_;
        std::vector<bodygraph_view_entry> entries_;
        int selected_ = 0;

        void rebuild() {
            entries_.clear();
            for( const auto &part : graph_->parts ) {
                for( const bodypart_id &id : part.second.bodyparts ) {
                    entries_.push_back( { id, nullptr, &part.second,
                                          who_.has_part( id, body_part_filter::equivalent ) } );
                }
                for( const sub_bodypart_id &id : part.second.sub_bodyparts ) {
                    const bodypart_id parent = id->parent.id();
                    entries_.push_back( { parent, &*id, &part.second,
                                          who_.has_part( parent, body_part_filter::equivalent ) } );
                }
            }
            std::sort( entries_.begin(), entries_.end(), []( const bodygraph_view_entry &lhs,
            const bodygraph_view_entry &rhs ) {
                if( lhs.subpart && rhs.subpart ) {
                    return lhs.subpart->name.translated_lt( rhs.subpart->name );
                }
                if( lhs.bodypart->name.translated_ne( rhs.bodypart->name ) ) {
                    return lhs.bodypart->name.translated_lt( rhs.bodypart->name );
                }
                if( static_cast<bool>( lhs.subpart ) != static_cast<bool>( rhs.subpart ) ) {
                    return lhs.subpart == nullptr;
                }
                // Equal display entries are intentionally equivalent; do not order by raw pointers.
                return false;
            } );
            if( entries_.empty() ) {
                selected_ = -1;
            } else {
                selected_ = std::clamp( selected_, 0, static_cast<int>( entries_.size() ) - 1 );
            }
        }

        static std::string field( const std::string &label, const std::string &value ) {
            return string_format( "%s: %s", colorize( label, c_light_gray ), value );
        }

        static void append_paired_fields( std::vector<std::string> &out, int width,
                                          const std::string &left, const std::string &right ) {
            if( width < 38 ) {
                out.emplace_back( left );
                out.emplace_back( right );
                return;
            }
            const int split = width / 2;
            const int left_width = utf8_width( left, true );
            const int right_width = utf8_width( right, true );
            if( left_width >= split || right_width > width - split ) {
                out.emplace_back( left );
                out.emplace_back( right );
                return;
            }
            std::string row = left;
            row.append( split - left_width, ' ' );
            row += right;
            out.emplace_back( std::move( row ) );
        }

        std::vector<std::string> format_info( const bodygraph_info &info, int width ) const {
            std::vector<std::string> out;
            out.emplace_back( "" );
            out.emplace_back( colorize( _( "STATUS" ), c_light_cyan ) );

            const std::pair<std::string, nc_color> hpbar = get_hp_bar( info.part_hp_cur,
                    info.part_hp_max );
            out.emplace_back( field( _( "Health" ), colorize( hpbar.first, hpbar.second ) ) );

            const flag_id thermometer_item( "THERMOMETER" );
            const json_character_flag thermometer_character( "THERMOMETER" );
            const bool temp_precise = who_.cache_has_item_with( thermometer_item ) ||
                                      who_.has_flag( thermometer_character );
            const units::temperature temp = units::from_fahrenheit( info.temperature.first / 50.0 );
            const std::string temp_text = temp_precise ?
                                          colorize( print_temperature( temp ), info.temperature.second ) :
                                          info.temp_approx;

            append_paired_fields( out, width,
                                  field( _( "Body temp" ), temp_text ),
                                  field( _( "Wetness" ), string_format( "%d%%",
                                          static_cast<int>( info.wetness * 100.0f ) ) ) );
            append_paired_fields( out, width,
                                  field( info.specific_sublimb ? _( "Coverage" ) : _( "Coverage (Avg.)" ),
                                         string_format( "%d%%", info.avg_coverage ) ),
                                  field( _( "Encumbrance" ), string_format( "%d",
                                          info.total_encumbrance ) ) );

            std::vector<std::string> visible_effects;
            for( const effect &eff : info.effects ) {
                if( !eff.get_id()->is_show_in_info() ) {
                    continue;
                }
                const game_message_type rating = eff.get_id()->get_rating( eff.get_intensity() );
                visible_effects.emplace_back( colorize( eff.disp_name(),
                                              rating == m_good ? c_green : rating == m_bad ? c_red : c_yellow ) );
            }
            if( !visible_effects.empty() ) {
                out.emplace_back( "" );
                out.emplace_back( colorize( string_format( _( "EFFECTS (%d)" ),
                                            static_cast<int>( visible_effects.size() ) ), c_light_cyan ) );
                for( const std::string &effect_name : visible_effects ) {
                    out.emplace_back( string_format( "  %s", effect_name ) );
                }
            }

            out.emplace_back( "" );
            out.emplace_back( colorize( string_format( _( "WORN (%d)" ),
                                        static_cast<int>( info.worn_names.size() ) ), c_light_cyan ) );
            if( info.worn_names.empty() ) {
                out.emplace_back( colorize( _( "  Nothing worn on this area." ), c_dark_gray ) );
            } else {
                for( const std::string &worn : info.worn_names ) {
                    out.emplace_back( string_format( "  %s", worn ) );
                }
            }

            out.emplace_back( "" );
            out.emplace_back( colorize( info.specific_sublimb ? _( "PROTECTION" ) :
                                        _( "PROTECTION (AVERAGE)" ), c_light_cyan ) );

            const int value_width = width >= 42 ? 7 : 6;
            const int label_width = width - 1 - value_width * 3;
            if( label_width >= 8 ) {
                std::string header( label_width, ' ' );
                header += " ";
                header += colorize( left_justify( trim_by_length( _( "worst" ), value_width ),
                                                  value_width, true ), c_red );
                header += colorize( left_justify( trim_by_length( _( "median" ), value_width ),
                                                  value_width, true ), c_yellow );
                header += colorize( left_justify( trim_by_length( _( "best" ), value_width ),
                                                  value_width, true ), c_light_green );
                out.emplace_back( header );

                const auto value = [&]( double amount, nc_color color ) {
                    return colorize( string_format( value_width >= 7 ? "%7.2f" : "%6.2f", amount ), color );
                };
                for( const damage_type &type : damage_type::get_all() ) {
                    if( info.best_case.type_resist( type.id ) <= 1 ) {
                        continue;
                    }
                    const std::string name = trim_by_length( uppercase_first_letter( type.name.translated() ),
                                             label_width );
                    std::string row = left_justify( name, label_width, true ) + " ";
                    if( type.env ) {
                        row.append( value_width * 2, ' ' );
                        row += value( info.best_case.type_resist( type.id ), c_light_green );
                    } else {
                        row += value( info.worst_case.type_resist( type.id ), c_red );
                        row += value( info.median_case.type_resist( type.id ), c_yellow );
                        row += value( info.best_case.type_resist( type.id ), c_light_green );
                    }
                    out.emplace_back( std::move( row ) );
                }
            } else {
                std::string legend = string_format( "%s %s %s", colorize( _( "worst" ), c_red ),
                                                    colorize( _( "median" ), c_yellow ),
                                                    colorize( _( "best" ), c_light_green ) );
                const int available = clamp( width - utf8_width( legend, true ), 0, width );
                legend.insert( legend.begin(), available > 2 ? 2 : available, ' ' );
                out.emplace_back( legend );
                for( const damage_type &type : damage_type::get_all() ) {
                    if( info.best_case.type_resist( type.id ) <= 1 ) {
                        continue;
                    }
                    out.emplace_back( uppercase_first_letter( type.name.translated() ) );
                    if( type.env ) {
                        out.emplace_back( colorize( string_format( "  %5.2f",
                                                        info.best_case.type_resist( type.id ) ), c_light_green ) );
                    } else {
                        out.emplace_back( string_format( "  %s %s %s",
                                                        colorize( string_format( "%5.2f",
                                                                info.worst_case.type_resist( type.id ) ), c_red ),
                                                        colorize( string_format( "%5.2f",
                                                                info.median_case.type_resist( type.id ) ), c_yellow ),
                                                        colorize( string_format( "%5.2f",
                                                                info.best_case.type_resist( type.id ) ), c_light_green ) ) );
                    }
                }
            }
            return out;
        }
};

#endif // CATA_SRC_BODYGRAPH_VIEW_MODEL_H
