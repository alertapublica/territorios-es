// Shared cases (casos.json) for the JavaScript library; pruebas/test_casos.py runs the same ones.
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { test } from 'node:test';
import {
  checkLetters, combine, createCatalog, createLimits, displayName, locate, normalize, parseCadastralReference,
  relateCadastralReference, relateName, relation,
} from '../js/index.js';
import { loadCatalog, loadLimits } from '../js/node.js';
import { gzipSync } from 'node:zlib';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));
const CASES = read('./casos.json');
const CATALOG = createCatalog(read('./datos/territorios.json'));

test('normalize', () => {
  for (const [text, expected] of CASES.normalize) assert.equal(normalize(text), expected, text);
});

test('displayName', () => {
  for (const [official, expected] of CASES.display_name) assert.equal(displayName(official), expected, official);
});

test('resolve', () => {
  for (const [system, code, expected, ancestors] of CASES.resolve) {
    const found = CATALOG.resolve(system, code);
    assert.deepEqual(found ? [found.id, found.ancestors] : [null, null], [expected, ancestors], `${system} ${code}`);
  }
});

test('children', () => {
  for (const [id, expected] of CASES.children) assert.deepEqual(CATALOG.children(id), expected, id);
});

test('name', () => {
  for (const [id, lang, short, expected] of CASES.name) assert.equal(CATALOG.name(id, lang, short), expected, `${id} ${lang}`);
});

test('search', () => {
  for (const [text, within, levels, expected] of CASES.search) {
    const found = CATALOG.search(text, { within, levels }).map((c) => [c.id, c.reason]);
    assert.deepEqual(found, expected, text);
  }
});

test('mentions', () => {
  for (const [text, levels, expected] of CASES.mentions) {
    const found = CATALOG.mentions(text, levels ? { levels } : {}).map((m) => [m.text, m.candidates.map((c) => c.id)]);
    assert.deepEqual(found, expected, text);
  }
});

test('relateName', () => {
  for (const [text, within, levels, status, territory, candidates, reason] of CASES.relate_name) {
    const found = relateName(CATALOG, text, { within, levels });
    assert.deepEqual([found.status, found.territory, found.candidates, found.reason], [status, territory, candidates, reason], text);
  }
});

test('parseCadastralReference', () => {
  for (const [text, expected] of CASES.cadastral_reference) assert.deepEqual(parseCadastralReference(text), expected, text);
  assert.equal(parseCadastralReference(null), null);
  assert.throws(() => checkLetters('13096A00100192'));
});

test('relateCadastralReference', () => {
  for (const [text, status, territory, reason] of CASES.relate_cadastral_reference) {
    const found = relateCadastralReference(CATALOG, text);
    assert.deepEqual([found.status, found.territory, found.reason], [status, territory, reason], text);
  }
});

test('locate', () => {
  const limits = createLimits(read('./limites.json'));
  for (const [lon, lat, status, territory, candidates, reason] of CASES.locate) {
    const found = locate(limits, lon, lat);
    assert.deepEqual([found.status, found.territory, found.candidates, found.reason], [status, territory, candidates, reason], `${lon} ${lat}`);
  }
  const found = locate(limits, 0.9999, 0.5);
  assert.deepEqual(found.evidence.map((e) => [e.territory, e.inside, e.distance_m]),
    [['es:municipio:15030', true, 11.1], ['es:municipio:32054', false, 11.1]]);
  assert.equal(locate(limits, 0.9999, 0.5, { margin: 5 }).status, 'resolved');
  for (const [lon, lat] of [[NaN, 0], [200, 0], ['1', 0]]) assert.throws(() => locate(limits, lon, lat));
  const folder = mkdtempSync(join(tmpdir(), 'limites-'));
  const path = join(folder, 'limites-municipios.geojson.gz');
  writeFileSync(path, gzipSync(readFileSync(new URL('./limites.json', import.meta.url))));
  assert.equal(locate(loadLimits(path), 0.5, 0.5).territory, 'es:municipio:15030');
  assert.equal(limits.attribution, 'Obra derivada de BDLJE Continua CC-BY 4.0 ign.es');
});

test('combine', () => {
  const a = relation('resolved', 'es:municipio:32054', ['es:municipio:32054']);
  const b = relation('pending', null, ['es:municipio:32054', 'es:provincia:32']);
  const c = relation('resolved', 'es:provincia:32', ['es:provincia:32']);
  const nothing = relation('pending', null, [], 'not_found');
  assert.equal(combine(a, b).status, 'resolved');
  assert.equal(combine(a, nothing).territory, 'es:municipio:32054');
  assert.equal(combine(a, c).status, 'conflict');
  assert.equal(combine(b, b).status, 'pending');
  assert.equal(combine(nothing).status, 'pending');
  assert.throws(() => relation('resolved'));
});

test('loadCatalog reads a data folder', () => {
  process.env.TERRITORIOS_ES_DATOS = new URL('./datos', import.meta.url).pathname;
  assert.equal(loadCatalog().name('es:autonomia:09', 'en'), 'Catalonia');
  delete process.env.TERRITORIOS_ES_DATOS;
});

test('within must exist', () => {
  assert.throws(() => CATALOG.search('Ourense', { within: 'es:provincia:99' }));
});
