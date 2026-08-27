from ..write_text import write_text


def parse_crafting_group(json, origin):
    write_text(json["name"], origin,
               comment="Section heading in the crafting browser")
