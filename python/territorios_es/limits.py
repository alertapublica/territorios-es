"""From a point to its municipality, without network, with the boundaries file attached to each
release (limites-municipios.geojson.gz: IGN boundaries simplified to 5 m, CC BY 4.0, «Obra
derivada de BDLJE Continua CC-BY 4.0 ign.es»). js/limits.js mirrors this file.

    limits = te.load_limits("limites-municipios.geojson.gz")
    te.locate(-7.8639, 42.3355, limits)["territory"]   # 'es:municipio:32054'

The boundaries have an uncertainty of about 40 m, so a point closer than 50 m to another unit is
pending, never «the nearest one».
"""
from __future__ import annotations

import gzip
import json
import math
import os
from pathlib import Path

from . import geo
from .relation import relation

MARGIN_M = 50.0


class Limits:
    def __init__(self, collection: dict):
        if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
            raise ValueError("Not a GeoJSON FeatureCollection")
        self.attribution = collection.get("attribution")
        self.reference_date = collection.get("reference_date")
        self._units = []
        for feature in collection.get("features") or []:
            geometry = feature.get("geometry") or {}
            if geometry.get("type") == "Polygon":
                shapes = [geometry["coordinates"]]
            elif geometry.get("type") == "MultiPolygon":
                shapes = geometry["coordinates"]
            else:
                raise ValueError(f"Unsupported geometry {geometry.get('type')!r}")
            polygons = [[[v for point in ring for v in point[:2]] for ring in shape] for shape in shapes]
            properties = feature.get("properties") or {}
            self._units.append((feature.get("id"), properties.get("bddae"), polygons, geo.bbox(polygons)))

    def __len__(self):
        return len(self._units)

    def locate(self, lon: float, lat: float, margin: float = MARGIN_M) -> dict:
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (lon, lat, margin)) \
                or not (-180 <= lon <= 180 and -90 <= lat <= 90) or margin < 0:
            raise ValueError("lon and lat must be finite degrees, margin a distance in metres")
        dy = margin / geo.METRES_PER_DEGREE
        dx = dy / max(math.cos(math.radians(lat)), 1e-6)
        inside, near, evidence = [], [], []
        for identity, code, polygons, (x1, y1, x2, y2) in self._units:
            if not (x1 - dx <= lon <= x2 + dx and y1 - dy <= lat <= y2 + dy):
                continue
            is_inside = geo.contains(polygons, lon, lat)
            gap = geo.distance(polygons, lon, lat)
            if not is_inside and gap > margin:
                continue
            (inside if is_inside else near).append(identity)
            evidence.append({"source": "ign:limits", "datum": [lon, lat], "territory": identity, "bddae": code,
                             "inside": is_inside, "distance_m": round(gap, 1)})
        evidence.sort(key=lambda e: (not e["inside"], e["distance_m"], e["bddae"] or ""))
        known = [i for i in inside + near if i]
        if len(inside) > 1:
            return relation("conflict", None, known, "overlap", evidence)
        if inside and inside[0] is None:
            return relation("pending", None, known, "shared_area", evidence)
        if inside and not near:
            return relation("resolved", inside[0], inside, "inside", evidence)
        if inside or near:
            return relation("pending", None, known, "near_boundary", evidence)
        return relation("pending", None, (), "outside", evidence)


def load_limits(path: str | os.PathLike) -> Limits:
    """Limits from the release file, compressed (.gz) or not."""
    raw = Path(path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return Limits(json.loads(raw))


def locate(lon: float, lat: float, limits: Limits | str | os.PathLike, margin: float = MARGIN_M) -> dict:
    """The municipality of a point: resolved inside one municipality and more than `margin` metres
    from any other unit; pending near a boundary, in a shared area or outside every unit (the sea,
    abroad); conflict if the point is inside two units."""
    if not isinstance(limits, Limits):
        limits = load_limits(limits)
    return limits.locate(lon, lat, margin)
