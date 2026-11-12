// Catalogue of territories built from datos/territorios.json. Mirrors python/territorios_es/catalog.py.
import { ENTITY_LEVELS, entityRecords } from './entities.js';
import { dropArticle, normalize } from './text.js';

export const LEVELS = [
  'country', 'autonomous_community', 'province', 'island', 'municipality', 'judicial_district', 'warning_zone',
  'comarca', ...ENTITY_LEVELS,
];
// Groups of municipalities that do not change their parent: the field of the municipality that names
// its group is the level of the group.
const GROUPS = ['island', 'judicial_district', 'warning_zone', 'comarca'];
// Levels that search() leaves out unless asked for: a judicial district has the name of its seat, a
// warning zone of AEMET is not an administration, a comarca exists only in some communities (and
// some share their name with a municipality) and population entities have tens of thousands of
// namesakes.
const UNSEARCHED_LEVELS = ['judicial_district', 'warning_zone', 'comarca', ...ENTITY_LEVELS];
export const REASONS = ['official', 'part', 'lang', 'alias', 'variant'];
export const DEFAULT_MENTION_LEVELS = ['autonomous_community', 'province'];
const TRANSLATED_LEVELS = ['country', 'autonomous_community'];

const compare = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const clone = (value) => JSON.parse(JSON.stringify(value));

function* forms(record) {
  const names = record.names;
  yield [names.official, 'official', null];
  yield [names.display, 'official', null];
  for (const [lang, part] of Object.entries(names.parts ?? {})) yield [part, 'part', lang];
  for (const group of ['lang', 'short']) {
    for (const [lang, value] of Object.entries(names[group] ?? {})) yield [value, 'lang', lang];
  }
  for (const alias of names.aliases ?? []) yield [alias.name, 'alias', alias.lang ?? null];
  for (const value of [names.display, ...Object.values(names.parts ?? {}), ...Object.values(names.lang ?? {})]) {
    const shorter = dropArticle(value);
    if (shorter) yield [shorter, 'variant', null];
  }
}

// `data`, the content of territorios.json; `entities`, that of entidades.csv, if the population
// entities are wanted too.
export function createCatalog(data, { entities = null } = {}) {
  if (data.schema !== 1) throw new Error('Unsupported data schema');
  const byId = new Map();
  const codes = new Map();
  const childrenOf = new Map();
  let records = data.territories;
  if (entities != null) {
    const municipalities = new Map(records.filter((r) => r.level === 'municipality').map((r) => [r.codes?.['ine:municipio'], r.id]));
    records = [...records, ...entityRecords(entities, (code) => municipalities.get(code))];
  }
  for (const record of records) {
    const id = record.id;
    if (typeof id !== 'string' || byId.has(id)) throw new Error(`Missing or repeated id: ${id}`);
    if (!LEVELS.includes(record.level)) throw new Error(`Unknown level in ${id}`);
    if (!record.names?.official || !record.names?.display) throw new Error(`Missing official or display name in ${id}`);
    for (const [system, code] of Object.entries(record.codes ?? {})) {
      const key = `${system}|${code}`;
      if (typeof code !== 'string' || !code || codes.has(key)) throw new Error(`Invalid or repeated code ${system}=${code} in ${id}`);
      codes.set(key, id);
    }
    byId.set(id, record);
  }
  for (const [id, record] of byId) {
    if (record.parent != null) {
      if (!byId.has(record.parent)) throw new Error(`Unknown parent ${record.parent} of ${id}`);
      if (!childrenOf.has(record.parent)) childrenOf.set(record.parent, []);
      childrenOf.get(record.parent).push(id);
    }
    // An island, a judicial district, a warning zone or a comarca groups municipalities, whose parent
    // stays the province.
    for (const group of GROUPS) {
      const memberOf = record[group];
      if (memberOf == null) continue;
      if (byId.get(memberOf)?.level !== group) throw new Error(`Unknown ${group} ${memberOf} of ${id}`);
      if (!childrenOf.has(memberOf)) childrenOf.set(memberOf, []);
      childrenOf.get(memberOf).push(id);
    }
  }
  const checked = new Set();
  for (let id of byId.keys()) {
    const path = [];
    while (id != null && !checked.has(id)) {
      if (path.includes(id)) throw new Error(`Cycle of parents at ${id}`);
      path.push(id);
      id = byId.get(id).parent;
    }
    for (const seen of path) checked.add(seen);
  }

  const ancestors = (id) => {
    const result = [];
    let parent = byId.get(id).parent;
    while (parent) {
      result.push(parent);
      parent = byId.get(parent).parent;
    }
    return result;
  };

  // Index: normalized form -> entries [rank, level, id, reason, lang], best first.
  const best = new Map();
  const keys = new Map(); // many entities share a name
  for (const [id, record] of byId) {
    for (const [text, reason, lang] of forms(record)) {
      let key = keys.get(text);
      if (key === undefined) keys.set(text, (key = normalize(text)));
      if (!key) continue;
      const rank = REASONS.indexOf(reason);
      const slot = `${key}\u0000${id}`;
      const current = best.get(slot);
      if (!current || rank < current[0] || (rank === current[0] && (lang ?? '') < (current[2] ?? ''))) {
        best.set(slot, [rank, reason, lang, key, id]);
      }
    }
  }
  const index = new Map();
  for (const [rank, reason, lang, key, id] of best.values()) {
    if (!index.has(key)) index.set(key, []);
    index.get(key).push([rank, LEVELS.indexOf(byId.get(id).level), id, reason, lang]);
  }
  for (const entries of index.values()) {
    entries.sort((a, b) => a[0] - b[0] || a[1] - b[1] || compare(a[2], b[2]));
  }

  const candidate = ([, , id, reason, lang]) => {
    const record = byId.get(id);
    const found = { id, level: record.level, name: record.names.display, reason, lang };
    for (const link of ['municipality', 'collective_entity']) { // of a population entity
      if (link in record) found[link] = record[link];
    }
    return found;
  };
  const accept = (id, within, levels) => {
    const level = byId.get(id).level;
    if (levels != null ? !levels.includes(level) : UNSEARCHED_LEVELS.includes(level)) return false;
    if (within == null || ancestors(id).includes(within)) return true;
    // A population entity is in the island, comarca… of its municipality.
    const record = byId.get(byId.get(id).municipality) ?? byId.get(id);
    return GROUPS.some((group) => record[group] === within);
  };
  const territory = (id) => {
    const record = typeof id === 'string' ? byId.get(id) : undefined;
    return record ? { ...clone(record), ancestors: ancestors(id) } : null;
  };
  const mentionPatterns = new Map();

  return {
    referenceDate: data.reference_date ?? null,
    territory,
    ancestors,
    resolve(system, code) {
      if (typeof code !== 'string') return null;
      const id = codes.get(`${system}|${code}`);
      return id ? territory(id) : null;
    },
    children(id) {
      return [...(childrenOf.get(id) ?? [])].sort(compare);
    },
    ids(level = null) {
      return [...byId.keys()].filter((id) => level == null || byId.get(id).level === level).sort(compare);
    },
    name(id, lang = 'es', short = false) {
      const record = typeof id === 'string' ? byId.get(id) : undefined;
      if (!record) return null;
      const names = record.names;
      if (TRANSLATED_LEVELS.includes(record.level)) {
        if (short && names.short?.[lang] != null) return names.short[lang];
        if (names.lang?.[lang] != null) return names.lang[lang];
        return names.display;
      }
      return names.parts?.[lang] ?? names.display;
    },
    search(text, { within = null, levels = null } = {}) {
      if (within != null && !byId.has(within)) throw new Error(`Unknown territory ${within}`);
      return (index.get(normalize(text)) ?? []).filter((e) => accept(e[2], within, levels)).map(candidate);
    },
    mentions(text, { levels = DEFAULT_MENTION_LEVELS, within = null } = {}) {
      const cacheKey = levels.join('|');
      if (!mentionPatterns.has(cacheKey)) {
        const forms = new Map();
        for (const [key, entries] of index) {
          const kept = entries.filter((e) => levels.includes(byId.get(e[2]).level));
          if (kept.length) forms.set(key, kept);
        }
        const ordered = [...forms.keys()].sort((a, b) => b.length - a.length || compare(a, b));
        const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const pattern = ordered.length
          ? new RegExp(`(?<![a-z0-9])(?:${ordered.map(escape).join('|')})(?![a-z0-9])`, 'g') : null;
        mentionPatterns.set(cacheKey, [pattern, forms]);
      }
      const [pattern, forms] = mentionPatterns.get(cacheKey);
      if (!pattern) return [];
      const found = [];
      for (const match of normalize(text).matchAll(pattern)) {
        const candidates = forms.get(match[0]).filter((e) => accept(e[2], within, levels)).map(candidate);
        if (candidates.length) found.push({ text: match[0], candidates });
      }
      return found;
    },
  };
}
