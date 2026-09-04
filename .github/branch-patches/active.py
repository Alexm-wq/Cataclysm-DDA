from pathlib import Path

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")

old = '''    // Advertise Peek only when the adjacent viewpoint is actually beside an
    // obstruction and would reveal space the player cannot currently see.  The
    // obstruction belongs to the peek position, not necessarily to both positions:
    // requiring a wall adjacent to both incorrectly rejects ordinary corner peeks.
    const bool meaningful_peek = [&]() {
        if( !is_adjacent || is_self || here.impassable( mouse_target ) ) {
            return false;
        }

        bool has_local_occluder = false;
        for( const tripoint_bub_ms &corner : here.points_in_radius( mouse_target, 1, 0 ) ) {
            if( corner == player_pos || corner == mouse_target ) {
                continue;
            }
            if( !here.has_flag( ter_furn_flag::TFLAG_TRANSPARENT, corner ) ) {
                has_local_occluder = true;
                break;
            }
        }
        if( !has_local_occluder ) {
            return false;
        }

        constexpr int peek_probe_radius = 3;
        for( const tripoint_bub_ms &probe :
             here.points_in_radius( mouse_target, peek_probe_radius, 0 ) ) {
            // Ignore the squares immediately around the character: peeking is useful
            // only if the shifted viewpoint exposes space beyond normal adjacency.
            if( square_dist( probe.xy(), player_pos.xy() ) <= 1 ) {
                continue;
            }
            if( here.sees( mouse_target, probe, peek_probe_radius ) &&
                !here.sees( player_pos, probe, peek_probe_radius + 1 ) ) {
                return true;
            }
        }
        return false;
    }();
'''

new = '''    // Contextual Peek is about geometry, not current visibility.  Requiring an
    // LOS difference makes valid corners disappear when the area beyond is dark or
    // otherwise currently uninformative.  Mirror the actual one-tile peek movement:
    // advertise diagonal peeks around a blocked bridge tile, and cardinal peeks when
    // the one-tile viewpoint shift carries the player past the end of a side obstacle.
    const bool meaningful_peek = [&]() {
        if( !is_adjacent || is_self || here.impassable( mouse_target ) ) {
            return false;
        }

        const int dx = mouse_target.x() - player_pos.x();
        const int dy = mouse_target.y() - player_pos.y();

        // Classic diagonal corner peek.  The two squares shared by the player's and
        // target's neighborhoods are the orthogonal bridge tiles.  If either is
        // impassable, stepping the viewpoint diagonally is genuinely peeking around it.
        if( std::abs( dx ) == 1 && std::abs( dy ) == 1 ) {
            for( const tripoint_bub_ms &bridge : here.points_in_radius( player_pos, 1, 0 ) ) {
                if( bridge == player_pos || bridge == mouse_target ||
                    square_dist( bridge.xy(), mouse_target.xy() ) != 1 ) {
                    continue;
                }
                if( here.impassable( bridge ) ) {
                    return true;
                }
            }
            return false;
        }

        if( std::abs( dx ) + std::abs( dy ) != 1 ) {
            return false;
        }

        // Cardinal peeks are useful when the shift moves past the end of an obstacle
        // running alongside the player.  Compare each side square at the current
        // position with the matching side square at the peek position.
        bool current_side_a_blocked = false;
        bool target_side_a_blocked = false;
        bool current_side_b_blocked = false;
        bool target_side_b_blocked = false;

        for( const tripoint_bub_ms &side : here.points_in_radius( player_pos, 1, 0 ) ) {
            if( dx != 0 ) {
                if( side.y() == player_pos.y() - 1 ) {
                    if( side.x() == player_pos.x() ) {
                        current_side_a_blocked = here.impassable( side );
                    } else if( side.x() == mouse_target.x() ) {
                        target_side_a_blocked = here.impassable( side );
                    }
                } else if( side.y() == player_pos.y() + 1 ) {
                    if( side.x() == player_pos.x() ) {
                        current_side_b_blocked = here.impassable( side );
                    } else if( side.x() == mouse_target.x() ) {
                        target_side_b_blocked = here.impassable( side );
                    }
                }
            } else {
                if( side.x() == player_pos.x() - 1 ) {
                    if( side.y() == player_pos.y() ) {
                        current_side_a_blocked = here.impassable( side );
                    } else if( side.y() == mouse_target.y() ) {
                        target_side_a_blocked = here.impassable( side );
                    }
                } else if( side.x() == player_pos.x() + 1 ) {
                    if( side.y() == player_pos.y() ) {
                        current_side_b_blocked = here.impassable( side );
                    } else if( side.y() == mouse_target.y() ) {
                        target_side_b_blocked = here.impassable( side );
                    }
                }
            }
        }

        return ( current_side_a_blocked && !target_side_a_blocked ) ||
               ( current_side_b_blocked && !target_side_b_blocked );
    }();
'''

count = text.count(old)
if count != 1:
    raise RuntimeError(f"peek eligibility block: expected 1 match, found {count}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

assert "peek_probe_radius" not in text
assert "Classic diagonal corner peek" in text
assert "current_side_a_blocked" in text

Path("/tmp/branch_patch_commit_message").write_text(
    "Use corner geometry for contextual peeking\n", encoding="utf-8"
)
