"""Wikidata (CC0): identifiers, names by language and Wikipedia articles."""
from __future__ import annotations

import json
from urllib.parse import unquote

LANGS = ("es", "ca", "gl", "eu", "oc", "en", "ast", "an")
ENDPOINT = "https://query.wikidata.org/sparql"

# Spanish territories: municipalities by their 5-digit INE code (P772 also holds 2- and 11-digit
# codes) and communities and provinces by ISO 3166-2.
_SPAIN = """
  { ?item wdt:P772 ?ine . FILTER(STRLEN(?ine) = 5) }
  UNION
  { ?item wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "ES-")) }
"""
_COUNTRIES = "?item wdt:P297 ?alpha2 ."

_SPAIN_CODES = """SELECT ?item ?ine ?iso ?nuts ?lau ?osm ?geonames ?end WHERE {{
  {items}
  OPTIONAL {{ ?item wdt:P605 ?nuts }} OPTIONAL {{ ?item wdt:P782 ?lau }}
  OPTIONAL {{ ?item wdt:P402 ?osm }} OPTIONAL {{ ?item wdt:P1566 ?geonames }}
  OPTIONAL {{ ?item wdt:P576 ?end }}
}}"""
_COUNTRY_CODES = f"""SELECT ?item ?alpha2 ?alpha3 ?numeric ?osm ?geonames ?end WHERE {{
  {_COUNTRIES}
  OPTIONAL {{ ?item wdt:P298 ?alpha3 }} OPTIONAL {{ ?item wdt:P299 ?numeric }}
  OPTIONAL {{ ?item wdt:P402 ?osm }} OPTIONAL {{ ?item wdt:P1566 ?geonames }}
  OPTIONAL {{ ?item wdt:P576 ?end }}
}}"""


def queries(extra_qids=()) -> dict[str, str]:
    """One query for the codes and one per language for labels and articles: a single big query
    times out on the public endpoint and comes back cut off. extra_qids: Spanish items without an
    INE or ISO code (the islands), by their QID."""
    spain = _SPAIN
    if extra_qids:
        spain += f"  UNION\n  {{ VALUES ?item {{ {' '.join('wd:' + q for q in extra_qids)} }} }}\n"
    result = {}
    for prefix, items, codes in (("spain", spain, _SPAIN_CODES.format(items=spain)),
                                 ("country", _COUNTRIES, _COUNTRY_CODES)):
        result[f"{prefix}_codes"] = codes
        for lang in LANGS:
            result[f"{prefix}_labels_{lang}"] = f"""SELECT ?item ?label WHERE {{
  {items}
  ?item rdfs:label ?label . FILTER(LANG(?label) = "{lang}")
}}"""
            result[f"{prefix}_articles_{lang}"] = f"""SELECT ?item ?article WHERE {{
  {items}
  ?article schema:about ?item ; schema:isPartOf <https://{lang}.wikipedia.org/> .
}}"""
    return result


def _value(binding: dict, key: str) -> str | None:
    return binding[key]["value"] if key in binding else None


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def parse(results: dict[str, bytes], prefix: str) -> dict[str, dict]:
    """Items by QID: {"codes": {property: set}, "dissolved": bool, "labels": {lang: str},
    "articles": {lang: title}}."""
    items: dict[str, dict] = {}

    def item(uri):
        return items.setdefault(_qid(uri), {"codes": {}, "dissolved": False, "labels": {}, "articles": {}})

    for binding in json.loads(results[f"{prefix}_codes"])["results"]["bindings"]:
        entry = item(_value(binding, "item"))
        for key in ("ine", "iso", "nuts", "lau", "osm", "geonames", "alpha2", "alpha3", "numeric"):
            value = _value(binding, key)
            if value:
                entry["codes"].setdefault(key, set()).add(value)
        if _value(binding, "end"):
            entry["dissolved"] = True
    keys = sorted(results)
    labels = [b for k in keys if k.startswith(f"{prefix}_labels") for b in json.loads(results[k])["results"]["bindings"]]
    articles = [b for k in keys if k.startswith(f"{prefix}_articles") for b in json.loads(results[k])["results"]["bindings"]]
    for binding in labels:
        label = binding["label"]
        item(_value(binding, "item"))["labels"][label["xml:lang"]] = label["value"]
    for binding in articles:
        url = _value(binding, "article")
        lang = url.split("//", 1)[1].split(".", 1)[0]
        title = url.rsplit("/wiki/", 1)[-1]
        item(_value(binding, "item"))["articles"][lang] = unquote(title).replace("_", " ")
    return items


def to_jsonable(items: dict[str, dict]) -> dict[str, dict]:
    """Same structure with sorted lists instead of sets (for fixtures)."""
    return {q: {**v, "codes": {k: sorted(s) for k, s in v["codes"].items()}} for q, v in sorted(items.items())}


def from_jsonable(items: dict[str, dict]) -> dict[str, dict]:
    return {q: {**v, "codes": {k: set(s) for k, s in v["codes"].items()}} for q, v in items.items()}
