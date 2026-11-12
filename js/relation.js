// Relations with a status and evidence. Mirrors python/territorios_es/relation.py.
export const STATUSES = ['resolved', 'pending', 'conflict'];
const sortedSet = (values) => [...new Set(values)].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

export function relation(status, territory = null, candidates = [], reason = '', evidence = []) {
  if (!STATUSES.includes(status)) throw new Error(`Unknown status ${status}`);
  if ((status === 'resolved') !== (territory != null)) throw new Error('Only a resolved relation has a territory');
  return { status, territory, candidates: sortedSet(candidates), reason, evidence: [...evidence] };
}

export function relateName(catalog, text, { within = null, levels = null } = {}) {
  const found = catalog.search(text, { within, levels });
  const ids = sortedSet(found.map((c) => c.id));
  const evidence = found.map((c) => ({ source: 'name', datum: text, territory: c.id, reason: c.reason }));
  if (ids.length === 1) return relation('resolved', ids[0], ids, 'name', evidence);
  return relation('pending', null, ids, ids.length ? 'ambiguous' : 'not_found', evidence);
}

export function combine(...relations) {
  const evidence = relations.flatMap((r) => r.evidence);
  if (relations.some((r) => r.status === 'conflict')) {
    return relation('conflict', null, relations.flatMap((r) => r.candidates), 'conflict', evidence);
  }
  let possible = null;
  for (const r of relations) {
    const options = r.status === 'resolved' ? [r.territory] : r.candidates;
    if (r.status === 'pending' && !options.length) continue;
    possible = possible == null ? new Set(options) : new Set(options.filter((o) => possible.has(o)));
    if (!possible.size) {
      const ids = relations.flatMap((x) => (x.territory ? [x.territory] : x.candidates));
      return relation('conflict', null, ids, 'contradiction', evidence);
    }
  }
  if (possible == null) return relation('pending', null, [], 'not_found', evidence);
  if (possible.size === 1) {
    const [only] = possible;
    return relation('resolved', only, possible, 'combined', evidence);
  }
  return relation('pending', null, possible, 'ambiguous', evidence);
}

// The same relation about municipalities: each population entity becomes its municipality, so that it
// can be combined with relations about municipalities. Other territories stay as they are. A pending
// relation whose candidates all fall in one municipality becomes resolved.
export function toMunicipality(catalog, rel) {
  const up = (id) => catalog.territory(id)?.municipality ?? id;
  const ids = sortedSet([rel.territory, ...rel.candidates].filter((id) => id != null));
  const evidence = [...rel.evidence, ...ids.filter((id) => up(id) !== id)
    .map((id) => ({ source: 'municipality', datum: id, territory: up(id) }))];
  const candidates = sortedSet(rel.candidates.map(up));
  if (rel.status === 'resolved') return relation('resolved', up(rel.territory), candidates, rel.reason, evidence);
  if (rel.status === 'pending' && candidates.length === 1) {
    return relation('resolved', candidates[0], candidates, 'same_municipality', evidence);
  }
  return relation(rel.status, null, candidates, rel.reason, evidence);
}
