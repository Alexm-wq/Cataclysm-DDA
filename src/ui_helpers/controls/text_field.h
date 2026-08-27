#pragma once
#ifndef CATA_SRC_UI_HELPERS_CONTROLS_TEXT_FIELD_H
#define CATA_SRC_UI_HELPERS_CONTROLS_TEXT_FIELD_H

#include <algorithm>
#include <optional>
#include <string>
#include <utility>

#include "../../catacharset.h"
#include "../../color.h"
#include "../../cuboid_rectangle.h"
#include "../../cursesdef.h"
#include "../../output.h"
#include "../../point.h"

struct ui_text_field_style {
    nc_color label = c_light_gray;
    nc_color border = c_light_cyan;
    nc_color text = c_white;
    nc_color placeholder = c_dark_gray;
    nc_color clear = c_light_red;
    nc_color clear_disabled = c_dark_gray;
};

enum class ui_text_field_hit : int {
    none,
    edit,
    clear
};

class ui_text_field
{
    public:
        void clear() {
            configured_ = false;
            edit_hit_.reset();
            clear_hit_.reset();
        }

        void configure( const catacurses::window &parent, const point &pos, const int requested_width,
                        std::string label, std::string value, std::string placeholder,
                        const bool clearable = true,
                        const ui_text_field_style &style = ui_text_field_style() ) {
            clear();
            const int available = getmaxx( parent ) - pos.x;
            if( available < 4 || pos.y < 0 || pos.y >= getmaxy( parent ) ) {
                return;
            }
            style_ = style;
            pos_ = pos;
            label_ = std::move( label );
            value_ = std::move( value );
            placeholder_ = std::move( placeholder );
            width_ = std::clamp( requested_width, 4, available );
            const int label_width = std::min( utf8_width( label_ ), std::max( 0, width_ - 4 ) );
            field_x_ = pos_.x + label_width;
            field_width_ = std::max( 4, pos_.x + width_ - field_x_ );
            field_width_ = std::min( field_width_, getmaxx( parent ) - field_x_ );
            if( field_width_ < 4 ) {
                return;
            }
            const int clear_width = clearable && field_width_ >= 7 ? 3 : 0;
            const int edit_right = field_x_ + field_width_ - 2 - clear_width;
            edit_hit_ = inclusive_rectangle<point>( point( field_x_, pos_.y ),
                        point( std::max( field_x_, edit_right ), pos_.y ) );
            if( clear_width > 0 ) {
                const int clear_x = field_x_ + field_width_ - 4;
                clear_hit_ = inclusive_rectangle<point>( point( clear_x, pos_.y ),
                             point( clear_x + 2, pos_.y ) );
            }
            configured_ = true;
        }

        void draw( const catacurses::window &parent ) const {
            if( !configured_ ) {
                return;
            }
            trim_and_print( parent, pos_, std::max( 0, field_x_ - pos_.x ), style_.label, label_ );
            mvwputch( parent, point( field_x_, pos_.y ), style_.border, '[' );
            mvwputch( parent, point( field_x_ + field_width_ - 1, pos_.y ), style_.border, ']' );
            const int text_width = std::max( 1, field_width_ - 2 - ( clear_hit_ ? 3 : 0 ) );
            trim_and_print( parent, point( field_x_ + 1, pos_.y ), text_width,
                            value_.empty() ? style_.placeholder : style_.text,
                            value_.empty() ? placeholder_ : value_ );
            if( clear_hit_ ) {
                trim_and_print( parent, clear_hit_->p_min, 3,
                                value_.empty() ? style_.clear_disabled : style_.clear, "[x]" );
            }
        }

        ui_text_field_hit hit_test( const point &parent_pos ) const {
            if( clear_hit_ && clear_hit_->contains( parent_pos ) ) {
                return ui_text_field_hit::clear;
            }
            if( edit_hit_ && edit_hit_->contains( parent_pos ) ) {
                return ui_text_field_hit::edit;
            }
            return ui_text_field_hit::none;
        }

        point edit_start() const {
            return configured_ ? point( field_x_ + 1, pos_.y ) : point::zero;
        }
        int edit_end_x() const {
            return configured_ ? ( clear_hit_ ? clear_hit_->p_min.x - 1 : field_x_ + field_width_ - 2 ) : 0;
        }

    private:
        ui_text_field_style style_;
        point pos_ = point::zero;
        std::string label_;
        std::string value_;
        std::string placeholder_;
        int width_ = 0;
        int field_x_ = 0;
        int field_width_ = 0;
        bool configured_ = false;
        std::optional<inclusive_rectangle<point>> edit_hit_;
        std::optional<inclusive_rectangle<point>> clear_hit_;
};

#endif // CATA_SRC_UI_HELPERS_CONTROLS_TEXT_FIELD_H
