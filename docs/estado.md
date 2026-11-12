# Estado de territorios-es

Generado por `python web/estado.py` a partir de `datos/`, `pruebas/datos/` y `fuentes/`; la CI comprueba que está al día. Con pestañas y en seis idiomas, en la [web de datos](https://alertapublica.github.io/territorios-es/es/estado/). [English](status.md). Lo que falta, en los [issues «objetivo»](https://github.com/alertapublica/territorios-es/issues?q=is%3Aissue+is%3Aopen+label%3Aobjetivo).

| **9.160** | **8 de 9** | **8.132** | **25** | **14.054** |
|:---:|:---:|:---:|:---:|:---:|
| territorios | niveles con datos | municipios | fuentes · descarga 2026-11-11 | pares código postal–municipio |

**Índice**: [Territorios](#territorios) · [Cobertura](#cobertura) · [Por comunidad](#por-comunidad) · [Repositorio](#repositorio) · [Fuentes](#fuentes) · [Ficheros](#ficheros) · [Librería](#librería)

## Territorios

Las flechas continuas van del padre al hijo; las de puntos, de un territorio a otro que enlaza en un campo, con cuántos lo tienen. En verde, lo que ya está en `datos/`; en ámbar, lo que el generador ya sabe hacer pero aún no está en `datos/` (el recuento es entonces el de los datos de prueba).

```mermaid
flowchart TB
  accTitle: Territorios
  autonomous_community["Comunidades y ciudades autónomas<br>19"]:::done
  province["Provincias<br>52"]:::done
  municipality["Municipios<br>8.132"]:::done
  island["Islas<br>11"]:::done
  judicial_district["Partidos judiciales<br>431"]:::done
  warning_zone["Zonas de aviso de AEMET<br>182"]:::done
  comarca["Comarcas<br>84"]:::done
  minor_local_entity["Entidades locales menores<br>sin generar · prueba: 72"]:::todo
  country["Países<br>249"]:::done
  autonomous_community --> comarca
  autonomous_community --> province
  country --> autonomous_community
  municipality --> minor_local_entity
  province --> island
  province --> judicial_district
  province --> municipality
  province --> warning_zone
  judicial_district -.->|"sede: 431 de 431"| municipality
  municipality -.->|"comarca: 1.767 de 8.132"| comarca
  municipality -.->|"isla: 155 de 8.132"| island
  municipality -.->|"partido judicial: 8.132 de 8.132"| judicial_district
  municipality -.->|"zona de aviso: 8.124 de 8.132"| warning_zone
  classDef done fill:#d8f0d8,stroke:#2e7d32,color:#173d17
  classDef todo fill:#fdecc8,stroke:#b26a00,color:#4a2c00,stroke-dasharray:4 3
  classDef box fill:#e6eef8,stroke:#3b6ea8,color:#14304f
```

## Cobertura

Cuántos municipios tienen cada dato en `municipios.csv`. Los datos que solo existen en una parte del territorio se cuentan sobre los municipios de esa parte.

| Dato | Municipios | % |  |
|---|---:|---:|---|
| población (INE) | 8.132 de 8.132 | 100 % | `████████████████████` |
| partido judicial (Justicia) | 8.132 de 8.132 | 100 % | `████████████████████` |
| zona de aviso (AEMET) | 8.124 de 8.132 | 99,9 % | `███████████████████░` |
| comarca · Cataluña, Aragón, Álava y El Bierzo | 1.767 de 1.767 | 100 % | `████████████████████` |
| isla (INE) · Baleares y Canarias | 155 de 155 | 100 % | `████████████████████` |
| código postal | 8.132 de 8.132 | 100 % | `████████████████████` |
| LAU (Eurostat) | 8.132 de 8.132 | 100 % | `████████████████████` |
| NUTS 3 | 8.132 de 8.132 | 100 % | `████████████████████` |
| superficie (Eurostat) | 8.132 de 8.132 | 100 % | `████████████████████` |
| código DGC (Catastro) · régimen común | 7.608 de 7.608 | 100 % | `████████████████████` |
| código BDDAE (IGN) | 8.132 de 8.132 | 100 % | `████████████████████` |
| capital (IGN) | 8.105 de 8.132 | 99,7 % | `███████████████████░` |
| coordenadas de la capital | 8.105 de 8.132 | 99,7 % | `███████████████████░` |
| altitud de la capital | 8.105 de 8.132 | 99,7 % | `███████████████████░` |
| Wikidata | 8.129 de 8.132 | 99,9 % | `███████████████████░` |
| OpenStreetMap | 8.121 de 8.132 | 99,9 % | `███████████████████░` |
| GeoNames | 7.991 de 8.132 | 98,3 % | `███████████████████░` |

<details>
<summary>Municipios a los que les falta cada dato (si son 30 o menos)</summary>

| Dato | Municipios |
|---|---|
| zona de aviso (AEMET) | San Martín del Tesorillo (11903), Fuente Carreteros (14901), La Guijarrosa (14902), Fornes (18077), Torrenueva Costa (18916), La Zarza-Perrunal (21902), El Palmar de Troya (41904), Usansolo (48916) |
| capital (IGN) | la Vall de Laguar (03137), Canovelles (08041), Capolat (08045), L'Espunyola (08078), Fogars de la Selva (08082), Malla (08111), Les Masies de Voltregà (08117), La Quar (08177), Teià (08281), Los Ausines (09030), Valle de Losa (09908), Los Cortijos (13036), Foixà (17068), Ataun (20015), Valderrueda (24183), La Molsosa (25136), Pinós (25167), La Hiruela (28069), Moaña (36029), Nigrán (36035), Hermigua (38021), Puntallana (38030), El Pinar de El Hierro (38901), Valdáliga (39091), Barrika (48014), Galdakao (48036), Erandio (48902) |
| coordenadas de la capital | la Vall de Laguar (03137), Canovelles (08041), Capolat (08045), L'Espunyola (08078), Fogars de la Selva (08082), Malla (08111), Les Masies de Voltregà (08117), La Quar (08177), Teià (08281), Los Ausines (09030), Valle de Losa (09908), Los Cortijos (13036), Foixà (17068), Ataun (20015), Valderrueda (24183), La Molsosa (25136), Pinós (25167), La Hiruela (28069), Moaña (36029), Nigrán (36035), Hermigua (38021), Puntallana (38030), El Pinar de El Hierro (38901), Valdáliga (39091), Barrika (48014), Galdakao (48036), Erandio (48902) |
| altitud de la capital | la Vall de Laguar (03137), Canovelles (08041), Capolat (08045), L'Espunyola (08078), Fogars de la Selva (08082), Malla (08111), Les Masies de Voltregà (08117), La Quar (08177), Teià (08281), Los Ausines (09030), Valle de Losa (09908), Los Cortijos (13036), Foixà (17068), Ataun (20015), Valderrueda (24183), La Molsosa (25136), Pinós (25167), La Hiruela (28069), Moaña (36029), Nigrán (36035), Hermigua (38021), Puntallana (38030), El Pinar de El Hierro (38901), Valdáliga (39091), Barrika (48014), Galdakao (48036), Erandio (48902) |
| Wikidata | Ezkio-Itsaso (20035), Ceuta (51001), Melilla (52001) |
| OpenStreetMap | Bahabón de Esgueva (09033), Illana (19152), Ezkio-Itsaso (20035), Uharte Arakil (31123), Iza/Itza (31131), Jaurrieta (31134), Ultzama (31236), l'Alcúdia (46019), Carlet (46085), Ceuta (51001), Melilla (52001) |

</details>

**Fuente que decide los códigos postales (municipios)**

```mermaid
%%{init: {"themeVariables": {"pie1": "#4e8fd6", "pie2": "#f2a33a", "pie3": "#4cb08a", "pie4": "#d98cb8", "pie5": "#8cc8ef", "pie6": "#e6794a", "pie7": "#e8dc4a", "pie8": "#b0b0b0", "pieSectionTextColor": "#111111", "pieStrokeColor": "#ffffff", "pieOpacity": "1"}}}%%
pie showData
  accTitle: Fuente que decide los códigos postales (municipios)
  "INE" : 6593
  "ICGC" : 947
  "IDENA" : 272
  "Eustat" : 252
  "IDEIB" : 67
  "Ayto. de Madrid" : 1
```

**Nombres por idioma de Wikidata (todos los territorios)**

```mermaid
%%{init: {"themeVariables": {"pie1": "#4e8fd6", "pie2": "#f2a33a", "pie3": "#4cb08a", "pie4": "#d98cb8", "pie5": "#8cc8ef", "pie6": "#e6794a", "pie7": "#e8dc4a", "pie8": "#b0b0b0", "pieSectionTextColor": "#111111", "pieStrokeColor": "#ffffff", "pieOpacity": "1"}}}%%
pie showData
  accTitle: Nombres por idioma de Wikidata (todos los territorios)
  "aragonés" : 1231
  "castellano" : 1195
  "catalán" : 686
  "euskera" : 570
  "asturiano" : 558
  "aranés" : 525
  "gallego" : 432
  "inglés" : 381
```

## Por comunidad

| Comunidad | Municipios | Población | Partidos | Zonas de aviso | Islas | Comarcas | Con código postal | Fuente que decide (municipios) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Andalucía | 785 | 8.666.412 | 85 | 29 | — | — | 100 % | INE 785 |
| Aragón | 731 | 1.358.812 | 16 | 9 | — | 33 | 100 % | INE 731 |
| Principado de Asturias | 78 | 1.013.529 | 18 | 5 | — | — | 100 % | INE 78 |
| Illes Balears | 67 | 1.237.480 | 6 | 7 | 4 | — | 100 % | IDEIB 67 |
| Canarias | 88 | 2.249.976 | 19 | 13 | 7 | — | 100 % | INE 88 |
| Cantabria | 102 | 593.964 | 8 | 4 | — | — | 100 % | INE 102 |
| Castilla y León | 2.248 | 2.398.500 | 41 | 24 | — | 1 | 100 % | INE 2.248 |
| Castilla-La Mancha | 919 | 2.119.234 | 31 | 17 | — | — | 100 % | INE 919 |
| Cataluña | 947 | 8.146.265 | 49 | 16 | — | 43 | 100 % | ICGC 947 |
| Comunitat Valenciana | 542 | 5.415.843 | 36 | 11 | — | — | 100 % | INE 542 |
| Extremadura | 388 | 1.051.638 | 21 | 8 | — | — | 100 % | INE 388 |
| Galicia | 313 | 2.713.169 | 45 | 16 | — | — | 100 % | INE 313 |
| Comunidad de Madrid | 179 | 7.137.031 | 21 | 3 | — | — | 100 % | INE 178 · Ayto. de Madrid 1 |
| Región de Murcia | 45 | 1.589.138 | 11 | 5 | — | — | 100 % | INE 45 |
| Comunidad Foral de Navarra | 272 | 683.500 | 5 | 4 | — | — | 100 % | IDENA 272 |
| País Vasco | 252 | 2.242.342 | 14 | 7 | — | 7 | 100 % | Eustat 252 |
| La Rioja | 174 | 327.286 | 3 | 2 | — | — | 100 % | INE 174 |
| Ceuta | 1 | 83.595 | 1 | 1 | — | — | 100 % | INE 1 |
| Melilla | 1 | 86.780 | 1 | 1 | — | — | 100 % | INE 1 |

## Repositorio

De las fuentes a los datos y de los datos a la librería, la web y las pruebas. Los hexágonos son los workflows de GitHub Actions.

```mermaid
flowchart TB
  accTitle: Repositorio
  ext(["25 fuentes externas<br>AEMET · Aragón · Ayto. de Madrid · CDAU · Catastro · Eurostat · Eustat · ICGC · IDEIB · IDENA · IGN · INE · Idescat · Justicia · REL · Wikidata"])
  hand[/"fuentes/<br>14 listas revisadas a mano"/]
  descargas["descargas<br>descarga con caché, huella SHA-256 y relay"]
  readers["lectores<br>aemet · catastro · codigos_postales · comarcas · eurostat · ign · ine · justicia · wikidata"]
  construir["construir<br>cruza las fuentes y arma el catálogo"]
  exportar["exportar<br>escribe datos/ y comprueba su coherencia"]
  limites["limites<br>simplifica los límites a GeoJSON"]
  datos[("datos/<br>15 ficheros")]
  geo[("limites-municipios.geojson.gz<br>adjunto a cada versión")]
  report["informe de discrepancias (issue)"]
  lib["librería Python y JavaScript"]
  web["web de datos (GitHub Pages)"]
  users(["quien la usa"])
  fixture[("pruebas/datos/<br>datos de prueba (sin red)")]
  tests["pruebas"]
  ext --> descargas --> readers --> construir --> exportar --> datos
  hand --> construir
  readers --> limites --> geo
  construir --> report
  datos --> lib
  geo --> lib
  datos --> web
  lib --> users
  web --> users
  construir --> fixture --> tests
  lib --> tests
  wf_ci_yml{{"CI"}}
  wf_generar_yml{{"Generar datos"}}
  wf_codigos_postales_yml{{"Códigos postales"}}
  wf_limites_yml{{"Límites de la versión"}}
  wf_pages_yml{{"Web de datos"}}
  wf_generar_yml -.-> descargas
  wf_codigos_postales_yml -.-> readers
  wf_limites_yml -.-> limites
  wf_pages_yml -.-> web
  wf_ci_yml -.-> tests
  class datos,geo,fixture done
  class ext,hand,users box
  classDef done fill:#d8f0d8,stroke:#2e7d32,color:#173d17
  classDef todo fill:#fdecc8,stroke:#b26a00,color:#4a2c00,stroke-dasharray:4 3
  classDef box fill:#e6eef8,stroke:#3b6ea8,color:#14304f
```

<details>
<summary>Los 5 workflows</summary>

| Workflow | Cuándo | Qué hace |
|---|---|---|
| [CI](../.github/workflows/ci.yml) | push, PR, a mano | pruebas de Python y JS, datos de prueba al día, coherencia de datos/, paquetes instalables y este mapa |
| [Generar datos](../.github/workflows/generar.yml) | a mano, programado (`17 5 3 * *`) | descarga las fuentes y regenera datos/ y este mapa; en main abre una PR y actualiza el issue del informe |
| [Códigos postales](../.github/workflows/codigos-postales.yml) | a mano, programado (`41 4 10 1,7 *`) | recopila los códigos postales de todas las fuentes, regenera este mapa y abre una PR |
| [Límites de la versión](../.github/workflows/limites.yml) | al publicar una versión | adjunta limites-municipios.geojson.gz a cada versión |
| [Web de datos](../.github/workflows/pages.yml) | al acabar la CI, a mano | publica la web y esta página de estado en GitHub Pages cuando la CI pasa en main |

</details>

<details>
<summary>Los 15 módulos del generador</summary>

| Módulo | Qué hace |
|---|---|
| `aemet` | zona de aviso de cada municipio; nombre de cada zona de aviso |
| `catastro` | código DGC de cada municipio |
| `codigos_postales` | códigos postales del municipio de Madrid; códigos postales de Cataluña; códigos postales de Navarra; códigos postales del País Vasco; códigos postales de Baleares; códigos postales de toda España (callejero del censo electoral); códigos postales de Andalucía (contraste); códigos postales de los municipios de régimen común |
| `comarcas` | comarca de cada municipio de Cataluña; comarca de cada municipio de Aragón |
| `eurostat` | LAU, NUTS 3 y superficie |
| `ign` | capital de cada municipio, con coordenadas y altitud; código BDDAE y límites municipales |
| `ine` | códigos y nombres oficiales de los municipios; islas y sus municipios; cambios de nombre del año; provincias y comunidades; población oficial |
| `justicia` | partido judicial de cada municipio y su sede |
| `wikidata` | nombres por idioma, enlaces e identificadores |
| `__main__` | orquesta las descargas y escribe el informe |
| `descargas` | descarga con caché, huella SHA-256 y relay |
| `xlsx` | lee XLSX sin dependencias |
| `construir` | cruza las fuentes y arma el catálogo |
| `exportar` | escribe datos/ y comprueba su coherencia |
| `limites` | simplifica los límites a GeoJSON |

</details>

## Fuentes

Qué organismo alimenta cada fichero de `datos/`.

```mermaid
flowchart LR
  accTitle: Fuentes
  o_AEMET(["AEMET"]):::box
  o_Aragón(["Aragón"]):::box
  o_Ayto__de_Madrid(["Ayto. de Madrid"]):::box
  o_CDAU(["CDAU"]):::box
  o_Catastro(["Catastro"]):::box
  o_Eurostat(["Eurostat"]):::box
  o_Eustat(["Eustat"]):::box
  o_ICGC(["ICGC"]):::box
  o_IDEIB(["IDEIB"]):::box
  o_IDENA(["IDENA"]):::box
  o_IGN(["IGN"]):::box
  o_INE(["INE"]):::box
  o_Idescat(["Idescat"]):::box
  o_Justicia(["Justicia"]):::box
  o_REL(["REL"]):::box
  o_Wikidata(["Wikidata"]):::box
  f_codigos_postales_fuentes_csv[("codigos-postales-fuentes.csv")]:::done
  f_codigos_postales_csv[("codigos-postales.csv")]:::done
  f_codigos_csv[("codigos.csv")]:::done
  f_comarcas_csv[("comarcas.csv")]:::done
  f_comunidades_csv[("comunidades.csv")]:::done
  f_entidades_menores_csv[("entidades-menores.csv")]:::todo
  f_islas_csv[("islas.csv")]:::done
  f_limites_municipios_geojson_gz[("limites-municipios.geojson.gz")]:::box
  f_municipios_csv[("municipios.csv")]:::done
  f_nombres_csv[("nombres.csv")]:::done
  f_paises_csv[("paises.csv")]:::done
  f_partidos_judiciales_csv[("partidos-judiciales.csv")]:::done
  f_provincias_csv[("provincias.csv")]:::done
  f_wikipedia_csv[("wikipedia.csv")]:::done
  f_zonas_aviso_csv[("zonas-aviso.csv")]:::done
  o_AEMET --> f_municipios_csv
  o_AEMET --> f_zonas_aviso_csv
  o_Aragón --> f_comarcas_csv
  o_Aragón --> f_municipios_csv
  o_Ayto__de_Madrid --> f_codigos_postales_fuentes_csv
  o_Ayto__de_Madrid --> f_codigos_postales_csv
  o_CDAU --> f_codigos_postales_fuentes_csv
  o_CDAU --> f_codigos_postales_csv
  o_Catastro --> f_codigos_postales_fuentes_csv
  o_Catastro --> f_codigos_postales_csv
  o_Catastro --> f_codigos_csv
  o_Catastro --> f_municipios_csv
  o_Eurostat --> f_codigos_csv
  o_Eurostat --> f_municipios_csv
  o_Eustat --> f_codigos_postales_fuentes_csv
  o_Eustat --> f_codigos_postales_csv
  o_ICGC --> f_codigos_postales_fuentes_csv
  o_ICGC --> f_codigos_postales_csv
  o_IDEIB --> f_codigos_postales_fuentes_csv
  o_IDEIB --> f_codigos_postales_csv
  o_IDENA --> f_codigos_postales_fuentes_csv
  o_IDENA --> f_codigos_postales_csv
  o_IGN --> f_limites_municipios_geojson_gz
  o_IGN --> f_municipios_csv
  o_INE --> f_codigos_postales_fuentes_csv
  o_INE --> f_codigos_postales_csv
  o_INE --> f_codigos_csv
  o_INE --> f_comunidades_csv
  o_INE --> f_islas_csv
  o_INE --> f_municipios_csv
  o_INE --> f_nombres_csv
  o_INE --> f_provincias_csv
  o_Idescat --> f_comarcas_csv
  o_Idescat --> f_municipios_csv
  o_Justicia --> f_municipios_csv
  o_Justicia --> f_partidos_judiciales_csv
  o_REL --> f_comarcas_csv
  o_REL --> f_entidades_menores_csv
  o_REL --> f_municipios_csv
  o_Wikidata --> f_codigos_csv
  o_Wikidata --> f_nombres_csv
  o_Wikidata --> f_paises_csv
  o_Wikidata --> f_wikipedia_csv
  classDef done fill:#d8f0d8,stroke:#2e7d32,color:#173d17
  classDef todo fill:#fdecc8,stroke:#b26a00,color:#4a2c00,stroke-dasharray:4 3
  classDef box fill:#e6eef8,stroke:#3b6ea8,color:#14304f
```

<details>
<summary>Las 25 fuentes, con su lector y la fecha de descarga</summary>

| Fuente | Organismo | Lector | Aporta | Descargada |
|---|---|---|---|---|
| `ine_municipios` | INE | `generador/ine.py` | códigos y nombres oficiales de los municipios | 2026-11-11 |
| `ine_islas` | INE | `generador/ine.py` | islas y sus municipios | 2026-11-11 |
| `ine_cambios` | INE | `generador/ine.py` | cambios de nombre del año | 2026-11-11 |
| `ine_provincias` | INE | `generador/ine.py` | provincias y comunidades | 2026-11-11 |
| `ine_poblacion` | INE | `generador/ine.py` | población oficial | 2026-11-11 |
| `mjusticia_censo_judicial` | Justicia | `generador/justicia.py` | partido judicial de cada municipio y su sede | 2026-11-11 |
| `aemet_municipios` | AEMET | `generador/aemet.py` | zona de aviso de cada municipio | 2026-11-11 |
| `aemet_zonas` | AEMET | `generador/aemet.py` | nombre de cada zona de aviso | 2026-11-11 |
| `idescat_comarcas` | Idescat | `generador/comarcas.py` | comarca de cada municipio de Cataluña | 2026-11-11 |
| `aragon_comarcas` | Aragón | `generador/comarcas.py` | comarca de cada municipio de Aragón | 2026-11-11 |
| `rel_comarcas` | REL | `fuentes/` | comarcas que son entidad local; cuadrillas de Álava y El Bierzo (exportación revisada a mano) | aún no |
| `rel_eatim` | REL | `fuentes/` | entidades locales menores, con su municipio y su tipo (exportación revisada a mano) | aún no |
| `eurostat_lau` | Eurostat | `generador/eurostat.py` | LAU, NUTS 3 y superficie | 2026-11-11 |
| `wikidata` | Wikidata | `generador/wikidata.py` | nombres por idioma, enlaces e identificadores | 2026-11-11 |
| `catastro` | Catastro | `generador/catastro.py` | código DGC de cada municipio | 2026-11-11 |
| `ign_poblaciones` | IGN | `generador/ign.py` | capital de cada municipio, con coordenadas y altitud | 2026-11-11 |
| `ign_limites` | IGN | `generador/ign.py` | código BDDAE y límites municipales | 2026-11-11 |
| `madrid_direcciones` | Ayto. de Madrid | `generador/codigos_postales.py` | códigos postales del municipio de Madrid | 2026-11-11 |
| `icgc_direcciones` | ICGC | `generador/codigos_postales.py` | códigos postales de Cataluña | 2026-11-11 |
| `idena_direcciones` | IDENA | `generador/codigos_postales.py` | códigos postales de Navarra | 2026-11-11 |
| `eustat_portales` | Eustat | `generador/codigos_postales.py` | códigos postales del País Vasco | 2026-11-11 |
| `ideib_portales` | IDEIB | `generador/codigos_postales.py` | códigos postales de Baleares | 2026-11-11 |
| `ine_callejero` | INE | `generador/codigos_postales.py` | códigos postales de toda España (callejero del censo electoral) | 2026-11-11 |
| `cdau_portales` | CDAU | `generador/codigos_postales.py` | códigos postales de Andalucía (contraste) | 2026-11-11 |
| `catastro_direcciones` | Catastro | `generador/codigos_postales.py` | códigos postales de los municipios de régimen común | 2026-11-11 |

</details>

## Ficheros

«Explorar» abre la tabla en Datasette Lite (filtros, orden y consultas SQL en el navegador) desde una base SQLite que la web publica con todos los CSV y los códigos como texto.

| Fichero | Filas | Tamaño | Lo alimentan | Estado |  |
|---|---:|---:|---|---|---|
| [`codigos-postales-fuentes.csv`](../datos/codigos-postales-fuentes.csv) | 33.537 | 1,7 MB | Ayto. de Madrid, CDAU, Catastro, Eustat, ICGC, IDEIB, IDENA, INE | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/codigos-postales-fuentes) |
| [`codigos-postales.csv`](../datos/codigos-postales.csv) | 14.054 | 865 KB | Ayto. de Madrid, CDAU, Catastro, Eustat, ICGC, IDEIB, IDENA, INE | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/codigos-postales) |
| [`codigos.csv`](../datos/codigos.csv) | 67.083 | 2,9 MB | Catastro, Eurostat, INE, Wikidata | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/codigos) |
| [`comarcas.csv`](../datos/comarcas.csv) | 84 | 15 KB | Aragón, Idescat, REL | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/comarcas) |
| [`comunidades.csv`](../datos/comunidades.csv) | 19 | 5 KB | INE | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/comunidades) |
| `entidades-menores.csv` | 72 |  | REL | solo en pruebas |  |
| [`islas.csv`](../datos/islas.csv) | 11 | 2 KB | INE | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/islas) |
| [`manifiesto.json`](../datos/manifiesto.json) |  | 22 KB |  | en datos/ |  |
| [`municipios.csv`](../datos/municipios.csv) | 8.132 | 2,3 MB | AEMET, Aragón, Catastro, Eurostat, IGN, INE, Idescat, Justicia, REL | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/municipios) |
| [`nombres.csv`](../datos/nombres.csv) | 24.394 | 1,1 MB | INE, Wikidata | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/nombres) |
| [`paises.csv`](../datos/paises.csv) | 249 | 23 KB | Wikidata | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/paises) |
| [`partidos-judiciales.csv`](../datos/partidos-judiciales.csv) | 431 | 58 KB | Justicia | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/partidos-judiciales) |
| [`provincias.csv`](../datos/provincias.csv) | 52 | 8 KB | INE | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/provincias) |
| [`territorios.json`](../datos/territorios.json) | 9.160 | 5,5 MB |  | en datos/ |  |
| [`wikipedia.csv`](../datos/wikipedia.csv) | 64.898 | 4,9 MB | Wikidata | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/wikipedia) |
| [`zonas-aviso.csv`](../datos/zonas-aviso.csv) | 182 | 15 KB | AEMET | en datos/ | [explorar](https://lite.datasette.io/?url=https%3A%2F%2Falertapublica.github.io%2Fterritorios-es%2Fdatos%2Fterritorios-es.db#/territorios-es/zonas-aviso) |

<details>
<summary>Las 14 listas revisadas a mano (<code>fuentes/</code>)</summary>

| Lista | Filas | Aporta |
|---|---:|---|
| `fuentes.json` |  | URL, licencia y atribución de cada fuente |
| `comunidades.csv` | 19 | comunidades: nombre, ISO 3166-2, NUTS 2 |
| `nombres-comunidades.csv` | 114 | nombres de las comunidades en cada idioma |
| `provincias.csv` | 52 | provincias: ISO 3166-2 y NUTS 3 |
| `islas.csv` | 11 | Wikidata y NUTS 3 de cada isla |
| `comarcas.csv` | 84 | comarcas: tipo, nombre y códigos |
| `comarcas-municipios.csv` | 89 | municipios de las cuadrillas de Álava y de El Bierzo |
| `entidades-menores.csv` | 3.674 | entidades locales menores: número del Registro, municipio, tipo, nombre, capitalidad y fecha de inscripción |
| `zonas-aviso.csv` | 4 | zona de los municipios que faltan en el maestro de AEMET |
| `alias.csv` | 23 | alias |
| `partes-bilingues.csv` | 273 | partes de los nombres bilingües |
| `descartes-wikidata.csv` | 7 | etiquetas de Wikidata descartadas |
| `paises-ue.csv` | 30 | países de la UE y del EEE |
| `paises-excluidos.csv` | 6 | códigos ISO que no son países |

</details>

## Librería

Los mismos módulos en Python (`python/territorios_es/`) y JavaScript (`js/`).

```mermaid
flowchart LR
  accTitle: Librería
  d_Catastro[("Catastro")]:::box
  d_codigos_postales_csv[("codigos-postales.csv")]:::done
  d_limites_municipios_geojson_gz[("limites-municipios.geojson.gz")]:::box
  d_territorios_json[("territorios.json")]:::done
  m_catalog["catalog<br>resolve · territory · search · mentions · name · children"]
  d_territorios_json --> m_catalog
  m_relation["relation<br>relate_name · combine"]
  m_text["text<br>normalize · display_name · slugify"]
  m_geo["geo<br>distances · point in polygon"]
  m_catastro["catastro<br>parse_cadastral_reference · relate_cadastral_reference"]
  m_catastro_online["catastro_online · con red<br>locate_reference · locate_point"]
  d_Catastro --> m_catastro_online
  m_limits["limits<br>load_limits · locate"]
  d_limites_municipios_geojson_gz --> m_limits
  m_postal["postal<br>postal_codes · municipalities · relate_postal_code"]
  d_codigos_postales_csv --> m_postal
  m_text --> m_catalog
  m_catalog --> m_relation
  m_geo --> m_limits
  classDef done fill:#d8f0d8,stroke:#2e7d32,color:#173d17
  classDef todo fill:#fdecc8,stroke:#b26a00,color:#4a2c00,stroke-dasharray:4 3
  classDef box fill:#e6eef8,stroke:#3b6ea8,color:#14304f
```
