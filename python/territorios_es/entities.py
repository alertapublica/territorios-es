"""Population entities (entidades de población) of the INE street register, from datos/entidades.csv.
js/entities.js mirrors this file.

    cat = te.load_entities()                                      # territories and entities
    cat.search("A Devesa", levels=["singular_entity"])            # each candidate with its municipality
    cat.resolve("ine:entidad", "36038010100")["ancestors"][:2]    # its parish (ALBA) and Pontevedra

Four levels below the municipality (design §4.1): the collective entity (the parishes of Galicia and
Asturias…, only where there are any), the singular entity, and the nucleus and the scattered part
(diseminado) of a singular entity. The table has the identifier, frozen the first time it is given
(§4.6), the 12-digit code of the street register and the official name as the INE writes it, in
capitals and with the article in brackets. The level and the parent come out of the code: province
and municipality (5), collective (2), singular (2), check digit (1), nucleus (2; 99 is the scattered
part). The 11-digit code (`ine:entidad`) leaves out the check digit, as the IGN and Wikidata do.
"""
from __future__ import annotations

import csv
import io
import re

from .text import display_name

ENTITY_HEADER = ["id", "ine_dc", "official"]
ENTITY_LEVELS = ("collective_entity", "singular_entity", "nucleus", "scattered")
_CODE = re.compile(r"[0-9]{12}")


def entity_code(code: str) -> str:
    """12 digits of the street register -> 11 of the INE without the check digit."""
    return code[:9] + code[10:]


def entity_level(code: str) -> str | None:
    """Level of an 11-digit code; None for a municipality or a code that is not an entity."""
    collective, singular, nucleus = code[5:7], code[7:9], code[9:11]
    if singular == "00":
        return "collective_entity" if collective != "00" and nucleus == "00" else None
    if nucleus == "00":
        return "singular_entity"
    return "scattered" if nucleus == "99" else "nucleus"


def entity_records(text: str, municipality_id) -> list[dict]:
    """Records in the shape of territorios.json for the rows of entidades.csv. `municipality_id`
    gives the identifier of a municipality from its INE code (None if it does not exist)."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or rows[0] != ENTITY_HEADER:
        raise ValueError("Not an entidades.csv table")
    by_code, found = {}, []
    for row in rows[1:]:
        if len(row) != len(ENTITY_HEADER) or not _CODE.fullmatch(row[1]) or not row[0] or not row[2]:
            raise ValueError(f"Invalid row {row}")
        code = entity_code(row[1])
        level, municipality = entity_level(code), municipality_id(code[:5])
        if level is None or municipality is None or code in by_code:
            raise ValueError(f"Not an entity of a known municipality, or repeated: {row}")
        by_code[code] = row[0]
        found.append((row, code, level, municipality))
    records = []
    for row, code, level, municipality in found:
        collective = by_code.get(code[:7] + "0000") if code[5:7] != "00" else municipality
        parent = {"collective_entity": municipality, "singular_entity": collective}.get(
            level, by_code.get(code[:9] + "00"))
        if collective is None or parent is None:
            raise ValueError(f"Missing parent entity of {row[0]}")
        record = {"id": row[0], "level": level, "parent": parent,
                  "codes": {"ine:entidad": code, "ine:entidad:dc": row[1]},
                  "names": {"official": row[2], "display": display_name(row[2]), "reviewed": False},
                  "municipality": municipality}
        if collective != municipality and level != "collective_entity":
            record["collective_entity"] = collective
        records.append(record)
    return records
