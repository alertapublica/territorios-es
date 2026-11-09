"""Shared cases (casos.json), run against the fixture data. js/*.test.mjs runs the same cases."""
import json
import unittest

from pruebas import ROOT
from territorios_es import Catalog, combine, relation
from territorios_es.relation import relate_name
from territorios_es.text import display_name, normalize

CASES = json.loads((ROOT / "pruebas" / "casos.json").read_text(encoding="utf-8"))
CATALOG = Catalog(json.loads((ROOT / "pruebas" / "datos" / "territorios.json").read_text(encoding="utf-8")))


class SharedCases(unittest.TestCase):
    def test_normalize(self):
        for text, expected in CASES["normalize"]:
            self.assertEqual(normalize(text), expected, text)

    def test_display_name(self):
        for official, expected in CASES["display_name"]:
            self.assertEqual(display_name(official), expected, official)

    def test_resolve(self):
        for system, code, expected, ancestors in CASES["resolve"]:
            found = CATALOG.resolve(system, code)
            self.assertEqual((found["id"], found["ancestors"]) if found else (None, None),
                             (expected, ancestors), (system, code))

    def test_name(self):
        for identity, lang, short, expected in CASES["name"]:
            self.assertEqual(CATALOG.name(identity, lang, short), expected, (identity, lang, short))

    def test_search(self):
        for text, within, levels, expected in CASES["search"]:
            found = [[c["id"], c["reason"]] for c in CATALOG.search(text, within=within, levels=levels)]
            self.assertEqual(found, expected, text)

    def test_mentions(self):
        for text, levels, expected in CASES["mentions"]:
            options = {"levels": levels} if levels else {}
            found = [[m["text"], [c["id"] for c in m["candidates"]]] for m in CATALOG.mentions(text, **options)]
            self.assertEqual(found, expected, text)

    def test_relate_name(self):
        for text, within, levels, status, territory, candidates, reason in CASES["relate_name"]:
            found = relate_name(CATALOG, text, within=within, levels=levels)
            self.assertEqual((found["status"], found["territory"], found["candidates"], found["reason"]),
                             (status, territory, candidates, reason), text)


class Relations(unittest.TestCase):
    def test_combine(self):
        a = relation("resolved", "es:municipio:32054", ["es:municipio:32054"])
        b = relation("pending", None, ["es:municipio:32054", "es:provincia:32"])
        c = relation("resolved", "es:provincia:32", ["es:provincia:32"])
        nothing = relation("pending", None, [], "not_found")
        self.assertEqual(combine(a, b)["status"], "resolved")
        self.assertEqual(combine(a, nothing)["territory"], "es:municipio:32054")
        self.assertEqual(combine(a, c)["status"], "conflict")
        self.assertEqual(combine(b, b)["status"], "pending")
        self.assertEqual(combine(nothing)["status"], "pending")
        self.assertEqual(combine(a, relation("conflict", None, ["x"]))["status"], "conflict")
        with self.assertRaises(ValueError):
            relation("resolved")


class CatalogValidation(unittest.TestCase):
    def test_rejects_repeated_codes_and_unknown_parents(self):
        base = {"schema": 1, "territories": [
            {"id": "a", "level": "country", "parent": None, "codes": {"x": "1"}, "names": {"official": "A", "display": "A"}}]}
        Catalog(base)
        twice = {**base, "territories": base["territories"] * 2}
        self.assertRaises(ValueError, Catalog, twice)
        orphan = {**base, "territories": [{**base["territories"][0], "parent": "z"}]}
        self.assertRaises(ValueError, Catalog, orphan)
        self.assertRaises(ValueError, Catalog, {"schema": 2, "territories": []})

    def test_within_must_exist(self):
        self.assertRaises(ValueError, CATALOG.search, "Ourense", within="es:provincia:99")


if __name__ == "__main__":
    unittest.main()
