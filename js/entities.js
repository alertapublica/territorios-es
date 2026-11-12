// Population entities (entidades de población) of the INE street register, from datos/entidades.csv.
// Mirrors python/territorios_es/entities.py: the level and the parent come out of the 12-digit code
// (province and municipality 5, collective 2, singular 2, check digit 1, nucleus 2; 99 is the
// scattered part), and `ine:entidad` is the 11-digit code without the check digit.
import { displayName } from './text.js';

export const ENTITY_HEADER = ['id', 'ine_dc', 'official'];
export const ENTITY_LEVELS = ['collective_entity', 'singular_entity', 'nucleus', 'scattered'];
const CODE = /^[0-9]{12}$/;

export const entityCode = (code) => code.slice(0, 9) + code.slice(10);

// Level of an 11-digit code; null for a municipality or a code that is not an entity.
export function entityLevel(code) {
  const [collective, singular, nucleus] = [code.slice(5, 7), code.slice(7, 9), code.slice(9, 11)];
  if (singular === '00') return collective !== '00' && nucleus === '00' ? 'collective_entity' : null;
  if (nucleus === '00') return 'singular_entity';
  return nucleus === '99' ? 'scattered' : 'nucleus';
}

// One row of the table: the names have no commas or quotes, but a CSV reader keeps it safe.
function parseRow(line) {
  const cells = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cell += '"'; i += 1; } else if (ch === '"') quoted = false; else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { cells.push(cell); cell = ''; } else cell += ch;
  }
  cells.push(cell);
  return cells;
}

// Records in the shape of territorios.json for the content of entidades.csv. `municipalityId` gives the
// identifier of a municipality from its INE code (null or undefined if it does not exist).
export function entityRecords(text, municipalityId) {
  const lines = text.split(/\r?\n/).filter((line) => line !== '');
  if (!lines.length || lines[0] !== ENTITY_HEADER.join(',')) throw new Error('Not an entidades.csv table');
  const byCode = new Map();
  const found = [];
  for (const line of lines.slice(1)) {
    const row = parseRow(line);
    if (row.length !== ENTITY_HEADER.length || !CODE.test(row[1]) || !row[0] || !row[2]) throw new Error(`Invalid row ${line}`);
    const code = entityCode(row[1]);
    const level = entityLevel(code);
    const municipality = municipalityId(code.slice(0, 5));
    if (level == null || municipality == null || byCode.has(code)) {
      throw new Error(`Not an entity of a known municipality, or repeated: ${line}`);
    }
    byCode.set(code, row[0]);
    found.push([row, code, level, municipality]);
  }
  return found.map(([row, code, level, municipality]) => {
    const collective = code.slice(5, 7) !== '00' ? byCode.get(`${code.slice(0, 7)}0000`) : municipality;
    const parent = level === 'collective_entity' ? municipality
      : level === 'singular_entity' ? collective : byCode.get(`${code.slice(0, 9)}00`);
    if (collective == null || parent == null) throw new Error(`Missing parent entity of ${row[0]}`);
    const record = {
      id: row[0], level, parent, codes: { 'ine:entidad': code, 'ine:entidad:dc': row[1] },
      names: { official: row[2], display: displayName(row[2]), reviewed: false }, municipality,
    };
    if (collective !== municipality && level !== 'collective_entity') record.collective_entity = collective;
    return record;
  });
}
