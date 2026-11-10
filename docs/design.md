# Design of territorios-es

Draft of 9 November 2026. The decisions already taken are in the section
[Decisions](#12-decisions); what is missing, in [Pending](#13-pending), and what has to be
checked for each source, in [To verify](#14-to-verify). There is a Spanish version at
[`diseno.md`](diseno.md).

## 1. Purpose

Many projects need the same thing: to know that "Orense", "Ourense" and `32054` refer to the same
place, to convert from one code to another and to show the correct name in each language.
`territorios-es` brings all of that together in one place, where a territory is recognised by any
of its names and codes. Its data is regenerated from the official sources, and the open ones
(Wikidata, OpenStreetMap) serve as support and for cross-checking. It offers three things:

1. **Catalogue**: Spain, its autonomous communities and autonomous cities, provinces and
   municipalities, and the countries of the world, with their hierarchy, their names (official,
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
  and the reference date. The generator runs in GitHub Actions, not locally.
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
- **Everything is deterministic, no AI.** Fuzzy search is an optional add-on.
- **All useful sources are used, related with their provenance** (see section 5).

## 4. Data

### 4.1 Levels

First version:

- **Spain**: 19 autonomous communities and autonomous cities, 52 provinces and 8,132
  municipalities (those of the INE as of 1 January 2026).
- **Countries**: the complete ISO 3166-1 list, with its name in each language and whether they
  belong to the EU or the European Economic Area. It is useful, for example, for the nationality
  requirement in job calls.

Second version: islands (cabildos and consells), official comarcas and judicial districts. The
islands are done (version 0.3):

- **Islands**: the 11 with a cabildo (Canary Islands) or a consell insular (Balearic Islands),
  with level `island` and an identifier with the INE island code (`es:isla:384` is Tenerife;
  `es:isla:072`, Ibiza). Their parent is the province. Municipalities keep their parent and also
  carry the field `island`. The code, the official name and the municipalities of each island come
  from the INE island table (`26codislas.xlsx`); `fuentes/islas.csv` adds the Wikidata item and the
  NUTS 3, which is only used to cross-check (Eivissa and Formentera share ES531). Smaller islands go
  with the municipality they belong to (La Graciosa with Teguise, in Lanzarote; Cabrera with Palma,
  in Mallorca). The name is the INE's official one (§4.4); the others come from Wikidata.

Later: population entities from the INE Nomenclátor (núcleos, and parishes in Galicia and
Asturias), which number in the tens of thousands.

### 4.2 Codes

| Code | Levels | Source | Notes |
|---|---|---|---|
| INE | autonomous community (2 digits), province (2), island (3), municipality (5 + check digit) | Annual INE dictionary and island table | Official; it is the basis of identity. |
| ISO 3166-1 | country (alpha-2, alpha-3, numeric) | Wikidata, cross-checked with the UN | |
| ISO 3166-2 | autonomous community and province (`ES-GA`, `ES-C`) | Hand-reviewed list, cross-checked with Wikidata | |
| NUTS 2024 | NUTS 1 (groups of autonomous communities), NUTS 2 (autonomous community), NUTS 3 (province; islands in the Balearic and Canary Islands) | Eurostat | For cross-referencing with European statistics. |
| LAU | municipality | Annual Eurostat LAU table | In Spain it is the 5-digit INE code (checked on all 8,132 municipalities); see §4.5 for what else it provides. |
| DGC (Catastro) | municipality (`dgc:municipio`, 5 digits: office 2 + municipality 3) | Free Catastro web services (`OVCCallejero`, `ConsultaProvincia` and `ConsultaMunicipio`), which give the DGC and the INE code of each municipality | Different from the INE code in many municipalities (A Coruña: INE `15030`, DGC `15900`). The link is by code, not by name; the name is only cross-checked. Álava, Gipuzkoa, Navarre and Biscay have a foral land registry and have no DGC code. |
| BDDAE (INSPIRE) | municipality (`ign:bddae`, 11 digits: 34 + community 2 + province 2 + INE 5) | IGN boundaries (BDLJE) | Code of the IGN administrative unit and `localId` of its INSPIRE identifier (namespace `ES.IGN.BDDAE`). Linked when the INE code, the province and the community match. |
| Wikidata | all | SPARQL from the INE code | CC0. Provides names per language, links to Wikipedia and other identifiers. |
| OpenStreetMap | all | Relation identifier, from Wikidata and cross-checked with OSM | The Wikidata identifier is CC0; whatever is copied from OSM goes separately under ODbL (§7). |
| GeoNames | all | From Wikidata | CC BY 4.0. Widely used by other tools. |
| Postal code | municipality (many-to-many relationship) | To be decided: the INE electoral roll street directory, if it is confirmed that it includes the postal code and can be reused | Useful for reading addresses. CartoCiudad is not suitable: the postal codes belong to Correos and its agreement with the CNIG only allows consulting them, not downloading them. |
| datos.gob.es | autonomous community and province | URIs of the Norma Técnica de reutilización (annex V) | Additional identifier for linking with the national open data catalogue; there are no municipality URIs. |
| EU Vocabularies (ATU) | to be confirmed | Publications Office of the EU | List of administrative units of the Member States with URIs; linked if it reaches municipalities. |

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
| Asturian, Aragonese | `ast`, `an` | protected, not official. They are stored in the data, marked as such, but are not used in the interface. |

Name fields of each territory:

| Field | Example | Origin |
|---|---|---|
| `official` | «Coruña, A», «Alicante/Alacant», «Balears, Illes» | INE, literal |
| `display` | «A Coruña», «Alicante/Alacant», «Illes Balears» | Derived: the article moves to the front. It can be corrected by hand. |
| `parts` | `{"es": "Alicante", "ca": "Alacant"}` | Only in bilingual official names. The language of each part comes from a hand-reviewed list cross-checked with Wikidata. |
| `lang` | `{"en": "Catalonia", "eu": "Katalunia"}` | Usual name in each language. For autonomous communities, a hand-reviewed list; for provinces and municipalities, Wikidata, only if it differs from the official one. |
| `short` | «Baleares», «Navarra» | Autonomous communities and provinces; hand-reviewed list, per language. |
| `aliases` | «Orense», «Lérida», «La Coruña», «Guipúzcoa» | Hand-reviewed list, with its language and its type (exonym, historical, abbreviation). |
| `slug` | `a-coruna` | Derived |

The official INE names are already those of the local language when the law so states: in Galicia,
Catalonia and Illes Balears only the Galician or Catalan form is official. "Gerona" or "Sanjenjo"
are not official names, but aliases.

### 4.4 Which name is shown in each language

The data stores all the names; this is the default rule of `name(id, lang)`:

- **Autonomous communities**: the name in the language of the page ("Catalonia", "Katalunia",
  "Cataluña").
- **Provinces, islands and municipalities**: the official one. If it is bilingual, only the part in the
  language of the page ("Alacant" in Catalan, "San Sebastián" in Spanish) and the full name in the
  others. In Spanish "Girona" is shown, not "Gerona".
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
- **Simplified maps** (TopoJSON of autonomous communities, provinces and municipalities) for
  drawing on a website, made by us from those of the IGN.
- **Population** from the INE padrón and **area**: used to order candidates.
- **From the Eurostat LAU table**, per municipality: degree of
  urbanisation (city, intermediate, rural), whether it is coastal and which city or functional
  urban area it belongs to. For example, they make it possible to filter job offers in rural areas
  with an official criterion.
- **European typologies per province** (NUTS 3): urban or rural, metropolitan, mountain, coastal,
  island and border.
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
| `resolve(system, code)` | From a code to a territory with its ancestors, or `None`/`null` if it does not exist. Systems: `ine:autonomia`, `ine:provincia`, `ine:municipio`, `ine:municipio:dc`, `dgc:municipio`, `iso3166-1:alpha2`, `iso3166-1:alpha3`, `iso3166-2`, `nuts`, `lau`, `wikidata`, `osm:relation`, `geonames`… |
| `territory(id)` | Full record: names, codes, parent and ancestors. |
| `search(text, within, levels)` | Candidates for a text, each with its reason (`official`, `part`, `lang`, `alias` or `variant`) and in a fixed order. `within` limits the search to a scope, for example a province or an island. |
| `children(id)` | The territories whose parent is this one; for an island, its municipalities. Those of a Balearic or Canary province include its islands and its municipalities. |
| `mentions(text, levels)` | Territories named within a longer text ("Moncada (Valencia)"), without overlapping and starting with the longest name. By default, only autonomous communities and provinces. |
| `normalize(text)` | The common normalisation: no accents or capitals, "l·l" as "ll", the article in front and hyphens as spaces. |
| `name(id, lang, short)` | The name that is displayed, according to §4.4. |
| `relate_name(text, within, levels)` | A relation with status: resolved (one candidate), pending (none or several) or conflict. |
| `combine(relations)` | Joins several relations of the same object: if they agree, resolved; if they contradict each other, conflict. |
| `parse_cadastral_reference(text)` | Parts of a 14, 18 or 20-character cadastral reference: parcel, kind (rustic or urban), property, check letters and whether they are right, and, for a rustic parcel, the DGC code of its municipality. Offline. |
| `relate_cadastral_reference(text)` | The municipality of a cadastral reference: resolved for a rustic parcel whose DGC code is in the catalogue; pending for an urban one (it does not carry the municipality), when the check letters are wrong or when the code is unknown. |
| `locate(lon, lat, limits)` | Voceiro's point-to-municipality mapping, with the release boundaries file (`load_limits`; in JS, `loadLimits` in Node or `createLimits` in the browser): resolved inside one municipality and more than 50 m from any other; pending near a boundary, in a shared area or outside all of them (the sea, abroad); conflict if it falls in two. It never returns "the nearest". |

Fuzzy search (`fuzzy=True`, with an optional dependency) is left for later.

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
    of the bilingual names, URL of each source);
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
  - whatever is copied from OpenStreetMap goes in separate files under ODbL, because that licence
    requires publishing under ODbL any database that mixes its data.

  The README has the table of attributions.

## 8. Data website

It is published on GitHub Pages from the first version: the files, the description of each field
and the attributions, in Spanish, Catalan, Galician, Basque, Aranese and English. It grows with
each new mapping. We write the translations ourselves when writing them (they are not generated at
run time) and they are marked as pending review until someone with command of the language reviews
them.

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
- **Change notice**: an automatic PR when the INE publishes a new municipality or a name change.

## 11. Similar projects

Review of 9 November 2026. None brings together everything we are looking for (official and
European codes, names in the co-official languages, tools in Python and JS and regeneration from
the source), but several are useful for cross-checking or as inspiration:

| Project | What it provides | Intended use |
|---|---|---|
| [codeforspain/ds-organizacion-administrativa](https://github.com/codeforspain/ds-organizacion-administrativa) | Autonomous communities, provinces, current and historical municipalities (INE dictionaries since 2004) and islands, in CSV and JSON. | Cross-checking only: the repository has no licence. On 10 November 2026 it matched our data in all 8,132 municipalities and 52 provinces. Its sources are the INE's, which we read directly. |
| [inigoflores/ds-municipios-catastro-es](https://github.com/inigoflores/ds-municipios-catastro-es) | Mapping of INE and Catastro codes taken from the OVC service. | Cross-checking of the Catastro mapping that we will make. |
| EU Vocabularies: ATU and Country authority tables (Publications Office) | Administrative units of the Member States, current and past, with stable URIs. | Cross-checking and linking, if its coverage of Spain reaches municipalities. |
| Eurostat GISCO | LAU–NUTS tables and boundaries. | The tables and the codes, yes. The boundaries, no: their licence excludes commercial use. |
| EuroGeographics, Open Maps For Europe | European boundaries. | Discarded: EuroGeographics' own licence, EuroBoundaryMap is not open, and the data for Spain come from the IGN, which we use directly. |
| Unicode CLDR and Debian iso-codes | Translated names of countries and of ISO 3166-2 subdivisions. | Candidate for country names per language (today from Wikidata); Unicode licence for CLDR. |
| mapSpain and giscoR (R packages) | Maps of Spain and dictionaries of codes and names. | Inspiration. |
| datos.gob.es | URIs of autonomous communities and provinces. | Additional identifier (§4.2). |
| Base de datos general de entidades locales (Ministry of Finance) | Local entities with INE code and NIF. | For the sibling repo of public bodies. |

Reviewed on 10 November 2026:

- Who's On First, geoBoundaries and Overture Maps: derived from OpenStreetMap or from the official
  sources we already use, with mixed licences. They add nothing.
- es-atlas: TopoJSON built from the IGN files, like our boundaries.
- INE JSON API (`servicios.ine.es/wstempus`): gives, for example, the official population of each
  municipality with its code, in one table per province. Useful for population (§13).
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

## 13. Pending

- Translate this document and the README into Catalan, Galician, Basque and Aranese.
- Review the translations of the website and of the names of autonomous communities (marked as
  pending).
- Review the discrepancy report of the first generation: Wikidata labels that are the name of
  another municipality, repeated identifiers and former municipalities with an INE code in
  Wikidata; fix in Wikidata what is their error.
- Allow Actions to open PRs: it is an organisation setting (Settings → Actions → General →
  Workflow permissions). Until then, the monthly update pushes the data branch and warns with the
  link to open the PR by hand. GitHub Pages is already enabled.
- Version 0.4, in order: official INE population as of 1 January (JSON API, one table per province)
  instead of Eurostat's; postal codes from the electoral roll street directory (each street section
  carries its postal district; first, clarify whether the INE licence covers that datum, which
  comes from Correos); judicial districts and official comarcas (find a source: the Registro de
  Entidades Locales records islands, comarcas and associations of municipalities); country names
  from CLDR; GitHub actions still on Node 20.
- Later: population entities, historical INE changes (annual dictionaries since 2004 and each
  year's page of changes), fuzzy search.

## 14. To verify

Before using each source, its URL, format and licence have to be checked. Already checked on
9 November 2026:

- **Eurostat LAU table**: the validated one is `EU-27-LAU-2024-NUTS-2024.xlsx` and there is a 2025
  one "partially validated" ([page](https://ec.europa.eu/eurostat/web/nuts/local-administrative-units)).
  Opened by the generator in Actions: it has NUTS 3, the LAU code (in Spain, the 5-digit INE code,
  identical for the 8,132 municipalities of 2026), names, population, area, degree of
  urbanisation, coast, city and functional urban area.
- **NUTS 2024**: in force since 1 January 2024 (Commission Delegated Regulation (EU) 2023/674);
  Spain has 7 NUTS 1, 19 NUTS 2 and 59 NUTS 3. It remains to confirm whether there are changes
  with respect to NUTS 2021.
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
  with the postal district of each street section.

To be checked:

- electoral roll street directory: whether the INE licence covers the postal code (it comes from
  Correos);
- licences of iso-codes and EU Vocabularies.
