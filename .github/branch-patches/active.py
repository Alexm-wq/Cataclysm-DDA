from pathlib import Path


path = Path("src/sdltiles.cpp")
text = path.read_text(encoding="utf-8")
old = '''    } else if( font && utf8_width( button.icon ) == 1 ) {\n        const int pair = std::clamp( button.icon_color_pair, 0,\n                         static_cast<int>( cata_cursesport::colorpairs.size() ) - 1 );\n        const int left = button.pos_pixels.x + ( button.size_pixels.x - font->width ) / 2;\n        const int top = button.pos_pixels.y + ( button.size_pixels.y - font->height ) / 2;\n        draw_string( *font, renderer, geometry, button.icon, point( left, top ),\n                     cata_cursesport::colorpairs[pair].FG );\n    }\n'''
new = '''    } else if( font && utf8_width( button.icon ) == 1 ) {\n        const int pair = std::clamp( button.icon_color_pair, 0,\n                         static_cast<int>( cata_cursesport::colorpairs.size() ) - 1 );\n        const int left = button.pos_pixels.x + ( button.size_pixels.x - font->width ) / 2;\n        const int top = button.pos_pixels.y + ( button.size_pixels.y - font->height ) / 2;\n        font->OutputChar( renderer, geometry, button.icon, point( left, top ),\n                          static_cast<unsigned char>( cata_cursesport::colorpairs[pair].FG ) );\n    }\n'''
if old not in text:
    raise SystemExit("expected key-glyph draw_string block not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
