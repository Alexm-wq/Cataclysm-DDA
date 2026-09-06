#include <algorithm>
#include <cstdlib>

#include "avatar.h"
#include "game.h"
#include "messages.h"
#include "monster.h"
#include "translations.h"
#include "type_id.h"

void spawn_vehicle_editor_test_ocular_parasite()
{
    const tripoint_bub_ms center = get_avatar().pos_bub();
    const mtype_id parasite_id( "mon_ocular_parasite_human" );

    const auto try_spawn = [&]( const int dx, const int dy ) {
        const tripoint_bub_ms target( center.x() + dx, center.y() + dy, center.z() );
        return g->place_critter_at( parasite_id, target ) != nullptr;
    };

    // Prefer a simple cardinal spawn exactly three tiles from the player.
    if( try_spawn( 3, 0 ) || try_spawn( -3, 0 ) || try_spawn( 0, 3 ) || try_spawn( 0, -3 ) ) {
        add_msg( m_info, _( "Spawned an ocular parasite host three tiles away." ) );
        return;
    }

    // If the cardinal tiles are obstructed, use another tile on the exact radius-3 ring.
    for( int dx = -3; dx <= 3; ++dx ) {
        for( int dy = -3; dy <= 3; ++dy ) {
            if( std::max( std::abs( dx ), std::abs( dy ) ) != 3 ) {
                continue;
            }
            if( ( dx == 3 && dy == 0 ) || ( dx == -3 && dy == 0 ) ||
                ( dx == 0 && dy == 3 ) || ( dx == 0 && dy == -3 ) ) {
                continue;
            }
            if( try_spawn( dx, dy ) ) {
                add_msg( m_info, _( "Spawned an ocular parasite host three tiles away." ) );
                return;
            }
        }
    }

    add_msg( m_warning, _( "No open tile exactly three tiles away was available for the ocular parasite host." ) );
}
