# Design of territorios-es

It describes what is in the repository. The decisions taken are in the section
[Decisions](#12-decisions) and what has been checked for each source, in
[Source checks](#13-source-checks). What is missing is in the
[issues labelled «objetivo»](https://github.com/alertapublica/territorios-es/issues?q=is%3Aissue+is%3Aopen+label%3Aobjetivo). There is a Spanish
version at [`diseno.md`](diseno.md).

## 1. Purpose

Many projects need the same thing: to know that "Orense", "Ourense" and `32054` refer to the same
place, to convert from one code to another and to show the correct name in each language.
`territorios-es` brings all of that together in one place, where a territory is recognised by any
of its names and codes. Its data is regenerated from the official sources, and the open ones
(Wikidata, OpenStreetMap) serve as support and for cross-checking. It offers three things:

1. **Catalogue**: Spain, its autonomous communities and autonomous cities, provinces, islands,
   municipalities, judicial districts, AEMET warning zones, comarcas and minor local entities, and the countries of the
   world, with their hierarchy, their names (official,
   display, per language and aliases) and their codes (INE, Catastro, ISO, European and others).
2. **Tools** in Python and JavaScript: resolve a code, search for a name within a scope, find
   mentions in a text, choose the name displayed in each language and relate references to their
   status and evidence.
3. **Open data**: the mapping of codes and names in CSV and JSON, with the source, date and
   licence of each datum, and a website that explains them in six languages.

It does not include what only makes sense in a specific project, such as "Ámbito nacional" or
"Varias comunidades" in empleo-publico-abierto. Each project builds that on top.

## 2. Starting point

The core comes from the territories module of [Voceiro](https://github.com/thendabs1/voceiro)
(`shared/territorios/`). It is the most polished thing we have:

- the INE (National Statistics Institute) dictionary of municipalities for 2026, with check digit,
  URL and SHA-256 hash;
- `resolver(sistema, codigo)` in Python and JavaScript, with test cases shared by both;
- the IGN (National Geographic Institute) municipal boundaries for the 52 provinces and the
  mapping from a point to its municipality, with a 50 m margin;
- the relator contract: statuses (resolved, pending, conflict), reason and evidence.

It lacks coordinates and population from an official source, names in other languages and the
codes that are not INE's.

empleo-publico-abierto has its own list of municipalities and its free-text reading
(`empleo/regions.py`): it gives a municipality only when there is no ambiguity and, otherwise, the
province or the autonomous community. Its aliases ("Orense", "Lérida") are written inside the
code.

Today the table of autonomous communities and provinces, the list of municipalities and the rules
that turn «Coruña, A» into "A Coruña" are repeated across several projects, and each one uses its
own identifier format. This library replaces those copies.

The similar projects that already exist, in Spain and in the EU, are reviewed in the section
[Similar projects](#11-similar-projects).

## 3. Principles

- **Everything can be regenerated.** Each data file states the URL it comes from, its SHA-256 hash
  and the reference date. The generator runs in GitHub Actions, not locally. Servers that do not
  answer GitHub's IPs (today, the ICGC) are read through a relay with a Spanish IP (`VIA_RELAY` in
  `generador/descargas.py`, secrets `RELAY_URL` and `RELAY_CLAVE`); the URL recorded is always the
  source's.
- **The literal text of the source is kept.** The forms we derive ourselves ("A Coruña", the
  slugs) are stored separately and marked as derived.
- **A name is not enough to identify a territory.** `search` returns candidates with the reason
  for each one, and the consumer decides: empleo, only if there is no ambiguity; another project,
  within the province it already knows.
- **Codes are always text strings.** Lost leading zeros are not filled in and one code is not
  deduced from another.
- **Identifiers are stable.** A municipality born from a merger receives a new identifier and a
  succession link, and the old one is not reused.
- **The network is not used at run time.** The catalogue ships with the package; the boundaries,
  because of their size, are downloaded separately when needed. The only exception is the optional
  `catastro_online` module, which calls the Catastro only when asked to (§6).
- **Everything is deterministic, no AI.**
- **All useful sources are used, related with their provenance** (see section 5).

## 4. Data

### 4.1 Levels

- **Spain**: 19 autonomous communities and autonomous cities, 52 provinces and 8,132
  municipalities (those of the INE as of 1 January 2026).
- **Countries**: the complete ISO 3166-1 list, with its name in each language and whether they
  belong to the EU or the European Economic Area. It is useful, for example, for the nationality
  requirement in job calls.
- **Islands**: the 11 with a cabildo (Canary Islands) or a consell insular (Balearic Islands),
  with level `island` and an identifier with the INE island code (`es:isla:384` is Tenerife;
  `es:isla:072`, Ibiza). Their parent is the province. Municipalities keep their parent and also
  carry the field `island`. The code, the official name and the municipalities of each island come
  from the INE island table (`26codislas.xlsx`); `fuentes/islas.csv` adds the Wikidata item and the
  NUTS 3, which is only used to cross-check (Eivissa and Formentera share ES531). Smaller islands go
  with the municipality they belong to (La Graciosa with Teguise, in Lanzarote; Cabrera with Palma,
  in Mallorca). The name is the INE's official one (§4.4); the others come from Wikidata.
- **Judicial districts** (partidos judiciales): the 431 of the judicial map, with level
  `judicial_district` and an identifier with the code of the Ministry of Justice's Censo Judicial:
  province and number of the district within it (`es:partido:0705` is Eivissa; `es:partido:5112`,
  Ceuta). Their parent is the province, since no district crosses one; municipalities keep their
  parent and also carry the field `judicial_district`, as with the islands. The municipalities of
  each district and its seat come from the Censo Judicial. The name is the seat's, with its parts if
  it is bilingual, because the Censo writes it in capitals and with some typos
  («CATARRO4623548000000JA» for Catarroja). Organic Law 1/2025 keeps the districts: each has a
  court of first instance (tribunal de instancia) seated in its capital. `search` and `mentions`
  leave them out unless asked for in `levels`, since they are named after their seat.
- **AEMET warning zones**: the 182 land zones of Meteoalerta, by which AEMET (the State
  Meteorological Agency) issues its warnings, with level `warning_zone` and an identifier with the
  six-digit AEMET code (`es:zona-aviso:774602` is Litoral norte de Valencia). It is not an
  administration but the division used to warn about rain, wind, snow or heat, and it covers the
  whole country. Their parent is the province and municipalities also carry the field
  `warning_zone`, as with the islands. The zone of each municipality comes from the municipality
  master of AEMET OpenData, which needs a key (the secret `AEMET_API_KEY`), and the name of each
  zone from the table of the zone boundaries. The master leaves out some new municipalities and
  keeps some extinct ones: those that AEMET does place on its website go in
  `fuentes/zonas-aviso.csv`, with the link to their page, and the rest stay without a zone and are
  listed in the report; it is never inferred from the map, which dates from 2018 and does not
  match the current boundaries. The coastal zones (suffix `C`) are not included. `search` and
  `mentions` leave them out unless asked for in `levels`.
- **Comarcas**: only those that are a local entity, those in the Registro de Entidades Locales: the
  42 comarcas of Catalonia plus Aran, the 33 of Aragon, the 7 cuadrillas of Álava and El Bierzo. Of
  the 42 Catalan ones, the Registro does not have the Lluçanès yet, created as a comarca by Law
  7/2023 although its council will not be set up until after the 2027 local elections (the Registro
  will register it then); it is already here. They are 84, with 1,767 municipalities. Level `comarca`, with the community as parent, since some cross a provincial
  border; municipalities keep their parent and also carry the field `comarca`. The identifier is
  our own and does not change: `es:comarca:CCNN`, with the INE community and a number, which in
  Catalonia and Aragon is that of the comarca at Idescat and in the Government of Aragon
  (`es:comarca:0943` is the Lluçanès; `es:comarca:0217`, the Central one) and in Álava and El
  Bierzo the order of its number in the Registro (`es:comarca:1604`, the cuadrilla of
  Vitoria-Gasteiz). The Registro number (8 digits) and the regional code are kept as codes.
  `fuentes/comarcas.csv` lists them with their type (`comarca`, `cuadrilla` or `aran`, a unique
  territorial entity) and their name: Idescat's in Catalonia and the Registro's elsewhere. The
  municipalities of each come every month from Idescat and Aragón Open Data, by INE code, and in
  Álava and El Bierzo from `fuentes/comarcas-municipios.csv`, taken from the Registro. The Barcelonès
  is still a comarca although its council was abolished in 2019. The comarcas of Galicia, the
  Valencian Community or Asturias, which are statistical or planning areas, are left out; if they
  are added, they will have another type. `search` and `mentions` leave them out unless asked for
  in `levels`, since they only exist in four communities and some share their name with a
  municipality.
- **Minor local entities**: the entities below the municipality (EATIM) registered in the Registro
  de Entidades Locales, 3,674 in 776 municipalities of 15 communities (León 1,225, Burgos 643,
  Cantabria 514, Navarre 344, Álava 333, Palencia 223; 9 in Galicia). Level `minor_local_entity`,
  the first below the municipality, which is its parent. The identifier is the Registro number,
  eight digits: 04, the INE province and an order number (`es:entidad-menor:04360001` is Arcos da
  Condesa, in Caldas de Reis); it is also the code `rel:eatim`. `fuentes/entidades-menores.csv`
  comes from the Registro's export, reviewed by hand, with the municipality by its INE code (the
  Registro only gives its name; all 3,674 match a single municipality of their province), the type,
  the seat (76 have one) and the registration date, which is not the date of creation. The last two
  are only there to cross-check against the Registro and are not published. The name is the
  Registro's, with the article in front for display, and the 126 bilingual ones have their parts
  reviewed in `partes-bilingues.csv` («Brañas/Leitariegos», in Asturias, is not bilingual and goes to
  the report). The type is the category of each community's law:

  | Type | Where | Law |
  |---|---|---|
  | `concejo` | Álava and Navarre (677) | Norma Foral 11/1995 de Concejos (Álava); [Ley Foral 6/1990, art. 37](https://www.boe.es/buscar/act.php?id=BOE-A-1990-19817) |
  | `parroquia_rural` | Asturias (39) | [Ley 11/1986, art. 1](https://www.boe.es/buscar/act.php?id=BOE-A-1987-773) |
  | `entidad_local_autonoma` | Andalusia (36) | [Ley 5/2010, art. 113](https://www.boe.es/buscar/act.php?id=BOE-A-2010-11491); the 36 are those in the annex of [Decreto 76/2023](https://www.juntadeandalucia.es/boja/2023/64/BOJA23-064-00003-6113-01_00281152.pdf) |
  | `entitat_municipal_descentralitzada` | Catalonia (65) | [Decreto Legislativo 2/2003, art. 2](https://www.boe.es/buscar/act.php?id=DOGC-f-2003-90008) |
  | `eatim` | Castilla-La Mancha (42) | [Ley 3/1991, art. 24](https://www.boe.es/buscar/act.php?id=BOE-A-1991-10111) |
  | `entidad_local_menor` | the rest (2,815) | Castilla y León, [Ley 1/1998, art. 49](https://www.boe.es/buscar/act.php?id=BOE-A-1998-20054); Cantabria, [Ley 3/2022, art. 2](https://www.boe.es/buscar/act.php?id=BOE-A-2022-12386); Aragon, [Ley 7/1999, arts. 85–89](https://www.boe.es/buscar/act.php?id=BOE-A-1999-10151); Galicia, [Ley 5/1997, art. 153](https://www.boe.es/buscar/act.php?id=BOE-A-1997-21040); Extremadura, [Ley 17/2010, art. 70](https://www.boe.es/buscar/act.php?id=BOE-A-2011-555); Valencian Community, [Ley 8/2010, art. 54](https://www.boe.es/buscar/act.php?id=BOE-A-2010-11729); La Rioja, [Ley 1/2003, art. 76](https://www.boe.es/buscar/act.php?id=BOE-A-2003-5909); Madrid, [Ley 2/2003, art. 81](https://www.boe.es/buscar/act.php?id=BOE-A-2003-10722); Balearic Islands, [Ley 20/2006, art. 53](https://www.boe.es/buscar/act.php?id=BOE-A-2007-1893); Bizkaia, Norma Foral 9/2012, art. 58; Gipuzkoa, Norma Foral 2/2003, arts. 26–29 |

  «Junta vecinal» is the governing body in Castilla y León, and Cantabria's law recognises it as a
  traditional name, but the type is entidad local menor. The 36 of the Condado de Treviño belong to
  Burgos. No match with the INE population entities is assumed (decision 18). `search` and
  `mentions` leave them out unless asked for in `levels`, since 244 have the same name as their
  municipality and others the name of another one; with `within`, an entity is also within the
  island, judicial district, warning zone and comarca of its municipality.

### 4.2 Codes

| Code | Levels | Source | Notes |
|---|---|---|---|
| INE | autonomous community (2 digits), province (2), island (3, `ine:isla`), municipality (5 + check digit) | Annual INE dictionary and island table | Official; it is the basis of identity. |
| Censo Judicial | judicial district (`mjusticia:partido`, 4 digits: province 2 + number 2) | Ministry of Justice's Censo Judicial | The number is the district's in the judicial map of its province. The Generalitat's technical catalogue (CTEAJE) uses the same code except in Ceuta and Melilla (1112 and 2908, against 5112 and 5208). |
| AEMET | warning zone (`aemet:zona`, 6 digits: community 2 + province or island group 2 + zone 2) | AEMET OpenData municipality master and Meteoalerta zone boundaries | The community and province digits are AEMET's, not the INE's (the Balearic Islands use 53–55 and the Canary Islands 90–96). |
| Comarca | comarca (`rel:comarca`, 8 digits; `idescat:comarca` and `aragon:comarca`, 2 digits) | Registro de Entidades Locales, Idescat and Government of Aragon | The Registro number starts with 06 and the community; the Registro's Excel drops the leading zero. The Lluçanès does not have one yet. |
| Minor local entity | minor local entity (`rel:eatim`, 8 digits) | Registro de Entidades Locales | Starts with 04 and the INE province; the Registro's Excel drops the leading zero. |
| ISO 3166-1 | country (alpha-2, alpha-3, numeric) | Wikidata | |
| ISO 3166-2 | autonomous community and province (`ES-GA`, `ES-C`) | Hand-reviewed list; linked to Wikidata | |
| NUTS 2024 | NUTS 1 (groups of autonomous communities), NUTS 2 (autonomous community), NUTS 3 (province; islands in the Balearic and Canary Islands) | Eurostat | For cross-referencing with European statistics. |
| LAU | municipality | Annual Eurostat LAU table | In Spain it is the 5-digit INE code (checked on all 8,132 municipalities); see §4.5 for what else it provides. |
| DGC (Catastro) | municipality (`dgc:municipio`, 5 digits: office 2 + municipality 3) | Free Catastro web services (`OVCCallejero`, `ConsultaProvincia` and `ConsultaMunicipio`), which give the DGC and the INE code of each municipality | Different from the INE code in many municipalities (A Coruña: INE `15030`, DGC `15900`). The link is by code, not by name; the name is only cross-checked. Álava, Gipuzkoa, Navarre and Biscay have a foral land registry and have no DGC code. |
| BDDAE (INSPIRE) | municipality (`ign:bddae`, 11 digits: 34 + community 2 + province 2 + INE 5) | IGN boundaries (BDLJE) | Code of the IGN administrative unit and `localId` of its INSPIRE identifier (namespace `ES.IGN.BDDAE`). Linked when the INE code, the province and the community match. |
| Wikidata | all | SPARQL from the INE code | CC0. Provides names per language, links to Wikipedia and other identifiers. |
| OpenStreetMap | all | Relation identifier, from Wikidata | The Wikidata identifier is CC0; whatever is copied from OSM goes separately under ODbL (§7). |
| GeoNames | all | From Wikidata | CC BY 4.0. Widely used by other tools. |
| Postal code | municipality (many-to-many relationship, `datos/codigos-postales.csv`) | What the public administrations publish: Madrid city council, ICGC (Catalonia), IDENA (Navarre), Eustat (Basque Country), IDEIB (Balearic Islands), the INE electoral roll street directory (all Spain), CDAU (Andalusia, cross-checking only) and the Catastro (INSPIRE Addresses, common regime) | Useful for reading addresses. Not a `resolve` system (§6). In each municipality the first source that covers it and has data decides (decision 14); each pair carries its source, its count in that source's unit and the other sources that have it (`also`). `codigos-postales-fuentes.csv` keeps what each source says, for cross-checking and for claims. Its own workflow rebuilds it twice a year. Discarded sources: CartoCiudad (its agreement with Correos only allows consulting the codes, not downloading them) and the Correos website. |

DIR3 and the other codes of public bodies do not go here: they identify the town council, not the
territory (see §10).

### 4.3 Names and languages

Languages, with their BCP 47 code:

| Language | Code | Status |
|---|---|---|
| Spanish (Castilian) | `es` | official throughout Spain |
| Catalan / Valencian | `ca` | co-official in Catalonia, Illes Balears and the Comunitat Valenciana. If a Valencian-specific interface is ever needed, its code is `ca-ES-valencia`. |
| Galician | `gl` | co-official in Galicia |
| Basque | `eu` | co-official in the Basque Country and in the Basque-speaking area of Navarre |
| Aranese (Occitan) | `oc` | official in Catalonia; official name of the nine municipalities of the Val d'Aran. The Wikidata labels in `oc` are general Occitan, not always the Aranese standard. |
| English | `en` | not official; for the international public |
| Asturian, Aragonese | `ast`, `an` | protected, not official. They are stored in the data with their code, but are not used in the interface. |

Name fields of each territory:

| Field | Example | Origin |
|---|---|---|
| `official` | «Coruña, A», «Alicante/Alacant», «Balears, Illes» | INE, literal |
| `display` | «A Coruña», «Alicante/Alacant», «Illes Balears» | Derived: the article moves to the front. It can be corrected by hand. |
| `parts` | `{"es": "Alicante", "ca": "Alacant"}` | Only in bilingual official names. The language of each part comes from a hand-reviewed list cross-checked with Wikidata. |
| `lang` | `{"en": "Catalonia", "eu": "Katalunia"}` | Usual name in each language. For autonomous communities, a hand-reviewed list; for provinces, islands and municipalities, Wikidata, without a final qualifier in brackets («Neda (A Coruña)») and only if it differs from the official one leaving aside accents, capitals and punctuation (for searching they are the same name). |
| `short` | «Baleares», «Navarra» | Autonomous communities; hand-reviewed list, per language. |
| `aliases` | «Orense», «Lérida», «La Coruña», «Guipúzcoa» | Hand-reviewed list, with its language and its type (exonym, historical, abbreviation). |
| `slug` | `a-coruna` | Derived |

In `fuentes/nombres-comunidades.csv`, each `revisado` (reviewed) name carries its source in `source`: `ine`
(official name), `estatuto` (statute of autonomy), `optimot` (Catalan), `rag` (Galician), `euskaltzaindia`
(rule 32), `iea` (dictionary of the Institut d'Estudis Aranesi) or `uso` (English, no standard). `pendiente`
(pending) names carry no source.

The official INE names are already those of the local language when the law so states: in Galicia,
Catalonia and Illes Balears only the Galician or Catalan form is official. "Gerona" or "Sanjenjo"
are not official names, but aliases.

### 4.4 Which name is shown in each language

The data stores all the names; this is the default rule of `name(id, lang)`:

- **Countries and autonomous communities**: the name in the language of the page ("Catalonia", "Katalunia",
  "Cataluña").
- **Provinces, islands, comarcas, judicial districts, warning zones, municipalities and minor local entities**: the official one (a district's is
  its seat's). If it is bilingual, only the part in the language of the page ("Alacant" in Catalan,
  "San Sebastián" in Spanish) and the full name in the others. In Spanish "Girona" is shown, not "Gerona".
- The usual names in other languages ("Gerona", "Seville", "Saragossa") are used for searching and
  are available for anyone who wants to display them.

### 4.5 Geography, population and classifications

- **Reference point of the municipality** (its capital): the population nucleus that the IGN
  marks as the capital of the municipality in its features API (collection `nuc`, product IGR
  Poblaciones, CC BY 4.0), with longitude, latitude and altitude. Some capitals are not nuclei for
  the INE: they are in the collection `opob` of the same product, read only for the places marked
  as municipal capitals. It is cross-checked with the
  boundaries: a capital outside its municipality goes to the report. The Nomenclátor de Municipios
  y Entidades de Población would give the same, but its download needs a form signed by the
  browser; if the CNIG gives a direct link, the source can change.
- **Municipal boundaries**: IGN, Base de Datos de Límites Jurisdiccionales (BDLJE), CC BY 4.0. The
  zip weighs 66 MB and the municipalities 145 MB of GML, so they go neither in git nor in the
  package: each GitHub release carries `limites-municipios.geojson.gz`, simplified to 5 m (far
  below the boundaries' own uncertainty of about 40 m) and with our identifiers. It includes the
  shared areas that belong to no municipality (comunidades jurisdiccionales), without an
  identifier.
- **Official population** of provinces and municipalities from the INE (padrón at 1 January),
  from its JSON API: one table per province with its total and that of each municipality. The
  municipalities are checked to add up to their province's total. The INE tables for communities
  and islands end in 2021; their population would be the sum of their provinces or
  municipalities. Together with the **area** from the LAU table, used to order candidates.
- **From the Eurostat LAU table**, per municipality: degree of
  urbanisation (city, intermediate, rural), whether it is coastal and which city or functional
  urban area it belongs to. For example, they make it possible to filter job offers in rural areas
  with an official criterion.
- **Time zone**: `Europe/Madrid`; `Atlantic/Canary` in the Canary Islands; `Africa/Ceuta` in Ceuta
  and Melilla.
- **Links to Wikipedia** in each language, from Wikidata.

### 4.6 Changes over time

The INE publishes a new dictionary every year and the list of changes (additions, removals,
mergers and name changes), and during the year, the changes registered in the Registro de
Entidades Locales. The data start from the dictionary as of 1 January 2026 and apply the name
changes registered since then: the new name becomes the official one and the previous one stays
as an alias (`former_official`, with the date of the resolution in `until`). Additions and
removals of the year go to the report and come in with the next dictionary. Afterwards:

- a name change keeps the identifier and stores the previous name as an alias with dates;
- a merger or segregation creates new identities and succession links;
- a monthly workflow checks whether the sources have changed and, if so, opens a PR with the
  summary: new or removed municipalities and changes of name or code.

## 5. How the sources are related

- **The owner of each datum rules**: the INE for official codes and names, the IGN for coordinates
  and boundaries, Eurostat for NUTS and LAU, ISO for its codes. Wikidata and OSM fill in what the
  official source does not provide (names in other languages, links) and serve for cross-checking.
- **Each link stores its provenance**: the source, how it was made (by code, by name or by
  position) and the date of the source.
- **Differences are not resolved silently.** The generator writes a discrepancy report and Actions
  publishes it in an issue that is updated on each run, like the employment areas report. They are
  corrected by hand: in `fuentes/` if the error is ours, or in Wikidata and OSM if it is theirs.
- **The hand-reviewed lists** (`fuentes/`) are small and say where each value came from. The
  generator cross-checks them against the automatic sources.

## 6. Interface

The same in Python and in JavaScript, in English, with the same test cases for both languages. The
data fields are also in English. In JavaScript, compound names are camelCase (`relateName`) and
options go in an object (`search(text, { within, levels })`).

| Function | What it does |
|---|---|
| `resolve(system, code)` | From a code to a territory with its ancestors, or `None`/`null` if it does not exist. Systems: `ine:autonomia`, `ine:provincia`, `ine:municipio`, `ine:municipio:dc`, `dgc:municipio`, `mjusticia:partido`, `aemet:zona`, `rel:comarca`, `idescat:comarca`, `aragon:comarca`, `rel:eatim`, `iso3166-1:alpha2`, `iso3166-1:alpha3`, `iso3166-2`, `nuts`, `lau`, `wikidata`, `osm:relation`, `geonames`… |
| `territory(id)` | Full record: names, codes, parent and ancestors. |
| `search(text, within, levels)` | Candidates for a text, each with its reason (`official`, `part`, `lang`, `alias` or `variant`) and in a fixed order. `within` limits the search to a scope, for example a province, an island, a judicial district, a warning zone or a comarca; a minor local entity is within those of its municipality. Judicial districts, warning zones, comarcas and minor local entities only come up if asked for in `levels`. |
| `children(id)` | The territories whose parent is this one; for an island, a judicial district, a warning zone or a comarca, its municipalities. Those of a community include its comarcas; those of a province include its judicial districts, its warning zones and, in the Balearic and Canary Islands, its islands; those of a municipality are its minor local entities. |
| `mentions(text, levels)` | Territories named within a longer text ("Moncada (Valencia)"), without overlapping and starting with the longest name. If the full name is not in the catalogue, it may return a shorter one contained in it ("Perales de Alfambra" → Alfambra). By default, only autonomous communities and provinces. |
| `normalize(text)` | The common normalisation: no accents or capitals, "l·l" as "ll", the article in front and hyphens as spaces. |
| `name(id, lang, short)` | The name that is displayed, according to §4.4. |
| `relate_name(text, within, levels)` | A relation with status: resolved (one candidate), pending (none or several) or conflict. |
| `combine(relations)` | Joins several relations of the same object: if they agree, resolved; if they contradict each other, conflict. |
| `parse_cadastral_reference(text)` | Parts of a 14, 18 or 20-character cadastral reference: parcel, kind (rustic or urban), property, check letters and whether they are right, and, for a rustic parcel, the DGC code of its municipality. Offline. |
| `relate_cadastral_reference(text)` | The municipality of a cadastral reference: resolved for a rustic parcel whose DGC code is in the catalogue; pending for an urban one (it does not carry the municipality), when the check letters are wrong or when the code is unknown. |
| `locate(lon, lat, limits)` | Voceiro's point-to-municipality mapping, with the release boundaries file (`load_limits`; in JS, `loadLimits` in Node or `createLimits` in the browser): resolved inside one municipality and more than 50 m from any other; pending near a boundary, in a shared area or outside all of them (the sea, abroad); conflict if it falls in two. It never returns "the nearest". |
| `postal_codes(id)` | The postal codes of a municipality, by code, each with its source, its count, its unit and the other sources that have it (`also`). |
| `municipalities(code)` | The municipalities of a postal code: by count when all have the same unit (addresses, portals or street sections), otherwise by the street sections of the INE (0 if it lacks the pair), because counts in different units do not compare. |
| `relate_postal_code(code)` | Resolved if the code belongs to a single municipality; pending if it belongs to several or to none. The evidence carries each candidate's source, count, unit and `also`. `combine` with the municipality's name removes the ambiguity. |

Postal codes have their own table (`load_postal_codes`; in JS, `loadPostalCodes` in Node or
`createPostalCodes` in the browser), not `resolve`: a code spans several municipalities and a
municipality has several codes, while `resolve` returns a single territory.

The rest of the library never calls the Catastro. To place an urban reference or a point there is
the separate, optional module `catastro_online` (in JS, the subpath
`territorios-es/catastro-online`, asynchronous, which also works in the browser because the
Catastro answers with `Access-Control-Allow-Origin: *`). It uses the Catastro's free services and
stores nothing:

| Function | What it does |
|---|---|
| `locate_reference(text)` | The municipality of an urban or rustic cadastral reference according to `Consulta_DNPRC` (one request). A rustic one is cross-checked with the offline reading: if they differ, conflict. |
| `locate_point(lon, lat, srs)` | The parcel at a point (`Consulta_RCCOOR`) and its municipality (`Consulta_DNPRC`): two requests. Pending when there is no parcel (the sea or the foral territories). The parcel goes into the evidence. |

Both return a relation with status and evidence, like the other functions, and accept their own
`fetch` (for tests, caching or pauses). A network error or an unreadable answer raises
`CatastroError`. They should not be run in a loop without a pause.

**Identifiers**: Voceiro's, which are already published: `pais:ES`, `es:autonomia:12`,
`es:provincia:36`, `es:municipio:36038`. They are labels, so it does not matter that they are in
Spanish. Each consumer can keep providing its own codes (empleo publishes the INE code without a
prefix).

**Relator**: this is where the generic relation model goes, with status, candidates, reason and
evidence. Each project keeps only what is its own (for example, the coverage of a media outlet).

## 7. Package, versions and licences

- **Structure**:
  - `datos/`: generated files (JSON and CSV) and their manifest;
  - `fuentes/`: what is hand-reviewed (names per language, aliases, ISO and NUTS codes, languages
    of the bilingual names, URL of each source); for a source copied by hand, such as the exports
    of the Registro de Entidades Locales, `fuentes.json` keeps the date (`retrieved`) and the lists
    made from it (`copies`), and the manifest the digest of each;
  - `python/` and `js/`: two small readers of the same data;
  - `generador/`: downloads, cross-checking and discrepancy report;
  - `web/`: the data website;
  - `pruebas/`: cases shared by Python and JS.
- **Installation**:
  - Python: `pip install "territorios-es @ git+https://github.com/alertapublica/territorios-es@vX.Y.Z"`.
  - JS: `npm install github:alertapublica/territorios-es#vX.Y.Z`.
- **Versions** (semver): patch, corrections; minor, data for the new year and new codes or fields;
  major, changing identifiers or removing fields. Each consumer pins the exact version.
- **Licences**:
  - the code, MIT;
  - each datum keeps the licence of its source: INE (CC BY 4.0), IGN/CNIG
    (CC BY 4.0), Eurostat (CC BY 4.0), GeoNames (CC BY 4.0), Wikidata (CC0);
  - IGN: the licence (Orden FOM/2807/2015) asks to cite each product with the formula of the
    Sistema Cartográfico Nacional table: "IGR_POBLACIONES 2024 CC-BY 4.0 scne.es" for the capitals
    and, since the boundaries are simplified, "Obra derivada de BDLJE Continua CC-BY 4.0 ign.es",
    which also goes inside the boundaries file (the licence asks for it in the metadata);
  - Catastro: its licence (July 2016) allows public and commercial use only of transformed
    information and forbids spreading the original or presenting it as "información catastral".
    We publish the crosswalk of codes with our identifiers, citing the source; the original answers
    stay in the Actions cache and never enter the repository (tests use invented answers of the
    same shape);
  - postal codes: each source with its licence and attribution (table in the README): Madrid city
    council, ICGC, IDENA, Eustat, INE and CDAU, CC BY 4.0; IDEIB, CC BY; Catastro, the DGC licence,
    citing the source and the access date (`retrieved` in the manifest). Only the postal
    code–municipality pairs with their count are published, never the addresses. The postal code is
    Correos's: its database is not copied, what the administrations publish is gathered, and there
    is a way to claim (issue «Reclamación sobre datos»);
  - whatever is copied from OpenStreetMap goes in separate files under ODbL, because that licence
    requires publishing under ODbL any database that mixes its data.

  The README has the table of attributions.

## 8. Data website

It is published on GitHub Pages from the first version: the files, the description of each field
and the attributions, in Spanish, Catalan, Galician, Basque, Aranese and English. It grows with
each new mapping. We write the translations ourselves when writing them (they are not generated at
run time) and they are marked as pending review until someone with command of the language reviews
them.

Every page links to the status page (`<language>/estado/`, in the same six languages): levels and
relations of the published data, coverage of each datum over the municipalities where it exists
(listing those missing it, when few), each community, sources, files, library and workflows, with
Mermaid diagrams. «Explore» opens each table in Datasette Lite from a SQLite database the website
publishes with every CSV and the codes as text, so that 01001 does not become 1001. `web/estado.py`
builds it from `datos/`, `fuentes/` and the repository itself, and it is published when CI passes on
`main`. The same script writes `docs/estado.md` and `docs/status.md` (Spanish and English), which
GitHub renders: CI checks they are up to date and the data workflows regenerate them in their PRs.
If a source, module, workflow, level or column appears that is not on its map, or the map names
something that no longer exists, the check fails.

The status page also has two tabs about the sources and time. "Cross-check" counts, on the published
data, how many sources give each pair of postal code and municipality, what each one brings (and what
only it says or is not published) and which source gives each name and each code. "Changes" compares
every generation of `datos/` with the previous one, row by row and with one key per file
(`web/cambios.py`): rows added, removed and changed and new columns, with the detail when they are
few, and since when each source has had the same footprint. A generation is a change of `datos/` that
reaches `main`, so it comes from the git history and is only on the website, not in `docs/status.md`.
Everything that is published goes through git; the originals of each source are not kept, and their
footprint and the date they were read stay in the manifest. A published file with these changes is
left for later.

## 9. Ready for the EU

The first version is Spain only, but nothing prevents extending it:

- the code does not assume Spain: the name rules (articles, bilingual separator) are data per
  language, not code;
- the European codes (NUTS, LAU) are already in the model, and the LAU table reader takes the
  country as a parameter;
- identifiers carry the country in front. For other countries it is proposed to use the European
  ones (`eu:nuts:PT11`, `pt:lau:1601`), which will have to be decided when the time comes;
- the data of another country would go in its own folder or in a sibling repo with this same code.

## 10. Adoption and what we can contribute

- **empleo-publico-abierto**, the first: replace `municipios.csv` and the tables of `regions.py`.
  Test: `api/ofertas.json` identical in `ccaa`, `provincia` and `municipio` with the same data.
  Afterwards: coordinates in the API, a map of offers, alerts "within X km of…" and pages per
  province (also for the Tragsa website).
- **Other projects** adopt the library in their own repo, at their own pace.
- **Public bodies** (town councils, provincial councils, mancomunidades, DIR3, electronic office,
  notice board and employment page): in a sibling repo, later on, linked with these identifiers.
  They change more often and have other sources, such as the Registro de Entidades Locales.
- **Non-working days per territory**, to calculate deadlines in working days: another sibling
  dataset.

## 11. Similar projects

Review of 9 November 2026. None brings together everything we are looking for (official and
European codes, names in the co-official languages, tools in Python and JS and regeneration from
the source), but several are useful for cross-checking or as inspiration:

| Project | What it provides | Intended use |
|---|---|---|
| [codeforspain/ds-organizacion-administrativa](https://github.com/codeforspain/ds-organizacion-administrativa) | Autonomous communities, provinces, current and historical municipalities (INE dictionaries since 2004) and islands, in CSV and JSON. | Cross-checking only: the repository has no licence. On 10 November 2026 it matched our data in all 8,132 municipalities and 52 provinces. Its sources are the INE's, which we read directly. |
| [inigoflores/ds-municipios-catastro-es](https://github.com/inigoflores/ds-municipios-catastro-es) | Mapping of INE and Catastro codes taken from the OVC service. | Cross-checking of our Catastro mapping. |
| EU Vocabularies: ATU and Country authority tables (Publications Office) | Administrative units of the Member States, current and past, with stable URIs. | Cross-checking and linking, if its coverage of Spain reaches municipalities. |
| Eurostat GISCO | LAU–NUTS tables and boundaries. | The tables and the codes, yes. The boundaries, no: their licence excludes commercial use. |
| EuroGeographics, Open Maps For Europe | European boundaries. | Discarded: EuroGeographics' own licence, EuroBoundaryMap is not open, and the data for Spain come from the IGN, which we use directly. |
| Unicode CLDR and Debian iso-codes | Translated names of countries and of ISO 3166-2 subdivisions. | Reviewed on 11 November 2026 (CLDR 49): discarded for country names, which still come from Wikidata. It has no Aranese and uses interface names («Congo - Kinshasa», «RAE de Hong Kong (China)», «Côte d’Ivoire» in Spanish). |
| mapSpain and giscoR (R packages) | Maps of Spain and dictionaries of codes and names. | Inspiration. |
| datos.gob.es | URIs of autonomous communities and provinces. | Possible additional identifier. |
| Base de datos general de entidades locales (Ministry of Finance) | Local entities with INE code and NIF. | For the sibling repo of public bodies. |

Reviewed on 10 November 2026:

- Who's On First, geoBoundaries and Overture Maps: derived from OpenStreetMap or from the official
  sources we already use, with mixed licences. They add nothing.
- es-atlas: TopoJSON built from the IGN files, like our boundaries.
- INE JSON API (`servicios.ine.es/wstempus`): gives, for example, the official population of each
  municipality with its code, in one table per province. Used for population (§4.5).
- Nomenclátor Geográfico Básico (collection `namedplace` of the IGN API): 1.19 million place names,
  without their language. Not useful for names per language.

## 12. Decisions

Taken with the project owner on 9 November 2026:

1. The document does not describe projects outside this library.
2. Languages: all the official languages of Spain and English; Asturian and Aragonese in the data,
   without an interface.
3. Everything is translated: data, website and documentation. The README and the design come
   first in Spanish and English; the long documentation in the other languages, afterwards.
4. Which name is shown: the rule of §4.4.
5. Voceiro's identifiers.
6. Code, fields and technical documentation in English.
7. The sources are related as section 5 says.
8. OpenStreetMap as support, and Open Maps For Europe (EuroGeographics) too, for cross-checking.
9. European codes for the Spanish territories, with everything ready to extend to the EU.
10. First version: countries, time zone, links to Wikipedia and postal codes (the latter, if a
    reusable source is confirmed, see §4.2). Second: islands, comarcas and judicial districts.
    Later: population entities and non-working days.
11. The generic relation model (statuses and evidence) lives here.
12. Public bodies, in a sibling repo.
13. The data website is published with the first version.

Taken on 10 November 2026:

14. Postal codes: in this repo, with their own workflow twice a year that only writes
    `datos/codigos-postales.csv`, `datos/codigos-postales-fuentes.csv` and their manifest entries
    (which the monthly generator keeps). It gathers what the administrations publish, with the
    source of each pair and a way to claim; the Correos database is not copied. In each municipality
    the first source that covers it and has data decides: Madrid city council; ICGC, IDENA, Eustat and
    IDEIB; INE; CDAU; Catastro. All its pairs of that municipality are published, with no threshold
    (a pair is in or out), and no other source fills in single pairs, because the old codes of the
    Catastro would come back. Fixed rules for all: five digits with a province 01–52, no XX000
    (filler), and the mergers that the Catastro still files under the old DGC codes (Oza-Cesuras,
    Cerdedo-Cotobade). Each pair carries its source's count in its unit, never adding up units, and
    the other sources that have it (`also`). If a download fails nothing is written. The API works
    both ways and stays out of `resolve`.

Taken on 11 November 2026:

15. Judicial districts: level `judicial_district` with the province as parent, like the islands,
    from the Ministry of Justice's Censo Judicial in every monthly generation. Identifier
    `es:partido:PPNN` (province and the Ministry's number), named after the seat and left out of
    `search` and `mentions` unless asked for. The download is mandatory: if the Ministry does not
    answer, the generation fails before writing anything, instead of publishing the municipalities
    without a district. No third-party repositories: none is maintained or improves on the official
    source.
16. AEMET warning zones: level `warning_zone` with the province as parent, from the municipality
    master of AEMET OpenData (with the key as a repository secret) and the table of the zone
    boundaries, in every monthly generation. Identifier `es:zona-aviso:CCPPZZ` (AEMET code), with
    its official name and left out of `search` and `mentions` unless asked for. The download is
    mandatory, as is the Censo Judicial's. The master is preferred to the PDF table of the
    Meteoalerta plan, which has the same (checked on 11 November 2026: the master's 8,122 rows,
    without its 2 extinct municipalities and with the 4 exceptions of `fuentes/zonas-aviso.csv`, are
    the PDF's 8,124 municipalities, with the same zone), because it is JSON and there is no need to
    read 221 pages.
17. Comarcas: only those that are a local entity, with the Lluçanès from now on (it is created by
    law and its council comes in 2027), level `comarca` with the community as parent and our own
    identifier `es:comarca:CCNN`, which does not depend on the Registro registering it and does not
    change if it is renamed (the cuadrilla of Ayala is now Aiaraldea's). The municipalities of
    Catalonia and Aragon come every month from Idescat and Aragón Open Data; the list of comarcas
    and the municipalities of Álava and El Bierzo, from a hand-reviewed export of the Registro,
    because it is an old binary Excel file and they change very little. Municipalities of other
    communities are not filled in with statistical comarcas.

Taken on 12 November 2026:

18. Population entities (#31): set aside until a concrete use measures with real texts what they
    add. The INE street register was read (146,079 entities on four levels) and their names were
    matched with the IGN. There may be matches: 86% of the names of singular entities belong to a
    single municipality, and search does not find many of them today. But this way of doing it
    was heavy: the npm package went from 0.9 to 2.2 MB compressed, loading the entities took 5 to
    9 s and about 350 MB of memory, and every month left thousands of name warnings. What was
    checked, and where to start if it is taken up again, is in #31.

Taken on 13 November 2026:

19. Minor local entities (#48): those of the Registro de Entidades Locales, level
    `minor_local_entity` with the municipality as parent and identifier `es:entidad-menor:` plus the
    Registro number, the only code they have. The list comes from an export of the Registro reviewed
    by hand, like the comarcas, with the municipality by INE code and the type under each
    community's law, checked article by article (in Andalusia, entity by entity). Left out of
    `search` and `mentions` unless asked for. No match with the population entities, which are still
    set aside. The DIR3 and NIF of public bodies, these entities included, do not go here (§4.2):
    they will go to the public bodies repository (§10).

## 13. Source checks

Before using each source, its URL, format and licence have to be checked. Already checked on
9 November 2026:

- **Eurostat LAU table**: the validated one is `EU-27-LAU-2024-NUTS-2024.xlsx` and there is a 2025
  one "partially validated" ([page](https://ec.europa.eu/eurostat/web/nuts/local-administrative-units)).
  Opened by the generator in Actions: it has NUTS 3, the LAU code (in Spain, the 5-digit INE code,
  identical for the 8,132 municipalities of 2026), names, population, area, degree of
  urbanisation, coast, city and functional urban area.
- **NUTS 2024**: in force since 1 January 2024 (Commission Delegated Regulation (EU) 2023/674);
  Spain has 7 NUTS 1, 19 NUTS 2 and 59 NUTS 3.
- **Wikidata**: property P772 (INE code) admits 2 digits (province), 5 (municipality) and 11
  (population entity), so it has to be filtered by length. P782 (LAU) carries the country prefix.
  There is no property for the Catastro code.
- **Catastro**: `ConsultaProvincia` gives the 48 common-regime provinces (without Álava,
  Gipuzkoa, Navarre or Biscay) and `ConsultaMunicipio`, per province, each municipality with its
  DGC code (`locat`: office and municipality) and its INE code (`loine`), written as numbers
  without leading zeros. For A Coruña it gives 95 municipalities for the INE's 93: it includes
  Cesuras and Oza dos Ríos, merged in 2013, which go to the report. The DGC code differs from the
  INE code in 61 of the 95. In the first full generation: 7,608 municipalities with a DGC code (all
  the common-regime ones). Some Catastro offices are not provinces and have their own two digits,
  which start the DGC code and the rustic references: 51 (Cartagena), 52 (Gijón), 53 (Jerez), 54
  (Vigo), 55 (Ceuta) and 56 (Melilla). The Catastro cuts names at 30 characters and sometimes puts
  the article at the end or leaves it out; the name cross-check allows for that and only reports
  really different names (old names such as «La Bisbal de Falset», or abbreviations).
- **GISCO boundaries**: they exclude commercial use and carry "© EuroGeographics". Discarded as a
  source.
- **CartoCiudad**: it does not allow downloading postal codes (agreement with Correos,
  BOE-A-2023-11522). Discarded for postal codes.
- **IGN**: CC BY 4.0 licence (Orden FOM/2807/2015 and the CNIG conditions), with the attribution
  formula of each product in the Sistema Cartográfico Nacional table. The boundaries (BDLJE) are
  downloaded from a direct link in the IGN Atom feed: a 66 MB zip, updated on 10 August 2026, with
  8,220 municipal units in GML (EPSG:4258, latitude and longitude) and an uncertainty of about
  40 m. The CNIG download server cuts the TLS connection from some networks; from Actions it
  works. The Nomenclátor de Municipios y Entidades de Población (CSV and Access, March 2026) has
  capital, coordinates, altitude, official area and Registro de Entidades Locales number, but it
  can only be downloaded through a form signed by the browser (403 without it), so the capitals
  come from the IGN features API (collection `nuc`, 37,497 nuclei with INE code, coordinates,
  altitude and `capital`: one digit per level, State, community, province and municipality). None
  of them has names per language.

Checked on 10 November 2026:

- **INE licence**: CC BY 4.0 (legal notice). For processed data the attribution is «Elaboración
  propia con datos extraídos del sitio web del INE: www.ine.es», with the update date of the
  original.
- **INE codes operation**: besides the dictionary and the province table, it publishes the island
  table (`26codislas.xlsx`, with the municipalities of each island; its title says «a 1 de enero
  de 2025», but it matches the 2026 dictionary), each year's changes
  (`codmunNN/NNcodmunmod.htm`), those registered so far this year (`codmun_anual.htm`; 15 name
  changes on 10 November) and the number of municipalities per province, community and island.
- **Eurostat LAU table**: 2024 is still the latest validated one; 2025 and 2026 are «partially
  validated».
- **IGN capitals**: 79 municipalities without a capital in `nuc`; the collection `opob` marks it for
  54 (two of them with two, which stay without a capital) and the other collections have none.
- **Electoral roll street directory (INE)**: national and provincial files in January and July,
  with the postal district of each street section (Correos's). The July 2026 edition has 13,988
  pairs in 8,132 municipalities; 4 are XX000 (28000 in Madrid among them). It is the source for all
  Spain.
- **Cross-check of postal-code sources**: where there are three, the share of what each would publish
  that another one also has. Catalonia: ICGC 98.6 %, INE 98.8 %, Catastro 89.6 %. Madrid city: city
  council 88.9 % (seven border pairs of one or two addresses), INE 98.2 %. Balearic Islands: IDEIB
  92.9 %, INE 98.8 %. Andalusia: CDAU 78.7 % (402 pairs no one else has), INE 98.0 %, Catastro
  95.7 %. None is always right: the ICGC puts Santa Pau's 17811 in Olot (2,968 addresses), the IDEIB
  Palma's 07010 in Santa Margalida, and the INE keeps Manresa's 08240.
- **ICGC, Adreces (simplified version)**: one ZIP for all Catalonia in a directory with the date in
  the name (`adreces-simplificat-v1r0-YYYYMMDD.zip`); two CSV tables (";") with `codmuni` (INE code
  and check digit) and `codpostal`. No XX000.
- **Madrid city council, official street directory**: CSV of current addresses (Windows-1252, ";"),
  with the date in its name; its URL comes from the catalogue API (`package_show`). `COD_POSTAL` per
  address; no 28000.
- **IDEIB, portals of the Balearic Islands**: a one-column CSV (`ADRECA_DET`) with the postal code
  after the number and the INE municipality inside `ID_PORTAL`. 308,733 portals, 3 without a code.
- **CDAU, portals of Andalusia**: a 200 MB ZIP with a 700 MB CSV, `ine_mun` and `cod_postal`.
  Cross-checking only: a fifth of its pairs are in no other source.
- **Catastro, INSPIRE Addresses**: a general ATOM with 52 territorial offices (plus entries for the
  foral cadastres, which point to other servers), one ATOM per office (ISO-8859-1) and one ZIP per
  municipality with a GML (EPSG:25830). Each address links its postal code (`AD:PostalDescriptor`)
  and its municipality (DGC code). The code drops its leading zero (`2250` is 02250); in Madrid, 282
  addresses link a descriptor that is not in the file. Use `https://` and `/INSPIRE/Addresses/`, and
  encode the spaces and eñes of the links. The download licence (clauses 3, 5–8 and 12) does not
  exclude third-party data, allows public and commercial use of transformed information and asks
  to cite the DGC and the access date.
- **IDENA, addresses of Navarre**: a shapefile whose DBF has the INE municipality without the
  province (`CMUNICIPIO`) and `CODPOSTAL`. CC BY 4.0 according to its metadata, with the attribution
  "Información geográfica propiedad del Gobierno de Navarra.".
- **Eustat, NORA street directory**: one file per historical territory, CSV (UTF-8 with BOM, ";") or
  XLSX (prefix `x:`). The Gipuzkoa CSV is always cut halfway through the download; the XLSX comes
  down whole. CC BY 4.0, with the attribution "Eusko Jaurlaritza / Gobierno Vasco; Eustat;
  geoEuskadi".
- **Official INE population**: operation 22 (`DPOP`) of the JSON API. `TABLAS_OPERACION/22` gives
  52 tables with the code `PROV-MUN` («Población por municipios y sexo», one per province,
  including Ceuta and Melilla) and `DATOS_TABLA/{id}?nult=1&tip=AM&tv=18:451` the latest year of
  the total for both sexes, with the INE code in each series' metadata: 1 January 2025, final,
  published on 11 December 2025. Municipalities that no longer exist keep their series, empty
  (Cesuras). The tables
  for communities (2853) and islands (2910) end in 2021. The national table by municipality
  (29005) is over 10 MB.

Checked on 11 November 2026:

- **Censo Judicial (Ministry of Justice)**: XLSX in the Ministry's download area and in the
  datos.gob.es catalogue (`e05228601-censo-judicial`); according to the dataset's metadata, its
  conditions of use are the catalogue's general ones (`https://datos.gob.es/avisolegal`). The
  Ministry portal's legal notice limits its other contents to private use. One row per
  municipality with `CPRO`, `PJ` (district number), `CODM PJ` (seat), `CODM` and `CPJ` («SI» at the
  seat), and a last row «Actualizado a 25/03/2026». It has the dictionary's 8,132 municipalities and
  431 districts, each with one seat in its province, and it matches row by row the PDF Nomenclátor
  de Partidos Judiciales of 30 December 2025. Its population matches the INE's; its postal code is
  that of the court or town hall, not the municipality's. No district joins two islands except
  Eivissa's, which includes Formentera.
- **Cross-checking the districts**: the CGPJ publishes the population by district and municipality
  every year (XLSX, names only) and the Generalitat the CTEAJE catalogue of Spain's districts (code,
  name and seat). No third-party repository with the national relation is maintained.

Checked on 13 November 2026:

- **Minor local entities in the Registro de Entidades Locales**: exported without a form at
  `…/export_excel/eatimes/all/all` (community and province; with a single `all` the server gives a
  PHP error), in the same old binary Excel as the comarcas. Columns: community, province, name,
  registration number (without the leading zero), registration date, seat and municipality, by
  name only. No coordinates, population entity code or Wikidata (in Wikidata, 226 items are a minor
  local entity, Q3333989). The latest registered are Igeldo and Aizarotz, in 2025.
