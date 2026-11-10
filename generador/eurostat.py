"""Eurostat: LAU–NUTS correspondence table (one sheet per country)."""
from __future__ import annotations

import re

from .xlsx import read_rows


def find_link(page: bytes, pattern: str, base: str) -> str:
    """Absolute URL of the first link on the page whose address matches the pattern."""
    for href in re.findall(r'href="([^"]+)"', page.decode("utf-8", errors="replace")):
        if re.search(pattern, href):
            return href if href.startswith("http") else base.rstrip("/") + "/" + href.lstrip("/")
    raise ValueError(f"No link matching {pattern!r}")


def _header_index(header: list[str]) -> dict[str, int]:
    wanted = {"nuts3": r"^NUTS ?3( CODE)?$", "lau": r"^LAU( CODE| ID|_ID)$",
              "name_national": r"^LAU NAME NATIONAL", "name_latin": r"^LAU NAME LATIN",
              "area": r"AREA", "degurba": r"^DEGURBA$",
              "coastal": r"^COASTAL", "city": r"^CITY[ _]ID$", "fua": r"^FUA[ _]ID$"}
    index = {}
    for i, cell in enumerate(header):
        label = re.sub(r"\s+", " ", cell.strip().upper())
        for key, pattern in wanted.items():
            if key not in index and re.search(pattern, label):
                index[key] = i
    return index


def parse_lau(content: bytes, sheet: str) -> tuple[dict[str, dict], list[str]]:
    """({LAU code: fields}, header). Fields are kept as written (strings)."""
    rows = read_rows(content, sheet)
    for position, row in enumerate(rows[:20]):
        index = _header_index(row)
        if "lau" in index and "nuts3" in index:
            break
    else:
        raise ValueError(f"LAU header not found; first rows: {rows[:3]}")
    header = rows[position]
    result = {}
    for row in rows[position + 1:]:
        row = row + [""] * (len(header) - len(row))
        code = row[index["lau"]].strip()
        if not code:
            continue
        result[code] = {key: row[i].strip() for key, i in index.items() if row[i].strip()}
    return result, header


def ine_code(lau_code: str) -> str | None:
    """INE municipality code a Spanish LAU code stands for, or None. Accepts «36038» and
    country-prefixed forms («ES36038», «ES_36038»); nothing is padded or guessed."""
    match = re.fullmatch(r"(?:ES_?)?([0-9]{5})", lau_code)
    return match.group(1) if match else None
