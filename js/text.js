// Text rules shared by the library and the generator. Mirrors python/territorios_es/text.py.

export const ARTICLES = {
  es: ['El', 'La', 'Los', 'Las'],
  gl: ['O', 'A', 'Os', 'As'],
  ca: ['El', 'La', 'Els', 'Les', "L'", 'Es', 'Sa', 'Ses'],
  oc: ['Eth', 'Era', 'Es', 'Eras'],
};
const ALL = new Set(Object.values(ARTICLES).flat().map((a) => a.toLowerCase()));
const BY_LENGTH = [...ALL].sort((a, b) => b.length - a.length || (a < b ? -1 : a > b ? 1 : 0));
// After a comma («Coruña, A») or, in the INE street register, in brackets («DEVESA (A)»).
// Also an article followed by another bracket («ERMO (O) (SAN XULIAN)»).
const TRAILING_ARTICLES = [/^(.+), ([^,/]+)$/, /^(.+) \(([^()/]+)\)$/, /^([^()]+) \(([^()/]+)\)( \([^()]+\))$/];
const APOSTROPHES = /[’‘´`]/g;

export function flipArticle(name) {
  const trimmed = name.trim();
  for (const pattern of TRAILING_ARTICLES) {
    const match = pattern.exec(trimmed);
    if (!match) continue;
    const article = match[2].replace(APOSTROPHES, "'");
    if (ALL.has(article.toLowerCase())) return article + (article.endsWith("'") ? '' : ' ') + match[1] + (match[3] ?? '');
  }
  return trimmed;
}

export function displayName(official) {
  return official.split('/').map(flipArticle).join('/');
}

export function dropArticle(name) {
  const lower = name.toLowerCase();
  for (const article of BY_LENGTH) {
    if (article.endsWith("'") && lower.startsWith(article) && name.length > article.length) {
      return name.slice(article.length);
    }
    if (lower.startsWith(`${article} `) && name.length > article.length + 1) {
      return name.slice(article.length + 1);
    }
  }
  return null;
}

export function normalize(text) {
  if (typeof text !== 'string') return '';
  let plain = flipArticle(text.replace(APOSTROPHES, "'")).normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
  plain = plain.replaceAll('l·l', 'll').replaceAll('l.l', 'll');
  plain = plain.replace(/[^a-z0-9']+/g, ' ').replace(/\s*'\s*/g, "'");
  return plain.replace(/\s+/g, ' ').replace(/^[ ']+|[ ']+$/g, '');
}

export function slugify(text) {
  return normalize(text).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
