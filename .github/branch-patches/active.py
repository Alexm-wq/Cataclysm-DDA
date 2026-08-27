from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/crafting_gui.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''    const auto recipe_category_identity = []( const recipe *rec ) {\n        if( rec == nullptr ) {\n            return std::make_pair( std::string(), std::string() );\n        }\n        if( const crafting_group *group = crafting_group_for_recipe( rec->ident() ) ) {\n            return std::make_pair( group->category.str(), group->subcategory );\n        }\n        return std::make_pair( rec->category.str(), rec->subcategory );\n    };\n''',
    '''    std::map<recipe_id, std::pair<std::string, std::string>> legacy_group_identity;\n    const auto recipe_category_identity = [&]( const recipe *rec ) {\n        if( rec == nullptr ) {\n            return std::make_pair( std::string(), std::string() );\n        }\n        if( const crafting_group *group = crafting_group_for_recipe( rec->ident() ) ) {\n            return std::make_pair( group->category.str(), group->subcategory );\n        }\n        const auto legacy = legacy_group_identity.find( rec->ident() );\n        if( legacy != legacy_group_identity.end() ) {\n            return legacy->second;\n        }\n        return std::make_pair( rec->category.str(), rec->subcategory );\n    };\n''',
    "legacy category identity map",
)

text = replace_once(
    text,
    '''    const recipe_subset &available_recipes =\n        crafter->get_group_available_recipes( inventory_override );\n    if( uistate.crafting_browser_recipe.is_valid() ) {\n''',
    '''    const recipe_subset &available_recipes =\n        crafter->get_group_available_recipes( inventory_override );\n\n    // Mods can still use the legacy nested-category mechanism without defining\n    // crafting_group metadata.  Preserve those concrete recipes by inheriting\n    // the first real category/subcategory from their nested parent.  Base-game\n    // recipes with explicit crafting_group metadata always take precedence.\n    std::set<recipe_id> legacy_nested_visiting;\n    std::function<void( const recipe *, std::pair<std::string, std::string> )> map_legacy_nested;\n    map_legacy_nested = [&]( const recipe *parent, std::pair<std::string, std::string> inherited ) {\n        if( parent == nullptr || !parent->is_nested() ||\n            !legacy_nested_visiting.insert( parent->ident() ).second ) {\n            return;\n        }\n        if( parent->category.str() != "CC_*" && parent->subcategory != "CSC_*_NESTED" ) {\n            inherited = std::make_pair( parent->category.str(), parent->subcategory );\n        }\n        for( const recipe_id &child_id : parent->nested_category_data ) {\n            const recipe *child = &child_id.obj();\n            if( child->is_nested() ) {\n                map_legacy_nested( child, inherited );\n            } else if( crafting_group_for_recipe( child_id ) == nullptr &&\n                       !inherited.first.empty() && inherited.first != "CC_*" ) {\n                legacy_group_identity.emplace( child_id, inherited );\n            }\n        }\n        legacy_nested_visiting.erase( parent->ident() );\n    };\n    for( const recipe *rec : available_recipes ) {\n        if( rec != nullptr && rec->is_nested() && rec->category.str() != "CC_*" ) {\n            map_legacy_nested( rec, std::make_pair( rec->category.str(), rec->subcategory ) );\n        }\n    }\n\n    if( uistate.crafting_browser_recipe.is_valid() ) {\n''',
    "build legacy nested fallback map",
)

path.write_text(text, encoding="utf-8")
Path("/tmp/branch_patch_commit_message").write_text(
    "Preserve legacy mod recipe groups in crafting browser\n", encoding="utf-8"
)
