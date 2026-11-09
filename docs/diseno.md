# Diseño de territorios-es

Borrador del 9 de noviembre de 2026. Las decisiones ya tomadas están en el apartado
[Decisiones](#12-decisiones); lo que falta, en [Pendiente](#13-pendiente), y lo que hay que
comprobar de cada fuente, en [Por verificar](#14-por-verificar). Hay una versión en inglés en
[`design.md`](design.md).

## 1. Para qué

Muchos proyectos necesitan lo mismo: saber que «Orense», «Ourense» y `32054` hablan del mismo
sitio, pasar de un código a otro y mostrar el nombre correcto en cada idioma. `territorios-es`
reúne todo eso en un solo lugar, donde un territorio se reconoce por cualquiera de sus nombres y
códigos. Sus datos se regeneran desde las fuentes oficiales, y las abiertas (Wikidata,
OpenStreetMap) sirven de apoyo y de contraste. Ofrece tres cosas:

1. **Catálogo**: España, sus comunidades y ciudades autónomas, provincias y municipios, y los
   países del mundo, con su jerarquía, sus nombres (oficial, visible, por idioma y alias) y sus
   códigos (INE, Catastro, ISO, europeos y otros).
2. **Herramientas** en Python y JavaScript: resolver un código, buscar un nombre dentro de un
   ámbito, encontrar menciones en un texto, elegir el nombre que se muestra en cada idioma y
   relacionar referencias con su estado y sus evidencias.
3. **Datos abiertos**: el cruce de códigos y nombres en CSV y JSON, con la fuente, la fecha y la
   licencia de cada dato, y una web que los explica en seis idiomas.

No incluye lo que solo tiene sentido en un proyecto concreto, como «Ámbito nacional» o «Varias
comunidades» en empleo-publico-abierto. Cada proyecto lo construye encima.

## 2. Punto de partida

El núcleo sale del módulo de territorios de [Voceiro](https://github.com/thendabs1/voceiro)
(`shared/territorios/`). Es lo más trabajado que tenemos:

- el diccionario de municipios del INE de 2026, con dígito de control, URL y huella SHA-256;
- `resolver(sistema, codigo)` en Python y JavaScript, con casos de prueba comunes a los dos;
- los límites municipales del IGN de las 52 provincias y el paso de un punto a su municipio, con
  un margen de 50 m;
- el contrato del relacionador: estados (resuelto, pendiente, conflicto), motivo y evidencias.

Le faltan las coordenadas y la población de una fuente oficial, los nombres en otros idiomas y
los códigos que no son del INE.

empleo-publico-abierto tiene su propia lista de municipios y su lectura de texto libre
(`empleo/regions.py`): da un municipio solo cuando no hay ambigüedad y, si no, la provincia o la
comunidad. Sus alias («Orense», «Lérida») están escritos dentro del código.

Hoy la tabla de comunidades y provincias, la lista de municipios y las reglas que pasan
«Coruña, A» a «A Coruña» están repetidas en varios proyectos, y cada uno usa su propio formato de
identificador. Esta librería sustituye esas copias.

Los proyectos parecidos que ya existen, en España y en la UE, se repasan en el apartado
[Proyectos parecidos](#11-proyectos-parecidos).

## 3. Principios

- **Todo se puede regenerar.** Cada fichero de datos indica la URL de la que sale, su huella
  SHA-256 y la fecha de referencia. El generador se ejecuta en GitHub Actions, no en local.
- **Se conserva el texto literal de la fuente.** Las formas que derivamos nosotros («A Coruña»,
  los slugs) se guardan aparte y marcadas como derivadas.
- **Un nombre no basta para identificar un territorio.** `search` devuelve candidatos con el
  motivo de cada uno, y es el consumidor quien decide: empleo, solo si no hay ambigüedad; otro
  proyecto, dentro de la provincia que ya conoce.
- **Los códigos son siempre cadenas de texto.** No se rellenan ceros perdidos ni se deduce un
  código a partir de otro.
- **Los identificadores son estables.** Un municipio que nace de una fusión recibe un
  identificador nuevo y un enlace de sucesión, y el antiguo no se reutiliza.
- **No se usa la red al ejecutar.** El catálogo viaja con el paquete; los límites, por su tamaño,
  se descargan aparte cuando hacen falta.
- **Todo es determinista, sin IA.** La búsqueda aproximada es un añadido opcional.
- **Se usan todas las fuentes que sirvan, relacionadas con su procedencia** (ver el apartado 5).

## 4. Datos

### 4.1 Niveles

Primera versión:

- **España**: 19 comunidades y ciudades autónomas, 52 provincias y 8.132 municipios (los del INE
  a 1 de enero de 2026).
- **Países**: la lista ISO 3166-1 completa, con su nombre en cada idioma y si pertenecen a la UE
  o al Espacio Económico Europeo. Sirve, por ejemplo, para el requisito de nacionalidad de las
  convocatorias.

Segunda versión: islas (cabildos y consells), comarcas oficiales y partidos judiciales.

Más adelante: entidades de población del Nomenclátor del INE (núcleos, y parroquias en Galicia y
Asturias), que son decenas de miles.

### 4.2 Códigos

| Código | Niveles | Fuente | Notas |
|---|---|---|---|
| INE | comunidad (2 cifras), provincia (2), municipio (5 + dígito de control) | Diccionario anual del INE | Oficial; es la base de la identidad. |
| ISO 3166-1 | país (alfa-2, alfa-3, numérico) | Wikidata, contrastado con la ONU | |
| ISO 3166-2 | comunidad y provincia (`ES-GA`, `ES-C`) | Lista revisada a mano, contrastada con Wikidata | |
| NUTS 2024 | NUTS 1 (grupos de comunidades), NUTS 2 (comunidad), NUTS 3 (provincia; islas en Baleares y Canarias) | Eurostat | Para cruzar con estadísticas europeas. |
| LAU | municipio | Tabla anual LAU de Eurostat | En España es el código INE de 5 cifras (comprobado en los 8.132 municipios); ver §4.5 para lo que trae además. |
| DGC (Catastro) | municipio | Servicio OVC del Catastro | Navarra y el País Vasco tienen catastro foral y no tienen código DGC: queda vacío, documentado. Segunda versión. |
| INSPIRE | municipio | IGN (unidades administrativas) | Identificador europeo de la unidad administrativa. Llega con los límites. |
| Wikidata | todos | SPARQL a partir del código INE | CC0. Aporta nombres por idioma, enlaces a Wikipedia y otros identificadores. |
| OpenStreetMap | todos | Identificador de la relación, desde Wikidata y contrastado con OSM | El identificador de Wikidata es CC0; lo que se copie de OSM va aparte con ODbL (§7). |
| GeoNames | todos | Desde Wikidata | CC BY 4.0. Muy usado por otras herramientas. |
| Código postal | municipio (relación de muchos a muchos) | Por decidir: el callejero del censo electoral del INE, si se confirma que trae el código postal y se puede reutilizar | Útil para leer direcciones. CartoCiudad no sirve: los códigos postales son de Correos y su convenio con el CNIG solo permite consultarlos, no descargarlos. |
| datos.gob.es | comunidad y provincia | URIs de la Norma Técnica de reutilización (anexo V) | Identificador adicional para enlazar con el catálogo nacional de datos abiertos; no hay URIs de municipio. |
| EU Vocabularies (ATU) | por confirmar | Oficina de Publicaciones de la UE | Lista de unidades administrativas de los Estados miembros con URIs; se enlaza si llega a municipios. |

DIR3 y los demás códigos de organismos no van aquí: identifican al ayuntamiento, no al territorio
(ver §10).

### 4.3 Nombres e idiomas

Idiomas, con su código BCP 47:

| Idioma | Código | Situación |
|---|---|---|
| castellano | `es` | oficial en toda España |
| catalán / valenciano | `ca` | cooficial en Cataluña, Illes Balears y la Comunitat Valenciana. Si algún día hace falta una interfaz propia en valenciano, su código es `ca-ES-valencia`. |
| gallego | `gl` | cooficial en Galicia |
| euskera | `eu` | cooficial en el País Vasco y en la zona vascófona de Navarra |
| aranés (occitano) | `oc` | oficial en Cataluña; nombre oficial de los nueve municipios del Arán. Las etiquetas de Wikidata en `oc` son de occitano general, no siempre de la norma aranesa. |
| inglés | `en` | no oficial; para el público internacional |
| asturiano, aragonés | `ast`, `an` | protegidos, no oficiales. Se guardan en los datos, marcados así, pero no se usan en la interfaz. |

Campos de nombre de cada territorio:

| Campo | Ejemplo | Origen |
|---|---|---|
| `official` | «Coruña, A», «Alicante/Alacant», «Balears, Illes» | INE, literal |
| `display` | «A Coruña», «Alicante/Alacant», «Illes Balears» | Derivado: el artículo pasa delante. Se puede corregir a mano. |
| `parts` | `{"es": "Alicante", "ca": "Alacant"}` | Solo en los nombres oficiales bilingües. El idioma de cada parte sale de una lista revisada a mano y contrastada con Wikidata. |
| `lang` | `{"en": "Catalonia", "eu": "Katalunia"}` | Nombre habitual en cada idioma. En las comunidades, lista revisada a mano; en provincias y municipios, Wikidata, solo si difiere del oficial. |
| `short` | «Baleares», «Navarra» | Comunidades y provincias; lista revisada a mano, por idioma. |
| `aliases` | «Orense», «Lérida», «La Coruña», «Guipúzcoa» | Lista revisada a mano, con su idioma y su tipo (exónimo, histórico, abreviatura). |
| `slug` | `a-coruna` | Derivado |

Los nombres oficiales del INE son ya los de la lengua propia cuando la ley lo dice: en Galicia,
Cataluña e Illes Balears solo la forma gallega o catalana es oficial. «Gerona» o «Sanjenjo» no son
nombres oficiales, sino alias.

### 4.4 Qué nombre se muestra en cada idioma

Los datos guardan todos los nombres; esta es la regla por defecto de `name(id, lang)`:

- **Comunidades**: el nombre en el idioma de la página («Catalonia», «Katalunia», «Cataluña»).
- **Provincias y municipios**: el oficial. Si es bilingüe, solo la parte del idioma de la página
  («Alacant» en catalán, «San Sebastián» en castellano) y el nombre completo en los demás.
  En castellano se muestra «Girona», no «Gerona».
- Los nombres habituales en otros idiomas («Gerona», «Seville», «Saragossa») sirven para buscar y
  quedan a mano para quien quiera mostrarlos.

### 4.5 Geografía, población y clasificaciones

- **Punto de referencia del municipio** (su capital): Nomenclátor Geográfico de Municipios y
  Entidades de Población del IGN/CNIG, contrastado con Wikidata y OSM.
- **Límites municipales**: IGN, unidades administrativas INSPIRE (BDDAE), CC BY 4.0. Ocupan unos
  33 MB comprimidos, así que no van en git: se publican como ficheros de cada versión en GitHub
  Releases, con su huella en un manifiesto, y se descargan por provincia la primera vez que hacen
  falta.
- **Mapas simplificados** (TopoJSON de comunidades, provincias y municipios) para dibujar en una
  web, hechos por nosotros a partir de los del IGN.
- **Población** del padrón del INE y **superficie**: sirven para ordenar candidatos.
- **De la tabla LAU de Eurostat**, por municipio: grado de
  urbanización (ciudad, intermedio, rural), si es costero y a qué ciudad o área urbana funcional
  pertenece. Por ejemplo, permiten
  filtrar ofertas en el medio rural con un criterio oficial.
- **Tipologías europeas por provincia** (NUTS 3): urbana o rural, metropolitana, de montaña,
  costera, insular y fronteriza.
- **Huso horario**: `Europe/Madrid`; `Atlantic/Canary` en Canarias; `Africa/Ceuta` en Ceuta y
  Melilla.
- **Enlaces a Wikipedia** en cada idioma, desde Wikidata.

### 4.6 Cambios en el tiempo

El INE publica cada año un diccionario nuevo y la relación de variaciones (altas, bajas, fusiones
y cambios de nombre). La primera versión es una foto a 1 de enero de 2026. Después:

- un cambio de nombre conserva el identificador y guarda el nombre anterior como alias con fechas;
- una fusión o segregación crea identidades nuevas y enlaces de sucesión;
- un workflow mensual comprueba si las fuentes han cambiado y, si es así, abre una PR con el
  resumen: municipios nuevos o dados de baja y cambios de nombre o de código.

## 5. Cómo se relacionan las fuentes

- **Manda el dueño de cada dato**: el INE en los códigos y nombres oficiales, el IGN en las
  coordenadas y los límites, Eurostat en NUTS y LAU, ISO en sus códigos. Wikidata y OSM completan
  lo que la fuente oficial no da (nombres en otros idiomas, enlaces) y sirven para contrastar.
- **Cada enlace guarda su procedencia**: la fuente, cómo se hizo (por código, por nombre o por
  posición) y la fecha de la fuente.
- **Las diferencias no se resuelven en silencio.** El generador escribe un informe de
  discrepancias y Actions lo publica en un issue que se actualiza en cada ejecución, como el
  informe de áreas de empleo. Se corrigen a mano: en `fuentes/` si el error es nuestro, o en
  Wikidata y OSM si es suyo.
- **Las listas revisadas a mano** (`fuentes/`) son pequeñas y dicen de dónde salió cada valor. El
  generador las contrasta con las fuentes automáticas.

## 6. Interfaz

La misma en Python y en JavaScript, en inglés, con unos mismos casos de prueba para los dos
lenguajes. Los campos de los datos también van en inglés. En JavaScript, los nombres compuestos van
en camelCase (`relateName`) y las opciones en un objeto (`search(text, { within, levels })`).

| Función | Qué hace |
|---|---|
| `resolve(system, code)` | De un código a un territorio con sus ancestros, o `None`/`null` si no existe. Sistemas: `ine:autonomia`, `ine:provincia`, `ine:municipio`, `ine:municipio:dc`, `iso3166-1:alpha2`, `iso3166-1:alpha3`, `iso3166-2`, `nuts`, `lau`, `wikidata`, `osm:relation`, `geonames`… |
| `territory(id)` | Ficha completa: nombres, códigos, padre y ancestros. |
| `search(text, within, levels)` | Candidatos para un texto, cada uno con su motivo (`official`, `part`, `lang`, `alias` o `variant`) y en un orden fijo. `within` limita la búsqueda a un ámbito, por ejemplo a una provincia. |
| `mentions(text, levels)` | Territorios nombrados dentro de un texto más largo («Moncada (Valencia)»), sin solaparse y empezando por el nombre más largo. Por defecto, solo comunidades y provincias. |
| `normalize(text)` | La normalización común: sin tildes ni mayúsculas, «l·l» como «ll», el artículo delante y los guiones como espacios. |
| `name(id, lang, short)` | El nombre que se muestra, según §4.4. |
| `relate_name(text, within, levels)` | Una relación con estado: resuelto (un candidato), pendiente (ninguno o varios) o conflicto. |
| `combine(relations)` | Une varias relaciones del mismo objeto: si coinciden, resuelto; si se contradicen, conflicto. |
| `locate(lon, lat)` | Segunda versión. El paso de punto a municipio de Voceiro: resuelto, pendiente (a menos de 50 m de otro municipio) o conflicto. Nunca devuelve «el más cercano». |

La búsqueda aproximada (`fuzzy=True`, con una dependencia opcional) queda para más adelante.

**Identificadores**: los de Voceiro, que ya están publicados: `pais:ES`, `es:autonomia:12`,
`es:provincia:36`, `es:municipio:36038`. Son etiquetas, así que no importa que estén en castellano.
Cada consumidor puede seguir dando sus códigos (empleo publica el código INE sin prefijo).

**Relacionador**: aquí va el modelo genérico de relación, con estado, candidatos, motivo y
evidencias. Cada proyecto conserva solo lo suyo (por ejemplo, la cobertura de un medio).

## 7. Paquete, versiones y licencias

- **Estructura**:
  - `datos/`: ficheros generados (JSON y CSV) y su manifiesto;
  - `fuentes/`: lo revisado a mano (nombres por idioma, alias, códigos ISO y NUTS, idiomas de los
    nombres bilingües, URL de cada fuente);
  - `python/` y `js/`: dos lectores pequeños de los mismos datos;
  - `generador/`: descargas, contraste e informe de discrepancias;
  - `web/`: la web de datos;
  - `pruebas/`: casos comunes a Python y JS.
- **Instalación**:
  - Python: `pip install "territorios-es @ git+https://github.com/alertapublica/territorios-es@vX.Y.Z"`.
  - JS: `npm install github:alertapublica/territorios-es#vX.Y.Z`.
- **Versiones** (semver): parche, correcciones; menor, datos del año nuevo y códigos o campos
  nuevos; mayor, cambiar identificadores o quitar campos. Cada consumidor fija la versión exacta.
- **Licencias**:
  - el código, MIT;
  - cada dato conserva la licencia de su fuente: INE y Catastro (reutilización citando la
    fuente), IGN/CNIG (CC BY 4.0), Eurostat (CC BY 4.0), GeoNames (CC BY 4.0), Wikidata (CC0);
  - lo que se copie de OpenStreetMap va en ficheros aparte con ODbL, porque esa licencia obliga a
    publicar con ODbL cualquier base de datos que mezcle sus datos.

  El README tiene la tabla de atribuciones.

## 8. Web de datos

Se publica en GitHub Pages desde la primera versión: los ficheros, la descripción de cada campo y
las atribuciones, en castellano, catalán, gallego, euskera, aranés e inglés. Crece con cada cruce
nuevo. Las traducciones las redactamos nosotros al escribirlas (no se generan en ejecución) y
quedan marcadas como pendientes de revisión hasta que alguien con dominio del idioma las revise.

## 9. Preparado para la UE

La primera versión es solo España, pero nada impide ampliarla:

- el código no supone España: las reglas de nombres (artículos, separador bilingüe) son datos por
  idioma, no código;
- los códigos europeos (NUTS, LAU) ya están en el modelo, y el lector de la tabla LAU recibe el
  país como parámetro;
- los identificadores llevan el país delante. Para otros países se propone usar los europeos
  (`eu:nuts:PT11`, `pt:lau:1601`), que habrá que decidir cuando toque;
- los datos de otro país irían en su propia carpeta o en un repo hermano con este mismo código.

## 10. Adopción y lo que podemos aportar

- **empleo-publico-abierto**, el primero: sustituir `municipios.csv` y las tablas de `regions.py`.
  Prueba: `api/ofertas.json` idéntico en `ccaa`, `provincia` y `municipio` con los mismos datos.
  Después: coordenadas en la API, un mapa de ofertas, avisos «a menos de X km de…» y páginas por
  provincia (también para la web de Tragsa).
- **Otros proyectos** adoptan la librería en su propio repo, a su ritmo.
- **Organismos** (ayuntamientos, diputaciones, mancomunidades, DIR3, sede electrónica, tablón y
  página de empleo): en un repo hermano, más adelante, enlazado con estos identificadores. Cambian
  más a menudo y tienen otras fuentes, como el Registro de Entidades Locales.
- **Días inhábiles por territorio**, para calcular plazos en días hábiles: otro conjunto hermano.
- **Aviso de cambios**: una PR automática cuando el INE publique un municipio nuevo o un cambio de
  nombre.

## 11. Proyectos parecidos

Revisión del 9 de noviembre de 2026. Ninguno reúne todo lo que buscamos (códigos oficiales y
europeos, nombres en las lenguas cooficiales, herramientas en Python y JS y regeneración desde la
fuente), pero varios sirven para contrastar o como inspiración:

| Proyecto | Qué aporta | Uso previsto |
|---|---|---|
| [codeforspain/ds-organizacion-administrativa](https://github.com/codeforspain/ds-organizacion-administrativa) | Comunidades, provincias, municipios actuales e históricos e islas con códigos INE, en CSV y JSON; actualizado con el INE de 2026. | Contraste, sobre todo para islas y municipios históricos. Licencia por confirmar. |
| [inigoflores/ds-municipios-catastro-es](https://github.com/inigoflores/ds-municipios-catastro-es) | Cruce de códigos INE y Catastro sacado del servicio OVC. | Contraste del cruce con el Catastro que haremos nosotros. |
| EU Vocabularies: tablas de autoridad ATU y Country (Oficina de Publicaciones) | Unidades administrativas de los Estados miembros, actuales y pasadas, con URIs estables. | Contraste y enlace, si su cobertura de España llega a municipios. |
| Eurostat GISCO | Tablas LAU–NUTS y límites. | Las tablas y los códigos, sí. Los límites no: su licencia excluye el uso comercial. |
| EuroGeographics, Open Maps For Europe | Límites europeos (EuroBoundaryMap 2025, con NUTS 2024) con licencia abierta propia. | Contraste de límites y nombres, tras leer su especificación. |
| Unicode CLDR y Debian iso-codes | Nombres traducidos de países y de subdivisiones ISO 3166-2. | Contraste de los nombres de países y comunidades; licencias por confirmar. |
| mapSpain y giscoR (paquetes de R) | Mapas de España y diccionarios de códigos y nombres. | Inspiración. |
| datos.gob.es | URIs de comunidades y provincias. | Identificador adicional (§4.2). |
| Base de datos general de entidades locales (Ministerio de Hacienda) | Entidades locales con código INE y NIF. | Para el repo hermano de organismos. |

Quedan por revisar: Who's On First, geoBoundaries, Overture Maps, es-atlas, la API JSON del INE y
el Nomenclátor Geográfico Básico (nombres de lugar por idioma).

## 12. Decisiones

Tomadas con el responsable del proyecto el 9 de noviembre de 2026:

1. El documento no describe proyectos ajenos a esta librería.
2. Idiomas: todos los oficiales de España e inglés; asturiano y aragonés en los datos, sin
   interfaz.
3. Se traduce todo: datos, web y documentación. El README y el diseño van primero en castellano e
   inglés; la documentación larga en los demás idiomas, después.
4. Qué nombre se muestra: la regla de §4.4.
5. Identificadores de Voceiro.
6. Código, campos y documentación técnica en inglés.
7. Las fuentes se relacionan como dice el apartado 5.
8. OpenStreetMap como apoyo, y Open Maps For Europe (EuroGeographics) también, para contrastar.
9. Códigos europeos de los territorios españoles, con todo preparado para ampliar a la UE.
10. Primera versión: países, huso horario, enlaces a Wikipedia y códigos postales (estos, si se
    confirma una fuente reutilizable, ver §4.2). Segunda: islas, comarcas y partidos judiciales.
    Más adelante: entidades de población y días inhábiles.
11. El modelo genérico de relación (estados y evidencias) vive aquí.
12. Los organismos, en un repo hermano.
13. La web de datos se publica con la primera versión.

## 13. Pendiente

- Traducir este documento y el README al catalán, gallego, euskera y aranés.
- Revisar las traducciones de la web y de los nombres de comunidades (marcadas como pendientes).
- Revisar los proyectos que quedan en el apartado 11.
- Revisar el informe de discrepancias de la primera generación: etiquetas de Wikidata que son el
  nombre de otro municipio, identificadores repetidos y municipios antiguos con código INE en
  Wikidata; corregir en Wikidata lo que sea error suyo.
- Activar GitHub Pages en el repositorio y permitir que Actions abra PR (ajustes del repositorio).
- Segunda versión: DGC, coordenadas y límites del IGN, `locate`, mapas simplificados, islas,
  comarcas, partidos judiciales, Open Maps For Europe.
- Más adelante: entidades de población, variaciones históricas del INE, búsqueda aproximada.

## 14. Por verificar

Antes de usar cada fuente hay que comprobar su URL, su formato y su licencia. Lo ya comprobado el
9 de noviembre de 2026:

- **Tabla LAU de Eurostat**: la validada es `EU-27-LAU-2024-NUTS-2024.xlsx` y hay una de 2025
  «parcialmente validada» ([página](https://ec.europa.eu/eurostat/web/nuts/local-administrative-units)).
  Abierta por el generador en Actions: trae NUTS 3, código LAU (en España, el del INE de 5 cifras,
  igual en los 8.132 municipios de 2026), nombres, población, superficie, grado de urbanización,
  costa, ciudad y área urbana funcional.
- **NUTS 2024**: en vigor desde el 1 de enero de 2024 (Reglamento Delegado (UE) 2023/674); España
  tiene 7 NUTS 1, 19 NUTS 2 y 59 NUTS 3. Falta confirmar si hay cambios respecto a NUTS 2021.
- **Wikidata**: la propiedad P772 (código INE) admite 2 cifras (provincia), 5 (municipio) y 11
  (entidad de población), así que hay que filtrar por longitud. P782 (LAU) lleva el prefijo del
  país. No hay propiedad para el código del Catastro.
- **Límites de GISCO**: excluyen el uso comercial y llevan «© EuroGeographics». Descartados como
  fuente.
- **CartoCiudad**: no permite descargar los códigos postales (convenio con Correos,
  BOE-A-2023-11522). Descartado para los códigos postales.
- **Nomenclátor Geográfico de Municipios y Entidades de Población (CNIG)**: se descarga en formato
  Access (`.mdb`) y trae nombres, coordenadas y población. Falta confirmar la licencia y si trae
  nombres por idioma.

Por comprobar:

- servicio OVC del Catastro (`ConsultaMunicipioCodigos`): URL exacta y qué devuelve para territorio
  común y foral;
- callejero del censo electoral del INE: si trae el código postal y se puede reutilizar;
- INE: fichero de cifras oficiales de población por municipio (a 1 de enero de 2025) y
  condiciones de reutilización;
- límites del IGN: si se pueden redistribuir como ficheros de versión en GitHub Releases (CC BY
  4.0 lo permite citando la fuente);
- licencias de codeforspain, CLDR, iso-codes, EU Vocabularies y Open Maps For Europe.
