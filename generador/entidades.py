"""Population entities (entidades de población) of the INE street register: writes datos/entidades.csv
from the population units file (UP…) of the same ZIP that codigos_postales reads its street sections
from (design §4.1). One row per entity: identifier, 12-digit code and the name as the INE writes it;
the library takes the level and the parent from the code (python/territorios_es/entities.py).
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter

from territorios_es.entities import ENTITY_HEADER, ENTITY_LEVELS, entity_code, entity_level

from .codigos_postales import ine_register_file

FILE = "entidades.csv"
# Fixed width (cp1252): code at 0–12; names of the collective entity, the singular entity and the
# nucleus (or «*DISEMINADO*») at these positions.
NAMES = {"collective_entity": (169, 239), "singular_entity": (314, 384), "nucleus": (459, 529),
         "scattered": (459, 529)}
LEVEL_NAMES = {"collective_entity": "colectivas", "singular_entity": "singulares", "nucleus": "núcleos",
               "scattered": "diseminados"}
SECTION = "Entidades de población que no se publican"
_CODE = re.compile(r"[0-9]{12}")


def parse_units(content: bytes) -> list[tuple[str, str]]:
    """[(12-digit code, official name)] of the entities in the population units file of the street
    register ZIP, read line by line. Municipality rows are left out."""
    archive, name = ine_register_file(content, "UP", "unidades poblacionales")
    units, lines, odd = [], 0, 0
    with archive.open(name) as stream:
        for raw in stream:
            lines += 1
            line = raw.decode("cp1252")
            code = line[0:12]
            if not _CODE.fullmatch(code):
                odd += 1
                continue
            level = entity_level(entity_code(code))
            if level is not None:
                start, end = NAMES[level]
                units.append((code, line[start:end].strip()))
    if not units or odd > lines * 0.01:
        raise ValueError(f"INE: {odd} de {lines} unidades poblacionales sin la forma esperada")
    return units


def build(units: list[tuple[str, str]], data: dict) -> tuple[list[list[str]], list[str], dict[str, int]]:
    """(rows of entidades.csv sorted by code, what is left out and why, count per level). An entity is
    left out if its municipality is not in the catalogue, it has no name, its code is repeated or
    its parent entity is missing: the library would refuse the table."""
    municipalities = {t["codes"]["ine:municipio"] for t in data["territories"]
                      if t["level"] == "municipality" and "ine:municipio" in t.get("codes", {})}
    kept, left_out, seen = {}, [], set()
    for code, name in sorted(units):
        short = entity_code(code)
        if short in seen:
            left_out.append(f"{code}: código repetido")
            continue
        seen.add(short)
        if code[:5] not in municipalities:
            left_out.append(f"{code} {name}: el municipio {code[:5]} no está en el catálogo")
        elif not name:
            left_out.append(f"{code}: sin nombre")
        else:
            kept[short] = [f"es:entidad:{short}", code, name]
    # Parents before children: collective, singular, nucleus or scattered part.
    for short in sorted(kept, key=lambda c: ENTITY_LEVELS.index(entity_level(c))):
        level = entity_level(short)
        parent = (short[:7] + "0000" if level == "singular_entity" and short[5:7] != "00"
                  else short[:9] + "00" if level in ("nucleus", "scattered") else None)
        if parent is not None and parent not in kept:
            left_out.append(f"{kept[short][1]} {kept[short][2]}: falta su entidad {parent}")
            del kept[short]
    rows = [kept[short] for short in sorted(kept, key=lambda c: kept[c][1])]
    counts = Counter(entity_level(entity_code(row[1])) for row in rows)
    return rows, left_out, {level: counts[level] for level in ENTITY_LEVELS}


def table(rows: list[list[str]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(ENTITY_HEADER)
    writer.writerows(rows)
    return out.getvalue()


def summary(counts: dict[str, int]) -> str:
    return ", ".join(f"{n:,}".replace(",", ".") + f" {LEVEL_NAMES[level]}" for level, n in counts.items())
