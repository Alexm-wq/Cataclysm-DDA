from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


path = "src/construction_ui.cpp"

replace_once(
    path,
    """        bool blink = true;\n        bool activity_handoff = false;\n        bool ui_hidden = false;\n""",
    """        bool blink = true;\n        bool activity_handoff = false;\n        bool ui_hidden = false;\n        bool handoff_repaint_pending = false;\n""",
)

replace_once(
    path,
    """        current_ui->on_redraw( [this]( ui_adaptor & adaptor ) {\n            if( !ui_hidden ) {\n                draw( adaptor );\n            }\n        } );\n""",
    """        current_ui->on_redraw( [this]( ui_adaptor & adaptor ) {\n            if( ui_hidden ) {\n                return;\n            }\n            // The game invalidates the top UI every activity turn.  While an\n            // ACT_BUILD handoff is advancing, the Construction workspace is\n            // intentionally a dormant frame: keep it visible, but do not\n            // repaint the auxiliary map and catalog on every simulated turn.\n            if( activity_handoff && !handoff_repaint_pending ) {\n                return;\n            }\n            draw( adaptor );\n            handoff_repaint_pending = false;\n        } );\n""",
)

replace_once(
    path,
    """void construction_workspace::begin_activity_handoff()\n{\n    // Keep this exact workspace and adaptor registered while ACT_BUILD advances.\n    activity_handoff = ui != nullptr;\n}\n""",
    """void construction_workspace::begin_activity_handoff()\n{\n    // Keep this exact workspace and adaptor registered while ACT_BUILD advances.\n    // Paint the newly-created partial construction once, then let the frame stay\n    // dormant until a query restore or completion actually changes UI state.\n    activity_handoff = ui != nullptr;\n    handoff_repaint_pending = activity_handoff;\n}\n""",
)

replace_once(
    path,
    """void construction_workspace::resume_activity_handoff()\n{\n    activity_handoff = false;\n    ui_hidden = false;\n""",
    """void construction_workspace::resume_activity_handoff()\n{\n    activity_handoff = false;\n    handoff_repaint_pending = false;\n    ui_hidden = false;\n""",
)

replace_once(
    path,
    """void construction_workspace::restore_after_query()\n{\n    if( !activity_handoff || !ui_hidden || !ui ) {\n        return;\n    }\n    ui_hidden = false;\n""",
    """void construction_workspace::restore_after_query()\n{\n    if( !activity_handoff || !ui_hidden || !ui ) {\n        return;\n    }\n    ui_hidden = false;\n    // The popup overwrote the editor, so this is one of the few redraws that\n    // must be allowed while ACT_BUILD is still running.\n    handoff_repaint_pending = true;\n""",
)

# Source-only contracts: no compile/build step here.
text = Path(path).read_text()
for needle in [
    "bool handoff_repaint_pending = false;",
    "if( activity_handoff && !handoff_repaint_pending )",
    "handoff_repaint_pending = activity_handoff;",
    "handoff_repaint_pending = true;",
]:
    if needle not in text:
        raise RuntimeError(f"missing redraw-throttle contract: {needle}")

Path("/tmp/branch_patch_commit_message").write_text(
    "Throttle Construction redraws during activities [skip ci]\n"
)
print("Construction activity handoff redraw throttle staged")
