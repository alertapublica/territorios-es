// Browser-safe entry point: pass the contents of datos/territorios.json to createCatalog.
export { createCatalog, LEVELS, REASONS, DEFAULT_MENTION_LEVELS } from './catalog.js';
export { normalize, displayName, flipArticle, dropArticle, slugify, ARTICLES } from './text.js';
export { relation, relateName, combine, STATUSES } from './relation.js';
