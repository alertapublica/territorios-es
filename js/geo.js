// Plane geometry on longitude/latitude. Mirrors python/territorios_es/geo.py: a ring is a flat
// array [lon0, lat0, lon1, lat1, …] whose last point repeats the first; a polygon is a list of
// rings (exterior first, then holes). Distances use a local equirectangular projection.
export const METRES_PER_DEGREE = 111320;

export function ringContains(ring, x, y) {
  let inside = false;
  const n = ring.length;
  let x1 = ring[n - 2];
  let y1 = ring[n - 1];
  for (let i = 0; i < n; i += 2) {
    const x2 = ring[i];
    const y2 = ring[i + 1];
    if ((y2 > y) !== (y1 > y) && x < ((x1 - x2) * (y - y2)) / (y1 - y2) + x2) inside = !inside;
    x1 = x2;
    y1 = y2;
  }
  return inside;
}

export const polygonContains = (polygon, x, y) =>
  ringContains(polygon[0], x, y) && !polygon.slice(1).some((hole) => ringContains(hole, x, y));

export const contains = (polygons, x, y) => polygons.some((polygon) => polygonContains(polygon, x, y));

export function ringDistance(ring, x, y) {
  const kx = Math.cos((y * Math.PI) / 180) * METRES_PER_DEGREE;
  const ky = METRES_PER_DEGREE;
  let best = Infinity;
  let ax = (ring[0] - x) * kx;
  let ay = (ring[1] - y) * ky;
  for (let i = 2; i < ring.length; i += 2) {
    const bx = (ring[i] - x) * kx;
    const by = (ring[i + 1] - y) * ky;
    const dx = bx - ax;
    const dy = by - ay;
    const length = dx * dx + dy * dy;
    const t = length === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / length));
    const px = ax + t * dx;
    const py = ay + t * dy;
    best = Math.min(best, px * px + py * py);
    ax = bx;
    ay = by;
  }
  return Math.sqrt(best);
}

export function distance(polygons, x, y) {
  let best = Infinity;
  for (const polygon of polygons) for (const ring of polygon) best = Math.min(best, ringDistance(ring, x, y));
  return best;
}

export function bbox(polygons) {
  let [x1, y1, x2, y2] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const polygon of polygons) {
    const ring = polygon[0];
    for (let i = 0; i < ring.length; i += 2) {
      x1 = Math.min(x1, ring[i]);
      x2 = Math.max(x2, ring[i]);
      y1 = Math.min(y1, ring[i + 1]);
      y2 = Math.max(y2, ring[i + 1]);
    }
  }
  return [x1, y1, x2, y2];
}
