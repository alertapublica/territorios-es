"""python -m generador [--salida datos] [--informe informe.md] [--cache DIR]
python -m generador --check [--salida datos]
python -m generador --fixture   (rebuilds pruebas/datos from pruebas/fuentes, offline)

Downloads go to third-party servers: run it in GitHub Actions, not on a personal connection.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from . import descargas, eurostat, ine, wikidata  # noqa: E402
from .construir import build, load_hand_lists  # noqa: E402
from .exportar import check, write  # noqa: E402

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

    c = config["wikidata"]
    raw = {}
    for key, query in wikidata.queries().items():
        got = descargas.fetch(c["url"], data={"query": query}, accept="application/sparql-results+json",
                              cache=cache, cache_name=f"wikidata_{key}.json")
        raw[key] = got.content
        records[f"wikidata_{key}"] = got.record(licence=c["licence"], attribution=c["attribution"])
        records[f"wikidata_{key}"]["url"] = c["url"] + " (SPARQL: " + key + ")"
    inputs["wikidata_spain"] = wikidata.parse(raw, "spain")
    inputs["wikidata_countries"] = wikidata.parse(raw, "country")
    return inputs, records


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
    args = parser.parse_args(argv)
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
