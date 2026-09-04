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
            return format_info( info, std::max( 8, width ) );
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

        std::vector<std::string> format_info( const bodygraph_info &info, int width ) const {
            std::vector<std::string> out;
            if( info.specific_sublimb ) {
                out.emplace_back( string_format( "%s: %s", colorize( _( "Sub part of" ), c_magenta ),
                                                 info.parent_bp_name ) );
            }

            const std::pair<std::string, nc_color> hpbar = get_hp_bar( info.part_hp_cur,
                    info.part_hp_max );
            out.emplace_back( string_format( "%s: %s", colorize( _( "Health" ), c_magenta ),
                                             colorize( hpbar.first, hpbar.second ) ) );
            out.emplace_back( string_format( "%s: %d%%", colorize( _( "Wetness" ), c_magenta ),
                                             static_cast<int>( info.wetness * 100.0f ) ) );

            const flag_id thermometer_item( "THERMOMETER" );
            const json_character_flag thermometer_character( "THERMOMETER" );
            const bool temp_precise = who_.cache_has_item_with( thermometer_item ) ||
                                      who_.has_flag( thermometer_character );
            const units::temperature temp = units::from_fahrenheit( info.temperature.first / 50.0 );
            out.emplace_back( string_format( "%s: %s", colorize( _( "Body temp" ), c_magenta ),
                                             temp_precise ? colorize( print_temperature( temp ),
                                                     info.temperature.second ) : info.temp_approx ) );
            out.emplace_back( "--" );

            out.emplace_back( string_format( "%s:", colorize( _( "Effects" ), c_magenta ) ) );
            for( const effect &eff : info.effects ) {
                if( eff.get_id()->is_show_in_info() ) {
                    const game_message_type rating = eff.get_id()->get_rating( eff.get_intensity() );
                    out.emplace_back( string_format( "  %s", colorize( eff.disp_name(),
                                                    rating == m_good ? c_green : rating == m_bad ? c_red : c_yellow ) ) );
                }
            }
            out.emplace_back( "--" );

            out.emplace_back( string_format( "%s:", colorize( _( "Worn" ), c_magenta ) ) );
            for( const std::string &worn : info.worn_names ) {
                out.emplace_back( string_format( "  %s", worn ) );
            }
            out.emplace_back( "--" );

            out.emplace_back( string_format( "%s: %d%%",
                                             colorize( info.specific_sublimb ? _( "Coverage" ) :
                                                     _( "Coverage (Avg.)" ), c_magenta ), info.avg_coverage ) );
            out.emplace_back( "--" );
            out.emplace_back( string_format( "%s: %d", colorize( _( "Encumbrance" ), c_magenta ),
                                             info.total_encumbrance ) );
            out.emplace_back( "--" );

            out.emplace_back( string_format( "%s:", colorize( info.specific_sublimb ?
                                             _( "Protection" ) : _( "Protection (Avg.)" ), c_magenta ) ) );
            std::string legend = string_format( "%s %s %s", colorize( _( "worst" ), c_red ),
                                                colorize( _( "median" ), c_yellow ),
                                                colorize( _( "best" ), c_light_green ) );
            int available = clamp( width - utf8_width( legend, true ), 0, width );
            legend.insert( legend.begin(), available > 4 ? 4 : available, ' ' );
            out.emplace_back( legend );

            const auto resist_line = [&]( const damage_type_id &type ) {
                const std::string worst = string_format( width <= 18 ? "%4.1f" : "%5.2f",
                                          info.worst_case.type_resist( type ) );
                const std::string median = string_format( width <= 18 ? "%4.1f" : "%5.2f",
                                           info.median_case.type_resist( type ) );
                const std::string best = string_format( width <= 18 ? "%4.1f" : "%5.2f",
                                         info.best_case.type_resist( type ) );
                std::string text = string_format( "%s %s %s", colorize( worst, c_red ),
                                                  colorize( median, c_yellow ),
                                                  colorize( best, c_light_green ) );
                int space = clamp( width - utf8_width( text, true ), 0, width );
                text.insert( text.begin(), space > 4 ? 4 : space, ' ' );
                return text;
            };
            const auto environmental_line = [&]( const damage_type_id &type ) {
                return colorize( string_format( "    %5.2f", info.best_case.type_resist( type ) ),
                                 c_white );
            };

            for( const damage_type &type : damage_type::get_all() ) {
                if( info.best_case.type_resist( type.id ) > 1 ) {
                    out.emplace_back( string_format( "  %s:",
                                                     uppercase_first_letter( type.name.translated() ) ) );
                    out.emplace_back( type.env ? environmental_line( type.id ) : resist_line( type.id ) );
                }
            }
            return out;
        }
};

#endif // CATA_SRC_BODYGRAPH_VIEW_MODEL_H
