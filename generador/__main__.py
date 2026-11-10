"""python -m generador [--salida datos] [--informe informe.md] [--cache DIR]
python -m generador --check [--salida datos]
python -m generador --fixture   (rebuilds pruebas/datos from pruebas/fuentes, offline)
python -m generador --limites limites-municipios.geojson.gz [--salida datos] [--cache DIR]

Downloads go to third-party servers: run it in GitHub Actions, not on a personal connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from . import catastro, descargas, eurostat, ign, ine, wikidata  # noqa: E402
from .construir import build, load_hand_lists  # noqa: E402
from .exportar import check, write  # noqa: E402
from .limites import build_limits  # noqa: E402

FUENTES = ROOT / "fuentes"


def download_all(cache: Path | None) -> tuple[dict, dict]:
    """(inputs for build, source records for the manifest)."""
    config = load_hand_lists(FUENTES)["sources"]
    records, inputs = {}, {}

    c = config["ine_municipios"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="ine_municipios.xlsx")
    inputs["municipalities"] = ine.parse_municipalities(got.content, c["title_must_contain"])
    records["ine_municipios"] = got.record(reference_date=c["reference_date"], licence=c["licence"],
                                           attribution=c["attribution"])

    c = config["ine_islas"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="ine_islas.xlsx")
    inputs["ine_islands"], date = ine.parse_islands(got.content)
    records["ine_islas"] = got.record(reference_date=date, licence=c["licence"], attribution=c["attribution"])

    c = config["ine_cambios"]
    try:
        got = descargas.fetch(c["url"], cache=cache, cache_name="ine_cambios.htm")
        since, changes = ine.parse_changes(got.content)
        inputs["ine_changes"] = {"since": since, "changes": changes}
        records["ine_cambios"] = got.record(reference_date=since, licence=c["licence"], attribution=c["attribution"])
    except (RuntimeError, ValueError) as error:
        print(f"Aviso: {error}", file=sys.stderr)
        inputs["ine_changes"] = None

    c = config["ine_provincias"]
    try:
        got = descargas.fetch(c["url"], cache=cache, cache_name="ine_provincias.htm")
        inputs["ine_provinces"] = ine.parse_provinces(got.content)
        records["ine_provincias"] = got.record(licence=c["licence"], attribution=c["attribution"])
    except RuntimeError as error:
        print(f"Aviso: {error}", file=sys.stderr)
        inputs["ine_provinces"] = []

    c = config["eurostat_lau"]
    page = descargas.fetch(c["page"], cache=cache, cache_name="eurostat_lau.html")
    url = eurostat.find_link(page.content, c["link_pattern"], "https://ec.europa.eu")
    got = descargas.fetch(url, cache=cache, cache_name="eurostat_lau.xlsx")
    inputs["lau"], header = eurostat.parse_lau(got.content, c["country_sheet"])
    inputs["lau_area_unit"] = "km2" if any("KM2" in h.upper() for h in header) else "m2"
    print("Columnas LAU:", header, file=sys.stderr)
    records["eurostat_lau"] = got.record(reference_date=c["reference_date"], licence=c["licence"],
                                         attribution=c["attribution"], columns=header)

    c = config["catastro"]
    got = descargas.fetch(c["provinces_url"], cache=cache, cache_name="catastro_provincias.xml",
                          validate=catastro.parse_provinces)
    provinces = catastro.parse_provinces(got.content)
    answers = [got]
    inputs["catastro"] = []
    for code, name in provinces:
        got = descargas.fetch(catastro.municipalities_url(name), cache=cache,
                              cache_name=f"catastro_municipios_{code}.xml", validate=catastro.parse_municipalities)
        answers.append(got)
        inputs["catastro"] += catastro.parse_municipalities(got.content)
    inputs["catastro_provinces"] = [code for code, _ in provinces]
    # One manifest entry for the 1 + N answers: the digest covers all of them, in order.
    records["catastro"] = {
        "url": c["municipalities_url"] + f" ({len(provinces)} provincias)",
        "sha256": hashlib.sha256("".join(a.sha256 for a in answers).encode()).hexdigest(),
        "bytes": sum(len(a.content) for a in answers), "retrieved": answers[0].retrieved,
        "licence": c["licence"], "attribution": c["attribution"]}

    c = config["ign_poblaciones"]
    answers, rows, counts = [], [], []
    for other, name in ((False, "ign_poblaciones"), (True, "ign_otras_capitales")):
        found, offset = [], 0
        while True:
            got = descargas.fetch(ign.populations_url(offset, other=other), cache=cache,
                                  cache_name=f"{name}_{offset}.json", validate=ign.parse_populations)
            page, matched = ign.parse_populations(got.content)
            answers.append(got)
            found += page
            offset += ign.PAGE
            if offset >= matched:
                break
            if not page:
                raise ValueError(f"IGN: página vacía en {offset} de {matched}")
        if len(found) != matched:
            raise ValueError(f"IGN: {len(found)} poblaciones de {matched}")
        rows += found
        counts.append(matched)
    inputs["ign_capitals"] = ign.municipal_capitals(rows)
    records["ign_poblaciones"] = {
        "url": f"{ign.POPULATIONS_URL} ({counts[0]} núcleos) y {ign.OTHER_POPULATIONS_URL}?capital="
               f"{ign.OTHER_CAPITALS} ({counts[1]} capitales que no son núcleos); {len(answers)} páginas",
        "sha256": hashlib.sha256("".join(a.sha256 for a in answers).encode()).hexdigest(),
        "bytes": sum(len(a.content) for a in answers), "retrieved": answers[0].retrieved,
        "licence": c["licence"], "attribution": c["attribution"]}

    c = config["ign_limites"]
    got = download_limits(cache)
    inputs["ign_units"] = ign.parse_units(got.content)
    records["ign_limites"] = got.record(licence=c["licence"], attribution=c["attribution"])

    c = config["wikidata"]
    raw = {}
    islands = [row["wikidata"] for row in load_hand_lists(FUENTES)["islands"] if row["wikidata"]]
    for key, query in wikidata.queries(islands).items():
        got = descargas.fetch(c["url"], data={"query": query}, accept="application/sparql-results+json",
                              cache=cache, cache_name=f"wikidata_{key}.json", validate=json.loads)
        raw[key] = got.content
        records[f"wikidata_{key}"] = got.record(licence=c["licence"], attribution=c["attribution"])
        records[f"wikidata_{key}"]["url"] = c["url"] + " (SPARQL: " + key + ")"
    inputs["wikidata_spain"] = wikidata.parse(raw, "spain")
    inputs["wikidata_countries"] = wikidata.parse(raw, "country")
    return inputs, records


def download_limits(cache: Path | None):
    return descargas.fetch(ign.LIMITS_URL, cache=cache, cache_name="ign_limites.zip",
                           validate=ign.check_zip)


def limits_file(path: Path, salida: Path, cache: Path | None):
    """Boundaries file for a release, linked with the identifiers of salida/territorios.json."""
    config = load_hand_lists(FUENTES)["sources"]["ign_limites"]
    got = download_limits(cache)
    data = json.loads((salida / "territorios.json").read_text(encoding="utf-8"))
    content, counts = build_limits(ign.parse_units(got.content), data, got.record(attribution=config["attribution"]))
    path.write_bytes(content)
    print(json.dumps({**counts, "bytes_gzip": len(content)}, ensure_ascii=False))


def fixture():
    folder = ROOT / "pruebas" / "fuentes"
    inputs = json.loads((folder / "entrada.json").read_text(encoding="utf-8"))
    inputs["wikidata_spain"] = wikidata.from_jsonable(inputs["wikidata_spain"])
    inputs["wikidata_countries"] = wikidata.from_jsonable(inputs["wikidata_countries"])
    data, report, articles = build(inputs, FUENTES, "2026-01-01")
    write(ROOT / "pruebas" / "datos", data, articles, {"fixture": {"url": "pruebas/fuentes/entrada.json"}})
    (ROOT / "pruebas" / "datos" / "informe.md").write_text(report.markdown(), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=ROOT / "datos")
    parser.add_argument("--informe", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--limites", type=Path)
    args = parser.parse_args(argv)
    if args.limites:
        limits_file(args.limites, args.salida, args.cache)
        return 0
    if args.check:
        problems = check(args.salida)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    if args.fixture:
        fixture()
        return 0
    inputs, records = download_all(args.cache)
    reference = load_hand_lists(FUENTES)["sources"]["ine_municipios"]["reference_date"]
    data, report, articles = build(inputs, FUENTES, reference)
    write(args.salida, data, articles, records)
    text = report.markdown()
    if args.informe:
        args.informe.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
