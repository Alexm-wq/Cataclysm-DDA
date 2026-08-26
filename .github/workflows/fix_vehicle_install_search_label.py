from pathlib import Path

path = Path("src/veh_interact.cpp")
text = path.read_text()
old = 'const std::string search_text = install_info->filter.empty() ? _( "all" ) : install_info->filter;'
new = 'const std::string search_text = install_info->filter.empty() ? _( "All parts" ) : install_info->filter;'
if text.count(old) != 1:
    raise RuntimeError(f"expected exactly one search placeholder, found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
