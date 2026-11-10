"""INE: dictionary of municipalities (XLSX), islands with their municipalities (XLSX), the changes
registered in the Registro de Entidades Locales since the dictionary (HTML), the list of
provinces by community (HTML) and the official population of provinces and municipalities (JSON
API)."""
from __future__ import annotations

import html
import json
import re

from .xlsx import read_rows, sheet_names


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


ISLANDS_HEADER = ["CPRO", "CISLA", "ISLA", "CMUN", "DC", "NOMBRE"]


def parse_islands(content: bytes) -> tuple[list[list[str]], str | None]:
    """([[island code, island name as written by the INE, municipality code5, check digit], …]
    sorted by municipality, reference date «YYYY-MM-DD» from the sheet titles or None). One sheet
    per province (07, 35, 38); the island code starts with the province code."""
    months = {"enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
              "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11",
              "diciembre": "12"}
    result, seen, dates = [], set(), set()
    for sheet in sheet_names(content):
        rows = read_rows(content, sheet)
        title = rows[0][0] if rows and rows[0] else ""
        if match := re.search(r"(\d{1,2}) de (\w+) de (\d{4})", title):
            dates.add(f"{match[3]}-{months.get(match[2].lower(), '00')}-{int(match[1]):02d}")
        header_at = next((i for i, row in enumerate(rows) if [c.strip() for c in row[:6]] == ISLANDS_HEADER), None)
        if header_at is None:
            raise ValueError(f"Unexpected INE islands sheet {sheet!r}: no header {ISLANDS_HEADER}")
        for row in rows[header_at + 1:]:
            if not any(c.strip() for c in row):
                continue
            province, island, name, municipality, check, _ = ((c.strip() for c in (row + [""] * 6)[:6]))
            code = province + municipality
            if (not re.fullmatch(r"[0-9]{5}", code) or not re.fullmatch(r"[0-9]{3}", island)
                    or not island.startswith(province) or not re.fullmatch(r"[0-9]", check) or not name
                    or code in seen):
                raise ValueError(f"Invalid or repeated INE islands row: {row}")
            seen.add(code)
            result.append([island, name, code, check])
    if not result:
        raise ValueError("No islands in the INE file")
    return sorted(result, key=lambda r: r[2]), (dates.pop() if len(dates) == 1 else None)


_CHANGE_SECTIONS = {"municipios creados": "created", "municipios desaparecidos": "dissolved",
                    "cambio de denominación": "renamed", "corrección en la denominación": "corrected"}


def _html_text(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    if "�" in text:
        head = content[:4000].decode("ascii", errors="replace").lower()
        text = content.decode("iso-8859-15" if "iso-8859-15" in head else "latin-1")
    return text


def _cells(row: str) -> list[str]:
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)]


def _date(text: str) -> str | None:
    match = re.fullmatch(r"(\d{2})[/-](\d{2})[/-](\d{4})", text)
    return f"{match[3]}-{match[2]}-{match[1]}" if match else None


def parse_changes(content: bytes) -> tuple[str | None, list[dict]]:
    """(start date «YYYY-MM-DD» from the title, changes) of the page of municipal changes registered
    in the REL during the year. Each change: kind (created, dissolved, renamed, corrected), INE
    code, check digit, name (the new one, or the one created or dissolved), previous name (renamed
    and corrected), date (REL resolution or extinction) and other (the municipality it comes from or
    goes to)."""
    text = _html_text(content)
    start = re.search(r"producidas desde el (\d{2}-\d{2}-\d{4})", text)
    changes, section = [], None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S | re.I):
        cells = _cells(row)
        heading = " ".join(cells).lower()
        for key, kind in _CHANGE_SECTIONS.items():
            if key in heading and len([c for c in cells if c]) == 1:
                section = kind
        code_at = next((i for i, c in enumerate(cells) if re.fullmatch(r"\d{2} ?\d{3} ?\d", c)), None)
        if section is None or code_at is None:
            continue
        if section in ("created", "dissolved") and code_at > 1 and changes and not any(cells[:code_at]):
            # another municipality it comes from or goes to, on a row of its own
            changes[-1]["other"] = "; ".join(filter(None, [changes[-1]["other"], " ".join(cells[code_at:code_at + 2])]))
            continue
        digits = cells[code_at].replace(" ", "")
        change = {"kind": section, "code": digits[:5], "check": digits[5]}
        if section in ("renamed", "corrected"):  # provincia, nueva, código, anterior, fecha
            if code_at != 2 or len(cells) < 4:
                raise ValueError(f"Unexpected INE change row: {cells}")
            change.update(name=cells[1], previous=cells[3], date=_date(cells[4]) if len(cells) > 4 else None)
        else:  # provincia, código, denominación, del que se segrega / al que se incorpora, fecha(s)
            if code_at != 1 or len(cells) < 3:
                raise ValueError(f"Unexpected INE change row: {cells}")
            change.update(name=cells[2], other=cells[3] if len(cells) > 3 else "",
                          date=_date(cells[4]) if len(cells) > 4 else None)
        if not change["name"]:
            raise ValueError(f"INE change without a name: {cells}")
        changes.append(change)
    return (_date(start[1]) if start else None), changes


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


def population_tables(content: bytes, table_code: str) -> list[int]:
    """Ids of the tables of an operation (TABLAS_OPERACION of the JSON API) with that code. In the
    operation of the official population («DPOP»), «PROV-MUN» is one table per province."""
    try:
        ids = sorted(int(t["Id"]) for t in json.loads(content) if t.get("Codigo") == table_code)
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError(f"Unexpected INE table list: {error}") from error
    if not ids:
        raise ValueError(f"No INE tables with code {table_code!r}")
    return ids


def parse_population(content: bytes) -> tuple[dict[str, int], str]:
    """({province code2 or municipality code5: population}, reference date «YYYY-MM-DD») of one
    province table (DATOS_TABLA with nult=1 and tip=AM): its total and each of its municipalities,
    both sexes. Codes come from the series metadata, not from the names. Municipalities that no
    longer exist keep their series, without data (Cesuras, merged into Oza-Cesuras in 2013)."""
    values, dates = {}, set()
    try:
        for series in json.loads(content):
            meta = {m["T3_Variable"]: m["Codigo"] for m in series["MetaData"]}
            if meta.get("Sexo") != "0":
                continue
            code = meta.get("Municipios") or meta.get("Provincias") or ""
            data = series["Data"]
            if not data:
                continue
            if (not re.fullmatch(r"[0-9]{2}|[0-9]{5}", code) or code in values or len(data) != 1
                    or not isinstance(data[0]["Valor"], (int, float))):
                raise ValueError(f"Unexpected INE population series: {series.get('Nombre')!r}")
            values[code] = int(data[0]["Valor"])
            dates.add(data[0]["Fecha"][:10])
    except (TypeError, KeyError, AttributeError) as error:
        raise ValueError(f"Unexpected INE population table: {error}") from error
    provinces = [code for code in values if len(code) == 2]
    if len(provinces) != 1 or any(code[:2] != provinces[0] for code in values) or len(values) < 2:
        raise ValueError(f"INE population table without one province and its municipalities: {provinces}")
    if len(dates) != 1 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", next(iter(dates))):
        raise ValueError(f"INE population table with dates {sorted(dates)}")
    return values, dates.pop()
