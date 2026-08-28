from pathlib import Path


def replace_once(path_str: str, old: str, new: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one block in {path_str}, found {count}: {old[:180]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    "src/vehicle.h",
    '''        std::string name( bool with_prefix = true ) const;\n\n        struct carried_part_data {\n''',
    '''        std::string name( bool with_prefix = true ) const;\n\n        /** Optional player-defined label for this exact installed component. */\n        std::optional<std::string> get_label() const;\n        /** Set the component label; an empty string removes it. */\n        void set_label( const std::string &text );\n\n        struct carried_part_data {\n'''
)

replace_once(
    "src/vehicle_part.cpp",
    '''std::string vehicle_part::name( bool with_prefix ) const\n{\n''',
    '''std::optional<std::string> vehicle_part::get_label() const\n{\n    static const std::string key = "vehicle_part_label";\n    const std::string value = base.get_var( key );\n    return value.empty() ? std::nullopt : std::make_optional( value );\n}\n\nvoid vehicle_part::set_label( const std::string &text )\n{\n    static const std::string key = "vehicle_part_label";\n    if( text.empty() ) {\n        base.remove_var( key );\n    } else {\n        base.set_var( key, text );\n    }\n}\n\nstd::string vehicle_part::name( bool with_prefix ) const\n{\n'''
)

replace_once(
    "src/veh_interact.h",
    '''        struct reshape_info_t;\n\n        std::unique_ptr<reshape_info_t> reshape_info;\n\n        struct refuel_info_t;\n''',
    '''        struct reshape_info_t;\n\n        std::unique_ptr<reshape_info_t> reshape_info;\n\n        struct relabel_info_t;\n        std::unique_ptr<relabel_info_t> relabel_info;\n\n        struct refuel_info_t;\n'''
)

replace_once(
    "src/veh_interact.h",
    '''        bool apply_reshape_variant();\n        bool handle_reshape_mouse( const std::string &action );\n        void refresh_refuel_sources( map &here );\n''',
    '''        bool apply_reshape_variant();\n        bool handle_reshape_mouse( const std::string &action );\n        void open_relabel_mode( bool part_mode );\n        void close_relabel_mode();\n        void sync_relabel_selection();\n        void edit_relabel_text();\n        bool apply_relabel();\n        bool handle_relabel_mouse( const std::string &action );\n        void refresh_refuel_sources( map &here );\n'''
)

replace_once(
    "src/veh_interact.h",
    '''        void display_part_details();\n        void display_reshape_pane();\n        void display_stats( map &here ) const;\n''',
    '''        void display_part_details();\n        void display_reshape_pane();\n        void display_relabel_pane();\n        void display_stats( map &here ) const;\n'''
)

Path("/tmp/branch_patch_commit_message").write_text(
    "Add per-part vehicle label model\n", encoding="utf-8"
)
