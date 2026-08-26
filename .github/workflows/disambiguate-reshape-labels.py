from pathlib import Path

path = Path('src/veh_interact.cpp')
text = path.read_text()

old = '''            const bool selected = index == reshape_info->variant_pos;\n            const bool committed = id == reshape_info->committed_variant;\n            const std::string label = variant.get_label().empty() ? _( "Default" ) : variant.get_label();\n\n            if( selected ) {\n'''
new = '''            const bool selected = index == reshape_info->variant_pos;\n            const bool committed = id == reshape_info->committed_variant;\n            const std::string base_label = variant.get_label().empty() ? _( "Default" ) : variant.get_label();\n\n            // Vehicle JSON can legitimately define multiple distinct variant IDs with\n            // the same human-readable label (for example front_left and nw are both\n            // \"Front Left\" on doors).  Preserve every real variant, but disambiguate\n            // duplicate labels in this browser so their different tile previews are not\n            // presented as accidental duplicates.  Unique labels remain untouched.\n            const int duplicate_count = static_cast<int>( std::count_if(\n                                            reshape_info->variants.begin(), reshape_info->variants.end(),\n            [&]( const std::string &other_id ) {\n                const vpart_variant &other = vpi.variants.at( other_id );\n                const std::string other_label = other.get_label().empty() ? _( "Default" ) : other.get_label();\n                return other_label == base_label;\n            } ) );\n            std::string label = base_label;\n            if( duplicate_count > 1 ) {\n                std::string qualifier;\n                if( id == "nw" ) {\n                    qualifier = _( "northwest" );\n                } else if( id == "ne" ) {\n                    qualifier = _( "northeast" );\n                } else if( id == "sw" ) {\n                    qualifier = _( "southwest" );\n                } else if( id == "se" ) {\n                    qualifier = _( "southeast" );\n                } else {\n                    qualifier = id;\n                    std::replace( qualifier.begin(), qualifier.end(), '_', '-' );\n                }\n                label += " (" + qualifier + ")";\n            }\n\n            if( selected ) {\n'''

count = text.count(old)
if count != 1:
    raise SystemExit(f'expected exactly one reshape label block, found {count}')
text = text.replace(old, new, 1)
path.write_text(text)
