from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    text = text.replace(old, new, 1)


replace_once(
'''    if( editor_test_mode ) {
        msg += _( "<color_light_cyan>Test mode: components and tools are ignored.</color>\\n" );
    }
''',
'''    if( editor_test_mode ) {
        msg += _( "<color_light_cyan>Test mode: components, tools, and skill requirements are ignored.</color>\\n" );
    }
''',
"test mode requirements message",
)

replace_once(
'''    for( const auto &e : skills ) {
        bool hasSkill = player_character.get_knowledge_level( e.first ) >= e.second;
        if( !hasSkill ) {
            ok = false;
        }
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
        msg += string_format( _( "> %1$s%2$s %3$i</color>\\n" ), status_color( hasSkill ),
                              e.first.obj().name(), e.second );
    }
''',
'''    for( const auto &e : skills ) {
        const bool has_skill = player_character.get_knowledge_level( e.first ) >= e.second;
        const bool requirement_met = editor_test_mode || has_skill;
        if( !requirement_met ) {
            ok = false;
        }
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
        msg += string_format( _( "> %1$s%2$s %3$i</color>\\n" ), status_color( requirement_met ),
                              e.first.obj().name(), e.second );
    }
''',
"general skill bypass",
)

replace_once(
'''    if( dif_eng > 0 ) {
        if( !allow_more_eng || player_character.get_knowledge_level( skill_mechanics ) < dif_eng ) {
            ok = false;
        }
        if( allow_more_eng ) {
            //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
            nmsg += string_format( _( "> %1$s%2$s %3$i</color> for extra engines." ),
                                   status_color( player_character.get_knowledge_level( skill_mechanics ) >= dif_eng ),
                                   skill_mechanics.obj().name(), dif_eng ) + "\\n";
''',
'''    if( dif_eng > 0 ) {
        const bool engine_skill_met = editor_test_mode ||
                                      player_character.get_knowledge_level( skill_mechanics ) >= dif_eng;
        if( !allow_more_eng || !engine_skill_met ) {
            ok = false;
        }
        if( allow_more_eng ) {
            //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
            nmsg += string_format( _( "> %1$s%2$s %3$i</color> for extra engines." ),
                                   status_color( engine_skill_met ),
                                   skill_mechanics.obj().name(), dif_eng ) + "\\n";
''',
"extra engine skill bypass",
)

replace_once(
'''    if( dif_steering > 0 ) {
        if( player_character.get_knowledge_level( skill_mechanics ) < dif_steering ) {
            ok = false;
        }
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
        nmsg += string_format( _( "> %1$s%2$s %3$i</color> for extra steering axles." ),
                               status_color( player_character.get_knowledge_level( skill_mechanics ) >= dif_steering ),
                               skill_mechanics.obj().name(), dif_steering ) + "\\n";
    }
''',
'''    if( dif_steering > 0 ) {
        const bool steering_skill_met = editor_test_mode ||
                                        player_character.get_knowledge_level( skill_mechanics ) >= dif_steering;
        if( !steering_skill_met ) {
            ok = false;
        }
        //~ %1$s represents the internal color name which shouldn't be translated, %2$s is skill name, and %3$i is skill level
        nmsg += string_format( _( "> %1$s%2$s %3$i</color> for extra steering axles." ),
                               status_color( steering_skill_met ),
                               skill_mechanics.obj().name(), dif_steering ) + "\\n";
    }
''',
"steering skill bypass",
)

replace_once(
'''                msg = editor_test_mode ?
                      _( "Test mode enabled: components and tools are ignored; vehicle legality still applies." ) :
                      _( "Test mode disabled." );
''',
'''                msg = editor_test_mode ?
                      _( "Test mode enabled: components, tools, and skill requirements are ignored; vehicle legality still applies." ) :
                      _( "Test mode disabled." );
''',
"test mode toggle message",
)

replace_once(
'''bool veh_interact::run_editor_context_action( map &here, const std::string &action )
{
    close_editor_context_menu();

    if( action == "EDITOR_INSTALL" ) {
''',
'''bool veh_interact::run_editor_context_action( map &here, const std::string &action )
{
    // Context-menu actions are stored in editor_context_buttons.  The menu is
    // destroyed before dispatch, so preserve the selected action before clearing
    // that vector.  Otherwise `action` can refer to a destroyed std::string.
    const std::string selected_action = action;
    close_editor_context_menu();

    if( selected_action == "EDITOR_INSTALL" ) {
''',
"context action lifetime fix",
)

replace_once(
'''    if( action == "EDITOR_REMOVE" ) {
''',
'''    if( selected_action == "EDITOR_REMOVE" ) {
''',
"remove dispatch action",
)

replace_once(
'''    if( action == "EDITOR_REPAIR" ) {
''',
'''    if( selected_action == "EDITOR_REPAIR" ) {
''',
"repair dispatch action",
)

path.write_text(text)
