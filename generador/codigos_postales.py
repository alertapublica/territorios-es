"""Postal codes (códigos postales) of each municipality, with the number of addresses of each pair,
from the address registers that can be republished. Writes datos/codigos-postales.csv.

- Catastro, INSPIRE Addresses (AD): the common regime (all but Navarre and the Basque Country), one
  GML per municipality, numbered with its DGC code, which goes to INE with the crosswalk that is
  already in territorios.json.
- IDENA (Gobierno de Navarra): the address points of Navarre (CC BY 4.0).
- Eustat / Gobierno Vasco, NORA street register: the portals of Álava, Gipuzkoa and Bizkaia (CC BY 4.0).

The postal code is Correos's; each register carries it on its addresses under its own licence. The
INE electoral street register has it too, but the INE licence excludes data of third parties: it is
downloaded only to compare, and the report never writes a code that only the INE has.

Catastro licence (DGC, July 2016): public and commercial use of transformed information only, citing
the DGC and the access date. The originals stay in the Actions cache and are never committed; the
tests use invented files with the same shape.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from . import xlsx
from .construir import Report

FILE = "codigos-postales.csv"
HEADER = ["postal_code", "id", "ine", "addresses", "source"]
# Source in the table → its entry in fuentes.json and in the manifest.
SOURCES = {"catastro": "catastro_direcciones", "idena": "idena_direcciones", "eustat": "eustat_portales"}
NAVARRA = "31"
EUSKADI = ("01", "20", "48")
# A pair with fewer addresses is left out (and goes to the report), unless it is the municipality's
# most used code: every municipality with addresses keeps at least one.
MIN_ADDRESSES = 3
CHANGE_WARNING = 0.05  # share of pairs that may change from one run to the next without a warning
# Fixed cases of the real data, checked on every run and by --check (not on the test fixture).
CASES = {
    "includes": {"es:municipio:08019": [f"080{n:02d}" for n in range(1, 43)]},
    "first": {"29620": ["es:municipio:29901", "es:municipio:29067"], "31001": ["es:municipio:31201"],
              "01001": ["es:municipio:01059"], "02250": ["es:municipio:02001"]},
}

CATASTRO = "https://www.catastro.hacienda.gob.es/INSPIRE/Addresses"
_ATOM = "{http://www.w3.org/2005/Atom}"
_AD = "{urn:x-inspire:specification:gmlas:Addresses:3.0}"
_GML = "{http://www.opengis.net/gml/3.2}"
_HREF = "{http://www.w3.org/1999/xlink}href"
_OFFICE = re.compile(r"/INSPIRE/addresses/([0-9]{2})/ES\.SDGC\.ad\.atom_\1\.xml$", re.IGNORECASE)
_ZIP = re.compile(r"/A\.ES\.SDGC\.AD\.([0-9]{5})\.zip$")
_VALID = re.compile(r"[0-9]{5}")


def postal_code(text: str | None) -> str:
    """The code as the source writes it, without spaces. The Catastro drops the leading zero
    («2250» is 02250); a postal code always has five digits, so a four-digit one gets it back."""
    text = (text or "").strip()
    return "0" + text if re.fullmatch(r"[0-9]{4}", text) else text


def valid(code: str) -> bool:
    """Five digits, the first two a province (01–52)."""
    return bool(_VALID.fullmatch(code)) and 1 <= int(code[:2]) <= 52


# Catastro ----------------------------------------------------------------------------------------

def _xml(content: bytes, who: str) -> ET.Element:
    try:
        return ET.fromstring(content)
    except ET.ParseError as error:
        raise ValueError(f"{who}: XML no válido ({error})") from None


def parse_catastro_feed(content: bytes) -> list[str]:
    """Territorial offices (two digits) of the general ATOM of addresses. Its entries for the foral
    cadastres (Bizkaia, Gipuzkoa, Navarra) point to other servers and are left out."""
    root = _xml(content, "Catastro")
    offices = {m.group(1) for link in root.iter(_ATOM + "link") if (m := _OFFICE.search(link.get("href", "")))}
    if not offices:
        raise ValueError("Catastro: el ATOM de direcciones no trae gerencias")
    return sorted(offices)


def office_feed_url(office: str) -> str:
    # Always https and /INSPIRE/Addresses/: by http the office feed came back empty (10-11-2026).
    return f"{CATASTRO}/{office}/ES.SDGC.ad.atom_{office}.xml"


def parse_office_feed(content: bytes) -> list[list]:
    """[[DGC code, [URL, …]], …] of an office ATOM, one ZIP per municipality. The links carry spaces
    and letters such as Ñ («02024-CASAS IBAÑEZ»): the first URL encodes them in UTF-8, the second (if
    it differs) in ISO-8859-1, the encoding of the feed."""
    root = _xml(content, "Catastro")
    found = {}
    for link in root.iter(_ATOM + "link"):
        href = link.get("href", "")
        match = _ZIP.search(href)
        if link.get("rel") != "enclosure" or not match:
            continue
        href = re.sub(r"^http://", "https://", href.strip())
        urls = [quote(href, safe=":/%")]
        try:
            latin = quote(href, safe=":/%", encoding="iso-8859-1")
        except UnicodeEncodeError:
            latin = urls[0]
        found[match.group(1)] = urls + ([latin] if latin != urls[0] else [])
    if not found:
        raise ValueError("Catastro: el ATOM de la gerencia no trae municipios")
    return sorted([dgc, urls] for dgc, urls in found.items())


def feed_updated(content: bytes) -> str | None:
    """Date of the last update of an ATOM feed (YYYY-MM-DD)."""
    text = _xml(content, "Catastro").findtext(_ATOM + "updated") or ""
    return text[:10] if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text[:10]) else None


def check_zip(content: bytes, extension: str = ".gml"):
    """Cheap check of a download (retried if it fails): a whole ZIP with a file of that kind."""
    try:
        names = zipfile.ZipFile(io.BytesIO(content)).namelist()
    except zipfile.BadZipFile:
        raise ValueError("no es un ZIP completo") from None
    if not any(n.lower().endswith(extension) for n in names):
        raise ValueError(f"el ZIP no trae ningún {extension or 'fichero'}")


def parse_catastro_ad(content: bytes) -> Counter:
    """Counter{(postal code, DGC code): addresses} of a municipality ZIP (INSPIRE AD GML, read as a
    stream: Madrid has 168,000 addresses). Each address links its postal descriptor
    (`xlink:href="#ES.SDGC.PD.…"`) and its municipality (`#ES.SDGC.AU.28.900`). An address without
    a descriptor, or whose descriptor is not in the file, counts with the code ""."""
    check_zip(content)
    archive = zipfile.ZipFile(io.BytesIO(content))
    name = next(n for n in archive.namelist() if n.lower().endswith(".gml") and ".MD." not in n.upper())
    links: Counter = Counter()
    descriptors: dict[str, str] = {}
    try:
        with archive.open(name) as stream:
            for _, element in ET.iterparse(stream):
                if element.tag == _AD + "Address":
                    hrefs = [c.get(_HREF) or "" for c in element.iter(_AD + "component")]
                    descriptor = next((h[1:] for h in hrefs if h.startswith("#ES.SDGC.PD.")), "")
                    unit = next((h[len("#ES.SDGC.AU."):] for h in hrefs if h.startswith("#ES.SDGC.AU.")), "")
                    dgc = unit.replace(".", "")
                    if not re.fullmatch(r"[0-9]{5}", dgc):
                        raise ValueError(f"Catastro: dirección sin municipio ({unit!r})")
                    links[descriptor, dgc] += 1
                    element.clear()
                elif element.tag == _AD + "PostalDescriptor":
                    descriptors[element.get(_GML + "id", "")] = postal_code(element.findtext(_AD + "postCode"))
                    element.clear()
                elif element.tag == _GML + "featureMember":
                    element.clear()
    except ET.ParseError as error:
        raise ValueError(f"Catastro: GML no válido ({error})") from None
    counts: Counter = Counter()
    for (descriptor, dgc), n in links.items():
        counts[descriptors.get(descriptor, ""), dgc] += n
    return counts


# Navarra -----------------------------------------------------------------------------------------

def parse_navarra(content: bytes) -> Counter:
    """Counter{(postal code, INE code): address points} of the IDENA ZIP (a shapefile). Its DBF has
    CMUNICIPIO, the INE number of the municipality without the province, and CODPOSTAL."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValueError("IDENA: no es un ZIP completo") from None
    names = [n for n in archive.namelist() if n.lower().endswith(".dbf")]
    if len(names) != 1:
        raise ValueError(f"IDENA: se esperaba un DBF y hay {len(names)}")
    counts: Counter = Counter()
    with archive.open(names[0]) as stream:
        head = stream.read(32)
        records = int.from_bytes(head[4:8], "little")
        header_size = int.from_bytes(head[8:10], "little")
        record_size = int.from_bytes(head[10:12], "little")
        fields, offset = {}, 1
        rest = stream.read(header_size - 32)
        for i in range(0, len(rest) - 1, 32):
            if rest[i] == 0x0D:
                break
            field = rest[i:i + 32]
            fields[field[:11].split(b"\0")[0].decode("ascii")] = (offset, field[16])
            offset += field[16]
        if not {"CMUNICIPIO", "CODPOSTAL"} <= fields.keys():
            raise ValueError(f"IDENA: faltan columnas; hay {sorted(fields)}")
        value = lambda record, key: record[fields[key][0]:sum(fields[key])].decode("latin-1").strip()
        for _ in range(records):
            record = stream.read(record_size)
            if len(record) < record_size:
                raise ValueError("IDENA: el DBF está cortado")
            if record[:1] == b"*":  # deleted
                continue
            number = value(record, "CMUNICIPIO")
            if not re.fullmatch(r"[0-9]{1,3}", number):
                raise ValueError(f"IDENA: municipio no válido {number!r}")
            counts[postal_code(value(record, "CODPOSTAL")), NAVARRA + number.zfill(3)] += 1
    return counts


# País Vasco --------------------------------------------------------------------------------------

def parse_euskadi(content: bytes) -> Counter:
    """Counter{(postal code, INE code): portals} of a NORA file of Eustat, CSV (UTF-8 with BOM, «;»,
    CRLF) or XLSX (prefix x:). Columns: 0 province (territorio histórico), 2 municipality, 18 postal
    code (with a space in front)."""
    if content[:2] == b"PK":
        rows = iter(xlsx.read_rows(content))
    else:
        rows = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), delimiter=";")
    header = next(rows, [])
    if len(header) < 19 or "Código TH" not in header[0] or "Código Municipio" not in header[2] \
            or "Código Postal" not in header[18]:
        raise ValueError(f"Eustat: cabecera inesperada {header[:3]}…")
    counts: Counter = Counter()
    for row in rows:
        if not any(row):
            continue
        province, number = row[0].strip(), row[2].strip()
        if not re.fullmatch(r"[0-9]{1,2}", province) or not re.fullmatch(r"[0-9]{1,3}", number):
            raise ValueError(f"Eustat: municipio no válido {row[:4]}")
        counts[postal_code(row[18] if len(row) > 18 else ""), province.zfill(2) + number.zfill(3)] += 1
    return counts


def check_euskadi(content: bytes):
    """Cheap check of a NORA download: a whole XLSX, or a CSV with its header."""
    if content[:2] == b"PK":
        check_zip(content, ".xml")
    elif "Código Postal" not in content[:2000].decode("utf-8-sig", errors="replace"):
        raise ValueError("Eustat: no es el CSV de portales")


# INE (only to compare) ---------------------------------------------------------------------------

def ine_street_urls(template: str, today: str) -> list[str]:
    """The electoral street register comes out in January and July: the last three, newest first."""
    year, month = int(today[:4]), int(today[5:7])
    periods = [(year, 7), (year, 1), (year - 1, 7), (year - 1, 1)]
    return [template.format(month=f"{m:02d}", year=y) for y, m in periods if (y, m) <= (year, month)][:3]


def parse_ine_streets(content: bytes) -> set[tuple[str, str]]:
    """{(postal code, INE code)} of the INE electoral street register: the sections file (TRAM…, at
    times inside a second ZIP), fixed width, with the municipality at 0–5 and the postal code at
    42–47. Only to compare: never published."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        name = next(n for n in archive.namelist() if "TRAM" in n.upper())
        if name.lower().endswith(".zip"):
            archive = zipfile.ZipFile(io.BytesIO(archive.read(name)))
            name = next(n for n in archive.namelist() if "TRAM" in n.upper())
    except (zipfile.BadZipFile, StopIteration):
        raise ValueError("INE: el ZIP del callejero no trae el fichero de tramos") from None
    pairs, lines, odd = set(), 0, 0
    with archive.open(name) as stream:
        for raw in stream:
            lines += 1
            line = raw.decode("cp1252")
            municipality, code = line[0:5], line[42:47]
            if re.fullmatch(r"[0-9]{5}", municipality) and re.fullmatch(r"[0-9]{5}", code):
                pairs.add((code, municipality))
            else:
                odd += 1
    if not lines or odd > lines * 0.01:
        raise ValueError(f"INE: {odd} de {lines} tramos sin la forma esperada")
    return pairs


# Table -------------------------------------------------------------------------------------------

def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _addresses(n: int) -> str:
    return "1 dirección" if n == 1 else f"{_fmt(n)} direcciones"


def build(counts: dict[str, Counter], data: dict, previous: list[list[str]] | None = None,
          ine_pairs: set | None = None, min_addresses: int = MIN_ADDRESSES) -> tuple[list[list], Report]:
    """(rows of the table, report). `counts` has a Counter{(postal code, municipality code): n} per
    source: DGC codes for «catastro», INE codes for «idena» and «eustat». `data` is territorios.json,
    `previous` the rows of the table published before, `ine_pairs` the INE register to compare."""
    report = Report()
    towns = {t["id"]: t for t in data["territories"] if t["level"] == "municipality"}
    name = lambda identity: f'{towns[identity]["names"]["display"]} ({identity})'
    by_dgc = {t["codes"]["dgc:municipio"]: i for i, t in towns.items() if "dgc:municipio" in t["codes"]}
    by_ine = {t["codes"]["ine:municipio"]: i for i, t in towns.items()}
    province = lambda identity: towns[identity]["parent"].rsplit(":", 1)[1]

    def owner(identity: str) -> str:
        p = province(identity)
        return "idena" if p == NAVARRA else "eustat" if p in EUSKADI else "catastro"

    pairs: dict[str, Counter] = {}
    with_addresses: Counter = Counter()
    for source in SOURCES:
        lookup = by_dgc if source == "catastro" else by_ine
        unknown: Counter = Counter()
        total = empty = 0
        for (code, number), n in sorted(counts.get(source, Counter()).items()):
            total += n
            identity = lookup.get(number)
            if identity is None:
                unknown[number] += n
                continue
            if owner(identity) != source:
                report.add("Códigos postales: municipio que no es de esta fuente (no se publica)",
                           f"{source}: {name(identity)}, {_addresses(n)}")
                continue
            with_addresses[identity] += n
            if not code:
                empty += n
            elif not valid(code):
                report.add("Códigos postales: código no válido (no se publica)",
                           f"«{code}» en {name(identity)}: {_addresses(n)}")
            else:
                pairs.setdefault(identity, Counter())[code] += n
        for number, n in unknown.items():
            report.add(f"Códigos postales: municipio sin cruce en {source} (no se publica)",
                       f"{number}: {_addresses(n)}")
        report.summary[f"direcciones ({source})"] = f"{_fmt(total)}; sin código postal: {_fmt(empty)}"

    ine_by_id = None
    if ine_pairs is not None:
        ine_by_id = {(code, by_ine[number]) for code, number in ine_pairs if number in by_ine}

    rows, buckets = [], {}
    limits = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 10), (11, 20), (21, 50), (51, None)]
    for identity, counter in sorted(pairs.items()):
        top = max(counter.values())
        for code, n in sorted(counter.items()):
            low, high = next(b for b in limits if n >= b[0] and (b[1] is None or n <= b[1]))
            bucket = buckets.setdefault((low, high), [0, 0])
            bucket[0] += 1
            bucket[1] += bool(ine_by_id and (code, identity) in ine_by_id)
            if n >= min_addresses or n == top:
                rows.append([code, identity, towns[identity]["codes"]["ine:municipio"], n, owner(identity)])
            else:
                report.add(f"Códigos postales: pares con menos de {min_addresses} direcciones (no se publican)",
                           f"{code} {name(identity)}: {n}")
    rows.sort(key=lambda r: (r[0], r[1]))
    for (low, high), (n, in_ine) in sorted(buckets.items()):
        label = _addresses(low) if low == high else f"{low}–{high} direcciones" if high else f"más de {low - 1} direcciones"
        extra = f" ({_fmt(in_ine)} también en el INE)" if ine_by_id is not None else ""
        report.summary[f"pares con {label}"] = _fmt(n) + extra

    published = {identity for _, identity, *_ in rows}
    report.summary["pares publicados"] = _fmt(len(rows))
    report.summary["códigos postales"] = _fmt(len({r[0] for r in rows}))
    report.summary["municipios con código"] = f"{_fmt(len(published))} de {_fmt(len(towns))}"
    for code, identity, _, n, _ in rows:
        if code[:2] != province(identity):
            report.add("Códigos postales: código de otra provincia", f"{code} {name(identity)}: {_addresses(n)}")
    for identity in sorted(towns.keys() - published):
        why = f"{_addresses(with_addresses[identity])}, ninguna con código válido" \
            if with_addresses[identity] else "sin direcciones en la fuente"
        report.add("Códigos postales: municipios sin código postal", f"{name(identity)}: {why}")

    if previous is not None:
        before = {(r[0], r[1]) for r in previous}
        now = {(r[0], r[1]) for r in rows}
        for code, identity in sorted(now - before):
            report.add("Códigos postales: pares nuevos", f"{code} {name(identity) if identity in towns else identity}")
        for code, identity in sorted(before - now):
            report.add("Códigos postales: pares que desaparecen", f"{code} {name(identity) if identity in towns else identity}")
        share = len(now ^ before) / max(len(before), 1)
        report.summary["cambio respecto a la tabla anterior"] = f"{share:.1%}".replace(".", ",")
        if share > CHANGE_WARNING:
            report.add("Códigos postales: aviso", f"cambia el {share:.1%} de los pares (más del "
                       f"{CHANGE_WARNING:.0%}): revisar antes de publicar".replace(".", ","))

    if ine_by_id is not None:
        ours = {(r[0], r[1]): r[3] for r in rows}
        only_ine = Counter(identity for code, identity in ine_by_id - ours.keys())
        report.summary["contraste con el INE"] = (
            f"coinciden {_fmt(len(ours.keys() & ine_by_id))} pares; {_fmt(len(ours.keys() - ine_by_id))} solo en "
            f"nuestra tabla; {_fmt(sum(only_ine.values()))} solo en el INE, en {_fmt(len(only_ine))} municipio(s)")
        for (code, identity), n in sorted(ours.items()):
            if (code, identity) not in ine_by_id:
                report.add("Contraste INE: pares solo en nuestra tabla", f"{code} {name(identity)}: {_addresses(n)}")
        # The INE codes are Correos's: only the municipality and how many, never the code.
        for identity, n in sorted(only_ine.items()):
            report.add("Contraste INE: municipios con códigos que solo están en el INE (sin el código)",
                       f"{name(identity)}: {n}")
    return rows, report


def check_cases(rows: list[list]) -> list[str]:
    """The fixed cases (CASES) that the rows do not meet."""
    problems = []
    by_code: dict[str, list] = {}
    for code, identity, _, n, _ in rows:
        by_code.setdefault(code, []).append((-int(n), identity))
    for identity, codes in CASES["includes"].items():
        have = {code for code, other, *_ in rows if other == identity}
        missing = [c for c in codes if c not in have]
        if missing:
            problems.append(f"{identity} no tiene {', '.join(missing)}")
    for code, expected in CASES["first"].items():
        found = [identity for _, identity in sorted(by_code.get(code, []))][:len(expected)]
        if found != expected:
            problems.append(f"{code} da {found}, se esperaba {expected}")
    return problems


def table(rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    return out.getvalue()


def read_table(path: Path) -> list[list[str]] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    if not rows or rows[0] != HEADER:
        raise ValueError(f"{path}: cabecera inesperada")
    return rows[1:]


def check(path: Path) -> list[str]:
    """Problems of a published table (empty if it is consistent). Municipalities that no longer
    exist are not a problem here: they go to the generator's report (orphans)."""
    try:
        rows = read_table(path)
    except ValueError as error:
        return [str(error)]
    problems, seen = [], set()
    for row in rows:
        if len(row) != len(HEADER):
            problems.append(f"{FILE}: fila con {len(row)} campos: {row}")
            continue
        code, identity, ine, n, source = row
        if not valid(code) or identity != f"es:municipio:{ine}" or not re.fullmatch(r"[0-9]{5}", ine) \
                or not n.isdigit() or int(n) < 1 or source not in SOURCES or (code, identity) in seen:
            problems.append(f"{FILE}: fila no válida o repetida: {row}")
        seen.add((code, identity))
    if not problems and path.read_text(encoding="utf-8") != table(sorted(rows, key=lambda r: (r[0], r[1]))):
        problems.append(f"{FILE} no está en forma canónica")
    return problems


def orphans(path: Path, data: dict) -> list[str]:
    """Municipalities of the published table that are not in territorios.json (a merger with the new
    INE dictionary): they are fixed by running the postal-code workflow again."""
    rows = read_table(path) or []
    known = {t["id"] for t in data["territories"]}
    return sorted({f"{identity}: relanzar codigos-postales.yml" for _, identity, *_ in rows if identity not in known})


def write(folder: Path, rows: list[list], records: dict):
    """The table and its entries in manifiesto.json (the rest of the manifest is generar.yml's)."""
    text = table(rows)
    (folder / FILE).write_text(text, encoding="utf-8")
    path = folder / "manifiesto.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["sources"].update(records)
    manifest["files"][FILE] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    manifest["files"] = dict(sorted(manifest["files"].items()))
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
