"""The municipal boundaries file published with each release (limites-municipios.geojson.gz):
the BDLJE units simplified to a few metres, with our identifiers. Derived work of the IGN data
(CC BY 4.0): the attribution travels inside the file, as the IGN licence asks for metadata."""
from __future__ import annotations

import gzip
import json

from territorios_es import geo

TOLERANCE_M = 5.0
DECIMALS = 5  # ~1 m
ATTRIBUTION = "Obra derivada de BDLJE Continua CC-BY 4.0 ign.es"


def _coordinates(ring) -> list[list[float]]:
    return [[round(ring[i], DECIMALS), round(ring[i + 1], DECIMALS)] for i in range(0, len(ring), 2)]


def build_limits(units: list[list], data: dict, source: dict, tolerance: float = TOLERANCE_M) -> tuple[bytes, dict]:
    """(gzip of the GeoJSON, counts). `data` is territorios.json: units are linked to municipalities
    by their BDDAE code, as the generator did; the others (shared areas) keep only their code."""
    ids = {t["codes"]["ign:bddae"]: t["id"] for t in data["territories"] if "ign:bddae" in t["codes"]}
    features, before, after = [], 0, 0
    for code, kind, label, polygons in units:
        rings = []
        for polygon in polygons:
            simple = [geo.simplify_ring(ring, tolerance) for ring in polygon]
            before += sum(len(r) for r in polygon) // 2
            after += sum(len(r) for r in simple) // 2
            rings.append([_coordinates(r) for r in simple])
        feature = {"type": "Feature"}
        if code in ids:
            feature["id"] = ids[code]
        feature["properties"] = {"bddae": code, "kind": kind, "name": label}
        feature["geometry"] = {"type": "MultiPolygon", "coordinates": rings}
        features.append(feature)
    collection = {"type": "FeatureCollection", "attribution": ATTRIBUTION, "licence": "CC BY 4.0",
                  "source": source, "reference_date": data.get("reference_date"),
                  "simplification_m": tolerance, "features": features}
    text = json.dumps(collection, ensure_ascii=False, separators=(",", ":"))
    counts = {"features": len(features), "linked": sum("id" in f for f in features),
              "points_before": before, "points_after": after, "bytes_json": len(text.encode())}
    return gzip.compress(text.encode(), mtime=0), counts
