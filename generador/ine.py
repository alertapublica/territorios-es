"""INE: dictionary of municipalities (XLSX) and the list of provinces by community (HTML)."""
from __future__ import annotations

import html
import re

from .xlsx import read_rows


def parse_municipalities(content: bytes, title_must_contain: str) -> list[list[str]]:
    """[[code5, check digit, official name, community], …] sorted by code."""
    rows = read_rows(content)
    title = rows[0][0] if rows and rows[0] else ""
    if title_must_contain not in title:
        raise ValueError(f"Unexpected INE edition: {title!r}")
    header = [c.strip() for c in rows[1][:5]]
    if header != ["CODAUTO", "CPRO", "CMUN", "DC", "NOMBRE"]:
        raise ValueError(f"Unexpected INE header: {header}")
    result, seen = [], set()
    for row in rows[2:]:
        if not any(row):
            continue
        row = (row + [""] * 5)[:5]
        ccaa, province, municipality, check, name = (c.strip() for c in row)
        code = province + municipality
        if (not re.fullmatch(r"[0-9]{5}", code) or not re.fullmatch(r"[0-9]", check)
                or not re.fullmatch(r"[0-9]{2}", ccaa) or not name or code in seen):
            raise ValueError(f"Invalid or repeated INE row: {row}")
        seen.add(code)
        result.append([code, check, name, ccaa])
    return sorted(result)


def parse_provinces(content: bytes) -> list[list[str]]:
    """[[province, community, province name as written by the INE], …] from the HTML table.
    Only used to cross-check fuentes/provincias.csv: an empty result is reported, not fatal."""
    text = content.decode("utf-8", errors="replace")
    if "charset=iso-8859-1" in text.lower() or "�" in text:
        text = content.decode("latin-1")
    result = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S | re.I)]
        cells = [re.sub(r"\s+", " ", c) for c in cells]
        if len(cells) >= 4 and re.fullmatch(r"[0-9]{2}", cells[0]) and re.fullmatch(r"[0-9]{2}", cells[2]):
            result.append([cells[2], cells[0], cells[3]])
    return sorted(result)
