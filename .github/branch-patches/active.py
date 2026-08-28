from pathlib import Path

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")
old = '''    return pos.x >= 0 && pos.y >= 0 &&\n           pos.x + size.x <= getmaxx( catacurses::stdscr ) &&\n           pos.y + size.y <= getmaxy( catacurses::stdscr );\n}\n#endif\n\n#endif\n\nstatic bool safemode_corner_controls_fit( const catacurses::window &panel )\n'''
new = '''    return pos.x >= 0 && pos.y >= 0 &&\n           pos.x + size.x <= getmaxx( catacurses::stdscr ) &&\n           pos.y + size.y <= getmaxy( catacurses::stdscr );\n}\n#endif\n\nstatic bool safemode_corner_controls_fit( const catacurses::window &panel )\n'''
if text.count(old) != 1:
    raise SystemExit("expected duplicate safemode geometry endif block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
