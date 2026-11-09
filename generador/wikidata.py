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

_LANG_FILTER = ", ".join(f'"{lang}"' for lang in LANGS)
_WIKIS = " ".join(f"<https://{lang}.wikipedia.org/>" for lang in LANGS)


def queries() -> dict[str, str]:
    return {
        "spain_codes": f"""SELECT ?item ?ine ?iso ?nuts ?lau ?osm ?geonames ?end WHERE {{
  {_SPAIN}
  OPTIONAL {{ ?item wdt:P605 ?nuts }} OPTIONAL {{ ?item wdt:P782 ?lau }}
  OPTIONAL {{ ?item wdt:P402 ?osm }} OPTIONAL {{ ?item wdt:P1566 ?geonames }}
  OPTIONAL {{ ?item wdt:P576 ?end }}
}}""",
        "spain_labels": f"""SELECT ?item ?label WHERE {{
  {_SPAIN}
  ?item rdfs:label ?label . FILTER(LANG(?label) IN ({_LANG_FILTER}))
}}""",
        "spain_articles": f"""SELECT ?item ?article WHERE {{
  {_SPAIN}
  ?article schema:about ?item ; schema:isPartOf ?wiki . VALUES ?wiki {{ {_WIKIS} }}
}}""",
        "country_codes": f"""SELECT ?item ?alpha2 ?alpha3 ?numeric ?osm ?geonames ?end WHERE {{
  {_COUNTRIES}
  OPTIONAL {{ ?item wdt:P298 ?alpha3 }} OPTIONAL {{ ?item wdt:P299 ?numeric }}
  OPTIONAL {{ ?item wdt:P402 ?osm }} OPTIONAL {{ ?item wdt:P1566 ?geonames }}
  OPTIONAL {{ ?item wdt:P576 ?end }}
}}""",
        "country_labels": f"""SELECT ?item ?label WHERE {{
  {_COUNTRIES}
  ?item rdfs:label ?label . FILTER(LANG(?label) IN ({_LANG_FILTER}))
}}""",
        "country_articles": f"""SELECT ?item ?article WHERE {{
  {_COUNTRIES}
  ?article schema:about ?item ; schema:isPartOf ?wiki . VALUES ?wiki {{ {_WIKIS} }}
}}""",
    }


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
    for binding in json.loads(results[f"{prefix}_labels"])["results"]["bindings"]:
        label = binding["label"]
        item(_value(binding, "item"))["labels"][label["xml:lang"]] = label["value"]
    for binding in json.loads(results[f"{prefix}_articles"])["results"]["bindings"]:
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
