// From a point to its municipality, without network, with the boundaries file of each release
// (limites-municipios.geojson.gz). Mirrors python/territorios_es/limits.py. In Node, loadLimits()
// reads the file; in the browser, pass the parsed GeoJSON to createLimits().
import { bbox, contains, distance, METRES_PER_DEGREE } from './geo.js';
import { relation } from './relation.js';

export const MARGIN_M = 50;

export function createLimits(collection) {
  if (!collection || collection.type !== 'FeatureCollection') throw new Error('Not a GeoJSON FeatureCollection');
  const units = (collection.features ?? []).map((feature) => {
    const geometry = feature.geometry ?? {};
    let shapes;
    if (geometry.type === 'Polygon') shapes = [geometry.coordinates];
    else if (geometry.type === 'MultiPolygon') shapes = geometry.coordinates;
    else throw new Error(`Unsupported geometry ${geometry.type}`);
    const polygons = shapes.map((shape) => shape.map((ring) => ring.flatMap((point) => [point[0], point[1]])));
    return { id: feature.id ?? null, bddae: feature.properties?.bddae ?? null, polygons, box: bbox(polygons) };
  });
  return {
    attribution: collection.attribution ?? null,
    referenceDate: collection.reference_date ?? null,
    size: units.length,
    units,
  };
}

const round1 = (value) => Math.round(value * 10) / 10;

export function locate(limits, lon, lat, { margin = MARGIN_M } = {}) {
  if (![lon, lat, margin].every((v) => typeof v === 'number' && Number.isFinite(v))
      || lon < -180 || lon > 180 || lat < -90 || lat > 90 || margin < 0) {
    throw new Error('lon and lat must be finite degrees, margin a distance in metres');
  }
  const dy = margin / METRES_PER_DEGREE;
  const dx = dy / Math.max(Math.cos((lat * Math.PI) / 180), 1e-6);
  const inside = [];
  const near = [];
  const evidence = [];
  for (const { id, bddae, polygons, box: [x1, y1, x2, y2] } of limits.units) {
    if (!(x1 - dx <= lon && lon <= x2 + dx && y1 - dy <= lat && lat <= y2 + dy)) continue;
    const isInside = contains(polygons, lon, lat);
    const gap = distance(polygons, lon, lat);
    if (!isInside && gap > margin) continue;
    (isInside ? inside : near).push(id);
    evidence.push({ source: 'ign:limits', datum: [lon, lat], territory: id, bddae, inside: isInside, distance_m: round1(gap) });
  }
  evidence.sort((a, b) => (a.inside === b.inside ? 0 : a.inside ? -1 : 1) || a.distance_m - b.distance_m
    || ((a.bddae ?? '') < (b.bddae ?? '') ? -1 : (a.bddae ?? '') > (b.bddae ?? '') ? 1 : 0));
  const known = [...inside, ...near].filter(Boolean);
  if (inside.length > 1) return relation('conflict', null, known, 'overlap', evidence);
  if (inside.length && inside[0] == null) return relation('pending', null, known, 'shared_area', evidence);
  if (inside.length && !near.length) return relation('resolved', inside[0], inside, 'inside', evidence);
  if (inside.length || near.length) return relation('pending', null, known, 'near_boundary', evidence);
  return relation('pending', null, [], 'outside', evidence);
}
