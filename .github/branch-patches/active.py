from pathlib import Path
import subprocess

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")

old_tooltip = """            safemode_corner_tooltip.configure( catacurses::stdscr, *safe_bounds, tooltip_pos,\n                                               tooltip_text, std::chrono::milliseconds( 1000 ),\n                                               tooltip_width );\n"""
new_tooltip = """            ui_tooltip_style tooltip_style;\n            tooltip_style.border = c_light_gray;\n            tooltip_style.text = enabled ? c_light_green : c_light_red;\n            safemode_corner_tooltip.configure( catacurses::stdscr, *safe_bounds, tooltip_pos,\n                                               tooltip_text, std::chrono::milliseconds( 1000 ),\n                                               tooltip_width, tooltip_style );\n"""
if old_tooltip not in text:
    raise SystemExit("expected safemode tooltip configure block not found")
text = text.replace(old_tooltip, new_tooltip, 1)

old_alert_border = """    wborder( alert, LINE_XOXO, LINE_XOXO, LINE_OXOX, LINE_OXOX,\n             LINE_OXXO, LINE_OOXX, LINE_XXOO, LINE_XOOX );\n"""
new_alert_border = """    draw_border( alert, c_light_gray );\n"""
if old_alert_border not in text:
    raise SystemExit("expected safemode alert border block not found")
text = text.replace(old_alert_border, new_alert_border, 1)

path.write_text(text, encoding="utf-8")
subprocess.run(["git", "diff", "--check"], check=True)
