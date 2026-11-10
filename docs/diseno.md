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
  se descargan aparte cuando hacen falta. La única excepción es el módulo opcional
  `catastro_online`, que solo llama al Catastro cuando se le pide (§6).
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

Segunda versión: islas (cabildos y consells), comarcas oficiales y partidos judiciales. Las islas
ya están (versión 0.3):

- **Islas**: las 11 que tienen cabildo (Canarias) o consell insular (Illes Balears), con nivel
  `island` e identificador con el código de isla del INE (`es:isla:384` es Tenerife; `es:isla:072`,
  Ibiza). Su padre es la provincia. Los municipios no cambian de padre: llevan además el campo
  `island`. El código, el nombre oficial y los municipios de cada isla salen de la tabla de islas
  del INE (`26codislas.xlsx`); `fuentes/islas.csv` añade el elemento de Wikidata y el NUTS 3, que
  solo sirve para contrastar (Eivissa y Formentera comparten la ES531). Las islas menores van con
  el municipio al que pertenecen (La Graciosa con Teguise, en Lanzarote; Cabrera con Palma, en
  Mallorca). El nombre es el oficial del INE (§4.4) y los demás salen de Wikidata.

Más adelante: entidades de población del Nomenclátor del INE (núcleos, y parroquias en Galicia y
Asturias), que son decenas de miles.

### 4.2 Códigos

| Código | Niveles | Fuente | Notas |
|---|---|---|---|
| INE | comunidad (2 cifras), provincia (2), isla (3), municipio (5 + dígito de control) | Diccionario anual y tabla de islas del INE | Oficial; es la base de la identidad. |
| ISO 3166-1 | país (alfa-2, alfa-3, numérico) | Wikidata, contrastado con la ONU | |
| ISO 3166-2 | comunidad y provincia (`ES-GA`, `ES-C`) | Lista revisada a mano, contrastada con Wikidata | |
| NUTS 2024 | NUTS 1 (grupos de comunidades), NUTS 2 (comunidad), NUTS 3 (provincia; islas en Baleares y Canarias) | Eurostat | Para cruzar con estadísticas europeas. |
| LAU | municipio | Tabla anual LAU de Eurostat | En España es el código INE de 5 cifras (comprobado en los 8.132 municipios); ver §4.5 para lo que trae además. |
| DGC (Catastro) | municipio (`dgc:municipio`, 5 cifras: delegación 2 + municipio 3) | Servicios web libres del Catastro (`OVCCallejero`, `ConsultaProvincia` y `ConsultaMunicipio`), que dan el código DGC y el del INE de cada municipio | Distinto del INE en muchos municipios (A Coruña: INE `15030`, DGC `15900`). El enlace es por código, no por nombre; el nombre solo se contrasta. Álava, Gipuzkoa, Navarra y Bizkaia tienen catastro foral y quedan sin código DGC. |
| BDDAE (INSPIRE) | municipio (`ign:bddae`, 11 cifras: 34 + comunidad 2 + provincia 2 + INE 5) | Límites del IGN (BDLJE) | Código de la unidad administrativa del IGN y `localId` de su identificador INSPIRE (espacio de nombres `ES.IGN.BDDAE`). Se enlaza si coinciden el código INE, la provincia y la comunidad. |
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
- **Provincias, islas y municipios**: el oficial. Si es bilingüe, solo la parte del idioma de la página
  («Alacant» en catalán, «San Sebastián» en castellano) y el nombre completo en los demás.
  En castellano se muestra «Girona», no «Gerona».
- Los nombres habituales en otros idiomas («Gerona», «Seville», «Saragossa») sirven para buscar y
  quedan a mano para quien quiera mostrarlos.

### 4.5 Geografía, población y clasificaciones

- **Punto de referencia del municipio** (su capital): el núcleo de población que el IGN marca como
  capital del municipio en su API de entidades (colección `nuc`, producto IGR Poblaciones, CC BY
  4.0), con longitud, latitud y altitud. Algunas capitales no son núcleos para el INE: están en la
  colección `opob` del mismo producto, de la que se leen solo las marcadas como capital municipal. Se contrasta con los límites: una capital fuera de su
  término va al informe. El Nomenclátor de Municipios y Entidades de Población traería lo mismo,
  pero su descarga exige un formulario con firma del navegador; si el CNIG da un enlace directo,
  se puede cambiar de fuente.
- **Límites municipales**: IGN, Base de Datos de Límites Jurisdiccionales (BDLJE), CC BY 4.0. El
  zip pesa 66 MB y los municipios, 145 MB en GML, así que no van en git ni en el paquete: cada
  versión de GitHub lleva adjunto `limites-municipios.geojson.gz`, simplificado a 5 m (muy por
  debajo de la incertidumbre de unos 40 m de los propios límites) y con nuestros identificadores.
  Incluye las zonas comunes que no son de ningún municipio (comunidades jurisdiccionales), sin
  identificador.
- **Mapas simplificados** (TopoJSON de comunidades, provincias y municipios) para dibujar en una
  web, hechos por nosotros a partir de los del IGN.
- **Población oficial** del INE (padrón a 1 de enero) de provincias y municipios, de su API JSON:
  una tabla por provincia con su total y el de cada municipio. Se comprueba que los municipios
  suman el total de su provincia. Las tablas del INE de comunidades e islas acaban en 2021; su
  población sería la suma de sus provincias o municipios. Con la **superficie** de la tabla LAU,
  sirven para ordenar candidatos.
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
y cambios de nombre), y durante el año, los cambios que se van anotando en el Registro de
Entidades Locales. Los datos parten del diccionario a 1 de enero de 2026 y aplican los cambios de
nombre anotados desde entonces: el nombre nuevo pasa a ser el oficial y el anterior queda como
alias (`former_official`, con la fecha de la resolución en `until`). Las altas y bajas del año van
al informe y entran con el diccionario siguiente. Después:

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
| `resolve(system, code)` | De un código a un territorio con sus ancestros, o `None`/`null` si no existe. Sistemas: `ine:autonomia`, `ine:provincia`, `ine:municipio`, `ine:municipio:dc`, `dgc:municipio`, `iso3166-1:alpha2`, `iso3166-1:alpha3`, `iso3166-2`, `nuts`, `lau`, `wikidata`, `osm:relation`, `geonames`… |
| `territory(id)` | Ficha completa: nombres, códigos, padre y ancestros. |
| `search(text, within, levels)` | Candidatos para un texto, cada uno con su motivo (`official`, `part`, `lang`, `alias` o `variant`) y en un orden fijo. `within` limita la búsqueda a un ámbito, por ejemplo a una provincia o a una isla. |
| `children(id)` | Los territorios cuyo padre es este; en una isla, sus municipios. Los de una provincia de Baleares o Canarias incluyen sus islas y sus municipios. |
| `mentions(text, levels)` | Territorios nombrados dentro de un texto más largo («Moncada (Valencia)»), sin solaparse y empezando por el nombre más largo. Si el nombre completo no está en el catálogo, puede dar otro más corto contenido en él («Perales de Alfambra» → Alfambra). Por defecto, solo comunidades y provincias. |
| `normalize(text)` | La normalización común: sin tildes ni mayúsculas, «l·l» como «ll», el artículo delante y los guiones como espacios. |
| `name(id, lang, short)` | El nombre que se muestra, según §4.4. |
| `relate_name(text, within, levels)` | Una relación con estado: resuelto (un candidato), pendiente (ninguno o varios) o conflicto. |
| `combine(relations)` | Une varias relaciones del mismo objeto: si coinciden, resuelto; si se contradicen, conflicto. |
| `parse_cadastral_reference(text)` | Partes de una referencia catastral de 14, 18 o 20 caracteres: parcela, tipo (rústica o urbana), cargo, letras de control y si son correctas, y, si es rústica, el código DGC del municipio. Sin red. |
| `relate_cadastral_reference(text)` | El municipio de una referencia catastral: resuelto si es rústica y su código DGC está en el catálogo; pendiente si es urbana (no lleva el municipio), si las letras de control no cuadran o si el código no se conoce. |
| `locate(lon, lat, limits)` | El paso de punto a municipio de Voceiro, con el fichero de límites de la versión (`load_limits`; en JS, `loadLimits` en Node o `createLimits` en el navegador): resuelto dentro de un municipio y a más de 50 m de cualquier otro; pendiente cerca de un límite, en una zona común o fuera de todos (el mar, el extranjero); conflicto si cae en dos. Nunca devuelve «el más cercano». |

La búsqueda aproximada (`fuzzy=True`, con una dependencia opcional) queda para más adelante.

El resto de la librería no llama nunca al Catastro. Para situar una referencia urbana o unas
coordenadas está el módulo aparte y opcional `catastro_online` (en JS, la subruta
`territorios-es/catastro-online`, asíncrona, que funciona también en el navegador porque el
Catastro responde con `Access-Control-Allow-Origin: *`). Usa los servicios libres del Catastro y
no guarda nada:

| Función | Qué hace |
|---|---|
| `locate_reference(text)` | El municipio de una referencia catastral, urbana o rústica, según `Consulta_DNPRC` (una petición). En una rústica se contrasta con la lectura sin red: si no coinciden, conflicto. |
| `locate_point(lon, lat, srs)` | La parcela que hay en un punto (`Consulta_RCCOOR`) y su municipio (`Consulta_DNPRC`): dos peticiones. Pendiente si no hay parcela (el mar o los territorios forales). La parcela queda en la evidencia. |

Las dos devuelven una relación con estado y evidencias, como las demás, y aceptan un `fetch`
propio (para pruebas, caché o pausas). Un error de red o una respuesta ilegible lanza
`CatastroError`. No conviene usarlas en bucle sin pausa.

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
  - cada dato conserva la licencia de su fuente: INE (CC BY 4.0), IGN/CNIG
    (CC BY 4.0), Eurostat (CC BY 4.0), GeoNames (CC BY 4.0), Wikidata (CC0);
  - IGN: la licencia (Orden FOM/2807/2015) pide citar cada producto con la fórmula de la tabla del
    Sistema Cartográfico Nacional: «IGR_POBLACIONES 2024 CC-BY 4.0 scne.es» para las capitales y,
    como los límites se simplifican, «Obra derivada de BDLJE Continua CC-BY 4.0 ign.es», que va
    también dentro del fichero de límites (la licencia la pide en los metadatos);
  - Catastro: su licencia (julio de 2016) permite el uso público y comercial solo de la
    información transformada y prohíbe difundir la original o presentarla como «información
    catastral». Publicamos el cruce de códigos con nuestros identificadores, citando la fuente; las
    respuestas originales se quedan en la caché de Actions y nunca entran en el repo (las pruebas
    usan respuestas inventadas con la misma forma);
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
| [codeforspain/ds-organizacion-administrativa](https://github.com/codeforspain/ds-organizacion-administrativa) | Comunidades, provincias, municipios actuales e históricos (diccionarios del INE desde 2004) e islas, en CSV y JSON. | Solo contraste: el repositorio no tiene licencia. El 10 de noviembre de 2026 coincidía con nuestros datos en los 8.132 municipios y las 52 provincias. Sus fuentes son las del INE, que leemos directamente. |
| [inigoflores/ds-municipios-catastro-es](https://github.com/inigoflores/ds-municipios-catastro-es) | Cruce de códigos INE y Catastro sacado del servicio OVC. | Contraste del cruce con el Catastro que haremos nosotros. |
| EU Vocabularies: tablas de autoridad ATU y Country (Oficina de Publicaciones) | Unidades administrativas de los Estados miembros, actuales y pasadas, con URIs estables. | Contraste y enlace, si su cobertura de España llega a municipios. |
| Eurostat GISCO | Tablas LAU–NUTS y límites. | Las tablas y los códigos, sí. Los límites no: su licencia excluye el uso comercial. |
| EuroGeographics, Open Maps For Europe | Límites europeos. | Descartado: la licencia es propia de EuroGeographics, EuroBoundaryMap no es abierto y los datos de España salen del IGN, que usamos directamente. |
| Unicode CLDR y Debian iso-codes | Nombres traducidos de países y de subdivisiones ISO 3166-2. | Candidato para los nombres de países por idioma (hoy, de Wikidata); licencia de Unicode para CLDR. |
| mapSpain y giscoR (paquetes de R) | Mapas de España y diccionarios de códigos y nombres. | Inspiración. |
| datos.gob.es | URIs de comunidades y provincias. | Identificador adicional (§4.2). |
| Base de datos general de entidades locales (Ministerio de Hacienda) | Entidades locales con código INE y NIF. | Para el repo hermano de organismos. |

Revisados el 10 de noviembre de 2026:

- Who's On First, geoBoundaries y Overture Maps: derivan de OpenStreetMap o de las fuentes
  oficiales que ya usamos, con licencias mezcladas. No aportan nada.
- es-atlas: TopoJSON hecho con los ficheros del IGN, como nuestros límites.
- API JSON del INE (`servicios.ine.es/wstempus`): da, por ejemplo, la población oficial de cada
  municipio con su código, en una tabla por provincia. Se usa para la población (§4.5).
- Nomenclátor Geográfico Básico (colección `namedplace` de la API del IGN): 1,19 millones de nombres
  de lugar, sin indicar el idioma. No sirve para los nombres por idioma.

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
- Revisar el informe de discrepancias de la primera generación: etiquetas de Wikidata que son el
  nombre de otro municipio, identificadores repetidos y municipios antiguos con código INE en
  Wikidata; corregir en Wikidata lo que sea error suyo.
- Permitir que Actions abra PR: es un ajuste de la organización (Settings → Actions → General →
  Workflow permissions). Mientras no esté, la actualización mensual sube la rama con los datos y
  avisa con el enlace para abrir la PR a mano. GitHub Pages ya está activo.
- Versión 0.4, por orden: población oficial del INE a 1 de enero en lugar de la de Eurostat (hecho);
  códigos postales del callejero del censo electoral (cada tramo lleva
  su distrito postal; antes hay que aclarar si la licencia del INE cubre ese dato, cuyo origen es
  Correos); partidos judiciales y comarcas oficiales (buscar fuente: el Registro de Entidades
  Locales anota islas, comarcas y mancomunidades); nombres de países desde CLDR; acciones de
  GitHub que aún usan Node 20.
- Más adelante: entidades de población, variaciones históricas del INE (diccionarios anuales desde
  2004 y páginas de modificaciones de cada año), búsqueda aproximada.

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
- **Catastro**: `ConsultaProvincia` da las 48 provincias de régimen común (sin Álava, Gipuzkoa,
  Navarra ni Bizkaia) y `ConsultaMunicipio`, por provincia, cada municipio con su código DGC
  (`locat`: delegación y municipio) y su código del INE (`loine`), escritos como números sin ceros
  a la izquierda. En A Coruña da 95 municipios para los 93 del INE: incluye Cesuras y Oza dos Ríos,
  fusionados en 2013, que van al informe. El código DGC no coincide con el del INE en 61 de los 95.
  En la primera generación completa: 7.608 municipios con código DGC (todos los de régimen común).
  Algunas gerencias del Catastro no son provincias y tienen sus propias dos cifras, que encabezan
  el código DGC y las referencias rústicas: 51 (Cartagena), 52 (Gijón), 53 (Jerez), 54 (Vigo), 55
  (Ceuta) y 56 (Melilla). El Catastro corta los nombres a 30 caracteres y a veces pone el artículo
  al final o lo omite; el contraste de nombres lo tiene en cuenta y solo informa de los distintos
  de verdad (nombres antiguos como «La Bisbal de Falset» o abreviaturas).
- **Límites de GISCO**: excluyen el uso comercial y llevan «© EuroGeographics». Descartados como
  fuente.
- **CartoCiudad**: no permite descargar los códigos postales (convenio con Correos,
  BOE-A-2023-11522). Descartado para los códigos postales.
- **IGN**: licencia CC BY 4.0 (Orden FOM/2807/2015 y condiciones del CNIG), con la fórmula de
  atribución de cada producto en la tabla del Sistema Cartográfico Nacional. Los límites (BDLJE)
  se descargan de un enlace directo del feed Atom del IGN: un zip de 66 MB, actualizado el 10 de
  agosto de 2026, con 8.220 unidades municipales en GML (EPSG:4258, latitud y longitud) y una
  incertidumbre de unos 40 m. El servidor de descargas del CNIG corta la conexión TLS desde
  algunas redes; desde Actions funciona. El Nomenclátor de Municipios y Entidades de Población
  (CSV y Access, marzo de 2026) trae capital, coordenadas, altitud, superficie oficial y número del
  Registro de Entidades Locales, pero solo se descarga con un formulario firmado por el navegador
  (403 sin él), así que las capitales salen de la API de entidades del IGN (colección `nuc`,
  37.497 núcleos con código INE, coordenadas, altitud y `capital`: una cifra por nivel, Estado,
  comunidad, provincia y municipio). Ninguno trae nombres por idioma.

Comprobado el 10 de noviembre de 2026:

- **Licencia del INE**: CC BY 4.0 (aviso legal). Para datos tratados, la cita es «Elaboración propia
  con datos extraídos del sitio web del INE: www.ine.es», con la fecha de actualización del original.
- **Operación de códigos del INE**: además del diccionario y de la tabla de provincias, publica la
  tabla de islas (`26codislas.xlsx`, con el municipio de cada isla; su título dice «a 1 de enero de
  2025», pero coincide con el diccionario de 2026), las modificaciones de cada año
  (`codmunNN/NNcodmunmod.htm`), las anotadas en lo que va de año (`codmun_anual.htm`; el 10 de
  noviembre, 15 cambios de nombre) y el número de municipios por provincia, comunidad e isla.
- **Tabla LAU de Eurostat**: la de 2024 sigue siendo la última validada; las de 2025 y 2026 están
  «parcialmente validadas».
- **Capitales del IGN**: 79 municipios sin capital en `nuc`; la colección `opob` marca la de 54 (dos
  de ellos con dos, que quedan sin capital) y en las demás colecciones no hay ninguna.
- **Callejero del censo electoral (INE)**: ficheros nacionales y provinciales en enero y julio, con
  el distrito postal de cada tramo de vía.
- **Población oficial del INE**: operación 22 (`DPOP`) de la API JSON. `TABLAS_OPERACION/22` da 52
  tablas con el código `PROV-MUN` («Población por municipios y sexo», una por provincia, con Ceuta y
  Melilla) y `DATOS_TABLA/{id}?nult=1&tip=AM&tv=18:451`, el último año del total de ambos sexos con
  el código del INE en los metadatos de cada serie: 1 de enero de 2025, definitivo, publicado el 11
  de diciembre de 2025. Los municipios que ya no existen siguen con su serie, vacía (Cesuras). Las tablas
  de comunidades (2853) e islas (2910) acaban en 2021. La tabla nacional por municipio (29005)
  pasa de 10 MB.

Por comprobar:

- callejero del censo electoral: si la licencia del INE cubre el código postal (su origen es
  Correos);
- licencias de iso-codes y EU Vocabularies.
