"""Postal codes (códigos postales) of each municipality and municipalities of each postal code, from
datos/codigos-postales.csv. js/postal.js mirrors this file.

    te.postal_codes("es:municipio:08019")[0]["postal_code"]   # '08001'
    [m["id"] for m in te.municipalities("29620")]             # Torremolinos, then Málaga
    te.relate_postal_code("29620")["status"]                  # 'pending': two municipalities

A postal code can span several municipalities and a municipality has several codes, so the postal
code is not a `resolve` system (that one gives a single territory). Each pair carries the number of
addresses that use it in the source (Catastro, IDENA or Eustat): it orders the municipalities of a
shared code, the main one first. Codes are strings of five digits: no zero padding.
"""
from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

from .relation import relation

HEADER = ["postal_code", "id", "ine", "addresses", "source"]
_CODE = re.compile(r"[0-9]{5}")


class PostalCodes:
    def __init__(self, text: str):
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or rows[0] != HEADER:
            raise ValueError("Not a codigos-postales.csv table")
        self._by_code: dict[str, list[dict]] = {}
        self._by_id: dict[str, list[dict]] = {}
        for row in rows[1:]:
            if len(row) != len(HEADER) or not _CODE.fullmatch(row[0]) or not row[3].isdigit():
                raise ValueError(f"Invalid row {row}")
            item = {"postal_code": row[0], "id": row[1], "addresses": int(row[3]), "source": row[4]}
            self._by_code.setdefault(row[0], []).append(item)
            self._by_id.setdefault(row[1], []).append(item)
        for items in self._by_code.values():
            items.sort(key=lambda i: (-i["addresses"], i["id"]))
        for items in self._by_id.values():
            items.sort(key=lambda i: i["postal_code"])

    def __len__(self):
        return sum(len(items) for items in self._by_code.values())

    def postal_codes(self, identity: str) -> list[dict]:
        """Postal codes of a municipality, by code."""
        return [dict(i) for i in self._by_id.get(identity, [])] if isinstance(identity, str) else []

    def municipalities(self, code: str) -> list[dict]:
        """Municipalities of a postal code, the one with most addresses first."""
        return [dict(i) for i in self._by_code.get(code, [])] if isinstance(code, str) else []

    def relate(self, code: str) -> dict:
        """Resolved if only one municipality has the code; pending if several (candidates, and the
        evidence in order of addresses) or none."""
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            return relation("pending", None, (), "not_a_postal_code")
        found = self._by_code.get(code, [])
        ids = [i["id"] for i in found]
        evidence = [{"source": "postal_code", "datum": code, "territory": i["id"], "addresses": i["addresses"]}
                    for i in found]
        if len(ids) == 1:
            return relation("resolved", ids[0], ids, "postal_code", evidence)
        return relation("pending", None, ids, "ambiguous" if ids else "not_found", evidence)


def load_postal_codes(path: str | os.PathLike) -> PostalCodes:
    return PostalCodes(Path(path).read_text(encoding="utf-8"))
