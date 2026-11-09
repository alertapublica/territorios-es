"""Cadastral references (referencia catastral) of the Dirección General del Catastro, offline.
js/catastro.js mirrors this file.

A reference has 14 characters for the parcel, then 4 for the property inside it (cargo) and 2
check letters: 20 in all. A rustic parcel carries its municipality (DGC code: office 2 +
municipality 3, then sector, polygon and parcel); an urban one does not (block, parcel and map
sheet), so it can only be placed with the Catastro's own services, which this module never calls.
"""
from __future__ import annotations

import re

from .relation import relation

_WEIGHTS = (13, 15, 12, 5, 4, 17, 9, 21, 3, 7, 1)
_LETTERS = "MQWERTYUIOPASDFGHJKLBZX"
_RUSTIC = re.compile(r"[0-9]{5}[A-ZÑ][0-9]{8}")
_URBAN = re.compile(r"[0-9]{7}[A-ZÑ]{2}[0-9]{4}[A-ZÑ]")
_SHAPE = re.compile(r"[0-9A-ZÑ]{14}(?:[0-9]{4}(?:[A-ZÑ]{2})?)?")


def _value(char: str) -> int:
    if char.isdigit():
        return int(char)
    if char == "Ñ":
        return 15
    return ord(char) - 64 if char <= "N" else ord(char) - 63  # A=1 … N=14, Ñ=15, O=16 … Z=27


def check_letters(reference: str) -> str:
    """The two check letters of an 18-character reference (parcel + property)."""
    if not _SHAPE.fullmatch(reference) or len(reference) < 18:
        raise ValueError(f"Not an 18-character cadastral reference: {reference!r}")
    tail = reference[14:18]
    return "".join(_LETTERS[sum(_value(c) * w for c, w in zip(part + tail, _WEIGHTS)) % 23]
                   for part in (reference[:7], reference[7:14]))


def parse_cadastral_reference(text: str) -> dict | None:
    """Parts of a reference, or None if the text does not look like one. Spaces and case are
    ignored. `valid` is None when there are no check letters to verify."""
    if not isinstance(text, str):
        return None
    reference = re.sub(r"\s+", "", text).upper()
    if not _SHAPE.fullmatch(reference):
        return None
    parcel = reference[:14]
    kind = "rustic" if _RUSTIC.fullmatch(parcel) else "urban" if _URBAN.fullmatch(parcel) else "other"
    check = reference[18:] or None
    return {"reference": reference, "parcel": parcel, "kind": kind, "property": reference[14:18] or None,
            "check": check, "valid": None if check is None else check == check_letters(reference[:18]),
            "dgc": parcel[:5] if kind == "rustic" else None}


def relate_cadastral_reference(catalog, text: str) -> dict:
    """Municipality of a reference: resolved for a rustic parcel whose DGC code is known; pending
    otherwise (an urban reference does not say where it is). Never calls the Catastro."""
    parsed = parse_cadastral_reference(text)
    if parsed is None:
        return relation("pending", None, (), "not_a_reference")
    if parsed["valid"] is False:
        return relation("pending", None, (), "invalid_check")
    if parsed["kind"] != "rustic":
        return relation("pending", None, (), parsed["kind"])
    found = catalog.resolve("dgc:municipio", parsed["dgc"])
    if found is None:
        return relation("pending", None, (), "not_found")
    evidence = [{"source": "cadastral_reference", "datum": parsed["reference"], "territory": found["id"],
                 "reason": "dgc:municipio"}]
    return relation("resolved", found["id"], [found["id"]], "cadastral_reference", evidence)
