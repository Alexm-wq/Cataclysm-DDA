from pathlib import Path
import subprocess

path = Path("src/game.cpp")
text = path.read_text(encoding="utf-8")

old = """static constexpr int safemode_corner_button_base_pixels = 16;\nstatic constexpr int safemode_corner_launcher_base_pixels = 8;\n"""
new = """static constexpr int safemode_corner_button_base_pixels = 24;\nstatic constexpr int safemode_corner_launcher_base_pixels = 12;\n"""

if old not in text:
    raise SystemExit("expected safemode pixel-size constants not found")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

subprocess.run(["git", "diff", "--check"], check=True)
