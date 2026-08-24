from pathlib import Path

path = Path("src/advanced_inv.cpp")
text = path.read_text()
start = text.index("bool advanced_inventory::action_split_stack")
end = text.index("bool advanced_inventory::action_reload", start)
body = text[start:end]
count = body.count("redraw_sidebar();")
if count != 2:
    raise SystemExit(f"expected 2 split-local redraw_sidebar calls, found {count}")
body = body.replace("            redraw_sidebar();\n", "").replace("        redraw_sidebar();\n", "")
text = text[:start] + body + text[end:]
path.write_text(text)
