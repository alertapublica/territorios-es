"""Comarcas: which municipalities belong to each comarca, from the two communities that publish it
every month with INE codes. Idescat for Catalonia (comarcas and Aran) and Aragón Open Data for
Aragon. The list of comarcas, and the members in Álava and El Bierzo, are in fuentes/."""
from __future__ import annotations

import csv
import io
import re


def _members(rows, municipality: str, comarca: str, label: str) -> list[list[str]]:
    result, seen = [], set()
    for row in rows:
        code, number = (row.get(municipality) or "").strip(), (row.get(comarca) or "").strip()
        if not re.fullmatch(r"[0-9]{5}", code) or not re.fullmatch(r"[0-9]{2}", number) or code in seen:
            raise ValueError(f"{label}: fila no válida o repetida: {dict(row)}")
        seen.add(code)
        result.append([code, number])
    if not result:
        raise ValueError(f"{label}: sin municipios")
    return sorted(result)


def parse_idescat(content: bytes) -> list[list[str]]:
    """[[municipality code5, Idescat comarca code2], …] from the Idescat table of municipalities
    (CSV with «;», three lines of title before the header). Its municipality code is the INE one with
    its check digit."""
    try:
        lines = content.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        raise ValueError("Idescat: la tabla de municipios no está en UTF-8") from None
    header = next((i for i, line in enumerate(lines) if line.startswith("Codi;Nom;Codi comarca;")), None)
    if header is None:
        raise ValueError("Idescat: no está la cabecera «Codi;Nom;Codi comarca;» de la tabla de municipios")
    rows = []
    for row in csv.DictReader(lines[header:], delimiter=";"):
        code = (row.get("Codi") or "").strip()
        if not re.fullmatch(r"[0-9]{6}", code):
            raise ValueError(f"Idescat: código de municipio no válido: {dict(row)}")
        rows.append({"ine": code[:5], "comarca": row.get("Codi comarca")})
    return _members(rows, "ine", "comarca", "Idescat")


def parse_aragon(content: bytes) -> list[list[str]]:
    """[[municipality code5, Aragon comarca code2], …] from the Aragón Open Data table of
    municipalities (CSV with «,»: codigo_mun and codigo_comarc)."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Aragón Open Data: la tabla de municipios no está en UTF-8") from None
    reader = csv.DictReader(io.StringIO(text))
    if not {"codigo_mun", "codigo_comarc"} <= set(reader.fieldnames or []):
        raise ValueError(f"Aragón Open Data: faltan codigo_mun y codigo_comarc; hay {reader.fieldnames}")
    return _members(reader, "codigo_mun", "codigo_comarc", "Aragón Open Data")
