// Optional: places a cadastral reference or a point with the Catastro's free web services.
// Mirrors python/territorios_es/catastro_online.py. The only module that uses the network, and only
// when called; one request per call (two for a point). Works in Node and in the browser: the
// Catastro answers with Access-Control-Allow-Origin: * (checked 2026-11-09).
import { parseCadastralReference, relateCadastralReference } from './catastro.js';
import { combine, relation } from './relation.js';

export const SERVICE = 'https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC';

export class CatastroError extends Error {}

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
const text = (xml, tag) => [...xml.matchAll(new RegExp(`<${tag}>([^<]*)</${tag}>`, 'g'))]
  .map((m) => m[1].replace(/&(amp|lt|gt|quot|apos);/g, (_, e) => ENTITIES[e]).trim());
const blocks = (xml, tag) => [...xml.matchAll(new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`, 'g'))].map((m) => m[1]);

async function defaultFetch(url) {
  let response;
  try {
    response = await fetch(url);
  } catch (error) {
    throw new CatastroError(`Catastro: ${error.message}`);
  }
  if (!response.ok) throw new CatastroError(`Catastro: HTTP ${response.status}`);
  return response.text();
}

async function answer(fetchText, url) {
  const xml = String(await fetchText(url));
  if (!/^\s*(<\?xml[^>]*>\s*)?<[a-z_]+[\s>]/i.test(xml) || !xml.includes('http://www.catastro.meh.es/')) {
    throw new CatastroError('Catastro: respuesta no válida');
  }
  return { xml, errors: blocks(xml, 'err').flatMap((e) => text(e, 'des')) };
}

function ineCodes(xml) {
  const codes = new Set();
  for (const loine of blocks(xml, 'loine')) {
    const [province = ''] = text(loine, 'cp');
    const [municipality = ''] = text(loine, 'cm');
    if (!/^[0-9]{1,2}$/.test(province) || !/^[0-9]{1,3}$/.test(municipality)) {
      throw new CatastroError(`Catastro: código del INE no válido ${province} ${municipality}`);
    }
    codes.add(province.padStart(2, '0') + municipality.padStart(3, '0'));
  }
  return [...codes].sort();
}

async function byReference(catalog, parcel, fetchText) {
  const url = `${SERVICE}/OVCCallejero.asmx/Consulta_DNPRC?${new URLSearchParams({ Provincia: '', Municipio: '', RC: parcel })}`;
  const { xml, errors } = await answer(fetchText, url);
  const source = 'catastro:Consulta_DNPRC';
  if (errors.length) {
    return relation('pending', null, [], 'not_found', [{ source, datum: parcel, territory: null, reason: errors.join('; ') }]);
  }
  const codes = ineCodes(xml);
  const found = codes.map((code) => [code, catalog.resolve('ine:municipio', code)]);
  const evidence = found.map(([code, t]) => ({ source, datum: parcel, territory: t ? t.id : null, reason: `ine:${code}` }));
  const ids = [...new Set(found.filter(([, t]) => t).map(([, t]) => t.id))].sort();
  if (codes.length > 1) return relation('conflict', null, ids, 'conflict', evidence);
  if (ids.length === 1) return relation('resolved', ids[0], ids, 'catastro', evidence);
  return relation('pending', null, [], 'not_found', evidence);
}

export async function locateReference(catalog, text, { fetch: fetchText = defaultFetch } = {}) {
  const offline = relateCadastralReference(catalog, text);
  if (['not_a_reference', 'invalid_check'].includes(offline.reason)) return offline;
  const online = await byReference(catalog, parseCadastralReference(text).parcel, fetchText);
  return offline.status === 'resolved' ? combine(offline, online) : online;
}

export async function locatePoint(catalog, lon, lat, { srs = 'EPSG:4326', fetch: fetchText = defaultFetch } = {}) {
  const point = `${lon},${lat}`;
  const params = new URLSearchParams({ SRS: srs, Coordenada_X: String(lon), Coordenada_Y: String(lat) });
  const { xml, errors } = await answer(fetchText, `${SERVICE}/OVCCoordenadas.asmx/Consulta_RCCOOR?${params}`);
  const source = 'catastro:Consulta_RCCOOR';
  const parcels = [...new Set(blocks(xml, 'pc').map((pc) => (text(pc, 'pc1')[0] ?? '') + (text(pc, 'pc2')[0] ?? '')))].sort();
  if (errors.length || !parcels.length) {
    return relation('pending', null, [], 'not_found', [{ source, datum: point, territory: null, reason: errors.join('; ') }]);
  }
  if (parcels.length > 1 || parseCadastralReference(parcels[0]) == null) {
    throw new CatastroError(`Catastro: parcela no válida en ${point}: ${parcels}`);
  }
  const found = await byReference(catalog, parcels[0], fetchText);
  const first = { source, datum: point, territory: null, reason: parcels[0] };
  return relation(found.status, found.territory, found.candidates, found.reason, [first, ...found.evidence]);
}
