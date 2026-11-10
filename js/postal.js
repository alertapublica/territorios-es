// Postal codes of each municipality and municipalities of each postal code, from
// datos/codigos-postales.csv. Mirrors python/territorios_es/postal.py.
import { relation } from './relation.js';

export const POSTAL_HEADER = ['postal_code', 'id', 'ine', 'source', 'count', 'unit', 'also'];
const CODE = /^[0-9]{5}$/;
const compare = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

// By count when all have the same unit; otherwise as in the table, which goes by the street sections
// of the INE (counts in different units are never compared).
function ordered(items) {
  if (new Set(items.map((i) => i.unit)).size === 1) {
    items.sort((a, b) => b.count - a.count || compare(a.id, b.id));
  }
  return items;
}

// `text` is the content of codigos-postales.csv.
export function createPostalCodes(text) {
  const lines = text.split(/\r?\n/).filter((line) => line !== '');
  if (!lines.length || lines[0] !== POSTAL_HEADER.join(',')) throw new Error('Not a codigos-postales.csv table');
  const byCode = new Map();
  const byId = new Map();
  for (const line of lines.slice(1)) {
    const row = line.split(',');
    if (row.length !== POSTAL_HEADER.length || !CODE.test(row[0]) || !/^[0-9]+$/.test(row[4])) {
      throw new Error(`Invalid row ${line}`);
    }
    const item = {
      postal_code: row[0], id: row[1], source: row[3], count: Number(row[4]), unit: row[5],
      also: row[6] ? row[6].split(' ') : [],
    };
    if (!byCode.has(item.postal_code)) byCode.set(item.postal_code, []);
    byCode.get(item.postal_code).push(item);
    if (!byId.has(item.id)) byId.set(item.id, []);
    byId.get(item.id).push(item);
  }
  for (const items of byCode.values()) ordered(items);
  for (const items of byId.values()) items.sort((a, b) => compare(a.postal_code, b.postal_code));
  const copy = (items) => (items ?? []).map((i) => ({ ...i, also: [...i.also] }));

  return {
    size: lines.length - 1,
    // Postal codes of a municipality, by code.
    postalCodes(id) {
      return typeof id === 'string' ? copy(byId.get(id)) : [];
    },
    // Municipalities of a postal code: by count when all have the same unit, otherwise as in the
    // table (by the street sections of the INE).
    municipalities(code) {
      return typeof code === 'string' ? copy(byCode.get(code)) : [];
    },
    // Resolved if only one municipality has the code; pending if several (each one's source,
    // count, unit and other sources in the evidence) or none.
    relate(code) {
      if (typeof code !== 'string' || !CODE.test(code)) return relation('pending', null, [], 'not_a_postal_code');
      const found = byCode.get(code) ?? [];
      const ids = found.map((i) => i.id);
      const evidence = found.map((i) => ({
        source: 'postal_code', datum: code, territory: i.id, origin: i.source, count: i.count, unit: i.unit,
        also: [...i.also],
      }));
      if (ids.length === 1) return relation('resolved', ids[0], ids, 'postal_code', evidence);
      return relation('pending', null, ids, ids.length ? 'ambiguous' : 'not_found', evidence);
    },
  };
}
