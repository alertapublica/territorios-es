"""python -m generador [--salida datos] [--informe informe.md] [--cache DIR]
python -m generador --check [--salida datos]
python -m generador --fixture   (rebuilds pruebas/datos from pruebas/fuentes, offline)
python -m generador --limites limites-municipios.geojson.gz [--salida datos] [--cache DIR]
python -m generador --codigos-postales [--salida datos] [--informe informe.md] [--cache DIR]

Downloads go to third-party servers: run it in GitHub Actions, not on a personal connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from . import catastro, codigos_postales, descargas, eurostat, ign, ine, wikidata  # noqa: E402
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

    c = config["ine_poblacion"]
    got = descargas.fetch(c["tables_url"], cache=cache, cache_name="ine_poblacion_tablas.json",
                          validate=lambda content: ine.population_tables(content, c["table_code"]))
    tables = ine.population_tables(got.content, c["table_code"])
    expected = len(load_hand_lists(FUENTES)["provinces"])
    if len(tables) != expected:
        raise ValueError(f"INE: {len(tables)} tablas de población por provincia, se esperaban {expected}")
    answers, population, dates = [got], {}, set()
    for table in tables:
        got = descargas.fetch(c["data_url"].format(table=table), cache=cache,
                              cache_name=f"ine_poblacion_{table}.json", validate=ine.parse_population)
        answers.append(got)
        values, date = ine.parse_population(got.content)
        if population.keys() & values.keys():
            raise ValueError(f"INE: la tabla de población {table} repite códigos de otra")
        population.update(values)
        dates.add(date)
    if len(dates) != 1:
        raise ValueError(f"INE: tablas de población con fechas distintas: {sorted(dates)}")
    inputs["ine_population"] = {"date": next(iter(dates)), "values": population}
    # One manifest entry for the 1 + N answers: the digest covers all of them, in order.
    records["ine_poblacion"] = {
        "url": c["data_url"].format(table="…") + f" ({len(tables)} tablas de {c['tables_url']})",
        "sha256": hashlib.sha256("".join(a.sha256 for a in answers).encode()).hexdigest(),
        "bytes": sum(len(a.content) for a in answers), "retrieved": answers[0].retrieved,
        "reference_date": next(iter(dates)), "licence": c["licence"], "attribution": c["attribution"]}

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


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f} min".replace(".", ",")


def _joined(url: str, answers: list, **extra) -> dict:
    """One manifest entry for several answers: the digest covers all of them, in order."""
    return {"url": url, "sha256": hashlib.sha256("".join(a.sha256 for a in answers).encode()).hexdigest(),
            "bytes": sum(a.bytes for a in answers), "retrieved": answers[0].retrieved, **extra}


class _Seen:
    """What the manifest needs from a download, without keeping its content in memory."""

    def __init__(self, got):
        self.sha256, self.bytes, self.retrieved = got.sha256, len(got.content), got.retrieved


def download_postal_codes(cache: Path | None, workers: int = 3) -> tuple[dict, dict, dict]:
    """(counts by source, manifest records, timings). The Catastro
    server is slow: a few connections at a time, each with the usual pause between requests."""
    config = load_hand_lists(FUENTES)["sources"]
    counts, records, timings = {}, {}, {}
    start = time.monotonic()

    c = config["catastro_direcciones"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="cp_catastro_atom.xml",
                          validate=codigos_postales.parse_catastro_feed)
    answers, files, updated = [_Seen(got)], [], codigos_postales.feed_updated(got.content)
    for office in codigos_postales.parse_catastro_feed(got.content):
        got = descargas.fetch(codigos_postales.office_feed_url(office), cache=cache,
                              cache_name=f"cp_catastro_atom_{office}.xml", validate=codigos_postales.parse_office_feed)
        answers.append(_Seen(got))
        files += codigos_postales.parse_office_feed(got.content)
    offices = len(answers) - 1
    print(f"Catastro: {offices} gerencias, {len(files)} municipios ({_minutes(time.monotonic() - start)})",
          file=sys.stderr, flush=True)

    def one(dgc: str, urls: list[str]):
        error = None
        for i, url in enumerate(urls):
            try:
                return descargas.fetch(url, cache=cache, cache_name=f"cp_catastro_{dgc}.zip",
                                       validate=codigos_postales.check_zip), i
            except RuntimeError as e:
                error = e
        raise error

    catastro, seen, failed, latin, parsing = Counter(), {}, [], 0, 0.0
    with ThreadPoolExecutor(workers) as pool:
        pending = {pool.submit(one, dgc, urls): dgc for dgc, urls in files}
        for done, future in enumerate(as_completed(pending), 1):
            dgc = pending.pop(future)
            try:
                got, encoding = future.result()
                begin = time.monotonic()
                catastro.update(codigos_postales.parse_catastro_ad(got.content))
                parsing += time.monotonic() - begin
                seen[dgc], latin = _Seen(got), latin + encoding
            except (RuntimeError, ValueError) as error:
                failed.append(f"{dgc}: {error}")
            del future
            if done % 250 == 0 or done == len(files):
                mb = sum(s.bytes for s in seen.values()) / 1e6
                print(f"Catastro: {done}/{len(files)} ZIP, {mb:.0f} MB, {_minutes(time.monotonic() - start)}",
                      file=sys.stderr, flush=True)
    counts["catastro"] = catastro
    answers += [seen[dgc] for dgc in sorted(seen)]
    records["catastro_direcciones"] = _joined(
        c["url"] + f" ({len(seen)} municipios de {offices} gerencias)", answers, reference_date=updated,
        licence=c["licence"], attribution=c["attribution"])
    mb = sum(s.bytes for s in seen.values()) / 1e6
    timings["Catastro"] = (f"{_minutes(time.monotonic() - start)} ({len(seen)} ZIP, {mb:.0f} MB, {workers} a la vez; "
                           f"lectura de los GML {_minutes(parsing)}; {latin} enlaces en ISO-8859-1)")

    begin = time.monotonic()
    c = config["idena_direcciones"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="cp_idena.zip",
                          validate=lambda content: codigos_postales.check_zip(content, ".dbf"))
    counts["idena"] = codigos_postales.parse_navarra(got.content)
    records["idena_direcciones"] = got.record(licence=c["licence"], attribution=c["attribution"])
    timings["IDENA"] = _minutes(time.monotonic() - begin)

    begin = time.monotonic()
    c = config["eustat_portales"]
    counts["eustat"], answers = Counter(), []
    for province, url in sorted(c["urls"].items()):
        got = descargas.fetch(url, cache=cache, cache_name=f"cp_eustat_{province}", validate=codigos_postales.check_euskadi)
        counts["eustat"].update(codigos_postales.parse_euskadi(got.content))
        answers.append(_Seen(got))
    records["eustat_portales"] = _joined(" ".join(url for _, url in sorted(c["urls"].items())), answers,
                                         licence=c["licence"], attribution=c["attribution"])
    timings["Eustat"] = _minutes(time.monotonic() - begin)

    begin = time.monotonic()
    c = config["icgc_direcciones"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="cp_icgc_directorio.html",
                          validate=lambda content: codigos_postales.icgc_zip_url(content, c["url"]))
    url = codigos_postales.icgc_zip_url(got.content, c["url"])
    got = descargas.fetch(url, cache=cache, cache_name="cp_icgc_" + url.rsplit("/", 1)[1],
                          validate=lambda content: codigos_postales.check_zip(content, ".csv"))
    counts["icgc"] = codigos_postales.parse_icgc(got.content)
    records["icgc_direcciones"] = got.record(licence=c["licence"], attribution=c["attribution"])
    timings["ICGC"] = _minutes(time.monotonic() - begin)

    begin = time.monotonic()
    c = config["madrid_direcciones"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="cp_madrid_catalogo.json",
                          validate=lambda content: codigos_postales.madrid_csv_url(content, c["resource"]))
    url = codigos_postales.madrid_csv_url(got.content, c["resource"])
    got = descargas.fetch(url, cache=cache, cache_name="cp_madrid_" + url.rsplit("/", 1)[1],
                          validate=codigos_postales.check_madrid)
    counts["madrid"] = codigos_postales.parse_madrid(got.content)
    records["madrid_direcciones"] = got.record(licence=c["licence"], attribution=c["attribution"])
    timings["Madrid"] = _minutes(time.monotonic() - begin)

    begin = time.monotonic()
    c = config["ideib_portales"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="cp_ideib.csv", validate=codigos_postales.check_ideib)
    counts["ideib"] = codigos_postales.parse_ideib(got.content)
    records["ideib_portales"] = got.record(licence=c["licence"], attribution=c["attribution"])
    timings["IDEIB"] = _minutes(time.monotonic() - begin)

    begin = time.monotonic()
    c = config["cdau_portales"]
    got = descargas.fetch(c["url"], cache=cache, cache_name="cp_cdau.zip",
                          validate=lambda content: codigos_postales.check_zip(content, ".csv"))
    counts["cdau"] = codigos_postales.parse_cdau(got.content)
    records["cdau_portales"] = got.record(licence=c["licence"], attribution=c["attribution"])
    del got
    timings["CDAU"] = _minutes(time.monotonic() - begin)

    # The INE register: the newest edition that answers (it comes out in January and July).
    begin, c, errors = time.monotonic(), config["ine_callejero"], []
    for url in codigos_postales.ine_street_urls(c["url"], date.today().isoformat()):
        try:
            got = descargas.fetch(url, cache=cache, cache_name="cp_ine_" + url.rsplit("/", 1)[1],
                                  validate=lambda content: codigos_postales.check_zip(content, ""))
            counts["ine"] = codigos_postales.parse_ine_streets(got.content)
        except (RuntimeError, ValueError) as error:
            errors.append(f"{url.rsplit('/', 1)[1]}: {error}")
            continue
        records["ine_callejero"] = got.record(licence=c["licence"], attribution=c["attribution"])
        timings["INE"] = f"{_minutes(time.monotonic() - begin)} ({url.rsplit('/', 1)[1]})"
        break
    else:
        failed.append("INE: " + "; ".join(errors))
    timings["total"] = _minutes(time.monotonic() - start)
    if failed:
        timings["descargas fallidas"] = f"{len(failed)}: " + "; ".join(sorted(failed)[:20])
    return counts, records, timings


def postal_codes_file(salida: Path, informe: Path | None, cache: Path | None) -> int:
    """datos/codigos-postales.csv, its observations and its report, linked with the identifiers of
    salida/territorios.json. Nothing is written if a download failed: the previous table stays."""
    counts, records, timings = download_postal_codes(cache)
    data = json.loads((salida / "territorios.json").read_text(encoding="utf-8"))
    previous = codigos_postales.read_table(salida / codigos_postales.FILE)
    rows, observations, report = codigos_postales.build(counts, data, previous)
    problems = codigos_postales.check_cases(rows)
    for problem in problems:
        report.add("Códigos postales: casos fijos que fallan", problem)
    for key, value in timings.items():
        report.summary[f"tiempo: {key}" if key != "descargas fallidas" else key] = value
    write_postal = "descargas fallidas" not in timings
    if write_postal:
        codigos_postales.write(salida, rows, observations, records)
    text = report.markdown().replace("# Informe del generador", "# Informe de códigos postales", 1)
    if informe:
        informe.write_text(text, encoding="utf-8")
    print(text)
    return 0 if write_postal and not problems else 1


def fixture():
    folder = ROOT / "pruebas" / "fuentes"
    inputs = json.loads((folder / "entrada.json").read_text(encoding="utf-8"))
    inputs["wikidata_spain"] = wikidata.from_jsonable(inputs["wikidata_spain"])
    inputs["wikidata_countries"] = wikidata.from_jsonable(inputs["wikidata_countries"])
    data, report, articles = build(inputs, FUENTES, "2026-01-01")
    write(ROOT / "pruebas" / "datos", data, articles, {"fixture": {"url": "pruebas/fuentes/entrada.json"}})
    (ROOT / "pruebas" / "datos" / "informe.md").write_text(report.markdown(), encoding="utf-8")
    # Postal codes: invented counts in the shape of the readers' output.
    raw = json.loads((folder / "codigos-postales.json").read_text(encoding="utf-8"))
    counts = {source: Counter({(code, number): n for code, number, n in raw[source]}) for source in raw}
    rows, observations, report = codigos_postales.build(counts, data)
    codigos_postales.write(ROOT / "pruebas" / "datos", rows, observations, {"fixture_codigos_postales": {
        "url": "pruebas/fuentes/codigos-postales.json"}})
    text = report.markdown().replace("# Informe del generador", "# Informe de códigos postales", 1)
    (ROOT / "pruebas" / "datos" / "informe-codigos-postales.md").write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, default=ROOT / "datos")
    parser.add_argument("--informe", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--limites", type=Path)
    parser.add_argument("--codigos-postales", action="store_true")
    args = parser.parse_args(argv)
    if args.limites:
        limits_file(args.limites, args.salida, args.cache)
        return 0
    if args.codigos_postales:
        return postal_codes_file(args.salida, args.informe, args.cache)
    if args.check:
        problems = check(args.salida)
        # The fixed cases of the real postal codes (the test fixture has other, invented ones).
        try:
            rows = codigos_postales.read_table(args.salida / codigos_postales.FILE)
        except ValueError:
            rows = None  # check() already reports it
        if rows is not None:
            problems += codigos_postales.check_cases(rows)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    if args.fixture:
        fixture()
        return 0
    inputs, records = download_all(args.cache)
    reference = load_hand_lists(FUENTES)["sources"]["ine_municipios"]["reference_date"]
    data, report, articles = build(inputs, FUENTES, reference)
    for orphan in codigos_postales.orphans(args.salida / codigos_postales.FILE, data):
        report.add("Códigos postales: municipios que ya no existen", orphan)
    write(args.salida, data, articles, records)
    text = report.markdown()
    if args.informe:
        args.informe.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
