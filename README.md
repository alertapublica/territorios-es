# territorios-es

*[English below](#english)*

Territorios de España —comunidades y ciudades autónomas, provincias, islas y municipios— y países del
mundo, con todos sus nombres (el oficial; en castellano, catalán, gallego, euskera, aranés e
inglés; y alias), sus códigos (INE, Catastro, IGN, ISO, NUTS, LAU, Wikidata, OpenStreetMap,
GeoNames…), la capital de cada municipio con sus coordenadas y los límites municipales,
regenerables desde las fuentes oficiales y abiertas. Incluye una librería pequeña en
Python y JavaScript para resolver códigos, buscar nombres y elegir el nombre que se muestra en
cada idioma.

Los identificadores (`es:municipio:36038`) solo cambian en una versión mayor; los campos y niveles
nuevos llegan en versiones menores. El planteamiento está en [`docs/diseno.md`](docs/diseno.md).

## Uso

```python
import territorios_es as te

te.resolve("ine:municipio", "36038")["id"]              # 'es:municipio:36038'
te.name("es:provincia:03", "ca")                        # 'Alacant'
te.name("es:autonomia:09", "en")                        # 'Catalonia'
[c["id"] for c in te.search("Ourense", levels=["municipality"])]   # ['es:municipio:32054']
te.relate_name("Ourense")["status"]                     # 'pending': provincia y municipio
te.children("es:isla:formentera")                       # ['es:municipio:07024']: municipios de la isla
te.parse_cadastral_reference("9872023VH5797S0001WX")["valid"]  # True: letras de control correctas
te.relate_cadastral_reference("13096A001001920000YY")["territory"]  # municipio de una parcela rústica
```

```js
import { loadCatalog, relateName, relateCadastralReference } from 'territorios-es';   // en el navegador: createCatalog(datos)
const te = loadCatalog();
te.name('es:municipio:20069', 'eu');                      // 'Donostia'
te.search('Orense', { within: 'es:autonomia:12' });
relateName(te, 'Ourense', { levels: ['municipality'] });  // { status: 'resolved', … }
relateCadastralReference(te, '13096A001001920000YY');     // sin red

import { locateReference } from 'territorios-es/catastro-online';  // con red; también en el navegador
await locateReference(te, '9872023VH5797S0001WX');        // { status: 'resolved', territory: 'es:municipio:13077', … }
```

Funciones: `resolve`, `territory`, `search`, `mentions`, `name`, `children` (en una isla, sus
municipios), `normalize`,
`relate_name` (en JS, `relateName`), `combine`, `parse_cadastral_reference` y
`relate_cadastral_reference` (referencias catastrales, sin red) y `locate` (de un punto a su
municipio). Están descritas en el apartado 6 del diseño.

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
| INE | códigos y nombres oficiales de municipios | reutilización citando la fuente |
| Eurostat | LAU, NUTS 3 de cada municipio (y con él, su isla), población y superficie | CC BY 4.0 |
| Dirección General del Catastro | código DGC de cada municipio (cruce con el INE; sin Álava, Gipuzkoa, Navarra ni Bizkaia) | licencia de la DGC: uso de la información transformada citando la fuente; no es «información catastral» ni tiene valor fehaciente |
| Instituto Geográfico Nacional | capital de cada municipio, con sus coordenadas y altitud | CC BY 4.0: «IGR_POBLACIONES 2024 CC-BY 4.0 scne.es» |
| Instituto Geográfico Nacional | código BDDAE y límites municipales (fichero adjunto a cada versión, simplificado) | CC BY 4.0: «Obra derivada de BDLJE Continua CC-BY 4.0 ign.es» |
| Wikidata | nombres por idioma, enlaces, identificadores | CC0 |
| GeoNames (vía Wikidata) | identificador | CC BY 4.0 |
| Listas revisadas a mano (`fuentes/`) | nombres de comunidades, islas, alias, ISO 3166-2, NUTS | MIT |

---

## English

Spanish territories —autonomous communities and cities, provinces, islands and municipalities— and the
countries of the world, with all their names (official; in Spanish, Catalan, Galician, Basque,
Aranese and English; aliases), their codes (INE, Catastro, IGN, ISO, NUTS, LAU, Wikidata,
OpenStreetMap, GeoNames…), the capital of each municipality with its coordinates and the municipal
boundaries, rebuilt from official and open sources. It ships a small Python and JavaScript library
to resolve codes, search names, pick the display name for each language and place a point in its
municipality.

Identifiers (`es:municipio:36038`) only change in a major version; new fields and levels come in
minor versions. The design is in [`docs/design.md`](docs/design.md). Usage, data, tests and
licences are described in the Spanish section above; code and field names are in English. The
code is MIT-licensed; each datum keeps its source's licence.
