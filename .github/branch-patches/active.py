from pathlib import Path

path = Path("src/construction_ui.cpp")
text = path.read_text()

def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match, found {count}")
    text = text.replace(old, new, 1)

replace_once(
    """        void rebuild_inspector();
        void refresh_active_target();
        void set_focus( workspace_focus next, ui_adaptor &ui );
""",
    """        void rebuild_inspector();
        void refresh_active_target();
        void clear_selection();
        void set_focus( workspace_focus next, ui_adaptor &ui );
"""
)

replace_once(
    """    rebuild_inspector();
}

void construction_workspace::rebuild_inspector()
""",
    """    rebuild_inspector();
}

void construction_workspace::clear_selection()
{
    selected_group = construction_group_str_id::NULL_ID();
    selected_target.reset();
    hovered_target.reset();
    context_target.reset();
    context_actions.clear();
    adjacent_resolutions.clear();
    resolution = construction_target_resolution();
    transient_status.clear();
    palette.clear_selection();
    rebuild_inspector();
}

void construction_workspace::rebuild_inspector()
"""
)

replace_once(
    """    } else if( id == \"CLEAR\" ) {
        selected_target.reset();
        refresh_active_target();
    }
""",
    """    } else if( id == \"CLEAR\" ) {
        clear_selection();
    }
"""
)

replace_once(
    """    if( action == \"QUIT\" ) {
        if( category_menu.is_open() ) {
            category_menu.close();
        } else if( context_menu.is_open() ) {
            context_menu.close();
        } else {
            exit_requested = true;
        }
        return true;
    }
""",
    """    if( action == \"QUIT\" ) {
        if( category_menu.is_open() ) {
            category_menu.close();
        } else if( context_menu.is_open() ) {
            context_menu.close();
        } else if( !selected_group.is_null() || selected_target || hovered_target || context_target ) {
            clear_selection();
        } else {
            exit_requested = true;
        }
        return true;
    }
"""
)

path.write_text(text)
Path("/tmp/branch_patch_commit_message").write_text(
    "Make Escape clear construction selection [skip ci]\n"
)
