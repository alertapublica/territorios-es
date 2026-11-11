"""Ministerio de Justicia: the Censo Judicial (XLSX), with the judicial district (partido judicial)
of every municipality, its seat and the date of the last update."""
from __future__ import annotations

import re

from .xlsx import read_rows

# Columns used: province, district number within the province, seat municipality, municipality and
# the mark of the seat («SI»). The header writes some names on two lines.
COLUMNS = {"CPRO": "province", "PJ": "number", "CODM PJ": "seat", "CODM": "municipality", "CPJ": "is_seat"}


def parse_census(content: bytes) -> tuple[list[list[str]], str | None]:
    """([[municipality code5, district code (province + number, 4 digits), seat code5], …], date of
    the «Actualizado a dd/mm/yyyy» line as yyyy-mm-dd or None). Raises ValueError if the table does
    not hold together: each district has one seat, in its province, marked as such."""
    rows = read_rows(content)
    if not rows:
        raise ValueError("Censo Judicial: hoja vacía")
    header = [" ".join(cell.split()) for cell in rows[0]]
    missing = [name for name in COLUMNS if name not in header]
    if missing:
        raise ValueError(f"Censo Judicial: faltan las columnas {missing}")
    at = {COLUMNS[name]: header.index(name) for name in COLUMNS}
    result, updated, seats, district_of = [], None, {}, {}
    for row in rows[1:]:
        cells = {key: (row[i].strip() if i < len(row) else "") for key, i in at.items()}
        if not any(cells.values()):
            stamp = re.search(r"Actualizado a (\d{2})/(\d{2})/(\d{4})", " ".join(row))
            if stamp:
                updated = f"{stamp[3]}-{stamp[2]}-{stamp[1]}"
            continue
        # The XLSX writes the province and the number without their leading zero.
        province, number = cells["province"].zfill(2), cells["number"].zfill(2)
        municipality, seat = cells["municipality"], cells["seat"]
        if (not re.fullmatch(r"[0-9]{5}", municipality) or not re.fullmatch(r"[0-9]{5}", seat)
                or not re.fullmatch(r"[0-9]{2}", province) or not re.fullmatch(r"0?[1-9]|[1-9][0-9]", cells["number"])
                or municipality[:2] != province or seat[:2] != province or municipality in district_of
                or (cells["is_seat"] == "SI") != (municipality == seat) or cells["is_seat"] not in ("", "SI")):
            raise ValueError(f"Censo Judicial: fila no válida o repetida: {row[:12]}")
        district = province + number
        district_of[municipality] = district
        if seats.setdefault(district, seat) != seat:
            raise ValueError(f"Censo Judicial: el partido {district} tiene varias sedes ({seats[district]}, {seat})")
        result.append([municipality, district, seat])
    if not result:
        raise ValueError("Censo Judicial: sin municipios")
    missing_seats = sorted(d for d, seat in seats.items() if district_of.get(seat) != d)
    if missing_seats:
        raise ValueError(f"Censo Judicial: partidos con la sede fuera de la tabla o en otro partido: {missing_seats}")
    return result, updated
