"""Dirección General del Catastro (DGC): municipality codes from its free web services
(OVCCallejero, ConsultaProvincia and ConsultaMunicipio).

The DGC numbers municipalities on its own: A Coruña is INE 15030 and DGC 15900. Each answer gives
both codes, so the crosswalk comes from the DGC itself, not from matching names. The services
leave out Álava, Gipuzkoa, Navarra and Bizkaia, which have their own (foral) cadastre.

Licence (DGC, July 2016): public and commercial use only of transformed information; the original
answers are not redistributed. They are cached in Actions only, never committed.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

SERVICE = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx"
PROVINCES_URL = SERVICE + "/ConsultaProvincia"
# Provinces with a foral cadastre (INE codes): not in the DGC services.
FORAL = ("01", "20", "31", "48")
_NS = "{http://www.catastro.meh.es/}"


def municipalities_url(province_name: str) -> str:
    return f"{SERVICE}/ConsultaMunicipio?Provincia={quote(province_name)}&Municipio="


def _root(content: bytes, expected: str) -> ET.Element:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise ValueError(f"Catastro: XML no válido ({error})") from None
    if root.tag != _NS + expected:
        raise ValueError(f"Catastro: respuesta inesperada <{root.tag}>")
    errors = [e.findtext(_NS + "des") or "" for e in root.iter(_NS + "err")]
    if errors:
        raise ValueError(f"Catastro: {'; '.join(errors)}")
    return root


def _count(root: ET.Element, tag: str) -> int:
    value = root.findtext(f"{_NS}control/{_NS}{tag}") or ""
    if not value.isdigit():
        raise ValueError(f"Catastro: falta el recuento <{tag}>")
    return int(value)


def _code(value: str | None, width: int) -> str:
    """The services write codes as numbers without leading zeros ("7"); both codes have a fixed
    width (province 2, municipality 3), so the zeros are part of the code, not a guess."""
    value = (value or "").strip()
    if not re.fullmatch(r"[0-9]{1,%d}" % width, value):
        raise ValueError(f"Catastro: código no válido {value!r}")
    return value.zfill(width)


def parse_provinces(content: bytes) -> list[list[str]]:
    """[[INE province code, name as the DGC writes it], …] sorted by code."""
    root = _root(content, "consulta_provinciero")
    rows = [[_code(p.findtext(_NS + "cpine"), 2), (p.findtext(_NS + "np") or "").strip()]
            for p in root.iter(_NS + "prov")]
    if len(rows) != _count(root, "cuprov") or not all(name for _, name in rows):
        raise ValueError("Catastro: lista de provincias incompleta")
    return sorted(rows)


def parse_municipalities(content: bytes) -> list[list[str]]:
    """[[DGC code (delegation 2 + municipality 3), INE code (5), name as the DGC writes it], …]."""
    root = _root(content, "consulta_municipiero")
    rows = []
    for m in root.iter(_NS + "muni"):
        dgc = _code(m.findtext(f"{_NS}locat/{_NS}cd"), 2) + _code(m.findtext(f"{_NS}locat/{_NS}cmc"), 3)
        ine = _code(m.findtext(f"{_NS}loine/{_NS}cp"), 2) + _code(m.findtext(f"{_NS}loine/{_NS}cm"), 3)
        name = (m.findtext(_NS + "nm") or "").strip()
        if not name:
            raise ValueError(f"Catastro: municipio {dgc} sin nombre")
        rows.append([dgc, ine, name])
    if len(rows) != _count(root, "cumun"):
        raise ValueError("Catastro: lista de municipios incompleta")
    return sorted(rows)
