"""Postal codes (códigos postales) of each municipality and municipalities of each postal code, from
datos/codigos-postales.csv. js/postal.js mirrors this file.

    te.postal_codes("es:municipio:08019")[0]["postal_code"]   # '08001'
    [m["id"] for m in te.municipalities("28760")]             # Tres Cantos, then Madrid
    te.relate_postal_code("28760")["status"]                  # 'pending': two municipalities

A postal code can span several municipalities and a municipality has several codes, so the postal
code is not a `resolve` system (that one gives a single territory). Each pair carries its source (the
one that decides in that municipality), its count in that source's unit (addresses, portals or street
sections) and the other sources that have it too (`also`). The municipalities of a shared code go by
count when all have the same unit; otherwise as in the table, by the street sections of the INE.
Codes are strings of five digits: no zero padding.
"""
from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

from .relation import relation

HEADER = ["postal_code", "id", "ine", "source", "count", "unit", "also"]
_CODE = re.compile(r"[0-9]{5}")


def _ordered(items: list[dict]) -> list[dict]:
    """By count when all have the same unit; otherwise as in the table, which goes by the street
    sections of the INE (counts in different units are never compared)."""
    if len({i["unit"] for i in items}) == 1:
        return sorted(items, key=lambda i: (-i["count"], i["id"]))
    return items


def _copy(item: dict) -> dict:
    return {**item, "also": list(item["also"])}


class PostalCodes:
    def __init__(self, text: str):
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or rows[0] != HEADER:
            raise ValueError("Not a codigos-postales.csv table")
        by_code: dict[str, list[dict]] = {}
        by_id: dict[str, list[dict]] = {}
        for row in rows[1:]:
            if len(row) != len(HEADER) or not _CODE.fullmatch(row[0]) or not row[4].isdigit():
                raise ValueError(f"Invalid row {row}")
            item = {"postal_code": row[0], "id": row[1], "source": row[3], "count": int(row[4]),
                    "unit": row[5], "also": row[6].split(" ") if row[6] else []}
            by_code.setdefault(row[0], []).append(item)
            by_id.setdefault(row[1], []).append(item)
        self._by_code = {code: _ordered(items) for code, items in by_code.items()}
        self._by_id = {i: sorted(items, key=lambda x: x["postal_code"]) for i, items in by_id.items()}

    def __len__(self):
        return sum(len(items) for items in self._by_code.values())

    def postal_codes(self, identity: str) -> list[dict]:
        """Postal codes of a municipality, by code."""
        return [_copy(i) for i in self._by_id.get(identity, [])] if isinstance(identity, str) else []

    def municipalities(self, code: str) -> list[dict]:
        """Municipalities of a postal code: by count when all have the same unit, otherwise as in
        the table (by the street sections of the INE)."""
        return [_copy(i) for i in self._by_code.get(code, [])] if isinstance(code, str) else []

    def relate(self, code: str) -> dict:
        """Resolved if only one municipality has the code; pending if several (candidates, and each
        one's source, count, unit and other sources in the evidence) or none."""
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            return relation("pending", None, (), "not_a_postal_code")
        found = self._by_code.get(code, [])
        ids = [i["id"] for i in found]
        evidence = [{"source": "postal_code", "datum": code, "territory": i["id"], "origin": i["source"],
                     "count": i["count"], "unit": i["unit"], "also": list(i["also"])} for i in found]
        if len(ids) == 1:
            return relation("resolved", ids[0], ids, "postal_code", evidence)
        return relation("pending", None, ids, "ambiguous" if ids else "not_found", evidence)


def load_postal_codes(path: str | os.PathLike) -> PostalCodes:
    return PostalCodes(Path(path).read_text(encoding="utf-8"))
