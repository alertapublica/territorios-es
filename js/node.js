// Node entry point: adds loadCatalog(), which reads the bundled datos/territorios.json, and the
// loaders of the other bundled files.
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { createCatalog } from './catalog.js';
import { createLimits } from './limits.js';
import { createPostalCodes } from './postal.js';

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

// Postal codes from datos/codigos-postales.csv (by default, the bundled one).
export function loadPostalCodes(path = process.env.TERRITORIOS_ES_DATOS
  ? `${process.env.TERRITORIOS_ES_DATOS}/codigos-postales.csv`
  : new URL('../datos/codigos-postales.csv', import.meta.url)) {
  return createPostalCodes(readFileSync(path, 'utf8'));
}

// Catalogue with the territories and the population entities of datos/entidades.csv (by default, the
// bundled ones). It takes a few seconds: loadCatalog() keeps the catalogue without entities.
const bundled = (name) => (process.env.TERRITORIOS_ES_DATOS
  ? `${process.env.TERRITORIOS_ES_DATOS}/${name}` : new URL(`../datos/${name}`, import.meta.url));
export function loadEntities(path = bundled('entidades.csv'), territories = bundled('territorios.json')) {
  return createCatalog(JSON.parse(readFileSync(territories, 'utf8')), { entities: readFileSync(path, 'utf8') });
}
