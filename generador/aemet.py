"""AEMET: the warning zones of Meteoalerta. The zone of every municipality comes from the municipality
master of AEMET OpenData (needs a key); the code and name of every zone, from the table (DBF) of the
zone boundaries published with the Meteoalerta plan."""
from __future__ import annotations

import io
import json
import re
import struct
import zipfile
import zlib

ZONE = re.compile(r"[0-9]{6}")


def data_link(content: bytes) -> str:
    """AEMET OpenData answers in two steps: first a JSON with the temporary link to the data."""
    try:
        answer = json.loads(content.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as error:
        raise ValueError(f"AEMET OpenData: respuesta que no es JSON ({error})") from None
    link = answer.get("datos") if isinstance(answer, dict) else None
    if not isinstance(link, str) or not link.startswith("https://"):
        detail = answer.get("descripcion") if isinstance(answer, dict) else None
        raise ValueError(f"AEMET OpenData: sin enlace a los datos ({detail or 'respuesta inesperada'})")
    return link


def parse_municipalities(content: bytes) -> list[list[str]]:
    """[[municipality code5, zone code6], …] from the master of municipalities (JSON in ISO-8859-15,
    with ids like «id01001»). Raises ValueError if the answer is not that table or repeats a code."""
    try:
        rows = json.loads(content.decode("iso-8859-15"))
    except json.JSONDecodeError as error:
        raise ValueError(f"AEMET: el maestro de municipios no es JSON ({error})") from None
    if not isinstance(rows, list) or not rows:
        raise ValueError("AEMET: maestro de municipios vacío o con otra forma")
    result, seen = [], set()
    for row in rows:
        code = re.fullmatch(r"id([0-9]{5})", str(row.get("id", ""))) if isinstance(row, dict) else None
        zone = str(row.get("zona_comarcal", "")).strip() if isinstance(row, dict) else ""
        if code is None or not ZONE.fullmatch(zone) or code[1] in seen:
            raise ValueError(f"AEMET: fila no válida o repetida en el maestro de municipios: {str(row)[:200]}")
        seen.add(code[1])
        result.append([code[1], zone])
    return sorted(result)


def _dbf(content: bytes) -> list[dict[str, str]]:
    """Records of a dBase III table (character fields only), in ISO-8859-15 as AEMET writes them."""
    if len(content) < 32:
        raise ValueError("AEMET: tabla DBF vacía")
    count, header, length = struct.unpack("<4xIHH", content[:12])
    if header < 33 or len(content) < header + count * length:
        raise ValueError("AEMET: tabla DBF cortada")
    fields, offset = [], 1
    for start in range(32, header - 1, 32):
        field = content[start:start + 32]
        if field[:1] == b"\r":
            break
        fields.append((field[:11].split(b"\0")[0].decode("ascii", errors="replace"), offset, field[16]))
        offset += field[16]
    if offset > length:
        raise ValueError("AEMET: tabla DBF con campos más largos que el registro")
    records = []
    for i in range(count):
        record = content[header + i * length:header + (i + 1) * length]
        if len(record) < length:
            raise ValueError("AEMET: tabla DBF cortada")
        if record[:1] == b"*":  # deleted
            continue
        records.append({name: record[at:at + size].decode("iso-8859-15").strip() for name, at, size in fields})
    return records


def parse_zones(content: bytes) -> list[list[str]]:
    """[[zone code6, name], …] from the ZIP of the zone boundaries: the table of the land zones (the
    coastal ones, with a «C» after the code, are another layer and are left out)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        tables = [n for n in archive.namelist() if n.lower().endswith(".dbf") and "coster" not in n.lower()]
        if len(tables) != 1:
            raise ValueError(f"AEMET: se esperaba una tabla DBF de zonas terrestres y hay {tables}")
        table = archive.read(tables[0])
    except (zipfile.BadZipFile, zlib.error, EOFError) as error:
        raise ValueError(f"AEMET: la delimitación de zonas no es un ZIP válido ({error})") from None
    records = _dbf(table)
    if records and not {"COD_Z", "NOM_Z"} <= records[0].keys():
        raise ValueError(f"AEMET: faltan las columnas COD_Z y NOM_Z; hay {sorted(records[0])}")
    result, seen = [], set()
    for record in records:
        code, name = record["COD_Z"], record["NOM_Z"]
        if not ZONE.fullmatch(code) or not name or code in seen:
            raise ValueError(f"AEMET: zona no válida o repetida: {record}")
        seen.add(code)
        result.append([code, name])
    if not result:
        raise ValueError("AEMET: delimitación sin zonas")
    return sorted(result)
