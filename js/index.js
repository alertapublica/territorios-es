// Browser-safe entry point: pass the contents of datos/territorios.json to createCatalog.
export { createCatalog, LEVELS, REASONS, DEFAULT_MENTION_LEVELS } from './catalog.js';
export { normalize, displayName, flipArticle, dropArticle, slugify, ARTICLES } from './text.js';
export { relation, relateName, combine, toMunicipality, STATUSES } from './relation.js';
export { ENTITY_LEVELS } from './entities.js';
export { checkLetters, parseCadastralReference, relateCadastralReference } from './catastro.js';
export { createLimits, locate, MARGIN_M } from './limits.js';
export { createPostalCodes, POSTAL_HEADER } from './postal.js';
