// Node entry point: adds loadCatalog(), which reads the bundled datos/territorios.json.
import { readFileSync } from 'node:fs';
import { createCatalog } from './catalog.js';

export * from './index.js';

export function loadCatalog(path = process.env.TERRITORIOS_ES_DATOS
  ? `${process.env.TERRITORIOS_ES_DATOS}/territorios.json`
  : new URL('../datos/territorios.json', import.meta.url)) {
  return createCatalog(JSON.parse(readFileSync(path, 'utf8')));
}
