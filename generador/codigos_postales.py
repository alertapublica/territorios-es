"""Postal codes (códigos postales) of each municipality, gathered from what the public administrations
publish, with the source of each pair. Writes datos/codigos-postales.csv (the pairs published) and
datos/codigos-postales-fuentes.csv (what each source says: to compare, and to answer claims).

Sources (SOURCES), the most trusted first:
- Ayuntamiento de Madrid, official street directory: the city of Madrid only.
- Regional registers that carry the code of Correos on each address: ICGC (Catalonia), IDENA
  (Navarre), Eustat / NORA (Basque Country) and IDEIB (Balearic Islands).
- INE, street register of the electoral roll: street sections of all Spain.
- CDAU (Andalusia), portals: contrast only, behind the INE (a fifth of its pairs are in no other
  source).
- Catastro, INSPIRE Addresses (AD): the common regime, one GML per municipality, numbered with its
  DGC code, which goes to INE with the crosswalk of territorios.json (and MERGED_DGC).

In each municipality decides the first source whose scope covers it and that has data for it: all
its pairs there are published, with no threshold, and no other source fills in single pairs (that
would bring back the old codes of the Catastro). Fixed rules for every source: five digits with a
province (01–52), and no XX000 (filler: neither the ICGC nor the Madrid city council use one). The
other sources stay as observations; the column `also` of each pair says which of them have it too.
Each pair carries the count of its own source, in its own unit: counts in different units are never
added up.

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
from urllib.parse import quote, urljoin

from . import xlsx
from .construir import Report

FILE = "codigos-postales.csv"
OBSERVATIONS = "codigos-postales-fuentes.csv"
OBSERVATION_HEADER = ["postal_code", "id", "ine", "source", "count", "unit"]
HEADER = OBSERVATION_HEADER + ["also"]
NAVARRA = "31"
EUSKADI = ("01", "20", "48")
ANDALUCIA = ("04", "11", "14", "18", "21", "23", "29", "41")
# Name in the tables → its entry in fuentes.json and the manifest, the unit it counts and its scope
# (INE code prefixes; None: all Spain). In this order of precedence; the scopes of the regional
# sources never overlap.
SOURCES = {
    "madrid": {"entry": "madrid_direcciones", "unit": "addresses", "scope": ("28079",)},
    "icgc": {"entry": "icgc_direcciones", "unit": "addresses", "scope": ("08", "17", "25", "43")},
    "idena": {"entry": "idena_direcciones", "unit": "addresses", "scope": (NAVARRA,)},
    "eustat": {"entry": "eustat_portales", "unit": "portals", "scope": EUSKADI},
    "ideib": {"entry": "ideib_portales", "unit": "portals", "scope": ("07",)},
    "ine": {"entry": "ine_callejero", "unit": "street_sections", "scope": None},
    # Contrast only, behind the INE: a fifth of its pairs are in no other source (2026-11).
    "cdau": {"entry": "cdau_portales", "unit": "portals", "scope": ANDALUCIA},
    "catastro": {"entry": "catastro_direcciones", "unit": "addresses", "scope": None},
}
ENTRIES = [s["entry"] for s in SOURCES.values()]
UNITS = {"addresses": ("dirección", "direcciones"), "portals": ("portal", "portales"),
         "street_sections": ("tramo", "tramos")}
# Merged municipalities whose addresses the Catastro still files under the old DGC codes.
MERGED_DGC = {"15026": "15902", "15064": "15902", "36011": "36902", "36012": "36902"}
CHANGE_WARNING = 0.05  # share of pairs that may change from one run to the next without a warning
# Fixed cases of the real data, checked on every run and by --check (not on the test fixture).
CASES = {
    "includes": {"es:municipio:08019": [f"080{n:02d}" for n in range(1, 43)]},
    "first": {"29620": ["es:municipio:29901"], "28760": ["es:municipio:28903", "es:municipio:28079"],
              "31001": ["es:municipio:31201"], "01001": ["es:municipio:01059"], "02250": ["es:municipio:02001"]},
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


# Cataluña (ICGC) y Madrid ------------------------------------------------------------------------

def parse_icgc(content: bytes) -> Counter:
    """Counter{(postal code, INE code): addresses} of the ICGC «Adreces simplificat» ZIP (all
    Catalonia): CSV files «;» in UTF-8; the two address tables (adrecavia, adrecaedi) carry `codmuni`
    (INE code and check digit) and `codpostal`, whose content its specification attributes to Correos."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValueError("ICGC: no es un ZIP completo") from None
    names = sorted(n for n in archive.namelist() if re.search(r"-(adrecavia|adrecaedi)-.*\.csv$", n))
    if len(names) != 2:
        raise ValueError(f"ICGC: se esperaban las tablas adrecavia y adrecaedi; hay {archive.namelist()}")
    counts: Counter = Counter()
    for name in names:
        with archive.open(name) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""), delimiter=";")
            if not {"codmuni", "codpostal"} <= set(reader.fieldnames or ()):
                raise ValueError(f"ICGC: faltan columnas en {name}: {reader.fieldnames}")
            for row in reader:
                municipality = (row["codmuni"] or "").strip()
                if not re.fullmatch(r"[0-9]{6}", municipality):
                    raise ValueError(f"ICGC: municipio no válido {municipality!r}")
                counts[postal_code(row["codpostal"]), municipality[:5]] += 1
    return counts


def icgc_zip_url(listing: bytes, base: str) -> str:
    """The newest ZIP of the ICGC directory (adreces-simplificat-v1r0-YYYYMMDD.zip): its name carries
    the date of the edition."""
    found = re.findall(r'href="([^"]*/adreces-simplificat-v[0-9]+r[0-9]+-([0-9]{8})\.zip)"',
                       listing.decode("utf-8", "replace"), re.IGNORECASE)
    if not found:
        raise ValueError("ICGC: el directorio no trae ningún ZIP de direcciones")
    return urljoin(base, max(found, key=lambda f: f[1])[0])


MADRID = "28079"


def madrid_csv_url(content: bytes, resource: str) -> str:
    """URL of the CSV of current addresses in the answer of the datos.madrid.es catalogue (CKAN
    package_show): its file name carries the date."""
    try:
        resources = json.loads(content)["result"]["resources"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("Madrid: respuesta no válida del catálogo") from None
    url = next((r.get("url") for r in resources if r.get("id") == resource), None)
    if not url:
        raise ValueError(f"Madrid: el catálogo no trae el recurso {resource}")
    return url


def check_madrid(content: bytes):
    if b"COD_POSTAL" not in content[:2000]:
        raise ValueError("Madrid: no es el CSV de direcciones")


def parse_madrid(content: bytes) -> Counter:
    """Counter{(postal code, "28079"): addresses} of the official street directory of the Madrid city
    council (CSV «;» in Windows-1252, one row per address, with `COD_POSTAL`)."""
    reader = csv.DictReader(io.StringIO(content.decode("cp1252"), newline=""), delimiter=";")
    if "COD_POSTAL" not in (reader.fieldnames or ()):
        raise ValueError(f"Madrid: falta COD_POSTAL; columnas {reader.fieldnames}")
    counts: Counter = Counter()
    for row in reader:
        counts[postal_code(row["COD_POSTAL"]), MADRID] += 1
    return counts


# Illes Balears (IDEIB) ---------------------------------------------------------------------------

_IDEIB_CODE = re.compile(r"\s([0-9]{5})\s")
_IDEIB_PORTAL = re.compile(r"/ ID_PORTAL:7([0-9]{3})[0-9]{7}$")


def parse_ideib(content: bytes) -> Counter:
    """Counter{(postal code, INE code): portals} of the portals of the Balearic Islands (IDEIB): a CSV
    of one column, ADRECA_DET, «street number  postal code locality municipality / INE_VIA:… /
    ID_VIAL:… / ID_PORTAL:7MMMNNNNNNN», where MMM is the INE number of the municipality."""
    rows = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    if next(rows, None) != ["ADRECA_DET"]:
        raise ValueError("IDEIB: no es el CSV de portales (ADRECA_DET)")
    counts: Counter = Counter()
    for row in rows:
        if not row:
            continue
        text = row[0].strip()
        portal = _IDEIB_PORTAL.search(text)
        if not portal:
            raise ValueError(f"IDEIB: portal sin municipio {text!r}")
        code = _IDEIB_CODE.search(text.split(" / ")[0] + " ")
        counts[code.group(1) if code else "", "07" + portal.group(1)] += 1
    return counts


def check_ideib(content: bytes):
    if not content[:20].decode("utf-8-sig", "replace").lstrip('"').startswith("ADRECA_DET"):
        raise ValueError("IDEIB: no es el CSV de portales")


# Andalucía (CDAU) --------------------------------------------------------------------------------

def parse_cdau(content: bytes) -> Counter:
    """Counter{(postal code, INE code): portals} of the portals of the Callejero Digital de Andalucía
    Unificado: a ZIP with one CSV «;» in UTF-8 (700 MB, read as a stream), with `ine_mun` and
    `cod_postal`."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
    except (zipfile.BadZipFile, StopIteration):
        raise ValueError("CDAU: el ZIP no trae el CSV de portales") from None
    counts: Counter = Counter()
    with archive.open(name) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""), delimiter=";")
        if not {"ine_mun", "cod_postal"} <= set(reader.fieldnames or ()):
            raise ValueError(f"CDAU: faltan columnas; hay {reader.fieldnames}")
        for row in reader:
            municipality = (row["ine_mun"] or "").strip()
            if not re.fullmatch(r"[0-9]{5}", municipality):
                raise ValueError(f"CDAU: municipio no válido {municipality!r}")
            counts[postal_code(row["cod_postal"]), municipality] += 1
    return counts


# INE ---------------------------------------------------------------------------------------------

def ine_street_urls(template: str, today: str) -> list[str]:
    """The electoral street register comes out in January and July: the last three, newest first."""
    year, month = int(today[:4]), int(today[5:7])
    periods = [(year, 7), (year, 1), (year - 1, 7), (year - 1, 1)]
    return [template.format(month=f"{m:02d}", year=y) for y, m in periods if (y, m) <= (year, month)][:3]


def parse_ine_streets(content: bytes) -> Counter:
    """Counter{(postal code, INE code): street sections} of the INE electoral street register: the
    sections file (TRAM…, at times inside a second ZIP), fixed width, with the municipality at 0–5
    and the postal code at 42–47 (the code of each section comes from Correos)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        name = next(n for n in archive.namelist() if "TRAM" in n.upper())
        if name.lower().endswith(".zip"):
            archive = zipfile.ZipFile(io.BytesIO(archive.read(name)))
            name = next(n for n in archive.namelist() if "TRAM" in n.upper())
    except (zipfile.BadZipFile, StopIteration):
        raise ValueError("INE: el ZIP del callejero no trae el fichero de tramos") from None
    pairs, lines, odd = Counter(), 0, 0
    with archive.open(name) as stream:
        for raw in stream:
            lines += 1
            line = raw.decode("cp1252")
            municipality, code = line[0:5], line[42:47]
            if re.fullmatch(r"[0-9]{5}", municipality) and re.fullmatch(r"[0-9]{5}", code):
                pairs[code, municipality] += 1
            else:
                odd += 1
    if not lines or odd > lines * 0.01:
        raise ValueError(f"INE: {odd} de {lines} tramos sin la forma esperada")
    return pairs


# Table -------------------------------------------------------------------------------------------

def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _count(n: int, unit: str) -> str:
    one, many = UNITS[unit]
    return f"1 {one}" if n == 1 else f"{_fmt(n)} {many}"


def covers(source: str, ine: str) -> bool:
    scope = SOURCES[source]["scope"]
    return scope is None or ine.startswith(scope)


def ordered(items: list[dict]) -> list[dict]:
    """The municipalities of a code, as the API gives them: by count when all have the same unit;
    otherwise in the order of the table, which build() sets by the street sections of the INE (counts
    in different units are never compared)."""
    if len({i["unit"] for i in items}) == 1:
        return sorted(items, key=lambda i: (-i["count"], i["id"]))
    return list(items)


def _canonical(rows: list[list]) -> list[list]:
    """Rows by code and, within a code of a single unit, by count; a code with several units keeps
    the order it has."""
    units: dict[str, set] = {}
    for row in rows:
        units.setdefault(row[0], set()).add(row[5])
    return sorted(rows, key=lambda r: (r[0], (-int(r[4]), r[1]) if len(units[r[0]]) == 1 else (0, "")))


def build(counts: dict[str, Counter], data: dict, previous: list[list[str]] | None = None
          ) -> tuple[list[list], list[list], Report]:
    """(rows of the table, observations, report). `counts` has a Counter{(postal code, municipality
    code): n} per source (DGC codes for «catastro», INE codes for the rest), `data` is
    territorios.json and `previous` the rows of the table published before."""
    report = Report()
    towns = {t["id"]: t for t in data["territories"] if t["level"] == "municipality"}
    name = lambda identity: f'{towns[identity]["names"]["display"]} ({identity})'
    ine_of = lambda identity: towns[identity]["codes"]["ine:municipio"]
    by_ine = {t["codes"]["ine:municipio"]: i for i, t in towns.items()}
    by_dgc = {**{dgc: by_ine[ine] for dgc, ine in MERGED_DGC.items() if ine in by_ine},
              **{t["codes"]["dgc:municipio"]: i for i, t in towns.items() if "dgc:municipio" in t["codes"]}}
    order = list(SOURCES)

    # What each source says, harmonised: valid codes of known municipalities within its scope.
    seen: dict[str, dict[tuple, int]] = {}
    for source in order:
        if source not in counts:
            continue
        unit, lookup = SOURCES[source]["unit"], by_dgc if source == "catastro" else by_ine
        found = seen[source] = {}
        unknown, outside, total, empty = Counter(), Counter(), 0, 0
        for (code, number), n in sorted(counts[source].items()):
            total += n
            identity = lookup.get(number)
            if identity is None:
                unknown[number] += n
            elif not covers(source, ine_of(identity)):
                outside[identity] += n
            elif not code:
                empty += n
            elif not valid(code):
                report.add("Códigos postales: código no válido (no se publica)",
                           f"{source}: «{code}» en {name(identity)}, {_count(n, unit)}")
            elif code.endswith("000"):
                report.add("Códigos postales: código de relleno XX000 (no se publica)",
                           f"{source}: {code} en {name(identity)}, {_count(n, unit)}")
            else:
                found[code, identity] = found.get((code, identity), 0) + n
        for number, n in unknown.items():
            report.add(f"Códigos postales: municipio sin cruce en {source} (no se publica)",
                       f"{number}: {_count(n, unit)}")
        for identity, n in outside.items():
            report.add("Códigos postales: municipio fuera del ámbito de la fuente (no se publica)",
                       f"{source}: {name(identity)}, {_count(n, unit)}")
        report.summary[f"fuente {source}"] = (f"{_count(total, unit)}; sin código postal: {_fmt(empty)}; "
                                              f"{_fmt(len(found))} pares")

    by_town: dict[str, dict[str, dict[str, int]]] = {}
    for source, found in seen.items():
        for (code, identity), n in found.items():
            by_town.setdefault(identity, {}).setdefault(source, {})[code] = n

    rows, decided = [], Counter()
    for identity, have in sorted(by_town.items()):
        decider = next(s for s in order if s in have)
        decided[decider] += 1
        missing = [s for s in order[:order.index(decider)] if covers(s, ine_of(identity))]
        if missing:
            report.add("Códigos postales: municipio sin datos en su fuente (decide la siguiente)",
                       f"{name(identity)}: decide {decider}; sin datos en {', '.join(missing)}")
        for code, n in sorted(have[decider].items()):
            also = " ".join(s for s in order if s != decider and code in have.get(s, {}))
            rows.append([code, identity, ine_of(identity), decider, n, SOURCES[decider]["unit"], also])
    # A code whose municipalities have different units goes by the street sections of the INE, the
    # source that covers all Spain (0 if it does not have the pair); then by identifier.
    ine = seen.get("ine", {})
    rows = _canonical(sorted(rows, key=lambda r: (r[0], -ine.get((r[0], r[1]), 0), r[1])))
    units: dict[str, set] = {}
    for row in rows:
        units.setdefault(row[0], set()).add(row[5])
    observations = sorted(([code, identity, ine_of(identity), source, n, SOURCES[source]["unit"]]
                           for source, found in seen.items() for (code, identity), n in found.items()),
                          key=lambda r: (r[0], r[1], order.index(r[3])))

    published = {(r[0], r[1]) for r in rows}
    alone = [r for r in rows if not r[6]]
    report.summary["pares publicados"] = _fmt(len(rows))
    backed = len(rows) - len(alone)
    share = f"{backed / max(len(rows), 1):.1%}".replace(".", ",")
    report.summary["pares que tiene también otra fuente"] = f"{_fmt(backed)} ({share})"
    report.summary["códigos postales"] = _fmt(len({r[0] for r in rows}))
    report.summary["códigos con municipios de fuentes de distinta unidad (por tramos del INE)"] = _fmt(
        sum(len(u) > 1 for u in units.values()))
    report.summary["municipios con código"] = f"{_fmt(len({r[1] for r in rows}))} de {_fmt(len(towns))}"
    for source in order:
        if decided[source]:
            report.summary[f"municipios que decide {source}"] = _fmt(decided[source])
    for code, identity, _, source, n, unit, _ in alone:
        report.add("Códigos postales: pares publicados que no tiene ninguna otra fuente",
                   f"{code} {name(identity)}: {source}, {_count(n, unit)}")
    others: dict[tuple, list[str]] = {}
    for code, identity, _, source, n, unit in observations:
        if (code, identity) not in published:
            others.setdefault((code, identity), []).append(f"{source} {_count(n, unit)}")
    for (code, identity), said in sorted(others.items()):
        if len(said) > 1:
            report.add("Códigos postales: pares de dos o más fuentes que no se publican",
                       f"{code} {name(identity)}: {'; '.join(said)}")
    report.summary["pares de otras fuentes que no se publican"] = _fmt(len(others))
    for code, identity, _, source, n, unit, _ in rows:
        if code[:2] != ine_of(identity)[:2]:
            report.add("Códigos postales: código de otra provincia", f"{code} {name(identity)}: {source}, {_count(n, unit)}")
    for identity in sorted(towns.keys() - by_town.keys()):
        report.add("Códigos postales: municipios sin código postal", name(identity))

    if previous is not None:
        before = {(r[0], r[1]) for r in previous}
        label = lambda identity: name(identity) if identity in towns else identity
        for code, identity in sorted(published - before):
            report.add("Códigos postales: pares nuevos", f"{code} {label(identity)}")
        for code, identity in sorted(before - published):
            report.add("Códigos postales: pares que desaparecen", f"{code} {label(identity)}")
        share = len(published ^ before) / max(len(before), 1)
        report.summary["cambio respecto a la tabla anterior"] = f"{share:.1%}".replace(".", ",")
        if share > CHANGE_WARNING:
            report.add("Códigos postales: aviso", f"cambia el {share:.1%} de los pares (más del "
                       f"{CHANGE_WARNING:.0%}): revisar antes de publicar".replace(".", ","))
    return rows, observations, report


def check_cases(rows: list[list]) -> list[str]:
    """The fixed cases (CASES) that the rows do not meet."""
    problems = []
    by_code: dict[str, list] = {}
    for code, identity, _, _, n, unit, *_ in rows:
        by_code.setdefault(code, []).append({"id": identity, "count": int(n), "unit": unit})
    for identity, codes in CASES["includes"].items():
        have = {code for code, other, *_ in rows if other == identity}
        missing = [c for c in codes if c not in have]
        if missing:
            problems.append(f"{identity} no tiene {', '.join(missing)}")
    for code, expected in CASES["first"].items():
        found = [i["id"] for i in ordered(by_code.get(code, []))][:len(expected)]
        if found != expected:
            problems.append(f"{code} da {found}, se esperaba {expected}")
    return problems


def table(rows: list[list], header: list[str] = HEADER) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def read_table(path: Path, header: list[str] = HEADER) -> list[list[str]] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    if not rows or rows[0] != header:
        raise ValueError(f"{path}: cabecera inesperada")
    return rows[1:]


def check(path: Path, header: list[str] = HEADER) -> list[str]:
    """Problems of a published table or of its observations (empty if it is consistent).
    Municipalities that no longer exist are not a problem here: they go to the generator's report
    (orphans)."""
    try:
        rows = read_table(path, header)
    except ValueError as error:
        return [str(error)]
    order = list(SOURCES)
    key = (lambda r: (r[0], r[1])) if header == HEADER else (lambda r: (r[0], r[1], order.index(r[3])))
    canonical = _canonical if header == HEADER else lambda rows: sorted(rows, key=key)
    problems, seen = [], set()
    for row in rows:
        if len(row) != len(header):
            problems.append(f"{path.name}: fila con {len(row)} campos: {row}")
            continue
        code, identity, ine, source, n, unit = row[:6]
        also = row[6].split(" ") if header == HEADER and row[6] else []
        if not valid(code) or code.endswith("000") or identity != f"es:municipio:{ine}" \
                or not re.fullmatch(r"[0-9]{5}", ine) or not n.isdigit() or int(n) < 1 \
                or source not in SOURCES or unit != SOURCES[source]["unit"] or key(row) in seen \
                or any(s not in SOURCES or s == source for s in also) or also != sorted(also, key=order.index):
            problems.append(f"{path.name}: fila no válida o repetida: {row}")
            continue
        seen.add(key(row))
    if not problems and path.read_text(encoding="utf-8") != table(canonical(rows), header):
        problems.append(f"{path.name} no está en forma canónica")
    return problems


def orphans(path: Path, data: dict) -> list[str]:
    """Municipalities of the published table that are not in territorios.json (a merger with the new
    INE dictionary): they are fixed by running the postal-code workflow again."""
    rows = read_table(path) or []
    known = {t["id"] for t in data["territories"]}
    return sorted({f"{identity}: relanzar codigos-postales.yml" for _, identity, *_ in rows if identity not in known})


def write(folder: Path, rows: list[list], observations: list[list], records: dict):
    """The table, its observations and their entries in manifiesto.json (the rest of the manifest is
    generar.yml's)."""
    path = folder / "manifiesto.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for name, text in ((FILE, table(rows)), (OBSERVATIONS, table(observations, OBSERVATION_HEADER))):
        (folder / name).write_text(text, encoding="utf-8")
        manifest["files"][name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    manifest["sources"].update(records)
    manifest["files"] = dict(sorted(manifest["files"].items()))
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
