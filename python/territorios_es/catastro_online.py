"""Optional: places a cadastral reference or a point with the Catastro's free web services.

This is the only part of the library that uses the network, and only when called. Each call makes
one request (two for a point) to ovc.catastro.meh.es: do not run it in a loop without a pause.
Nothing is stored. js/catastro_online.js mirrors this file.

    from territorios_es.catastro_online import locate_reference, locate_point
    locate_reference("9872023VH5797S0001WX")["territory"]   # 'es:municipio:13077'
    locate_point(-3.6, 39.2)["territory"]                   # 'es:municipio:13096'
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .catastro import parse_cadastral_reference, relate_cadastral_reference
from .relation import combine, relation

SERVICE = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC"
USER_AGENT = "territorios-es (+https://github.com/alertapublica/territorios-es)"
_NS = "{http://www.catastro.meh.es/}"


class CatastroError(RuntimeError):
    """The service could not be reached or gave an answer that cannot be read."""


def default_fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except OSError as error:
        raise CatastroError(f"Catastro: {error}") from error


def _catalog(catalog):
    if catalog is None:
        from . import load
        return load()
    return catalog


def _answer(content: bytes) -> tuple[ET.Element, list[str]]:
    """(root, error messages of the service)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise CatastroError(f"Catastro: respuesta no válida ({error})") from None
    return root, [(e.findtext(_NS + "des") or "").strip() for e in root.iter(_NS + "err")]


def _ine_codes(root: ET.Element) -> set[str]:
    codes = set()
    for loine in root.iter(_NS + "loine"):
        province, municipality = (loine.findtext(_NS + "cp") or "").strip(), (loine.findtext(_NS + "cm") or "").strip()
        if not re.fullmatch(r"[0-9]{1,2}", province) or not re.fullmatch(r"[0-9]{1,3}", municipality):
            raise CatastroError(f"Catastro: código del INE no válido {province!r} {municipality!r}")
        codes.add(province.zfill(2) + municipality.zfill(3))
    return codes


def _by_reference(catalog, parcel: str, fetch) -> dict:
    url = f"{SERVICE}/OVCCallejero.asmx/Consulta_DNPRC?" + urllib.parse.urlencode(
        {"Provincia": "", "Municipio": "", "RC": parcel})
    root, errors = _answer(fetch(url))
    source = "catastro:Consulta_DNPRC"
    if errors:
        return relation("pending", None, (), "not_found",
                        [{"source": source, "datum": parcel, "territory": None, "reason": "; ".join(errors)}])
    codes = _ine_codes(root)
    found = {code: catalog.resolve("ine:municipio", code) for code in sorted(codes)}
    evidence = [{"source": source, "datum": parcel, "territory": t["id"] if t else None, "reason": f"ine:{code}"}
                for code, t in found.items()]
    ids = sorted({t["id"] for t in found.values() if t})
    if len(codes) > 1:
        return relation("conflict", None, ids, "conflict", evidence)
    if len(ids) == 1:
        return relation("resolved", ids[0], ids, "catastro", evidence)
    return relation("pending", None, (), "not_found", evidence)


def locate_reference(text: str, catalog=None, fetch=None) -> dict:
    """Municipality of a cadastral reference (urban or rustic) according to the Catastro. A rustic
    reference is also read offline: both must agree, or the relation is a conflict."""
    catalog = _catalog(catalog)
    offline = relate_cadastral_reference(catalog, text)
    if offline["reason"] in ("not_a_reference", "invalid_check"):
        return offline
    online = _by_reference(catalog, parse_cadastral_reference(text)["parcel"], fetch or default_fetch)
    return combine(offline, online) if offline["status"] == "resolved" else online


def locate_point(lon: float, lat: float, srs: str = "EPSG:4326", catalog=None, fetch=None) -> dict:
    """Municipality at a point according to the Catastro: the parcel there, then its municipality.
    Pending when there is no parcel (the sea, or the foral territories, which are not in the
    Catastro). The parcel found is in the evidence."""
    catalog, fetch = _catalog(catalog), fetch or default_fetch
    point = f"{lon},{lat}"
    url = f"{SERVICE}/OVCCoordenadas.asmx/Consulta_RCCOOR?" + urllib.parse.urlencode(
        {"SRS": srs, "Coordenada_X": lon, "Coordenada_Y": lat})
    root, errors = _answer(fetch(url))
    source = "catastro:Consulta_RCCOOR"
    parcels = sorted({(pc.findtext(_NS + "pc1") or "").strip() + (pc.findtext(_NS + "pc2") or "").strip()
                      for pc in root.iter(_NS + "pc")})
    if errors or not parcels:
        return relation("pending", None, (), "not_found",
                        [{"source": source, "datum": point, "territory": None, "reason": "; ".join(errors)}])
    if len(parcels) > 1 or parse_cadastral_reference(parcels[0]) is None:
        raise CatastroError(f"Catastro: parcela no válida en {point}: {parcels}")
    found = _by_reference(catalog, parcels[0], fetch)
    first = {"source": source, "datum": point, "territory": None, "reason": parcels[0]}
    return relation(found["status"], found["territory"], found["candidates"], found["reason"],
                    [first, *found["evidence"]])
