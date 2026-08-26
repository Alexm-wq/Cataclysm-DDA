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
    '#include <array>\n#include <cmath>\n',
    '#include <array>\n#include <chrono>\n#include <cmath>\n',
    'chrono include',
)

replace_once(
'''struct veh_interact::install_info_t {
    int pos = 0;
    std::vector<const vpart_info *> tab_vparts;
    std::string filter;
    bool available_materials_only = false;
    bool show_all = false;
    bool dirty = true;
    bool selected_can_install = false;
    std::map<std::string, bool> materials_available;
};
''',
'''struct veh_interact::install_info_t {
    int pos = 0;
    std::vector<const vpart_info *> tab_vparts;
    std::string filter;
    bool available_materials_only = false;
    bool show_all = false;
    bool dirty = true;
    bool selected_can_install = false;
    std::map<std::string, bool> materials_available;
    std::string last_clicked_part;
    std::optional<std::chrono::steady_clock::time_point> last_click_time;
};
''',
    'install double-click state',
)

replace_once(
'''    if( !install_info || !install_info->dirty ) {
        return;
    }

    std::string previous_id = install_selected_part_cache;
''',
'''    if( !install_info || !install_info->dirty ) {
        return;
    }

    // A rebuilt list can represent another mount, layer, system or search.  Do
    // not let the first click in the new list complete a double-click started
    // against the previous candidate set.
    install_info->last_clicked_part.clear();
    install_info->last_click_time.reset();

    std::string previous_id = install_selected_part_cache;
''',
    'clear double-click state on candidate rebuild',
)

replace_once(
'''                if( row >= 0 && row < static_cast<int>( install_info->tab_vparts.size() ) ) {
                    install_info->pos = row;
                    sync_install_selection( here );
                }
                return true;
''',
'''                if( row >= 0 && row < static_cast<int>( install_info->tab_vparts.size() ) ) {
                    const vpart_info *const clicked_part = install_info->tab_vparts[row];
                    const std::string clicked_id = clicked_part != nullptr ? clicked_part->id.str() : std::string();
                    const auto now = std::chrono::steady_clock::now();
                    const bool double_click = !clicked_id.empty() &&
                                              install_info->last_clicked_part == clicked_id &&
                                              install_info->last_click_time.has_value() &&
                                              now - *install_info->last_click_time <= std::chrono::milliseconds( 500 );

                    install_info->pos = row;
                    sync_install_selection( here );

                    if( double_click ) {
                        install_info->last_clicked_part.clear();
                        install_info->last_click_time.reset();
                        confirm_install( here );
                    } else {
                        install_info->last_clicked_part = clicked_id;
                        install_info->last_click_time = now;
                    }
                }
                return true;
''',
    'double-click install row',
)

path.write_text(text)
