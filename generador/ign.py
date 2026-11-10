"""Instituto Geográfico Nacional (IGN): the capital of each municipality and the municipal
boundaries. Both CC BY 4.0 (Orden FOM/2807/2015).

- Capitals: the IGN features API (OGC API Features), collection «nuc» (Núcleos de población, from
  the IGR Poblaciones product). Each núcleo has its INE entity code (11 digits, the first 5 are the
  municipality), coordinates, altitude and `capital`, one digit per level (State, community,
  province, municipality): Madrid 1111…, Ourense 0011…, Santiago de Compostela 0101…. Some
  capitals are not núcleos for the INE: they are in the collection «opob» (Otras poblaciones) of
  the same product, read only for the places marked as municipal capitals (`capital=000100`).
- Boundaries: Base de Datos de Límites Jurisdiccionales de España (BDLJE), a zip of INSPIRE GML
  files. Each municipal unit has a national code: 34 + community (2) + province (2) + INE (5).
"""
from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from array import array
from urllib.parse import urlencode

POPULATIONS_URL = "https://api-features.ign.es/collections/nuc/items"
OTHER_POPULATIONS_URL = "https://api-features.ign.es/collections/opob/items"
OTHER_CAPITALS = "000100"
POPULATION_FIELDS = "codine,nombre,capital,longitud,latitud,altitud"
PAGE = 5000
LIMITS_URL = "https://centrodedescargas.cnig.es/CentroDescargas/documentos/atom/au/lineas_limite_gml.zip"
_UNITS_FILE = re.compile(r"au_AdministrativeUnit_4thOrder\d*\.gml$")
_GML = "{http://www.opengis.net/gml/3.2}"
_AU = "{http://inspire.ec.europa.eu/schemas/au/4.0}"
_GN = "{http://inspire.ec.europa.eu/schemas/gn/4.0}"
_GMD = "{http://www.isotc211.org/2005/gmd}"


def populations_url(offset: int, limit: int = PAGE, other: bool = False) -> str:
    """A page of núcleos, or with other=True of the other populations marked as municipal capitals."""
    query = {"f": "json", "skipGeometry": "true", "properties": POPULATION_FIELDS, "limit": limit, "offset": offset}
    if other:
        query["capital"] = OTHER_CAPITALS
    return (OTHER_POPULATIONS_URL if other else POPULATIONS_URL) + "?" + urlencode(query)


def parse_populations(content: bytes) -> tuple[list[list], int]:
    """([[INE entity code, name, capital digits, lon, lat, altitude or None], …], total number of
    núcleos in the collection)."""
    try:
        answer = json.loads(content)
        matched = int(answer["numberMatched"])
        features = answer["features"]
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"IGN: respuesta no válida ({error})") from None
    rows = []
    for feature in features:
        p = feature.get("properties") or {}
        code, capital = str(p.get("codine") or ""), str(p.get("capital") or "")
        if not re.fullmatch(r"[0-9]{11}", code) or not re.fullmatch(r"[01]{4,}", capital):
            raise ValueError(f"IGN: núcleo con código o capital no válidos: {p!r}")
        try:
            lon, lat = float(p["longitud"]), float(p["latitud"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"IGN: núcleo {code} sin coordenadas") from None
        altitude = p.get("altitud")
        rows.append([code, str(p.get("nombre") or "").strip(), capital, lon, lat,
                     None if altitude is None else float(altitude)])
    return rows, matched


def municipal_capitals(rows: list[list]) -> list[list]:
    """[[INE municipality, INE entity, name, lon, lat, altitude], …] of the núcleos marked as the
    capital of their municipality (fourth digit of `capital`)."""
    return sorted([code[:5], code, name, round(lon, 6), round(lat, 6), None if alt is None else round(alt, 1)]
                  for code, name, capital, lon, lat, alt in rows if capital[3] == "1")


def _ring(pos_list: str) -> array:
    """GML posList in EPSG:4258 axis order (latitude longitude) to a flat [lon, lat, …] ring."""
    values = array("d", map(float, pos_list.split()))
    if len(values) < 8 or len(values) % 2:
        raise ValueError("IGN: anillo no válido")
    ring = array("d", values)
    ring[0::2], ring[1::2] = values[1::2], values[0::2]
    return ring


def check_zip(content: bytes):
    if content[:2] != b"PK":
        raise ValueError("IGN: la descarga de límites no es un zip")


def parse_units(content: bytes) -> list[list]:
    """[[national code (11 digits), kind («Municipio»…), name, polygons], …] from the BDLJE zip.
    Polygons are lists of flat rings (geo.py)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise ValueError("IGN: el fichero de límites no es un zip") from None
    names = sorted(n for n in archive.namelist() if _UNITS_FILE.search(n))
    if not names:
        raise ValueError("IGN: el zip no trae las unidades municipales (4thOrder)")
    units = []
    for name in names:
        with archive.open(name) as file:
            for _, element in ET.iterparse(file):
                if element.tag != _AU + "AdministrativeUnit":
                    continue
                code = (element.findtext(_AU + "nationalCode") or "").strip()
                if not re.fullmatch(r"[0-9]{11}", code):
                    raise ValueError(f"IGN: unidad con código no válido {code!r}")
                kind = (element.findtext(f"{_AU}nationalLevelName/{_GMD}LocalisedCharacterString") or "").strip()
                label = (element.findtext(f".//{_GN}SpellingOfName/{_GN}text") or "").strip()
                polygons = []
                for polygon in element.iter(_GML + "Polygon"):
                    rings = [_ring(p.text or "") for p in polygon.iter(_GML + "posList")]
                    if rings:
                        polygons.append(rings)
                if not polygons:
                    raise ValueError(f"IGN: unidad {code} sin geometría")
                units.append([code, kind, label, polygons])
                element.clear()
    return sorted(units, key=lambda unit: unit[0])
