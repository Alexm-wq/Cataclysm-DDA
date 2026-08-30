from pathlib import Path

p = Path("src/construction.cpp")
text = p.read_text()
old = """    if( who.fine_detail_vision_mod() >= 4 && !who.has_trait( trait_DEBUG_HS ) &&
        !con.dark_craftable ) {
        return ret_val<void>::make_failure( _( "It is too dark to construct right now." ) );
    }

    who.assign_activity( ACT_BUILD );
"""
new = """    if( who.fine_detail_vision_mod() >= 4 && !who.has_trait( trait_DEBUG_HS ) &&
        !get_option<bool>( "UI_TEST_MODE" ) && !con.dark_craftable ) {
        return ret_val<void>::make_failure( _( "It is too dark to construct right now." ) );
    }

    who.assign_activity( ACT_BUILD );
"""
if text.count(old) != 1:
    raise RuntimeError(f"expected one resume darkness block, found {text.count(old)}")
p.write_text(text.replace(old, new, 1))
Path("/tmp/branch_patch_commit_message").write_text(
    "Make resumed construction free in UI test mode [skip ci]\n"
)
