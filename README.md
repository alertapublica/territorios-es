# territorios-es

*[English below](#english)*

Territorios de España —comunidades y ciudades autónomas, provincias, islas, partidos judiciales,
zonas de aviso de AEMET, comarcas y municipios— y países del mundo, con todos sus nombres (el oficial; en castellano, catalán, gallego, euskera, aranés e
inglés; y alias), sus códigos (INE, Catastro, IGN, ISO, NUTS, LAU, Wikidata, OpenStreetMap,
GeoNames…), la capital de cada municipio con sus coordenadas, los límites municipales, los
códigos postales y las entidades de población (parroquias, núcleos…), regenerables desde las fuentes
oficiales y abiertas. Incluye una librería pequeña en
Python y JavaScript para resolver códigos, buscar nombres y elegir el nombre que se muestra en
cada idioma.

Los identificadores (`es:municipio:36038`) solo cambian en una versión mayor; los campos y niveles
nuevos llegan en versiones menores. El planteamiento está en [`docs/diseno.md`](docs/diseno.md) y lo
que falta, en los [issues «objetivo»](https://github.com/alertapublica/territorios-es/issues?q=is%3Aissue+is%3Aopen+label%3Aobjetivo).

La [web de datos](https://alertapublica.github.io/territorios-es/) describe cada fichero y cada campo en seis idiomas. Su página de
[estado](https://alertapublica.github.io/territorios-es/es/estado/) (también en [`docs/estado.md`](docs/estado.md)) muestra qué hay en los
datos, cuánto cubre cada dato, de dónde sale cada cosa y cómo se relacionan las piezas del repositorio.

## Uso

```python
import territorios_es as te

te.resolve("ine:municipio", "36038")["id"]              # 'es:municipio:36038'
te.name("es:provincia:03", "ca")                        # 'Alacant'
te.name("es:autonomia:09", "en")                        # 'Catalonia'
[c["id"] for c in te.search("Ourense", levels=["municipality"])]   # ['es:municipio:32054']
te.relate_name("Ourense")["status"]                     # 'pending': provincia y municipio
te.children("es:isla:071")                              # ['es:municipio:07024']: municipios de Formentera
te.territory("es:municipio:07024")["judicial_district"]  # 'es:partido:0705': el partido de Eivissa
te.territory("es:municipio:46220")["warning_zone"]      # 'es:zona-aviso:774602': zona de avisos de AEMET
te.territory("es:municipio:25243")["comarca"]          # 'es:comarca:0939': Aran
te.parse_cadastral_reference("9872023VH5797S0001WX")["valid"]  # True: letras de control correctas
te.relate_cadastral_reference("13096A001001920000YY")["territory"]  # municipio de una parcela rústica
[m["id"] for m in te.municipalities("28760")]          # Tres Cantos y Madrid, primero el principal
te.relate_postal_code("28760")["status"]                # 'pending': el código es de dos municipios
ent = te.load_entities()                                 # con las entidades de población (unos segundos)
[c["municipality"] for c in ent.search("A Devesa", levels=["singular_entity"])]   # sus municipios
found = te.relate_name("A Devesa", within="es:municipio:36038", levels=["singular_entity", "nucleus"], catalog=ent)
te.to_municipality(found, ent)["territory"]              # 'es:municipio:36038': para combinarla
```

```js
import { loadCatalog, loadEntities, loadPostalCodes, relateName, relateCadastralReference } from 'territorios-es';   // en el navegador: createCatalog(datos)
const te = loadCatalog();
te.name('es:municipio:20069', 'eu');                      // 'Donostia'
te.search('Orense', { within: 'es:autonomia:12' });
relateName(te, 'Ourense', { levels: ['municipality'] });  // { status: 'resolved', … }
relateCadastralReference(te, '13096A001001920000YY');     // sin red
loadPostalCodes().postalCodes('es:municipio:08019');     // en el navegador: createPostalCodes(csv)
loadEntities().resolve('ine:entidad', '36038010101');      // en el navegador: createCatalog(datos, { entities: csv })

import { locateReference } from 'territorios-es/catastro-online';  // con red; también en el navegador
await locateReference(te, '9872023VH5797S0001WX');        // { status: 'resolved', territory: 'es:municipio:13077', … }
```

Funciones: `resolve`, `territory`, `search`, `mentions`, `name`, `children` (en una isla, un
partido judicial, una zona de aviso de AEMET o una comarca, sus municipios), `normalize`,
`relate_name` (en JS, `relateName`), `combine`, `parse_cadastral_reference` y
`relate_cadastral_reference` (referencias catastrales, sin red), `locate` (de un punto a su
municipio), `postal_codes`, `municipalities` y `relate_postal_code` (códigos postales) y
`load_entities` y `to_municipality` (entidades de población). Están descritas en el apartado 6 del
diseño.

Un código postal puede ser de varios municipios y un municipio tiene varios códigos, así que no es
un sistema de `resolve`. Cada par lleva la fuente que decide en su municipio, su recuento en la
unidad de esa fuente (direcciones, portales o tramos) y las demás fuentes que lo tienen (`also`).
Los municipios de un código compartido van por recuento si todos tienen la misma unidad y, si no,
por los tramos del INE (la única fuente de toda España). Cuando la relación queda pendiente, sus evidencias traen todo eso de cada
candidato.

Las entidades de población del callejero del INE (`datos/entidades.csv`: entidades colectivas, como
las parroquias de Galicia y Asturias; entidades singulares; núcleos y diseminados) son unas 146.000,
así que se cargan aparte, con `load_entities` (en JS, `loadEntities`). Cada una cuelga de su
municipio y está en su isla, partido judicial, zona de aviso y comarca, también para `within`.
`search` solo las devuelve si se piden en `levels`, y cada candidato lleva su municipio y su
colectiva. `to_municipality` lleva una relación con entidades a su municipio para combinarla con
otras. El nombre que se muestra («A Devesa») lleva su procedencia en `names.source`: una corrección
revisada a mano (`manual`, la única con `reviewed`), la grafía de un núcleo o lugar del IGN de esa
entidad (`ign`, `ign_lugar`, con el lugar en `names.ref`), una regla de mayúsculas y artículos sobre
el nombre del INE (`regla`, que no pone las tildes que el INE no escribe) o, en un diseminado, el de
su entidad singular («Diseminado de A Devesa»). `names.official` sigue siendo el literal del INE.

`locate` usa los límites municipales del IGN, que por tamaño no van en el paquete: cada versión
lleva adjunto `limites-municipios.geojson.gz` (simplificado a 5 m), que se descarga una vez. Un
punto a menos de 50 m de otro municipio queda pendiente, nunca se elige «el más cercano».

```python
limits = te.load_limits("limites-municipios.geojson.gz")
te.locate(-7.8639, 42.3355, limits)["territory"]          # 'es:municipio:32054'
```

```js
import { loadLimits, locate } from 'territorios-es';        // en el navegador: createLimits(geojson)
locate(loadLimits('limites-municipios.geojson.gz'), -7.8639, 42.3355).territory;
```

Opcional y con red (una o dos peticiones al Catastro por llamada), para referencias urbanas y
coordenadas:

```python
from territorios_es.catastro_online import locate_reference, locate_point

locate_reference("9872023VH5797S0001WX")["territory"]   # 'es:municipio:13077'
locate_point(-3.6, 39.2)["territory"]                   # 'es:municipio:13096'
```

Instalación, con la versión fijada:

```sh
pip install "territorios-es @ git+https://github.com/alertapublica/territorios-es@vX.Y.Z"
npm install github:alertapublica/territorios-es#vX.Y.Z
```

## Datos

Los datos están en [`datos/`](datos/), en JSON y CSV (los límites, adjuntos a cada versión), con la URL, la huella SHA-256 y la fecha de
cada fuente en `datos/manifiesto.json`. Los genera `python -m generador` en GitHub Actions
(workflow «Generar datos»), que abre una PR con los cambios y actualiza un issue con las
discrepancias entre fuentes. Las listas revisadas a mano están en [`fuentes/`](fuentes/).

Los códigos postales se recopilan de lo que publican las administraciones, con su propio workflow
(«Códigos postales», `python -m generador --codigos-postales`), dos veces al año, porque son miles
de descargas. En cada municipio decide la primera fuente que lo cubre y tiene datos, en este orden:
el Ayuntamiento de Madrid (solo su municipio); las fuentes autonómicas que llevan el código de Correos
en cada dirección (ICGC, IDENA, Eustat e IDEIB); el callejero del censo electoral del INE; el CDAU
(Andalucía) y el Catastro. Se publican todos sus pares de ese municipio, sin umbrales, salvo los
códigos mal formados y los de relleno (XX000). `datos/codigos-postales.csv` tiene los pares publicados
y `datos/codigos-postales-fuentes.csv`, lo que dice cada fuente, también lo que no se publica.

### Reclamaciones

Si un código postal o cualquier otro dato está mal, o crees que no debería publicarse, abre un
[issue de reclamación](https://github.com/alertapublica/territorios-es/issues/new?template=reclamacion.md)
con el dato, la fuente y por qué. Se revisa con las fuentes y, si procede, se corrige o se retira.

## Pruebas

```sh
python -m unittest discover -s pruebas -t .
node --test pruebas/*.test.mjs
python -m generador --fixture   # regenera los datos de prueba (sin red)
```

Python y JavaScript comparten los casos de `pruebas/casos.json`.

## Licencias

El código va con licencia MIT ([LICENSE](LICENSE)). Cada dato conserva la licencia de su fuente:

| Fuente | Datos | Licencia |
|---|---|---|
| INE | códigos y nombres oficiales de municipios e islas, cambios de nombre del año y población oficial de provincias y municipios | CC BY 4.0: «Elaboración propia con datos extraídos del sitio web del INE: www.ine.es» (fecha de cada fichero en el manifiesto) |
| Eurostat | LAU, NUTS 3 de cada municipio y superficie | CC BY 4.0 |
| Ministerio de Justicia (Censo Judicial) | partido judicial de cada municipio y su sede | condiciones generales de reutilización de datos.gob.es: «Fuente: Ministerio de Justicia, Censo Judicial» (fecha de actualización en el manifiesto) |
| AEMET | zona de aviso (Meteoalerta) de cada municipio y nombre de cada zona | nota legal de AEMET: «Fuente: AEMET» |
| Idescat | comarca de cada municipio de Cataluña | reutilización citando la fuente: «Fuente: Idescat» |
| Gobierno de Aragón (Aragón Open Data) | comarca de cada municipio de Aragón | CC BY 4.0 |
| Registro de Entidades Locales | comarcas que son entidad local y municipios de las cuadrillas de Álava y de El Bierzo (exportación revisada en `fuentes/`) | reutilización citando la fuente: «Fuente: Registro de Entidades Locales» |
| Dirección General del Catastro | código DGC de cada municipio (cruce con el INE; sin Álava, Gipuzkoa, Navarra ni Bizkaia) | licencia de la DGC: uso de la información transformada citando la fuente; no es «información catastral» ni tiene valor fehaciente |
| Ayuntamiento de Madrid (callejero oficial) | códigos postales del municipio de Madrid, con el número de direcciones | CC BY 4.0: «Ayuntamiento de Madrid» |
| Institut Cartogràfic i Geològic de Catalunya (Adreces) | códigos postales de Cataluña, con el número de direcciones | CC BY 4.0: «Institut Cartogràfic i Geològic de Catalunya (ICGC)» |
| Gobierno de Navarra (IDENA) | códigos postales de Navarra, con el número de direcciones | CC BY 4.0: «Información geográfica propiedad del Gobierno de Navarra.» |
| Eustat / Gobierno Vasco (callejero NORA) | códigos postales del País Vasco, con el número de portales | CC BY 4.0: «Eusko Jaurlaritza / Gobierno Vasco; Eustat; geoEuskadi» |
| Govern de les Illes Balears (IDEIB) | códigos postales de Baleares, con el número de portales | CC BY: «Govern de les Illes Balears, IDEIB» |
| INE (callejero del censo electoral) | códigos postales de toda España, con el número de tramos de calle; entidades de población | CC BY 4.0: «Elaboración propia con datos extraídos del sitio web del INE: www.ine.es» |
| Instituto de Estadística y Cartografía de Andalucía (CDAU) | códigos postales de Andalucía, con el número de portales (contraste) | CC BY 4.0: «Fuente: CDAU (Entidades Locales-Junta de Andalucía- IGN)» |
| Dirección General del Catastro | códigos postales de los municipios de régimen común, con el número de direcciones (de INSPIRE Addresses) | licencia de la DGC: uso de la información transformada citando la fuente y la fecha de acceso (en el manifiesto); no es «información catastral» |
| Instituto Geográfico Nacional | capital de cada municipio, con sus coordenadas y altitud; grafía de los nombres de las entidades de población (`ign`, `ign_lugar`) | CC BY 4.0: «IGR_POBLACIONES 2024 CC-BY 4.0 scne.es» |
| Instituto Geográfico Nacional | código BDDAE y límites municipales (fichero adjunto a cada versión, simplificado) | CC BY 4.0: «Obra derivada de BDLJE Continua CC-BY 4.0 ign.es» |
| Wikidata | nombres por idioma, enlaces, identificadores | CC0 |
| GeoNames (vía Wikidata) | identificador | CC BY 4.0 |
| Listas revisadas a mano (`fuentes/`) | nombres de comunidades, alias, ISO 3166-2, NUTS, elemento de Wikidata de cada isla | MIT |

---

## English

Spanish territories —autonomous communities and cities, provinces, islands, judicial districts,
AEMET warning zones, comarcas and municipalities— and the countries of the world, with all their names (official; in Spanish, Catalan, Galician, Basque,
Aranese and English; aliases), their codes (INE, Catastro, IGN, ISO, NUTS, LAU, Wikidata,
OpenStreetMap, GeoNames…), the capital of each municipality with its coordinates, the municipal
boundaries, the postal codes and the population entities (parishes, nuclei…), rebuilt from official and open sources. It ships a small Python and JavaScript library
to resolve codes, search names, pick the display name for each language and place a point in its
municipality.

Identifiers (`es:municipio:36038`) only change in a major version; new fields and levels come in
minor versions. The design is in [`docs/design.md`](docs/design.md) and what is missing, in the
[«objetivo» issues](https://github.com/alertapublica/territorios-es/issues?q=is%3Aissue+is%3Aopen+label%3Aobjetivo). The [data website](https://alertapublica.github.io/territorios-es/)
describes every file and field in six languages, and its [status page](https://alertapublica.github.io/territorios-es/en/estado/) (also in
[`docs/status.md`](docs/status.md)) shows what is in the data, how much each datum covers, where
everything comes from and how the pieces of the repository relate. Usage, data, tests and
licences are described in the Spanish section above; code and field names are in English. The
code is MIT-licensed; each datum keeps its source's licence. To report a wrong datum, or to ask for
one to be withdrawn, open a [claim issue](https://github.com/alertapublica/territorios-es/issues/new?template=reclamacion.md).
