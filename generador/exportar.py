"""Writes datos/: territorios.json (one territory per line), CSV tables and the manifest.
Every CSV except wikipedia.csv is derived from territorios.json, so --check can rebuild them."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

from territorios_es.catalog import Catalog

from .construir import UI_LANGS

# Where each kind of datum comes from (design §5). Used for the provenance columns.
CODE_SOURCES = {
    "ine:autonomia": "ine", "ine:provincia": "ine", "ine:municipio": "ine", "ine:municipio:dc": "ine",
    "iso3166-1:alpha2": "wikidata", "iso3166-1:alpha3": "wikidata", "iso3166-1:numeric": "wikidata",
    "iso3166-2": "fuentes", "nuts": "fuentes", "lau": "eurostat", "dgc:municipio": "catastro", "ign:bddae": "ign",
    "wikidata": "wikidata", "osm:relation": "wikidata", "geonames": "wikidata",
}


def _name_source(level: str, kind: str, lang: str | None = None) -> str:
    if kind == "official":
        return "wikidata" if level == "country" else ("ine" if level == "municipality" else "fuentes")
    if kind in ("display", "parts", "short", "aliases"):
        return "derivado" if kind == "display" and level == "municipality" else "fuentes"
    return "fuentes" if level == "autonomous_community" and lang in UI_LANGS else "wikidata"


def territories_json(data: dict) -> str:
    head = json.dumps({k: v for k, v in data.items() if k != "territories"}, ensure_ascii=False)[:-1]
    lines = [json.dumps(t, ensure_ascii=False, separators=(",", ":")) for t in data["territories"]]
    return head + ',"territories":[\n' + ",\n".join(lines) + "\n]}\n"


def _table(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(["" if v is None else v for v in row] for row in rows)
    return out.getvalue()


def tables(data: dict) -> dict[str, str]:
    """CSV files derived from territorios.json."""
    catalog = Catalog(data)
    by_level: dict[str, list[dict]] = {}
    for t in data["territories"]:
        by_level.setdefault(t["level"], []).append(t)
    names = lambda t: [catalog.name(t["id"], lang) for lang in UI_LANGS]
    name_cols = [f"name_{lang}" for lang in UI_LANGS]
    code = lambda t, system: t["codes"].get(system)
    files = {}
    files["paises.csv"] = _table(
        ["id", "alpha2", "alpha3", "numeric", "wikidata", "in_eu", "in_eea", *name_cols],
        [[t["id"], code(t, "iso3166-1:alpha2"), code(t, "iso3166-1:alpha3"), code(t, "iso3166-1:numeric"),
          code(t, "wikidata"), int(t["eu"]) if "eu" in t else None, int(t["eea"]) if "eea" in t else None, *names(t)]
         for t in by_level.get("country", [])])
    files["comunidades.csv"] = _table(
        ["id", "ine", "subtype", "iso3166_2", "nuts1", "nuts2", "wikidata", "osm_relation", "geonames",
         "official", "display", *name_cols, *[f"short_{lang}" for lang in UI_LANGS], "time_zone"],
        [[t["id"], code(t, "ine:autonomia"), t["subtype"], code(t, "iso3166-2"), t["nuts1"], code(t, "nuts"),
          code(t, "wikidata"), code(t, "osm:relation"), code(t, "geonames"), t["names"]["official"],
          t["names"]["display"], *names(t), *[catalog.name(t["id"], lang, short=True) for lang in UI_LANGS],
          t["time_zone"]] for t in by_level.get("autonomous_community", [])])
    files["provincias.csv"] = _table(
        ["id", "ine", "autonomia", "iso3166_2", "nuts3", "wikidata", "osm_relation", "geonames",
         "official", "display", *name_cols, "time_zone"],
        [[t["id"], code(t, "ine:provincia"), t["parent"].rsplit(":", 1)[1], code(t, "iso3166-2"), code(t, "nuts"),
          code(t, "wikidata"), code(t, "osm:relation"), code(t, "geonames"), t["names"]["official"],
          t["names"]["display"], *names(t), t["time_zone"]] for t in by_level.get("province", [])])
    files["municipios.csv"] = _table(
        ["id", "ine", "ine_dc", "dgc", "bddae", "provincia", "autonomia", "lau", "nuts3", "wikidata",
         "osm_relation", "geonames", "official", "display", *name_cols, "population", "area_km2", "capital",
         "lon", "lat", "altitude", "time_zone", "slug"],
        [[t["id"], code(t, "ine:municipio"), code(t, "ine:municipio:dc"), code(t, "dgc:municipio"),
          code(t, "ign:bddae"), t["parent"].rsplit(":", 1)[1], catalog.ancestors(t["id"])[1].rsplit(":", 1)[1],
          code(t, "lau"), t.get("nuts3"), code(t, "wikidata"), code(t, "osm:relation"), code(t, "geonames"),
          t["names"]["official"], t["names"]["display"], *names(t), t.get("stats", {}).get("population"),
          t.get("stats", {}).get("area_km2"), *[t.get("capital", {}).get(k) for k in ("name", "lon", "lat", "altitude")],
          t["time_zone"], t["slug"]]
         for t in by_level.get("municipality", [])])
    files["codigos.csv"] = _table(
        ["id", "system", "code", "source"],
        [[t["id"], system, value, CODE_SOURCES.get(system, "")]
         for t in data["territories"] for system, value in t["codes"].items()])
    rows = []
    for t in data["territories"]:
        n, level = t["names"], t["level"]
        rows.append([t["id"], "official", "", n["official"], _name_source(level, "official")])
        rows.append([t["id"], "display", "", n["display"], _name_source(level, "display")])
        for kind in ("parts", "lang", "short"):
            for lang, value in n.get(kind, {}).items():
                rows.append([t["id"], kind, lang, value, _name_source(level, kind, lang)])
        for alias in n.get("aliases", []):
            rows.append([t["id"], f"alias:{alias['kind']}", alias["lang"], alias["name"], "fuentes"])
    files["nombres.csv"] = _table(["id", "kind", "lang", "name", "source"], rows)
    return files


def wikipedia_csv(articles: list[list[str]]) -> str:
    rows = [[i, lang, title, f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"]
            for i, lang, title in sorted(articles)]
    return _table(["id", "lang", "title", "url"], rows)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write(folder: Path, data: dict, articles: list[list[str]], sources: dict):
    folder.mkdir(parents=True, exist_ok=True)
    contents = {"territorios.json": territories_json(data), **tables(data),
                "wikipedia.csv": wikipedia_csv(articles)}
    for name, text in contents.items():
        (folder / name).write_text(text, encoding="utf-8")
    manifest = {"schema": data["schema"], "reference_date": data["reference_date"], "sources": sources,
                "files": {name: _sha(text) for name, text in sorted(contents.items())}}
    (folder / "manifiesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")


def check(folder: Path) -> list[str]:
    """Problems found in an existing datos/ folder (empty list if it is consistent)."""
    problems = []
    manifest = json.loads((folder / "manifiesto.json").read_text(encoding="utf-8"))
    data = json.loads((folder / "territorios.json").read_text(encoding="utf-8"))
    Catalog(data)  # validates ids, levels, parents and codes
    if (folder / "territorios.json").read_text(encoding="utf-8") != territories_json(data):
        problems.append("territorios.json is not in canonical form")
    for name, text in tables(data).items():
        if (folder / name).read_text(encoding="utf-8") != text:
            problems.append(f"{name} does not match territorios.json")
    for name, digest in manifest["files"].items():
        if _sha((folder / name).read_text(encoding="utf-8")) != digest:
            problems.append(f"{name} does not match manifiesto.json")
    return problems
