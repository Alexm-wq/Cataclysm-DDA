from pathlib import Path

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
old = '''    if( is_adjacent && !is_self ) {
        add_action( ACTION_PEEK );
    }
'''
new = '''    // Peeking is only useful when shifting the viewpoint onto this adjacent tile
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
    if( meaningful_peek ) {
        add_action( ACTION_PEEK );
    }
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one Peek context block, found {text.count(old)}")
path.write_text(text.replace(old, new), encoding="utf-8")
