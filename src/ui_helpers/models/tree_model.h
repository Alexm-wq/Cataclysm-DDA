#pragma once
#ifndef CATA_SRC_UI_HELPERS_MODELS_TREE_MODEL_H
#define CATA_SRC_UI_HELPERS_MODELS_TREE_MODEL_H

#include <utility>
#include <vector>

/** Parent indices refer to earlier rows in a depth-first ordered list.
 * Nonselectable rows are groups: activating them only expands/collapses them.
 */
struct ui_tree_node {
    int parent = -1;
    bool selectable = true;
};

/** Renderer-independent hierarchy. Row identities do not change when branches
 * collapse, so selection can remain independent of visibility and expansion.
 */
class ui_tree_model
{
    public:
        void reset( std::vector<ui_tree_node> nodes ) {
            nodes_ = std::move( nodes );
            const int count = static_cast<int>( nodes_.size() );
            depths_.assign( count, 0 );
            expandable_.assign( count, false );
            expanded_.assign( count, false );
            for( int i = 0; i < count; ++i ) {
                int &parent = nodes_[i].parent;
                // Reject missing/forward parents, including cycles.
                if( parent < 0 || parent >= i ) {
                    parent = -1;
                } else {
                    depths_[i] = depths_[parent] + 1;
                    expandable_[parent] = true;
                }
            }
            rebuild_visible();
        }

        int parent( const int index ) const {
            return valid( index ) ? nodes_[index].parent : -1;
        }

        int depth( const int index ) const {
            return valid( index ) ? depths_[index] : 0;
        }

        bool selectable( const int index ) const {
            return valid( index ) && nodes_[index].selectable;
        }

        bool expandable( const int index ) const {
            return valid( index ) && expandable_[index];
        }

        bool expanded( const int index ) const {
            return valid( index ) && expanded_[index];
        }

        const std::vector<int> &visible_indices() const {
            return visible_;
        }

        int visible_position( const int index ) const {
            return valid( index ) ? positions_[index] : -1;
        }

        int index_at( const int position ) const {
            return position >= 0 && position < static_cast<int>( visible_.size() ) ?
                   visible_[position] : -1;
        }

        int visible_ancestor( int index ) const {
            while( valid( index ) && visible_position( index ) < 0 ) {
                index = parent( index );
            }
            return valid( index ) ? index : -1;
        }

        bool set_expanded( const int index, const bool value ) {
            if( !expandable( index ) || expanded_[index] == value ) {
                return false;
            }
            expanded_[index] = value;
            rebuild_visible();
            return true;
        }

        /** Open only the ancestors needed to reveal a known selection. */
        void reveal( const int index ) {
            bool changed = false;
            for( int ancestor = parent( index ); ancestor >= 0; ancestor = parent( ancestor ) ) {
                changed = changed || !expanded_[ancestor];
                expanded_[ancestor] = true;
            }
            if( changed ) {
                rebuild_visible();
            }
        }

    private:
        bool valid( const int index ) const {
            return index >= 0 && index < static_cast<int>( nodes_.size() );
        }

        void rebuild_visible() {
            visible_.clear();
            positions_.assign( nodes_.size(), -1 );
            for( int i = 0; i < static_cast<int>( nodes_.size() ); ++i ) {
                const int ancestor = parent( i );
                if( ancestor < 0 || ( expanded_[ancestor] && positions_[ancestor] >= 0 ) ) {
                    positions_[i] = static_cast<int>( visible_.size() );
                    visible_.push_back( i );
                }
            }
        }

        std::vector<ui_tree_node> nodes_;
        std::vector<int> depths_;
        std::vector<bool> expandable_;
        std::vector<bool> expanded_;
        std::vector<int> visible_;
        std::vector<int> positions_;
};

#endif // CATA_SRC_UI_HELPERS_MODELS_TREE_MODEL_H
