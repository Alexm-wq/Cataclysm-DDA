from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one match in {path}, found {count}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/advanced_inv.h",
    '''    // Optional exact item to focus when a world context action opens the workspace.\n    std::optional<item_location> focus;\n};''',
    '''    // Optional exact item to focus when a world context action opens the workspace.\n    std::optional<item_location> focus;\n    // Optional source override for a world tile that has both ground/furniture items\n    // and vehicle cargo.  true selects vehicle cargo; false selects map storage.\n    std::optional<bool> prefer_vehicle;\n};'''
)

replace_once(
    "src/advanced_inv.cpp",
    '''        bool show_vehicle = false;\n        if( squares[location].can_store_in_vehicle() ) {\n            const bool has_vehicle_items = !squares[location].get_vehicle_stack().empty();\n            const bool has_ground_items = !get_map().i_at( squares[location].pos ).empty();\n            show_vehicle = has_vehicle_items && !has_ground_items;\n        }''',
    '''        bool show_vehicle = false;\n        if( squares[location].can_store_in_vehicle() ) {\n            if( entry.prefer_vehicle.has_value() ) {\n                show_vehicle = *entry.prefer_vehicle;\n            } else {\n                const bool has_vehicle_items = !squares[location].get_vehicle_stack().empty();\n                const bool has_ground_items = !get_map().i_at( squares[location].pos ).empty();\n                show_vehicle = has_vehicle_items && !has_ground_items;\n            }\n        }'''
)

replace_once(
    "src/game.cpp",
    '''    std::vector<item_location> context_containers;\n    for( item &it : here.i_at( mouse_target ) ) {\n        if( it.is_container() ) {\n            context_containers.emplace_back( map_cursor( here.get_abs( mouse_target ) ), &it );\n        }\n    }\n    if( const optional_vpart_position vp = here.veh_at( mouse_target ) ) {\n        if( const std::optional<vpart_reference> cargo = vp.cargo() ) {\n            vehicle_cursor cursor( cargo->vehicle(), cargo->part_index() );\n            auto cargo_items = cargo->items();\n            for( item &it : cargo_items ) {\n                if( it.is_container() ) {\n                    context_containers.emplace_back( cursor, &it );\n                }\n            }\n        }\n    }''',
    '''    // Preserve the actual world-storage hierarchy.  Items on CONTAINER furniture\n    // are contents of that furniture, and items in vehicle cargo are contents of that\n    // cargo part; neither should become dozens of top-level world context actions.\n    const bool furniture_storage = here.has_furn( mouse_target ) &&\n                                   here.has_flag( ter_furn_flag::TFLAG_CONTAINER, mouse_target );\n    std::optional<vpart_reference> vehicle_storage;\n    if( const optional_vpart_position vp = here.veh_at( mouse_target ) ) {\n        vehicle_storage = vp.cargo();\n    }\n\n    std::vector<item_location> context_containers;\n    if( !furniture_storage ) {\n        for( item &it : here.i_at( mouse_target ) ) {\n            if( it.is_container() ) {\n                context_containers.emplace_back( map_cursor( here.get_abs( mouse_target ) ), &it );\n            }\n        }\n    }\n    // Vehicle cargo is itself the top-level storage object.  Its nested item\n    // containers remain available after opening the cargo workspace.\n'''
)

replace_once(
    "src/game.cpp",
    '''    if( is_adjacent && can_interact_at( ACTION_CLOSE, here, mouse_target ) ) {\n        entries.emplace_back( string_format( _( "Close %s" ), structural_name ),\n                              action_ident( ACTION_CLOSE ) );\n    }\n\n    // Every physical top-level container gets its own action.''',
    '''    if( is_adjacent && can_interact_at( ACTION_CLOSE, here, mouse_target ) ) {\n        entries.emplace_back( string_format( _( "Close %s" ), structural_name ),\n                              action_ident( ACTION_CLOSE ) );\n    }\n\n    if( is_adjacent && furniture_storage &&\n        !here.has_flag( ter_furn_flag::TFLAG_SEALED, mouse_target ) ) {\n        entries.emplace_back( string_format( _( "Open %s" ), here.furnname( mouse_target ) ),\n                              "CONTEXT_FURNITURE_STORAGE" );\n    }\n    if( is_adjacent && vehicle_storage ) {\n        entries.emplace_back( string_format( _( "Open %s" ), vehicle_storage->info().name() ),\n                              "CONTEXT_VEHICLE_STORAGE" );\n    }\n\n    // Every loose top-level container gets its own action.  Containers inside\n    // furniture or vehicle storage are intentionally one level deeper.'''
)

replace_once(
    "src/game.cpp",
    '''    if( is_adjacent && can_interact_at( ACTION_PICKUP, here, mouse_target ) ) {\n        add_action( ACTION_PICKUP );\n    }''',
    '''    if( is_adjacent && !furniture_storage && !vehicle_storage &&\n        can_interact_at( ACTION_PICKUP, here, mouse_target ) ) {\n        add_action( ACTION_PICKUP );\n    }'''
)

replace_once(
    "src/game.cpp",
    '''        const auto container_action = container_actions.find( result.entry->id );\n        if( container_action != container_actions.end() ) {''',
    '''        if( result.entry->id == "CONTEXT_FURNITURE_STORAGE" ) {\n            context_menu.close();\n            create_advanced_inv( { inventory_workspace_preset::pickup, mouse_target,\n                                   std::nullopt, false } );\n            return false;\n        }\n        if( result.entry->id == "CONTEXT_VEHICLE_STORAGE" ) {\n            context_menu.close();\n            create_advanced_inv( { inventory_workspace_preset::pickup, mouse_target,\n                                   std::nullopt, true } );\n            return false;\n        }\n\n        const auto container_action = container_actions.find( result.entry->id );\n        if( container_action != container_actions.end() ) {'''
)

Path("/tmp/branch_patch_commit_message").write_text("Respect storage hierarchy in world context menu\n")
print("world storage hierarchy patched")
