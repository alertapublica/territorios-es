"""Instituto Geográfico Nacional (IGN): the capital of each municipality and the municipal
boundaries. Both CC BY 4.0 (Orden FOM/2807/2015).

- Places: the IGN features API (OGC API Features), collections «nuc» (Núcleos de población) and
  «opob» (Otras poblaciones) of the IGR Poblaciones product, read whole. Each place has its own
  identifier, the INE code of the entity it belongs to (11 digits, the first 5 are the
  municipality; only the municipality for many in «opob»), its name, coordinates, altitude and
  `capital`, one digit per level (State, community, province, municipality): Madrid 1111…,
  Ourense 0011…, Santiago de Compostela 0101…. «opob» also has a kind (OPOB, NUCL, BARR, URBA are
  populations; the rest are facilities). They give the capital of each municipality and the
  spelling of the names of the population entities (entidades.py).
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
POPULATION_FIELDS = "codine,nombre,capital,longitud,latitud,altitud"
OTHER_FIELDS = POPULATION_FIELDS + ",tipo"
PAGE = 5000
LIMITS_URL = "https://centrodedescargas.cnig.es/CentroDescargas/documentos/atom/au/lineas_limite_gml.zip"
_UNITS_FILE = re.compile(r"au_AdministrativeUnit_4thOrder\d*\.gml$")
_GML = "{http://www.opengis.net/gml/3.2}"
_AU = "{http://inspire.ec.europa.eu/schemas/au/4.0}"
_GN = "{http://inspire.ec.europa.eu/schemas/gn/4.0}"
_GMD = "{http://www.isotc211.org/2005/gmd}"


def populations_url(offset: int, limit: int = PAGE, other: bool = False) -> str:
    """A page of núcleos, or with other=True of the other populations."""
    query = {"f": "json", "skipGeometry": "true", "properties": OTHER_FIELDS if other else POPULATION_FIELDS,
             "limit": limit, "offset": offset}
    return (OTHER_POPULATIONS_URL if other else POPULATIONS_URL) + "?" + urlencode(query)


def parse_populations(content: bytes, collection: str = "nuc") -> tuple[list[list], int, int]:
    """([[INE entity code, name, capital digits, lon, lat, altitude, reference, kind], …], total
    number of places in the collection, places left out). The reference is «ign:nuc/<id>» or
    «ign:opob/<id>»; the kind is NUC for a núcleo. A place without a valid code or name is left out
    (one in «opob»); a capital must have its coordinates."""
    try:
        answer = json.loads(content)
        matched = int(answer["numberMatched"])
        features = answer["features"]
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f"IGN: respuesta no válida ({error})") from None
    rows, skipped = [], 0
    for feature in features:
        p = feature.get("properties") or {}
        code, name, capital = str(p.get("codine") or ""), str(p.get("nombre") or "").strip(), str(p.get("capital") or "0000")
        if not re.fullmatch(r"[0-9]{11}", code) or not name or not isinstance(feature.get("id"), int):
            skipped += 1
            continue
        if not re.fullmatch(r"[01]{4,}", capital):
            raise ValueError(f"IGN: lugar con capital no válida: {p!r}")
        try:
            lon, lat = float(p["longitud"]), float(p["latitud"])
        except (KeyError, TypeError, ValueError):
            if capital[3] == "1":
                raise ValueError(f"IGN: capital {code} sin coordenadas") from None
            lon = lat = None
        altitude = p.get("altitud")
        rows.append([code, name, capital, lon, lat, None if altitude is None else float(altitude),
                     f"ign:{collection}/{feature['id']}", str(p.get("tipo") or "NUC") if collection == "opob" else "NUC"])
    return rows, matched, skipped


def municipal_capitals(rows: list[list]) -> list[list]:
    """[[INE municipality, INE entity, name, lon, lat, altitude, reference], …] of the places marked
    as the capital of their municipality (fourth digit of `capital`)."""
    return sorted([code[:5], code, name, round(lon, 6), round(lat, 6), None if alt is None else round(alt, 1), ref]
                  for code, name, capital, lon, lat, alt, ref, _ in rows if capital[3] == "1")


def places(rows: list[list]) -> list[list[str]]:
    """[[INE entity code, name, reference, kind], …] of every place, for the names of the entities."""
    return sorted([code, name, ref, kind] for code, name, _, _, _, _, ref, kind in rows)


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
