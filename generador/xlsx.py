"""Minimal XLSX reader (stdlib only): the rows of one sheet as lists of strings."""
from __future__ import annotations

import io
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "p": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _column(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group()
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - 64
    return number - 1


def sheet_names(content: bytes) -> list[str]:
    with ZipFile(io.BytesIO(content)) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
    return [s.get("name") for s in workbook.findall("s:sheets/s:sheet", NS)]


def read_rows(content: bytes, sheet: str | None = None) -> list[list[str]]:
    """Rows of the named sheet (the first one by default). Empty cells are ''."""
    with ZipFile(io.BytesIO(content)) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = workbook.findall("s:sheets/s:sheet", NS)
        chosen = sheets[0] if sheet is None else next((s for s in sheets if s.get("name") == sheet), None)
        if chosen is None:
            raise ValueError(f"Sheet {sheet!r} not found; sheets: {[s.get('name') for s in sheets]}")
        rel_id = chosen.get(f"{{{NS['r']}}}id")
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels.findall("p:Relationship", NS) if r.get("Id") == rel_id)
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            for item in ET.fromstring(book.read("xl/sharedStrings.xml")).findall("s:si", NS):
                shared.append("".join(t.text or "" for t in item.iter(f"{{{NS['s']}}}t")))
        rows = []
        for row in ET.fromstring(book.read(path)).findall("s:sheetData/s:row", NS):
            cells: dict[int, str] = {}
            for cell in row.findall("s:c", NS):
                kind, value = cell.get("t"), cell.find("s:v", NS)
                if kind == "s" and value is not None:
                    text = shared[int(value.text)]
                elif kind == "inlineStr":
                    text = "".join(t.text or "" for t in cell.iter(f"{{{NS['s']}}}t"))
                else:
                    text = value.text if value is not None and value.text is not None else ""
                cells[_column(cell.get("r"))] = text
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        return rows
