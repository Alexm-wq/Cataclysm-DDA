from pathlib import Path
import re

CPP = Path('src/veh_interact.cpp')
STATUS = Path('doc/UI_MODERNIZATION_STATUS/VEHICLE_EDITOR_OVERHAUL_STATUS.md')

c = CPP.read_text()

quick = r'''bool veh_interact::queue_quick_refill_all( map &here )
{
    if( !refuel_info ) {
        return false;
    }

    // Quick refill operates over every refillable store, independent of the
    // manual checkbox selection.  Rebuild against all stores first.
    std::vector<bool> saved_selection = refuel_info->selected_tanks;
    std::fill( refuel_info->selected_tanks.begin(), refuel_info->selected_tanks.end(), false );
    refresh_refuel_sources( here );

    const auto source_payload = []( const item_location &source ) -> const item * {
        if( !source ) {
            return nullptr;
        }
        if( source->is_watertight_container() && source->num_item_stacks() == 1 && !source->empty() ) {
            return &source->only_item();
        }
        return source.get_item();
    };

    struct source_state_t {
        int remaining = 0;
        bool divisible = false;
    };
    std::vector<source_state_t> source_state;
    source_state.reserve( refuel_info->sources.size() );
    for( const refuel_info_t::source_t &source : refuel_info->sources ) {
        const item *payload = source_payload( source.location );
        source_state.push_back( {
            refill_source_available( source.location ),
            payload != nullptr && payload->count_by_charges()
        } );
    }

    // Larger deficits first, while source choice prefers the smallest source
    // that completes the current store in one transfer.  If no source can
    // finish it, consume the largest useful source.  This minimizes transfer
    // count greedily under the existing one-turn-per-transfer refill model.
    std::vector<size_t> tank_order( refuel_info->tanks.size() );
    std::iota( tank_order.begin(), tank_order.end(), 0 );
    const auto maximum_need = [&]( const size_t tank_slot ) {
        int result = 0;
        const vehicle_part &part = veh->part( refuel_info->tanks[tank_slot] );
        for( const refuel_info_t::source_t &source : refuel_info->sources ) {
            if( refill_source_compatible( part, source.location ) ) {
                result = std::max( result, refill_part_remaining( part, source.location ) );
            }
        }
        return result;
    };
    std::stable_sort( tank_order.begin(), tank_order.end(), [&]( const size_t lhs, const size_t rhs ) {
        return maximum_need( lhs ) > maximum_need( rhs );
    } );

    std::vector<std::pair<int, item_location>> plan;
    for( const size_t tank_slot : tank_order ) {
        const int part_index = refuel_info->tanks[tank_slot];
        vehicle_part &part = veh->part( part_index );
        std::optional<itype_id> chosen_fuel;
        int tank_remaining = 0;

        while( true ) {
            int best_source = -1;
            int best_transfer = 0;
            bool best_finishes = false;
            int best_finishing_surplus = INT_MAX;
            int best_capacity = 0;

            for( size_t s = 0; s < refuel_info->sources.size(); ++s ) {
                if( source_state[s].remaining <= 0 ) {
                    continue;
                }
                const item_location &source = refuel_info->sources[s].location;
                const item *payload = source_payload( source );
                if( payload == nullptr || !refill_source_compatible( part, source ) ) {
                    continue;
                }
                if( chosen_fuel && payload->typeId() != *chosen_fuel ) {
                    continue;
                }

                const int capacity = chosen_fuel ? tank_remaining : refill_part_remaining( part, source );
                if( capacity <= 0 ) {
                    continue;
                }
                const int transfer = std::min( capacity, source_state[s].remaining );
                const bool finishes = transfer >= capacity;
                const int surplus = finishes ? source_state[s].remaining - capacity : INT_MAX;

                if( best_source < 0 ||
                    ( finishes && !best_finishes ) ||
                    ( finishes == best_finishes && finishes && surplus < best_finishing_surplus ) ||
                    ( !finishes && !best_finishes && transfer > best_transfer ) ) {
                    best_source = static_cast<int>( s );
                    best_transfer = transfer;
                    best_finishes = finishes;
                    best_finishing_surplus = surplus;
                    best_capacity = capacity;
                }
            }

            if( best_source < 0 || best_transfer <= 0 ) {
                break;
            }

            const item_location source = refuel_info->sources[best_source].location;
            const item *payload = source_payload( source );
            if( payload == nullptr ) {
                break;
            }
            if( !chosen_fuel ) {
                chosen_fuel = payload->typeId();
                tank_remaining = best_capacity;
            }

            // Recompute against the simulated deficit, not the unchanged live
            // vehicle part.  This prevents a multi-source fill from being
            // over-planned and charged unnecessary extra turns.
            const int transfer = std::min( tank_remaining, source_state[best_source].remaining );
            if( transfer <= 0 ) {
                break;
            }
            plan.emplace_back( part_index, source );
            tank_remaining -= transfer;
            source_state[best_source].remaining -= transfer;
            if( !source_state[best_source].divisible ) {
                source_state[best_source].remaining = 0;
            }
            if( tank_remaining <= 0 ) {
                break;
            }
        }
    }

    if( plan.empty() ) {
        refuel_info->selected_tanks = std::move( saved_selection );
        refresh_refuel_sources( here );
        msg = _( "No valid refuel transfers are available." );
        return false;
    }

    // Each pair is one canonical vehicle refill transfer. serialize_activity()
    // charges exactly one normal action-turn per pair, including the current turn.
    return queue_refill_plan( plan );
}

void veh_interact::display_refuel_pane'''

c, n = re.subn(
    r'bool veh_interact::queue_quick_refill_all\( map &here \)\n\{.*?\n\}\n\nvoid veh_interact::display_refuel_pane',
    quick,
    c,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit(f'quick refill finalizer expected one match, got {n}')

old = '''            trim_and_print( w_refuel_details, point( 1, detail_y++ ),
                            std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_cyan,
                            string_format( "%s: %s", part.name(), tank_amount( part ) ) );
            if( part.is_tank() ) {
'''
new = '''            trim_and_print( w_refuel_details, point( 1, detail_y++ ),
                            std::max( 1, getmaxx( w_refuel_details ) - 2 ), c_light_cyan,
                            string_format( "%s: %s", part.name(), tank_amount( part ) ) );
            if( detail_y < getmaxy( w_refuel_details ) - 6 ) {
                const std::string fuel_name = part.ammo_current().is_null() ?
                                              _( "Empty" ) : item::nname( part.ammo_current() );
                trim_and_print( w_refuel_details, point( 3, detail_y++ ),
                                std::max( 1, getmaxx( w_refuel_details ) - 4 ), c_light_gray,
                                string_format( _( "Fuel: %s" ), fuel_name ) );
            }
            if( part.is_tank() ) {
'''
if c.count(old) != 1:
    raise SystemExit(f'fuel type detail expected one match, got {c.count(old)}')
c = c.replace(old, new, 1)

CPP.write_text(c)

s = STATUS.read_text()
s = s.replace('The remaining ~10% is primarily stabilization and UX completion.',
              'The remaining ~4% is primarily stabilization and UX completion.')
s = s.replace('**Quick refill all** builds a turn-cost-aware plan that prefers a single source able to finish a store, otherwise consuming the largest useful source first to reduce transfer count.',
              '**Quick refill all** builds a turn-cost-aware plan that prefers a single source able to finish a store, otherwise consuming the largest useful source first; its planner tracks simulated remaining tank capacity so multi-source fills cannot be over-planned or charged extra transfers.')
STATUS.write_text(s)

assert 'std::optional<itype_id> chosen_fuel' in CPP.read_text()
assert 'simulated deficit' in CPP.read_text()
assert 'Fuel: %s' in CPP.read_text()
assert 'remaining ~4%' in STATUS.read_text()
print('vehicle refuel finalizer applied')
