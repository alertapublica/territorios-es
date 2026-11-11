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
  Los servidores que no responden a las IP de GitHub (hoy, el ICGC) se leen por un relay con IP
  española (`VIA_RELAY` en `generador/descargas.py`, secretos `RELAY_URL` y `RELAY_CLAVE`); la
  URL que consta es siempre la de la fuente.
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
ya están (versión 0.3); los partidos judiciales, las zonas de aviso de AEMET y las comarcas, desde la
0.4:

- **Islas**: las 11 que tienen cabildo (Canarias) o consell insular (Illes Balears), con nivel
  `island` e identificador con el código de isla del INE (`es:isla:384` es Tenerife; `es:isla:072`,
  Ibiza). Su padre es la provincia. Los municipios no cambian de padre: llevan además el campo
  `island`. El código, el nombre oficial y los municipios de cada isla salen de la tabla de islas
  del INE (`26codislas.xlsx`); `fuentes/islas.csv` añade el elemento de Wikidata y el NUTS 3, que
  solo sirve para contrastar (Eivissa y Formentera comparten la ES531). Las islas menores van con
  el municipio al que pertenecen (La Graciosa con Teguise, en Lanzarote; Cabrera con Palma, en
  Mallorca). El nombre es el oficial del INE (§4.4) y los demás salen de Wikidata.
- **Partidos judiciales**: los 431 de la demarcación judicial, con nivel `judicial_district` e
  identificador con el código del Censo Judicial del Ministerio de Justicia: provincia y número del
  partido dentro de ella (`es:partido:0705` es Eivissa; `es:partido:5112`, Ceuta). Su padre es la
  provincia, porque ningún partido la cruza; los municipios no cambian de padre y llevan además el
  campo `judicial_district`, como con las islas. Los municipios de cada partido y su sede salen del
  Censo Judicial. El nombre es el de la sede, con sus partes si es bilingüe, porque el Censo lo
  escribe en mayúsculas y con alguna errata («CATARRO4623548000000JA» por Catarroja). La LO 1/2025
  mantiene los partidos: cada uno tiene un tribunal de instancia con sede en su capital. `search` y
  `mentions` no los devuelven salvo que se pidan en `levels`, porque se llaman como su sede.
- **Zonas de aviso de AEMET**: las 182 zonas terrestres de Meteoalerta, por las que AEMET emite
  sus avisos, con nivel `warning_zone` e identificador con el código de AEMET, de seis cifras
  (`es:zona-aviso:774602` es el Litoral norte de Valencia). No es una administración, sino la
  división con la que se avisa de lluvia, viento, nieve o calor; cubre todo el país. Su padre es
  la provincia y los municipios llevan además el campo `warning_zone`, como con las islas. La zona
  de cada municipio sale del maestro de municipios de AEMET OpenData, que pide clave (el secreto
  `AEMET_API_KEY`), y el nombre de cada zona, de la tabla de su delimitación. El maestro deja fuera
  algún municipio nuevo y conserva otros ya extinguidos: los que AEMET sí sitúa en su web van en
  `fuentes/zonas-aviso.csv`, con el enlace a su ficha, y los demás se quedan sin zona y salen en el
  informe; nunca se deduce del mapa, que es de 2018 y no casa con los límites actuales. Las zonas
  costeras (sufijo `C`) quedan para más adelante. `search` y `mentions` no las devuelven salvo que
  se pidan en `levels`.
- **Comarcas**: solo las que son entidad local, las del Registro de Entidades Locales: las 42
  comarcas de Cataluña más Aran, las 33 de Aragón, las 7 cuadrillas de Álava y El Bierzo. De las 42
  catalanas, el Registro aún no tiene el Lluçanès, que la Ley 7/2023 creó como comarca aunque su
  consejo no se constituye hasta después de las elecciones municipales de 2027 (el Registro la
  inscribirá entonces); aquí ya está. Son 84 y 1.767 municipios.
  Nivel `comarca`, con padre en la comunidad, porque alguna cruza el límite provincial; los
  municipios no cambian de padre y llevan además el campo `comarca`. El identificador es propio y
  no cambia: `es:comarca:CCNN`, con la comunidad del INE y un número, que en Cataluña y Aragón es
  el de su comarca en Idescat y en el Gobierno de Aragón (`es:comarca:0943` es el Lluçanès;
  `es:comarca:0217`, la Central) y en Álava y El Bierzo, el orden de su número en el Registro
  (`es:comarca:1604`, la cuadrilla de Vitoria-Gasteiz). El número del Registro (8 cifras) y el
  código autonómico van como códigos. `fuentes/comarcas.csv` las lista con su tipo (`comarca`,
  `cuadrilla` o `aran`, entidad territorial singular) y su nombre: el de Idescat en Cataluña y el
  del Registro en las demás. Los municipios de cada una salen cada mes de Idescat y de Aragón Open
  Data, por código INE, y en Álava y El Bierzo de `fuentes/comarcas-municipios.csv`, sacada del
  Registro. El Barcelonès sigue siendo comarca aunque su consejo se suprimió en 2019. Las comarcas
  de Galicia, la Comunitat Valenciana o Asturias, que son estadísticas o de planificación, quedan
  fuera; si se añaden, irán con otro tipo. `search` y `mentions` no las devuelven salvo que se
  pidan en `levels`, porque solo existen en cuatro comunidades y alguna se llama como un municipio.

Más adelante: entidades de población del Nomenclátor del INE (núcleos, y parroquias en Galicia y
Asturias), que son decenas de miles.

### 4.2 Códigos

| Código | Niveles | Fuente | Notas |
|---|---|---|---|
| INE | comunidad (2 cifras), provincia (2), isla (3), municipio (5 + dígito de control) | Diccionario anual y tabla de islas del INE | Oficial; es la base de la identidad. |
| Censo Judicial | partido judicial (`mjusticia:partido`, 4 cifras: provincia 2 + número 2) | Censo Judicial del Ministerio de Justicia | El número es el del partido en la demarcación de su provincia. El catálogo técnico de la Generalitat (CTEAJE) usa el mismo código salvo en Ceuta y Melilla (1112 y 2908, frente a 5112 y 5208). |
| AEMET | zona de aviso (`aemet:zona`, 6 cifras: comunidad 2 + provincia o grupo de islas 2 + zona 2) | Maestro de municipios de AEMET OpenData y delimitación de zonas de Meteoalerta | Las cifras de comunidad y provincia son de AEMET, no del INE (Baleares usa 53–55 y Canarias 90–96). |
| Comarca | comarca (`rel:comarca`, 8 cifras; `idescat:comarca` y `aragon:comarca`, 2 cifras) | Registro de Entidades Locales, Idescat y Gobierno de Aragón | El número del Registro empieza por 06 y la comunidad; el Excel del Registro pierde el cero inicial. El Lluçanès aún no lo tiene. |
| ISO 3166-1 | país (alfa-2, alfa-3, numérico) | Wikidata, contrastado con la ONU | |
| ISO 3166-2 | comunidad y provincia (`ES-GA`, `ES-C`) | Lista revisada a mano, contrastada con Wikidata | |
| NUTS 2024 | NUTS 1 (grupos de comunidades), NUTS 2 (comunidad), NUTS 3 (provincia; islas en Baleares y Canarias) | Eurostat | Para cruzar con estadísticas europeas. |
| LAU | municipio | Tabla anual LAU de Eurostat | En España es el código INE de 5 cifras (comprobado en los 8.132 municipios); ver §4.5 para lo que trae además. |
| DGC (Catastro) | municipio (`dgc:municipio`, 5 cifras: delegación 2 + municipio 3) | Servicios web libres del Catastro (`OVCCallejero`, `ConsultaProvincia` y `ConsultaMunicipio`), que dan el código DGC y el del INE de cada municipio | Distinto del INE en muchos municipios (A Coruña: INE `15030`, DGC `15900`). El enlace es por código, no por nombre; el nombre solo se contrasta. Álava, Gipuzkoa, Navarra y Bizkaia tienen catastro foral y quedan sin código DGC. |
| BDDAE (INSPIRE) | municipio (`ign:bddae`, 11 cifras: 34 + comunidad 2 + provincia 2 + INE 5) | Límites del IGN (BDLJE) | Código de la unidad administrativa del IGN y `localId` de su identificador INSPIRE (espacio de nombres `ES.IGN.BDDAE`). Se enlaza si coinciden el código INE, la provincia y la comunidad. |
| Wikidata | todos | SPARQL a partir del código INE | CC0. Aporta nombres por idioma, enlaces a Wikipedia y otros identificadores. |
| OpenStreetMap | todos | Identificador de la relación, desde Wikidata y contrastado con OSM | El identificador de Wikidata es CC0; lo que se copie de OSM va aparte con ODbL (§7). |
| GeoNames | todos | Desde Wikidata | CC BY 4.0. Muy usado por otras herramientas. |
| Código postal | municipio (relación de muchos a muchos, `datos/codigos-postales.csv`) | Lo que publican las administraciones: Ayuntamiento de Madrid, ICGC (Cataluña), IDENA (Navarra), Eustat (País Vasco), IDEIB (Baleares), callejero del censo electoral del INE (toda España), CDAU (Andalucía, solo contraste) y Catastro (INSPIRE Addresses, régimen común) | Útil para leer direcciones. No es un sistema de `resolve` (§6). En cada municipio decide la primera fuente que lo cubre y tiene datos (decisión 14); cada par lleva su fuente, su recuento en la unidad de esa fuente y las demás fuentes que lo tienen (`also`). `codigos-postales-fuentes.csv` guarda lo que dice cada fuente, para contrastar y para atender reclamaciones. Lo regenera su propio workflow dos veces al año. Fuentes descartadas: CartoCiudad (su convenio con Correos solo permite consultar los códigos, no descargarlos) y la web de Correos. |
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
- **Provincias, islas, partidos judiciales y municipios**: el oficial (el de un partido es el de su
  sede). Si es bilingüe, solo la parte del idioma de la página («Alacant» en catalán, «San
  Sebastián» en castellano) y el nombre completo en los demás.
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
| `resolve(system, code)` | De un código a un territorio con sus ancestros, o `None`/`null` si no existe. Sistemas: `ine:autonomia`, `ine:provincia`, `ine:municipio`, `ine:municipio:dc`, `dgc:municipio`, `mjusticia:partido`, `aemet:zona`, `rel:comarca`, `idescat:comarca`, `aragon:comarca`, `iso3166-1:alpha2`, `iso3166-1:alpha3`, `iso3166-2`, `nuts`, `lau`, `wikidata`, `osm:relation`, `geonames`… |
| `territory(id)` | Ficha completa: nombres, códigos, padre y ancestros. |
| `search(text, within, levels)` | Candidatos para un texto, cada uno con su motivo (`official`, `part`, `lang`, `alias` o `variant`) y en un orden fijo. `within` limita la búsqueda a un ámbito, por ejemplo a una provincia, a una isla, a un partido judicial, a una zona de aviso o a una comarca. Los partidos judiciales, las zonas de aviso y las comarcas solo salen si se piden en `levels`. |
| `children(id)` | Los territorios cuyo padre es este; en una isla, un partido judicial, una zona de aviso o una comarca, sus municipios. Los de una comunidad incluyen sus comarcas; los de una provincia incluyen sus partidos judiciales, sus zonas de aviso y, en Baleares y Canarias, sus islas. |
| `mentions(text, levels)` | Territorios nombrados dentro de un texto más largo («Moncada (Valencia)»), sin solaparse y empezando por el nombre más largo. Si el nombre completo no está en el catálogo, puede dar otro más corto contenido en él («Perales de Alfambra» → Alfambra). Por defecto, solo comunidades y provincias. |
| `normalize(text)` | La normalización común: sin tildes ni mayúsculas, «l·l» como «ll», el artículo delante y los guiones como espacios. |
| `name(id, lang, short)` | El nombre que se muestra, según §4.4. |
| `relate_name(text, within, levels)` | Una relación con estado: resuelto (un candidato), pendiente (ninguno o varios) o conflicto. |
| `combine(relations)` | Une varias relaciones del mismo objeto: si coinciden, resuelto; si se contradicen, conflicto. |
| `parse_cadastral_reference(text)` | Partes de una referencia catastral de 14, 18 o 20 caracteres: parcela, tipo (rústica o urbana), cargo, letras de control y si son correctas, y, si es rústica, el código DGC del municipio. Sin red. |
| `relate_cadastral_reference(text)` | El municipio de una referencia catastral: resuelto si es rústica y su código DGC está en el catálogo; pendiente si es urbana (no lleva el municipio), si las letras de control no cuadran o si el código no se conoce. |
| `locate(lon, lat, limits)` | El paso de punto a municipio de Voceiro, con el fichero de límites de la versión (`load_limits`; en JS, `loadLimits` en Node o `createLimits` en el navegador): resuelto dentro de un municipio y a más de 50 m de cualquier otro; pendiente cerca de un límite, en una zona común o fuera de todos (el mar, el extranjero); conflicto si cae en dos. Nunca devuelve «el más cercano». |
| `postal_codes(id)` | Los códigos postales de un municipio, por código, cada uno con su fuente, su recuento, su unidad y las demás fuentes que lo tienen (`also`). |
| `municipalities(code)` | Los municipios de un código postal: por recuento si todos tienen la misma unidad (direcciones, portales o tramos) y, si no, por los tramos del INE (0 si no tiene el par), porque recuentos de unidades distintas no se comparan. |
| `relate_postal_code(code)` | Resuelto si el código es de un solo municipio; pendiente si es de varios o de ninguno. Las evidencias traen la fuente, el recuento, la unidad y `also` de cada candidato. Con `combine` y el nombre del municipio se deshace la ambigüedad. |

Los códigos postales van en su propia tabla (`load_postal_codes`; en JS, `loadPostalCodes` en Node o
`createPostalCodes` en el navegador), no en `resolve`: un código abarca varios municipios y un
municipio tiene varios códigos, y `resolve` devuelve un solo territorio.

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
  - códigos postales: cada fuente con su licencia y su atribución (tabla del README): Ayuntamiento
    de Madrid, ICGC, IDENA, Eustat, INE y CDAU, CC BY 4.0; IDEIB, CC BY; Catastro, la licencia de la
    DGC, citando la fuente y la fecha de acceso (`retrieved` en el manifiesto). Solo se publican los
    pares código postal–municipio con su recuento, nunca las direcciones. El código postal es de
    Correos: no se copia su base de datos, se recopila lo que publican las administraciones, y hay
    una vía de reclamación (issue «Reclamación sobre datos»);
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
| Unicode CLDR y Debian iso-codes | Nombres traducidos de países y de subdivisiones ISO 3166-2. | Revisado el 11 de noviembre de 2026 (CLDR 49): descartado para los nombres de países, que siguen saliendo de Wikidata. No trae aranés y usa nombres de interfaz («Congo - Kinshasa», «RAE de Hong Kong (China)», «Côte d’Ivoire» en castellano). |
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

Tomadas el 10 de noviembre de 2026:

14. Códigos postales: en este repo, con un workflow propio dos veces al año que solo escribe
    `datos/codigos-postales.csv`, `datos/codigos-postales-fuentes.csv` y sus entradas del manifiesto
    (que el generador mensual conserva). Es un recopilador de lo que publican las administraciones,
    con la procedencia de cada par y una vía de reclamación; no se copia la base de Correos. En cada
    municipio decide la primera fuente que lo cubre y tiene datos: Ayuntamiento de Madrid; ICGC,
    IDENA, Eustat e IDEIB; INE; CDAU; Catastro. Se publican todos sus pares de ese municipio, sin
    umbrales (o sale o no sale), y ninguna otra fuente rellena pares sueltos, porque volverían los
    códigos antiguos del Catastro. Reglas fijas para todas: cinco cifras con provincia 01–52, fuera
    los XX000 (relleno) y las fusiones que el Catastro sigue archivando con los códigos DGC antiguos
    (Oza-Cesuras, Cerdedo-Cotobade). Cada par lleva el recuento de su fuente en su unidad, sin sumar
    unidades, y las demás fuentes que lo tienen (`also`). Si falla una descarga no se escribe nada.
    La API va en los dos sentidos y queda fuera de `resolve`.

Tomada el 11 de noviembre de 2026:

15. Partidos judiciales: nivel `judicial_district` con padre en la provincia, como las islas, a
    partir del Censo Judicial del Ministerio de Justicia en cada generación mensual. Identificador
    `es:partido:PPNN` (provincia y número del Ministerio), nombre de la sede y fuera de `search` y
    `mentions` salvo que se pidan. La descarga es obligatoria: si el Ministerio no responde, la
    generación falla antes de escribir nada, en lugar de publicar los municipios sin partido. Sin
    repositorios ajenos: ninguno está mantenido ni mejora la fuente oficial.
16. Zonas de aviso de AEMET: nivel `warning_zone` con padre en la provincia, a partir del maestro
    de municipios de AEMET OpenData (con la clave como secreto del repositorio) y de la tabla de la
    delimitación de zonas, en cada generación mensual. Identificador `es:zona-aviso:CCPPZZ` (código
    de AEMET), con su nombre oficial y fuera de `search` y `mentions` salvo que se pidan. La
    descarga es obligatoria, como la del Censo Judicial. Se prefiere el maestro a la tabla en PDF
    del plan Meteoalerta, que trae lo mismo (comprobado el 11 de noviembre de 2026: las 8.122 filas
    del maestro, sin los 2 municipios extinguidos y con las 4 excepciones de `fuentes/zonas-aviso.csv`,
    son los 8.124 municipios del PDF, con la misma zona), porque es JSON y no hay que leer 221 páginas.
17. Comarcas: solo las que son entidad local, con el Lluçanès desde ya (está creado por ley y su
    consejo llega en 2027), nivel `comarca` con padre en la comunidad e identificador propio
    `es:comarca:CCNN`, que no depende de que el Registro la inscriba ni cambia si la renombran (la
    cuadrilla de Ayala ya se llama de Aiaraldea). Los municipios de Cataluña y Aragón salen cada mes
    de Idescat y Aragón Open Data; la lista de comarcas y los municipios de Álava y El Bierzo, de
    una exportación del Registro revisada a mano, porque es un Excel binario antiguo y cambian muy
    poco. No se rellenan con comarcas estadísticas los municipios de las demás comunidades.

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
  recopilador de códigos postales (hecho, con la tirada completa de todas las fuentes; después,
  más fuentes: La Rioja, Gipuzkoa, Málaga, Barcelona…); partidos judiciales (hecho); zonas de aviso
  de AEMET (hecho); comarcas que son entidad local (hecho); acciones de GitHub que aún usan Node 20
  (las actualiza Dependabot).
- Comarcas, más adelante: contrastar cada mes con la exportación del Registro de Entidades Locales
  (se baja sin navegador de `…/export_excel/comarcas/all`, pero es un Excel binario antiguo, .xls,
  que habría que leer); su elemento de Wikidata y sus nombres en otros idiomas; inscribir el
  Lluçanès cuando el Registro lo haga, tras las elecciones de 2027. Las comarcas estadísticas o de
  planificación (Galicia, Comunitat Valenciana, Asturias, la zonificación de Navarra) irían con
  otro tipo, si se quieren.
- Cruces de los partidos judiciales, como capas posteriores: su elemento de Wikidata (390 de 431,
  enlazables por la sede) y sus nombres en otros idiomas; la población por partido del CGPJ; las
  demás demarcaciones del Censo Judicial (sección de la Audiencia, Tribunal Superior, fiscalía,
  registro civil).
- Zonas de aviso de AEMET, más adelante: las 51 costeras, ligadas a su zona terrestre, y su
  elemento de Wikidata. Pedir a AEMET que sitúe los municipios que aún no tienen zona (San Martín
  del Tesorillo, Usansolo, El Palmar de Troya…).
- Nombres de países: siguen saliendo de Wikidata, que tiene alguna errata. Revisarlos, corregir
  aquí las erratas con un fichero en `fuentes/` y corregirlas también en Wikidata.
- Códigos postales en Andalucía: el CDAU trae 526 pares que no tiene el INE, que decide allí;
  176 los confirma el Catastro (Vera Playa, 04621, entre ellos). Probablemente son zonas de segunda
  residencia que no salen en el censo electoral, del que sale el dato del INE. Valorar si el CDAU
  debe aportar esos pares.
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
  el distrito postal de cada tramo de vía (el de Correos). La edición de julio de 2026 trae 13.988
  pares en 8.132 municipios; 4 son XX000 (28000 en Madrid, entre ellos). Es la fuente de toda España.
- **Contraste entre fuentes de códigos postales**: donde hay tres, parte de lo que publicaría cada una
  que tiene también otra. Cataluña: ICGC 98,6 %, INE 98,8 %, Catastro 89,6 %. Madrid capital:
  Ayuntamiento 88,9 % (siete pares de borde, de una o dos direcciones), INE 98,2 %. Baleares: IDEIB
  92,9 %, INE 98,8 %. Andalucía: CDAU 78,7 % (402 pares que no tiene nadie más), INE 98,0 %,
  Catastro 95,7 %. Ninguna acierta siempre: el ICGC pone el 17811 de Santa Pau en Olot (2.968
  direcciones), la IDEIB el 07010 de Palma en Santa Margalida y el INE conserva el 08240 de Manresa.
- **ICGC, Adreces (versión simplificada)**: un ZIP para toda Cataluña en un directorio con la fecha
  en el nombre (`adreces-simplificat-v1r0-AAAAMMDD.zip`); dos tablas CSV («;») con `codmuni` (INE y
  dígito de control) y `codpostal`. Ningún XX000.
- **Ayuntamiento de Madrid, callejero oficial**: CSV de direcciones vigentes (Windows-1252, «;»),
  con la fecha en el nombre; su URL sale de la API del catálogo (`package_show`). `COD_POSTAL` por
  dirección; ningún 28000.
- **IDEIB, portales de Baleares**: un CSV de una columna (`ADRECA_DET`) con el código postal detrás
  del número y el municipio del INE dentro de `ID_PORTAL`. 308.733 portales, 3 sin código.
- **CDAU, portales de Andalucía**: un ZIP de 200 MB con un CSV de 700 MB, `ine_mun` y `cod_postal`.
  Solo contraste: una quinta parte de sus pares no está en ninguna otra fuente.
- **Catastro, INSPIRE Addresses**: un ATOM general con 52 gerencias (y entradas de los catastros
  forales, que apuntan a otros servidores), un ATOM por gerencia (ISO-8859-1) y un ZIP por municipio
  con un GML (EPSG:25830). Cada dirección enlaza su código postal (`AD:PostalDescriptor`) y su
  municipio (código DGC). El código va sin el cero inicial (`2250` es 02250); en Madrid, 282
  direcciones enlazan un descriptor que no está en el fichero. Hay que usar `https://` y
  `/INSPIRE/Addresses/`, y codificar los espacios y las eñes de los enlaces. La licencia de descarga
  (cláusulas 3, 5–8 y 12) no excluye datos de terceros, permite el uso público y comercial de la
  información transformada y pide citar a la DGC y la fecha de acceso.
- **IDENA, direcciones de Navarra**: shapefile cuyo DBF trae el municipio del INE sin la provincia
  (`CMUNICIPIO`) y `CODPOSTAL`. CC BY 4.0 según sus metadatos, con la atribución «Información
  geográfica propiedad del Gobierno de Navarra.».
- **Eustat, callejero NORA**: un fichero por territorio histórico, CSV (UTF-8 con BOM, «;») o XLSX
  (prefijo `x:`). El CSV de Gipuzkoa se corta siempre a mitad de descarga; el XLSX baja entero.
  CC BY 4.0, con la atribución «Eusko Jaurlaritza / Gobierno Vasco; Eustat; geoEuskadi».
- **Población oficial del INE**: operación 22 (`DPOP`) de la API JSON. `TABLAS_OPERACION/22` da 52
  tablas con el código `PROV-MUN` («Población por municipios y sexo», una por provincia, con Ceuta y
  Melilla) y `DATOS_TABLA/{id}?nult=1&tip=AM&tv=18:451`, el último año del total de ambos sexos con
  el código del INE en los metadatos de cada serie: 1 de enero de 2025, definitivo, publicado el 11
  de diciembre de 2025. Los municipios que ya no existen siguen con su serie, vacía (Cesuras). Las tablas
  de comunidades (2853) e islas (2910) acaban en 2021. La tabla nacional por municipio (29005)
  pasa de 10 MB.

Comprobado el 11 de noviembre de 2026:

- **Censo Judicial (Ministerio de Justicia)**: XLSX en la zona de descargas del Ministerio y en el
  catálogo de datos.gob.es (`e05228601-censo-judicial`); según los metadatos del conjunto, sus
  condiciones de uso son las generales del catálogo (`https://datos.gob.es/avisolegal`). El aviso
  legal del portal del Ministerio limita sus demás contenidos al uso privado.
  Una fila por municipio con `CPRO`, `PJ` (número del partido), `CODM PJ` (sede), `CODM` y `CPJ`
  («SI» en la sede), y una última fila «Actualizado a 25/03/2026». Trae los 8.132 municipios del
  diccionario y 431 partidos, cada uno con una sede en su provincia, y coincide fila a fila con el
  Nomenclátor de Partidos Judiciales en PDF del 30 de diciembre de 2025. Su población coincide con
  la del INE; su código postal es el de la sede del juzgado o del ayuntamiento, no el del municipio.
  Ninguno de sus partidos reúne dos islas salvo el de Eivissa, que incluye Formentera.
- **Contraste de partidos**: el CGPJ publica cada año la población por partido y municipio (XLSX,
  solo con nombres) y la Generalitat el catálogo CTEAJE de partidos de España (código, nombre y
  sede). Ningún repositorio ajeno con la relación nacional está mantenido.

Por comprobar:

- licencias de iso-codes y EU Vocabularies.
