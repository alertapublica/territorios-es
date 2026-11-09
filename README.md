# territorios-es

*[English below](#english)*

Territorios de España —comunidades y ciudades autónomas, provincias y municipios— y países del
mundo, con todos sus nombres (el oficial; en castellano, catalán, gallego, euskera, aranés e
inglés; y alias) y sus códigos (INE, Catastro, ISO, NUTS, LAU, Wikidata, OpenStreetMap,
GeoNames…), regenerables desde las fuentes oficiales y abiertas. Incluye una librería pequeña en
Python y JavaScript para resolver códigos, buscar nombres y elegir el nombre que se muestra en
cada idioma.

**En desarrollo.** El planteamiento está en [`docs/diseno.md`](docs/diseno.md).

## Uso

```python
import territorios_es as te

te.resolve("ine:municipio", "36038")["id"]              # 'es:municipio:36038'
te.name("es:provincia:03", "ca")                        # 'Alacant'
te.name("es:autonomia:09", "en")                        # 'Catalonia'
[c["id"] for c in te.search("Ourense", levels=["municipality"])]   # ['es:municipio:32054']
te.relate_name("Ourense")["status"]                     # 'pending': provincia y municipio
```

```js
import { loadCatalog, relateName } from 'territorios-es';   // en el navegador: createCatalog(datos)
const te = loadCatalog();
te.name('es:municipio:20069', 'eu');                      // 'Donostia'
te.search('Orense', { within: 'es:autonomia:12' });
relateName(te, 'Ourense', { levels: ['municipality'] });  // { status: 'resolved', … }
```

Funciones: `resolve`, `territory`, `search`, `mentions`, `name`, `children`, `normalize`,
`relate_name` (en JS, `relateName`) y `combine`. Están descritas en el apartado 6 del diseño.

Instalación, con la versión fijada:

```sh
pip install "territorios-es @ git+https://github.com/alertapublica/territorios-es@vX.Y.Z"
npm install github:alertapublica/territorios-es#vX.Y.Z
```

## Datos

Los datos están en [`datos/`](datos/), en JSON y CSV, con la URL, la huella SHA-256 y la fecha de
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
| Eurostat | LAU, NUTS 3 de cada municipio, población y superficie | CC BY 4.0 |
| Dirección General del Catastro | código DGC de cada municipio (cruce con el INE; sin Álava, Gipuzkoa, Navarra ni Bizkaia) | licencia de la DGC: uso de la información transformada citando la fuente; no es «información catastral» ni tiene valor fehaciente |
| Wikidata | nombres por idioma, enlaces, identificadores | CC0 |
| GeoNames (vía Wikidata) | identificador | CC BY 4.0 |
| Listas revisadas a mano (`fuentes/`) | nombres de comunidades, alias, ISO 3166-2, NUTS | MIT |

---

## English

Spanish territories —autonomous communities and cities, provinces and municipalities— and the
countries of the world, with all their names (official; in Spanish, Catalan, Galician, Basque,
Aranese and English; aliases) and their codes (INE, Catastro, ISO, NUTS, LAU, Wikidata,
OpenStreetMap, GeoNames…), rebuilt from official and open sources. It ships a small Python and
JavaScript library to resolve codes, search names and pick the display name for each language.

**Work in progress.** The design is in [`docs/design.md`](docs/design.md). Usage, data, tests and
licences are described in the Spanish section above; code and field names are in English. The
code is MIT-licensed; each datum keeps its source's licence.
