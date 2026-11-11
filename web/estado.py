"""Status of the repository, drawn with Mermaid: docs/estado.md and docs/status.md, which GitHub renders,
and the status page of the website (<lang>/estado/ in its six languages, built by web/construir.py), with tabs. What
changes with the data (levels, counts, coverage, files, source dates) is read from datos/, pruebas/datos/
and fuentes/; how the pieces connect (which source feeds what, which module reads it, what each workflow
does) is declared below.

    python web/estado.py            # rewrites both Markdown files
    python web/estado.py --check    # fails if they are stale or something is missing from the map

--check fails when a source, a hand list, a generator or library module, a workflow, a level, a column
of municipios.csv or a file of datos/ is not declared here, so the map grows with the repository.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = {"es": ROOT / "docs" / "estado.md", "en": ROOT / "docs" / "status.md"}
REPO = "https://github.com/alertapublica/territorios-es"
PAGES = "https://alertapublica.github.io/territorios-es"
DATASETTE = "https://lite.datasette.io/?url="
DATABASE = "territorios-es.db"  # SQLite built by web/construir.py with every CSV, codes as text

TEXTS = ROOT / "web" / "textos.json"  # every visible text, under "estado", in each language of the website

# What is drawn and in which order; the names of each item are in web/textos.json.
LEVELS = ["autonomous_community", "province", "municipality", "island", "judicial_district", "warning_zone", "comarca",
          "country"]
LINKS = ["island", "judicial_district", "warning_zone", "comarca", "seat", "capital"]  # fields pointing to another territory
COVERAGE = ["population", "partido", "zona_aviso", "comarca", "isla", "postal_code", "lau", "nuts3", "area_km2", "dgc",
            "bddae", "capital", "lon", "altitude", "wikidata", "osm_relation", "geonames"]  # columns of municipios.csv
SCOPE = {  # data that only exist in part of the country: which municipalities they apply to
    "isla": lambda r: r["provincia"] in ("07", "35", "38"),
    "dgc": lambda r: r["provincia"] not in ("01", "20", "31", "48"),
    "comarca": lambda r: r["autonomia"] in ("02", "09") or r["provincia"] == "01" or (r["provincia"] == "24" and r["comarca"]),
}
MISSING_LIST = 30  # list the municipalities missing a datum when they are this many or fewer
MUNICIPAL_PLAIN = {"id", "ine", "ine_dc", "provincia", "autonomia", "official", "display", "lat", "time_zone", "slug"}
CP_SOURCES = {"madrid": "Ayto. de Madrid", "icgc": "ICGC", "idena": "IDENA", "eustat": "Eustat", "ideib": "IDEIB",
              "ine": "INE", "cdau": "CDAU", "catastro": "Catastro"}

POSTAL = ["codigos-postales.csv", "codigos-postales-fuentes.csv"]
SOURCES = {  # key in fuentes/fuentes.json: (organisation, generator module, files it feeds)
    "ine_municipios": ("INE", "ine", ["municipios.csv", "codigos.csv", "nombres.csv"]),
    "ine_islas": ("INE", "ine", ["islas.csv", "municipios.csv"]),
    "ine_cambios": ("INE", "ine", ["nombres.csv"]),
    "ine_provincias": ("INE", "ine", ["provincias.csv", "comunidades.csv"]),
    "ine_poblacion": ("INE", "ine", ["provincias.csv", "municipios.csv"]),
    "mjusticia_censo_judicial": ("Justicia", "justicia", ["partidos-judiciales.csv", "municipios.csv"]),
    "aemet_municipios": ("AEMET", "aemet", ["municipios.csv"]),
    "aemet_zonas": ("AEMET", "aemet", ["zonas-aviso.csv"]),
    "idescat_comarcas": ("Idescat", "comarcas", ["comarcas.csv", "municipios.csv"]),
    "aragon_comarcas": ("Aragón", "comarcas", ["comarcas.csv", "municipios.csv"]),
    "rel_comarcas": ("REL", "fuentes/", ["comarcas.csv", "municipios.csv"]),
    "eurostat_lau": ("Eurostat", "eurostat", ["municipios.csv", "codigos.csv"]),
    "wikidata": ("Wikidata", "wikidata", ["nombres.csv", "codigos.csv", "wikipedia.csv", "paises.csv"]),
    "catastro": ("Catastro", "catastro", ["municipios.csv", "codigos.csv"]),
    "ign_poblaciones": ("IGN", "ign", ["municipios.csv"]),
    "ign_limites": ("IGN", "ign", ["municipios.csv", "limites-municipios.geojson.gz"]),
    "madrid_direcciones": ("Ayto. de Madrid", "codigos_postales", POSTAL),
    "icgc_direcciones": ("ICGC", "codigos_postales", POSTAL),
    "idena_direcciones": ("IDENA", "codigos_postales", POSTAL),
    "eustat_portales": ("Eustat", "codigos_postales", POSTAL),
    "ideib_portales": ("IDEIB", "codigos_postales", POSTAL),
    "ine_callejero": ("INE", "codigos_postales", POSTAL),
    "cdau_portales": ("CDAU", "codigos_postales", POSTAL),
    "catastro_direcciones": ("Catastro", "codigos_postales", POSTAL),
}
HAND_LISTS = ["fuentes.json", "comunidades.csv", "nombres-comunidades.csv", "provincias.csv", "islas.csv", "comarcas.csv",
              "comarcas-municipios.csv", "zonas-aviso.csv", "alias.csv", "partes-bilingues.csv", "descartes-wikidata.csv",
              "paises-ue.csv", "paises-excluidos.csv"]
GENERATOR = ["__main__", "descargas", "xlsx", "construir", "exportar", "limites"]  # generator modules that read no source
LIBRARY = {  # module (Python .py and JavaScript .js): data it reads, what it offers
    "catalog": ("territorios.json", "resolve · territory · search · mentions · name · children"),
    "relation": (None, "relate_name · combine"),
    "text": (None, "normalize · display_name · slugify"),
    "geo": (None, "distances · point in polygon"),
    "catastro": (None, "parse_cadastral_reference · relate_cadastral_reference"),
    "catastro_online": ("Catastro", "locate_reference · locate_point"),
    "limits": ("limites-municipios.geojson.gz", "load_limits · locate"),
    "postal": ("codigos-postales.csv", "postal_codes · municipalities · relate_postal_code"),
}
LIBRARY_GLUE = {"__init__.py", "index.js", "node.js"}
WORKFLOWS = {"ci.yml": "CI", "generar.yml": "Generar datos", "codigos-postales.yml": "Códigos postales",
             "limites.yml": "Límites de la versión", "pages.yml": "Web de datos"}  # their names in GitHub Actions
TEXT_GROUPS = {"levels": LEVELS, "links": LINKS, "coverage": COVERAGE, "sources": SOURCES, "hand_lists": HAND_LISTS,
               "generator": GENERATOR, "workflows": WORKFLOWS}


@lru_cache(maxsize=1)
def texts() -> dict:
    """web/textos.json: each language of the website, with the status page under "estado"."""
    return json.loads(TEXTS.read_text(encoding="utf-8"))


STYLE = ["classDef done fill:#d8f0d8,stroke:#2e7d32,color:#173d17",
         "classDef todo fill:#fdecc8,stroke:#b26a00,color:#4a2c00,stroke-dasharray:4 3",
         "classDef box fill:#e6eef8,stroke:#3b6ea8,color:#14304f"]
PIE = ('%%{init: {"themeVariables": {' + ", ".join(f'"pie{n}": "{c}"' for n, c in enumerate(
    ["#4e8fd6", "#f2a33a", "#4cb08a", "#d98cb8", "#8cc8ef", "#e6794a", "#e8dc4a", "#b0b0b0"], 1))
       + ', "pieSectionTextColor": "#111111", "pieStrokeColor": "#ffffff", "pieOpacity": "1"}}}%%')
TABS = {"summary": ["levels", "progress"], "coverage": ["coverage"], "communities": ["communities"], "repo": ["repo"],
        "sources": ["sources"], "files": ["files"], "library": ["library"]}
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs"


def _num(n: int | None, lang: str) -> str:
    if n is None:
        return ""
    return f"{n:,}" if lang == "en" else f"{n:,}".replace(",", ".")


def _size(n: int, lang: str) -> str:
    text = f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{max(1, round(n / 1024))} KB"
    return text if lang == "en" else text.replace(".", ",")


def _rows(path: Path) -> int:
    if path.suffix == ".csv":
        with path.open(encoding="utf-8") as f:
            return sum(1 for _ in f) - 1
    if path.name == "territorios.json":
        return len(json.loads(path.read_text(encoding="utf-8"))["territories"])
    return 0


@lru_cache(maxsize=None)
def _csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _pct(n: int, total: int, lang: str) -> str:
    if not total:
        return ""
    text = "100" if n == total else f"{min(100 * n / total, 99.9):.1f}"
    return (text if lang == "en" else text.replace(".", ",")) + " %"


def _node(name: str) -> str:
    return re.sub(r"\W", "_", name)


@lru_cache(maxsize=None)
def _territories(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["territories"] if path.exists() else []


def _graph(territories: list[dict]):
    """Counts per level, parent edges and link edges (with how many territories carry the link)."""
    level_of = {t["id"]: t["level"] for t in territories}
    counts, parents, links = {}, {}, {}
    for t in territories:
        counts[t["level"]] = counts.get(t["level"], 0) + 1
        if t.get("parent") in level_of:
            key = (level_of[t["parent"]], t["level"])
            parents[key] = parents.get(key, 0) + 1
        for field, value in t.items():
            if field in ("id", "parent") or not isinstance(value, str) or value not in level_of:
                continue
            key = (t["level"], field, level_of[value])
            links[key] = links.get(key, 0) + 1
    return counts, parents, links


def _workflow_triggers(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    inline = re.search(r"^on:[ \t]*([^\s#].*)$", text, re.M)  # on: push · on: [push, pull_request]
    if inline:
        triggers = re.findall(r"[\w-]+", inline.group(1))
    else:
        block = re.search(r"^on:[ \t]*\n((?:[ \t]+.*\n|\n)+)", text, re.M)
        triggers = re.findall(r"^  (\w+):", block.group(1), re.M) if block else []
    return triggers, re.findall(r"""cron:\s*["']([^"']+)["']""", text)


def _pending(lang: str) -> list[str]:
    doc = ROOT / "docs" / ("design.md" if lang == "en" else "diseno.md")
    text = doc.read_text(encoding="utf-8")
    section = re.search(r"^## 13\..*?\n(.*?)(?=^## )", text, re.M | re.S)
    items = []
    for bullet in re.findall(r"^- (.*?)(?=^- |\Z)", section.group(1) if section else "", re.M | re.S):
        # The first sentence, as written (with its parentheses, such as «(hecho)»); a long one keeps what comes
        # before its colon, if that says enough, or is cut.
        sentence = re.split(r"(?<=[.;])\s", " ".join(bullet.split()))[0].rstrip(".;")
        lead, sep, _ = sentence.partition(": ")
        if len(sentence) > 140 and sep and len(lead) >= 30:
            sentence = lead
        items.append(sentence if len(sentence) <= 140 else sentence[:137].rsplit(" ", 1)[0] + "…")
    return items


def _published() -> list[str]:
    """Files of datos/ that the website copies (FILES in web/construir.py, which imports this module)."""
    try:
        from . import construir
    except ImportError:  # run as a script: python web/estado.py
        import construir
    return construir.FILES


def problems() -> list[str]:
    """What exists in the repository but is not on the map."""
    out = []
    fuentes = json.loads((ROOT / "fuentes" / "fuentes.json").read_text(encoding="utf-8"))
    out += [f"fuente sin declarar en SOURCES: {k}" for k in fuentes if k not in SOURCES]
    out += [f"fuente declarada que ya no está en fuentes.json: {k}" for k in SOURCES if k not in fuentes]
    hand = {p.name for p in (ROOT / "fuentes").iterdir() if p.suffix in (".csv", ".json")}
    out += [f"lista sin declarar en HAND_LISTS: fuentes/{k}" for k in sorted(hand - set(HAND_LISTS))]
    readers = {s[1] for s in SOURCES.values()}
    for p in sorted((ROOT / "generador").glob("*.py")):
        if p.stem not in readers and p.stem not in GENERATOR and p.stem != "__init__":
            out.append(f"módulo del generador sin declarar: generador/{p.name}")
    for p in sorted((ROOT / "python" / "territorios_es").glob("*.py")) + sorted((ROOT / "js").glob("*.js")):
        if p.stem not in LIBRARY and p.name not in LIBRARY_GLUE:
            out.append(f"módulo de la librería sin declarar en LIBRARY: {p.relative_to(ROOT)}")
    for mod in LIBRARY:
        for path in (ROOT / "python" / "territorios_es" / f"{mod}.py", ROOT / "js" / f"{mod}.js"):
            if not path.exists():
                out.append(f"módulo de LIBRARY que no existe: {path.relative_to(ROOT)}")
    for mod in GENERATOR:
        if not (ROOT / "generador" / f"{mod}.py").exists():
            out.append(f"módulo de GENERATOR que no existe: generador/{mod}.py")
    workflows = {p.name for p in (ROOT / ".github" / "workflows").glob("*.y*ml")}
    out += [f"workflow sin declarar en WORKFLOWS: {name}" for name in sorted(workflows - set(WORKFLOWS))]
    out += [f"workflow de WORKFLOWS que no existe: {name}" for name in sorted(set(WORKFLOWS) - workflows)]
    out += [f"lista de HAND_LISTS que no existe: fuentes/{name}" for name in HAND_LISTS if not (ROOT / "fuentes" / name).exists()]
    for path in (ROOT / "datos" / "territorios.json", ROOT / "pruebas" / "datos" / "territorios.json"):
        for t in _territories(path):
            if t["level"] not in LEVELS:
                out.append(f"nivel sin nombre en LEVELS: {t['level']}")
                break
            extra = [f for f, v in t.items() if isinstance(v, str) and v.startswith("es:") and f not in ("id", "parent")
                     and f not in LINKS]
            if extra:
                out.append(f"enlace sin nombre en LINKS: {extra[0]} ({t['level']})")
                break
    for path in (ROOT / "datos" / "municipios.csv", ROOT / "pruebas" / "datos" / "municipios.csv"):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        out += [f"columna de municipios.csv sin declarar en COVERAGE: {c}" for c in header
                if c not in COVERAGE and c not in MUNICIPAL_PLAIN and not c.startswith("name_")]
    es = texts()["es"]["estado"]
    for group, keys in TEXT_GROUPS.items():
        out += [f"falta el texto de {group}.{k} en web/textos.json (estado)" for k in keys if k not in es[group]]
    published = _published()
    for path in sorted((ROOT / "datos").glob("*.*")):
        if path.suffix in (".csv", ".json") and path.name not in published:
            out.append(f"datos/{path.name} no se publica en la web (FILES de web/construir.py)")
    return sorted(set(out))


# Blocks: ("p", text) · ("mermaid", code) · ("table", header, aligns, rows) · ("details", summary, blocks)
# · ("list", items[, lang]). A diagram may carry an accessible title: ("mermaid", code, title). Text is Markdown with `code`, **bold** and [links]; a table cell may be ("bar", n, total).

def collect(lang: str, datos: Path, html: bool = False):
    """Cards and sections of the status page, from datos/ (the same numbers for Markdown and HTML)."""
    t = texts()[lang]["estado"]
    repo = f"{REPO}/blob/main/" if html else "../"
    fixture = ROOT / "pruebas" / "datos"
    manifest_path = datos / "manifiesto.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    retrieved = {k: v.get("retrieved", "") for k, v in manifest.get("sources", {}).items()}
    wikidata = [v for s, v in retrieved.items() if s.startswith("wikidata_")]
    if wikidata:
        retrieved["wikidata"] = max(wikidata)
    territories = _territories(datos / "territorios.json")
    counts, parents, links = _graph(territories)
    test = _graph(_territories(fixture / "territorios.json"))
    readers = sorted({s[1] for s in SOURCES.values() if s[1] != "fuentes/"})
    data_files = sorted({f for s in SOURCES.values() for f in s[2] if f.endswith((".csv", ".json"))}
                        | {"territorios.json", "manifiesto.json"}
                        | {p.name for p in datos.glob("*") if p.suffix in (".csv", ".json")}
                        | {p.name for p in fixture.glob("*") if p.suffix in (".csv", ".json")})
    present = [f for f in data_files if (datos / f).exists()]
    orgs = sorted({s[0] for s in SOURCES.values()})
    levels = [lv for lv in LEVELS if lv in counts or lv in test[0]]
    munis = _csv(datos / "municipios.csv")
    postal = _csv(datos / "codigos-postales.csv")
    pending = _pending(lang)
    sections = {}

    # Territories
    code = ["flowchart TB"]
    for lv in levels:
        if lv in counts:
            code.append(f'  {lv}["{t["levels"][lv]}<br>{_num(counts[lv], lang)}"]:::done')
        else:
            code.append(f'  {lv}["{t["levels"][lv]}<br>{t["pending_gen"]} · {t["test"]}: {_num(test[0][lv], lang)}"]:::todo')
    def only_in_test(*lvs):  # a relation with a level that the generator can build but datos/ does not have yet
        return not all(lv in counts for lv in lvs)
    code += [f"  {parent} --> {child}" for parent, child in sorted(set(parents) | {e for e in test[1] if only_in_test(*e)})]
    for src, field, dst in sorted(set(links) | {e for e in test[2] if only_in_test(e[0], e[2])}):
        if field == "capital":
            continue
        n = links.get((src, field, dst))
        label = t["links"][field] + (f": {_num(n, lang)} {t['of']} {_num(counts.get(src), lang)}" if n else "")
        code.append(f'  {src} -.->|"{label}"| {dst}')
    sections["levels"] = [("p", t["levels_text"]), ("mermaid", "\n".join(code + [f"  {s}" for s in STYLE]), t["s_levels"])]

    # Coverage
    with_cp = {r["id"] for r in postal}
    total = len(munis)
    columns = set(munis[0]) if munis else set()
    test_columns = set(next(iter(_csv(fixture / "municipios.csv")), {}))
    rows, missing_rows = [], []
    for col in COVERAGE:
        where = t["coverage_where"].get(col)
        label = t["coverage"][col] + (f" · {where}" if where else "")
        if col != "postal_code" and col not in columns:
            if col in test_columns:
                rows.append([label, t["pending_gen"], "", ""])
            continue
        scope = [r for r in munis if SCOPE.get(col, bool)(r)]
        has = (lambda r: r["id"] in with_cp) if col == "postal_code" else (lambda r: r[col])
        missing = [r for r in scope if not has(r)]
        n = len(scope) - len(missing)
        rows.append([label, f"{_num(n, lang)} {t['of']} {_num(len(scope), lang)}", _pct(n, len(scope), lang),
                     ("bar", n, len(scope))])
        if 0 < len(missing) <= MISSING_LIST:
            missing_rows.append([label, ", ".join(f"{r['display']} ({r['ine']})" for r in missing)])
    blocks = [("p", t["coverage_text"]), ("table", [t["datum"], t["municipalities"], "%", ""], "lrrl", rows)]
    if missing_rows:
        blocks.append(("details", t["missing_details"].format(n=MISSING_LIST),
                       [("table", [t["datum"], t["municipalities"]], "ll", missing_rows)]))
    deciding = {}
    for r in postal:
        deciding.setdefault(r["id"], r["source"])
    by_source = {}
    for source in deciding.values():
        by_source[source] = by_source.get(source, 0) + 1
    names = {}
    for r in _csv(datos / "nombres.csv"):
        if r["kind"] == "lang" and r["source"] == "wikidata":
            names[r["lang"]] = names.get(r["lang"], 0) + 1
    if by_source:
        blocks.append(("p", f"**{t['pie_cp']}**"))
        blocks.append(("mermaid", "\n".join([PIE, "pie showData"] + [
            f'  "{CP_SOURCES.get(k, k)}" : {n}' for k, n in sorted(by_source.items(), key=lambda x: -x[1])]), t["pie_cp"]))
    if names:
        blocks.append(("p", f"**{t['pie_names']}**"))
        blocks.append(("mermaid", "\n".join([PIE, "pie showData"] + [
            f'  "{t["lang_names"].get(k, k)}" : {n}' for k, n in sorted(names.items(), key=lambda x: -x[1])]), t["pie_names"]))
    sections["coverage"] = blocks

    # Communities
    layers = [c for c in ("partido", "zona_aviso", "isla", "comarca") if c in columns]
    rows = []
    for com in _csv(datos / "comunidades.csv"):
        mine = [r for r in munis if r["autonomia"] == com["ine"]]
        people = sum(int(r["population"]) for r in mine if r["population"])
        cells = [_num(len({r[c] for r in mine if r[c]}), lang) if any(r[c] for r in mine) else "—" for c in layers]
        sources = {}
        for r in mine:
            if r["id"] in deciding:
                sources[deciding[r["id"]]] = sources.get(deciding[r["id"]], 0) + 1
        decide = " · ".join(f"{CP_SOURCES.get(k, k)} {_num(n, lang)}" for k, n in sorted(sources.items(), key=lambda x: -x[1]))
        rows.append([com.get(f"name_{lang}") or com["name_es"], _num(len(mine), lang), _num(people, lang),
                     *cells, _pct(sum(sources.values()), len(mine), lang), decide])
    sections["communities"] = [("table", [t["community"], t["municipalities"], t["population"],
                                          *[t[f"col_{c}"] for c in layers], t["with_cp"], t["cp_source"]],
                                "lrr" + "r" * len(layers) + "rl", rows)]

    # Repository
    code = ["flowchart TB",
            f'  ext(["{len(SOURCES)} {t["ext"]}<br>{" · ".join(orgs)}"])',
            f'  hand[/"fuentes/<br>{len(HAND_LISTS)} {t["hand"]}"/]',
            f'  descargas["descargas<br>{t["generator"]["descargas"]}"]',
            f'  readers["{t["readers"]}<br>{" · ".join(readers)}"]',
            f'  construir["construir<br>{t["generator"]["construir"]}"]',
            f'  exportar["exportar<br>{t["generator"]["exportar"]}"]',
            f'  limites["limites<br>{t["generator"]["limites"]}"]',
            f'  datos[("datos/<br>{len(present)} {t["data"]}")]',
            f'  geo[("limites-municipios.geojson.gz<br>{t["attached"]}")]',
            f'  report["{t["report"]}"]',
            f'  lib["{t["lib"]}"]', f'  web["{t["web"]}"]', f'  users(["{t["users"]}"])',
            f'  fixture[("pruebas/datos/<br>{t["fixture"]}")]', f'  tests["{t["tests"]}"]',
            "  ext --> descargas --> readers --> construir --> exportar --> datos",
            "  hand --> construir", "  readers --> limites --> geo", "  construir --> report",
            "  datos --> lib", "  geo --> lib", "  datos --> web", "  lib --> users", "  web --> users",
            "  construir --> fixture --> tests", "  lib --> tests"]
    code += [f'  wf_{_node(name)}{{{{"{title}"}}}}' for name, title in WORKFLOWS.items()]
    code += ["  wf_generar_yml -.-> descargas", "  wf_codigos_postales_yml -.-> readers", "  wf_limites_yml -.-> limites",
             "  wf_pages_yml -.-> web", "  wf_ci_yml -.-> tests",
             "  class datos,geo,fixture done", "  class ext,hand,users box", *[f"  {s}" for s in STYLE]]
    workflows = []
    for name, title in WORKFLOWS.items():
        triggers, crons = _workflow_triggers(ROOT / ".github" / "workflows" / name)
        when = ", ".join(t["triggers"].get(x, x) for x in triggers) + "".join(f" (`{c}`)" for c in crons)
        workflows.append([f"[{title}]({repo}.github/workflows/{name})", when, t["workflows"][name]])
    modules = [[f"`{mod}`", "; ".join(t["sources"][k] for k, s in SOURCES.items() if s[1] == mod)] for mod in readers]
    modules += [[f"`{mod}`", t["generator"][mod]] for mod in GENERATOR]
    sections["repo"] = [("p", t["flow_text"]), ("mermaid", "\n".join(code), t["s_repo"]),
                        ("details", t["workflows_details"].format(n=len(WORKFLOWS)),
                         [("table", [t["workflow"], t["when"], t["what"]], "lll", workflows)]),
                        ("details", t["generator_details"].format(n=len(modules)),
                         [("table", [t["gen_module"], t["what"]], "ll", modules)])]

    # Sources
    edges = sorted({(s[0], f) for s in SOURCES.values() for f in s[2]})
    code = ["flowchart LR"] + [f'  o_{_node(org)}(["{org}"]):::box' for org in orgs]
    for f in sorted({f for _, f in edges}):
        cls = "box" if f.endswith(".gz") else "done" if (datos / f).exists() else "todo"
        code.append(f'  f_{_node(f)}[("{f}")]:::{cls}')
    code += [f"  o_{_node(o)} --> f_{_node(f)}" for o, f in edges] + [f"  {s}" for s in STYLE]
    rows = [[f"`{key}`", org, "`fuentes/`" if module == "fuentes/" else f"`generador/{module}.py`", t["sources"][key],
             retrieved.get(key) or t["never"]] for key, (org, module, _) in SOURCES.items()]
    sections["sources"] = [("p", t["sources_text"]), ("mermaid", "\n".join(code), t["s_sources"]),
                           ("details", t["sources_details"].format(n=len(SOURCES)),
                            [("table", [t["source"], t["org"], t["module"], t["gives"], t["retrieved"]], "lllll", rows)])]

    # Files
    rows, published = [], _published()
    database = quote(f"{PAGES}/datos/{DATABASE}", safe="")
    for f in data_files:
        here = (datos / f).exists()
        path = datos / f if here else fixture / f
        link = (f"../../datos/{f}" if html else f"../datos/{f}") if here else None
        name = f"[`{f}`]({link})" if link else f"`{f}`"
        explore = (f"[{t['explore']}]({DATASETTE}{database}#/{Path(DATABASE).stem}/{Path(f).stem})"
                   if here and f.endswith(".csv") and f in published else "")
        rows.append([name, _num(_rows(path), lang) if path.exists() and f != "manifiesto.json" else "",
                     _size(path.stat().st_size, lang) if here else "",
                     ", ".join(sorted({s[0] for s in SOURCES.values() if f in s[2]})),
                     t["in_data"] if here else t["only_test"], explore])
    hand = [[f"`{name}`", _num(_rows(ROOT / "fuentes" / name), lang) if name.endswith(".csv") else "",
             t["hand_lists"][name]] for name in HAND_LISTS]
    sections["files"] = [("p", t["files_text"]),
                         ("table", [t["file"], t["rows"], t["size"], t["fed_by"], t["status"], ""], "lrrlll", rows),
                         ("details", t["hand_details"].format(n=len(HAND_LISTS)),
                          [("table", [t["list"], t["rows"], t["gives"]], "lrl", hand)])]

    # Library
    code = ["flowchart LR"]
    for d in sorted({d for d, _ in LIBRARY.values() if d}):
        code.append(f'  d_{_node(d)}[("{d}")]:::' + ("box" if d == "Catastro" or d.endswith(".gz") else "done"))
    for mod, (d, offers) in LIBRARY.items():
        net = f" · {t['net']}" if mod == "catastro_online" else ""
        code.append(f'  m_{mod}["{mod}{net}<br>{offers}"]')
        if d:
            code.append(f"  d_{_node(d)} --> m_{mod}")
    code += ["  m_text --> m_catalog", "  m_catalog --> m_relation", "  m_geo --> m_limits", *[f"  {s}" for s in STYLE]]
    sections["library"] = [("p", t["library_text"]), ("mermaid", "\n".join(code), t["s_library"])]

    # Progress
    done = [t["levels"][lv] for lv in levels if lv in counts]
    todo = [t["levels"][lv] for lv in levels if lv not in counts]
    sections["progress"] = [("list", [f"**{t['done_levels']}**: {', '.join(done) or t['none']}.",
                                      f"**{t['todo_levels']}**: {', '.join(todo) or t['none']}."]),
                            ("p", t["progress_text"].format(repo=repo)),
                            ("list", pending, None if lang in ("es", "en") else "es")]

    last = max((v for v in retrieved.values() if v), default="")
    cards = [(_num(len(territories), lang), t["c_territories"]),
             (f"{len(done)} {t['of']} {len(levels)}", t["c_levels"]),
             (_num(counts.get("municipality", 0), lang), t["c_municipalities"]),
             (str(len(SOURCES)), f"{t['c_sources']} {last}"),
             (_num(len(postal), lang), t["c_postal"]),
             (str(len(pending)), t["c_pending"])]
    return cards, sections


def _mermaid(block) -> str:
    """The diagram, with its accessible title (accTitle) after the line that names its type."""
    code = block[1]
    if len(block) > 2 and block[2]:
        lines = code.split("\n")
        at = next(i for i, line in enumerate(lines) if line.startswith(("flowchart", "pie")))
        code = "\n".join(lines[:at + 1] + ["  accTitle: " + re.sub(r"[\n:]", " ", block[2])] + lines[at + 1:])
    return code


def _anchor(title: str) -> str:
    """An ASCII id for a tab: the browser would encode accents in the address and the tab would not be found."""
    return _slug(unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode())


def _slug(title: str) -> str:
    return re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def _md_cell(cell) -> str:
    if isinstance(cell, tuple):
        _, n, total = cell
        filled = round(20 * n / total) if total else 0
        filled = 19 if filled == 20 and n < total else 1 if filled == 0 and n else filled
        return "`" + "█" * filled + "░" * (20 - filled) + "`"
    return str(cell).replace("|", "\\|")


def _md_blocks(blocks) -> list[str]:
    out = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            out += [block[1], ""]
        elif kind == "mermaid":
            out += ["```mermaid", _mermaid(block), "```", ""]
        elif kind == "list":
            out += [f"- {item}" for item in block[1]] + [""]
        elif kind == "table":
            _, header, aligns, rows = block
            out.append("| " + " | ".join(header) + " |")
            out.append("|" + "|".join("---:" if a == "r" else "---" for a in aligns) + "|")
            out += ["| " + " | ".join(_md_cell(c) for c in row) + " |" for row in rows] + [""]
        elif kind == "details":
            out += ["<details>", f"<summary>{_md_inline_html(block[1])}</summary>", ""] + _md_blocks(block[2]) + ["</details>", ""]
    return out


def _md_inline_html(text: str) -> str:
    """Markdown inside <summary> is not rendered by GitHub: turn `code` into <code>."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def markdown(lang: str, datos: Path) -> str:
    t = texts()[lang]["estado"]
    cards, sections = collect(lang, datos)
    order = [s for tab in TABS.values() for s in tab]
    order = order[:1] + [s for s in order[1:] if s != "progress"] + ["progress"]
    lines = [f"# {t['title']}", "", t["generated_md"].format(pages=PAGES), "",
             "| " + " | ".join(f"**{value}**" for value, _ in cards) + " |",
             "|" + "|".join(":---:" for _ in cards) + "|",
             "| " + " | ".join(label for _, label in cards) + " |", "",
             f"**{t['index']}**: " + " · ".join(f"[{t['s_' + s]}](#{_slug(t['s_' + s])})" for s in order), ""]
    for s in order:
        lines += [f"## {t['s_' + s]}", ""] + _md_blocks(sections[s])
    return "\n".join(lines).rstrip("\n") + "\n"


def _inline(text: str) -> str:
    text = escape(str(text), quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def _html_cell(cell, lang: str) -> str:
    if isinstance(cell, tuple):
        _, n, total = cell
        width = 100 * n / total if total else 0
        return f'<span class="bar" title="{_pct(n, total, lang)}"><i style="width:{width:.1f}%"></i></span>'
    return _inline(cell)


def _html_blocks(blocks, lang: str) -> str:
    out = []
    for block in blocks:
        kind = block[0]
        if kind == "p":
            out.append(f"<p>{_inline(block[1])}</p>")
        elif kind == "mermaid":
            t = texts()[lang]["estado"]
            tools = "".join(f'<button type="button" data-zoom="{k}" title="{escape(t["zoom_" + k])}" '
                            f'aria-label="{escape(t["zoom_" + k])}">{icon}</button>'
                            for k, icon in (("in", "+"), ("out", "−"), ("fit", "↔"), ("full", "⛶")))
            out.append(f'<div class="diagram"><div class="tools">{tools}</div>'
                       f'<div class="canvas"><pre class="mermaid">{escape(_mermaid(block), quote=False)}</pre></div></div>')
        elif kind == "list":
            lang_attr = f' lang="{block[2]}"' if len(block) > 2 and block[2] else ""
            out.append(f"<ul{lang_attr}>" + "".join(f"<li>{_inline(item)}</li>" for item in block[1]) + "</ul>")
        elif kind == "table":
            _, header, aligns, rows = block
            head = "".join(f'<th class="{a}">{_inline(h)}</th>' for h, a in zip(header, aligns))
            body = "".join("<tr>" + "".join(f'<td class="{a}">{_html_cell(c, lang)}</td>' for c, a in zip(row, aligns))
                           + "</tr>" for row in rows)
            out.append(f'<div class="table"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
        elif kind == "details":
            out.append(f"<details><summary>{_inline(block[1])}</summary>{_html_blocks(block[2], lang)}</details>")
    return "".join(out)


CSS = """.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:10px;margin:1.2em 0 .5em}
.card{border:1px solid var(--line);border-radius:8px;padding:.6em .8em}.card b{display:block;font-size:1.5rem;line-height:1.25}
.card span{display:block;color:var(--muted);font-size:.85rem;line-height:1.35}
.tabs{display:flex;flex-wrap:wrap;gap:2px;border-bottom:1px solid var(--line);margin-top:1.4em;position:sticky;top:0;
background:var(--bg);z-index:1;padding-top:6px}
.tabs a{padding:.45em .8em;text-decoration:none;color:var(--muted);border:1px solid transparent;border-radius:6px 6px 0 0;margin-bottom:-1px}
.tabs a[aria-current=true]{color:var(--fg);font-weight:600;border-color:var(--line);border-bottom-color:var(--bg);background:var(--bg)}
.panel>h2:first-child{margin-top:1em}.diagram{position:relative;margin:1em 0;border:1px solid var(--line);border-radius:8px;
background:var(--bg)}.canvas{overflow:auto;max-height:80vh;cursor:grab;padding:8px}.canvas.drag{cursor:grabbing;user-select:none}
pre.mermaid{background:none;text-align:center;margin:0}.tools{position:absolute;top:6px;right:6px;display:flex;gap:4px;z-index:1}
.tools button{font:inherit;min-width:2em;padding:.1em .4em;border:1px solid var(--line);border-radius:5px;background:var(--bg);
color:var(--fg);cursor:pointer}.diagram:fullscreen{border:0;border-radius:0;overflow:hidden}
.diagram:fullscreen .canvas{max-height:none;height:100vh}
th.r,td.r{text-align:right;white-space:nowrap}
.bar{display:inline-block;width:9rem;max-width:30vw;height:.65em;background:var(--line);border-radius:4px;overflow:hidden;
vertical-align:middle}.bar i{display:block;height:100%;background:var(--accent)}
details{margin:1em 0}summary{cursor:pointer;font-weight:600}"""

SCRIPT = """(() => {
// Tabs, zoom and dragging work even if Mermaid (jsDelivr) does not load: the diagrams then stay as text.
const dark = matchMedia("(prefers-color-scheme: dark)").matches;
const mermaid = import("%s").then(m => {
  m.default.initialize({startOnLoad: false, theme: dark ? "dark" : "default", securityLevel: "strict"});
  return m.default;
}).catch(() => null);
const tabs = [...document.querySelectorAll(".tabs a")], panels = [...document.querySelectorAll(".panel")];
async function show(id) {
  if (!panels.some(p => p.id === "tab-" + id)) id = panels[0].id.slice(4);
  for (const p of panels) p.hidden = p.id !== "tab-" + id;
  for (const a of tabs) a.hash === "#" + id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current");
  const nodes = [...document.getElementById("tab-" + id).querySelectorAll("pre.mermaid:not([data-processed])")];
  const m = await mermaid;
  if (m && nodes.length) await m.run({nodes});
}
function zoom(box, how) {
  const svg = box.querySelector("svg");
  if (how === "full") { document.fullscreenElement ? document.exitFullscreen() : box.requestFullscreen?.(); return; }
  if (!svg) return;
  const natural = svg.viewBox.baseVal.width || svg.getBoundingClientRect().width;
  const now = svg.getBoundingClientRect().width;
  if (how === "fit") { svg.style.width = ""; svg.style.maxWidth = svg.dataset.max || ""; return; }
  if (!svg.dataset.max) svg.dataset.max = svg.style.maxWidth;
  svg.style.maxWidth = "none";
  svg.style.width = Math.max(natural * 0.2, Math.min(natural * 6, now * (how === "in" ? 1.4 : 1 / 1.4))) + "px";
}
document.addEventListener("click", e => {
  const b = e.target.closest(".tools button");
  if (b) zoom(b.closest(".diagram"), b.dataset.zoom);
});
for (const c of document.querySelectorAll(".canvas")) {
  let x = 0, y = 0, on = false;
  c.addEventListener("pointerdown", e => { on = true; x = e.clientX; y = e.clientY; c.classList.add("drag"); });
  addEventListener("pointerup", () => { on = false; c.classList.remove("drag"); });
  c.addEventListener("pointermove", e => {
    if (!on) return;
    c.scrollLeft -= e.clientX - x; c.scrollTop -= e.clientY - y; x = e.clientX; y = e.clientY;
  });
}
for (const a of tabs) a.addEventListener("click", e => { e.preventDefault(); history.replaceState(null, "", a.hash); show(a.hash.slice(1)); });
addEventListener("hashchange", () => show(location.hash.slice(1)));
show(location.hash.slice(1));
})();""" % MERMAID


def page(lang: str, datos: Path) -> str:
    """The status page of the website (<lang>/estado/), with tabs, in every language of the website."""
    everything = texts()
    web, t = everything[lang], everything[lang]["estado"]
    cards, sections = collect(lang, datos, html=True)
    tab_title = {"summary": t["summary_tab"], **{k: t["s_" + k] for k in TABS if k != "summary"}}
    langs = " · ".join(f'<a href="../../{c}/estado/" hreflang="{c}" lang="{c}"' + (' aria-current="page"' if c == lang else "")
                       + f">{escape(other['language_name'])}</a>" for c, other in everything.items())
    nav = (f'<nav class="top"><a href="../">{escape(web["nav_data"])}</a><strong>{escape(web["nav_status"])}</strong>'
           f'<a href="{REPO}">GitHub</a><span class="langs">{langs}</span></nav>')
    review = f'<p class="note">{escape(web["review"])}</p>' if web.get("review") else ""
    panels = []
    for tab, names in TABS.items():
        body = "".join(f"<h2>{escape(t['s_' + s])}</h2>{_html_blocks(sections[s], lang)}" for s in names)
        panels.append(f'<section class="panel" id="tab-{_anchor(tab_title[tab])}" aria-label="{escape(tab_title[tab])}">{body}</section>')
    tabs = "".join(f'<a href="#{_anchor(tab_title[tab])}">{escape(tab_title[tab])}</a>' for tab in TABS)
    card_html = "".join(f"<div class=\"card\"><b>{escape(v)}</b><span>{_inline(label)}</span></div>" for v, label in cards)
    alternates = "".join(f'<link rel="alternate" hreflang="{c}" href="../../{c}/estado/">' for c in everything)
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(t["title"])}</title>'
            f'{alternates}<link rel="stylesheet" href="../../estilo.css"><style>{CSS}</style></head><body>'
            f'<header>{nav}<h1>{escape(t["title"])}</h1>'
            f'<p class="sub">{_inline(t["generated_html"].format(repo=REPO + "/blob/main/"))}</p></header>'
            f'<main>{review}<div class="cards">{card_html}</div><nav class="tabs" aria-label="{escape(t["index"])}">{tabs}</nav>'
            f'{"".join(panels)}</main>'
            f'<footer><p><a href="{REPO}">GitHub</a>. {escape(web["licence_code"])}</p></footer>'
            f'<script>{SCRIPT}</script></body></html>\n')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--datos", type=Path, default=ROOT / "datos")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    missing = problems()
    stale = [p for lang, p in OUT.items() if not p.exists() or p.read_text(encoding="utf-8") != markdown(lang, args.datos)]
    if args.check:
        for line in missing:
            print(f"web/estado.py: {line}", file=sys.stderr)
        for p in stale:
            print(f"{p.relative_to(ROOT)} no está al día: python web/estado.py", file=sys.stderr)
        return 1 if missing or stale else 0
    for line in missing:
        print(f"aviso: {line}", file=sys.stderr)
    for lang, p in OUT.items():
        p.write_text(markdown(lang, args.datos), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
