from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
old = '''    // Peeking is only useful when shifting the viewpoint onto this adjacent tile
    // actually reveals nearby space that is occluded from the player's current position.
    // Keep the keyboard action permissive, but avoid advertising Peek on ordinary open ground.
    const bool meaningful_peek = [&]() {
        if( !is_adjacent || is_self || here.impassable( mouse_target ) ) {
            return false;
        }
        constexpr int peek_probe_radius = 2;
        for( const tripoint_bub_ms &probe :
             here.points_in_radius( mouse_target, peek_probe_radius, 0 ) ) {
            if( here.sees( mouse_target, probe, peek_probe_radius ) &&
                !here.sees( player_pos, probe, peek_probe_radius + 1 ) ) {
                return true;
            }
        }
        return false;
    }();
'''
new = '''    // Advertise Peek only for an actual corner/doorway situation.  A raw LOS
    // difference is too permissive: any unrelated nearby wall can make some probe tile
    // visible from the adjacent square but not from the player's square.  Require an
    // opaque tile shared by both positions, then verify that the peek position reveals
    // space beyond the player's immediate neighborhood.
    const bool meaningful_peek = [&]() {
        if( !is_adjacent || is_self || here.impassable( mouse_target ) ) {
            return false;
        }

        bool has_shared_occluder = false;
        for( const tripoint_bub_ms &corner : here.points_in_radius( player_pos, 1, 0 ) ) {
            if( corner == player_pos || corner == mouse_target ||
                square_dist( corner.xy(), mouse_target.xy() ) > 1 ) {
                continue;
            }
            if( !here.has_flag( ter_furn_flag::TFLAG_TRANSPARENT, corner ) ) {
                has_shared_occluder = true;
                break;
            }
        }
        if( !has_shared_occluder ) {
            return false;
        }

        constexpr int peek_probe_radius = 2;
        for( const tripoint_bub_ms &probe :
             here.points_in_radius( mouse_target, peek_probe_radius, 0 ) ) {
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
text = replace_once(text, old, new, "contextual peek gate")
path.write_text(text, encoding="utf-8")

assert "has_shared_occluder" in text
assert "square_dist( probe.xy(), player_pos.xy() ) <= 1" in text

Path("/tmp/branch_patch_commit_message").write_text(
    "Tighten contextual peek eligibility\n", encoding="utf-8"
)
