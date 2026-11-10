"""Joins the downloaded sources and the hand-reviewed lists in fuentes/ into the catalogue.

Each datum comes from its owner (design §5): INE for codes and official names, Eurostat for NUTS
and LAU, ISO codes from the reviewed list, Wikidata for names in other languages and links. What
does not match is written to the report; nothing is chosen silently.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from territorios_es import geo
from territorios_es.text import ARTICLES, display_name, drop_article, flip_article, normalize, slugify

from .catastro import FORAL
from .eurostat import ine_code
from .wikidata import LANGS

UI_LANGS = ("es", "ca", "gl", "eu", "oc", "en")


class Report:
    """Discrepancies and notes, grouped by section."""

    def __init__(self):
        self.sections: dict[str, list[str]] = {}
        self.summary: dict[str, int | str] = {}

    def add(self, section: str, message: str):
        self.sections.setdefault(section, []).append(message)

    def markdown(self, limit: int = 60) -> str:
        lines = ["# Informe del generador", ""]
        lines += [f"- {key}: {value}" for key, value in self.summary.items()]
        if not self.sections:
            lines += ["", "Sin discrepancias."]
        for section, messages in sorted(self.sections.items()):
            lines += ["", f"## {section} ({len(messages)})", ""]
            lines += [f"- {m}" for m in sorted(messages)[:limit]]
            if len(messages) > limit:
                lines.append(f"- … y {len(messages) - limit} más")
        return "\n".join(lines) + "\n"


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_hand_lists(folder: Path) -> dict:
    return {
        "communities": _csv(folder / "comunidades.csv"),
        "community_names": _csv(folder / "nombres-comunidades.csv"),
        "provinces": _csv(folder / "provincias.csv"),
        "islands": _csv(folder / "islas.csv"),
        "parts": _csv(folder / "partes-bilingues.csv"),
        "aliases": _csv(folder / "alias.csv"),
        "eu": _csv(folder / "paises-ue.csv"),
        "not_countries": _csv(folder / "paises-excluidos.csv"),
        "discarded_labels": _csv(folder / "descartes-wikidata.csv"),
        "sources": json.loads((folder / "fuentes.json").read_text(encoding="utf-8")),
    }


def _single(item: dict, key: str, label: str, identity: str, report: Report) -> str | None:
    values = sorted(item["codes"].get(key, ()))
    if len(values) > 1:
        report.add("Wikidata: varios valores", f"{identity}: {label} {', '.join(values)}")
        return None
    return values[0] if values else None


# The Catastro services cut names at 30 characters and often write the article at the end
# («COVES DE VINROMA LES») or leave it out («BLAZQUEZ»).
CATASTRO_NAME_LENGTH = 30
_LOWER_ARTICLES = {a.lower() for group in ARTICLES.values() for a in group}


def _catastro_key(text: str) -> str:
    key = normalize(text.lower())  # lower case first, so that «PUEBLA, LA» flips its article
    key = drop_article(key) or key
    words = key.split(" ")
    return " ".join(words[:-1]) if len(words) > 1 and words[-1] in _LOWER_ARTICLES else key


def catastro_name_matches(dgc_name: str, names: dict) -> bool:
    """Whether the Catastro writes one of the names we have, allowing for its cut and its
    articles. Only a cross-check: the link itself is by code."""
    forms = [names["official"], names["display"], *names.get("lang", {}).values(),
             *(a["name"] for a in names.get("aliases", []))]
    parts = list(names.get("parts", {}).values())
    if len(parts) == 2:
        forms += [f"{parts[0]}/{parts[1]}", f"{parts[1]}/{parts[0]}", *parts]
    target = _catastro_key(dgc_name)
    keys = {_catastro_key(form) for form in forms}
    if len(dgc_name) >= CATASTRO_NAME_LENGTH - 1:  # a cut on a space loses the space
        cut = normalize(dgc_name.lower())
        return any(normalize(form.lower()).startswith(cut) or key.startswith(target) for form, key in
                   zip(forms, map(_catastro_key, forms)))
    return target in keys


def _other_names(item: dict | None, known: set[str], identity: str, discarded: set) -> dict[str, str]:
    """Wikidata labels that differ from the names we already have, minus the ones discarded by
    hand (fuentes/descartes-wikidata.csv)."""
    if not item:
        return {}
    return {lang: label for lang, label in sorted(item["labels"].items())
            if lang in LANGS and normalize(label) not in known and (identity, lang, label) not in discarded}


def _attach_wikidata(record: dict, item: dict | None, qid: str | None, report: Report):
    """QID, OSM and GeoNames of the item; nothing if the item already belongs to another territory."""
    if not item or not qid:
        return
    record["codes"]["wikidata"] = qid
    for key, system, label in (("osm", "osm:relation", "OSM"), ("geonames", "geonames", "GeoNames")):
        value = _single(item, key, label, record["id"], report)
        if value:
            record["codes"][system] = value


def _pick(qids: list[str], items: dict, key: str, report: Report, section: str) -> str | None:
    """The only current item for a code; several are reported and none is chosen."""
    current = [q for q in qids if not items[q]["dissolved"]]
    if len(current) == 1:
        return current[0]
    if len(current) > 1:
        report.add(section, f"{key}: varios elementos {', '.join(sorted(current))}; no se enlaza")
    return None


def ign_name_matches(label: str, names: dict) -> bool:
    """Whether the IGN writes one of the names we have (it puts the article in front)."""
    forms = [names["official"], names["display"], *names.get("parts", {}).values()]
    parts = list(names.get("parts", {}).values())
    if len(parts) == 2:
        forms += [f"{parts[0]}/{parts[1]}", f"{parts[1]}/{parts[0]}"]
    return normalize(label) in {normalize(form) for form in forms}


def _attach_ign(record: dict, ccaa: str, units: list[list], capitals: list[list], have_units: bool,
                have_capitals: bool, report: Report):
    """BDDAE code and capital of a municipality, cross-checked with each other."""
    identity, display = record["id"], record["names"]["display"]
    code = record["codes"]["ine:municipio"]
    unit = None
    if len(units) > 1:
        report.add("IGN: límites", f"{identity}: varias unidades ({', '.join(u[0] for u in units)}); no se enlaza")
    elif units:
        unit = units[0]
        if unit[0][2:6] != ccaa + code[:2]:
            report.add("IGN: límites", f"{identity}: la unidad {unit[0]} no es de la comunidad {ccaa}; no se enlaza")
            unit = None
        else:
            record["codes"]["ign:bddae"] = unit[0]
            if not ign_name_matches(unit[2], record["names"]):
                report.add("IGN: nombre distinto", f"{identity} «{display}»: «{unit[2]}» ({unit[0]})")
    elif have_units:
        report.add("IGN: límites", f"{identity} «{display}» no está en los límites del IGN")
    if len(capitals) > 1:
        report.add("IGN: capitales", f"{identity}: varias capitales "
                                     f"({', '.join(c[1] for c in capitals)}); no se usa ninguna")
    elif capitals:
        _, entity, label, lon, lat, altitude = capitals[0]
        record["capital"] = {"name": label, "ine": entity, "lon": lon, "lat": lat}
        if altitude is not None:
            record["capital"]["altitude"] = altitude
        if unit and not geo.contains(unit[3], lon, lat):
            report.add("IGN: capital fuera del término",
                       f"{identity} «{display}»: «{label}» ({entity}) a {geo.distance(unit[3], lon, lat):.0f} m "
                       f"del límite")
    elif have_capitals:
        report.add("IGN: capitales", f"{identity} «{display}» sin capital en el IGN")


def build(inputs: dict, fuentes: Path, reference_date: str) -> tuple[dict, Report, list[list[str]]]:
    """(data for territorios.json, report, Wikipedia rows [id, lang, title])."""
    report = Report()
    hand = load_hand_lists(fuentes)
    spain_items = inputs["wikidata_spain"]
    country_items = inputs["wikidata_countries"]
    articles: list[list[str]] = []
    used_qids: dict[str, str] = {}

    def claim(qid: str | None, identity: str) -> str | None:
        """A QID identifies one territory; the first (highest level) keeps it."""
        if qid is None:
            return None
        if qid in used_qids:
            report.add("Wikidata: elemento compartido",
                       f"{qid} es a la vez {used_qids[qid]} y {identity}; se queda en {used_qids[qid]}")
            return None
        used_qids[qid] = identity
        return qid

    def add_articles(identity: str, item: dict | None):
        for lang, title in sorted((item or {}).get("articles", {}).items()):
            articles.append([identity, lang, title])

    # Countries -----------------------------------------------------------------------------------
    by_alpha2: dict[str, list[str]] = {}
    for qid, item in country_items.items():
        for code in item["codes"].get("alpha2", ()):
            by_alpha2.setdefault(code, []).append(qid)
    eu = {row["alpha2"]: row for row in hand["eu"]}
    not_countries = {row["alpha2"] for row in hand["not_countries"]}
    discarded = {(row["id"], row["lang"], row["label"]) for row in hand["discarded_labels"]}
    countries = []
    for code in sorted(by_alpha2):
        if code in not_countries:
            continue
        if not re.fullmatch(r"[A-Z]{2}", code):
            report.add("Países", f"Código ISO no válido en Wikidata: {code!r}")
            continue
        current = sorted((q for q in by_alpha2[code] if not country_items[q]["dissolved"]),
                         key=lambda q: int(q[1:]))
        if not current:
            continue
        if len(current) > 1:
            report.add("Países", f"{code}: varios elementos {', '.join(current)}; se usa {current[0]}")
        qid = current[0]
        item = country_items[qid]
        identity = f"pais:{code}"
        labels = {lang: item["labels"][lang] for lang in LANGS if lang in item["labels"]}
        official = labels.get("es") or labels.get("en") or code
        record = {"id": identity, "level": "country", "parent": None, "codes": {"iso3166-1:alpha2": code},
                  "names": {"official": official, "display": official}}
        for key, system in (("alpha3", "iso3166-1:alpha3"), ("numeric", "iso3166-1:numeric")):
            value = _single(item, key, system, identity, report)
            if value:
                record["codes"][system] = value
        _attach_wikidata(record, item, claim(qid, identity), report)
        if labels:
            record["names"]["lang"] = labels
        record["slug"] = slugify(official)
        if code in eu:
            record["eu"] = eu[code]["eu"] == "1"
            record["eea"] = eu[code]["eea"] == "1"
        countries.append(record)
        add_articles(identity, item)
    known_countries = {r["codes"]["iso3166-1:alpha2"] for r in countries}
    if "ES" not in known_countries:
        raise ValueError("Spain is missing from the Wikidata countries")
    for code in sorted(set(eu) - known_countries):
        raise ValueError(f"EU/EEA country {code} missing from Wikidata")

    # Spanish items by code -------------------------------------------------------------------------
    by_iso: dict[str, list[str]] = {}
    by_ine: dict[str, list[str]] = {}
    for qid, item in spain_items.items():
        for code in item["codes"].get("iso", ()):
            by_iso.setdefault(code, []).append(qid)
        for code in item["codes"].get("ine", ()):
            by_ine.setdefault(code, []).append(qid)

    aliases: dict[str, list[dict]] = {}
    for row in hand["aliases"]:
        aliases.setdefault(row["id"], []).append({"name": row["alias"], "lang": row["lang"], "kind": row["kind"]})

    # Autonomous communities ----------------------------------------------------------------------
    community_names: dict[str, dict] = {}
    for row in hand["community_names"]:
        community_names.setdefault(row["ine"], {})[row["lang"]] = row
    communities, time_zone = [], {}
    for row in hand["communities"]:
        identity = f"es:autonomia:{row['ine']}"
        names = {"official": row["official"], "display": row["display"]}
        lang = {code: n["name"] for code, n in community_names.get(row["ine"], {}).items()}
        short = {code: n["short"] for code, n in community_names.get(row["ine"], {}).items() if n["short"]}
        qid = claim(_pick(by_iso.get(row["iso3166_2"], []), spain_items, row["iso3166_2"], report,
                          "Wikidata: ISO 3166-2"), identity)
        item = spain_items.get(qid) if qid else None
        if item is None:
            report.add("Wikidata: sin elemento", f"{identity} ({row['iso3166_2']})")
        else:
            nuts = item["codes"].get("nuts", set())
            if nuts and row["nuts2"] not in nuts:
                report.add("NUTS", f"{identity}: {row['nuts2']} en fuentes/, {', '.join(sorted(nuts))} en Wikidata")
            for code in ("ast", "an"):
                if code in item["labels"]:
                    lang[code] = item["labels"][code]
        names["lang"] = dict(sorted(lang.items()))
        if short:
            names["short"] = dict(sorted(short.items()))
        if aliases.get(identity):
            names["aliases"] = aliases[identity]
        record = {"id": identity, "level": "autonomous_community", "subtype": row["subtype"], "parent": "pais:ES",
                  "codes": {"ine:autonomia": row["ine"], "iso3166-2": row["iso3166_2"], "nuts": row["nuts2"]},
                  "names": names}
        _attach_wikidata(record, item, qid, report)
        record.update(slug=slugify(row["display"]), time_zone=row["time_zone"], nuts1=row["nuts2"][:3])
        time_zone[row["ine"]] = row["time_zone"]
        communities.append(record)
        add_articles(identity, item)

    # Provinces -----------------------------------------------------------------------------------
    parts_by_id = {row["id"]: row for row in hand["parts"]}

    def parts_of(identity: str, official: str) -> dict[str, str]:
        row = parts_by_id.get(identity)
        if "/" not in official:
            if row:
                report.add("Nombres bilingües", f"{identity}: «{official}» ya no es bilingüe")
            return {}
        if not row or row["official"] != official:
            report.add("Nombres bilingües", f"{identity}: «{official}» sin idiomas revisados en fuentes/partes-bilingues.csv")
            return {}
        first, second = official.split("/", 1)
        return {row["first"]: flip_article(first), row["second"]: flip_article(second)}

    ine_provinces = {p: (c, n) for p, c, n in inputs.get("ine_provinces") or []}
    if not ine_provinces:
        report.add("INE: provincias", "No se pudo leer la tabla de provincias del INE para contrastarla")
    provinces, province_ccaa, province_nuts = [], {}, {}
    for row in hand["provinces"]:
        identity = f"es:provincia:{row['ine']}"
        if ine_provinces:
            ccaa, ine_name = ine_provinces.get(row["ine"], (None, None))
            if ccaa != row["autonomia"] or normalize(ine_name or "") != normalize(row["official"]):
                report.add("INE: provincias", f"{identity}: fuentes/ dice {row['autonomia']} «{row['official']}», "
                                              f"el INE {ccaa} «{ine_name}»")
        names = {"official": row["official"], "display": row["display"]}
        parts = parts_of(identity, row["official"])
        if parts:
            names["parts"] = parts
        qid = claim(_pick(by_iso.get(row["iso3166_2"], []), spain_items, row["iso3166_2"], report,
                          "Wikidata: ISO 3166-2"), identity) if row["iso3166_2"] else None
        item = spain_items.get(qid) if qid else None
        known = {normalize(names["official"]), normalize(names["display"]), *map(normalize, parts.values())}
        lang = _other_names(item, known, identity, discarded)
        if lang:
            names["lang"] = lang
        if aliases.get(identity):
            names["aliases"] = aliases[identity]
        codes = {"ine:provincia": row["ine"]}
        if row["iso3166_2"]:
            codes["iso3166-2"] = row["iso3166_2"]
        if row["nuts3"]:
            codes["nuts"] = row["nuts3"]
            nuts = item["codes"].get("nuts", set()) if item else set()
            if nuts and row["nuts3"] not in nuts:
                report.add("NUTS", f"{identity}: {row['nuts3']} en fuentes/, {', '.join(sorted(nuts))} en Wikidata")
        record = {"id": identity, "level": "province", "parent": f"es:autonomia:{row['autonomia']}",
                  "codes": codes, "names": names}
        _attach_wikidata(record, item, qid, report)
        record.update(slug=slugify(row["display"]), time_zone=time_zone[row["autonomia"]])
        province_ccaa[row["ine"]] = row["autonomia"]
        province_nuts[row["ine"]] = row["nuts3"]
        provinces.append(record)
        add_articles(identity, item)

    # Islands ---------------------------------------------------------------------------------------
    # Cabildos (Canarias) and consells insulars (Illes Balears) group the municipalities of their
    # province without changing their parent. Each municipality goes to its island by its NUTS 3
    # (Eurostat), except where one NUTS 3 holds two islands (Eivissa y Formentera): there
    # fuentes/islas.csv lists the municipalities of the smaller one.
    islands, island_by_code, island_by_nuts, island_nuts3 = [], {}, {}, {}
    nuts_count: dict[str, int] = {}
    for row in hand["islands"]:
        nuts_count[row["nuts3"]] = nuts_count.get(row["nuts3"], 0) + 1
    for row in hand["islands"]:
        identity, province = row["id"], row["provincia"]
        if province not in province_ccaa or province_nuts[province]:
            raise ValueError(f"{identity}: province {province} is not split into islands")
        listed = row["municipios"].split()
        for code in listed:
            if code in island_by_code:
                raise ValueError(f"{code} listed in {island_by_code[code]} and {identity}")
            island_by_code[code] = identity
        if not listed:
            if row["nuts3"] in island_by_nuts:
                raise ValueError(f"NUTS 3 {row['nuts3']} in {island_by_nuts[row['nuts3']]} and {identity}")
            island_by_nuts[row["nuts3"]] = identity
        island_nuts3[identity] = row["nuts3"]
        qid = row["wikidata"] or None
        if qid and not re.fullmatch(r"Q[1-9][0-9]*", qid):
            raise ValueError(f"{identity}: invalid QID {qid!r}")
        item = spain_items.get(qid) if qid else None
        if item is None or item["dissolved"]:
            report.add("Wikidata: sin elemento", f"{identity} ({qid or 'sin QID en fuentes/islas.csv'})")
            item = None
        qid = claim(qid, identity) if item else None
        names = {"official": row["official"], "display": row["display"]}
        lang = _other_names(item, {normalize(row["official"]), normalize(row["display"])}, identity, discarded)
        if lang:
            names["lang"] = lang
        if aliases.get(identity):
            names["aliases"] = aliases[identity]
        # The NUTS 3 is a code of the island only when it holds no other island.
        codes = {"nuts": row["nuts3"]} if nuts_count[row["nuts3"]] == 1 else {}
        nuts = item["codes"].get("nuts", set()) if item else set()
        if nuts and row["nuts3"] not in nuts:
            report.add("NUTS", f"{identity}: {row['nuts3']} en fuentes/, {', '.join(sorted(nuts))} en Wikidata")
        record = {"id": identity, "level": "island", "parent": f"es:provincia:{province}", "codes": codes,
                  "names": names, "nuts3": row["nuts3"]}
        _attach_wikidata(record, item, qid, report)
        record.update(slug=slugify(row["display"]), time_zone=time_zone[province_ccaa[province]])
        islands.append(record)
        add_articles(identity, item)
    island_provinces = {r["parent"].rsplit(":", 1)[1] for r in islands}

    # Municipalities ------------------------------------------------------------------------------
    lau_by_ine: dict[str, str] = {}
    for lau_code in inputs.get("lau") or {}:
        code = ine_code(lau_code)
        if code is None:
            report.add("Eurostat LAU", f"Código LAU sin forma INE: {lau_code}")
        elif code in lau_by_ine:
            report.add("Eurostat LAU", f"{code}: varios códigos LAU ({lau_by_ine[code]}, {lau_code})")
        else:
            lau_by_ine[code] = lau_code
    lau = inputs.get("lau") or {}
    # Catastro: the DGC gives both codes, so the link is by code; the name is only a cross-check.
    dgc_by_ine: dict[str, list[list[str]]] = {}
    for dgc, ine, dgc_name in inputs.get("catastro") or []:
        dgc_by_ine.setdefault(ine, []).append([dgc, dgc_name])
    catastro_provinces = set(inputs.get("catastro_provinces") or [])
    if dgc_by_ine:
        expected = set(province_ccaa) - set(FORAL)
        for code in sorted(expected - catastro_provinces):
            report.add("Catastro", f"es:provincia:{code} no está en el Catastro")
        for code in sorted(catastro_provinces - expected):
            report.add("Catastro", f"El Catastro da la provincia {code}, que no se esperaba")
    # IGN: capital of each municipality (núcleos marked as such) and municipal units of the BDLJE.
    capitals_by_ine: dict[str, list[list]] = {}
    for row in inputs.get("ign_capitals") or []:
        capitals_by_ine.setdefault(row[0], []).append(row)
    units_by_ine: dict[str, list[list]] = {}
    for unit in inputs.get("ign_units") or []:
        units_by_ine.setdefault(unit[0][-5:], []).append(unit)
    area_in_m2 = inputs.get("lau_area_unit", "m2") == "m2"
    municipalities, ine_codes = [], set()
    island_nuts: dict[str, set] = {}
    for code, check, official, ccaa in inputs["municipalities"]:
        identity = f"es:municipio:{code}"
        ine_codes.add(code)
        province = code[:2]
        if province_ccaa.get(province) != ccaa:
            raise ValueError(f"{identity}: community {ccaa} does not match fuentes/provincias.csv")
        display = display_name(official)
        names = {"official": official, "display": display}
        parts = parts_of(identity, official)
        if parts:
            names["parts"] = parts
        qid = claim(_pick(by_ine.get(code, []), spain_items, code, report, "Wikidata: código INE"), identity)
        item = spain_items.get(qid) if qid else None
        if item is None and code not in by_ine:
            report.add("Wikidata: sin elemento", f"{identity} «{display}»")
        known = {normalize(official), normalize(display), *map(normalize, parts.values())}
        lang = _other_names(item, known, identity, discarded)
        if lang:
            names["lang"] = lang
        if aliases.get(identity):
            names["aliases"] = aliases[identity]
        codes = {"ine:municipio": code, "ine:municipio:dc": code + check}
        record = {"id": identity, "level": "municipality", "parent": f"es:provincia:{province}",
                  "codes": codes, "names": names}
        stats = {}
        if code in lau_by_ine:
            fields = lau[lau_by_ine[code]]
            codes["lau"] = lau_by_ine[code]
            nuts3 = fields.get("nuts3")
            if nuts3:
                record["nuts3"] = nuts3
                if province_nuts[province] and nuts3 != province_nuts[province]:
                    report.add("Eurostat LAU", f"{identity}: NUTS 3 {nuts3}, su provincia {province_nuts[province]}")
                if not province_nuts[province]:
                    island_nuts.setdefault(province, set()).add(nuts3)
            if fields.get("population", "").replace(".", "", 1).isdigit():
                stats["population"] = int(float(fields["population"]))
            try:
                area = float(fields["area"])
                stats["area_km2"] = round(area / 1_000_000 if area_in_m2 else area, 3)
            except (KeyError, ValueError):
                pass
            for key in ("degurba", "coastal", "city", "fua"):
                if fields.get(key):
                    stats[key] = fields[key]
        elif lau:
            report.add("Eurostat LAU", f"{identity} «{display}» no está en la tabla LAU")
        if province in island_provinces:
            island = island_by_code.get(code) or island_by_nuts.get(record.get("nuts3"))
            if island and code in island_by_code and record.get("nuts3") not in (None, island_nuts3[island]):
                report.add("Islas", f"{identity} «{display}»: en fuentes/islas.csv con {island}, "
                                    f"pero su NUTS 3 es {record['nuts3']}")
            if island:
                record["island"] = island
            elif lau:
                report.add("Islas", f"{identity} «{display}» sin isla (NUTS 3 {record.get('nuts3')})")
        entries = dgc_by_ine.get(code, [])
        if len(entries) > 1:
            report.add("Catastro", f"{identity}: varios códigos DGC "
                                   f"({', '.join(e[0] for e in entries)}); no se enlaza")
        elif entries:
            dgc, dgc_name = entries[0]
            codes["dgc:municipio"] = dgc
            if not catastro_name_matches(dgc_name, names):
                report.add("Catastro: nombre distinto", f"{identity} «{display}»: «{dgc_name}» ({dgc})")
        elif province in catastro_provinces:
            report.add("Catastro", f"{identity} «{display}» no está en el Catastro")
        _attach_wikidata(record, item, qid, report)
        _attach_ign(record, ccaa, units_by_ine.get(code, []), capitals_by_ine.get(code, []),
                    bool(units_by_ine), bool(capitals_by_ine), report)
        record.update(slug=slugify(display), time_zone=time_zone[ccaa])
        if stats:
            record["stats"] = stats
        municipalities.append(record)
        add_articles(identity, item)

    for code in sorted(set(lau_by_ine) - ine_codes):
        fields = lau[lau_by_ine[code]]
        report.add("Eurostat LAU", f"{lau_by_ine[code]} «{fields.get('name_national', '')}» no está en el INE")
    for code in sorted(set(dgc_by_ine) - ine_codes):
        for dgc, dgc_name in dgc_by_ine[code]:
            report.add("Catastro: no está en el INE", f"{dgc} «{dgc_name}» (INE {code})")
    # A DGC code given to two municipalities identifies neither of them.
    dgc_holders: dict[str, list[dict]] = {}
    for record in municipalities:
        if "dgc:municipio" in record["codes"]:
            dgc_holders.setdefault(record["codes"]["dgc:municipio"], []).append(record)
    for dgc, records in sorted(dgc_holders.items()):
        if len(records) > 1:
            for record in records:
                del record["codes"]["dgc:municipio"]
            report.add("Catastro", f"Código DGC {dgc} en {', '.join(r['id'] for r in records)}; no se usa en ninguno")
    # Some Catastro offices (gerencias) are not provinces: Jerez, Cartagena, Gijón, Vigo, Ceuta and
    # Melilla have their own two digits, which start the DGC code and the rustic references.
    offices: dict[tuple[str, str], int] = {}
    for record in municipalities:
        dgc = record["codes"].get("dgc:municipio")
        if dgc and dgc[:2] != record["codes"]["ine:municipio"][:2]:
            key = (record["codes"]["ine:municipio"][:2], dgc[:2])
            offices[key] = offices.get(key, 0) + 1
    for (province, office), count in sorted(offices.items()):
        report.add("Notas", f"es:provincia:{province}: {count} municipio(s) con la delegación {office} del Catastro")
    for code in sorted(set(units_by_ine) - ine_codes):
        for unit_code, kind, label, _ in units_by_ine[code]:
            report.add("IGN: límites", f"{unit_code} «{label}» ({kind or 'sin tipo'}) no es un municipio del INE")
    for code in sorted(set(capitals_by_ine) - ine_codes):
        for _, entity, label, *_ in capitals_by_ine[code]:
            report.add("IGN: capitales", f"{entity} «{label}» es capital de {code}, que no está en el INE")
    for code in sorted(set(by_ine) - ine_codes):
        report.add("Wikidata: código INE", f"{code} ({', '.join(sorted(by_ine[code]))}) no está en el INE")
    for code in sorted(set(island_by_code) - ine_codes):
        report.add("Islas", f"{code} está en fuentes/islas.csv ({island_by_code[code]}) pero no en el INE")
    with_members = {r["island"] for r in municipalities if "island" in r}
    for record in islands:
        if record["id"] not in with_members:
            report.add("Islas", f"{record['id']} sin municipios")
    for province, nuts in sorted(island_nuts.items()):
        report.add("Notas", f"es:provincia:{province} reparte sus municipios en las NUTS 3 {', '.join(sorted(nuts))}")
    for identity in sorted(set(parts_by_id) - {r["id"] for r in provinces + municipalities}):
        report.add("Nombres bilingües", f"{identity} está en fuentes/partes-bilingues.csv pero no en el INE")
    # A Wikidata label that is the name of another municipality is either a real homonym or an
    # error in Wikidata: listed for review, never removed silently.
    by_name: dict[str, set[str]] = {}
    for record in municipalities:
        by_name.setdefault(normalize(record["names"]["display"]), set()).add(record["id"])
    for record in municipalities:
        for lang, label in record["names"].get("lang", {}).items():
            others = sorted(by_name.get(normalize(label), set()) - {record["id"]})
            if others:
                report.add("Wikidata: nombre de otro municipio",
                           f"{record['id']} «{record['names']['display']}»: {lang} «{label}» es también "
                           f"{', '.join(others)}")
    if len(countries) != 249:
        report.add("Países", f"{len(countries)} países en lugar de los 249 códigos asignados de ISO 3166-1")
    # A code from Wikidata that two territories share identifies neither of them.
    holders: dict[tuple[str, str], list[dict]] = {}
    for record in countries + communities + provinces + islands + municipalities:
        for system in ("osm:relation", "geonames"):
            if system in record["codes"]:
                holders.setdefault((system, record["codes"][system]), []).append(record)
    for (system, value), records in sorted(holders.items()):
        if len(records) > 1:
            for record in records:
                del record["codes"][system]
            report.add("Wikidata: código repetido",
                       f"{system} {value} en {', '.join(r['id'] for r in records)}; no se usa en ninguno")
    known_ids = {r["id"] for r in countries + communities + provinces + islands + municipalities}
    for identity in sorted(set(aliases) - known_ids):
        raise ValueError(f"Alias for unknown territory {identity}")

    report.summary.update({
        "Países": len(countries), "Comunidades y ciudades autónomas": len(communities),
        "Provincias": len(provinces), "Islas": len(islands), "Municipios": len(municipalities),
        "Municipios con Wikidata": sum("wikidata" in r["codes"] for r in municipalities),
        "Municipios con código LAU": sum("lau" in r["codes"] for r in municipalities),
        "Municipios con código DGC": sum("dgc:municipio" in r["codes"] for r in municipalities),
        "Municipios con nombre bilingüe": sum("parts" in r["names"] for r in municipalities),
        "Municipios con capital (IGN)": sum("capital" in r for r in municipalities),
        "Municipios con límites (IGN)": sum("ign:bddae" in r["codes"] for r in municipalities),
        "Municipios con isla": sum("island" in r for r in municipalities),
    })
    data = {"schema": 1, "reference_date": reference_date,
            "territories": countries + communities + provinces + islands + municipalities}
    return data, report, articles
