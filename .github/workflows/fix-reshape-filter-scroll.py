from pathlib import Path

CPP = Path('src/veh_interact.cpp')
text = CPP.read_text()


def rep(old, new, label, count=1):
    global text
    found = text.count(old)
    if found != count:
        raise SystemExit(f'{label}: expected {count} match(es), got {found}')
    text = text.replace(old, new, count)


helper_anchor = '''static void act_vehicle_unload_fuel( map &here, vehicle *veh );\n'''
helper = r'''static bool reshape_part_has_visible_variants( const vpart_info &vpi )
{
    if( vpi.variants.size() <= 1 ) {
        return false;
    }
#if defined(TILES)
    // Vehicle-part JSON can inherit a generic superset of cosmetic variants that
    // the active tileset does not actually author for this visual family.  Treat
    // only variants with a resolvable vehicle-part tile as reshape choices.
    int visible = 0;
    for( const auto &[variant_id, variant] : vpi.variants ) {
        ( void )variant;
        if( has_vehicle_part_preview_tile( vpi.id.str(), variant_id ) && ++visible > 1 ) {
            return true;
        }
    }
    return false;
#else
    return true;
#endif
}

static void act_vehicle_unload_fuel( map &here, vehicle *veh );
'''
rep(helper_anchor, helper, 'reshape visibility helper anchor')

# Current-selection entry and context-menu eligibility use the exact selected part.
# Replace every raw selected-part test so right-click and reshape entry agree.
raw_selected = 'part.info().variants.size() > 1'
selected_count = text.count(raw_selected)
if selected_count < 1:
    raise SystemExit('selected-part reshape checks not found')
text = text.replace(raw_selected, 'reshape_part_has_visible_variants( part.info() )')

# Reshape inspector filter.
rep('''if( !vp.removed && vp.info().variants.size() > 1 ) {\n''',
    '''if( !vp.removed && reshape_part_has_visible_variants( vp.info() ) ) {\n''',
    'reshape inspector predicate')

# Synchronization must use the same tileset-aware predicate and only populate
# variants that really exist in the active visual family.
rep('''    if( vpi.variants.size() <= 1 ) {\n        return;\n    }\n\n    for( const auto &[variant_id, variant] : vpi.variants ) {\n        ( void )variant;\n        reshape_info->variants.push_back( variant_id );\n    }\n''',
    '''    if( !reshape_part_has_visible_variants( vpi ) ) {\n        return;\n    }\n\n    for( const auto &[variant_id, variant] : vpi.variants ) {\n        ( void )variant;\n#if defined(TILES)\n        if( !has_vehicle_part_preview_tile( vpi.id.str(), variant_id ) ) {\n            continue;\n        }\n#endif\n        reshape_info->variants.push_back( variant_id );\n    }\n''',
    'reshape variant population')

# Mouse-wheel scrolling must be independent from the currently selected row.
# The previous redraw-time follow logic pulled the list back to variant_pos and
# made the scrollbar appear unable to reach either end.
rep('''        if( reshape_info->variant_pos < reshape_info->variant_scroll ) {\n            reshape_info->variant_scroll = reshape_info->variant_pos;\n        } else if( visible > 0 && reshape_info->variant_pos >= reshape_info->variant_scroll + visible ) {\n            reshape_info->variant_scroll = reshape_info->variant_pos - visible + 1;\n        }\n\n''',
    '',
    'remove reshape selection-follow scroll clamp')

# Structural validation.
assert 'reshape_part_has_visible_variants( const vpart_info &vpi )' in text
assert 'has_vehicle_part_preview_tile( vpi.id.str(), variant_id )' in text
assert 'vp.info().variants.size() > 1' not in text
assert 'reshape_info->variant_scroll = reshape_info->variant_pos - visible + 1' not in text
assert '.viewport_pos( reshape_info->variant_scroll ).viewport_size( visible ).apply( w_msg );' in text

CPP.write_text(text)
print(f'patched selected-part reshape checks: {selected_count}')
