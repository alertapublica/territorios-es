// Optional Catastro services with a fake fetch; pruebas/test_catastro_online.py runs the same cases.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { createCatalog } from '../js/index.js';
import { CatastroError, locatePoint, locateReference } from '../js/catastro_online.js';

const CATALOG = createCatalog(JSON.parse(readFileSync(new URL('./datos/territorios.json', import.meta.url), 'utf8')));
const NS = 'xmlns="http://www.catastro.meh.es/"';
const dnp = (...places) => `<consulta_dnp ${NS}><control><cudnp>${places.length}</cudnp></control><lrcdnp>${
  places.map(([p, m]) => `<rcdnp><dt><loine><cp>${p}</cp><cm>${m}</cm></loine></dt></rcdnp>`).join('')}</lrcdnp></consulta_dnp>`;
const error = (answer, message) => `<${answer} ${NS}><control><cuerr>1</cuerr></control><lerr><err><cod>1</cod><des>${message}</des></err></lerr></${answer}>`;
const coordinates = (pc1, pc2) => `<consulta_coordenadas ${NS}><control><cucoor>1</cucoor><cuerr>0</cuerr></control><coordenadas><coord><pc><pc1>${pc1}</pc1><pc2>${pc2}</pc2></pc></coord></coordenadas></consulta_coordenadas>`;

function fake(...answers) {
  const urls = [];
  const fetch = async (url) => { urls.push(url); return answers.shift(); };
  return { fetch, urls };
}

test('urban reference', async () => {
  const f = fake(dnp(['15', '30']));
  const found = await locateReference(CATALOG, '1234567ab1234c', f);
  assert.deepEqual([found.status, found.territory, found.reason], ['resolved', 'es:municipio:15030', 'catastro']);
  assert.ok(f.urls[0].endsWith('/OVCCallejero.asmx/Consulta_DNPRC?Provincia=&Municipio=&RC=1234567AB1234C'));
});

test('rustic reference agrees or conflicts', async () => {
  let found = await locateReference(CATALOG, '15900A00100192', fake(dnp(['15', '30'], ['15', '30'])));
  assert.deepEqual([found.status, found.territory], ['resolved', 'es:municipio:15030']);
  found = await locateReference(CATALOG, '15900A00100192', fake(dnp(['36', '38'])));
  assert.equal(found.status, 'conflict');
});

test('not found and disagreement', async () => {
  let found = await locateReference(CATALOG, '1234567AB1234C', fake(error('consulta_dnp', 'NO EXISTE')));
  assert.deepEqual([found.status, found.reason, found.evidence[0].reason], ['pending', 'not_found', 'NO EXISTE']);
  found = await locateReference(CATALOG, '1234567AB1234C', fake(dnp(['15', '30'], ['36', '38'])));
  assert.equal(found.status, 'conflict');
  found = await locateReference(CATALOG, '1234567AB1234C', fake(dnp(['15', '26'])));
  assert.deepEqual([found.status, found.reason], ['pending', 'not_found']);
});

test('no request for what is not a reference', async () => {
  const f = fake();
  assert.equal((await locateReference(CATALOG, 'hola', f)).reason, 'not_a_reference');
  assert.equal((await locateReference(CATALOG, '13096A001001920000YX', f)).reason, 'invalid_check');
  assert.deepEqual(f.urls, []);
});

test('unreadable answer', async () => {
  await assert.rejects(locateReference(CATALOG, '1234567AB1234C', fake('<html>')), CatastroError);
});

test('point', async () => {
  const f = fake(coordinates('1234567', 'AB1234C'), dnp(['15', '30']));
  const found = await locatePoint(CATALOG, -8.4, 43.37, f);
  assert.deepEqual([found.status, found.territory], ['resolved', 'es:municipio:15030']);
  assert.ok(f.urls[0].includes('Consulta_RCCOOR?SRS=EPSG%3A4326&Coordenada_X=-8.4&Coordenada_Y=43.37'));
  assert.deepEqual(found.evidence[0], { source: 'catastro:Consulta_RCCOOR', datum: '-8.4,43.37', territory: null, reason: '1234567AB1234C' });
});

test('no parcel', async () => {
  const f = fake(error('consulta_coordenadas', 'NO HAY PARCELA'));
  const found = await locatePoint(CATALOG, -9.5, 43.0, f);
  assert.deepEqual([found.status, found.reason], ['pending', 'not_found']);
  assert.equal(f.urls.length, 1);
});
