from pathlib import Path

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
old = """    const Creature *const creature = get_creature_tracker().creature_at( mouse_target );
    const monster *const mon = dynamic_cast<const monster *>( creature );
    const npc *const guy = dynamic_cast<const npc *>( creature );
"""
new = """    Creature *const creature = get_creature_tracker().creature_at( mouse_target );
    const monster *const mon = dynamic_cast<const monster *>( creature );
    npc *const guy = dynamic_cast<npc *>( creature );
"""
if old not in text:
    raise SystemExit("expected contextual creature declarations not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
