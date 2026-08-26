from pathlib import Path

paths = [Path("src/veh_interact.cpp"), Path("src/sdltiles.cpp")]
changed = 0
for path in paths:
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        if "DebugLog( D_INFO, D_SDL )" in line:
            # Only promote the temporary vehicle live-camera diagnostics.
            # Some tagged stream expressions continue on later lines, so detect
            # the start line by looking ahead in a small local window below.
            idx = len(out)
            lookahead = line
            # This simple path handles the current code where the tag is on the
            # same DebugLog line; leave unrelated SDL logging untouched.
            if "[VEH_LIVE_" in line:
                line = line.replace("DebugLog( D_INFO, D_SDL )", "DebugLog( D_INFO, D_MAIN )")
                changed += 1
        out.append(line)
    path.write_text("".join(out))

# The diagnostics currently split the tag onto the same source line as the
# stream expression in some blocks, but guard against formatting variants by
# doing a second structured pass over each DebugLog statement.
for path in paths:
    text = path.read_text()
    marker = "DebugLog( D_INFO, D_SDL )"
    pos = 0
    pieces = []
    while True:
        start = text.find(marker, pos)
        if start < 0:
            pieces.append(text[pos:])
            break
        pieces.append(text[pos:start])
        # Inspect until the semicolon ending this stream statement. The tagged
        # diagnostics are short enough that the first semicolon is the end.
        end = text.find(";", start)
        if end < 0:
            raise SystemExit(f"unterminated DebugLog statement in {path}")
        statement = text[start:end + 1]
        if "[VEH_LIVE_CAMERA]" in statement or "[VEH_LIVE_RENDER]" in statement:
            statement = statement.replace(marker, "DebugLog( D_INFO, D_MAIN )", 1)
            changed += 1
        pieces.append(statement)
        pos = end + 1
    path.write_text("".join(pieces))

combined = "\n".join(path.read_text() for path in paths)
if "[VEH_LIVE_CAMERA]" not in combined or "[VEH_LIVE_RENDER]" not in combined:
    raise SystemExit("expected vehicle live diagnostics are missing")

# No tagged diagnostic may remain on the filterable SDL class.
for path in paths:
    text = path.read_text()
    marker = "DebugLog( D_INFO, D_SDL )"
    pos = 0
    while True:
        start = text.find(marker, pos)
        if start < 0:
            break
        end = text.find(";", start)
        if end < 0:
            break
        statement = text[start:end + 1]
        if "[VEH_LIVE_CAMERA]" in statement or "[VEH_LIVE_RENDER]" in statement:
            raise SystemExit(f"tagged D_SDL diagnostic remains in {path}")
        pos = end + 1

if changed == 0:
    raise SystemExit("no tagged diagnostics were promoted")

print(f"promoted {changed} tagged diagnostic statements to D_MAIN")
