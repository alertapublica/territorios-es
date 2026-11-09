"""Plane geometry on longitude/latitude, small enough for municipal boundaries. js/geo.js mirrors
this file.

A ring is a flat sequence [lon0, lat0, lon1, lat1, …] whose last point repeats the first; a polygon
is a list of rings (the exterior first, then the holes). Distances use a local equirectangular
projection: within a few kilometres the error is far below the 40 m uncertainty of the IGN
boundaries.
"""
from __future__ import annotations

import math

METRES_PER_DEGREE = 111_320.0


def ring_contains(ring, x: float, y: float) -> bool:
    """Even-odd rule (ray casting)."""
    inside = False
    n = len(ring)
    x1, y1 = ring[n - 2], ring[n - 1]
    for i in range(0, n, 2):
        x2, y2 = ring[i], ring[i + 1]
        if (y2 > y) != (y1 > y) and x < (x1 - x2) * (y - y2) / (y1 - y2) + x2:
            inside = not inside
        x1, y1 = x2, y2
    return inside


def polygon_contains(polygon, x: float, y: float) -> bool:
    return ring_contains(polygon[0], x, y) and not any(ring_contains(hole, x, y) for hole in polygon[1:])


def contains(polygons, x: float, y: float) -> bool:
    return any(polygon_contains(polygon, x, y) for polygon in polygons)


def ring_distance(ring, x: float, y: float) -> float:
    """Metres from the point to the nearest side of the ring."""
    kx = math.cos(math.radians(y)) * METRES_PER_DEGREE
    ky = METRES_PER_DEGREE
    best = math.inf
    ax, ay = (ring[0] - x) * kx, (ring[1] - y) * ky
    for i in range(2, len(ring), 2):
        bx, by = (ring[i] - x) * kx, (ring[i + 1] - y) * ky
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
        px, py = ax + t * dx, ay + t * dy
        best = min(best, px * px + py * py)
        ax, ay = bx, by
    return math.sqrt(best)


def distance(polygons, x: float, y: float) -> float:
    """Metres from the point to the nearest boundary (0 on the boundary; also from inside)."""
    return min((ring_distance(ring, x, y) for polygon in polygons for ring in polygon), default=math.inf)


def bbox(polygons) -> tuple[float, float, float, float]:
    xs = [v for polygon in polygons for i, v in enumerate(polygon[0]) if i % 2 == 0]
    ys = [v for polygon in polygons for i, v in enumerate(polygon[0]) if i % 2 == 1]
    return min(xs), min(ys), max(xs), max(ys)


def simplify_ring(ring, tolerance: float) -> list[float]:
    """Douglas-Peucker with a tolerance in metres. A ring that would collapse (fewer than four
    points) is kept as it was."""
    n = len(ring) // 2
    if n <= 4:
        return list(ring)
    kx = math.cos(math.radians(ring[1])) * METRES_PER_DEGREE
    ky = METRES_PER_DEGREE
    px = [ring[2 * i] * kx for i in range(n)]
    py = [ring[2 * i + 1] * ky for i in range(n)]
    # Split the closed ring at the point farthest from its start, then simplify both halves.
    far = max(range(n), key=lambda i: (px[i] - px[0]) ** 2 + (py[i] - py[0]) ** 2)
    keep = [False] * n
    keep[0] = keep[far] = keep[n - 1] = True
    stack = [(0, far), (far, n - 1)]
    limit = tolerance * tolerance
    while stack:
        first, last = stack.pop()
        if last - first < 2:
            continue
        ax, ay = px[first], py[first]
        dx, dy = px[last] - ax, py[last] - ay
        length = dx * dx + dy * dy
        worst, index = -1.0, -1
        for i in range(first + 1, last):
            ex, ey = px[i] - ax, py[i] - ay
            if length == 0:
                d = ex * ex + ey * ey
            else:
                cross = ex * dy - ey * dx
                d = cross * cross / length
            if d > worst:
                worst, index = d, i
        if worst > limit:
            keep[index] = True
            stack += [(first, index), (index, last)]
    out = [v for i in range(n) if keep[i] for v in (ring[2 * i], ring[2 * i + 1])]
    return out if len(out) >= 8 else list(ring)
