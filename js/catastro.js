// Cadastral references, offline. Mirrors python/territorios_es/catastro.py.
import { relation } from './relation.js';

const WEIGHTS = [13, 15, 12, 5, 4, 17, 9, 21, 3, 7, 1];
const LETTERS = 'MQWERTYUIOPASDFGHJKLBZX';
const RUSTIC = /^[0-9]{5}[A-ZÑ][0-9]{8}$/;
const URBAN = /^[0-9]{7}[A-ZÑ]{2}[0-9]{4}[A-ZÑ]$/;
const SHAPE = /^[0-9A-ZÑ]{14}(?:[0-9]{4}(?:[A-ZÑ]{2})?)?$/;

const value = (char) => {
  if (char >= '0' && char <= '9') return Number(char);
  if (char === 'Ñ') return 15;
  return char <= 'N' ? char.charCodeAt(0) - 64 : char.charCodeAt(0) - 63; // A=1 … N=14, Ñ=15, O=16 … Z=27
};

export function checkLetters(reference) {
  if (!SHAPE.test(reference) || reference.length < 18) throw new Error(`Not an 18-character cadastral reference: ${reference}`);
  const tail = reference.slice(14, 18);
  return [reference.slice(0, 7), reference.slice(7, 14)]
    .map((part) => [...(part + tail)].reduce((sum, c, i) => sum + value(c) * WEIGHTS[i], 0) % 23)
    .map((n) => LETTERS[n]).join('');
}

export function parseCadastralReference(text) {
  if (typeof text !== 'string') return null;
  const reference = text.replace(/\s+/g, '').toUpperCase();
  if (!SHAPE.test(reference)) return null;
  const parcel = reference.slice(0, 14);
  const kind = RUSTIC.test(parcel) ? 'rustic' : URBAN.test(parcel) ? 'urban' : 'other';
  const check = reference.slice(18) || null;
  return {
    reference, parcel, kind, property: reference.slice(14, 18) || null, check,
    valid: check == null ? null : check === checkLetters(reference.slice(0, 18)),
    dgc: kind === 'rustic' ? parcel.slice(0, 5) : null,
  };
}

export function relateCadastralReference(catalog, text) {
  const parsed = parseCadastralReference(text);
  if (parsed == null) return relation('pending', null, [], 'not_a_reference');
  if (parsed.valid === false) return relation('pending', null, [], 'invalid_check');
  if (parsed.kind !== 'rustic') return relation('pending', null, [], parsed.kind);
  const found = catalog.resolve('dgc:municipio', parsed.dgc);
  if (found == null) return relation('pending', null, [], 'not_found');
  const evidence = [{ source: 'cadastral_reference', datum: parsed.reference, territory: found.id, reason: 'dgc:municipio' }];
  return relation('resolved', found.id, [found.id], 'cadastral_reference', evidence);
}
