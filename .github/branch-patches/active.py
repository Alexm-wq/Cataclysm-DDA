from pathlib import Path

def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    p.write_text(text.replace(old, new, 1))

# UI_TEST_MODE makes construction economically free for UI testing while keeping
# real target/precondition rules.  This lets contextual actions be exercised on
# the correct world objects without requiring debug inventories or skill setup.
replace_once(
    "src/construction.cpp",
    """bool player_can_build( Character &you, const read_only_visitable &inv, const construction &con,
                       const bool can_construct_skip )
{
    if( you.has_trait( trait_DEBUG_HS ) ) {
        return true;
    }
""",
    """bool player_can_build( Character &you, const read_only_visitable &inv, const construction &con,
                       const bool can_construct_skip )
{
    if( you.has_trait( trait_DEBUG_HS ) || get_option<bool>( "UI_TEST_MODE" ) ) {
        return true;
    }
"""
)

replace_once(
    "src/construction.cpp",
    """bool player_can_see_to_build( Character &you, const construction_group_str_id &group )
{
    if( you.fine_detail_vision_mod() < 4 || you.has_trait( trait_DEBUG_HS ) ) {
        return true;
    }
""",
    """bool player_can_see_to_build( Character &you, const construction_group_str_id &group )
{
    if( you.fine_detail_vision_mod() < 4 || you.has_trait( trait_DEBUG_HS ) ||
        get_option<bool>( "UI_TEST_MODE" ) ) {
        return true;
    }
"""
)

replace_once(
    "src/construction.cpp",
    """ret_val<void> start_construction_at( Character &who, const construction &con,
                                     const tripoint_bub_ms &target )
{
    map &here = get_map();
""",
    """ret_val<void> start_construction_at( Character &who, const construction &con,
                                     const tripoint_bub_ms &target )
{
    map &here = get_map();
    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );
"""
)

replace_once(
    "src/construction.cpp",
    """    if( who.fine_detail_vision_mod() >= 4 && !who.has_trait( trait_DEBUG_HS ) &&
        !con.dark_craftable ) {
        return ret_val<void>::make_failure( _( "It is too dark to construct right now." ) );
    }

    std::list<item> used;
    partial_con pc;
    pc.id = con.id;
    if( who.has_trait( trait_DEBUG_HS ) ) {
""",
    """    if( who.fine_detail_vision_mod() >= 4 && !who.has_trait( trait_DEBUG_HS ) &&
        !free_test_mode && !con.dark_craftable ) {
        return ret_val<void>::make_failure( _( "It is too dark to construct right now." ) );
    }

    std::list<item> used;
    partial_con pc;
    pc.id = con.id;
    if( who.has_trait( trait_DEBUG_HS ) || free_test_mode ) {
"""
)

replace_once(
    "src/construction.cpp",
    """    pc.components = std::move( used );
    here.partial_con_set( target, pc );
    for( const std::vector<tool_comp> &tools : con.requirements->get_tools() ) {
        who.consume_tools( tools );
    }
""",
    """    pc.components = std::move( used );
    here.partial_con_set( target, pc );
    if( !free_test_mode ) {
        for( const std::vector<tool_comp> &tools : con.requirements->get_tools() ) {
            who.consume_tools( tools );
        }
    }
"""
)

# Keep the map resolver consistent with execution: test mode candidates are ready
# regardless of skills/inventory/darkness, but can_construct() still decides whether
# the clicked tile is semantically applicable.
replace_once(
    "src/construction_target.cpp",
    """#include "construction.h"
#include "map.h"
#include "translations.h"
""",
    """#include "construction.h"
#include "map.h"
#include "options.h"
#include "translations.h"
"""
)

replace_once(
    "src/construction_target.cpp",
    """static candidate_rank rank_candidate( Character &who, const read_only_visitable &inventory,
                                      const construction &candidate )
{
    candidate_rank rank;
    rank.candidate = &candidate;
    rank.meets_skills = who.meets_skill_requirements( candidate );
    for( const std::pair<const skill_id, int> &required : candidate.required_skills ) {
        rank.skill_deficit += std::max( 0.0f,
                                        required.second - who.get_skill_level( required.first ) );
    }
    rank.has_requirements = candidate.requirements->can_make_with_inventory(
                                inventory, is_crafting_component, 1, craft_flags::none, false );
    const bool eligible = player_can_build( who, inventory, candidate, true );
    rank.blocked_by_darkness = eligible && who.fine_detail_vision_mod() >= 4 &&
                               !who.has_trait( trait_DEBUG_HS ) && !candidate.dark_craftable;
    rank.ready = eligible && !rank.blocked_by_darkness;
    return rank;
}
""",
    """static candidate_rank rank_candidate( Character &who, const read_only_visitable &inventory,
                                      const construction &candidate )
{
    const bool free_test_mode = get_option<bool>( "UI_TEST_MODE" );
    candidate_rank rank;
    rank.candidate = &candidate;
    rank.meets_skills = free_test_mode || who.meets_skill_requirements( candidate );
    if( !free_test_mode ) {
        for( const std::pair<const skill_id, int> &required : candidate.required_skills ) {
            rank.skill_deficit += std::max( 0.0f,
                                            required.second - who.get_skill_level( required.first ) );
        }
    }
    rank.has_requirements = free_test_mode || candidate.requirements->can_make_with_inventory(
                                inventory, is_crafting_component, 1, craft_flags::none, false );
    const bool eligible = free_test_mode || player_can_build( who, inventory, candidate, true );
    rank.blocked_by_darkness = !free_test_mode && eligible && who.fine_detail_vision_mod() >= 4 &&
                               !who.has_trait( trait_DEBUG_HS ) && !candidate.dark_craftable;
    rank.ready = eligible && !rank.blocked_by_darkness;
    return rank;
}
"""
)

# Make the testing behavior explicit in the inspector while retaining the real
# requirement lists underneath for layout/usability testing.
replace_once(
    "src/construction_ui.cpp",
    """    add( target_description );

    if( operation == construction_operation::build && !context_actions.empty() ) {
""",
    """    add( target_description );
    if( get_option<bool>( "UI_TEST_MODE" ) ) {
        add( colorize( _( "UI test mode: skills, tools and components are free." ), c_light_blue ) );
    }

    if( operation == construction_operation::build && !context_actions.empty() ) {
"""
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Make construction free in UI test mode [skip ci]\n"
)
