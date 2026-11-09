// Node entry point: adds loadCatalog(), which reads the bundled datos/territorios.json.
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { createCatalog } from './catalog.js';
import { createLimits } from './limits.js';

export * from './index.js';

export function loadCatalog(path = process.env.TERRITORIOS_ES_DATOS
  ? `${process.env.TERRITORIOS_ES_DATOS}/territorios.json`
  : new URL('../datos/territorios.json', import.meta.url)) {
  return createCatalog(JSON.parse(readFileSync(path, 'utf8')));
}

// Limits from the release file (limites-municipios.geojson.gz), compressed or not.
export function loadLimits(path) {
  let raw = readFileSync(path);
  if (raw[0] === 0x1f && raw[1] === 0x8b) raw = gunzipSync(raw);
  return createLimits(JSON.parse(raw.toString('utf8')));
}
