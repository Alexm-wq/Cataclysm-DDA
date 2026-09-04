from pathlib import Path

path = Path("src/construction_ui.cpp")
text = path.read_text(encoding="utf-8")
old = '''    std::vector<ui_action_strip_item> actions = {
        { ui_action_entry( _( "Build" ), "MODE_BUILD", true,
                           mode == construction_workspace_mode::build ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Place" ), "MODE_PLACE", true,
                           mode == construction_workspace_mode::place ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Remove" ), "MODE_REMOVE", true,
                           mode == construction_workspace_mode::remove ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Markers" ), "MODE_MARKERS", true,
                           mode == construction_workspace_mode::markers ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Add plans" ), "MODE_PLAN", true,
                           mode == construction_workspace_mode::plan ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Manage plans" ), "MODE_PLANS", true,
                           mode == construction_workspace_mode::plans ), 0,
          ui_action_alignment::left }
    };
    if( compact && operation != construction_operation::remove ) {
        actions.push_back( { ui_action_entry( _( "Palette" ), "FOCUS_PALETTE", true,
                                              focus == workspace_focus::palette ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Map" ), "FOCUS_VIEWPORT", true,
                                              focus == workspace_focus::viewport ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Inspector" ), "FOCUS_INSPECTOR", true,
                                              focus == workspace_focus::inspector ), 1,
                             ui_action_alignment::left } );
    }
    if( compact && activity_handoff ) {
        actions.push_back( { ui_action_entry( _( "Pause" ), "PAUSE" ), 2,
                             ui_action_alignment::right } );
    }
    actions.push_back( { ui_action_entry( _( "Back" ), "BACK" ), 2,
                         ui_action_alignment::right } );
'''
new = '''    const bool editor_actions_enabled = !activity_handoff;
    std::vector<ui_action_strip_item> actions = {
        { ui_action_entry( _( "Build" ), "MODE_BUILD", editor_actions_enabled,
                           mode == construction_workspace_mode::build ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Place" ), "MODE_PLACE", editor_actions_enabled,
                           mode == construction_workspace_mode::place ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Remove" ), "MODE_REMOVE", editor_actions_enabled,
                           mode == construction_workspace_mode::remove ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Markers" ), "MODE_MARKERS", editor_actions_enabled,
                           mode == construction_workspace_mode::markers ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Add plans" ), "MODE_PLAN", editor_actions_enabled,
                           mode == construction_workspace_mode::plan ), 0,
          ui_action_alignment::left },
        { ui_action_entry( _( "Manage plans" ), "MODE_PLANS", editor_actions_enabled,
                           mode == construction_workspace_mode::plans ), 0,
          ui_action_alignment::left }
    };
    if( compact && operation != construction_operation::remove ) {
        actions.push_back( { ui_action_entry( _( "Palette" ), "FOCUS_PALETTE",
                                              editor_actions_enabled,
                                              focus == workspace_focus::palette ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Map" ), "FOCUS_VIEWPORT",
                                              editor_actions_enabled,
                                              focus == workspace_focus::viewport ), 1,
                             ui_action_alignment::left } );
        actions.push_back( { ui_action_entry( _( "Inspector" ), "FOCUS_INSPECTOR",
                                              editor_actions_enabled,
                                              focus == workspace_focus::inspector ), 1,
                             ui_action_alignment::left } );
    }
    if( compact && activity_handoff ) {
        actions.push_back( { ui_action_entry( _( "Pause" ), "PAUSE" ), 2,
                             ui_action_alignment::right } );
    }
    actions.push_back( { ui_action_entry( _( "Back" ), "BACK", editor_actions_enabled ), 2,
                         ui_action_alignment::right } );
'''
if text.count(old) != 1:
    raise RuntimeError(f"handoff header block: expected one match, found {text.count(old)}")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Disable inactive construction controls during handoff\n", encoding="utf-8"
)
